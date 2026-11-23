import streamlit as st
from google import genai
from google.genai import types
import streamlit.components.v1 as components
import requests
import math
import statistics
import time
import json
import re
import hmac
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import html as html_lib
import unicodedata
import uuid

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Humanizador Pro", page_icon="✍️", layout="wide")

# ==========================================
# LEE LAS CLAVES DESDE LOS SECRETOS DE STREAMLIT
# ==========================================
def leer_secreto(nombre, defecto=None):
    """Lee un secreto sin romper la app si no existe secrets.toml."""
    try:
        valor = st.secrets.get(nombre, defecto)
        return valor.strip() if isinstance(valor, str) else valor
    except Exception:
        return defecto

GEMINI_MODEL = leer_secreto("GEMINI_MODEL", "gemini-3.6-flash")

# Límite del texto de entrada (caracteres, contando espacios)
MAX_CARACTERES = 9000

# ==========================================
# PROVEEDORES DE MODELOS
# Cada proveedor se activa solo si su clave está en los Secretos de Streamlit.
# Los modelos se detectan automáticamente desde la cuenta; para fijar uno,
# agrega <PROVEEDOR>_MODEL en Secretos (por ejemplo OPENAI_MODEL = "gpt-...").
# ==========================================
PROVEEDORES = {
    # id: nombre visible, secreto de la clave, tipo de API, URL base
    "anthropic":  {"nombre": "Claude",     "clave": "ANTHROPIC_API_KEY",  "tipo": "anthropic", "base": "https://api.anthropic.com/v1"},
    "openai":     {"nombre": "ChatGPT",    "clave": "OPENAI_API_KEY",     "tipo": "openai",    "base": "https://api.openai.com/v1"},
    "deepseek":   {"nombre": "DeepSeek",   "clave": "DEEPSEEK_API_KEY",   "tipo": "openai",    "base": "https://api.deepseek.com/v1"},
    "nvidia":     {"nombre": "NVIDIA",     "clave": "NVIDIA_API_KEY",     "tipo": "openai",    "base": "https://integrate.api.nvidia.com/v1"},
    "mistral":    {"nombre": "Mistral",    "clave": "MISTRAL_API_KEY",    "tipo": "openai",    "base": "https://api.mistral.ai/v1"},
    "gemini":     {"nombre": "Gemini",     "clave": "GEMINI_API_KEY",     "tipo": "gemini",    "base": ""},
    "groq":       {"nombre": "Groq",       "clave": "GROQ_API_KEY",       "tipo": "openai",    "base": "https://api.groq.com/openai/v1"},
    "cerebras":   {"nombre": "Cerebras",   "clave": "CEREBRAS_API_KEY",   "tipo": "openai",    "base": "https://api.cerebras.ai/v1"},
    "openrouter": {"nombre": "OpenRouter", "clave": "OPENROUTER_API_KEY", "tipo": "openai",    "base": "https://openrouter.ai/api/v1"},
}
# Orden por defecto para elegir el modelo de la redacción final (mejor español primero)
ORDEN_CALIDAD = ["anthropic", "openai", "deepseek", "nvidia", "mistral", "gemini", "groq", "cerebras", "openrouter"]

# Orden por velocidad: los pasos intermedios usan primero los más rápidos
ORDEN_VELOCIDAD = ["groq", "cerebras", "gemini", "openai", "anthropic", "deepseek", "mistral", "nvidia", "openrouter"]
# Tiempo máximo por llamada (segundos). Si un modelo no responde, se pasa al siguiente.
TIEMPO_MAXIMO = {"intermedio": 30, "final": 60}
# Proveedores en pausa: {id: hora hasta la que no se usan}. Se comparte entre bloques y entre textos.
@st.cache_resource(show_spinner=False)
def _proveedores_pausados():
    return {}


PAUSADOS = _proveedores_pausados()   # sobrevive entre textos (Streamlit vuelve a correr el archivo en cada clic)
PAUSA_CUOTA = 120      # segundos sin usar un proveedor que respondió "cuota agotada"
PAUSA_LENTO = 180      # segundos sin usar un proveedor que no respondió a tiempo
PAUSA_DIARIA = 1800    # media hora sin usar un proveedor que agotó la cuota del día
MAX_ESPERAS = 2        # veces que se espera la cuota por minuto en un mismo texto
PAUSA_CLAVE = 1800     # media hora sin usar un proveedor con la clave rechazada


class ProveedorNoDisponible(RuntimeError):
    """Error que deja al proveedor en pausa: cuota agotada, lentitud o clave rechazada."""
    def __init__(self, mensaje, pausa):
        super().__init__(mensaje)
        self.pausa = pausa

CLAVES = {pid: leer_secreto(p["clave"]) for pid, p in PROVEEDORES.items()}

# Detectores con API pública. QuillBot y Grammarly no ofrecen API de detección: se revisan a mano.
GPTZERO_API_KEY = leer_secreto("GPTZERO_API_KEY")
COPYLEAKS_EMAIL = leer_secreto("COPYLEAKS_EMAIL")
COPYLEAKS_API_KEY = leer_secreto("COPYLEAKS_API_KEY")
RONDAS_DETECTOR = 3        # reescrituras como máximo tras medir (cada medición gasta créditos del detector)
OBJETIVO_IA = 0.5          # se da por logrado cuando el peor detector marca menos de 0,5% (se muestra 0%)
PARRAFOS_POR_RONDA = 8     # tope de párrafos que se reescriben en cada ronda

# Temperatura de la redacción final: más alta = elección de palabras menos previsible
TEMP_FINAL = 0.95
# Variación mínima del largo de las oraciones (desviación / promedio). Un texto de persona suele pasar de 0,5
RITMO_MINIMO = 0.50

EXCLUIDOS = ("whisper", "tts", "guard", "safeguard", "playai", "orpheus", "embed", "vision", "audio",
             "compound", "allam", "realtime", "image", "transcribe", "search", "moderation", "ocr",
             "dall", "davinci", "babbage", "turbo-instruct", "voxtral", "codestral", "computer-use", "sora",
             "-vl", "coder", "devstral", "magistral", "-tts", "omni", "edit",
             "rerank", "reward", "retriever", "parse", "clip", "safety", "vila", "kosmos", "deplot",
             "neva", "fuyu", "paligemma", "nemoretriever", "riva", "cosmos", "bge", "e5-", "arctic-embed")
# Modelos chicos: "8b", "-1.5b" (pero no "17b" ni "a3b", que son otra cosa)
PATRON_CHICO = re.compile(r"(?<![a-z0-9.])[1-9](?:\.\d)?b\b")
DEBILES = ("mini", "nano", "small", "tiny", "lite", "instant", "haiku", "ministral")
# En catálogos grandes (NVIDIA, OpenRouter, Groq, Cerebras) solo se aceptan familias de modelos de texto
FAMILIAS_TEXTO = ("llama", "mistral", "mixtral", "qwen", "deepseek", "gemma", "kimi", "glm", "nemotron",
                  "phi-", "minimax", "gpt-oss", "command", "hermes", "granite", "olmo", "jamba", "seed")
NO_TEXTO = ("pii", "gliner", "ner-", "classif", "detector", "translat", "nemoguard", "content-safety",
            "topic-control", "jailbreak", "math", "embed", "vision", "-vl", "ocr", "speech")

PREFERENCIAS = {
    "anthropic": ("sonnet", "opus", "haiku"),
    "openai": ("gpt-5", "gpt-4.1", "gpt-4o", "gpt"),
    "deepseek": ("deepseek-chat", "deepseek-v", "deepseek"),
    "mistral": ("mistral-large-latest", "mistral-medium-latest", "mistral-large", "mistral-medium", "mistral-small-latest"),
    "nvidia": ("deepseek-v3", "llama-3.3-70b", "llama-4-maverick", "qwen3-next", "mistral-medium",
               "kimi-k2", "qwen3", "mistral-large", "deepseek", "llama"),
    "groq": ("llama-3.3-70b", "llama-4-maverick", "kimi", "qwen", "llama-4", "gpt-oss-120b", "deepseek", "gpt-oss", "llama"),
    "cerebras": ("gpt-oss-120b", "qwen-3-235b", "llama-3.3-70b", "qwen", "llama"),
    "openrouter": ("deepseek", "llama-3.3-70b", "qwen3", "mistral", "gemma", "llama"),
}


def _puntaje_modelo(pid, mid, creado):
    low = mid.lower()
    debil = 1 if (PATRON_CHICO.search(low) or any(d in low for d in DEBILES)) else 0
    prefs = PREFERENCIAS.get(pid, ())
    pref = next((i for i, p in enumerate(prefs) if p in low), len(prefs))
    gratis = 0 if (pid == "openrouter" and low.endswith(":free")) else 1
    # Qwen y GLM a veces mezclan palabras en chino al escribir en español
    mezcla_idioma = 1 if any(x in low for x in ("qwen", "qwq", "glm", "minimax")) else 0
    # Los modelos que "razonan" antes de responder o que son gigantes tardan mucho más
    razonador = 1 if any(r in low for r in ("-r1", "reasoning", "thinking", "gpt-oss", "qwq")) and pid not in ("openai", "anthropic") else 0
    gigante = 1 if any(g in low for g in ("1t", "405b", "480b", "253b", "235b", "ultra")) else 0
    return (gratis, mezcla_idioma, debil, razonador, gigante, pref, -(creado or 0))


# Cambiar este número obliga a volver a detectar los modelos tras una actualización del código
VERSION_MODELOS = "v14"
# Modelos ya detectados en el hilo principal (los bloques en paralelo los leen de aquí)
MODELOS_RESUELTOS = {}


@st.cache_data(ttl=3600, show_spinner=False)
def detectar_modelos(pid, api_key, version=VERSION_MODELOS):
    """Lista de modelos de chat de la cuenta, del mejor al peor."""
    fijos = leer_secreto(f"{pid.upper()}_MODEL")
    if fijos:
        return [m.strip() for m in str(fijos).split(",") if m.strip()]
    if pid == "gemini":
        return [GEMINI_MODEL]
    p = PROVEEDORES[pid]
    if p["tipo"] == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    else:
        headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(f"{p['base']}/models", headers=headers, timeout=20)
    resp.raise_for_status()
    datos = resp.json().get("data", [])
    candidatos = []
    for item in datos:
        mid = item.get("id", "")
        low = mid.lower()
        if not mid or item.get("active", True) is False or any(x in low for x in EXCLUIDOS):
            continue
        if pid == "openai" and not low.startswith("gpt-"):
            continue
        if pid in ("nvidia", "openrouter", "groq", "cerebras"):
            if not any(f in low for f in FAMILIAS_TEXTO) or any(x in low for x in NO_TEXTO):
                continue
        creado = item.get("created") or 0
        if not creado and item.get("created_at"):
            # Claude entrega la fecha como texto: "2026-05-14T..." -> 20260514
            try:
                creado = int(str(item["created_at"])[:10].replace("-", ""))
            except ValueError:
                creado = 0
        candidatos.append((mid, creado))
    candidatos.sort(key=lambda c: _puntaje_modelo(pid, c[0], c[1]))
    return [c[0] for c in candidatos]


def _post_con_ajustes(url, headers, payload, tipo, limite=90):
    """POST que se adapta a lo que cada modelo acepta (temperatura, tokens, penalizaciones)."""
    ultimo = None
    for intento in range(5):
        resp = requests.post(url, headers=headers, json=payload, timeout=(10, limite))
        ultimo = resp
        if resp.status_code == 200:
            return resp
        texto = resp.text.lower()
        if resp.status_code == 400:
            cambiado = False
            if "penalty" in texto and ("frequency_penalty" in payload or "presence_penalty" in payload):
                payload.pop("frequency_penalty", None); payload.pop("presence_penalty", None); cambiado = True
            if ("temperature" in texto or "top_p" in texto) and ("temperature" in payload or "top_p" in payload):
                payload.pop("temperature", None); payload.pop("top_p", None); cambiado = True
            if "reasoning" in texto and "reasoning_effort" in payload:
                payload.pop("reasoning_effort", None); cambiado = True
            if "thinking" in texto and "thinking" in payload:
                payload.pop("thinking", None); cambiado = True
            if "max_tokens" in texto and "max_tokens" in payload and tipo == "openai":
                # Modelos nuevos de OpenAI usan max_completion_tokens (incluye el razonamiento)
                payload["max_completion_tokens"] = payload.pop("max_tokens") * 3; cambiado = True
            if cambiado:
                continue
        if resp.status_code == 429 and intento < 3:
            try:
                espera = float(resp.headers.get("retry-after", "0"))
            except (TypeError, ValueError):
                espera = 0
            if 0 < espera <= 4:
                time.sleep(espera + 0.5)
                continue
        break
    return ultimo


