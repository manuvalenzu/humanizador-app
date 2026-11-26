import re
import json
import time
import threading
import requests
import streamlit as st
import streamlit.components.v1 as components
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai


# ---------------------------------------------------------------------------
# Configuracion de la pagina
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Humanizador Pro",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Tema oscuro CSS completo
# ---------------------------------------------------------------------------
CSS_TEMA = """
<style>
:root {
    --bg: #0F1114;
    --surface: #171A1F;
    --surface-2: #20242B;
    --surface-3: #2A2F38;
    --ink: #ECEEF1;
    --ink-soft: #A6ACB6;
    --accent: #F2552C;
    --human: #22D3E6;
    --paper: #F2F1EC;
    --paper-ink: #1A1B1E;
}
body, .stApp, .stSidebar, .stSidebarHeader {
    background-color: var(--bg) !important;
    color: var(--ink) !important;
    font-family: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.stSidebar {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--surface-3) !important;
}
.stButton>button {
    background-color: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
.stButton>button:hover {
    background-color: #d94820 !important;
    transform: translateY(-1px) !important;
}
.stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div, .stMultiSelect>div>div>div {
    background-color: var(--surface-2) !important;
    color: var(--ink) !important;
    border: 1px solid var(--surface-3) !important;
    border-radius: 6px !important;
}
.stMetric {
    background-color: var(--surface-2) !important;
    padding: 12px !important;
    border-radius: 8px !important;
    border: 1px solid var(--surface-3) !important;
}
[data-testid="stMetricValue"] {
    color: var(--human) !important;
}
[data-testid="stMetricLabel"] {
    color: var(--ink-soft) !important;
}
.stDivider {
    border-color: var(--surface-3) !important;
}
h1, h2, h3 {
    color: var(--ink) !important;
    font-family: 'Instrument Sans', sans-serif !important;
}
.stExpander {
    background-color: var(--surface-2) !important;
    border: 1px solid var(--surface-3) !important;
    border-radius: 6px !important;
}
.stAlert {
    background-color: var(--surface-2) !important;
    border: 1px solid var(--surface-3) !important;
    border-radius: 6px !important;
}
</style>
"""
st.markdown(CSS_TEMA, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Constantes de configuracion
# ---------------------------------------------------------------------------
TEMPERATURA_FINAL = 1.35
TEMPERATURA_INTERMEDIA = 0.85
FREQUENCY_PENALTY = 0.50
PRESENCE_PENALTY = 0.50
TOP_P = 0.85
RITMO_MINIMO = 0.55
MAX_CARACTERES = 3000
MAX_TOKENS = 2048
TIMEOUT = 60
TAMANO_BLOQUE = 420
MAX_RONDAS_CORRECCION = 3
MAX_RONDAS_DETECTORES = 3

PAUSA_CUOTA = 120
PAUSA_LENTO = 180
PAUSA_DIARIA = 1800

LOGO_URL = "https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png"

CADENA_FINAL = ["groq", "openrouter", "nvidia", "deepseek", "gemini"]


# ---------------------------------------------------------------------------
# Proveedores y modelos
# ---------------------------------------------------------------------------
PROVEEDORES = {
    "groq": {
        "nombre": "Groq",
        "clave": "GROQ_API_KEY",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "models_endpoint": "https://api.groq.com/openai/v1/models",
        "tipo": "openai_compatible",
    },
    "openrouter": {
        "nombre": "OpenRouter",
        "clave": "OPENROUTER_API_KEY",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "models_endpoint": "https://openrouter.ai/api/v1/models",
        "tipo": "openai_compatible",
    },
    "nvidia": {
        "nombre": "NVIDIA",
        "clave": "NVIDIA_API_KEY",
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "models_endpoint": "https://integrate.api.nvidia.com/v1/models",
        "tipo": "openai_compatible",
    },
    "deepseek": {
        "nombre": "DeepSeek",
        "clave": "DEEPSEEK_API_KEY",
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "models_endpoint": "https://api.deepseek.com/v1/models",
        "tipo": "openai_compatible",
    },
    "gemini": {
        "nombre": "Google Gemini",
        "clave": "GEMINI_API_KEY",
        "endpoint": None,
        "models_endpoint": None,
        "tipo": "gemini_sdk",
    },
}

ORDEN_FALLBACK = ["groq", "openrouter", "nvidia", "deepseek", "gemini"]

MODELO_POR_PROVEEDOR = {
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "nvidia": "mistralai/mistral-large-4-1t-a52b",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.0-flash",
}

MODELOS_FIJOS = {
    "groq": ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama-3.1-8b-instant"],
    "openrouter": [
        "meta-llama/llama-3.3-70b-instruct",
        "qwen/qwen-2.5-72b-instruct",
        "mistralai/mistral-large",
    ],
    "nvidia": [
        "mistralai/mistral-large-4-1t-a52b",
        "meta/llama-3.3-70b-instruct",
        "deepseek-ai/deepseek-v3",
    ],
    "deepseek": ["deepseek-chat", "deepseek-flash"],
    "gemini": ["gemini-2.0-flash"],
}

EXCLUIDOS = [
    "whisper", "tts", "stt", "guard", "embed", "vision", "image", "audio",
    "speech", "moderation", "classifier", "safety", "filter", "embedding",
    "rerank", "token", "tokenizer",
]

FAMILIAS_TEXTO = [
    "llama", "mistral", "qwen", "deepseek", "gemma", "phi", "yi", "mixtral",
    "codellama", "wizard", "zephyr", "nous", "openchat", "starling", "solar",
    "command", "jamba", "dbrx", "falcon", "mpt", "replit", "stable", "vicuna",
    "alpaca", "koala", "orca", "dolphin", "hermes", "openhermes", "tiny",
    "gpt", "claude", "gemini",
]


# ---------------------------------------------------------------------------
# Muestra de estilo integrada (Tesis 2003)
# ---------------------------------------------------------------------------
MUESTRA_ESTILO_TESIS = """
Las ciudades han sido tradicionalmente de dos tipos, diseñadas y proyectadas de manera precisa con un orden predeterminado o desarrolladas con un crecimiento espontáneo sin ningún plan preestablecido. De cualquier manera que éstas sean clasificadas, dentro de estas dos categorías, su expansión y crecimiento han llevado a considerar los mecanismos de control necesarios para regular el uso del suelo y las posibles aplicaciones a que su desarrollo pudiese llegar a generar prospectivamente.

De acuerdo con lo anterior, es necesario comprender cómo la ciudad, a través del uso del suelo, caracteriza todavía en la actualidad los mismos tipos de ciudades antes mencionados y que pueden ser definidos como modelos históricos y antagónicos.

Para plantear una hipótesis al problema del suelo urbano, debemos necesariamente considerar tres factores que intervienen y se afectan mutuamente de acuerdo al uso del espacio territorial de la ciudad.
""".strip()


# ---------------------------------------------------------------------------
# Prompts del sistema
# ---------------------------------------------------------------------------
PROMPT_EN = (
    "Translate this Spanish text into plain, everyday English. Keep EXACTLY the "
    "same paragraphs (same number, same order) and the same level of detail: do "
    "not summarize or skip anything. Keep every fact, name, institution, number, "
    "quote and year exactly as written. Output ONLY the English text."
)

PROMPT_ES = (
    "Pasa este texto del inglés al español natural y directo. Cambia el orden de "
    "las ideas dentro de cada oración y los conectores, pero conserva los mismos "
    "párrafos, en el mismo orden y con la misma extensión. No resumas ni omitas "
    "nada. Conserva todos los datos, nombres, instituciones, cifras, citas y "
    "fechas sin inventar nada. Devuelve SOLO el texto en español."
)

PROMPT_RETRO = (
    "Retrotraduce este texto español: primero pásalo a inglés llano conservando "
    "cada dato, cifra, nombre, cita y año; luego regresa al español natural "
    "reordenando las ideas dentro de cada oración y cambiando los conectores. "
    "No resumas ni omitas nada. No uses calcos del inglés. Devuelve SOLO el texto "
    "final en español, con los mismos párrafos que el original."
)

PROMPT_ESTRUCTURA = (
    "Eres un editor humano. Rompe por completo la estructura del texto: "
    "1) Divide párrafos largos en bloques de 2 a 4 oraciones. "
    "2) Ninguna oración puede superar 30 palabras. "
    "3) Al menos el 30% de las oraciones deben tener entre 4 y 9 palabras. "
    "4) Alterna sin patrón: corta, larga, media, muy corta, larga. "
    "5) Nunca dos oraciones seguidas con la misma longitud. "
    "6) Nunca tres oraciones seguidas con la misma arquitectura sintáctica. "
    "7) Mueve complementos, invierte cláusulas, cambia sujetos de lugar. "
    "Conserva el significado y todos los datos. Devuelve SOLO el texto."
)

PROMPT_FINAL_BASE = (
    "Eres un escritor académico con voz propia. Redacta la versión final de un "
    "texto que debe leerse como escrito por una persona real."
)

PROMPT_FINAL_REGLAS = """
BURSTINESS EXTREMA (obligatorio):
1. Alterna oraciones cortas (5-10 palabras) con largas (25-40 palabras).
2. NUNCA dos oraciones seguidas de largo similar (diferencia mínima 8 palabras).
3. NUNCA tres oraciones seguidas de estructura parecida.
4. Máximo 20% de oraciones empezando con El/La/Los/Las/Se.

PROHIBIDO (no aparezca NUNCA):
- "asimismo", "no obstante", "por lo tanto", "sin embargo", "además" (máximo 1 cada uno).
- "en conclusión", "es fundamental", "cabe destacar", "juega un papel", "se ha convertido en", "en el ámbito de", "mediante".
- Moralejas o resúmenes al final: termina con un dato concreto.

PUNTUACIÓN:
- Usa punto y coma (;) al menos 2 veces.
- Usa paréntesis para citas o aclaraciones.
- Usa guion largo (—) para digresiones breves.

DATOS: conserva TODAS las fechas, nombres, cifras y citas TAL CUAL.
TONO: impersonal académico ("es necesario comprender", "debemos considerar").

Devuelve SOLO el texto reescrito, sin explicaciones."""

PROMPT_CORRECCION_BASE = (
    "Eres un corrector de estilo académico. Corrige SOLO los problemas listados. "
    "No resumas, no omitas, no cambies la extensión. Conserva todos los datos. "
    "Devuelve SOLO el texto corregido."
)

PROMPT_DETECTOR_BASE = (
    "Eres un editor que reescribe oraciones sospechosas de IA con cambio "
    "sintáctico total: activa a pasiva o viceversa, invierte el orden de las "
    "cláusulas, rompe el ritmo y cambia el sujeto de lugar. Conserva el "
    "significado y los datos exactos. No resumas. Devuelve SOLO el texto "
    "completo con las oraciones reescritas."
)


# ---------------------------------------------------------------------------
# Funciones para construir prompts con muestra e instrucciones de medida
# ---------------------------------------------------------------------------
def con_muestra(prompt_base: str, reglas: str, muestra: str, instruccion_medida: str) -> str:
    """Integra muestra de estilo e instrucciones de medida en el prompt."""
    return f"""{prompt_base}

MUESTRA DE ESTILO DE REFERENCIA (imita su registro, ritmo y tono):
---
{muestra}
---

{instruccion_medida}

{reglas}"""


def instrucciones_de_medida(num_parrafos: int, num_palabras: int, datos_clave: list) -> str:
    """Genera instrucciones de medida para el prompt."""
    datos_str = ", ".join(datos_clave) if datos_clave else "ninguno específico"
    return (
        f"MEDIDA DEL ORIGINAL: {num_parrafos} párrafos y {num_palabras} palabras. "
        f"El resultado debe tener entre {num_parrafos - 1} y {num_parrafos + 1} párrafos "
        f"y una extensión entre {int(num_palabras * 0.95)} y {int(num_palabras * 1.15)} palabras. "
        f"DATOS OBLIGATORIOS: [{datos_str}]. No pierdas ninguno."
    )


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def leer_secreto(nombre: str) -> str:
    """Lee una clave desde st.secrets. Devuelve string vacío si no existe."""
    valor = st.secrets.get(nombre, "")
    if valor is None:
        return ""
    return str(valor).strip()


def clean_text(texto: str) -> str:
    """Limpia caracteres invisibles, normaliza comillas, dashes y markdown residual."""
    if not texto:
        return ""

    caracteres_invisibles = [
        "\u200b", "\u200c", "\u200d", "\ufeff", "\u00ad",
        "\u2060", "\u2061", "\u2062", "\u2063", "\u2064",
        "\u2028", "\u2029",
    ]
    for c in caracteres_invisibles:
        texto = texto.replace(c, "")

    texto = texto.replace("\u2018", "'").replace("\u2019", "'")
    texto = texto.replace("\u201c", '"').replace("\u201d", '"')
    texto = texto.replace("\u2013", ", ").replace("\u2014", ", ")
    texto = texto.replace("\u2015", ", ")
    texto = texto.replace("\u2026", "...")

    texto = texto.replace("\u00a0", " ")
    texto = texto.replace("\u2009", " ")
    texto = texto.replace("\u202f", " ")
    texto = texto.replace("\u205f", " ")
    texto = texto.replace("\u3000", " ")

    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.+?)\*", r"\1", texto)
    texto = re.sub(r"__(.+?)__", r"\1", texto)
    texto = re.sub(r"_(.+?)_", r"\1", texto)
    texto = re.sub(r"^#{1,6}\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^[-*+]\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\d+\.\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", texto)

    texto = re.sub(r"\by\s+([ií])\b", r"e \1", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bo\s+([oó])\b", r"u \1", texto, flags=re.IGNORECASE)

    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"\s+([,;:!?])", r"\1", texto)
    texto = re.sub(r"([,;:!?])(?!\s)", r"\1 ", texto)
    texto = texto.strip()

    return texto


