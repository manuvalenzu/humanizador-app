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
import html as html_lib
import unicodedata

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

MI_API_KEY = leer_secreto("GEMINI_API_KEY")
MI_GROQ_KEY = leer_secreto("GROQ_API_KEY")
GEMINI_MODEL = leer_secreto("GEMINI_MODEL", "gemini-3.6-flash")

# Límite del texto de entrada (caracteres, contando espacios)
MAX_CARACTERES = 8000

# ==========================================
# AUTO-DETECCIÓN DE MODELOS ACTIVOS EN GROQ
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def obtener_modelos_groq_activos(api_key):
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json().get("data", [])

    # "compound" son agentes con búsqueda web: alteran el contenido, no sirven aquí
    excluidos = ("whisper", "tts", "guard", "safeguard", "playai", "orpheus", "embed",
                 "vision", "audio", "compound", "allam")
    candidatos = []
    for item in data:
        mid = item.get("id", "")
        low = mid.lower()
        if mid and item.get("active", True) and not any(x in low for x in excluidos):
            candidatos.append(mid)

    # Modelos grandes primero; los pequeños ("8b", "instant") al final
    prioridades = ("llama-3.3-70b", "gpt-oss-120b", "kimi", "llama-4-maverick", "qwen",
                   "llama-4", "deepseek", "gpt-oss", "mistral", "llama-3", "gemma")

    def puntaje(mid):
        low = mid.lower()
        if "8b" in low or "instant" in low:
            return len(prioridades) + 1
        for idx, pref in enumerate(prioridades):
            if pref in low:
                return idx
        return len(prioridades)

    candidatos.sort(key=puntaje)
    return candidatos


def quitar_razonamiento(texto):
    """qwen3 / deepseek-r1 devuelven su razonamiento entre <think>...</think>: se elimina."""
    if not texto:
        return ""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r"^.*?</think>", "", texto, flags=re.DOTALL | re.IGNORECASE)
    return texto.strip()