def llamar_proveedor(pid, system_prompt, user_text, temperature, limite=90):
    """Llama a un proveedor probando sus mejores modelos. Devuelve (texto, 'Proveedor (modelo)')."""
    p = PROVEEDORES[pid]
    clave = CLAVES.get(pid)
    if not clave:
        raise RuntimeError(f"{p['nombre']}: falta {p['clave']} en Secretos.")
    max_salida = max(1500, min(8000, len(user_text) // 3 + 800))

    if p["tipo"] == "gemini":
        client = genai.Client(api_key=clave, http_options=types.HttpOptions(timeout=limite * 1000))
        return llamar_gemini(client, user_text, system_prompt), f"Gemini ({GEMINI_MODEL})"

    modelos = MODELOS_RESUELTOS.get(pid) or detectar_modelos(pid, clave)
    if not modelos:
        raise RuntimeError(f"{p['nombre']}: no se encontraron modelos de texto en la cuenta.")

    ultimo_error = ""
    for modelo in modelos[:2]:
        try:
            if p["tipo"] == "anthropic":
                headers = {"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"}
                payload = {
                    "model": modelo, "max_tokens": max_salida, "system": system_prompt,
                    "messages": [{"role": "user", "content": user_text}],
                    "temperature": min(1.0, temperature),
                }
                resp = _post_con_ajustes(f"{p['base']}/messages", headers, payload, "anthropic", limite)
                if resp.status_code == 200:
                    bloques = resp.json().get("content", [])
                    contenido = "".join(b.get("text", "") for b in bloques if b.get("type") == "text")
                else:
                    contenido = ""
            else:
                headers = {"Authorization": f"Bearer {clave}", "Content-Type": "application/json"}
                if pid == "openrouter":
                    headers["X-Title"] = "Humanizador Pro"
                payload = {
                    "model": modelo,
                    "messages": [{"role": "system", "content": system_prompt},
                                 {"role": "user", "content": user_text}],
                    "temperature": temperature, "top_p": 0.95, "max_tokens": max_salida,
                }
                if pid in ("groq", "openrouter", "deepseek", "openai"):
                    payload["frequency_penalty"] = 0.25
                    payload["presence_penalty"] = 0.2
                # Si toca un modelo que razona (gpt-oss), que piense poco: responde mucho más rápido
                if "gpt-oss" in modelo.lower():
                    payload["reasoning_effort"] = "low"
                # Los modelos nuevos de DeepSeek (deepseek-flash, v4) "piensan" por defecto: gastan los
                # tokens en razonar y devuelven el texto vacío. Se apaga el modo pensamiento.
                if pid == "deepseek":
                    payload["thinking"] = {"type": "disabled"}
                resp = _post_con_ajustes(f"{p['base']}/chat/completions", headers, payload, "openai", limite)
                contenido = ""
                if resp.status_code == 200:
                    try:
                        contenido = resp.json()["choices"][0]["message"].get("content") or ""
                    except (ValueError, KeyError, IndexError):
                        contenido = ""
        except requests.Timeout:
            # Si un modelo no respondió a tiempo, el proveedor queda en pausa y se pasa al siguiente
            raise ProveedorNoDisponible(f"{p['nombre']} ({modelo}) tardó más de {limite} s en responder.", PAUSA_LENTO)
        except requests.RequestException as e:
            ultimo_error = f"{p['nombre']} ({modelo}) sin respuesta: {e}"
            continue
        contenido = quitar_razonamiento(contenido)
        if contenido:
            return contenido, f"{p['nombre']} ({modelo})"
        # La cuota y la clave son de la cuenta: no sirve probar otro modelo del mismo proveedor
        if resp.status_code == 429:
            try:
                reintento = float(resp.headers.get("retry-after", "0"))
            except (TypeError, ValueError):
                reintento = 0
            aviso429 = resp.text.lower()
            if reintento > PAUSA_CUOTA or any(x in aviso429 for x in ("per day", "tpd", "rpd", "daily")):
                # Cuota diaria (o espera larga): no sirve esperar un minuto, se usa otro proveedor
                raise ProveedorNoDisponible(f"{p['nombre']}: cuota diaria agotada.", max(reintento, PAUSA_DIARIA))
            raise ProveedorNoDisponible(f"{p['nombre']}: cuota agotada por ahora.", PAUSA_CUOTA)
        if resp.status_code in (401, 403):
            raise ProveedorNoDisponible(f"{p['nombre']}: la clave fue rechazada.", PAUSA_CLAVE)
        if resp.status_code == 402 or "insufficient balance" in resp.text.lower():
            # Saldo pagado agotado (DeepSeek, OpenAI, Anthropic): se salta este proveedor sin reintentar
            raise ProveedorNoDisponible(f"{p['nombre']}: se acabó el saldo de la cuenta. Recarga para volver a usarlo.", PAUSA_CLAVE)
        ultimo_error = (f"{p['nombre']} ({modelo}) HTTP {resp.status_code}: {resp.text[:200]}"
                        if resp.status_code != 200 else f"{p['nombre']} ({modelo}) devolvió una respuesta vacía.")
    raise RuntimeError(ultimo_error)


def quitar_razonamiento(texto):
    """Algunos modelos devuelven su razonamiento entre <think>...</think>: se elimina."""
    if not texto:
        return ""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r"^.*?</think>", "", texto, flags=re.DOTALL | re.IGNORECASE)
    return texto.strip()


# ==========================================
# LLAMADA A GEMINI CON REINTENTO ANTE ERRORES TEMPORALES
# ==========================================
def llamar_gemini(client, contents, system_instruction):
    # Gemini 3.6 Flash ya no usa temperature / top_p / top_k (Google pide quitarlos)
    # Pensamiento bajo: la reescritura no necesita razonar largo y así responde más rápido
    try:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        )
    except Exception:
        config = types.GenerateContentConfig(system_instruction=system_instruction)
    ultimo_error = None
    for intento in range(2):
        try:
            resp = client.models.generate_content(model=GEMINI_MODEL, contents=contents, config=config)
            texto = (resp.text or "").strip()
            if texto:
                return texto
            ultimo_error = RuntimeError("Gemini devolvió una respuesta vacía (posible bloqueo de contenido).")
        except Exception as e:
            ultimo_error = e
            # Si el modelo no acepta el nivel de pensamiento, se reintenta sin él
            if "thinking" in str(e).lower() and getattr(config, "thinking_config", None):
                config = types.GenerateContentConfig(system_instruction=system_instruction)
                continue
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "timeout" in str(e).lower():
                break
        if intento == 0:
            time.sleep(2)
    raise ultimo_error

# ==========================================
# CAPA A: LÓGICA DE LIMPIEZA (clean_marks + regla §8 + ortografía y/e)
# ==========================================
INVISIBLE = {
    0x200B: "zero width space", 0x200C: "zero width non-joiner", 0x200D: "zero width joiner",
    0x200E: "left-to-right mark", 0x200F: "right-to-left mark", 0x2060: "word joiner",
    0x2061: "function application", 0x2062: "invisible times", 0x2063: "invisible separator",
    0x2064: "invisible plus", 0xFEFF: "BOM / zero width no-break space", 0x00AD: "soft hyphen",
    0x061C: "arabic letter mark", 0x115F: "hangul choseong filler", 0x1160: "hangul jungseong filler",
    0x3164: "hangul filler", 0xFFA0: "halfwidth hangul filler",
}
BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x2070))
ODD_SPACES = {0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009,
              0x200A, 0x202F, 0x205F, 0x3000, 0x2028, 0x2029}
