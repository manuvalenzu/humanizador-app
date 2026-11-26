"""
Humanizador Pro - Aplicación Streamlit para humanizar textos generados por IA.

Pipeline multi-proveedor con retrotraducción, reestructuración,
auditoría de detectores, reescritura por detector, procesamiento en
bloques paralelos, sistema de pausados y tema oscuro completo.

Autor: Manu
Derechos reservados: Humanizadormanu, 2026
"""

import re
import json
import time
import math
import threading
import logging
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import streamlit as st
import streamlit.components.v1 as components
from google import genai


# ---------------------------------------------------------------------------
# Configuración de la página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Humanizador Pro",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/manuvalenzu/humanizador-app",
        "Report a bug": "https://github.com/manuvalenzu/humanizador-app/issues",
        "About": "Humanizador Pro - Convierte textos IA en prosa natural.",
    },
)


# ---------------------------------------------------------------------------
# Logging estructurado
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("humanizador")


# ---------------------------------------------------------------------------
# Tema oscuro CSS completo
# ---------------------------------------------------------------------------
CSS_TEMA = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&display=swap');

:root {
    --bg: #0F1114;
    --surface: #171A1F;
    --surface-2: #20242B;
    --surface-3: #2A2F38;
    --ink: #ECEEF1;
    --ink-soft: #A6ACB6;
    --accent: #F2552C;
    --accent-hover: #d94820;
    --human: #22D3E6;
    --paper: #F2F1EC;
    --paper-ink: #1A1B1E;
    --success: #22C55E;
    --warning: #F59E0B;
    --error: #EF4444;
    --border: #2A2F38;
    --shadow: rgba(0, 0, 0, 0.3);
}

html, body, .stApp {
    background-color: var(--bg) !important;
    color: var(--ink) !important;
    font-family: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

.stApp header {
    background-color: var(--surface) !important;
    border-bottom: 1px solid var(--border) !important;
}

.stSidebar {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
    padding-top: 1rem !important;
}

.stSidebar > div {
    background-color: var(--surface) !important;
}

.stSidebarHeader {
    background-color: var(--surface) !important;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--ink) !important;
    font-family: 'Instrument Sans', sans-serif !important;
    font-weight: 600 !important;
}

.stButton > button {
    background-color: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-family: 'Instrument Sans', sans-serif !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 4px var(--shadow) !important;
}

.stButton > button:hover {
    background-color: var(--accent-hover) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px var(--shadow) !important;
}