def llamar_groq_dinamico(api_key, system_prompt, user_text, temperature=1.0):
    modelos = obtener_modelos_groq_activos(api_key)
    if not modelos:
        raise RuntimeError("No se encontraron modelos de chat activos en tu cuenta de Groq.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # La respuesta mide más o menos lo mismo que el texto a reescribir; se deja margen.
    # Sin este tope, Groq reserva miles de tokens de salida y rechaza el pedido por tamaño.
    max_salida = max(1500, min(8000, len(user_text) // 3 + 800))

    ultimo_error = ""
    for modelo in modelos[:4]:
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": temperature,
            "top_p": 0.95,
            "frequency_penalty": 0.25,
            "presence_penalty": 0.2,
            "max_tokens": max_salida,
        }
        for intento in range(3):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
            except requests.RequestException as e:
                ultimo_error = f"Groq ({modelo}) sin respuesta: {e}"
                break
            # Si el modelo no acepta las penalizaciones, se reintenta sin ellas
            if resp.status_code == 400 and "penalty" in resp.text and intento == 0:
                payload.pop("frequency_penalty", None)
                payload.pop("presence_penalty", None)
                continue
            # Límite por minuto: si Groq pide esperar poco, espera y reintenta el mismo modelo
            if resp.status_code == 429 and intento < 2:
                try:
                    espera = float(resp.headers.get("retry-after", "0"))
                except (TypeError, ValueError):
                    espera = 0
                if 0 < espera <= 25:
                    time.sleep(espera + 0.5)
                    continue
            if resp.status_code == 200:
                try:
                    contenido = resp.json()["choices"][0]["message"].get("content") or ""
                except (ValueError, KeyError, IndexError):
                    contenido = ""
                contenido = quitar_razonamiento(contenido)
                if contenido:
                    return contenido, modelo
                ultimo_error = f"Groq ({modelo}) devolvió una respuesta vacía."
            else:
                ultimo_error = f"Groq ({modelo}) HTTP {resp.status_code}: {resp.text[:200]}"
            break

    raise RuntimeError(ultimo_error)

# ==========================================
# LLAMADA A GEMINI CON REINTENTO ANTE ERRORES TEMPORALES
# ==========================================
def llamar_gemini(client, contents, system_instruction):
    # Gemini 3.6 Flash ya no usa temperature / top_p / top_k (Google pide quitarlos)
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
            # Cuota agotada (429): no reintenta para no perder tiempo
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
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
]
PATRON_ENUMERACION = re.compile(
    r"\b[\wáéíóúñü]+(?: [\wáéíóúñü]+){0,2}, [\wáéíóúñü]+(?: [\wáéíóúñü]+){0,2},? (?:y|e) [\wáéíóúñü]+",
    re.IGNORECASE,
)
PATRON_GERUNDIO = re.compile(r", ([\wáéíóúñ]+(?:ando|iendo|yendo))\b", re.IGNORECASE)


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
    return par_ref, max(par_ref + 2, math.ceil(par_ref * 1.6))


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
        if cv < 0.40:
            problemas.append(
                f"Ritmo demasiado parejo (las oraciones miden casi lo mismo, promedio {media:.0f} palabras). "
                "Mezcla oraciones de 5 a 9 palabras con otras de 20 a 30."
            )
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

    if len(oraciones) >= 5:
        inicios = [o.split()[0].lower().strip(",.") for o in oraciones]
        for palabra in set(inicios):
            if inicios.count(palabra) >= 3 and inicios.count(palabra) / len(inicios) > 0.25:
                problemas.append(f'Muchas oraciones empiezan con "{palabra}". Varía los inicios.')

    if oraciones:
        ultima = oraciones[-1].lower()
        if re.search(r"\b(debe|deben|deberá|necesario|desafío|reto|futuro|oportunidad|clave|en definitiva)\b", ultima):
            problemas.append(f'La última oración suena a moraleja: "{oraciones[-1][:90]}". Reescríbela como un hecho concreto, sin borrar su contenido.')

    metricas["problemas"] = len(problemas)
    return problemas, metricas

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

@media (max-width: 768px) {
    .block-container { padding: 1.5rem 1rem 2rem 1rem !important; }
    .hoja { height: 340px; padding: 1.25rem 1.25rem; }
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
            '<p class="vacia-texto">Pega un texto a la izquierda y pulsa Refinar texto. '
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
    lectura = "ritmo parejo" if cv < 0.40 else "ritmo variado"
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

    if not MI_API_KEY:
        st.warning("Falta GEMINI_API_KEY en Secretos. Puedes pegarla aquí.")
        MI_API_KEY = st.text_input("API key de Gemini", type="password").strip()

    if not MI_GROQ_KEY:
        st.info("Agrega GROQ_API_KEY para activar el modo híbrido.")
        MI_GROQ_KEY = st.text_input("API key de Groq (opcional)", type="password").strip()

    solo_groq = False
    if MI_GROQ_KEY:
        solo_groq = st.toggle(
            "Usar solo Groq",
            value=True,
            help="Ahorra la cuota diaria de Gemini. Gemini queda solo como respaldo.",
        )

    if MI_GROQ_KEY:
        try:
            modelos_disponibles = obtener_modelos_groq_activos(MI_GROQ_KEY)
            modelo_principal = modelos_disponibles[0] if modelos_disponibles else "Groq automático"
        except Exception:
            modelo_principal = "Groq automático"
        motor = f"Groq ({modelo_principal})" if solo_groq else f"Gemini y Groq ({modelo_principal})"
    else:
        motor = "Gemini"
    st.markdown(
        f'<div class="motor"><p class="motor-label">Motor en uso</p>'
        f'<p class="motor-valor">{html_lib.escape(motor)}</p></div>',
        unsafe_allow_html=True,
    )

    usar_retrotraduccion = st.toggle(
        "Retrotraducción español, inglés, español",
        value=True,
        help="Capa B: desarma el texto pasándolo por el inglés antes de la redacción final.",
    )
    usar_estructura = st.toggle(
        "Romper estructura de párrafos",
        value=True,
        help="Capa de estructura: divide los párrafos (4 pasan a 5 o 6) y varía mucho el largo de las oraciones, sin resumir.",
    )
    usar_auditoria = st.toggle(
        "Revisión y corrección automática",
        value=True,
        help="Capa C: revisa ritmo, muletillas, enumeraciones, gerundios y cierre, y corrige hasta 2 veces.",
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
1. ROMPE LA ESTRUCTURA DE LOS PÁRRAFOS: si el original tiene 4 párrafos, el resultado tiene 5 o 6 párrafos más cortos. Divide los párrafos largos por donde cambia la idea. Que los párrafos no midan lo mismo: alguno de dos oraciones, otro de cinco.
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
6. RITMO IRREGULAR: alterna sin patrón fijo frases cortas (4 a 8 palabras) con frases medianas y alguna larga (25 a 35 palabras) con un inciso natural entre comas.
7. VOCABULARIO: prefiere la palabra común sobre la culta ("usar" en vez de "utilizar", "hacer" en vez de "llevar a cabo", "empezar" en vez de "iniciar").
8. FORMATO: solo prosa en párrafos separados por una línea en blanco. Sin rayas largas (— o –), sin negritas, sin listas, sin títulos y sin comillas curvas.

Devuelve ÚNICAMENTE el texto final en español, sin comentarios ni saludos.
"""
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


def instrucciones_de_medida(original, partir=False):
    """Le dice al modelo cuánto mide el original y qué datos no puede perder."""
    datos = extraer_datos_clave(original)
    par = len(dividir_parrafos(original))
    if partir:
        objetivo = f"entre {par + 1} y {max(par + 1, math.ceil(par * 1.5))} párrafos más cortos"
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
# ENRUTADOR: usa el proveedor preferido y cae al otro si falla
# ==========================================
def generar(system_prompt, texto, temperature, preferir, client, avisos):
    """preferir: 'groq' o 'gemini'. Devuelve (texto, nombre_modelo)."""
    orden = ["groq", "gemini"] if preferir == "groq" else ["gemini", "groq"]
    errores = []
    for proveedor in orden:
        try:
            if proveedor == "groq" and MI_GROQ_KEY:
                resultado = llamar_groq_dinamico(MI_GROQ_KEY, system_prompt, texto, temperature=temperature)
            elif proveedor == "gemini" and client is not None:
                resultado = (llamar_gemini(client, texto, system_prompt), "Gemini")
            else:
                continue
        except Exception as e:
            errores.append(f"{proveedor.capitalize()}: {e}")
            continue
        if errores:
            aviso = f"{errores[0][:160]} Se usó el otro proveedor como respaldo."
            if aviso not in avisos:
                avisos.append(aviso)
        return resultado
    raise RuntimeError(" | ".join(errores) or "No hay ningún proveedor configurado.")



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


def procesar(texto_original, estado):
    """Corre todo el flujo y devuelve (texto_final, modelo, avisos, auditoria, texto_base)."""
    avisos = []
    client = genai.Client(api_key=MI_API_KEY) if MI_API_KEY else None
    pref_b = "groq" if (solo_groq or client is None) else "gemini"
    partir = usar_estructura

    estado.update(label="Limpiando caracteres ocultos y formato")
    texto_base, _ = clean_text(texto_original)
    medida_igual = instrucciones_de_medida(texto_base, partir=False)
    medida = instrucciones_de_medida(texto_base, partir=partir)

    # CAPA B: retrotraducción o paráfrasis (conserva los párrafos del original)
    if usar_retrotraduccion:
        estado.update(label="Pasando el texto al inglés")
        texto_en, _ = generar(PROMPT_EN, texto_base, 0.6, pref_b, client, avisos)
        estado.update(label="Volviendo al español con otra estructura")
        borrador, _ = generar(PROMPT_ES, f"{medida_igual}\n\nTEXTO:\n{texto_en}", 0.85, pref_b, client, avisos)
    else:
        estado.update(label="Reordenando cláusulas y conectores")
        borrador, _ = generar(PROMPT_PARAFRASIS, f"{medida_igual}\n\nTEXTO:\n{texto_base}", 0.85, pref_b, client, avisos)
    borrador, _ = clean_text(borrador)

    pref_final = "groq" if MI_GROQ_KEY else "gemini"

    # CAPA DE DESTRUCCIÓN DE ESTRUCTURA: más párrafos, más cortos, oraciones de largo extremo
    if partir:
        estado.update(label="Rompiendo la estructura de párrafos y oraciones")
        entrada_estructura = f"{medida}\n\nTEXTO A REESTRUCTURAR:\n{borrador}"
        try:
            reestructurado, _ = generar(PROMPT_ESTRUCTURA, entrada_estructura, 0.85, pref_final, client, avisos)
            reestructurado, _ = clean_text(reestructurado)
            # Solo se usa si no resumió
            if contar_palabras(reestructurado) >= 0.88 * contar_palabras(texto_base):
                borrador = reestructurado
            else:
                avisos.append("La capa de estructura acortó el texto, así que se usó el borrador anterior.")
        except Exception as e_est:
            avisos.append(f"No se pudo aplicar la capa de estructura ({e_est}).")

    # REDACCIÓN FINAL (temperatura 0.85: menos frases hechas)
    estado.update(label="Redactando la versión final")
    entrada_final = f"{medida}\n\nTEXTO ORIGINAL (referencia de contenido y extensión):\n{texto_base}\n\nBORRADOR A REESCRIBIR:\n{borrador}"
    texto_generado, modelo_final = generar(PROMPT_FINAL, entrada_final, 0.85, pref_final, client, avisos)
    texto_generado, _ = clean_text(texto_generado)

    # CAPA C: revisión en código y corrección puntual
    problemas_iniciales, _ = auditar_texto(texto_generado, texto_base, partir)
    rondas = 3 if usar_auditoria else 1
    for ronda in range(rondas):
        problemas, _ = auditar_texto(texto_generado, texto_base, partir)
        # Sin la revisión de estilo activada, igual se corrige si quedó resumido o perdió datos
        if not usar_auditoria:
            problemas = problemas_de_fidelidad(texto_generado, texto_base, partir)
        if not problemas:
            break
        estado.update(label=f"Corrigiendo {len(problemas)} punto(s) detectados en la revisión")
        lista = "\n".join(f"- {p}" for p in problemas)
        try:
            corregido, _ = generar(
                PROMPT_CORRECCION,
                f"{medida}\n\nPROBLEMAS DETECTADOS:\n{lista}\n\nORIGINAL:\n{texto_base}\n\nTEXTO:\n{texto_generado}",
                0.7, pref_final, client, avisos,
            )
        except Exception as e_corr:
            avisos.append(f"No se pudo hacer la corrección automática ({e_corr}).")
            break
        corregido, _ = clean_text(corregido)
        nuevos, _ = auditar_texto(corregido, texto_base, partir)
        fidelidad_antes = len(problemas_de_fidelidad(texto_generado, texto_base, partir))
        fidelidad_despues = len(problemas_de_fidelidad(corregido, texto_base, partir))
        # Se acepta si mejora y no vuelve a acortar el texto
        no_acorta = contar_palabras(corregido) >= 0.95 * contar_palabras(texto_generado) or fidelidad_despues < fidelidad_antes
        if len(nuevos) < len(problemas) and fidelidad_despues <= fidelidad_antes and no_acorta:
            texto_generado = corregido
        else:
            break

    texto_limpio, _ = clean_text(texto_generado)
    problemas_finales, metricas = auditar_texto(texto_limpio, texto_base, partir)
    metricas["palabras_original"] = contar_palabras(texto_base)
    metricas["palabras_resultado"] = contar_palabras(texto_limpio)
    auditoria = {"antes": len(problemas_iniciales), "despues": problemas_finales, "metricas": metricas}
    return texto_limpio, modelo_final, avisos, auditoria, texto_base


col1, col2 = st.columns(2, gap="large")

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
    col_btn1, col_btn2 = st.columns([3, 1], gap="small")
    with col_btn1:
        refinar = st.button("Refinar texto", width="stretch", type="primary")
    with col_btn2:
        st.button("Limpiar", on_click=limpiar_textos, width="stretch")

    if refinar:
        if not texto_original.strip():
            st.warning("Pega un texto primero.")
        elif not MI_API_KEY and not MI_GROQ_KEY:
            st.error("Falta configurar al menos una API key (Gemini o Groq) en la barra lateral.")
        else:
            error_proceso = None
            with st.status("Preparando", expanded=False) as estado:
                try:
                    texto_limpio, modelo_final, avisos, auditoria, texto_base = procesar(texto_original, estado)
                except Exception as e:
                    error_proceso = e
                    estado.update(label="No se pudo terminar", state="error")
                else:
                    estado.update(label="Listo", state="complete")
                    st.session_state["texto_humanizado"] = texto_limpio
                    st.session_state["texto_fuente"] = texto_base
                    st.session_state["avisos"] = avisos
                    st.session_state["auditoria"] = auditoria
                    st.toast(f"Listo. Procesado con {modelo_final}.")
                    st.rerun()
            if error_proceso is not None:
                causa, detalle = explicar_error(error_proceso)
                st.error(causa)
                with st.expander("Ver detalle técnico"):
                    st.code(detalle, language=None)

with col2:
    resultado = st.session_state["texto_humanizado"]
    meta = f"{contar_palabras(resultado)} palabras" if resultado else "Sin resultado todavía"
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
                ta.value = text; document.body.appendChild(ta); ta.select();
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