def detectar_modelos() -> dict:
    """Detecta modelos disponibles haciendo GET a /models de cada proveedor."""
    disponibles = {}
    for prov in ORDEN_FALLBACK:
        cfg = PROVEEDORES[prov]
        api_key = leer_secreto(cfg["clave"])
        if not api_key:
            continue

        if cfg["tipo"] == "gemini_sdk":
            disponibles[prov] = MODELOS_FIJOS[prov]
            continue

        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            if prov == "openrouter":
                headers["HTTP-Referer"] = "https://streamlit.io"
            response = requests.get(cfg["models_endpoint"], headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            modelos_raw = data.get("data", [])
            modelos_filtrados = []
            for m in modelos_raw:
                mid = m.get("id", "")
                if any(exc in mid.lower() for exc in EXCLUIDOS):
                    continue
                if any(fam in mid.lower() for fam in FAMILIAS_TEXTO):
                    modelos_filtrados.append(mid)

            if modelos_filtrados:
                disponibles[prov] = modelos_filtrados[:10]
            else:
                disponibles[prov] = MODELOS_FIJOS[prov]
        except Exception:
            disponibles[prov] = MODELOS_FIJOS[prov]

    return disponibles


# ---------------------------------------------------------------------------
# Sistema de pausados
# ---------------------------------------------------------------------------
PAUSAS = {
    "groq": {"cuota": 0, "lento": 0, "diaria": 0},
    "openrouter": {"cuota": 0, "lento": 0, "diaria": 0},
    "nvidia": {"cuota": 0, "lento": 0, "diaria": 0},
    "deepseek": {"cuota": 0, "lento": 0, "diaria": 0},
    "gemini": {"cuota": 0, "lento": 0, "diaria": 0},
}


def registrar_pausa(proveedor: str, tipo: str):
    """Registra una pausa para un proveedor."""
    if proveedor in PAUSAS and tipo in PAUSAS[proveedor]:
        PAUSAS[proveedor][tipo] = time.time()


def esta_pausado(proveedor: str) -> bool:
    """Verifica si un proveedor está pausado."""
    if proveedor not in PAUSAS:
        return False
    ahora = time.time()
    pausas = PAUSAS[proveedor]
    if pausas["cuota"] and (ahora - pausas["cuota"]) < PAUSA_CUOTA:
        return True
    if pausas["lento"] and (ahora - pausas["lento"]) < PAUSA_LENTO:
        return True
    if pausas["diaria"] and (ahora - pausas["diaria"]) < PAUSA_DIARIA:
        return True
    return False


def manejar_error_api(proveedor: str, error: str):
    """Maneja errores de API y registra pausas según el tipo."""
    error_lower = error.lower()
    if "429" in error_lower or "rate limit" in error_lower or "quota" in error_lower:
        registrar_pausa(proveedor, "cuota")
    elif "timeout" in error_lower or "slow" in error_lower:
        registrar_pausa(proveedor, "lento")
    elif "daily" in error_lower or "day" in error_lower:
        registrar_pausa(proveedor, "diaria")


# ---------------------------------------------------------------------------
# Llamadas a APIs
# ---------------------------------------------------------------------------
def llamar_openai_compatible(proveedor: str, modelo: str, system_prompt: str,
                             user_prompt: str, temperature: float) -> str:
    """Llama a una API compatible con el formato de OpenAI."""
    cfg = PROVEEDORES[proveedor]
    api_key = leer_secreto(cfg["clave"])
    if not api_key:
        raise ValueError(f"{cfg['clave']} no configurada")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if proveedor == "openrouter":
        headers["HTTP-Referer"] = "https://streamlit.io"
        headers["X-Title"] = "Humanizador Pro"

    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "top_p": TOP_P,
        "frequency_penalty": FREQUENCY_PENALTY,
        "presence_penalty": PRESENCE_PENALTY,
        "max_tokens": MAX_TOKENS,
    }

    response = requests.post(cfg["endpoint"], headers=headers, json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def llamar_gemini(modelo: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
    """Llama a Google Gemini usando el SDK oficial."""
    api_key = leer_secreto(PROVEEDORES["gemini"]["clave"])
    if not api_key:
        raise ValueError("GEMINI_API_KEY no configurada")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=modelo,
        contents=user_prompt,
        config={
            "temperature": temperature,
            "top_p": TOP_P,
            "system_instruction": system_prompt,
        },
    )
    return response.text.strip()


def llamar_proveedor(proveedor: str, modelo: str, system_prompt: str,
                     user_prompt: str, temperature: float) -> dict:
    """Llama a un proveedor con fallback automático al siguiente disponible."""
    orden = [proveedor] + [p for p in ORDEN_FALLBACK if p != proveedor]
    ultimo_error = None

    for prov in orden:
        if esta_pausado(prov):
            continue

        cfg = PROVEEDORES[prov]
        if not leer_secreto(cfg["clave"]):
            continue

        modelo_actual = MODELO_POR_PROVEEDOR[prov] if prov != proveedor else modelo

        try:
            if cfg["tipo"] == "openai_compatible":
                resultado = llamar_openai_compatible(
                    prov, modelo_actual, system_prompt, user_prompt, temperature
                )
            elif cfg["tipo"] == "gemini_sdk":
                resultado = llamar_gemini(
                    modelo_actual, system_prompt, user_prompt, temperature
                )
            else:
                continue

            if not resultado:
                raise ValueError("Respuesta vacía")

            return {
                "texto": resultado,
                "proveedor_usado": cfg["nombre"],
                "modelo_usado": modelo_actual,
                "exito": True,
                "error": None,
            }
        except Exception as e:
            error_msg = f"{cfg['nombre']}: {str(e)}"
            ultimo_error = error_msg
            manejar_error_api(prov, str(e))
            continue

    return {
        "texto": "",
        "proveedor_usado": None,
        "modelo_usado": None,
        "exito": False,
        "error": ultimo_error or "Ningún proveedor disponible",
    }


# ---------------------------------------------------------------------------
# Pasos del pipeline
# ---------------------------------------------------------------------------
def procesar_bloque(texto: str, paso: str, proveedor: str, modelo: str,
                    instruccion_medida: str = "") -> dict:
    """Procesa un bloque del pipeline según el paso indicado."""
    prompts = {
        "es_en": (PROMPT_EN, TEMPERATURA_INTERMEDIA),
        "en_es": (PROMPT_ES, TEMPERATURA_INTERMEDIA),
        "retro": (PROMPT_RETRO, TEMPERATURA_INTERMEDIA),
        "estructura": (PROMPT_ESTRUCTURA, TEMPERATURA_INTERMEDIA),
        "final": (PROMPT_FINAL_BASE, TEMPERATURA_FINAL),
    }

    if paso not in prompts:
        return {"texto": texto, "proveedor_usado": None, "modelo_usado": None,
                "exito": False, "error": f"Paso desconocido: {paso}"}

    system_base, temperature = prompts[paso]

    if paso == "final":
        system_prompt = con_muestra(system_base, PROMPT_FINAL_REGLAS, MUESTRA_ESTILO_TESIS, instruccion_medida)
    else:
        system_prompt = system_base

    return llamar_proveedor(proveedor, modelo, system_prompt, texto, temperature)


def revisar_bloque(texto: str, proveedor: str, modelo: str, problemas: list,
                   longitud_original: int, datos_clave: list) -> dict:
    """Revisa y corrige un bloque hasta 3 rondas."""
    if not problemas:
        return {"texto": texto, "proveedor_usado": proveedor, "modelo_usado": modelo,
                "exito": True, "error": None}

    texto_actual = texto
    for ronda in range(1, MAX_RONDAS_CORRECCION + 1):
        lista = "\n".join(f"- {p}" for p in problemas)
        prompt_usuario = (
            f"Texto a corregir:\n---\n{texto_actual}\n---\n\nProblemas detectados:\n{lista}\n\n"
            f"Longitud original: {longitud_original} palabras. Mantén entre "
            f"{int(longitud_original * 0.95)} y {int(longitud_original * 1.15)} palabras.\n"
            f"Datos obligatorios: {', '.join(datos_clave)}. No pierdas ninguno.\n\n"
            f"Corrige SOLO estos problemas sin resumir ni cambiar la extensión."
        )

        res = llamar_proveedor(proveedor, modelo, PROMPT_CORRECCION_BASE, prompt_usuario,
                               TEMPERATURA_INTERMEDIA)
        if not res["exito"]:
            return {"texto": texto_actual, "proveedor_usado": res["proveedor_usado"],
                    "modelo_usado": res["modelo_usado"], "exito": False, "error": res["error"]}

        texto_actual = clean_text(res["texto"])
        nuevos_problemas = auditar_texto(texto_actual)

        if not nuevos_problemas:
            break

        problemas = nuevos_problemas

    return {"texto": texto_actual, "proveedor_usado": proveedor, "modelo_usado": modelo,
            "exito": True, "error": None}


def extraer_datos_clave(texto: str) -> list:
    """Extrae fechas, cifras y nombres propios del texto."""
    datos = []

    fechas = re.findall(r"\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b", texto, re.IGNORECASE)
    datos.extend(fechas)

    años = re.findall(r"\b\d{4}\b", texto)
    datos.extend(años)

    cifras = re.findall(r"\b\d+[.,]?\d*\s*(?:mil|millones|billones|%)?\b", texto, re.IGNORECASE)
    datos.extend(cifras)

    nombres = re.findall(r"\b[A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)+\b", texto)
    datos.extend(nombres[:10])

    return list(set(datos))


def ajustar_con_detectores(texto: str, proveedor: str, modelo: str) -> dict:
    """Ajusta el texto si hay detectores externos configurados."""
    gptzero_key = leer_secreto("GPTZERO_API_KEY")
    copyleaks_key = leer_secreto("COPYLEAKS_API_KEY")

    if not gptzero_key and not copyleaks_key:
        return {"texto": texto, "proveedor_usado": proveedor, "modelo_usado": modelo,
                "exito": True, "error": None}

    texto_actual = texto
    for ronda in range(1, MAX_RONDAS_DETECTORES + 1):
        score_ia = 0.0

        if gptzero_key:
            try:
                headers = {"X-API-KEY": gptzero_key, "Content-Type": "application/json"}
                payload = {"document": texto_actual}
                response = requests.post(
                    "https://api.gptzero.me/v2/predict/text",
                    headers=headers, json=payload, timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    score_ia = data.get("documents", [{}])[0].get("average_generated_prob", 0.0)
            except Exception:
                pass

        if score_ia > 0.30:
            res = reescribir_con_detector(texto_actual, proveedor, modelo)
            if res["exito"]:
                texto_actual = clean_text(res["texto"])
            else:
                break
        else:
            break

    return {"texto": texto_actual, "proveedor_usado": proveedor, "modelo_usado": modelo,
            "exito": True, "error": None}


def extraer_oraciones_problema(texto: str) -> list:
    """Devuelve las oraciones que violan reglas de detección."""
    oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+", texto) if o.strip()]
    problemas = []
    frases_vetadas = [
        "en conclusión", "es fundamental", "cabe destacar", "juega un papel",
        "se ha convertido en", "en el ámbito de", "mediante", "sin embargo",
    ]
    for o in oraciones:
        n = len(o.split())
        primera = o.split()[0] if o.split() else ""
        baja = o.lower()
        if n > 30 or n < 5 or primera in ["El", "La", "Los", "Las", "Se"] or any(
            f in baja for f in frases_vetadas
        ):
            problemas.append(o)
    return problemas


def reescribir_con_detector(texto: str, proveedor: str, modelo: str) -> dict:
    """Reescribe oraciones problemáticas con cambio sintáctico total."""
    malas = extraer_oraciones_problema(texto)
    if not malas:
        return {"texto": texto, "proveedor_usado": proveedor, "modelo_usado": modelo,
                "exito": True, "error": None}
    lista = "\n".join(f"- {o}" for o in malas)
    prompt_usuario = (
        f"Texto completo:\n---\n{texto}\n---\n\nReescribe con cambio sintáctico "
        f"total SOLO estas oraciones problemáticas (conserva el resto intacto):\n"
        f"{lista}"
    )
    return llamar_proveedor(proveedor, modelo, PROMPT_DETECTOR_BASE, prompt_usuario,
                            TEMPERATURA_FINAL)


# ---------------------------------------------------------------------------
# Auditoría automática (12+ detectores)
# ---------------------------------------------------------------------------
FRASES_VETADAS_IA = [
    "en conclusión", "es fundamental", "cabe destacar", "juega un papel",
    "se ha convertido en", "en el ámbito de", "mediante", "asimismo",
    "no obstante", "por lo tanto", "sin embargo", "además", "en definitiva",
    "vale la pena mencionar", "es importante señalar", "cabe mencionar",
    "en el mundo actual", "en la actualidad", "en este sentido",
    "resulta fundamental", "desempeña un papel crucial", "en resumen",
    "por otro lado", "cabe señalar", "es crucial", "es esencial",
    "no puede ignorarse", "merece la pena", "vale destacar",
    "en pocas palabras", "en síntesis", "en suma", "en conjunto",
    "a modo de conclusión", "para finalizar", "como conclusión",
    "en última instancia", "en términos generales", "en general",
    "en efecto", "de hecho", "por cierto", "por supuesto",
    "sin duda", "indudablemente", "evidentemente", "claramente",
    "obviamente", "naturalmente", "lógicamente",
]

CONECTORES_MANUAL = [
    "asimismo", "no obstante", "por lo tanto", "sin embargo", "además",
    "en consecuencia", "por consiguiente", "en efecto", "de hecho",
    "por otro lado", "en este sentido", "en definitiva",
]


def auditar_texto(texto: str) -> list:
    """Audita el texto y devuelve una lista de problemas detectados."""
    problemas = []
    oraciones = [o.strip() for o in re.split(r"[.!?]+", texto) if o.strip()]
    if len(oraciones) < 2:
        return problemas

    longitudes = [len(o.split()) for o in oraciones]
    media = sum(longitudes) / len(longitudes)
    varianza = sum((l - media) ** 2 for l in longitudes) / len(longitudes)
    cv = (varianza ** 0.5) / media if media > 0 else 0

    if cv < RITMO_MINIMO:
        problemas.append(f"Ritmo parejo (CV={cv:.2f} < {RITMO_MINIMO})")

    for i in range(len(longitudes) - 2):
        if (abs(longitudes[i] - longitudes[i + 1]) < 3
                and abs(longitudes[i + 1] - longitudes[i + 2]) < 3):
            problemas.append("Tres oraciones seguidas de largo similar")
            break

    if any(l > 38 for l in longitudes):
        problemas.append("Oraciones demasiado largas (>38 palabras)")

    if not any(l < 9 for l in longitudes):
        problemas.append("Ninguna oración corta (<9 palabras)")

    texto_lower = texto.lower()
    if any(frase in texto_lower for frase in FRASES_VETADAS_IA):
        problemas.append("Frases vetadas de IA detectadas")

    if re.search(r"\b\w+,\s+\w+\s+y\s+\w+\b", texto):
        problemas.append("Enumeraciones de tres elementos")

    if re.search(r",\s+\w+ando\b", texto):
        problemas.append("Gerundios de remate tras coma")

    inicios = [o.split()[0] for o in oraciones if o.split()]
    art = [i for i in inicios if i in ["El", "La", "Los", "Las", "Se"]]
    if len(inicios) > 0 and (len(art) / len(inicios)) > 0.30:
        problemas.append("Inicios repetitivos (El/La/Los/Las/Se > 30%)")

    parrafos = texto.split("\n\n")
    for p in parrafos:
        op = [o.strip() for o in re.split(r"[.!?]+", p) if o.strip()]
        if len(op) >= 3:
            lp = [len(o.split()) for o in op]
            if max(lp) - min(lp) < 5:
                problemas.append("Párrafos planos (oraciones de largo parecido)")
                break

    total_conectores = 0
    for c in CONECTORES_MANUAL:
        total_conectores += texto_lower.count(c)
    if total_conectores > len(oraciones) * 0.12:
        problemas.append(f"Conectores de manual en exceso ({total_conectores})")

    puntuacion = texto.count(";") + texto.count("—") + texto.count("(")
    if puntuacion < 3:
        problemas.append("Falta de puntuación variada (;, —, ())")

    if re.search(r"(en definitiva|en resumen|finalmente|como conclusión)\s*[,\.]",
                 texto_lower):
        problemas.append("Moralejas o resúmenes al final")

    palabras_inicio = [o.split()[0].lower() for o in oraciones if o.split()]
    from collections import Counter
    conteo_inicio = Counter(palabras_inicio)
    for palabra, count in conteo_inicio.items():
        if count > 3 and len(palabra) > 2:
            problemas.append(f"Repetición de '{palabra}' al inicio ({count} veces)")
            break

    return problemas


def calcular_ritmo(texto: str) -> float:
    """Calcula el coeficiente de variación (CV) de las longitudes de oraciones."""
    oraciones = [o.strip() for o in re.split(r"[.!?]+", texto) if o.strip()]
    if len(oraciones) < 2:
        return 0.0
    longitudes = [len(o.split()) for o in oraciones]
    media = sum(longitudes) / len(longitudes)
    if media == 0:
        return 0.0
    varianza = sum((l - media) ** 2 for l in longitudes) / len(longitudes)
    return (varianza ** 0.5) / media


def generar_svg_ritmo(longitudes_orig: list, longitudes_fin: list) -> str:
    """Genera un gráfico SVG de barras comparando ritmo original vs humanizado."""
    if not longitudes_orig and not longitudes_fin:
        return "<p>No hay suficientes oraciones para graficar.</p>"

    max_len = max(
        max(longitudes_orig) if longitudes_orig else 0,
        max(longitudes_fin) if longitudes_fin else 0,
        40,
    )
    n = max(len(longitudes_orig), len(longitudes_fin))
    ancho_barra = max(2, min(12, 700 // n))
    alto_max = 120
    gap = 2

    barras = ""
    for i in range(n):
        x = i * (ancho_barra * 2 + gap * 3)

        if i < len(longitudes_orig):
            l = longitudes_orig[i]
            h = max(int((l / max_len) * alto_max), 2)
            barras += (
                f'<rect x="{x}" y="{alto_max - h}" width="{ancho_barra}" height="{h}" '
                f'fill="#A6ACB6" opacity="0.55" rx="1" />'
            )

        if i < len(longitudes_fin):
            l = longitudes_fin[i]
            h = max(int((l / max_len) * alto_max), 2)
            barras += (
                f'<rect x="{x + ancho_barra + gap}" y="{alto_max - h}" '
                f'width="{ancho_barra}" height="{h}" fill="#22D3E6" rx="1" />'
            )

    ancho_total = n * (ancho_barra * 2 + gap * 3) + 10
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'height="{alto_max + 40}" viewBox="0 0 {ancho_total} {alto_max + 40}">'
        f'<text x="0" y="15" font-size="11" fill="#A6ACB6" font-family="sans-serif">'
        f'Gris: original | Cyan: humanizado</text>'
        f'<g transform="translate(5, 25)">{barras}</g>'
        f'<line x1="0" y1="{alto_max + 25}" x2="{ancho_total}" y2="{alto_max + 25}" '
        f'stroke="#2A2F38" stroke-width="1" />'
        f'</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# Pipeline completo
# ---------------------------------------------------------------------------
def armar_plan(proveedores_otros: list, modo_profundo: bool, romper_estructura: bool,
               correccion_auto: bool) -> list:
    """Arma el plan de pasos con diversidad de proveedores."""
    plan = []
    idx = 0

    if modo_profundo:
        plan.append({"paso": "retro", "proveedor": proveedores_otros[idx % len(proveedores_otros)]})
        idx += 1

    if romper_estructura:
        plan.append({"paso": "estructura", "proveedor": proveedores_otros[idx % len(proveedores_otros)]})
        idx += 1

    plan.append({"paso": "final", "proveedor": "groq"})

    if correccion_auto:
        plan.append({"paso": "correccion", "proveedor": proveedores_otros[idx % len(proveedores_otros)]})
        idx += 1
        plan.append({"paso": "detector", "proveedor": proveedores_otros[idx % len(proveedores_otros)]})

    return plan


def dividir_en_bloques(texto: str, tamano: int = TAMANO_BLOQUE) -> list:
    """Divide el texto en bloques de aproximadamente tamano palabras."""
    palabras = texto.split()
    bloques = []
    for i in range(0, len(palabras), tamano):
        bloque = " ".join(palabras[i:i + tamano])
        bloques.append(bloque)
    return bloques


def procesar_bloque_individual(bloque: str, plan: list, modelo_final: str,
                               instruccion_medida: str, datos_clave: list) -> dict:
    """Procesa un bloque individual siguiendo el plan."""
    texto_actual = bloque
    log = []

    for etapa in plan:
        paso = etapa["paso"]
        proveedor = etapa["proveedor"]
        modelo = MODELO_POR_PROVEEDOR.get(proveedor, MODELO_POR_PROVEEDOR["groq"])

        if paso == "retro":
            res = procesar_bloque(texto_actual, "retro", proveedor, modelo, instruccion_medida)
        elif paso == "estructura":
            res = procesar_bloque(texto_actual, "estructura", proveedor, modelo, instruccion_medida)
        elif paso == "final":
            res = procesar_bloque(texto_actual, "final", proveedor, modelo_final, instruccion_medida)
        elif paso == "correccion":
            problemas = auditar_texto(texto_actual)
            res = revisar_bloque(texto_actual, proveedor, modelo, problemas,
                                 len(texto_actual.split()), datos_clave)
        elif paso == "detector":
            res = reescribir_con_detector(texto_actual, proveedor, modelo)
        else:
            continue

        if not res["exito"]:
            return {"texto": texto_actual, "log": log, "exito": False, "error": res["error"]}

        texto_actual = clean_text(res["texto"])
        log.append(f"✓ {paso}: {res['proveedor_usado']}")

    return {"texto": texto_actual, "log": log, "exito": True, "error": None}


def procesar(texto: str, config: dict, estado: dict) -> dict:
    """Ejecuta el pipeline completo de humanización."""
    log_pasos = []
    inicio_total = time.time()

    proveedores_otros = config.get("proveedores_otros") or ["groq", "openrouter", "nvidia", "deepseek", "gemini"]
    if not proveedores_otros:
        proveedores_otros = ["groq", "openrouter", "nvidia", "deepseek", "gemini"]

    datos_clave = extraer_datos_clave(texto)
    num_parrafos = len([p for p in texto.split("\n\n") if p.strip()])
    num_palabras = len(texto.split())
    instruccion_medida = instrucciones_de_medida(num_parrafos, num_palabras, datos_clave)

    plan = armar_plan(
        proveedores_otros,
        config.get("modo_profundo", True),
        config.get("romper_estructura", True),
        config.get("correccion_auto", True),
    )

    bloques = dividir_en_bloques(texto, TAMANO_BLOQUE)
    texto_actual = ""

    if len(bloques) > 1:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            for i, bloque in enumerate(bloques):
                future = executor.submit(
                    procesar_bloque_individual,
                    bloque, plan, config.get("modelo_final", MODELO_POR_PROVEEDOR["groq"]),
                    instruccion_medida, datos_clave,
                )
                futures[future] = i

            resultados = [None] * len(bloques)
            for future in as_completed(futures):
                idx = futures[future]
                resultados[idx] = future.result()
                estado["progreso"] = (idx + 1) / len(bloques)

            for res in resultados:
                if not res["exito"]:
                    return {"exito": False, "texto": "", "log": log_pasos,
                            "duracion": time.time() - inicio_total, "problemas": [],
                            "ritmo_original": calcular_ritmo(texto), "ritmo_final": 0.0,
                            "error": res["error"]}
                texto_actual += res["texto"] + "\n\n"
                log_pasos.extend(res["log"])
    else:
        texto_actual = texto
        for etapa in plan:
            paso = etapa["paso"]
            proveedor = etapa["proveedor"]
            modelo = MODELO_POR_PROVEEDOR.get(proveedor, MODELO_POR_PROVEEDOR["groq"])

            if paso == "retro":
                res = procesar_bloque(texto_actual, "retro", proveedor, modelo, instruccion_medida)
            elif paso == "estructura":
                res = procesar_bloque(texto_actual, "estructura", proveedor, modelo, instruccion_medida)
            elif paso == "final":
                res = procesar_bloque(texto_actual, "final", proveedor,
                                      config.get("modelo_final", MODELO_POR_PROVEEDOR["groq"]),
                                      instruccion_medida)
            elif paso == "correccion":
                problemas = auditar_texto(texto_actual)
                res = revisar_bloque(texto_actual, proveedor, modelo, problemas,
                                     num_palabras, datos_clave)
            elif paso == "detector":
                res = reescribir_con_detector(texto_actual, proveedor, modelo)
            else:
                continue

            if not res["exito"]:
                return {"exito": False, "texto": "", "log": log_pasos,
                        "duracion": time.time() - inicio_total, "problemas": [],
                        "ritmo_original": calcular_ritmo(texto), "ritmo_final": 0.0,
                        "error": res["error"]}

            texto_actual = clean_text(res["texto"])
            log_pasos.append(f"✓ {paso}: {res['proveedor_usado']}")
            estado["progreso"] = (log_pasos.index(f"✓ {paso}: {res['proveedor_usado']}") + 1) / len(plan)

    texto_actual = clean_text(texto_actual)

    if config.get("correccion_auto", True):
        res = ajustar_con_detectores(texto_actual, "groq", MODELO_POR_PROVEEDOR["groq"])
        if res["exito"]:
            texto_actual = clean_text(res["texto"])
            log_pasos.append("✓ Ajuste con detectores externos")

    duracion = time.time() - inicio_total
    return {
        "exito": True,
        "texto": texto_actual,
        "log": log_pasos,
        "duracion": duracion,
        "problemas": auditar_texto(texto_actual),
        "ritmo_original": calcular_ritmo(texto),
        "ritmo_final": calcular_ritmo(texto_actual),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def mostrar_logo(ancho=140):
    """Muestra el logo de la aplicación."""
    try:
        st.image(LOGO_URL, width=ancho)
    except Exception:
        st.markdown('<div style="font-size:48px;text-align:center;">✍️</div>',
                    unsafe_allow_html=True)


def login_screen():
    """Pantalla de login con diseño completo."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div style="text-align:center; padding: 40px 0;">', unsafe_allow_html=True)
        mostrar_logo(180)
        st.markdown(
            '<h1 style="font-family: \'Instrument Sans\', sans-serif; font-size: 2.5rem; '
            'margin: 20px 0 10px 0;">Humanizador Pro</h1>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="color: #A6ACB6; font-size: 1.1rem; margin-bottom: 30px;">'
            'Convierte un texto generado por IA en prosa natural, con ritmo y voz de persona.</p>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

        pwd = st.text_input("Contraseña", type="password", key="login_pwd")
        if st.button("Ingresar", type="primary", use_container_width=True):
            esperada = leer_secreto("APP_PASSWORD") or "manu2026"
            if pwd == esperada:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")

        st.markdown(
            '<div style="text-align: center; margin-top: 60px; color: #A6ACB6; font-size: 0.85rem;">'
            '<p>Elaborado por Manu</p>'
            '<p>®Humanizadormanu, derechos reservados © 2026</p>'
            '</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Interfaz principal
# ---------------------------------------------------------------------------
def main():
    """Pantalla principal de la aplicación."""
    if not st.session_state.get("logged_in", False):
        login_screen()
        return

    with st.sidebar:
        mostrar_logo(100)
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

        st.header("⚙️ Configuración")

        modelo_final = st.selectbox(
            "Modelo para la redacción final", options=MODELOS_FIJOS["groq"], index=0
        )

        disponibles = detectar_modelos()
        modelos_otros = st.multiselect(
            "Modelos para los demás pasos",
            options=[m for lista in disponibles.values() for m in lista],
            default=MODELOS_FIJOS["groq"][:2],
        )

        with st.expander("Modelos conectados", expanded=False):
            for prov in ORDEN_FALLBACK:
                cfg = PROVEEDORES[prov]
                if leer_secreto(cfg["clave"]):
                    st.success(f"✓ {cfg['nombre']}: {MODELO_POR_PROVEEDOR[prov]}")
                else:
                    st.error(f"✗ {cfg['nombre']}: Sin clave")

        st.divider()
        modo_profundo = st.toggle("🔥 Modo Profundo", value=True)
        pasadas = st.slider("Pasadas de humanización", min_value=1, max_value=3, value=2)
        modelo_distinto = st.toggle("Un modelo distinto en cada paso", value=True)
        romper_estructura = st.toggle("Romper estructura de párrafos", value=True)
        correccion_auto = st.toggle("Revisión y corrección automática", value=True)

        st.divider()
        with st.expander("📋 Cómo usar la app"):
            st.markdown(
                "1. Pega tu texto (máx. 3000 caracteres).\n"
                "2. Ajusta la configuración.\n"
                "3. Pulsa **Humanizar texto**.\n"
                "4. Revisa ritmo y auditoría.\n"
                "5. Copia o descarga el resultado."
            )

    st.title("✍️ Humanizador Pro")
    st.caption(
        "Pipeline multi-proveedor con retrotraducción, reestructuración, "
        "auditoría de 12 puntos y reescritura por detector."
    )

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("📝 Texto original")
        texto_entrada = st.text_area(
            "Pega aquí el texto generado por IA",
            height=420,
            max_chars=MAX_CARACTERES,
            key="texto_entrada",
        )
        st.caption(f"{len(texto_entrada)} / {MAX_CARACTERES} caracteres")

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            procesar_btn = st.button(
                "🚀 Humanizar texto", type="primary", use_container_width=True,
                disabled=not texto_entrada.strip(),
            )
        with col_b2:
            if st.button("🗑️ Limpiar", use_container_width=True):
                st.session_state.texto_entrada = ""
                st.session_state.pop("resultado", None)
                st.rerun()

    with col_der:
        st.subheader("✨ Texto humanizado")
        if st.session_state.get("resultado"):
            res = st.session_state.resultado
            texto_escapado = (
                res["texto"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            st.markdown(
                f'<div style="background-color:#F2F1EC;padding:1.75rem 2rem;border-radius:4px;'
                f'font-family:\'Newsreader\',Georgia,serif;font-size:1.125rem;line-height:1.65;'
                f'height:400px;overflow-y:auto;color:#1A1B1E;white-space:pre-wrap;'
                f'box-shadow:0 2px 8px rgba(0,0,0,0.15);">{texto_escapado}</div>',
                unsafe_allow_html=True,
            )

            js_texto = json.dumps(res["texto"])
            html_copiar = (
                '<button id="btnC" style="background-color:#F2552C;color:#fff;'
                'border:none;padding:10px 18px;border-radius:6px;cursor:pointer;'
                'margin-top:10px;width:100%;font-weight:bold;font-family:\'Instrument Sans\',sans-serif;">'
                '📋 Copiar texto humanizado</button>'
                '<script>'
                'document.getElementById("btnC").addEventListener("click", function(){'
                'var t=' + js_texto + ';'
                'function ok(){var b=document.getElementById("btnC");'
                'b.textContent="✅ ¡Copiado!";setTimeout(function(){'
                'b.textContent="📋 Copiar texto humanizado";},1500);}'
                'if(navigator.clipboard && window.isSecureContext){'
                'navigator.clipboard.writeText(t).then(ok).catch(function(){fallback(t);ok();});'
                '}else{fallback(t);ok();}'
                'function fallback(s){var ta=document.createElement("textarea");'
                'ta.value=s;ta.style.position="fixed";ta.style.left="-9999px";'
                'document.body.appendChild(ta);ta.select();'
                'try{document.execCommand("copy");}catch(e){}'
                'document.body.removeChild(ta);}'
                '});'
                '</script>'
            )
            components.html(html_copiar, height=70)

            st.download_button(
                "📥 Descargar resultado", data=res["texto"],
                file_name="texto_humanizado.txt", mime="text/plain",
                use_container_width=True,
            )

    if st.session_state.get("resultado"):
        res = st.session_state.resultado
        st.divider()
        st.subheader("📊 Análisis de Ritmo y Auditoría")

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("### Ritmo del texto original")
            lo = [len(o.split()) for o in re.split(r"[.!?]+", texto_entrada) if o.strip()]
            lf = [len(o.split()) for o in re.split(r"[.!?]+", res["texto"]) if o.strip()]
            st.markdown(generar_svg_ritmo(lo, lf), unsafe_allow_html=True)
            st.metric("Coeficiente de Variación (CV) Original", f"{res['ritmo_original']:.2f}")
        with col_r2:
            st.markdown("### Ritmo del texto humanizado")
            st.markdown("<br>", unsafe_allow_html=True)
            cvf = calcular_ritmo(res["texto"])
            st.metric("Coeficiente de Variación (CV) Humanizado", f"{cvf:.2f}",
                      delta="Mejorado" if cvf >= RITMO_MINIMO else "Bajo")

        st.divider()
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.markdown("### 🔍 Problemas detectados")
            if res.get("problemas"):
                for p in res["problemas"]:
                    st.warning(f"⚠️ {p}")
                st.info("💡 Ejecuta otra pasada con Modo Profundo para reducirlos.")
            else:
                st.success("✅ Sin problemas graves en la auditoría.")
        with col_a2:
            st.markdown("### ⏱️ Información del proceso")
            st.metric("Tiempo total", f"{res['duracion']:.1f} segundos")
            st.metric("Pasos ejecutados", len(res.get("log", [])))
            with st.expander("Ver log de proveedores usados"):
                for linea in res.get("log", []):
                    st.write(linea)

    if procesar_btn:
        config = {
            "modo_profundo": modo_profundo,
            "pasadas": pasadas,
            "modelo_distinto": modelo_distinto,
            "romper_estructura": romper_estructura,
            "correccion_auto": correccion_auto,
            "modelo_final": modelo_final,
            "proveedores_otros": modelos_otros,
        }

        estado = {"paso": "Iniciando...", "progreso": 0.0, "res": None, "fin": False}

        def worker():
            estado["res"] = procesar(texto_entrada.strip(), config, estado)
            estado["fin"] = True

        hilo = threading.Thread(target=worker, daemon=True)
        hilo.start()

        cronometro_html = """
        <div id="crono" style="background-color:#20242B;padding:15px;border-radius:8px;
        text-align:center;font-family:'Instrument Sans',sans-serif;font-size:1.2rem;
        color:#22D3E6;border:1px solid #2A2F38;">Tiempo transcurrido: 0:00</div>
        <script>
        var inicio = Date.now();
        setInterval(function(){
            var t = Math.floor((Date.now() - inicio) / 1000);
            var m = Math.floor(t / 60);
            var s = t % 60;
            document.getElementById("crono").textContent = 
                "Tiempo transcurrido: " + m + ":" + (s < 10 ? "0" : "") + s;
        }, 250);
        </script>
        """
        components.html(cronometro_html, height=80)

        barra = st.progress(0)
        estatus = st.empty()

        while not estado["fin"]:
            time.sleep(0.4)
            barra.progress(min(estado["progreso"], 0.99))
            estatus.text(estado["paso"])

        hilo.join()
        barra.progress(1.0)
        estatus.text("¡Proceso completado!")
        time.sleep(0.6)
        barra.empty()
        estatus.empty()

        resultado = estado["res"]
        if resultado and resultado["exito"]:
            st.session_state.resultado = resultado
            st.rerun()
        else:
            err = resultado.get("error", "Desconocido") if resultado else "Sin respuesta"
            st.error(f"Error en el pipeline: {err}")
            if resultado and resultado.get("log"):
                with st.expander("Ver log de pasos ejecutados"):
                    for linea in resultado["log"]:
                        st.write(linea)


if __name__ == "__main__":
    main()