NBSP = 0x00A0
QUOTES = {"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "‚": "'", "«": '"', "»": '"'}

def _is_emoji(ch):
    cp = ord(ch)
    return (0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF or 0x2300 <= cp <= 0x23FF
            or 0x2B00 <= cp <= 0x2BFF or cp in (0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D))

def clean_text(s, quotes=True, keep_nbsp=False, strip_dashes=True):
    out, counts, prev = [], {}, ""
    i, n = 0, len(s)

    def hit(k):
        counts[k] = counts.get(k, 0) + 1

    while i < n:
        ch = s[i]; cp = ord(ch)
        nxt = s[i + 1] if i + 1 < n else ""
        if cp == 0x200D and prev and _is_emoji(prev) and nxt and _is_emoji(nxt):
            out.append(ch)
        elif cp in (0xFE0E, 0xFE0F):
            if prev and (_is_emoji(prev) or prev.isdigit() or prev in "#*"):
                out.append(ch)
            else:
                hit("variation selector suelto")
        elif 0xFE00 <= cp <= 0xFE0D or 0xE0100 <= cp <= 0xE01EF:
            hit("variation selector suelto")
        elif 0xE0000 <= cp <= 0xE007F:
            j = i
            while j < n and 0xE0000 <= ord(s[j]) <= 0xE007F:
                j += 1
            if prev == "\U0001F3F4" and ord(s[j - 1]) == 0xE007F:
                out.append(s[i:j])
            else:
                counts["caracteres tag (texto oculto)"] = counts.get("caracteres tag (texto oculto)", 0) + (j - i)
            prev = s[j - 1]; i = j; continue
        elif cp in INVISIBLE:
            hit(INVISIBLE[cp])
        elif cp in BIDI:
            hit("control bidireccional")
        elif cp in ODD_SPACES:
            hit("espacio Unicode no estándar"); out.append("\n" if cp in (0x2028, 0x2029) else " ")
        elif cp == NBSP and not keep_nbsp:
            hit("espacio duro (NBSP)"); out.append(" ")
        elif quotes and ch in QUOTES:
            hit("comilla curva"); out.append(QUOTES[ch])
        elif strip_dashes and ch in ("—", "–"):
            hit("raya de IA (em/en dash)")
            k = len(out) - 1
            while k >= 0 and out[k] == " ":
                k -= 1
            antes = out[k] if k >= 0 else ""
            m = i + 1
            while m < n and s[m] == " ":
                m += 1
            despues = s[m] if m < n else ""
            if antes.isdigit() and despues.isdigit():
                out.append("-")          # rangos: 2010–2020 -> 2010-2020
            elif antes in ("", "\n"):
                pass                     # raya de diálogo al inicio de línea
            else:
                out.append(", ")
        elif unicodedata.category(ch) == "Cc" and ch not in "\n\r\t":
            hit("carácter de control")
        elif unicodedata.category(ch) == "Co":
            hit("carácter de uso privado")
        else:
            out.append(ch)
        prev = ch; i += 1

    r = "".join(out)
    r = re.sub(r" +,", ",", r)
    r = re.sub(r",(\s*,)+", ",", r)
    r = re.sub(r",\s*([.;:!?)])", r"\1", r)
    r = re.sub(r"(\d) *- *(\d)", r"\1-\2", r)
    r = re.sub(r"[ \t]{2,}", " ", r)
    r = re.sub(r"^ +", "", r, flags=re.MULTILINE)
    r = re.sub(r"\*\*(.+?)\*\*", r"\1", r)                       # negritas markdown
    r = re.sub(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+", "", r, flags=re.MULTILINE)  # viñetas (no toca años)
    r = re.sub(r"^#+\s*", "", r, flags=re.MULTILINE)             # títulos markdown
    # y -> e ante sonido "i" (incluye mayúsculas), pero no ante diptongo: "agua y hielo"
    r = re.sub(r"\by (?=(?:[iíIÍ]|h[iíIÍ])(?![aeouáéóAEOU]))", "e ", r)
    r = re.sub(r"\bY (?=(?:[iíIÍ]|h[iíIÍ])(?![aeouáéóAEOU]))", "E ", r)
    # o -> u ante sonido "o"
    r = re.sub(r"\bo (?=h?[oóOÓ])", "u ", r)
    return r.strip(), counts

# ==========================================
# CAPA C: AUDITORÍA AUTOMÁTICA DEL RESULTADO
# Mide en código los rasgos que más delatan un texto de IA y,
# si encuentra problemas, pide una corrección puntual.
# ==========================================
FRASES_VETADAS = [
    "al tiempo que", "a esto se suma", "herramientas como", "a su vez", "ante este panorama",
    "entre los que destacan", "entre las que destacan", "cabe destacar", "cabe señalar",
    "es fundamental", "es crucial", "es importante destacar", "enfrenta un reto", "enfoque centrado en",
    "fomentar", "abordar", "mediante", "reside en", "en este sentido", "en este contexto",
    "por otro lado", "en definitiva", "en conclusión", "en resumen", "sin lugar a dudas",
    "juega un papel", "desempeña un papel", "un papel crucial", "un papel fundamental",
    "no solo", "sino también", "panorama", "paradigma", "potenciar", "integral", "crucial",
    "clave para", "de manera significativa", "de forma significativa", "en la era",
    "el desafío consiste", "abre la puerta", "abre posibilidades", "es una oportunidad",
    "cada vez más", "hoy en día", "en un mundo", "transformador", "revolucionar",
    # Estructuras de "ensayo clásico"
    "se sitúa entre", "se sitúa como", "entre los episodios más", "uno de los episodios más",
    "uno de los acontecimientos más", "fracturó profundamente", "profundamente", "hito fundamental",
    "marcó un hito", "un hito", "representa un testimonio", "constituye un testimonio", "es un testimonio",
    "un antes y un después", "dejó una huella", "huella imborrable", "sentó las bases", "no puede entenderse sin",
    "se erige", "da cuenta de", "pone de manifiesto", "en el marco de", "a lo largo de la historia",
    "sin precedentes", "de gran relevancia", "de suma importancia", "es posible afirmar", "resulta evidente",
    "cabe mencionar", "vale la pena", "trascendental", "ineludible", "multifacético", "complejo entramado",
    "en última instancia", "en este marco", "así pues", "por consiguiente", "asimismo", "no obstante",
    # Muletillas que los detectores asocian a texto generado
    "en la actualidad", "es esencial", "resulta fundamental", "resulta esencial", "en el ámbito de",
    "a nivel global", "a gran escala", "una amplia gama", "un amplio abanico", "en gran medida",
    "es innegable", "no cabe duda", "se ha convertido en", "ha cobrado relevancia", "pilar fundamental",
    "en pocas palabras", "dicho de otro modo", "en términos generales", "de manera eficaz", "de manera efectiva",
]
# Conectores de manual al inicio de la oración: uno suelto pasa, varios delatan
CONECTORES_INICIO = (
    "además", "sin embargo", "por lo tanto", "por tanto", "por ello", "por ende", "de este modo",
    "de esta manera", "de esta forma", "en consecuencia", "finalmente", "en primer lugar", "en segundo lugar",
    "por último", "de igual forma", "del mismo modo", "es decir", "en efecto", "ahora bien", "por su parte",
    "en cuanto a", "respecto a", "con respecto a", "de hecho", "en suma", "así mismo", "adicionalmente",
)
PATRON_ENUMERACION = re.compile(
    r"\b[\wáéíóúñü]+(?: [\wáéíóúñü]+){0,2}, [\wáéíóúñü]+(?: [\wáéíóúñü]+){0,2},? (?:y|e) [\wáéíóúñü]+",
    re.IGNORECASE,
)
PATRON_GERUNDIO = re.compile(
    r", (?!cuando\b|mando\b|comando\b|bando\b|blando\b|fernando\b|orlando\b)([\wáéíóúñ]+(?:ando|iendo|yendo))\b",
    re.IGNORECASE,
)


# Registro profesional
COLOQUIALISMOS = ("más y más", "rompecabezas", "por supuesto", "un montón", "o sea", "la verdad es que",
                  "de verdad", "súper", "para nada", "ni hablar", "a full", "harto")
INICIOS_REPETIBLES = ("tambien", "y", "pero", "asi", "despues", "entonces", "ademas")
CON_TILDE = {"tambien": "también", "asi": "así", "despues": "después", "ademas": "además"}
# Formas verbales frecuentes para reconocer una oración sin verbo
_VERBOS_COMUNES = {"es", "son", "fue", "fueron", "era", "eran", "hay", "había", "habia", "está", "esta",
                   "están", "estaban", "estaba", "tiene", "tienen", "tenía", "tenian", "tenían", "puede",
                   "pueden", "podía", "debe", "deben", "sirve", "sirvió", "basta", "bastaba", "queda", "quedó",
                   "existe", "existía", "va", "van", "iba", "hizo", "hace", "dio", "da", "ser", "sido"}
_TERMINACIONES_VERBO = ("ó", "aron", "ieron", "aba", "aban", "ía", "ían", "an", "en", "ará", "erá", "irá")
# Sustantivos en -ía que no son verbos (economía, geografía, monarquía...)
_SUSTANTIVOS_IA = ("nomía", "grafía", "logía", "quía", "sofía", "ergía", "pañía", "vía", "día", "gría", "licía", "cracia")


def _parece_fragmento(oracion):
    """Oración corta sin ningún verbo reconocible ("Y la cultura.", "Geopolítica y economía, por supuesto.")."""
    palabras = [w.strip(',.;:¿?¡!()"').lower() for w in oracion.split()]
    palabras = [w for w in palabras if w]
    if not palabras or len(palabras) > 7 or oracion.rstrip().endswith("?"):
        return False
    if any(w in _VERBOS_COMUNES for w in palabras):
        return False
    if any(len(w) > 3 and w.endswith(_TERMINACIONES_VERBO) and not w.endswith(_SUSTANTIVOS_IA) for w in palabras):
        return False
    return True


def contar_palabras(texto):
    return len(re.findall(r"\S+", texto or ""))


def dividir_parrafos(texto):
    return [p.strip() for p in re.split(r"\n\s*\n|\n", texto or "") if p.strip()]


def _normalizar(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


_MAYUS = "A-ZÁÉÍÓÚÑÜ"
_PATRON_NOMBRE = re.compile(
    rf"\b[{_MAYUS}][\wáéíóúñü]+(?:(?:\s+(?:de|del|la|las|los|y|e|el)){{0,2}}\s+[{_MAYUS}][\wáéíóúñü]+)*"
)
_MESES = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre"
_PATRON_FECHA = re.compile(rf"\b\d{{1,2}} de (?:{_MESES})(?: de(?:l año)? \d{{3,4}})?", re.IGNORECASE)
_PATRON_CIFRA = re.compile(r"\b\d[\d.,]*\d%?|\b\d%?")


def extraer_datos_clave(texto):
    """Fechas, cifras y nombres propios que el resultado debe conservar."""
    datos = []
    fechas = [m.group(0) for m in _PATRON_FECHA.finditer(texto)]
    for f in fechas:
        if f not in datos:
            datos.append(f)
    for m in _PATRON_CIFRA.finditer(texto):
        valor = m.group(0).rstrip(".,")
        # Un número que ya va dentro de una fecha completa no se repite suelto
        if not valor or valor in datos or any(re.search(rf"\b{re.escape(valor)}\b", f) and f.startswith(valor) for f in fechas):
            continue
        datos.append(valor)
    for m in _PATRON_NOMBRE.finditer(texto):
        nombre = m.group(0).strip()
        inicio = m.start()
        previo = texto[:inicio].rstrip()
        al_inicio = (not previo) or previo[-1] in ".!?:\n\"'("
        # Una sola palabra al inicio de oración suele ser una mayúscula normal, no un nombre
        if al_inicio and " " not in nombre:
            continue
        if al_inicio and " " in nombre:
            # "La Revolución Francesa" -> "Revolución Francesa"
            partes = nombre.split()
            if partes[0].lower() in ("la", "el", "los", "las", "en", "durante", "para", "con", "desde", "tras"):
                nombre = " ".join(partes[1:])
            if " " not in nombre and nombre[:1].isupper() and len(nombre) < 4:
                continue
        if len(nombre) >= 3 and nombre not in datos:
            datos.append(nombre)
    return datos[:40]


def datos_faltantes(original, resultado):
    res = _normalizar(resultado)
    return [d for d in extraer_datos_clave(original) if _normalizar(d) not in res]


def rango_parrafos(par_ref, partir):
    """Cuántos párrafos se aceptan. Con la capa de estructura, se permite dividir (4 -> 5 o 6)."""
    if not partir:
        return par_ref, par_ref
    return par_ref, max(par_ref + 1, math.ceil(par_ref * 1.5))


# Letras de escrituras que no corresponden a un texto en español
PATRON_OTRA_ESCRITURA = re.compile(
    r"[\u0400-\u04FF\u0590-\u05FF\u0600-\u06FF\u0E00-\u0E7F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\uF900-\uFAFF]+"
)


def palabras_otro_idioma(texto, referencia=""):
    """Trozos en otra escritura que no estaban en el original (p. ej. "定义了")."""
    del_original = set(PATRON_OTRA_ESCRITURA.findall(referencia or ""))
    return [t for t in dict.fromkeys(PATRON_OTRA_ESCRITURA.findall(texto or "")) if t not in del_original]


def problemas_de_fidelidad(texto, referencia, partir=False):
    """Compara contra el original: largo, párrafos y datos perdidos."""
    problemas = []
    p_ref, p_txt = contar_palabras(referencia), contar_palabras(texto)
    if p_ref and p_txt < 0.88 * p_ref:
        problemas.append(
            f"El texto quedó resumido: tiene {p_txt} palabras y el original {p_ref}. "
            f"Desarrolla de nuevo cada idea hasta llegar a unas {p_ref} palabras, sin agregar datos nuevos."
        )
    par_ref, par_txt = len(dividir_parrafos(referencia)), len(dividir_parrafos(texto))
    minimo, maximo = rango_parrafos(par_ref, partir)
    if par_ref and par_txt < minimo:
        problemas.append(
            f"El original tiene {par_ref} párrafo(s) y este texto solo {par_txt}: se juntaron o se perdieron ideas. "
            f"Vuelve a separar el contenido en al menos {minimo} párrafos, sin quitar nada."
        )
    elif par_ref and par_txt > maximo:
        problemas.append(
            f"El texto quedó demasiado fragmentado ({par_txt} párrafos para {par_ref} del original). "
            f"Únelo en {maximo} párrafos como máximo."
        )
    extranjeras = palabras_otro_idioma(texto, referencia)
    if extranjeras:
        problemas.append(
            "Hay palabras en otro idioma que no estaban en el original: "
            + ", ".join(f'"{t}"' for t in extranjeras[:5])
            + ". Reemplázalas por su equivalente en español, sin cambiar el resto de la oración."
        )
    faltan = datos_faltantes(referencia, texto)
    if faltan:
        problemas.append("Faltan estos datos del original y deben volver tal cual: " + ", ".join(f'"{d}"' for d in faltan) + ".")
    return problemas


def dividir_oraciones(texto):
    partes = re.split(r"(?<=[.!?])\s+", texto.strip())
    return [p for p in partes if len(p.split()) >= 2]


def auditar_texto(texto, referencia=None, partir=False):
    """Devuelve (lista_de_problemas, métricas). Con referencia, revisa también la fidelidad."""
    problemas = problemas_de_fidelidad(texto, referencia, partir) if referencia else []
    oraciones = dividir_oraciones(texto)
    largos = [len(o.split()) for o in oraciones]

    metricas = {"oraciones": len(oraciones), "variacion_ritmo": 0.0}
    if len(largos) >= 3:
        media = statistics.mean(largos)
        cv = statistics.pstdev(largos) / media if media else 0
        metricas["variacion_ritmo"] = round(cv, 2)
        if cv < RITMO_MINIMO:
            problemas.append(
                f"Ritmo demasiado parejo (las oraciones miden casi lo mismo, promedio {media:.0f} palabras). "
                "Mezcla oraciones de 4 a 9 palabras con otras de 22 a 32."
            )
        # Tres oraciones seguidas de largo casi igual: el patrón que más pesa en los detectores
        rachas = 0
        for k in range(len(largos) - 2):
            trio = largos[k:k + 3]
            if min(trio) >= 10 and max(trio) - min(trio) <= 3:
                problemas.append(
                    f'Tres oraciones seguidas miden casi lo mismo ({trio[0]}, {trio[1]} y {trio[2]} palabras), '
                    f'desde "{oraciones[k][:60]}...". Acorta una a menos de 9 palabras o une dos.'
                )
                rachas += 1
                if rachas == 2:
                    break
        cortas = sum(1 for x in largos if x <= 9)
        if cortas == 0:
            problemas.append("No hay ninguna oración corta. Agrega al menos dos de 5 a 9 palabras.")
        largas = [o for o in oraciones if len(o.split()) > 38]
        for o in largas[:2]:
            problemas.append(f'Oración demasiado larga, divídela: "{o[:90]}..."')

    bajo = texto.lower()
    vetadas = sorted({f for f in FRASES_VETADAS if re.search(r"\b" + re.escape(f) + r"\b", bajo)})
    if vetadas:
        problemas.append("Quita o reemplaza estas expresiones típicas de IA: " + ", ".join(f'"{v}"' for v in vetadas) + ".")

    for m in list(PATRON_ENUMERACION.finditer(texto))[:3]:
        problemas.append(f'Enumeración de tres elementos, sepárala en dos oraciones: "{m.group(0)}".')

    for m in list(PATRON_GERUNDIO.finditer(texto))[:3]:
        problemas.append(f'Gerundio de remate tras coma ("{m.group(1)}"): cámbialo por punto y un verbo conjugado.')

    if len(oraciones) >= 4:
        ARRANQUES = ("el", "la", "los", "las", "se")
        con_arranque = [o for o in oraciones if o.split()[0].lower().strip(',."¿¡(') in ARRANQUES]
        proporcion = len(con_arranque) / len(oraciones)
        if proporcion > 0.30:
            ejemplos = "; ".join(f'"{o[:60]}..."' for o in con_arranque[:4])
            problemas.append(
                f"{len(con_arranque)} de {len(oraciones)} oraciones ({round(proporcion * 100)}%) empiezan con "
                "El, La, Los, Las o Se. Deja menos del 30%: cambia el comienzo de varias, abriendo con una fecha, "
                "un lugar, un nombre propio, un complemento, un verbo o una subordinada (\"En 1789, ...\", "
                "\"Para los campesinos, ...\", \"Cuando cayó la fortaleza, ...\", \"Robespierre ...\"). "
                f"Por ejemplo estas: {ejemplos}"
            )

    # Párrafos con ritmo plano: los detectores puntúan por párrafo y por oración, no solo el texto entero
    planos = 0
    for parrafo in dividir_parrafos(texto):
        lp = [len(o.split()) for o in dividir_oraciones(parrafo)]
        if len(lp) >= 4 and statistics.mean(lp) and statistics.pstdev(lp) / statistics.mean(lp) < 0.30:
            problemas.append(
                f'El párrafo que empieza con "{parrafo[:60]}..." tiene todas sus oraciones de largo parecido. '
                "Deja una muy corta y otra larga dentro de ese mismo párrafo."
            )
            planos += 1
            if planos == 2:
                break

    if len(oraciones) >= 4:
        con_conector = [o for o in oraciones if _normalizar(o).lstrip('"¿¡(').startswith(
            tuple(_normalizar(c) + s for c in CONECTORES_INICIO for s in (",", " ")))]
        if len(con_conector) >= 2 and len(con_conector) / len(oraciones) > 0.12:
            ejemplos = "; ".join(f'"{o[:45]}..."' for o in con_conector[:3])
            problemas.append(
                f"{len(con_conector)} oraciones abren con un conector de manual ({ejemplos}). "
                "Deja uno como máximo: en las demás quita el conector o entra directo con el sujeto o el hecho."
            )

    if contar_palabras(texto) >= 150 and not re.search(r"[;:(?]", texto):
        problemas.append(
            "Toda la puntuación es coma y punto. Usa una o dos veces dos puntos, punto y coma, "
            "o un paréntesis, donde salga natural."
        )

    if len(oraciones) >= 5:
        inicios = [o.split()[0].lower().strip(",.") for o in oraciones]
        for palabra in set(inicios):
            if inicios.count(palabra) >= 3 and inicios.count(palabra) / len(inicios) > 0.25:
                problemas.append(f'Muchas oraciones empiezan con "{palabra}". Varía los inicios.')

    # Registro profesional: frases sin verbo, coloquialismos, preguntas retóricas e inicios repetidos
    sin_verbo = [o for o in oraciones if _parece_fragmento(o)]
    if sin_verbo:
        ejemplos = "; ".join(f'"{o[:60]}"' for o in sin_verbo[:4])
        problemas.append(
            f"Hay frases sueltas sin verbo que no suenan profesionales ({ejemplos}). "
            "Únelas a la oración anterior o reescríbelas como oración completa, sin borrar su contenido."
        )
    coloquiales = sorted({c for c in COLOQUIALISMOS if re.search(r"\b" + re.escape(c) + r"\b", bajo)})
    if coloquiales:
        problemas.append("Cambia estas expresiones coloquiales por otras de registro académico: "
                         + ", ".join(f'"{c}"' for c in coloquiales) + ".")
    preguntas = [o for o in oraciones if o.rstrip().endswith("?")]
    if preguntas and not (referencia and "?" in referencia):
        problemas.append(f'Quita la pregunta retórica y conviértela en afirmación: "{preguntas[0][:80]}".')
    if oraciones:
        inicios_reg = [_normalizar(o.split()[0]).strip(',."¿¡(') for o in oraciones if o.split()]
        for palabra in INICIOS_REPETIBLES:
            n = inicios_reg.count(palabra)
            if n >= 3:
                problemas.append(f'{n} oraciones empiezan con "{CON_TILDE.get(palabra, palabra).capitalize()}". Deja dos como máximo: '
                                 "une esas ideas a la oración anterior o abre con el sujeto.")

    if oraciones:
        ultima = oraciones[-1].lower()
        if re.search(r"\b(debe|deben|deberá|necesario|desafío|reto|futuro|oportunidad|clave|en definitiva)\b", ultima):
            problemas.append(f'La última oración suena a moraleja: "{oraciones[-1][:90]}". Reescríbela como un hecho concreto, sin borrar su contenido.')

    metricas["problemas"] = len(problemas)
    return problemas, metricas

# ==========================================
# CAPA D: VERIFICACIÓN CON DETECTORES REALES
# Mide el resultado en GPTZero y Copyleaks (los dos con API pública) y devuelve
# el porcentaje de IA y las oraciones que cada uno marcó.
# ==========================================
def detectores_activos():
    activos = []
    if GPTZERO_API_KEY:
        activos.append("GPTZero")
    if COPYLEAKS_EMAIL and COPYLEAKS_API_KEY:
        activos.append("Copyleaks")
    return activos


def medir_gptzero(texto):
    """Devuelve (porcentaje de IA, oraciones marcadas)."""
    headers = {"x-api-key": GPTZERO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"}
    payload = {"document": texto, "multilingual": True}
    resp = requests.post("https://api.gptzero.me/v2/predict/text", headers=headers, json=payload, timeout=(10, 60))
    if resp.status_code in (400, 422) and "multilingual" in resp.text.lower():
        payload.pop("multilingual")
        resp = requests.post("https://api.gptzero.me/v2/predict/text", headers=headers, json=payload, timeout=(10, 60))
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:160]}")
    doc = (resp.json().get("documents") or [{}])[0]
    probs = doc.get("class_probabilities") or {}
    if "human" in probs:
        ia = 100 * (1 - float(probs["human"]))        # cuenta "IA" y también "mixto"
    else:
        ia = 100 * float(doc.get("completely_generated_prob") or 0)
    frases = [s.get("sentence", "") for s in doc.get("sentences") or []
              if s.get("highlight_sentence_for_ai") or float(s.get("generated_prob") or 0) >= 0.5]
    return ia, [f for f in frases if f.strip()]


@st.cache_data(ttl=36 * 3600, show_spinner=False)
def _token_copyleaks(email, clave):
    resp = requests.post("https://id.copyleaks.com/v3/account/login/api",
                         json={"email": email, "key": clave}, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"no se pudo iniciar sesión (HTTP {resp.status_code})")
    return resp.json()["access_token"]


def medir_copyleaks(texto):
    """Devuelve (porcentaje de IA, tramos marcados). Copyleaks exige al menos 255 caracteres."""
    if len(texto) < 255:
        raise RuntimeError("el texto tiene menos de 255 caracteres, el mínimo que acepta")
    resp = None
    for intento in range(2):
        token = _token_copyleaks(COPYLEAKS_EMAIL, COPYLEAKS_API_KEY)
        resp = requests.post(
            f"https://api.copyleaks.com/v2/writer-detector/hp-{uuid.uuid4().hex[:24]}/check",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"text": texto}, timeout=(10, 60),
        )
        if resp.status_code == 401 and intento == 0:
            _token_copyleaks.clear()      # el token venció: se pide otro
            continue
        break
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:160]}")
    datos = resp.json()
    tramos, marcados = [], 0
    for r in datos.get("results") or []:
        if r.get("classification") != 2:              # 2 = IA, 1 = persona
            continue
        for m in r.get("matches") or []:
            chars = (m.get("text") or {}).get("chars") or {}
            for inicio, largo in zip(chars.get("starts") or [], chars.get("lengths") or []):
                tramos.append(texto[inicio:inicio + largo])
                marcados += largo
    resumen = datos.get("summary") or {}
    if "ai" in resumen:
        ia = 100 * float(resumen["ai"])
    else:
        ia = 100 * marcados / max(1, len(texto))
    return min(100.0, ia), [t for t in tramos if t.strip()]