.stButton > button:disabled {
    background-color: var(--surface-3) !important;
    color: var(--ink-soft) !important;
    cursor: not-allowed !important;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
.stMultiSelect > div > div > div,
.stNumberInput > div > div > input {
    background-color: var(--surface-2) !important;
    color: var(--ink) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    font-family: 'Instrument Sans', sans-serif !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(242, 85, 44, 0.2) !important;
}

.stMetric {
    background-color: var(--surface-2) !important;
    padding: 1rem !important;
    border-radius: 8px !important;
    border: 1px solid var(--border) !important;
    box-shadow: 0 2px 4px var(--shadow) !important;
}

[data-testid="stMetricValue"] {
    color: var(--human) !important;
    font-family: 'Instrument Sans', sans-serif !important;
    font-weight: 700 !important;
}

[data-testid="stMetricLabel"] {
    color: var(--ink-soft) !important;
    font-family: 'Instrument Sans', sans-serif !important;
}

[data-testid="stMetricDelta"] {
    font-weight: 600 !important;
}

.stDivider {
    border-color: var(--border) !important;
    margin: 1rem 0 !important;
}

.stExpander {
    background-color: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

.stExpander > div {
    background-color: var(--surface-2) !important;
    color: var(--ink) !important;
}

.stAlert {
    background-color: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--ink) !important;
}

[data-testid="stAlertContainer"] {
    background-color: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}

.stProgress > div > div > div > div {
    background-color: var(--accent) !important;
}

.stProgress > div > div > div {
    background-color: var(--surface-3) !important;
}

.stToggle {
    background-color: transparent !important;
}

.stToggle label {
    color: var(--ink) !important;
    font-family: 'Instrument Sans', sans-serif !important;
}

.stSlider > div > div > div > div {
    background-color: var(--accent) !important;
}

.stSlider > div > div > div {
    background-color: var(--surface-3) !important;
}

.stCaption {
    color: var(--ink-soft) !important;
    font-family: 'Instrument Sans', sans-serif !important;
}

[data-testid="stDownloadButton"] > button {
    background-color: var(--surface-2) !important;
    color: var(--ink) !important;
    border: 1px solid var(--border) !important;
}

[data-testid="stDownloadButton"] > button:hover {
    background-color: var(--surface-3) !important;
    border-color: var(--accent) !important;
}

hr {
    border-color: var(--border) !important;
}

a {
    color: var(--human) !important;
    text-decoration: none !important;
}

a:hover {
    text-decoration: underline !important;
}

code, pre {
    background-color: var(--surface-2) !important;
    color: var(--human) !important;
    border-radius: 4px !important;
    font-family: 'Courier New', monospace !important;
}

.cronometro-container {
    background-color: var(--surface-2) !important;
    padding: 1rem !important;
    border-radius: 8px !important;
    border: 1px solid var(--border) !important;
    text-align: center !important;
    font-family: 'Instrument Sans', sans-serif !important;
    font-size: 1.25rem !important;
    color: var(--human) !important;
    box-shadow: 0 2px 4px var(--shadow) !important;
}

.hoja-papel {
    background-color: var(--paper) !important;
    padding: 1.75rem 2rem !important;
    border-radius: 4px !important;
    font-family: 'Newsreader', Georgia, serif !important;
    font-size: 1.125rem !important;
    line-height: 1.65 !important;
    color: var(--paper-ink) !important;
    height: 400px !important;
    overflow-y: auto !important;
    white-space: pre-wrap !important;
    box-shadow: 0 4px 12px var(--shadow) !important;
    border: 1px solid #d4d2c8 !important;
}

.btn-copiar {
    background-color: var(--accent) !important;
    color: white !important;
    border: none !important;
    padding: 0.75rem 1.5rem !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    margin-top: 0.75rem !important;
    width: 100% !important;
    font-weight: 600 !important;
    font-family: 'Instrument Sans', sans-serif !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 4px var(--shadow) !important;
}

.btn-copiar:hover {
    background-color: var(--accent-hover) !important;
    transform: translateY(-1px) !important;
}

.btn-copiar.copiado {
    background-color: var(--success) !important;
}

.login-container {
    text-align: center !important;
    padding: 3rem 0 !important;
}

.login-title {
    font-family: 'Instrument Sans', sans-serif !important;
    font-size: 2.5rem !important;
    font-weight: 700 !important;
    color: var(--ink) !important;
    margin: 1.5rem 0 0.75rem 0 !important;
}

.login-subtitle {
    color: var(--ink-soft) !important;
    font-size: 1.1rem !important;
    margin-bottom: 2rem !important;
    font-family: 'Instrument Sans', sans-serif !important;
}

.login-footer {
    text-align: center !important;
    margin-top: 3.5rem !important;
    color: var(--ink-soft) !important;
    font-size: 0.85rem !important;
    font-family: 'Instrument Sans', sans-serif !important;
}

.login-footer p {
    margin: 0.25rem 0 !important;
}

.status-text {
    color: var(--human) !important;
    font-family: 'Instrument Sans', sans-serif !important;
    font-size: 0.95rem !important;
    margin-top: 0.5rem !important;
}

.log-line {
    color: var(--ink-soft) !important;
    font-family: 'Courier New', monospace !important;
    font-size: 0.85rem !important;
    padding: 0.25rem 0 !important;
}
</style>
"""
st.markdown(CSS_TEMA, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Constantes de configuración
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
MAX_RETRIES = 2
BASE_BACKOFF = 1.5
PAUSA_CUOTA = 120
PAUSA_LENTO = 180
PAUSA_DIARIA = 1800

LOGO_URL = "https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png"
LOGO_FONTSIZE = 180
LOGO_SIDEBAR = 100

GEMINI_MODEL_DEFAULT = "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------
PROVEEDORES: Dict[str, Dict[str, Any]] = {
    "groq": {
        "nombre": "Groq",
        "clave": "GROQ_API_KEY",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "models_endpoint": "https://api.groq.com/openai/v1/models",
        "tipo": "openai_compatible",
        "gratis": True,
        "velocidad": "muy_rapido",
    },
    "openrouter": {
        "nombre": "OpenRouter",
        "clave": "OPENROUTER_API_KEY",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "models_endpoint": "https://openrouter.ai/api/v1/models",
        "tipo": "openai_compatible",
        "gratis": False,
        "velocidad": "medio",
    },
    "nvidia": {
        "nombre": "NVIDIA",
        "clave": "NVIDIA_API_KEY",
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "models_endpoint": "https://integrate.api.nvidia.com/v1/models",
        "tipo": "openai_compatible",
        "gratis": True,
        "velocidad": "medio",
    },
    "deepseek": {
        "nombre": "DeepSeek",
        "clave": "DEEPSEEK_API_KEY",
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "models_endpoint": "https://api.deepseek.com/v1/models",
        "tipo": "openai_compatible",
        "gratis": False,
        "velocidad": "medio",
    },
    "gemini": {
        "nombre": "Google Gemini",
        "clave": "GEMINI_API_KEY",
        "endpoint": None,
        "models_endpoint": None,
        "tipo": "gemini_sdk",
        "gratis": True,
        "velocidad": "rapido",
    },
}

ORDEN_FALLBACK = ["groq", "openrouter", "nvidia", "deepseek", "gemini"]

MODELO_POR_PROVEEDOR: Dict[str, str] = {
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "nvidia": "mistralai/mistral-large-4-1t-a52b",
    "deepseek": "deepseek-chat",
    "gemini": GEMINI_MODEL_DEFAULT,
}

MODELOS_FIJOS: Dict[str, List[str]] = {
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
    "gemini": [GEMINI_MODEL_DEFAULT],
}

EXCLUIDOS = [
    "whisper", "tts", "stt", "guard", "embed", "vision", "image", "audio",
    "speech", "moderation", "classifier", "safety", "filter", "embedding",
    "rerank", "token", "tokenizer", "dall", "sora", "imagen", "flux",
    "stable-diffusion", "sd", "clip", "vit", "bert", "roberta",
]

FAMILIAS_TEXTO = [
    "llama", "mistral", "qwen", "deepseek", "gemma", "phi", "yi", "mixtral",
    "codellama", "wizard", "zephyr", "nous", "openchat", "starling", "solar",
    "command", "jamba", "dbrx", "falcon", "mpt", "replit", "stable", "vicuna",
    "alpaca", "koala", "orca", "dolphin", "hermes", "openhermes", "tiny",
    "gpt", "claude", "gemini", "grok",
]


# ---------------------------------------------------------------------------
# Muestra de estilo y prompts
# ---------------------------------------------------------------------------
MUESTRA_ESTILO_TESIS = """
Las ciudades han sido tradicionalmente de dos tipos, diseñadas y proyectadas de manera precisa con un orden predeterminado o desarrolladas con un crecimiento espontáneo sin ningún plan preestablecido. De cualquier manera que éstas sean clasificadas, dentro de estas dos categorías, su expansión y crecimiento han llevado a considerar los mecanismos de control necesarios para regular el uso del suelo y las posibles aplicaciones a que su desarrollo pudiese llegar a generar prospectivamente.

De acuerdo con lo anterior, es necesario comprender cómo la ciudad, a través del uso del suelo, caracteriza todavía en la actualidad los mismos tipos de ciudades antes mencionados y que pueden ser definidos como modelos históricos y antagónicos.

Para plantear una hipótesis al problema del suelo urbano, debemos necesariamente considerar tres factores que intervienen y se afectan mutuamente de acuerdo al uso del espacio territorial de la ciudad.
""".strip()

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


def con_muestra(prompt_base: str, reglas: str, muestra: str, instruccion_medida: str) -> str:
    return f"""{prompt_base}

MUESTRA DE ESTILO DE REFERENCIA (imita su registro, ritmo y tono):
---
{muestra}
---

{instruccion_medida}

{reglas}"""


def instrucciones_de_medida(num_parrafos: int, num_palabras: int, datos_clave: List[str]) -> str:
    datos_str = ", ".join(datos_clave[:15]) if datos_clave else "ninguno específico"
    min_palabras = int(num_palabras * 0.95)
    max_palabras = int(num_palabras * 1.15)
    min_parrafos = max(1, num_parrafos - 1)
    max_parrafos = num_parrafos + 1
    return (
        f"MEDIDA DEL ORIGINAL: {num_parrafos} párrafos y {num_palabras} palabras. "
        f"El resultado debe tener entre {min_parrafos} y {max_parrafos} párrafos "
        f"y una extensión entre {min_palabras} y {max_palabras} palabras. "
        f"DATOS OBLIGATORIOS: [{datos_str}]. No pierdas ninguno."
    )


# ---------------------------------------------------------------------------
# Secretos
# ---------------------------------------------------------------------------
def leer_secreto(nombre: str) -> str:
    try:
        valor = st.secrets.get(nombre, "")
    except Exception:
        return ""
    if valor is None:
        return ""
    return str(valor).strip()


# ---------------------------------------------------------------------------
# Limpieza de texto
# ---------------------------------------------------------------------------
def limpiar_caracteres_invisibles(texto: str) -> str:
    invisibles = [
        "\u200b", "\u200c", "\u200d", "\ufeff", "\u00ad",
        "\u2060", "\u2061", "\u2062", "\u2063", "\u2064",
        "\u2028", "\u2029", "\u200e", "\u200f",
    ]
    for c in invisibles:
        texto = texto.replace(c, "")
    return texto


def normalizar_comillas(texto: str) -> str:
    texto = texto.replace("\u2018", "'").replace("\u2019", "'")
    texto = texto.replace("\u201a", "'").replace("\u201b", "'")
    texto = texto.replace("\u201c", '"').replace("\u201d", '"')
    texto = texto.replace("\u201e", '"').replace("\u201f", '"')
    return texto


def normalizar_dashes(texto: str) -> str:
    texto = texto.replace("\u2013", ", ")
    texto = texto.replace("\u2014", ", ")
    texto = texto.replace("\u2015", ", ")
    texto = texto.replace("\u2212", "-")
    texto = texto.replace("\u2053", "~")
    return texto


def normalizar_espacios_unicode(texto: str) -> str:
    espacios = [
        "\u00a0", "\u2009", "\u200a", "\u202f", "\u205f", "\u3000",
        "\u2002", "\u2003", "\u2004", "\u2005", "\u2006", "\u2007",
        "\u2008", "\u200b",
    ]
    for e in espacios:
        texto = texto.replace(e, " ")
    return texto


def normalizar_elipsis(texto: str) -> str:
    return texto.replace("\u2026", "...")


def eliminar_markdown(texto: str) -> str:
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.+?)\*", r"\1", texto)
    texto = re.sub(r"__(.+?)__", r"\1", texto)
    texto = re.sub(r"_(.+?)_", r"\1", texto)
    texto = re.sub(r"^#{1,6}\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\s*[-*+]\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\d+\.\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", texto)
    texto = re.sub(r"~~(.+?)~~", r"\1", texto)
    texto = re.sub(r"\[\[?(.+?)\]\]?", r"\1", texto)
    return texto


def corregir_elisiones(texto: str) -> str:
    texto = re.sub(r"\by\s+([ií])\b", r"e \1", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bo\s+([oó])\b", r"u \1", texto, flags=re.IGNORECASE)
    return texto


def corregir_puntuacion(texto: str) -> str:
    texto = re.sub(r"\s+([,;:!?])", r"\1", texto)
    texto = re.sub(r"([,;:!?])(?!\s)", r"\1 ", texto)
    texto = re.sub(r"\(\s+", "(", texto)
    texto = re.sub(r"\s+\)", ")", texto)
    return texto


def corregir_espaciado(texto: str) -> str:
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def clean_text(texto: str) -> str:
    if not texto:
        return ""

    texto = limpiar_caracteres_invisibles(texto)
    texto = normalizar_comillas(texto)
    texto = normalizar_dashes(texto)
    texto = normalizar_espacios_unicode(texto)
    texto = normalizar_elipsis(texto)
    texto = eliminar_markdown(texto)
    texto = corregir_elisiones(texto)
    texto = corregir_puntuacion(texto)
    texto = corregir_espaciado(texto)

    patrones_ia = [
        r"^\s*Como (?:modelo de lenguaje|IA|asistente)[^\.]*\.\s*",
        r"^\s*Claro[,\s]+(?:aquí tienes|con gusto|por supuesto)[^\.]*\.\s*",
        r"^\s*Por supuesto[,\s]+[^\.]*\.\s*",
        r"^\s*Aquí (?:tiene|está|te presento)[^\.]*\.\s*",
        r"\s*En conclusión,\s*",
        r"\s*Es importante destacar que\s*",
        r"\s*Cabe mencionar que\s*",
        r"\s*En el mundo actual,\s*",
        r"\s*En la actualidad,\s*",
        r"\s*Vale la pena mencionar que\s*",
    ]
    for patron in patrones_ia:
        texto = re.sub(patron, " ", texto, flags=re.IGNORECASE)

    texto = re.sub(r"\s{2,}", " ", texto).strip()
    return texto


# ---------------------------------------------------------------------------
# Análisis lingüístico y auditoría
# ---------------------------------------------------------------------------
def extraer_oraciones(texto: str) -> List[str]:
    oraciones = re.split(r"(?<=[.!?])\s+", texto)
    return [o.strip() for o in oraciones if o.strip()]


def extraer_parrafos(texto: str) -> List[str]:
    parrafos = re.split(r"\n\s*\n", texto)
    return [p.strip() for p in parrafos if p.strip()]


def contar_palabras(texto: str) -> int:
    return len(texto.split())


def calcular_burstiness(texto: str) -> float:
    oraciones = extraer_oraciones(texto)
    if len(oraciones) < 2:
        return 0.0
    longitudes = [len(o.split()) for o in oraciones]
    media = sum(longitudes) / len(longitudes)
    if media == 0:
        return 0.0
    varianza = sum((l - media) ** 2 for l in longitudes) / len(longitudes)
    return math.sqrt(varianza) / media


def calcular_ritmo(texto: str) -> float:
    return calcular_burstiness(texto)


def detectar_gerundios_remate(texto: str) -> bool:
    return bool(re.search(r",\s+\w+(?:ando|endo)\b", texto))


def detectar_enumeracion(texto: str) -> bool:
    return bool(re.search(r"\b\w+,\s+\w+\s+y\s+\w+\b", texto))


def detectar_paralelismo(texto: str) -> bool:
    oraciones = extraer_oraciones(texto)
    for i in range(len(oraciones) - 2):
        l1 = len(oraciones[i].split())
        l2 = len(oraciones[i + 1].split())
        l3 = len(oraciones[i + 2].split())
        if abs(l1 - l2) < 2 and abs(l2 - l3) < 2:
            return True
    return False


def detectar_repeticion_letrica(texto: str) -> Dict[str, int]:
    oraciones = extraer_oraciones(texto)
    inicios = [o.split()[0].lower() for o in oraciones if o.split()]
    return {p: c for p, c in Counter(inicios).items() if c > 3 and len(p) > 2}


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
    "en la era digital", "en el contexto de", "en el marco de",
    "en relación con", "en cuanto a", "respecto a", "con respecto a",
    "por lo que", "de modo que", "de manera que", "en tal medida que",
    "dar a entender", "poner de manifiesto", "hacer hincapié",
    "tomar en cuenta", "cobrar relevancia", "adquirir importancia",
]

CONECTORES_MANUAL = [
    "asimismo", "no obstante", "por lo tanto", "sin embargo", "además",
    "en consecuencia", "por consiguiente", "en efecto", "de hecho",
    "por otro lado", "en este sentido", "en definitiva",
]


def auditar_texto(texto: str) -> List[str]:
    problemas: List[str] = []
    oraciones = extraer_oraciones(texto)
    if len(oraciones) < 2:
        return problemas

    longitudes = [len(o.split()) for o in oraciones]
    media = sum(longitudes) / len(longitudes)
    varianza = sum((l - media) ** 2 for l in longitudes) / len(longitudes)
    cv = math.sqrt(varianza) / media if media > 0 else 0

    if cv < RITMO_MINIMO:
        problemas.append(f"Ritmo parejo (CV={cv:.2f} < {RITMO_MINIMO})")

    for i in range(len(longitudes) - 2):
        if (
            abs(longitudes[i] - longitudes[i + 1]) < 3
            and abs(longitudes[i + 1] - longitudes[i + 2]) < 3
        ):
            problemas.append("Tres oraciones seguidas de largo similar")
            break

    if any(l > 38 for l in longitudes):
        problemas.append("Oraciones demasiado largas (>38 palabras)")

    if not any(l < 9 for l in longitudes):
        problemas.append("Ninguna oración corta (<9 palabras)")

    texto_lower = texto.lower()
    encontradas = [f for f in FRASES_VETADAS_IA if f in texto_lower]
    if encontradas:
        problemas.append(f"Frases vetadas de IA ({len(encontradas)} encontradas)")

    if detectar_enumeracion(texto):
        problemas.append("Enumeraciones de tres elementos")

    if detectar_gerundios_remate(texto):
        problemas.append("Gerundios de remate tras coma")

    inicios = [o.split()[0] for o in oraciones if o.split()]
    art = [i for i in inicios if i in ["El", "La", "Los", "Las", "Se"]]
    if len(inicios) > 0 and (len(art) / len(inicios)) > 0.30:
        problemas.append("Inicios repetitivos (El/La/Los/Las/Se > 30%)")

    parrafos = extraer_parrafos(texto)
    for p in parrafos:
        op = extraer_oraciones(p)
        if len(op) >= 3:
            lp = [len(o.split()) for o in op]
            if max(lp) - min(lp) < 5:
                problemas.append("Párrafos planos (oraciones de largo parecido)")
                break

    total_conectores = sum(texto_lower.count(c) for c in CONECTORES_MANUAL)
    if total_conectores > len(oraciones) * 0.12:
        problemas.append(f"Conectores de manual en exceso ({total_conectores})")

    puntuacion = texto.count(";") + texto.count("—") + texto.count("(")
    if puntuacion < 3:
        problemas.append("Falta de puntuación variada (;, —, ())")

    if re.search(
        r"(en definitiva|en resumen|finalmente|como conclusión)\s*[,\.]",
        texto_lower,
    ):
        problemas.append("Moralejas o resúmenes al final")

    rep_letrica = detectar_repeticion_letrica(texto)
    if rep_letrica:
        peor = max(rep_letrica.items(), key=lambda x: x[1])
        problemas.append(f"Repetición de '{peor[0]}' al inicio ({peor[1]} veces)")

    if detectar_paralelismo(texto):
        problemas.append("Paralelismo sintáctico excesivo")

    return problemas


# ---------------------------------------------------------------------------
# Detección de modelos y mapeo modelo -> proveedor
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def detectar_modelos(_version: int = 1) -> Dict[str, List[str]]:
    disponibles: Dict[str, List[str]] = {}

    for prov in ORDEN_FALLBACK:
        cfg = PROVEEDORES[prov]
        api_key = leer_secreto(cfg["clave"])
        if not api_key:
            continue

        if cfg["tipo"] == "gemini_sdk":
            disponibles[prov] = list(MODELOS_FIJOS[prov])
            continue

        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            if prov == "openrouter":
                headers["HTTP-Referer"] = "https://streamlit.io"

            response = requests.get(
                cfg["models_endpoint"], headers=headers, timeout=15
            )
            response.raise_for_status()
            data = response.json()

            modelos_raw = data.get("data", [])
            modelos_filtrados: List[str] = []

            for m in modelos_raw:
                mid = m.get("id", "")
                if not mid:
                    continue
                if any(exc in mid.lower() for exc in EXCLUIDOS):
                    continue
                if any(fam in mid.lower() for fam in FAMILIAS_TEXTO):
                    if mid not in modelos_filtrados:
                        modelos_filtrados.append(mid)

            disponibles[prov] = modelos_filtrados[:15] if modelos_filtrados else list(MODELOS_FIJOS[prov])

        except Exception as e:
            logger.warning(f"Error detectando modelos de {prov}: {e}")
            disponibles[prov] = list(MODELOS_FIJOS[prov])

    return disponibles


def construir_mapa_modelos(disponibles: Dict[str, List[str]]) -> Dict[str, str]:
    """Devuelve un diccionario modelo_id -> proveedor_key."""
    mapa: Dict[str, str] = {}
    for prov, lista in MODELOS_FIJOS.items():
        for m in lista:
            mapa[m] = prov
    for prov, lista in disponibles.items():
        for m in lista:
            mapa[m] = prov
    return mapa


def resolver_proveedor_de_modelo(modelo: str, mapa_modelos: Dict[str, str]) -> str:
    if modelo in mapa_modelos:
        return mapa_modelos[modelo]
    baja = modelo.lower()
    if "gemini" in baja:
        return "gemini"
    if "deepseek" in baja:
        return "deepseek"
    if "/" in modelo:
        return "openrouter"
    return "groq"


def construir_opciones_y_default(
    disponibles: Dict[str, List[str]],
) -> Tuple[List[str], List[str]]:
    todas_opciones: List[str] = []
    for lista in disponibles.values():
        for m in lista:
            if m not in todas_opciones:
                todas_opciones.append(m)

    if not todas_opciones:
        for lista in MODELOS_FIJOS.values():
            for m in lista:
                if m not in todas_opciones:
                    todas_opciones.append(m)

    default: List[str] = []
    for m in MODELOS_FIJOS["groq"][:2]:
        if m in todas_opciones and m not in default:
            default.append(m)

    if not default and todas_opciones:
        default = todas_opciones[:2]

    return todas_opciones, default


# ---------------------------------------------------------------------------
# Sistema de pausados y llamadas a API
# ---------------------------------------------------------------------------
PAUSAS: Dict[str, Dict[str, float]] = {
    prov: {"cuota": 0.0, "lento": 0.0, "diaria": 0.0}
    for prov in ORDEN_FALLBACK
}
_lock_pausas = threading.Lock()


def registrar_pausa(proveedor: str, tipo: str) -> None:
    with _lock_pausas:
        if proveedor in PAUSAS and tipo in PAUSAS[proveedor]:
            PAUSAS[proveedor][tipo] = time.time()
            logger.info(f"Pausa {tipo} registrada para {proveedor}")


def esta_pausado(proveedor: str) -> bool:
    with _lock_pausas:
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


def manejar_error_api(proveedor: str, error: str) -> None:
    error_lower = error.lower()
    if "429" in error_lower or "rate limit" in error_lower or "quota" in error_lower:
        registrar_pausa(proveedor, "cuota")
    elif "timeout" in error_lower or "slow" in error_lower:
        registrar_pausa(proveedor, "lento")
    elif "daily" in error_lower or "day" in error_lower:
        registrar_pausa(proveedor, "diaria")


def con_retry(func, *args, **kwargs):
    ultimo_error = None
    for intento in range(MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            ultimo_error = e
            if intento < MAX_RETRIES:
                espera = BASE_BACKOFF ** (intento + 1)
                logger.warning(f"Reintento {intento + 1} en {espera:.1f}s: {e}")
                time.sleep(espera)
    raise ultimo_error


def llamar_openai_compatible(
    proveedor: str,
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> str:
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

    def _hacer():
        response = requests.post(
            cfg["endpoint"], headers=headers, json=payload, timeout=TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    return con_retry(_hacer)


def llamar_gemini(
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> str:
    api_key = leer_secreto(PROVEEDORES["gemini"]["clave"])
    if not api_key:
        raise ValueError("GEMINI_API_KEY no configurada")

    def _hacer():
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

    return con_retry(_hacer)


def llamar_proveedor(
    proveedor: str,
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> dict:
    orden = [proveedor] + [p for p in ORDEN_FALLBACK if p != proveedor]
    ultimo_error = None

    for prov in orden:
        if esta_pausado(prov):
            continue

        cfg = PROVEEDORES[prov]
        if not leer_secreto(cfg["clave"]):
            continue

        modelo_actual = modelo if prov == proveedor else MODELO_POR_PROVEEDOR[prov]

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
# Datos clave y pasos del pipeline
# ---------------------------------------------------------------------------
def extraer_datos_clave(texto: str) -> List[str]:
    datos: List[str] = []
    fechas = re.findall(
        r"\b\d{1,2}\s+de\s+[a-záéíóúñ]+\s+de\s+\d{4}\b", texto, re.IGNORECASE
    )
    datos.extend(fechas)
    años = re.findall(r"\b\d{4}\b", texto)
    datos.extend(años)
    cifras = re.findall(
        r"\b\d+[.,]?\d*\s*(?:mil|millones|billones|%)?\b", texto, re.IGNORECASE
    )
    datos.extend(cifras)
    nombres = re.findall(r"\b[A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)+\b", texto)
    datos.extend(nombres[:15])
    citas = re.findall(r"[\"']([^\"']{10,80})[\"']", texto)
    datos.extend(citas[:5])
    return list(dict.fromkeys(datos))


def procesar_bloque(
    texto: str,
    paso: str,
    proveedor: str,
    modelo: str,
    instruccion_medida: str = "",
) -> dict:
    prompts = {
        "retro": (PROMPT_RETRO, TEMPERATURA_INTERMEDIA),
        "estructura": (PROMPT_ESTRUCTURA, TEMPERATURA_INTERMEDIA),
        "final": (PROMPT_FINAL_BASE, TEMPERATURA_FINAL),
    }

    if paso not in prompts:
        return {
            "texto": texto,
            "proveedor_usado": None,
            "modelo_usado": None,
            "exito": False,
            "error": f"Paso desconocido: {paso}",
        }

    system_base, temperature = prompts[paso]
    system_prompt = (
        con_muestra(system_base, PROMPT_FINAL_REGLAS, MUESTRA_ESTILO_TESIS, instruccion_medida)
        if paso == "final"
        else system_base
    )
    return llamar_proveedor(proveedor, modelo, system_prompt, texto, temperature)


def revisar_bloque(
    texto: str,
    proveedor: str,
    modelo: str,
    problemas: List[str],
    longitud_original: int,
    datos_clave: List[str],
) -> dict:
    if not problemas:
        return {
            "texto": texto,
            "proveedor_usado": proveedor,
            "modelo_usado": modelo,
            "exito": True,
            "error": None,
        }

    texto_actual = texto
    problemas_actuales = problemas

    for _ in range(MAX_RONDAS_CORRECCION):
        lista = "\n".join(f"- {p}" for p in problemas_actuales)
        prompt_usuario = (
            f"Texto a corregir:\n---\n{texto_actual}\n---\n\n"
            f"Problemas detectados:\n{lista}\n\n"
            f"Longitud original: {longitud_original} palabras. Mantén entre "
            f"{int(longitud_original * 0.95)} y {int(longitud_original * 1.15)} palabras.\n"
            f"Datos obligatorios: {', '.join(datos_clave[:10])}. No pierdas ninguno.\n\n"
            f"Corrige SOLO estos problemas sin resumir ni cambiar la extensión."
        )
        res = llamar_proveedor(
            proveedor, modelo, PROMPT_CORRECCION_BASE, prompt_usuario,
            TEMPERATURA_INTERMEDIA,
        )
        if not res["exito"]:
            return {
                "texto": texto_actual,
                "proveedor_usado": res["proveedor_usado"],
                "modelo_usado": res["modelo_usado"],
                "exito": False,
                "error": res["error"],
            }

        nuevo = clean_text(res["texto"])
        if nuevo == texto_actual:
            break
        texto_actual = nuevo
        nuevos_problemas = auditar_texto(texto_actual)
        if not nuevos_problemas:
            break
        problemas_actuales = nuevos_problemas

    return {
        "texto": texto_actual,
        "proveedor_usado": proveedor,
        "modelo_usado": modelo,
        "exito": True,
        "error": None,
    }


def extraer_oraciones_problema(texto: str) -> List[str]:
    oraciones = extraer_oraciones(texto)
    problemas: List[str] = []
    frases_vetadas = [
        "en conclusión", "es fundamental", "cabe destacar", "juega un papel",
        "se ha convertido en", "en el ámbito de", "mediante", "sin embargo",
    ]
    for o in oraciones:
        palabras = o.split()
        n = len(palabras)
        if n == 0:
            continue
        primera = palabras[0]
        baja = o.lower()
        if n > 30 or any(f in baja for f in frases_vetadas):
            problemas.append(o)
            continue
        if primera in ["El", "La", "Los", "Las", "Se"] and n >= 12:
            problemas.append(o)
    return problemas


def reescribir_con_detector(texto: str, proveedor: str, modelo: str) -> dict:
    malas = extraer_oraciones_problema(texto)
    if not malas:
        return {
            "texto": texto,
            "proveedor_usado": proveedor,
            "modelo_usado": modelo,
            "exito": True,
            "error": None,
        }

    lista = "\n".join(f"- {o}" for o in malas)
    prompt_usuario = (
        f"Texto completo:\n---\n{texto}\n---\n\n"
        f"Reescribe con cambio sintáctico total SOLO estas oraciones "
        f"problemáticas (conserva el resto intacto):\n{lista}"
    )
    return llamar_proveedor(
        proveedor, modelo, PROMPT_DETECTOR_BASE, prompt_usuario, TEMPERATURA_FINAL
    )


def ajustar_con_detectores(texto: str, proveedor: str, modelo: str) -> dict:
    gptzero_key = leer_secreto("GPTZERO_API_KEY")
    if not gptzero_key:
        return {
            "texto": texto,
            "proveedor_usado": proveedor,
            "modelo_usado": modelo,
            "exito": True,
            "error": None,
        }

    texto_actual = texto
    for _ in range(MAX_RONDAS_DETECTORES):
        score_ia = 0.0
        try:
            headers = {"X-API-KEY": gptzero_key, "Content-Type": "application/json"}
            response = requests.post(
                "https://api.gptzero.me/v2/predict/text",
                headers=headers,
                json={"document": texto_actual},
                timeout=30,
            )
            if response.status_code == 200:
                docs = response.json().get("documents", [])
                if docs:
                    score_ia = docs[0].get("average_generated_prob", 0.0)
        except Exception as e:
            logger.warning(f"GPTZero error: {e}")

        if score_ia <= 0.30:
            break
        res = reescribir_con_detector(texto_actual, proveedor, modelo)
        if not res["exito"]:
            break
        nuevo = clean_text(res["texto"])
        if nuevo == texto_actual:
            break
        texto_actual = nuevo

    return {
        "texto": texto_actual,
        "proveedor_usado": proveedor,
        "modelo_usado": modelo,
        "exito": True,
        "error": None,
    }


def armar_plan(
    modelos_otros: List[str],
    mapa_modelos: Dict[str, str],
    modo_profundo: bool,
    romper_estructura: bool,
    correccion_auto: bool,
    modelo_distinto: bool,
    pasadas: int,
    modelo_final: str,
    proveedor_final: str,
) -> List[Dict[str, str]]:
    pool_modelos = modelos_otros or [modelo_final]

    def _elegir(idx: int) -> Tuple[str, str]:
        if not modelo_distinto:
            return proveedor_final, modelo_final
        m = pool_modelos[idx % len(pool_modelos)]
        prov = resolver_proveedor_de_modelo(m, mapa_modelos)
        return prov, m

    plan: List[Dict[str, str]] = []
    idx = 0

    for _ in range(max(1, pasadas)):
        if modo_profundo:
            prov, mod = _elegir(idx)
            plan.append({"paso": "retro", "proveedor": prov, "modelo": mod})
            idx += 1
        if romper_estructura:
            prov, mod = _elegir(idx)
            plan.append({"paso": "estructura", "proveedor": prov, "modelo": mod})
            idx += 1

    plan.append({"paso": "final", "proveedor": proveedor_final, "modelo": modelo_final})

    if correccion_auto:
        prov, mod = _elegir(idx)
        plan.append({"paso": "correccion", "proveedor": prov, "modelo": mod})
        idx += 1
        prov, mod = _elegir(idx)
        plan.append({"paso": "detector", "proveedor": prov, "modelo": mod})

    return plan


def dividir_en_bloques(texto: str, tamano: int = TAMANO_BLOQUE) -> List[str]:
    parrafos = extraer_parrafos(texto)
    bloques: List[str] = []
    actual = ""
    actual_palabras = 0
    for p in parrafos:
        p_palabras = contar_palabras(p)
        if actual_palabras + p_palabras > tamano and actual:
            bloques.append(actual.strip())
            actual = p
            actual_palabras = p_palabras
        else:
            actual += "\n\n" + p if actual else p
            actual_palabras += p_palabras
    if actual.strip():
        bloques.append(actual.strip())
    return bloques if bloques else [texto]


def ejecutar_etapa(
    texto_actual: str,
    etapa: Dict[str, str],
    instruccion_medida: str,
    datos_clave: List[str],
) -> dict:
    paso = etapa["paso"]
    proveedor = etapa["proveedor"]
    modelo = etapa["modelo"]
    longitud_actual = contar_palabras(texto_actual)

    if paso in ("retro", "estructura", "final"):
        return procesar_bloque(texto_actual, paso, proveedor, modelo, instruccion_medida)
    if paso == "correccion":
        problemas = auditar_texto(texto_actual)
        return revisar_bloque(
            texto_actual, proveedor, modelo, problemas, longitud_actual, datos_clave
        )
    if paso == "detector":
        return reescribir_con_detector(texto_actual, proveedor, modelo)

    return {
        "texto": texto_actual,
        "proveedor_usado": None,
        "modelo_usado": None,
        "exito": False,
        "error": f"Paso no soportado: {paso}",
    }


def procesar_bloque_individual(
    bloque: str,
    plan: List[Dict[str, str]],
    instruccion_medida: str,
    datos_clave: List[str],
) -> dict:
    texto_actual = bloque
    log: List[str] = []

    for etapa in plan:
        res = ejecutar_etapa(texto_actual, etapa, instruccion_medida, datos_clave)
        if not res["exito"]:
            return {
                "texto": texto_actual,
                "log": log,
                "exito": False,
                "error": res["error"],
            }
        texto_actual = clean_text(res["texto"])
        log.append(f"✓ {etapa['paso']}: {res['proveedor_usado']} ({res['modelo_usado']})")

    return {"texto": texto_actual, "log": log, "exito": True, "error": None}


def procesar(texto: str, config: dict, estado: dict) -> dict:
    log_pasos: List[str] = []
    inicio_total = time.time()

    modelo_final = config.get("modelo_final", MODELO_POR_PROVEEDOR["groq"])
    mapa_modelos = config.get("mapa_modelos") or construir_mapa_modelos({})
    proveedor_final = config.get("modelo_final_prov") or resolver_proveedor_de_modelo(
        modelo_final, mapa_modelos
    )
    modelos_otros = config.get("proveedores_otros") or list(MODELO_POR_PROVEEDOR.values())
    pasadas = int(config.get("pasadas", 2))
    modelo_distinto = bool(config.get("modelo_distinto", True))

    datos_clave = extraer_datos_clave(texto)
    num_parrafos = len(extraer_parrafos(texto))
    num_palabras = contar_palabras(texto)
    instruccion_medida = instrucciones_de_medida(num_parrafos, num_palabras, datos_clave)

    plan = armar_plan(
        modelos_otros=modelos_otros,
        mapa_modelos=mapa_modelos,
        modo_profundo=config.get("modo_profundo", True),
        romper_estructura=config.get("romper_estructura", True),
        correccion_auto=config.get("correccion_auto", True),
        modelo_distinto=modelo_distinto,
        pasadas=pasadas,
        modelo_final=modelo_final,
        proveedor_final=proveedor_final,
    )

    bloques = dividir_en_bloques(texto, TAMANO_BLOQUE)
    texto_actual = ""

    if len(bloques) > 1:
        estado["paso"] = f"Procesando {len(bloques)} bloques en paralelo..."
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(
                    procesar_bloque_individual,
                    bloque, plan, instruccion_medida, datos_clave,
                ): i
                for i, bloque in enumerate(bloques)
            }
            resultados: List[Optional[dict]] = [None] * len(bloques)
            completados = 0
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    resultados[idx] = future.result()
                except Exception as e:
                    resultados[idx] = {
                        "texto": bloques[idx],
                        "log": [],
                        "exito": False,
                        "error": str(e),
                    }
                completados += 1
                estado["progreso"] = min(completados / len(bloques), 0.95)

            for res in resultados:
                if res is None:
                    continue
                if not res["exito"]:
                    return {
                        "exito": False,
                        "texto": "",
                        "log": log_pasos,
                        "duracion": time.time() - inicio_total,
                        "problemas": [],
                        "ritmo_original": calcular_ritmo(texto),
                        "ritmo_final": 0.0,
                        "error": res["error"],
                    }
                texto_actual += res["texto"] + "\n\n"
                log_pasos.extend(res["log"])
    else:
        texto_actual = texto
        for i, etapa in enumerate(plan):
            estado["paso"] = f"Etapa {i + 1}/{len(plan)}: {etapa['paso']}"
            res = ejecutar_etapa(texto_actual, etapa, instruccion_medida, datos_clave)
            if not res["exito"]:
                return {
                    "exito": False,
                    "texto": "",
                    "log": log_pasos,
                    "duracion": time.time() - inicio_total,
                    "problemas": [],
                    "ritmo_original": calcular_ritmo(texto),
                    "ritmo_final": 0.0,
                    "error": res["error"],
                }
            texto_actual = clean_text(res["texto"])
            log_pasos.append(
                f"✓ {etapa['paso']}: {res['proveedor_usado']} ({res['modelo_usado']})"
            )
            estado["progreso"] = min((i + 1) / len(plan), 0.95)

    texto_actual = clean_text(texto_actual)

    if config.get("correccion_auto", True):
        res = ajustar_con_detectores(texto_actual, proveedor_final, modelo_final)
        if res["exito"]:
            texto_actual = clean_text(res["texto"])
            log_pasos.append("✓ Ajuste con detectores externos")

    return {
        "exito": True,
        "texto": texto_actual,
        "log": log_pasos,
        "duracion": time.time() - inicio_total,
        "problemas": auditar_texto(texto_actual),
        "ritmo_original": calcular_ritmo(texto),
        "ritmo_final": calcular_ritmo(texto_actual),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Gráfico SVG, login, cronómetro y botón copiar
# ---------------------------------------------------------------------------
def generar_svg_ritmo(longitudes_orig: List[int], longitudes_fin: List[int]) -> str:
    if not longitudes_orig and not longitudes_fin:
        return "<p>No hay suficientes oraciones para graficar.</p>"

    max_len = max(
        max(longitudes_orig) if longitudes_orig else 0,
        max(longitudes_fin) if longitudes_fin else 0,
        40,
    )
    n = max(len(longitudes_orig), len(longitudes_fin))
    ancho_barra = max(2, min(12, 700 // max(n, 1)))
    alto_max = 120
    gap = 2

    barras = ""
    for i in range(n):
        x = i * (ancho_barra * 2 + gap * 3)
        if i < len(longitudes_orig):
            l = longitudes_orig[i]
            h = max(int((l / max_len) * alto_max), 2)
            barras += (
                f'<rect x="{x}" y="{alto_max - h}" width="{ancho_barra}" '
                f'height="{h}" fill="#A6ACB6" opacity="0.55" rx="1" />'
            )
        if i < len(longitudes_fin):
            l = longitudes_fin[i]
            h = max(int((l / max_len) * alto_max), 2)
            barras += (
                f'<rect x="{x + ancho_barra + gap}" y="{alto_max - h}" '
                f'width="{ancho_barra}" height="{h}" fill="#22D3E6" rx="1" />'
            )

    ancho_total = n * (ancho_barra * 2 + gap * 3) + 10
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'height="{alto_max + 40}" viewBox="0 0 {ancho_total} {alto_max + 40}">'
        f'<text x="0" y="15" font-size="11" fill="#A6ACB6" '
        f'font-family="sans-serif">Gris: original | Cyan: humanizado</text>'
        f'<g transform="translate(5, 25)">{barras}</g>'
        f'<line x1="0" y1="{alto_max + 25}" x2="{ancho_total}" '
        f'y2="{alto_max + 25}" stroke="#2A2F38" stroke-width="1" />'
        f'</svg>'
    )


def mostrar_logo(ancho: int = 140) -> None:
    try:
        st.image(LOGO_URL, width=ancho)
    except Exception:
        st.markdown(
            '<div style="font-size:48px;text-align:center;">✍️</div>',
            unsafe_allow_html=True,
        )


def login_screen() -> None:
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        mostrar_logo(LOGO_FONTSIZE)
        st.markdown('<h1 class="login-title">Humanizador Pro</h1>', unsafe_allow_html=True)
        st.markdown(
            '<p class="login-subtitle">Convierte un texto generado por IA en '
            'prosa natural, con ritmo y voz de persona.</p>',
            unsafe_allow_html=True,
        )

        pwd = st.text_input("Contraseña", type="password", key="login_pwd")
        if st.button("Ingresar", type="primary", use_container_width=True):
            esperada = leer_secreto("APP_PASSWORD")
            if not esperada:
                st.error(
                    "Falta configurar APP_PASSWORD en los secrets. "
                    "No se permite login con contraseña por defecto."
                )
            elif pwd == esperada:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")

        st.markdown(
            '<div class="login-footer">'
            '<p>Elaborado por Manu</p>'
            '<p>®Humanizadormanu, derechos reservados © 2026</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def render_cronometro(start_ts: Optional[float] = None) -> None:
    if start_ts is None:
        start_ts = time.time()
    html = f"""
    <div id="crono" class="cronometro-container">Tiempo transcurrido: 0:00</div>
    <script>
    var startTs = {start_ts * 1000};
    function tick() {{
        var t = Math.max(0, Math.floor((Date.now() - startTs) / 1000));
        var m = Math.floor(t / 60);
        var s = t % 60;
        var el = document.getElementById("crono");
        if (el) {{
            el.textContent = "Tiempo transcurrido: " + m + ":" + (s < 10 ? "0" : "") + s;
        }}
    }}
    tick();
    setInterval(tick, 250);
    </script>
    """
    components.html(html, height=80)


def render_boton_copiar(texto: str) -> None:
    js_texto = json.dumps(texto).replace("</", "<\\/")
    html_copiar = (
        '<button id="btnC" class="btn-copiar">📋 Copiar texto humanizado</button>'
        '<script>'
        'document.getElementById("btnC").addEventListener("click", function(){'
        'var t=' + js_texto + ';'
        'var btn = document.getElementById("btnC");'
        'function ok(){'
        'btn.textContent="✅ ¡Copiado!";'
        'btn.classList.add("copiado");'
        'setTimeout(function(){'
        'btn.textContent="📋 Copiar texto humanizado";'
        'btn.classList.remove("copiado");'
        '},1500);'
        '}'
        'function fallback(s){'
        'var ta=document.createElement("textarea");'
        'ta.value=s;'
        'ta.style.position="fixed";'
        'ta.style.left="-9999px";'
        'document.body.appendChild(ta);'
        'ta.select();'
        'try{document.execCommand("copy");}catch(e){}'
        'document.body.removeChild(ta);'
        '}'
        'if(navigator.clipboard && window.isSecureContext){'
        'navigator.clipboard.writeText(t).then(ok).catch(function(){fallback(t);ok();});'
        '}else{fallback(t);ok();}'
        '});'
        '</script>'
    )
    components.html(html_copiar, height=70)


# ---------------------------------------------------------------------------
# Interfaz principal
# ---------------------------------------------------------------------------
def main() -> None:
    if not st.session_state.get("logged_in", False):
        login_screen()
        return

    if st.session_state.pop("_limpiar_entrada", False):
        st.session_state.texto_entrada = ""
    elif "texto_entrada" not in st.session_state:
        st.session_state.texto_entrada = ""

    with st.sidebar:
        mostrar_logo(LOGO_SIDEBAR)
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

        st.header("⚙️ Configuración")

        modelo_final = st.selectbox(
            "Modelo para la redacción final",
            options=MODELOS_FIJOS["groq"],
            index=0,
        )
        modelo_final_prov = "groq"

        disponibles = detectar_modelos()
        mapa_modelos = construir_mapa_modelos(disponibles)
        opciones, default_otros = construir_opciones_y_default(disponibles)

        modelos_otros = st.multiselect(
            "Modelos para los demás pasos",
            options=opciones,
            default=default_otros,
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
        "auditoría de 12+ puntos y reescritura por detector."
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
                "🚀 Humanizar texto",
                type="primary",
                use_container_width=True,
                disabled=not texto_entrada.strip(),
            )
        with col_b2:
            if st.button("🗑️ Limpiar", use_container_width=True):
                st.session_state._limpiar_entrada = True
                st.session_state.pop("resultado", None)
                st.session_state.pop("crono_start", None)
                st.rerun()

    with col_der:
        st.subheader("✨ Texto humanizado")
        if st.session_state.get("resultado"):
            res = st.session_state.resultado
            texto_escapado = (
                res["texto"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            st.markdown(
                f'<div class="hoja-papel">{texto_escapado}</div>',
                unsafe_allow_html=True,
            )
            render_boton_copiar(res["texto"])
            st.download_button(
                "📥 Descargar resultado",
                data=res["texto"],
                file_name="texto_humanizado.txt",
                mime="text/plain",
                use_container_width=True,
            )

    if st.session_state.get("resultado"):
        res = st.session_state.resultado
        st.divider()
        st.subheader("📊 Análisis de Ritmo y Auditoría")

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("### Ritmo del texto original")
            lo = [len(o.split()) for o in extraer_oraciones(res.get("texto_original", ""))]
            lf = [len(o.split()) for o in extraer_oraciones(res["texto"])]
            st.markdown(generar_svg_ritmo(lo, lf), unsafe_allow_html=True)
            st.metric(
                "Coeficiente de Variación (CV) Original",
                f"{res['ritmo_original']:.2f}",
            )
        with col_r2:
            st.markdown("### Ritmo del texto humanizado")
            st.markdown("<br>", unsafe_allow_html=True)
            cvf = calcular_ritmo(res["texto"])
            st.metric(
                "Coeficiente de Variación (CV) Humanizado",
                f"{cvf:.2f}",
                delta="Mejorado" if cvf >= RITMO_MINIMO else "Bajo",
            )

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
                    st.write(f'<div class="log-line">{linea}</div>', unsafe_allow_html=True)

    if procesar_btn:
        config = {
            "modo_profundo": modo_profundo,
            "pasadas": pasadas,
            "modelo_distinto": modelo_distinto,
            "romper_estructura": romper_estructura,
            "correccion_auto": correccion_auto,
            "modelo_final": modelo_final,
            "modelo_final_prov": modelo_final_prov,
            "proveedores_otros": modelos_otros,
            "mapa_modelos": mapa_modelos,
        }
        estado = {"paso": "Iniciando...", "progreso": 0.0, "res": None, "fin": False}

        def worker():
            try:
                estado["res"] = procesar(texto_entrada.strip(), config, estado)
            except Exception as e:
                estado["res"] = {
                    "exito": False,
                    "texto": "",
                    "log": [],
                    "duracion": 0.0,
                    "problemas": [],
                    "ritmo_original": 0.0,
                    "ritmo_final": 0.0,
                    "error": f"Error inesperado: {e}",
                }
            finally:
                estado["fin"] = True

        st.session_state.crono_start = time.time()
        hilo = threading.Thread(target=worker, daemon=True)
        hilo.start()

        render_cronometro(st.session_state.crono_start)
        barra = st.progress(0)
        estatus = st.empty()

        while not estado["fin"]:
            barra.progress(min(estado["progreso"], 1.0))
            estatus.markdown(
                f'<div class="status-text">⏳ {estado["paso"]} — '
                f'{int(estado["progreso"] * 100)}%</div>',
                unsafe_allow_html=True,
            )
            time.sleep(0.3)

        hilo.join(timeout=1)
        barra.progress(1.0)
        estatus.markdown(
            '<div class="status-text">✅ Proceso completado</div>',
            unsafe_allow_html=True,
        )

        res = estado["res"]
        if res and res["exito"]:
            res["texto_original"] = texto_entrada.strip()
            st.session_state.resultado = res
            st.rerun()
        elif res:
            st.error(f"❌ Error: {res.get('error', 'desconocido')}")


if __name__ == "__main__":
    main()