def medir_detectores(texto):
    """Una medición por detector conectado: [{nombre, ia, frases}] o [{nombre, error}]."""
    mediciones = []
    for nombre, funcion in (("GPTZero", medir_gptzero), ("Copyleaks", medir_copyleaks)):
        if nombre not in detectores_activos():
            continue
        try:
            ia, frases = funcion(texto)
            mediciones.append({"nombre": nombre, "ia": round(max(0.0, ia), 1), "frases": frases})
        except Exception as e:
            mediciones.append({"nombre": nombre, "error": str(e)[:200]})
    return mediciones


def _clave_texto(t):
    return re.sub(r"\s+", " ", _normalizar(t)).strip()


def oraciones_marcadas(parrafo, frases):
    """Oraciones de un párrafo que coinciden con algún tramo marcado por un detector."""
    claves = set()
    for f in frases:
        for trozo in (dividir_oraciones(f) or [f]):
            c = _clave_texto(trozo)
            if len(c.split()) >= 4:
                claves.add(c[:60])
    marcadas = []
    for o in dividir_oraciones(parrafo):
        co = _clave_texto(o)
        if any(c in co or co[:60] in c for c in claves):
            marcadas.append(o)
    return marcadas


# ==========================================
# DISEÑO: tokens y estilos (todo color y fuente pasa por :root)
# Idea: el texto de la máquina entra en la pantalla oscura y sale
# como una hoja de papel escrita a mano: la pluma del logo deja tinta.
# ==========================================
st.markdown("""
<style>
/* Hallmark · checked: 2026-11-21 · genre: modern-minimal (inferred) · shape: app screen
 * idea: la salida es una hoja de papel con tinta; la firma es el ritmo de las oraciones
 * built: the project · redesign: polish */
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap');

:root {
    --bg: #0F1114;
    --surface: #171A1F;
    --surface-2: #20242B;
    --surface-3: #2A2F38;
    --ink: #ECEEF1;
    --ink-soft: #A6ACB6;
    --accent: #F2552C;          /* naranja del logo: solo la acción principal */
    --accent-press: #DB4A22;
    --on-accent: #0F1114;
    --human: #22D3E6;           /* cian del logo: foco y ritmo del resultado */
    --paper: #F2F1EC;
    --paper-ink: #1A1B1E;
    --paper-soft: #5B5E66;
    --font-ui: 'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
    --font-page: 'Newsreader', Georgia, 'Times New Roman', serif;
    --t-sm: 0.8125rem;
    --t-base: 1rem;
    --t-md: 1.1875rem;
    --t-lg: 1.75rem;
    --t-xl: clamp(2.75rem, 6.5vw, 5.25rem);
    --r: 4px;
    --dur-micro: 120ms;
    --dur-short: 200ms;
}

html, body { overflow-x: clip; }
.stApp { background-color: var(--bg); color: var(--ink); font-family: var(--font-ui); }
.stApp [data-testid="stMarkdownContainer"],
.stApp label, .stApp button, .stApp input, .stApp textarea { font-family: var(--font-ui); }
[data-testid="stHeader"] { background-color: transparent; }
#MainMenu, footer, [data-testid="stHeaderActionElements"] { display: none; }

.block-container { max-width: 1240px; padding: 2.5rem 2rem 3rem 2rem !important; }

/* ---------- Cabecera de la app ---------- */
.stApp h1.app-title {
    font-family: var(--font-ui) !important; font-size: var(--t-lg) !important; font-weight: 600 !important;
    letter-spacing: -0.02em; line-height: 1.1 !important; color: var(--ink) !important; margin: 0 !important; padding: 0 !important;
    overflow-wrap: break-word; min-width: 0;
}
.stApp p.app-lead { font-size: var(--t-base); color: var(--ink-soft); margin: 0.625rem 0 2.5rem 0 !important; max-width: 60ch; line-height: 1.5; }

.panel-head { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin: 0 0 0.625rem 0; }
.panel-title { font-size: var(--t-md); font-weight: 600; color: var(--ink); letter-spacing: -0.01em; }
.panel-meta { font-size: var(--t-sm); color: var(--ink-soft); font-variant-numeric: tabular-nums; }

/* ---------- Campo de entrada ---------- */
[data-testid="stTextArea"] [data-baseweb="textarea"] {
    background-color: var(--surface) !important; border: 1px solid var(--surface-3) !important;
    border-radius: var(--r) !important;
    transition: border-color var(--dur-micro) ease;
}
[data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within { border-color: var(--human) !important; }
[data-testid="stTextArea"] textarea {
    background-color: var(--surface) !important; color: var(--ink) !important;
    -webkit-text-fill-color: var(--ink) !important;
    font-size: var(--t-base) !important; line-height: 1.6 !important; padding: 1.25rem !important;
    caret-color: var(--human);
}
[data-testid="stTextArea"] textarea::placeholder { color: var(--ink-soft); -webkit-text-fill-color: var(--ink-soft); }
[data-testid="InputInstructions"] { color: var(--ink-soft) !important; }

/* ---------- La hoja: resultado ---------- */
.hoja {
    height: 400px; overflow-y: auto; box-sizing: border-box;
    background-color: var(--paper); color: var(--paper-ink);
    border-radius: var(--r); padding: 1.75rem 2rem;
}
.hoja p {
    font-family: var(--font-page) !important; font-size: 1.125rem; line-height: 1.65;
    color: var(--paper-ink); margin: 0 0 1em 0; max-width: 68ch;
}
.hoja p:last-child { margin-bottom: 0; }
.hoja.vacia {
    background-color: var(--surface-2); color: var(--ink-soft);
    display: flex; flex-direction: column; justify-content: center; padding: 2rem 2.5rem;
}
.hoja.vacia .vacia-titulo { font-family: var(--font-page); font-size: 1.5rem; line-height: 1.25; color: var(--ink); margin: 0 0 0.5rem 0; max-width: 22ch; }
.hoja.vacia .vacia-texto { font-size: var(--t-base); color: var(--ink-soft); margin: 0; max-width: 40ch; line-height: 1.5; }

/* ---------- Botones ---------- */
.stButton > button, [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {
    min-height: 44px; border-radius: var(--r) !important; font-weight: 600;
    transition: background-color var(--dur-micro) ease, transform var(--dur-micro) ease;
}
[data-testid="stBaseButton-primary"] {
    background-color: var(--accent) !important; color: var(--on-accent) !important; border: 0 !important;
}
.stApp .stButton button p, .stApp [data-testid="stFormSubmitButton"] button p { font-size: var(--t-base) !important; font-weight: 600 !important; }
[data-testid="stBaseButton-primary"] p { color: var(--on-accent) !important; }
[data-testid="stBaseButton-primary"]:hover { background-color: var(--accent-press) !important; }
[data-testid="stBaseButton-secondary"] {
    background-color: var(--surface-2) !important; color: var(--ink) !important; border: 0 !important;
}
[data-testid="stBaseButton-secondary"]:hover { background-color: var(--surface-3) !important; color: var(--ink) !important; }
[data-testid="stBaseButton-primary"]:active, [data-testid="stBaseButton-secondary"]:active { transform: translateY(1px); }
.stApp button:focus-visible, .stApp input:focus-visible, .stApp textarea:focus-visible, .stApp [role="checkbox"]:focus-visible {
    outline: 2px solid var(--human) !important; outline-offset: 2px; transition: none;
}

/* ---------- Barra lateral ---------- */
[data-testid="stSidebar"] { background-color: var(--surface); border-right: 0; }
[data-testid="stSidebar"] h3 { font-family: var(--font-ui); font-size: var(--t-md); font-weight: 600; color: var(--ink); letter-spacing: -0.01em; }
.motor { background-color: var(--surface-2); border-radius: var(--r); padding: 0.75rem 0.875rem; margin: 0.25rem 0 1.25rem 0; }
.motor-label { font-size: var(--t-sm); color: var(--ink-soft); margin: 0; }
.motor-valor { font-size: var(--t-base); color: var(--ink); margin: 0.125rem 0 0 0; font-weight: 500; overflow-wrap: anywhere; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { font-size: var(--t-base); color: var(--ink); }

/* ---------- Avisos, estado y campos de contraseña ---------- */
[data-testid="stAlert"] { border-radius: var(--r); }
[data-testid="stExpander"] details, [data-testid="stStatusWidget"] { border-radius: var(--r); }
[data-testid="stTextInput"] [data-baseweb="input"] {
    background-color: var(--surface-2) !important; border: 1px solid var(--surface-3) !important; border-radius: var(--r) !important;
}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within { border-color: var(--human) !important; }
[data-testid="stTextInput"] input { color: var(--ink) !important; background-color: var(--surface-2) !important; padding: 0.75rem 0.875rem !important; font-size: var(--t-base) !important; }
[data-testid="stTextInput"] label p { color: var(--ink-soft); font-size: var(--t-base); }

/* ---------- Ritmo de oraciones (firma de la app) ---------- */
.ritmo { background-color: var(--surface); border-radius: var(--r); padding: 1.75rem 2rem; margin-top: 2.5rem; }
.stApp h2.ritmo-titulo { font-family: var(--font-ui) !important; font-size: var(--t-md) !important; font-weight: 600 !important; color: var(--ink) !important; margin: 0 0 0.25rem 0 !important; padding: 0 !important; letter-spacing: -0.01em; line-height: 1.3 !important; }
.stApp p.ritmo-intro { font-size: var(--t-base); color: var(--ink-soft); margin: 0.25rem 0 1.5rem 0 !important; max-width: 70ch; line-height: 1.5; }
.ritmo-fila { display: grid; grid-template-columns: minmax(0, 15rem) minmax(0, 1fr); gap: 2rem; align-items: end; padding: 0.875rem 0; }
.ritmo-fila + .ritmo-fila { background-color: transparent; }
.ritmo-nombre { font-size: var(--t-base); color: var(--ink); margin: 0; font-weight: 500; }
.ritmo-dato { font-size: var(--t-sm); color: var(--ink-soft); margin: 0.125rem 0 0 0; font-variant-numeric: tabular-nums; }
.ritmo svg { display: block; max-width: 100%; height: auto; }
.barra-orig { fill: var(--ink-soft); opacity: 0.55; }
.barra-hum { fill: var(--human); }
.pendientes { margin: 1.25rem 0 0 0; padding: 1.25rem 0 0 0; }
.pendientes-titulo { font-size: var(--t-base); font-weight: 600; color: var(--ink); margin: 0 0 0.5rem 0; }
.pendientes ul { margin: 0; padding-left: 1.1rem; }
.pendientes li { color: var(--ink-soft); font-size: var(--t-base); line-height: 1.5; margin: 0 0 0.375rem 0; }
.sin-pendientes { font-size: var(--t-base); color: var(--ink-soft); margin: 1.25rem 0 0 0; }

/* ---------- Ingreso ---------- */
.stApp h1.ingreso-marca { font-family: var(--font-ui) !important; font-size: var(--t-xl) !important; font-weight: 600 !important; letter-spacing: -0.04em; line-height: 0.95 !important; color: var(--ink) !important; margin: 1.5rem 0 0 0 !important; padding: 0 !important; overflow-wrap: break-word; min-width: 0; }
.stApp p.ingreso-lead { font-size: var(--t-md); color: var(--ink-soft); line-height: 1.5; margin: 2rem 0 0 0 !important; max-width: 34ch; }
.ingreso-espacio { height: 9vh; }
.ingreso-form-titulo { font-size: var(--t-md); font-weight: 600; color: var(--ink); margin: 0 0 0.25rem 0; }
.stApp p.ingreso-form-texto { font-size: var(--t-base); color: var(--ink-soft); margin: 0.25rem 0 1rem 0 !important; }
.ingreso-form-pad { height: 9.5rem; }

/* ---------- Pie ---------- */
.pie { display: flex; justify-content: space-between; align-items: flex-end; gap: 2rem; flex-wrap: wrap; margin-top: 6rem; padding-top: 2rem; }
.pie-aviso { font-size: var(--t-sm); color: var(--ink-soft); line-height: 1.55; max-width: 62ch; margin: 0; }
.pie-firma { text-align: right; margin: 0; }
.pie-firma p { font-size: var(--t-sm); color: var(--ink-soft); margin: 0; }
.pie-firma .pie-autor { font-size: var(--t-base); color: var(--ink); font-weight: 500; }

/* ---------- Tablet (iPad y Android hasta 1024 px): paneles uno debajo del otro ---------- */
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
@media (max-width: 1024px) {
    .st-key-paneles [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; row-gap: 2rem; }
    .st-key-paneles [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important;
    }
    /* Los botones siguen lado a lado: Humanizar ancho, Limpiar angosto */
    .st-key-botones [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; row-gap: 0; }
    .st-key-botones [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        min-width: 0 !important; width: auto !important; flex: 1 1 0 !important;
    }
    .st-key-botones [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child { flex-grow: 3 !important; }
    /* La hoja crece con el texto (sin doble barra de desplazamiento en pantallas táctiles) */
    .hoja { height: auto; min-height: 220px; max-height: 75vh; }
    .ritmo-fila { grid-template-columns: minmax(0, 1fr); gap: 0.5rem; }
    .ritmo svg { margin-top: 0.5rem; width: 100%; max-width: 640px; height: auto; }
}

@media (max-width: 768px) {
    .block-container { padding: 1.5rem 1rem 2rem 1rem !important; }
    .hoja { padding: 1.25rem 1.25rem; }
    .ritmo { padding: 1.25rem; }
    .ritmo-fila { grid-template-columns: minmax(0, 1fr); gap: 0.5rem; }
    .pie { flex-direction: column; align-items: flex-start; }
    .pie-firma { text-align: left; }
    .ingreso-espacio { height: 3vh; }
    .ingreso-form-pad { height: 1rem; }
    .ritmo svg { margin-top: 0.5rem; }
}
@media (prefers-reduced-motion: reduce) {
    .stApp *, .stApp *::before, .stApp *::after { transition: none !important; animation: none !important; }
}
</style>
""", unsafe_allow_html=True)

LOGO_URL = "https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png"

PIE_HTML = """
<div class="pie">
    <p class="pie-aviso">Humanizador Pro es una herramienta de apoyo para pulir la redacción de textos. Los resultados deben ser revisados y validados por el usuario, quien asume la responsabilidad total sobre el contenido final y el uso que le dé.</p>
    <div class="pie-firma">
        <p class="pie-autor">Elaborado por Manu</p>
        <p>®Humanizadormanu, derechos reservados © 2026</p>
    </div>
</div>
"""


def html_hoja(texto):
    """El resultado como hoja de papel, con sus párrafos."""
    if not texto:
        return (
            '<div class="hoja vacia" role="region" aria-label="Texto humanizado">'
            '<p class="vacia-titulo">Aquí aparece tu texto reescrito.</p>'
            '<p class="vacia-texto">Pega un texto a la izquierda y pulsa Humanizar texto. '
            'El resultado queda en esta hoja, listo para copiar.</p></div>'
        )
    parrafos = dividir_parrafos(texto)
    cuerpo = "".join(f"<p>{html_lib.escape(p)}</p>" for p in parrafos)
    return f'<div class="hoja" role="region" aria-label="Texto humanizado" tabindex="0">{cuerpo}</div>'


def svg_ritmo(texto, clase):
    """Una barra por oración; la altura es su número de palabras."""
    largos = [len(o.split()) for o in dividir_oraciones(texto)][:70]
    if not largos:
        return ""
    paso = max(14, min(48, 860 // len(largos)))
    ancho, alto = round(paso * 0.68), 96
    barras = []
    for i, n in enumerate(largos):
        h = max(4, round(min(n, 45) / 45 * (alto - 4)))
        barras.append(f'<rect class="{clase}" x="{i * paso}" y="{alto - h}" width="{ancho}" height="{h}" rx="1"></rect>')
    total = len(largos) * paso
    etiqueta = f"Largo de cada oración: {', '.join(map(str, largos))} palabras"
    return (f'<svg width="{total}" height="{alto}" viewBox="0 0 {total} {alto}" role="img" '
            f'aria-label="{etiqueta}">{"".join(barras)}</svg>')


def fila_ritmo(nombre, texto, clase):
    _, m = auditar_texto(texto)
    n = m.get("oraciones", 0)
    cv = m.get("variacion_ritmo", 0.0)
    lectura = "ritmo parejo" if cv < RITMO_MINIMO else "ritmo variado"
    dato = f"{n} oraciones, variación {str(cv).replace('.', ',')}, {lectura}"
    return (f'<div class="ritmo-fila"><div><p class="ritmo-nombre">{nombre}</p>'
            f'<p class="ritmo-dato">{dato}</p></div>{svg_ritmo(texto, clase)}</div>')


# ==========================================
# 1. INGRESO
# ==========================================
def check_password():
    def verify_password():
        # Usa APP_PASSWORD de Secretos si existe; si no, la clave es "manu2026"
        clave_real = str(leer_secreto("APP_PASSWORD", "manu2026"))
        ingresada = st.session_state.get("password_input", "")
        if hmac.compare_digest(ingresada.encode(), clave_real.encode()):
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct"):
        return True

    st.markdown('<div class="ingreso-espacio"></div>', unsafe_allow_html=True)
    col_marca, col_form = st.columns([7, 5], gap="large")
    with col_marca:
        st.image(LOGO_URL, width=88)
        st.markdown(
            '<h1 class="ingreso-marca">Humanizador Pro</h1>'
            '<p class="ingreso-lead">Convierte un texto generado por IA en prosa natural, '
            'con ritmo y voz de persona.</p>',
            unsafe_allow_html=True,
        )
    with col_form:
        st.markdown('<div class="ingreso-form-pad"></div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="ingreso-form-titulo">Ingresar</p>'
            '<p class="ingreso-form-texto">Escribe la contraseña para usar la herramienta.</p>',
            unsafe_allow_html=True,
        )
        with st.form("form_ingreso", border=False):
            st.text_input("Contraseña", type="password", key="password_input")
            st.form_submit_button("Ingresar", on_click=verify_password, type="primary", width="stretch")
        if st.session_state.get("password_correct") is False:
            st.error("La contraseña no coincide. Intenta de nuevo.")

    st.markdown(PIE_HTML, unsafe_allow_html=True)
    return False

if not check_password():
    st.stop()

# ==========================================
# 2. BARRA LATERAL: CONFIGURACIÓN
# ==========================================
with st.sidebar:
    st.image(LOGO_URL, width=56)
    st.markdown("### Configuración")

    conectados = [pid for pid in ORDEN_CALIDAD if CLAVES.get(pid)]
    if not conectados:
        st.warning("No hay ninguna API key en Secretos. Puedes pegar una aquí para probar.")
        clave_tmp = st.text_input("API key de Gemini", type="password").strip()
        if clave_tmp:
            CLAVES["gemini"] = clave_tmp
        clave_tmp = st.text_input("API key de Groq", type="password").strip()
        if clave_tmp:
            CLAVES["groq"] = clave_tmp
        conectados = [pid for pid in ORDEN_CALIDAD if CLAVES.get(pid)]

    nombres = {pid: PROVEEDORES[pid]["nombre"] for pid in PROVEEDORES}
    modelo_final_id = None
    proveedores_mezcla = []
    if conectados:
        # Por defecto: un modelo de pago si lo hay (mejor calidad); si no, Groq (el gratis más rápido)
        pagos = [p for p in ("anthropic", "openai", "deepseek") if p in conectados]
        por_defecto = pagos[0] if pagos else ("groq" if "groq" in conectados else conectados[0])
        modelo_final_id = st.selectbox(
            "Modelo para la redacción final",
            conectados, index=conectados.index(por_defecto), format_func=lambda pid: nombres[pid],
            help="Hace el paso más importante. Por defecto se elige el que mejor escribe en español.",
        )
        proveedores_mezcla = st.multiselect(
            "Modelos para los demás pasos",
            conectados, default=conectados, format_func=lambda pid: nombres[pid],
            help="Cada paso usa un modelo distinto de esta lista. Si uno falla, se prueba el siguiente.",
        )
        detectados = {}
        for pid in conectados:
            try:
                detectados[pid] = detectar_modelos(pid, CLAVES[pid])
            except Exception:
                detectados[pid] = None
        with st.expander("Modelos conectados", expanded=False):
            st.caption("La app elige sola el más rápido y capaz de cada cuenta. Puedes cambiarlo aquí.")
            for pid in conectados:
                mods = detectados[pid]
                if mods is None:
                    st.markdown(f"**{nombres[pid]}:** clave no válida o sin conexión")
                    continue
                if not mods:
                    st.markdown(f"**{nombres[pid]}:** sin modelos de texto")
                    continue
                if len(mods) == 1:
                    st.markdown(f"**{nombres[pid]}:** {mods[0]}")
                    MODELOS_RESUELTOS[pid] = mods
                    continue
                opciones = mods[:30]
                elegido = st.selectbox(nombres[pid], opciones, index=0, key=f"modelo_{pid}")
                # El elegido va primero; los demás quedan de respaldo
                MODELOS_RESUELTOS[pid] = [elegido] + [m for m in mods if m != elegido]

    modo_profundo = st.toggle(
        "Modo profundo (más lento)",
        value=False,
        help="Apagado: una sola llamada por bloque, mucho más rápido. "
             "Encendido: pasa el texto por el inglés y de vuelta, reordena la estructura y corrige dos veces "
             "(4 a 6 llamadas por bloque).",
    )
    pasadas = st.slider(
        "Pasadas de humanización", 1, 3, 1,
        help="Con 2, el resultado de la primera pasada vuelve a entrar al humanizador, igual que copiarlo y "
             "pegarlo de nuevo. Cada pasada extra suma más o menos el mismo tiempo que la primera.",
    )
    mezclar_modelos = st.toggle(
        "Un modelo distinto en cada paso",
        value=True,
        disabled=not modo_profundo,
        help="Reparte traducción, estructura y redacción entre modelos distintos para no dejar la huella de uno solo.",
    )
    usar_retrotraduccion = True    # sin interruptor: se aplica siempre dentro del modo profundo
    usar_estructura = st.toggle(
        "Romper estructura de párrafos",
        value=True,
        disabled=not modo_profundo,
        help="Capa de estructura: divide los párrafos (4 pasan a 5 o 6) y varía mucho el largo de las oraciones, sin resumir.",
    )
    usar_auditoria = st.toggle(
        "Revisión y corrección automática",
        value=True,
        help="Capa C: revisa ritmo, muletillas, enumeraciones, gerundios, inicios y cierre, y corrige hasta 3 veces.",
    )
    usar_detectores = False        # verificación con GPTZero y Copyleaks desactivada (sin interruptor)
    muestra_estilo = st.text_area(
        "Muestra de tu propia escritura (opcional)",
        height=140, max_chars=3000, key="muestra_estilo",
        placeholder="Pega 2 o 3 párrafos escritos por ti, sin IA.",
        help="La redacción final imita el ritmo, el vocabulario y la puntuación de esta muestra. "
             "Es lo que más acerca el resultado a un texto escrito por ti.",
    ).strip()

    with st.expander("Cómo agregar más modelos"):
        st.markdown(
            "En Streamlit Cloud, abre **Settings → Secrets** y agrega las claves que tengas:\n\n"
            + "\n".join(f"- `{PROVEEDORES[pid]['clave']}` para {nombres[pid]}" for pid in ORDEN_CALIDAD)
            + "\n\nPara fijar un modelo concreto, agrega por ejemplo `OPENAI_MODEL = \"nombre-del-modelo\"`."
        )

    st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)
    if st.button("Cerrar sesión", width="stretch"):
        st.session_state.pop("password_correct", None)
        st.rerun()

# ==========================================
# 3. PANTALLA PRINCIPAL
# ==========================================
st.session_state.setdefault("texto_humanizado", "")
st.session_state.setdefault("texto_fuente", "")
st.session_state.setdefault("avisos", [])
st.session_state.setdefault("auditoria", None)

def limpiar_textos():
    st.session_state["texto_humanizado"] = ""
    st.session_state["texto_fuente"] = ""
    st.session_state["input_original_key"] = ""
    st.session_state["avisos"] = []
    st.session_state["auditoria"] = None

st.markdown(
    '<h1 class="app-title">Humanizador de textos</h1>'
    '<p class="app-lead">Pega un texto generado por IA y recíbelo reescrito con ritmo, '
    'vocabulario y estructura de persona.</p>',
    unsafe_allow_html=True,
)


# ==========================================
# PROMPTS
# ==========================================
REGLA_NO_RESUMIR = """
REGLA MÁXIMA (por encima de todas las demás): PROHIBIDO RESUMIR.
- Mantén la misma longitud total y el mismo nivel de detalle que el texto original.
- No omitas ninguna idea, argumento, ejemplo, dato ni matiz, y respeta el orden de las ideas.
- Nunca juntes párrafos ni dejes menos párrafos que el original. Dividir un párrafo largo en dos sí está permitido.
- Conserva TAL CUAL todas las fechas, años, cifras, nombres de personas, lugares, instituciones, obras y citas. Puedes moverlos dentro de la oración, pero nunca borrarlos ni cambiarlos.
- Cambiar el estilo nunca justifica acortar. Si dudas, deja la idea más desarrollada, no menos.
"""

PROMPT_EN = (
    "Translate this Spanish text into plain, everyday English. "
    "Keep EXACTLY the same paragraphs (same number, same order) and the same level of detail: do not summarize or skip anything. "
    "Keep every fact, name, institution, number, quote and year exactly as written. "
    "Output ONLY the English text."
)
PROMPT_ES = (
    "Pasa este texto del inglés al español natural y directo. "
    "Cambia el orden de las ideas dentro de cada oración y los conectores, pero conserva los mismos párrafos, "
    "en el mismo orden y con la misma extensión. No resumas ni omitas nada. "
    "Conserva todos los datos, nombres, instituciones, cifras, citas y fechas sin inventar nada. "
    "Devuelve SOLO el texto en español."
)
PROMPT_PARAFRASIS = (
    "Reescribe este texto cambiando el orden de las cláusulas, los conectores y los límites de las oraciones. "
    "Mantén la misma cantidad de párrafos y la misma extensión: no resumas ni omitas nada. "
    "Conserva todos los hechos, nombres, instituciones, fechas, citas y cifras sin inventar nada. Devuelve SOLO el texto."
)
PROMPT_ESTRUCTURA = """
Eres un editor que desarma la estructura de un ensayo escrito por IA, sin quitarle contenido.
""" + REGLA_NO_RESUMIR + """
QUÉ DEBES HACER:
1. ROMPE LA ESTRUCTURA DE LOS PÁRRAFOS: divide solo los párrafos más largos, por donde cambia la idea (si el original tiene 4 párrafos, el resultado tiene 5 o 6). Nunca dejes una sola oración por párrafo en todo el texto: que los párrafos midan distinto, alguno de dos oraciones y otro de cinco.
2. VARÍA EL LARGO DE LAS ORACIONES DE FORMA EXTREMA: mezcla oraciones de 4 a 7 palabras con otras de 30 a 40. Nunca tres oraciones seguidas de largo parecido.
3. CAMBIA LA ARQUITECTURA DE CADA PÁRRAFO: no empieces cada párrafo con una oración que lo resume ni lo cierres con una que concluye. Abre con un hecho, una fecha, un nombre o una consecuencia, y deja la explicación para después.
4. MUEVE LAS PIEZAS DENTRO DE CADA ORACIÓN: pon a veces la fecha o el lugar al inicio, a veces el sujeto al final, y otras usa una subordinada al comienzo.
5. Conserva todas las fechas, nombres, instituciones, cifras y citas tal cual.

Devuelve ÚNICAMENTE el texto reestructurado, con los párrafos separados por una línea en blanco.
"""

PROMPT_FINAL = """
Eres un historiador que escribe para una revista de divulgación seria: lenguaje directo y claro, cercano al que usa un buen profesor cuando explica en clase, sin perder la formalidad académica. Reescribe el borrador conservando todo su contenido, pero eliminando por completo la cadencia de IA y la estructura de "ensayo clásico".
""" + REGLA_NO_RESUMIR + """
ESTRUCTURA DE PÁRRAFOS: mantén la división en párrafos del borrador (no vuelvas a juntarlos).

DESTRUYE EL "ENSAYO CLÁSICO" (OBLIGATORIO):
A. PROHIBIDAS las fórmulas de importancia y grandeza. No uses ninguna de estas ni variantes parecidas:
   "se sitúa entre los episodios más...", "uno de los acontecimientos más...", "el conflicto fracturó profundamente...", "es un hito fundamental", "marcó un hito", "representa un testimonio", "constituye un testimonio", "un antes y un después", "dejó una huella imborrable", "sentó las bases", "no puede entenderse sin", "se erige como", "da cuenta de", "pone de manifiesto", "en el marco de", "a lo largo de la historia", "sin precedentes", "de gran relevancia", "de suma importancia", "trascendental", "es posible afirmar", "resulta evidente", "cabe mencionar", "asimismo", "no obstante", "por consiguiente", "en última instancia".
B. EN VEZ DE ADJETIVOS DE IMPORTANCIA, MUESTRA EL HECHO: no digas que algo "fue fundamental" o "transformó profundamente"; di qué cambió, quién lo hizo, cuándo y qué pasó después.
   - Mal: "La Revolución Francesa es un hito fundamental que fracturó profundamente la sociedad europea."
   - Bien: "Después de 1789, en Francia ya no mandaba solo el rey. Los nobles perdieron sus privilegios y muchos huyeron al extranjero."
   - Mal: "Este documento representa un testimonio de la lucha por los derechos."
   - Bien: "El documento recoge lo que pedían los diputados del Tercer Estado: igualdad ante la ley y libertad de expresión."
C. SUJETO Y VERBO CLAROS: prefiere "los diputados aprobaron" a "se produjo la aprobación por parte de los diputados". Evita la voz pasiva con "se" y las nominalizaciones (la implementación, la consolidación, la configuración).
D. INICIOS DE ORACIÓN: menos de un tercio de las oraciones puede empezar con "El", "La", "Los", "Las" o "Se". Abre las demás con una fecha, un lugar, un nombre propio, un complemento, un verbo o una subordinada.
E. CONECTORES SENCILLOS: usa "pero", "por eso", "así", "después", "entonces", "aun así", "en cambio". Nada de conectores de manual.

REGLAS DE ESTILO (aplícalas sin acortar el texto):
1. ENUMERACIONES: si el borrador enumera 3 o 4 elementos en una sola frase ("A, B, C y D"), repártelos en dos oraciones con verbos distintos. Todos los elementos se mantienen.
2. NADA DE PARES SIMÉTRICOS AL CIERRE DE LAS ORACIONES ("...la política y la sociedad"): separa las ideas en frases con distinto verbo, sin perder ninguna.
3. EXPRESIONES VETADAS (NO USES NINGUNA): "al tiempo que", "a esto se suma", "a su vez", "ante este panorama", "entre los que destacan", "cabe destacar", "es fundamental", "es crucial", "enfrenta un reto", "fomentar", "abordar", "mediante", "reside en", "en este sentido", "en este contexto", "por otro lado", "no solo... sino también", "juega un papel", "hoy en día", "cada vez más", "panorama", "paradigma", "potenciar", "integral", "clave para", "en conclusión", "en definitiva". Reemplázalas por una expresión común; no borres la idea que acompañan.
4. CERO GERUNDIOS DE REMATE: no cierres una frase con coma + gerundio ("..., provocando..."). Usa punto seguido y un verbo conjugado.
5. CIERRE SIN MORALEJA: si el último párrafo termina en una reflexión genérica, reescríbela como una afirmación concreta. No borres el párrafo de cierre.
6. RITMO IRREGULAR: alterna sin patrón fijo frases cortas (5 a 9 palabras, siempre con verbo conjugado y sentido completo) con frases medianas y alguna larga (25 a 35 palabras) con un inciso natural entre comas.
7. VOCABULARIO: prefiere la palabra común sobre la culta ("usar" en vez de "utilizar", "hacer" en vez de "llevar a cabo", "empezar" en vez de "iniciar").
8. FORMATO: solo prosa en párrafos separados por una línea en blanco. Sin rayas largas (— o –), sin negritas, sin listas, sin títulos y sin comillas curvas.
9. PUNTUACIÓN VARIADA: no todo es coma y punto. Usa alguna vez dos puntos, punto y coma o un paréntesis corto, donde salga natural. No uses preguntas retóricas.
10. PALABRA CONCRETA, NO LA PRIMERA QUE SALE: entre dos formas correctas de decir algo, elige la más específica y menos de plantilla ("los nobles vendieron sus tierras" en vez de "se produjeron cambios en la propiedad"). Repite una palabra si es la justa; no la cambies por un sinónimo solo para variar.
11. SIN MOLDE FIJO: que los párrafos no sigan todos el mismo esquema (afirmación, explicación, consecuencia). Como máximo una oración de todo el texto puede empezar con "Y" o "Pero". No redondees cada frase: un texto de persona tiene oraciones secas junto a otras más sueltas, pero todas completas.
12. CONECTORES AL INICIO: como máximo una oración de todo el texto puede abrir con "Además", "Sin embargo", "Por lo tanto", "Por ello", "De este modo", "Finalmente" o parecidos. Las demás entran directo con el sujeto o el hecho.
13. IDIOMA: escribe todo en español. Ninguna palabra en chino, inglés ni otro idioma, salvo nombres propios y citas que ya vengan así en el texto.
14. REGISTRO PROFESIONAL: escribe como un estudiante universitario avanzado o un profesional. Cada oración tiene sujeto y verbo conjugado: nada de frases sueltas sin verbo ("Y la cultura.", "Geopolítica y economía, por supuesto."). Sin coloquialismos ("más y más", "era un rompecabezas", "por supuesto", "un montón"). No empieces más de dos oraciones con la misma palabra ("También", "Y", "Pero", "Así").

Devuelve ÚNICAMENTE el texto final en español, sin comentarios ni saludos.
"""
PROMPT_RAPIDO = PROMPT_FINAL.replace(
    "ESTRUCTURA DE PÁRRAFOS: mantén la división en párrafos del borrador (no vuelvas a juntarlos).",
    """ESTRUCTURA (hazlo en esta misma pasada):
- Reordena las ideas dentro de cada párrafo y cambia la construcción de cada oración; no sigas el orden de frases del original.
- Divide solo los párrafos más largos, por donde cambia la idea. Nunca dejes una sola oración por párrafo en todo el texto.
- Varía el largo de las oraciones de forma marcada: algunas de 4 a 8 palabras y otras de 25 a 35.
- No empieces los párrafos con una oración que los resume ni los cierres con una que concluye.""",
).replace("Reescribe el borrador", "Reescribe el texto")

PROMPT_CORRECCION = """
Eres un corrector de estilo. Te paso el texto ORIGINAL, un TEXTO reescrito y una lista de PROBLEMAS detectados por una revisión automática.
Corrige SOLO esos problemas en el TEXTO y deja intacto todo lo demás.
""" + REGLA_NO_RESUMIR + """
- Si un problema dice que el texto quedó resumido o que faltan datos, recupera desde el ORIGINAL las ideas y los datos perdidos y vuelve a desarrollarlos con el estilo del TEXTO.
- Para corregir un problema de estilo, reescribe la frase; nunca la borres.
- No agregues información que no esté en el ORIGINAL y no añadas conclusiones.
Formato: solo prosa en párrafos separados por una línea en blanco, sin rayas largas, sin negritas, sin listas.
Devuelve ÚNICAMENTE el texto corregido.
"""


PROMPT_DETECTOR = """
Eres un editor que retoca a mano un párrafo en español. Un detector de texto generado por IA marcó las ORACIONES MARCADAS: su redacción es demasiado previsible.

QUÉ DEBES HACER:
1. Reescribe desde cero cada oración marcada: otra construcción sintáctica, otro orden de las piezas, otro verbo principal y otro largo. Cambiar sinónimos no sirve.
2. Puedes partir una oración marcada en dos (una de ellas de menos de 9 palabras) o unirla con la vecina. Evita que dos oraciones seguidas midan parecido.
3. Elige la palabra concreta y cotidiana en vez de la genérica. Sujeto y verbo claros, sin pasiva con "se" ni nominalizaciones.
4. No abras con conectores de manual ("Además", "Sin embargo", "Por lo tanto", "Asimismo"). Sin coma + gerundio al final, sin enumeraciones de tres elementos, sin frases de importancia ("es fundamental", "cabe destacar", "juega un papel").
5. Las oraciones NO marcadas quedan casi iguales: solo ajusta el enlace con las que cambiaste.
6. PROHIBIDO RESUMIR: conserva todas las ideas y TAL CUAL las fechas, cifras, nombres, instituciones y citas. La extensión del párrafo queda entre 95% y 115% de la actual.
7. No agregues información ni opiniones nuevas.

Formato: un solo párrafo de prosa, sin rayas largas, sin negritas, sin listas y sin comillas curvas.
Devuelve ÚNICAMENTE el párrafo reescrito.
"""


def con_muestra(prompt, muestra):
    """Agrega al prompt la muestra de escritura del usuario, si la hay."""
    if not muestra or contar_palabras(muestra) < 40:
        return prompt
    return (prompt + "\nMUESTRA DE ESTILO (escrita por la persona que firma el texto). Imita su voz: el largo y el ritmo de "
            "sus oraciones, su vocabulario, su puntuación y la forma en que une las ideas. Si la muestra contradice "
            "alguna regla de estilo anterior, manda la muestra. No copies su contenido ni sus datos, y no la "
            "menciones.\n<<<\n" + muestra + "\n>>>\n")


def instrucciones_de_medida(original, partir=False):
    """Le dice al modelo cuánto mide el original y qué datos no puede perder."""
    datos = extraer_datos_clave(original)
    par = len(dividir_parrafos(original))
    if partir:
        objetivo = f"entre {par} y {max(par + 1, math.ceil(par * 1.5))} párrafos; divide solo los párrafos más largos"
    else:
        objetivo = f"exactamente {par} párrafo(s)"
    lineas = [
        f"MEDIDA DEL ORIGINAL: {par} párrafo(s) y unas {contar_palabras(original)} palabras. "
        f"El resultado debe tener {objetivo} y una extensión total parecida (entre 95% y 115%)."
    ]
    if datos:
        lineas.append("DATOS OBLIGATORIOS (deben aparecer tal cual): " + ", ".join(datos) + ".")
    return "\n".join(lineas)


# ==========================================
# ENRUTADOR: qué modelo hace cada paso
# ==========================================
def armar_plan():
    """Devuelve {paso: [proveedores en orden de intento]}."""
    final = modelo_final_id
    disponibles = [pid for pid in ORDEN_CALIDAD if CLAVES.get(pid)]
    mezcla = [pid for pid in proveedores_mezcla if CLAVES.get(pid)] or disponibles
    # Pasos intermedios: primero los proveedores rápidos; OpenRouter gratis y NVIDIA quedan de respaldo
    rapidos = [pid for pid in ORDEN_VELOCIDAD if pid in mezcla and pid not in ("openrouter", "nvidia") and pid != final]
    otros = rapidos or [pid for pid in ORDEN_VELOCIDAD if pid in mezcla and pid != final] or [final]
    respaldo = [pid for pid in ORDEN_VELOCIDAD if pid in disponibles]
    plan = {}
    for i, paso in enumerate(["ingles", "espanol", "estructura"]):
        principal = otros[i % len(otros)] if mezclar_modelos else final
        plan[paso] = [principal] + [p for p in respaldo if p != principal]
    for paso in ("final", "correccion"):
        plan[paso] = [final] + [p for p in respaldo if p != final]
    # Ajuste por detectores: primero otra familia de modelos, para no repetir la huella de la redacción final
    plan["detector"] = [p for p in disponibles if p != final] + [final]
    return plan


def proveedor_en_pausa(pid):
    return PAUSADOS.get(pid, 0) > time.time()


def pausar_proveedor(pid, segundos):
    PAUSADOS[pid] = max(PAUSADOS.get(pid, 0), time.time() + segundos)


def esperar_cuota(pid, avanzar, esperas):
    """Si el proveedor principal está en pausa por cuota por minuto, espera a que se renueve (65 s como máximo)
    en vez de saltar a los proveedores lentos. Las pausas largas (clave rechazada) no se esperan."""
    resta = PAUSADOS.get(pid, 0) - time.time()
    if not 0 < resta <= PAUSA_CUOTA or esperas[0] >= MAX_ESPERAS:
        return
    esperas[0] += 1
    fin = time.time() + min(resta, 65)
    while time.time() < fin:
        avanzar(f"Esperando que se renueve la cuota de {PROVEEDORES[pid]['nombre']} (faltan {round(fin - time.time())} s)")
        time.sleep(1)
    PAUSADOS.pop(pid, None)


def generar(system_prompt, texto, temperature, paso, plan, avisos, usados, tiempos):
    """Prueba los proveedores del paso en orden, saltando los que están en pausa."""
    errores = []
    limite = TIEMPO_MAXIMO["final"] if paso in ("final", "correccion", "detector") else TIEMPO_MAXIMO["intermedio"]
    inicio = time.monotonic()
    disponibles = [p for p in plan[paso] if not proveedor_en_pausa(p)]
    # Si todos están en pausa, se intenta igual con el orden normal
    orden = disponibles or plan[paso]
    try:
        for pid in orden:
            try:
                resultado = llamar_proveedor(pid, system_prompt, texto, temperature, limite)
            except ProveedorNoDisponible as e:
                pausar_proveedor(pid, e.pausa)
                errores.append(str(e))
                continue
            except Exception as e:
                msg = str(e)
                # Gemini informa la cuota agotada como excepción de su propia librería
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                    pausar_proveedor(pid, 1800 if "day" in msg.lower() or "quota" in msg.lower() else PAUSA_CUOTA)
                    msg = f"{PROVEEDORES[pid]['nombre']}: cuota agotada por ahora."
                elif "timeout" in msg.lower() or "timed out" in msg.lower():
                    pausar_proveedor(pid, PAUSA_LENTO)
                errores.append(msg)
                continue
            if errores:
                aviso = f"{errores[0][:160]} Se usó otro modelo como respaldo."
                if aviso not in avisos:
                    avisos.append(aviso)
            usados[paso] = resultado[1]
            return resultado
        raise RuntimeError(" | ".join(errores) or "No hay ningún proveedor configurado.")
    finally:
        tiempos[paso] = tiempos.get(paso, 0) + (time.monotonic() - inicio)


def formato_tiempo(segundos):
    segundos = int(round(segundos or 0))
    return f"{segundos // 60} min {segundos % 60} s" if segundos >= 60 else f"{segundos} s"


def explicar_error(e):
    """Traduce el error técnico a una explicación y una acción concreta."""
    t = str(e)
    bajo = t.lower()
    if "413" in t or "request too large" in bajo or "too large" in bajo or "context_length" in bajo:
        causa = ("El texto es demasiado largo para el plan gratuito de Groq en una sola solicitud. "
                 "Prueba con un texto más corto o divídelo en dos partes.")
    elif "429" in t or "rate_limit" in bajo or "rate limit" in bajo or "resource_exhausted" in bajo:
        causa = ("Se agotó la cuota por minuto o por día del proveedor. Espera un minuto y vuelve a intentarlo. "
                 "Si sigue, la cuota diaria se renueva mañana.")
    elif "401" in t or "invalid api key" in bajo or "api_key_invalid" in bajo or "unauthorized" in bajo:
        causa = "Una API key no es válida. Revísala en los Secretos de Streamlit."
    elif "timed out" in bajo or "timeout" in bajo or "sin respuesta" in bajo:
        causa = "El proveedor tardó demasiado en responder. Vuelve a intentarlo en un momento."
    else:
        causa = "Ocurrió un error inesperado al procesar el texto."
    return causa, t[:600]


PALABRAS_POR_BLOQUE = 420   # bloques medianos: los modelos no resumen y se hacen menos llamadas
BLOQUES_EN_PARALELO = 2   # 2 a la vez: rápido sin agotar la cuota por minuto de los planes gratis


def es_titulo(parrafo):
    """Una línea corta sin punto final se trata como título y se deja tal cual."""
    p = parrafo.strip()
    return 0 < contar_palabras(p) <= 18 and p[-1:] not in ".!?;:" and "\n" not in p


def titulo_en_espanol(titulo, texto_completo=""):
    """En español los títulos van con mayúscula solo al inicio y en nombres propios (norma RAE).
    "El Futuro en Nuestras Manos" -> "El futuro en nuestras manos". Los nombres propios que en el
    texto aparecen con mayúscula a mitad de oración se respetan, igual que las siglas (IA, ONU)."""
    palabras = titulo.split()
    largas = [w for w in palabras if len(w.strip(':,.¿?¡!"()')) > 3]
    if len(largas) < 2 or sum(1 for w in largas if w[:1].isupper()) / len(largas) < 0.6:
        return titulo  # no está escrito con mayúscula en cada palabra
    propios = set(re.findall(r"(?<=[a-záéíóúñ,;] )([A-ZÁÉÍÓÚÑ][a-záéíóúñü]+)", texto_completo or ""))
    salida, inicio = [], True
    for w in palabras:
        limpia = w.strip(':,.¿?¡!"()')
        if inicio or limpia.isupper() or limpia in propios or not limpia[:1].isupper():
            salida.append(w)
        else:
            salida.append(w.replace(limpia, limpia[:1].lower() + limpia[1:], 1))
        inicio = w.endswith(":")
    return " ".join(salida)


def dividir_en_bloques(texto):
    """Agrupa párrafos en bloques de ~320 palabras. Devuelve [(es_titulo, texto)]."""
    bloques, actual = [], []
    for par in dividir_parrafos(texto):
        if es_titulo(par):
            if actual:
                bloques.append((False, "\n\n".join(actual))); actual = []
            bloques.append((True, par))
            continue
        if actual and contar_palabras("\n\n".join(actual + [par])) > PALABRAS_POR_BLOQUE:
            bloques.append((False, "\n\n".join(actual))); actual = []
        actual.append(par)
    if actual:
        bloques.append((False, "\n\n".join(actual)))
    return bloques


def plan_para_bloque(plan, indice):
    """Cada bloque empieza los pasos intermedios con un proveedor distinto, para repartir la carga."""
    nuevo = dict(plan)
    for paso in ("ingles", "espanol", "estructura"):
        lista = plan[paso]
        rapidos = [p for p in lista if p not in ("nvidia", "openrouter")]
        lentos = [p for p in lista if p in ("nvidia", "openrouter")]
        if len(rapidos) > 1:
            k = indice % len(rapidos)
            rapidos = rapidos[k:] + rapidos[:k]
        nuevo[paso] = rapidos + lentos
    return nuevo


def procesar_bloque(texto_base, plan, partir, avisos, opciones):
    """Todo el flujo para un bloque. No toca la interfaz (corre en paralelo)."""
    usados, tiempos = {}, {}
    medida = instrucciones_de_medida(texto_base, partir=partir)

    if not opciones["profundo"]:
        # MODO RÁPIDO: una sola llamada que reescribe, reestructura y limpia a la vez
        entrada = f"{medida}\n\nTEXTO A REESCRIBIR:\n{texto_base}"
        texto_generado, modelo_final = generar(con_muestra(PROMPT_RAPIDO, opciones.get("muestra")), entrada,
                                               TEMP_FINAL, "final", plan, avisos, usados, tiempos)
        texto_generado, _ = clean_text(texto_generado)
        return revisar_bloque(texto_generado, modelo_final, texto_base, medida, plan, partir, avisos, opciones, usados, tiempos)

    medida_igual = instrucciones_de_medida(texto_base, partir=False)

    # CAPA B: retrotraducción o paráfrasis
    if opciones["retro"]:
        texto_en, _ = generar(PROMPT_EN, texto_base, 0.6, "ingles", plan, avisos, usados, tiempos)
        borrador, _ = generar(PROMPT_ES, f"{medida_igual}\n\nTEXTO:\n{texto_en}", 0.85, "espanol", plan, avisos, usados, tiempos)
    else:
        borrador, _ = generar(PROMPT_PARAFRASIS, f"{medida_igual}\n\nTEXTO:\n{texto_base}", 0.85, "espanol", plan, avisos, usados, tiempos)
    borrador, _ = clean_text(borrador)

    # CAPA DE ESTRUCTURA
    if partir:
        try:
            reestructurado, _ = generar(PROMPT_ESTRUCTURA, f"{medida}\n\nTEXTO A REESTRUCTURAR:\n{borrador}",
                                        0.85, "estructura", plan, avisos, usados, tiempos)
            reestructurado, _ = clean_text(reestructurado)
            if contar_palabras(reestructurado) >= 0.88 * contar_palabras(texto_base):
                borrador = reestructurado
        except Exception as e_est:
            avisos.append(f"No se pudo aplicar la capa de estructura en un bloque ({e_est}).")

    # REDACCIÓN FINAL
    entrada_final = f"{medida}\n\nTEXTO ORIGINAL (referencia de contenido y extensión):\n{texto_base}\n\nBORRADOR A REESCRIBIR:\n{borrador}"
    texto_generado, modelo_final = generar(con_muestra(PROMPT_FINAL, opciones.get("muestra")), entrada_final,
                                           TEMP_FINAL, "final", plan, avisos, usados, tiempos)
    texto_generado, _ = clean_text(texto_generado)
    return revisar_bloque(texto_generado, modelo_final, texto_base, medida, plan, partir, avisos, opciones, usados, tiempos)


def revisar_bloque(texto_generado, modelo_final, texto_base, medida, plan, partir, avisos, opciones, usados, tiempos):
    """CAPA C: revisión en código y, solo si hace falta, una corrección."""
    problemas_iniciales, _ = auditar_texto(texto_generado, texto_base, partir)
    rondas = 2 if opciones["profundo"] else 1
    for ronda in range(rondas):
        problemas, _ = auditar_texto(texto_generado, texto_base, partir)
        fidelidad = problemas_de_fidelidad(texto_generado, texto_base, partir)
        if not opciones["auditoria"]:
            problemas = fidelidad
        # En modo rápido solo se corrige si se perdió contenido o hay varios problemas de estilo
        if not problemas or (not opciones["profundo"] and not fidelidad and len(problemas) < 3):
            break
        lista = "\n".join(f"- {p}" for p in problemas)
        plan_corr = plan
        if palabras_otro_idioma(texto_generado, texto_base):
            # El proveedor que mezcló idiomas pasa al final de la fila para esta corrección
            autor = next((pid for pid, p in PROVEEDORES.items() if modelo_final.startswith(p["nombre"] + " ")), None)
            if autor:
                plan_corr = dict(plan)
                plan_corr["correccion"] = [p for p in plan["correccion"] if p != autor] + [autor]
        try:
            corregido, _ = generar(
                con_muestra(PROMPT_CORRECCION, opciones.get("muestra")),
                f"{medida}\n\nPROBLEMAS DETECTADOS:\n{lista}\n\nORIGINAL:\n{texto_base}\n\nTEXTO:\n{texto_generado}",
                0.7, "correccion", plan_corr, avisos, usados, tiempos,
            )
        except Exception as e_corr:
            avisos.append(f"No se pudo hacer la corrección automática de un bloque ({e_corr}).")
            break
        corregido, _ = clean_text(corregido)
        nuevos, _ = auditar_texto(corregido, texto_base, partir)
        fid_antes = len(fidelidad)
        fid_despues = len(problemas_de_fidelidad(corregido, texto_base, partir))
        no_acorta = contar_palabras(corregido) >= 0.95 * contar_palabras(texto_generado) or fid_despues < fid_antes
        if len(nuevos) < len(problemas) and fid_despues <= fid_antes and no_acorta:
            texto_generado = corregido
        else:
            break
    return texto_generado, modelo_final, usados, tiempos, len(problemas_iniciales)


def reescribir_parrafo_marcado(parrafo, marcadas, plan, opciones, avisos, usados, tiempos):
    """Reescribe un párrafo marcado por un detector. Si pierde contenido, devuelve el párrafo sin cambios."""
    lista = "\n".join(f"- {o}" for o in marcadas) if marcadas else "- (todo el párrafo)"
    entrada = (f"El párrafo tiene {contar_palabras(parrafo)} palabras.\n\nORACIONES MARCADAS:\n{lista}\n\n"
               f"PÁRRAFO:\n{parrafo}")
    try:
        nuevo, _ = generar(con_muestra(PROMPT_DETECTOR, opciones.get("muestra")), entrada, TEMP_FINAL,
                           "detector", plan, avisos, usados, tiempos)
    except Exception:
        return parrafo
    nuevo, _ = clean_text(nuevo)
    nuevo = " ".join(dividir_parrafos(nuevo))          # sigue siendo un solo párrafo
    largo_ok = 0.88 * contar_palabras(parrafo) <= contar_palabras(nuevo) <= 1.30 * contar_palabras(parrafo)
    if not nuevo or not largo_ok or datos_faltantes(parrafo, nuevo):
        return parrafo
    return nuevo


def ajustar_con_detectores(texto, plan, opciones, avisos, usados, tiempos, avanzar):
    """CAPA D: mide, reescribe solo lo marcado y vuelve a medir. Se queda con la versión de menor puntaje."""
    historial, mejor = [], None

    def peor_de(mediciones):
        validas = [m["ia"] for m in mediciones if "ia" in m]
        return max(validas) if validas else None

    for ronda in range(RONDAS_DETECTOR + 1):
        avanzar(f"Midiendo en {' y '.join(detectores_activos())} (medición {ronda + 1})")
        mediciones = medir_detectores(texto)
        peor = peor_de(mediciones)
        if peor is None:
            # Ningún detector respondió: no hay con qué ajustar
            if mejor is None:
                mejor = (None, texto, mediciones)
            break
        historial.append(peor)
        if mejor is None or mejor[0] is None or peor < mejor[0]:
            mejor = (peor, texto, mediciones)
        if peor < OBJETIVO_IA or ronda == RONDAS_DETECTOR:
            break

        frases = [f for m in mediciones if m.get("ia", 0) >= OBJETIVO_IA for f in m.get("frases", [])]
        parrafos = dividir_parrafos(texto)
        candidatos = []
        for i, p in enumerate(parrafos):
            if es_titulo(p):
                continue
            marcadas = oraciones_marcadas(p, frases)
            if marcadas:
                candidatos.append((i, marcadas))
        if not candidatos:
            # El detector dio puntaje pero no señaló oraciones: se retocan los párrafos de ritmo más plano
            def planitud(p):
                lp = [len(o.split()) for o in dividir_oraciones(p)]
                return statistics.pstdev(lp) / statistics.mean(lp) if len(lp) >= 2 else 0.0
            orden = sorted((i for i, p in enumerate(parrafos) if not es_titulo(p)), key=lambda i: planitud(parrafos[i]))
            candidatos = [(i, []) for i in orden]
        candidatos = candidatos[:PARRAFOS_POR_RONDA]

        # Cada ronda empieza por un modelo distinto
        plan_ronda = dict(plan)
        lista = plan["detector"]
        k = ronda % len(lista)
        plan_ronda["detector"] = lista[k:] + lista[:k]

        avanzar(f"Reescribiendo {len(candidatos)} párrafo(s) marcados (ronda {ronda + 1} de {RONDAS_DETECTOR})")
        with ThreadPoolExecutor(max_workers=BLOQUES_EN_PARALELO) as pool:
            nuevos = list(pool.map(
                lambda c: reescribir_parrafo_marcado(parrafos[c[0]], c[1], plan_ronda, opciones, avisos, usados, tiempos),
                candidatos,
            ))
        cambiados = 0
        for (i, _), nuevo in zip(candidatos, nuevos):
            if nuevo != parrafos[i]:
                parrafos[i] = nuevo
                cambiados += 1
        if not cambiados:
            break
        texto, _ = clean_text("\n\n".join(parrafos))

    peor, texto_final, mediciones = mejor
    info = {"mediciones": [{k: v for k, v in m.items() if k != "frases"} for m in mediciones],
            "historial": historial, "rondas": max(0, len(historial) - 1)}
    for m in mediciones:
        if "error" in m:
            avisos.append(f"{m['nombre']} no respondió ({m['error'][:140]}).")
        elif m["ia"] >= OBJETIVO_IA:
            avisos.append(f"{m['nombre']} todavía marca {round(m['ia'])}% de IA tras {info['rondas']} ronda(s) de ajuste. "
                          "Cambia a mano las frases que señale o vuelve a pulsar Humanizar texto.")
    return texto_final, info


def procesar(texto_original, estado):
    """Corre todo el flujo y devuelve (texto_final, modelo, avisos, auditoria, texto_base)."""
    avisos = []
    plan = armar_plan()
    inicio_total = time.monotonic()
    esperas = [0]

    def avanzar(texto):
        estado.update(label=f"{texto} ({round(time.monotonic() - inicio_total)} s)")

    partir = usar_estructura
    opciones = {"retro": usar_retrotraduccion, "auditoria": usar_auditoria, "profundo": modo_profundo,
                "muestra": muestra_estilo}

    def una_pasada(texto_entrada, partir_p, numero):
        """Humaniza un texto completo por bloques. Devuelve (texto, modelo, usados, tiempos, antes, bloques)."""
        sufijo = f" (pasada {numero} de {pasadas})" if pasadas > 1 else ""
        bloques = dividir_en_bloques(texto_entrada)
        a_procesar = [i for i, (titulo, _) in enumerate(bloques) if not titulo]
        resultados = {}
        total = len(a_procesar)
        avanzar((f"Humanizando {total} bloque(s) en paralelo" if total > 1 else "Humanizando el texto") + sufijo)
        hilos = 1 if numero > 1 else max(1, min(BLOQUES_EN_PARALELO, total))
        with ThreadPoolExecutor(max_workers=hilos) as pool:
            futuros = {
                pool.submit(procesar_bloque, bloques[i][1], plan_para_bloque(plan, n + numero - 1), partir_p, avisos, opciones): i
                for n, i in enumerate(a_procesar)
            }
            pendientes = set(futuros)
            fallidos = {}
            while pendientes:
                hechos, pendientes = wait(pendientes, timeout=1, return_when=FIRST_COMPLETED)
                for f in hechos:
                    try:
                        resultados[futuros[f]] = f.result()
                    except Exception as e_bloque:
                        fallidos[futuros[f]] = e_bloque
                listos = total - len(pendientes)
                avanzar((f"Bloques listos: {listos} de {total}" if total > 1 else "Humanizando el texto") + sufijo)

        # Un bloque que falló (por cuota, casi siempre) se reintenta solo, tras una pausa corta
        for n, i in enumerate(sorted(fallidos)):
            esperar_cuota(plan["final"][0], avanzar, esperas)
            avanzar(f"Reintentando un bloque que se quedó sin cuota ({n + 1} de {len(fallidos)})")
            time.sleep(2)
            try:
                resultados[i] = procesar_bloque(bloques[i][1], plan_para_bloque(plan, i + 1), partir_p, avisos, opciones)
                del fallidos[i]
            except Exception as e_bloque:
                fallidos[i] = e_bloque
        if fallidos and len(fallidos) == total:
            raise next(iter(fallidos.values()))   # nada se pudo procesar: se muestra el error
        for i, e_bloque in fallidos.items():
            # Mejor un resultado parcial que perder todo el trabajo
            resultados[i] = (bloques[i][1], "", {}, {}, 0)
            avisos.append(f"Un bloque no se pudo humanizar ({str(e_bloque)[:120]}) y quedó como estaba. "
                          "Espera un minuto y vuelve a pasar solo ese párrafo.")

        # Arma el texto en el orden original (los títulos quedan tal cual)
        partes, usados_p, tiempos_p, antes_p, modelo_p = [], {}, {}, 0, ""
        for i, (titulo, texto) in enumerate(bloques):
            if titulo:
                partes.append(titulo_en_espanol(texto, texto_entrada))
                continue
            texto_bloque, modelo_bloque, usados_b, tiempos_b, antes_b = resultados[i]
            partes.append(texto_bloque)
            modelo_p = modelo_p or modelo_bloque
            antes_p += antes_b
            for k, v in usados_b.items():
                usados_p.setdefault(k, v)
            for k, v in tiempos_b.items():
                tiempos_p[k] = max(tiempos_p.get(k, 0), v)   # en paralelo cuenta el bloque más lento
        return clean_text("\n\n".join(partes))[0], modelo_p, usados_p, tiempos_p, antes_p, total

    avanzar("Limpiando caracteres ocultos y formato")
    texto_base, _ = clean_text(texto_original)

    # Asegura que la lista de modelos de cada proveedor esté lista antes de abrir los hilos
    for pid in {p for pasos in plan.values() for p in pasos}:
        if pid not in MODELOS_RESUELTOS and PROVEEDORES[pid]["tipo"] != "gemini":
            try:
                MODELOS_RESUELTOS[pid] = detectar_modelos(pid, CLAVES[pid])
            except Exception:
                pass

    texto_limpio, modelo_final, usados, tiempos, antes, total = una_pasada(texto_base, partir, 1)

    # PASADAS EXTRA: el resultado vuelve a entrar al humanizador (sin volver a dividir párrafos)
    for numero in range(2, pasadas + 1):
        esperar_cuota(plan["final"][0], avanzar, esperas)
        try:
            otro, modelo_p, usados_p, tiempos_p, _, _ = una_pasada(texto_limpio, False, numero)
        except Exception as e_pasada:
            avisos.append(f"La pasada {numero} no se pudo completar ({str(e_pasada)[:120]}). Quedó el resultado de la pasada anterior.")
            break
        # Se acepta solo si no se alejó del original: mismo largo y mismos datos
        corto = contar_palabras(otro) < 0.85 * contar_palabras(texto_base)
        pierde = len(datos_faltantes(texto_base, otro)) > len(datos_faltantes(texto_base, texto_limpio))
        if corto or pierde:
            avisos.append(f"La pasada {numero} {'acortó el texto' if corto else 'perdió datos del original'} y se descartó. "
                          "Quedó el resultado de la pasada anterior.")
            break
        texto_limpio, modelo_final = otro, (modelo_p or modelo_final)
        for k, v in usados_p.items():
            usados.setdefault(k, v)
        for k, v in tiempos_p.items():
            tiempos[k] = tiempos.get(k, 0) + v

    # CAPA D: medir en los detectores conectados y reescribir solo lo que marcan
    info_detectores = None
    if usar_detectores and detectores_activos():
        try:
            texto_limpio, info_detectores = ajustar_con_detectores(
                texto_limpio, plan, opciones, avisos, usados, tiempos, avanzar)
        except Exception as e_det:
            avisos.append(f"No se pudo verificar con los detectores ({str(e_det)[:140]}).")

    problemas_finales, metricas = auditar_texto(texto_limpio, texto_base, partir)
    metricas["palabras_original"] = contar_palabras(texto_base)
    metricas["palabras_resultado"] = contar_palabras(texto_limpio)
    metricas["bloques"] = total
    metricas["pasadas"] = pasadas
    auditoria = {"antes": antes, "despues": problemas_finales, "metricas": metricas, "modelos": usados,
                 "detectores": info_detectores,
                 "tiempos": {k: round(v, 1) for k, v in tiempos.items()},
                 "tiempo_total": round(time.monotonic() - inicio_total, 1)}
    return texto_limpio, modelo_final, avisos, auditoria, texto_base


paneles = st.container(key="paneles")
col1, col2 = paneles.columns(2, gap="large")

with col1:
    actual = st.session_state.get("input_original_key", "")
    st.markdown(
        f'<div class="panel-head"><span class="panel-title">Texto original</span>'
        f'<span class="panel-meta">{contar_palabras(actual)} palabras</span></div>',
        unsafe_allow_html=True,
    )
    texto_original = st.text_area(
        "Texto original", height=400, label_visibility="collapsed",
        max_chars=MAX_CARACTERES, key="input_original_key",
        placeholder="Pega aquí el texto que quieres reescribir.",
    )
    col_btn1, col_btn2 = st.container(key="botones").columns([3, 1], gap="small")
    with col_btn1:
        refinar = st.button("Humanizar texto", width="stretch", type="primary")
    with col_btn2:
        st.button("Limpiar", on_click=limpiar_textos, width="stretch")

    if refinar:
        if not texto_original.strip():
            st.warning("Pega un texto primero.")
        elif not conectados:
            st.error("Falta configurar al menos una API key en los Secretos de Streamlit.")
        else:
            error_proceso = None
            # Reloj en vivo: corre en el navegador mientras la app trabaja
            reloj = st.empty()
            with reloj.container():
                html_reloj = """
                <style>
                :root { --ink-soft: #A6ACB6; --ink: #ECEEF1;
                        --font-ui: 'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif; }
                html, body { margin: 0; background-color: transparent; overflow: clip; }
                p { margin: 6px 0 0 0; font-family: var(--font-ui); font-size: 15px; color: var(--ink-soft);
                    font-variant-numeric: tabular-nums; }
                b { color: var(--ink); font-weight: 600; }
                </style>
                <p>Tiempo transcurrido: <b id="t">0:00</b></p>
                <script>
                const t0 = Date.now(); const el = document.getElementById('t');
                setInterval(function () {
                    const s = Math.floor((Date.now() - t0) / 1000);
                    el.textContent = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
                }, 250);
                </script>
                """
                if hasattr(st, "iframe"):
                    st.iframe(html_reloj, height=34)
                else:
                    components.html(html_reloj, height=34)
            with st.status("Preparando", expanded=False) as estado:
                try:
                    texto_limpio, modelo_final, avisos, auditoria, texto_base = procesar(texto_original, estado)
                except Exception as e:
                    error_proceso = e
                    reloj.empty()
                    estado.update(label="No se pudo terminar", state="error")
                else:
                    reloj.empty()
                    estado.update(label=f"Listo en {formato_tiempo(auditoria['tiempo_total'])}", state="complete")
                    st.session_state["texto_humanizado"] = texto_limpio
                    st.session_state["texto_fuente"] = texto_base
                    st.session_state["avisos"] = avisos
                    st.session_state["auditoria"] = auditoria
                    st.toast(f"Listo en {formato_tiempo(auditoria['tiempo_total'])}. Redacción final: {modelo_final}.")
                    st.rerun()
            if error_proceso is not None:
                causa, detalle = explicar_error(error_proceso)
                st.error(causa)
                with st.expander("Ver detalle técnico"):
                    st.code(detalle, language=None)

with col2:
    resultado = st.session_state["texto_humanizado"]
    aud_meta = st.session_state.get("auditoria") or {}
    if resultado and aud_meta.get("tiempo_total") is not None:
        meta = f"{contar_palabras(resultado)} palabras, listo en {formato_tiempo(aud_meta['tiempo_total'])}"
    elif resultado:
        meta = f"{contar_palabras(resultado)} palabras"
    else:
        meta = "Sin resultado todavía"
    st.markdown(
        f'<div class="panel-head"><span class="panel-title">Texto humanizado</span>'
        f'<span class="panel-meta">{meta}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(html_hoja(resultado), unsafe_allow_html=True)

    if resultado:
        # Escapa "</" para que un texto con "</script>" no rompa el HTML del botón
        texto_json = json.dumps(resultado).replace("</", "<\\/")
        html_boton = f"""
        <style>
        :root {{
            --surface-2: #20242B; --surface-3: #2A2F38; --ink: #ECEEF1; --human: #22D3E6;
            --font-ui: 'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
        }}
        html, body {{ margin: 0; padding: 0; overflow: clip; background-color: transparent; }}
        #copyBtn {{
            box-sizing: border-box; width: 100%; height: 44px; margin-top: 12px;
            background-color: var(--surface-2); color: var(--ink); border: 0; border-radius: 4px;
            font-family: var(--font-ui); font-size: 16px; font-weight: 600; cursor: pointer;
            transition: background-color 120ms ease, transform 120ms ease;
        }}
        #copyBtn:hover {{ background-color: var(--surface-3); }}
        #copyBtn:active {{ transform: translateY(1px); }}
        #copyBtn:focus-visible {{ outline: 2px solid var(--human); outline-offset: 2px; transition: none; }}
        #copyBtn.ok {{ color: var(--human); }}
        @media (prefers-reduced-motion: reduce) {{ #copyBtn {{ transition: none; }} }}
        </style>
        <button id="copyBtn" type="button">Copiar texto humanizado</button>
        <script>
        const btn = document.getElementById('copyBtn');
        btn.addEventListener('click', function() {{
            const text = {texto_json};
            const copiar = (navigator.clipboard && navigator.clipboard.writeText)
                ? navigator.clipboard.writeText(text) : Promise.reject();
            copiar.catch(function() {{
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.setAttribute('readonly', '');                 // iOS: no abre el teclado
                ta.style.position = 'fixed'; ta.style.opacity = '0'; ta.style.fontSize = '16px';  // sin zoom
                document.body.appendChild(ta);
                ta.focus(); ta.select(); ta.setSelectionRange(0, text.length);   // iOS necesita el rango
                document.execCommand('copy'); document.body.removeChild(ta);
            }}).then(function() {{
                btn.textContent = 'Copiado'; btn.classList.add('ok');
                setTimeout(function() {{
                    btn.textContent = 'Copiar texto humanizado'; btn.classList.remove('ok');
                }}, 2000);
            }});
        }});
        </script>
        """
        # st.iframe reemplaza a components.html en Streamlit nuevo; respaldo para versiones viejas
        if hasattr(st, "iframe"):
            st.iframe(html_boton, height=60)
        else:
            components.html(html_boton, height=60)

for aviso in st.session_state["avisos"]:
    st.warning(aviso)

# ==========================================
# 4. RITMO DE ORACIONES Y REVISIÓN
# ==========================================
aud = st.session_state.get("auditoria")
if st.session_state["texto_humanizado"] and aud:
    pendientes = aud["despues"]
    if pendientes:
        items = "".join(f"<li>{html_lib.escape(p)}</li>" for p in pendientes)
        bloque_pendientes = (
            f'<div class="pendientes"><p class="pendientes-titulo">'
            f'Quedan {len(pendientes)} punto(s) para revisar a mano</p><ul>{items}</ul></div>'
        )
    else:
        hecho = (f"La revisión corrigió {aud['antes']} punto(s) y no quedan pendientes."
                 if aud["antes"] else "La revisión no encontró puntos pendientes.")
        bloque_pendientes = (
            f'<p class="sin-pendientes">{hecho} Igual conviene leerlo y cambiar alguna frase con tus palabras.</p>'
        )
    fuente = st.session_state.get("texto_fuente", "")
    m_aud = aud.get("metricas", {})
    if m_aud.get("palabras_original"):
        porcentaje = round(100 * m_aud["palabras_resultado"] / m_aud["palabras_original"])
        extension = (f'<p class="ritmo-intro">Extensión: {m_aud["palabras_resultado"]} palabras de '
                     f'{m_aud["palabras_original"]} del original ({porcentaje}%). '
                     f'Párrafos: {len(dividir_parrafos(st.session_state["texto_humanizado"]))} de {len(dividir_parrafos(fuente))}.</p>')
    else:
        extension = ""
    usados = aud.get("modelos") or {}
    etiquetas = {"ingles": "al inglés", "espanol": "vuelta al español", "estructura": "estructura",
                 "final": "redacción final", "correccion": "corrección", "detector": "ajuste por detectores"}
    if usados:
        tiempos_aud = aud.get("tiempos") or {}
        modelos_txt = "; ".join(
            f"{etiquetas[k]}: {html_lib.escape(v)} ({formato_tiempo(tiempos_aud.get(k, 0))})"
            for k, v in usados.items() if k in etiquetas
        )
        n_bloques = (aud.get("metricas") or {}).get("bloques", 1)
        en_bloques = f" Se procesó en {n_bloques} bloques en paralelo; cada tiempo es el del bloque más lento." if n_bloques > 1 else ""
        extension += f'<p class="ritmo-intro">Modelos y tiempos: {modelos_txt}. Total: {formato_tiempo(aud.get("tiempo_total", 0))}.{en_bloques}</p>'
    info_det = aud.get("detectores")
    if info_det:
        partes_det = []
        for m in info_det["mediciones"]:
            if "ia" in m:
                partes_det.append(f"{html_lib.escape(m['nombre'])}: {round(m['ia'])}% de IA")
            else:
                partes_det.append(f"{html_lib.escape(m['nombre'])}: sin respuesta")
        camino = ""
        if len(info_det["historial"]) > 1:
            camino = (" Peor puntaje en cada medición: "
                      + ", ".join(f"{round(h)}%" for h in info_det["historial"]) + ".")
        extension += (f'<p class="ritmo-intro">Detectores: {"; ".join(partes_det)}.{camino} '
                      "QuillBot y Grammarly no tienen API: pega el texto en sus páginas para revisarlos.</p>")
    filas = (fila_ritmo("Original", fuente, "barra-orig") if fuente else "") + \
        fila_ritmo("Humanizado", st.session_state["texto_humanizado"], "barra-hum")
    st.markdown(
        '<section class="ritmo" aria-labelledby="ritmo-titulo">'
        '<h2 class="ritmo-titulo" id="ritmo-titulo">Ritmo de las oraciones</h2>'
        '<p class="ritmo-intro">Cada barra es una oración y su altura es el número de palabras. '
        'Un texto generado suele tener barras parejas; uno escrito por una persona sube y baja.</p>'
        f'{extension}{filas}{bloque_pendientes}</section>',
        unsafe_allow_html=True,
    )

st.markdown(PIE_HTML, unsafe_allow_html=True)
