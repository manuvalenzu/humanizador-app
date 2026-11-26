"""
Humanizador Pro - Aplicación Streamlit para humanizar textos generados por IA.

Pipeline multi-proveedor con retrotraducción ES-EN-ES, reestructuración,
auditoría de 12+ detectores, reescritura por detector, procesamiento en
bloques paralelos, sistema de pausados, y tema oscuro completo.

Autor: Manu
Derechos reservados: Humanizadormanu, 2026
"""

import re
import json
import time
import math
import hashlib
import threading
import logging
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import streamlit as st
import streamlit.components.v1 as components
from google import genai


# ---------------------------------------------------------------------------
# Configuracion de la pagina
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

.badge-success {
    background-color: rgba(34, 197, 94, 0.15) !important;
    color: var(--success) !important;
    border: 1px solid var(--success) !important;
    padding: 4px 8px !important;
    border-radius: 4px !important;
    font-size: 0.85rem !important;
}

.badge-warning {
    background-color: rgba(245, 158, 11, 0.15) !important;
    color: var(--warning) !important;
    border: 1px solid var(--warning) !important;
    padding: 4px 8px !important;
    border-radius: 4px !important;
    font-size: 0.85rem !important;
}

.badge-error {
    background-color: rgba(239, 68, 68, 0.15) !important;
    color: var(--error) !important;
    border: 1px solid var(--error) !important;
    padding: 4px 8px !important;
    border-radius: 4px !important;
    font-size: 0.85rem !important;
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

.hoja-papel::-webkit-scrollbar {
    width: 8px !important;
}

.hoja-papel::-webkit-scrollbar-track {
    background: var(--paper) !important;
}

.hoja-papel::-webkit-scrollbar-thumb {
    background: #c4c2b8 !important;
    border-radius: 4px !important;
}

.hoja-papel::-webkit-scrollbar-thumb:hover {
    background: #a4a298 !important;
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

.logo-img {
    border-radius: 12px !important;
    box-shadow: 0 4px 12px var(--shadow) !important;
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

.log-success {
    color: var(--success) !important;
}

.log-warning {
    color: var(--warning) !important;
}

.log-error {
    color: var(--error) !important;
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
MAX_RETRIES = 2
BASE_BACKOFF = 1.5
PAUSA_CUOTA = 120
PAUSA_LENTO = 180
PAUSA_DIARIA = 1800

LOGO_URL = "https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png"
LOGO_FONTSIZE = 180
LOGO_SIDEBAR = 100

CADENA_FINAL = ["groq", "openrouter", "nvidia", "deepseek", "gemini"]

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
    "gpt", "claude", "gemini", "grok", "gemini-pro",
]


# ---------------------------------------------------------------------------
# Muestra de estilo integrada (Tesis 2003)
# ---------------------------------------------------------------------------
MUESTRA_ESTILO_TESIS = """
Las ciudades han sido tradicionalmente de dos tipos, diseñadas y proyectadas de manera precisa con un orden predeterminado o desarrolladas con un crecimiento espontáneo sin ningún plan preestablecido. De cualquier manera que éstas sean clasificadas, dentro de estas dos categorías, su expansión y crecimiento han llevado a considerar los mecanismos de control necesarios para regular el uso del suelo y las posibles aplicaciones a que su desarrollo pudiese llegar a generar prospectivamente.

De acuerdo con lo anterior, es necesario comprender cómo la ciudad, a través del uso del suelo, caracteriza todavía en la actualidad los mismos tipos de ciudades antes mencionados y que pueden ser definidos como modelos históricos y antagónicos.

Para plantear una hipótesis al problema del suelo urbano, debemos necesariamente considerar tres factores que intervienen y se afectan mutuamente de acuerdo al uso del espacio territorial de la ciudad.
""".strip()

VOCABULARIO_ACADEMICO = [
    "prospectivamente", "tuición", "antagónicos", "coyuntural", "delineamientos",
    "emplazamiento", "condicionantes y exigencias", "tejido social",
    "poder adquisitivo", "espacialidad", "territorialidad",
]

CONECTORES_ESTILO = [
    "De acuerdo con lo anterior", "De lo anterior se puede desprender",
    "Es así como", "De cualquier manera que éstas sean clasificadas",
    "Por lo tanto", "Sin embargo",
]


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
def con_muestra(
    prompt_base: str,
    reglas: str,
    muestra: str,
    instruccion_medida: str,
) -> str:
    """
    Integra la muestra de estilo de la tesis 2003 y las instrucciones de medida
    en un prompt base.

    Args:
        prompt_base: Instrucciones principales del rol.
        reglas: Reglas específicas del paso.
        muestra: Muestra de estilo a imitar.
        instruccion_medida: Instrucciones sobre párrafos, palabras y datos.

    Returns:
        Prompt final combinado.
    """
    return f"""{prompt_base}

MUESTRA DE ESTILO DE REFERENCIA (imita su registro, ritmo y tono):
---
{muestra}
---

{instruccion_medida}

{reglas}"""


def instrucciones_de_medida(
    num_parrafos: int,
    num_palabras: int,
    datos_clave: List[str],
) -> str:
    """
    Genera instrucciones de medida para incluir en los prompts.

    Args:
        num_parrafos: Cantidad de párrafos del original.
        num_palabras: Cantidad de palabras del original.
        datos_clave: Lista de datos que no se pueden perder.

    Returns:
        String con instrucciones de medida formateadas.
    """
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
# Utilidades de lectura de secretos
# ---------------------------------------------------------------------------
def leer_secreto(nombre: str) -> str:
    """
    Lee una clave desde st.secrets de forma segura.

    Args:
        nombre: Nombre de la clave a leer.

    Returns:
        Valor de la clave como string, o cadena vacía si no existe.
    """
    try:
        valor = st.secrets.get(nombre, "")
    except Exception:
        return ""
    if valor is None:
        return ""
    return str(valor).strip()


def validar_secretos() -> Dict[str, bool]:
    """
    Valida la presencia de todos los secretos necesarios.

    Returns:
        Diccionario con nombre de secreto y booleano de presencia.
    """
    resultado = {}
    for prov in ORDEN_FALLBACK:
        cfg = PROVEEDORES[prov]
        resultado[cfg["clave"]] = bool(leer_secreto(cfg["clave"]))
    resultado["APP_PASSWORD"] = bool(leer_secreto("APP_PASSWORD"))
    return resultado


# ---------------------------------------------------------------------------
# Funciones de limpieza de texto
# ---------------------------------------------------------------------------
def limpiar_caracteres_invisibles(texto: str) -> str:
    """
    Elimina caracteres invisibles como zero-width spaces, BOM, soft hyphens.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto sin caracteres invisibles.
    """
    invisibles = [
        "\u200b", "\u200c", "\u200d", "\ufeff", "\u00ad",
        "\u2060", "\u2061", "\u2062", "\u2063", "\u2064",
        "\u2028", "\u2029", "\u200e", "\u200f",
    ]
    for c in invisibles:
        texto = texto.replace(c, "")
    return texto


def normalizar_comillas(texto: str) -> str:
    """
    Convierte comillas curvas en comillas rectas.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto con comillas normalizadas.
    """
    texto = texto.replace("\u2018", "'").replace("\u2019", "'")
    texto = texto.replace("\u201a", "'").replace("\u201b", "'")
    texto = texto.replace("\u201c", '"').replace("\u201d", '"')
    texto = texto.replace("\u201e", '"').replace("\u201f", '"')
    return texto


def normalizar_dashes(texto: str) -> str:
    """
    Convierte em-dashes y en-dashes en coma o punto según contexto.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto con dashes normalizados.
    """
    texto = texto.replace("\u2013", ", ")
    texto = texto.replace("\u2014", ", ")
    texto = texto.replace("\u2015", ", ")
    texto = texto.replace("\u2212", "-")
    texto = texto.replace("\u2053", "~")
    return texto


def normalizar_espacios_unicode(texto: str) -> str:
    """
    Normaliza espacios Unicode raros a espacio estándar.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto con espacios normalizados.
    """
    espacios = [
        "\u00a0", "\u2009", "\u200a", "\u202f", "\u205f", "\u3000",
        "\u2002", "\u2003", "\u2004", "\u2005", "\u2006", "\u2007",
        "\u2008", "\u200b",
    ]
    for e in espacios:
        texto = texto.replace(e, " ")
    return texto


def normalizar_elipsis(texto: str) -> str:
    """
    Convierte elipsis Unicode en tres puntos.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto con elipsis normalizadas.
    """
    return texto.replace("\u2026", "...")


def eliminar_markdown(texto: str) -> str:
    """
    Elimina markdown residual: negritas, cursivas, listas, encabezados, código.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto sin markdown.
    """
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.+?)\*", r"\1", texto)
    texto = re.sub(r"__(.+?)__", r"\1", texto)
    texto = re.sub(r"_(.+?)_", r"\1", texto)
    texto = re.sub(r"^#{1,6}\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^[-*+]\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\d+\.\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\s*[-*+]\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", texto)
    texto = re.sub(r"~~(.+?)~~", r"\1", texto)
    texto = re.sub(r"\[\[?(.+?)\]\]?", r"\1", texto)
    return texto


def corregir_elisiones(texto: str) -> str:
    """
    Corrige elisiones: 'y' antes de 'i'/'í' pasa a 'e', 'o' antes de 'o'/'ó' pasa a 'u'.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto con elisiones corregidas.
    """
    texto = re.sub(r"\by\s+([ií])\b", r"e \1", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bo\s+([oó])\b", r"u \1", texto, flags=re.IGNORECASE)
    return texto


def corregir_puntuacion(texto: str) -> str:
    """
    Corrige espacios antes de signos de puntuación.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto con puntuación corregida.
    """
    texto = re.sub(r"\s+([,;:!?])", r"\1", texto)
    texto = re.sub(r"([,;:!?])(?!\s)", r"\1 ", texto)
    texto = re.sub(r"\(\s+", "(", texto)
    texto = re.sub(r"\s+\)", ")", texto)
    return texto


def corregir_espaciado(texto: str) -> str:
    """
    Normaliza múltiples espacios a uno solo.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto con espaciado normalizado.
    """
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def clean_text(texto: str) -> str:
    """
    Limpia un texto aplicando todas las normalizaciones.

    Args:
        texto: Texto de entrada.

    Returns:
        Texto completamente limpio y normalizado.
    """
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
# Funciones de análisis lingüístico
# ---------------------------------------------------------------------------
def extraer_oraciones(texto: str) -> List[str]:
    """
    Extrae las oraciones de un texto, preservando el orden.

    Args:
        texto: Texto de entrada.

    Returns:
        Lista de oraciones limpias.
    """
    oraciones = re.split(r"(?<=[.!?])\s+", texto)
    return [o.strip() for o in oraciones if o.strip()]


def extraer_parrafos(texto: str) -> List[str]:
    """
    Extrae los párrafos de un texto.

    Args:
        texto: Texto de entrada.

    Returns:
        Lista de párrafos limpios.
    """
    parrafos = re.split(r"\n\s*\n", texto)
    return [p.strip() for p in parrafos if p.strip()]


def contar_palabras(texto: str) -> int:
    """
    Cuenta palabras normalizadas.

    Args:
        texto: Texto de entrada.

    Returns:
        Número de palabras.
    """
    return len(texto.split())


def contar_silabas_espanol(palabra: str) -> int:
    """
    Aproxima el número de sílabas de una palabra en español.

    Args:
        palabra: Palabra a analizar.

    Returns:
        Número aproximado de sílabas.
    """
    palabra = palabra.lower().strip()
    if not palabra:
        return 0

    vocales = "aeiouáéíóúü"
    diptongos = ["ai", "ei", "oi", "au", "eu", "iu", "ui"]
    hiatos = ["aá", "eé", "ií", "oó", "uú"]

    silabas = 0
    i = 0
    while i < len(palabra):
        if palabra[i] in vocales:
            if i + 1 < len(palabra):
                par = palabra[i:i + 2]
                if par in diptongos:
                    silabas += 1
                    i += 2
                    continue
                if par in hiatos:
                    silabas += 2
                    i += 2
                    continue
            silabas += 1
        i += 1

    return max(1, silabas)


def calcular_flesch(texto: str) -> float:
    """
    Calcula el índice de legibilidad Flesch en español.

    Args:
        texto: Texto de entrada.

    Returns:
        Índice Flesch (0-100, mayor = más fácil).
    """
    oraciones = extraer_oraciones(texto)
    palabras = texto.split()
    if not oraciones or not palabras:
        return 0.0

    total_silabas = sum(contar_silabas_espanol(p) for p in palabras)
    palabras_por_oracion = len(palabras) / len(oraciones)
    silabas_por_palabra = total_silabas / len(palabras)

    flesch = 206.835 - 1.015 * palabras_por_oracion - 84.6 * silabas_por_palabra
    return max(0.0, min(100.0, flesch))


def calcular_ttr(texto: str) -> float:
    """
    Calcula el Type-Token Ratio (variedad léxica).

    Args:
        texto: Texto de entrada.

    Returns:
        TTR entre 0 y 1.
    """
    palabras = re.findall(r"\w+", texto.lower())
    if not palabras:
        return 0.0
    return len(set(palabras)) / len(palabras)


def calcular_burstiness(texto: str) -> float:
    """
    Calcula el coeficiente de variación de longitudes de oraciones.

    Args:
        texto: Texto de entrada.

    Returns:
        Coeficiente de variación (mayor = más variado).
    """
    oraciones = extraer_oraciones(texto)
    if len(oraciones) < 2:
        return 0.0
    longitudes = [len(o.split()) for o in oraciones]
    media = sum(longitudes) / len(longitudes)
    if media == 0:
        return 0.0
    varianza = sum((l - media) ** 2 for l in longitudes) / len(longitudes)
    return math.sqrt(varianza) / media


def calcular_perplexity_proxy(texto: str) -> float:
    """
    Proxy de perplexidad basado en rareza léxica.

    Args:
        texto: Texto de entrada.

    Returns:
        Valor proxy de perplexidad.
    """
    palabras = re.findall(r"\w+", texto.lower())
    if not palabras:
        return 0.0

    comunes = {
        "el", "la", "los", "las", "un", "una", "de", "del", "al", "en",
        "y", "o", "que", "es", "son", "ser", "estar", "hay", "con", "por",
        "para", "se", "su", "sus", "lo", "le", "les", "no", "si", "como",
        "pero", "muy", "más", "menos", "también", "aún", "ya", "este",
        "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    }

    raras = [p for p in palabras if p not in comunes]
    return len(raras) / len(palabras)


def detectar_voz_pasiva(oracion: str) -> bool:
    """
    Detecta si una oración está en voz pasiva.

    Args:
        oracion: Oración a analizar.

    Returns:
        True si es pasiva.
    """
    patrones = [
        r"\bes\s+\w+ado\b", r"\bes\s+\w+ida\b", r"\bes\s+\w+os\b",
        r"\bes\s+\w+as\b", r"\bfue\s+\w+ado\b", r"\bfue\s+\w+ida\b",
        r"\bson\s+\w+ados\b", r"\bson\s+\w+idas\b", r"\bfueron\s+\w+ados\b",
        r"\bfueron\s+\w+idas\b", r"\bha\s+sido\s+\w+ado\b",
        r"\bhan\s+sido\s+\w+ado\b", r"\bser\s+\w+ado\b",
    ]
    oracion_lower = oracion.lower()
    return any(re.search(p, oracion_lower) for p in patrones)


def detectar_gerundios_remate(oracion: str) -> bool:
    """
    Detecta gerundios de remate tras coma.

    Args:
        oracion: Oración a analizar.

    Returns:
        True si tiene gerundio de remate.
    """
    return bool(re.search(r",\s+\w+ando\b", oracion)) or bool(
        re.search(r",\s+\w+endo\b", oracion)
    )


def detectar_nominalizaciones(texto: str) -> List[str]:
    """
    Detecta nominalizaciones excesivas.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de nominalizaciones encontradas.
    """
    sufijos = ["ción", "miento", "miento", "ancia", "encia", "idad", "ura"]
    palabras = re.findall(r"\w+", texto.lower())
    return [p for p in palabras if any(p.endswith(s) for s in sufijos) and len(p) > 8]


def detectar_cliches(texto: str) -> List[str]:
    """
    Detecta clichés típicos de IA.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de clichés encontrados.
    """
    cliches = [
        "en el mundo actual", "en la era digital", "en la actualidad",
        "en este sentido", "en definitiva", "en resumen", "en conclusión",
        "es importante destacar", "cabe mencionar", "vale la pena",
        "juega un papel crucial", "desempeña un rol fundamental",
        "no cabe duda", "sin lugar a dudas", "resulta evidente",
    ]
    texto_lower = texto.lower()
    return [c for c in cliches if c in texto_lower]


def detectar_redundancias(texto: str) -> List[str]:
    """
    Detecta redundancias léxicas.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de redundancias encontradas.
    """
    redundancias = [
        "subir arriba", "bajar abajo", "salir fuera", "entrar dentro",
        "repetir de nuevo", "volver a repetir", "terminar definitivo",
        "completamente lleno", "totalmente vacío", "libre gratis",
        "previo anterior", "posterior siguiente", "final último",
    ]
    texto_lower = texto.lower()
    return [r for r in redundancias if r in texto_lower]


def detectar_repeticion_letrica(texto: str) -> Dict[str, int]:
    """
    Detecta palabras repetidas al inicio de oraciones.

    Args:
        texto: Texto a analizar.

    Returns:
        Diccionario palabra -> conteo.
    """
    oraciones = extraer_oraciones(texto)
    inicios = [o.split()[0].lower() for o in oraciones if o.split()]
    return {p: c for p, c in Counter(inicios).items() if c > 3 and len(p) > 2}


def detectar_repeticion_sintactica(texto: str) -> List[str]:
    """
    Detecta estructuras sintácticas repetidas.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de problemas sintácticos.
    """
    oraciones = extraer_oraciones(texto)
    problemas = []
    estructuras = []

    for o in oraciones:
        palabras = o.split()
        if len(palabras) >= 3:
            estructura = f"{palabras[0]}_{palabras[1]}_{palabras[-1]}"
            estructuras.append(estructura)

    conteo = Counter(estructuras)
    for e, c in conteo.items():
        if c >= 3:
            problemas.append(f"Estructura '{e}' repetida {c} veces")

    return problemas


def detectar_paralelismo(texto: str) -> bool:
    """
    Detecta paralelismos simétricos excesivos.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay paralelismo problemático.
    """
    oraciones = extraer_oraciones(texto)
    for i in range(len(oraciones) - 2):
        l1 = len(oraciones[i].split())
        l2 = len(oraciones[i + 1].split())
        l3 = len(oraciones[i + 2].split())
        if abs(l1 - l2) < 2 and abs(l2 - l3) < 2:
            return True
    return False


def detectar_enumeracion(texto: str) -> bool:
    """
    Detecta enumeraciones de tres elementos.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay enumeración de tres.
    """
    return bool(re.search(r"\b\w+,\s+\w+\s+y\s+\w+\b", texto))


def detectar_aposicion(texto: str) -> bool:
    """
    Detecta uso excesivo de aposiciones.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay aposiciones problemáticas.
    """
    return len(re.findall(r",\s+[A-Z][a-z]+,\s+", texto)) > 2


def detectar_inciso(texto: str) -> bool:
    """
    Detecta uso excesivo de incisos entre comas.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay incisos problemáticos.
    """
    return len(re.findall(r",\s+\w+\s+\w+\s+,", texto)) > 3


def detectar_subordinada(texto: str) -> bool:
    """
    Detecta subordinadas excesivamente largas.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay subordinadas problemáticas.
    """
    oraciones = extraer_oraciones(texto)
    for o in oraciones:
        if len(o.split()) > 35 and o.count("que") > 2:
            return True
    return False


def detectar_coordinada(texto: str) -> bool:
    """
    Detecta coordinadas excesivas.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay coordinadas problemáticas.
    """
    oraciones = extraer_oraciones(texto)
    for o in oraciones:
        if o.count(" y ") > 3 or o.count(" o ") > 3:
            return True
    return False


def detectar_yuxtapuesta(texto: str) -> bool:
    """
    Detecta yuxtaposiciones excesivas.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay yuxtaposiciones problemáticas.
    """
    return len(re.findall(r";\s+[a-z]", texto)) > 4


def detectar_periffrasis(texto: str) -> List[str]:
    """
    Detecta perífrasis verbales excesivas.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de perífrasis encontradas.
    """
    patrones = [
        r"va\s+a\s+\w+", r"está\s+\w+ando", r"tiene\s+que\s+\w+",
        r"puede\s+\w+", r"debe\s+\w+", r"suele\s+\w+",
    ]
    texto_lower = texto.lower()
    encontradas = []
    for p in patrones:
        encontradas.extend(re.findall(p, texto_lower))
    return encontradas


def detectar_locuciones(texto: str) -> List[str]:
    """
    Detecta locuciones típicas de IA.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de locuciones encontradas.
    """
    locuciones = [
        "en cuanto a", "respecto a", "con respecto a", "por lo que",
        "de modo que", "de manera que", "en tal medida que",
    ]
    texto_lower = texto.lower()
    return [l for l in locuciones if l in texto_lower]


def detectar_modismos(texto: str) -> List[str]:
    """
    Detecta modismos que pueden delatar IA.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de modismos encontrados.
    """
    modismos = [
        "dar a entender", "poner de manifiesto", "hacer hincapié",
        "tomar en cuenta", "cobrar relevancia", "adquirir importancia",
    ]
    texto_lower = texto.lower()
    return [m for m in modismos if m in texto_lower]


def detectar_tecnicismos(texto: str) -> List[str]:
    """
    Detecta tecnicismos innecesarios.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de tecnicismos encontrados.
    """
    tecnicismos = [
        "paradigma", "sinergia", "holístico", "proactivo", "resiliencia",
        "empoderamiento", "disruptivo", "innovador", "estratégico",
    ]
    texto_lower = texto.lower()
    return [t for t in tecnicismos if t in texto_lower]


def detectar_extranjerismos(texto: str) -> List[str]:
    """
    Detecta extranjerismos innecesarios.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de extranjerismos encontrados.
    """
    extranjerismos = [
        "feedback", "engagement", "insight", "benchmark", "roadmap",
        "stakeholder", "workflow", "deadline", "teamwork", "brainstorming",
    ]
    texto_lower = texto.lower()
    return [e for e in extranjerismos if e in texto_lower]


def detectar_queismo(texto: str) -> bool:
    """
    Detecta queísmo.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay queísmo.
    """
    return bool(re.search(r"\bpienso\s+que\b", texto.lower())) or bool(
        re.search(r"\bcreo\s+que\b", texto.lower())
    )


def detectar_dequeismo(texto: str) -> bool:
    """
    Detecta dequeísmo.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay dequeísmo.
    """
    return bool(re.search(r"\bde\s+que\b", texto.lower()))


def detectar_leismo(texto: str) -> bool:
    """
    Detecta leísmo.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay leísmo.
    """
    return bool(re.search(r"\ble\s+vi\b", texto.lower())) or bool(
        re.search(r"\ble\s+oí\b", texto.lower())
    )


def detectar_laismo(texto: str) -> bool:
    """
    Detecta laísmo.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay laísmo.
    """
    return bool(re.search(r"\bla\s+di\b", texto.lower())) or bool(
        re.search(r"\bla\s+avisé\b", texto.lower())
    )


def detectar_loismo(texto: str) -> bool:
    """
    Detecta loísmo.

    Args:
        texto: Texto a analizar.

    Returns:
        True si hay loísmo.
    """
    return bool(re.search(r"\blo\s+compré\b", texto.lower()))


def detectar_concordancia(texto: str) -> List[str]:
    """
    Detecta problemas de concordancia.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de problemas de concordancia.
    """
    problemas = []
    oraciones = extraer_oraciones(texto)
    for o in oraciones:
        if re.search(r"\b(?:la|las)\s+\w+(?:s)?\s+(?:es|son)\s+\w+o\b", o.lower()):
            problemas.append(f"Posible discordancia: {o[:50]}")
    return problemas[:5]


def detectar_regimen(texto: str) -> List[str]:
    """
    Detecta problemas de régimen preposicional.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de problemas de régimen.
    """
    problemas = []
    oraciones = extraer_oraciones(texto)
    verbos_requieren = {
        "asistir": "a", "contribuir": "a", "cumplir": "con",
        "insistir": "en", "consistir": "en", "depender": "de",
    }
    for o in oraciones:
        for verbo, prep in verbos_requieren.items():
            if verbo in o.lower() and f"{verbo} {prep}" not in o.lower():
                problemas.append(f"Régimen: '{verbo}' requiere '{prep}'")
    return problemas[:5]


def detectar_colocacion(texto: str) -> List[str]:
    """
    Detecta colocaciones problemáticas.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de colocaciones problemáticas.
    """
    problematicas = [
        ("hacer", "decisión"), ("hacer", "esfuerzo"),
        ("realizar", "una pregunta"), ("dar", "una respuesta"),
    ]
    encontradas = []
    texto_lower = texto.lower()
    for verbo, sust in problematicas:
        if f"{verbo} {sust}" in texto_lower:
            encontradas.append(f"{verbo} {sust}")
    return encontradas


def detectar_derivacion(texto: str) -> List[str]:
    """
    Detecta derivaciones excesivas.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de derivaciones.
    """
    sufijos = ["ización", "ificación", "amiento", "imiento", "encia"]
    palabras = re.findall(r"\w+", texto.lower())
    return [p for p in palabras if any(p.endswith(s) for s in sufijos)][:10]


def detectar_composicion(texto: str) -> List[str]:
    """
    Detecta palabras compuestas.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de compuestas.
    """
    compuestas = [
        "paraguas", "sacapuntas", "limpiaparabrisas", "abrelatas",
        "rompecabezas", "guardapolvo", "sacacorchos",
    ]
    texto_lower = texto.lower()
    return [c for c in compuestas if c in texto_lower]


def detectar_siglas(texto: str) -> List[str]:
    """
    Detecta siglas.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de siglas.
    """
    return re.findall(r"\b[A-Z]{2,}\b", texto)


def detectar_acronimos(texto: str) -> List[str]:
    """
    Detecta acrónimos.

    Args:
        texto: Texto a analizar.

    Returns:
        Lista de acrónimos.
    """
    acronimos = ["UNESCO", "OTAN", "ONU", "FMI", "BID", "CEPAL", "OEI"]
    return [a for a in acronimos if a in texto]


def analizar_texto_completo(texto: str) -> Dict[str, Any]:
    """
    Realiza un análisis lingüístico completo del texto.

    Args:
        texto: Texto a analizar.

    Returns:
        Diccionario con todas las métricas.
    """
    return {
        "palabras": contar_palabras(texto),
        "oraciones": len(extraer_oraciones(texto)),
        "parrafos": len(extraer_parrafos(texto)),
        "flesch": calcular_flesch(texto),
        "ttr": calcular_ttr(texto),
        "burstiness": calcular_burstiness(texto),
        "perplexity_proxy": calcular_perplexity_proxy(texto),
        "cliches": detectar_cliches(texto),
        "redundancias": detectar_redundancias(texto),
        "nominalizaciones": detectar_nominalizaciones(texto),
        "repeticion_letrica": detectar_repeticion_letrica(texto),
        "repeticion_sintactica": detectar_repeticion_sintactica(texto),
        "paralelismo": detectar_paralelismo(texto),
        "enumeracion": detectar_enumeracion(texto),
        "subordinada": detectar_subordinada(texto),
        "coordinada": detectar_coordinada(texto),
        "yuxtapuesta": detectar_yuxtapuesta(texto),
        "periffrasis": detectar_periffrasis(texto),
        "locuciones": detectar_locuciones(texto),
        "modismos": detectar_modismos(texto),
        "tecnicismos": detectar_tecnicismos(texto),
        "extranjerismos": detectar_extranjerismos(texto),
        "queismo": detectar_queismo(texto),
        "dequeismo": detectar_dequeismo(texto),
        "leismo": detectar_leismo(texto),
        "laismo": detectar_laismo(texto),
        "loismo": detectar_loismo(texto),
        "concordancia": detectar_concordancia(texto),
        "regimen": detectar_regimen(texto),
        "colocacion": detectar_colocacion(texto),
        "derivacion": detectar_derivacion(texto),
        "composicion": detectar_composicion(texto),
        "siglas": detectar_siglas(texto),
        "acronimos": detectar_acronimos(texto),
    }


# ---------------------------------------------------------------------------
# Detección de modelos reales
# ---------------------------------------------------------------------------
def detectar_modelos() -> Dict[str, List[str]]:
    """
    Detecta modelos disponibles haciendo GET a /models de cada proveedor.

    Returns:
        Diccionario proveedor -> lista de modelos de texto.
    """
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

            if modelos_filtrados:
                disponibles[prov] = modelos_filtrados[:15]
            else:
                disponibles[prov] = list(MODELOS_FIJOS[prov])

        except Exception as e:
            logger.warning(f"Error detectando modelos de {prov}: {e}")
            disponibles[prov] = list(MODELOS_FIJOS[prov])

    return disponibles


def construir_opciones_y_default(
    disponibles: Dict[str, List[str]],
) -> Tuple[List[str], List[str]]:
    """
    Construye la lista de opciones y el default para el multiselect,
    garantizando que el default sea subconjunto de options.

    Args:
        disponibles: Diccionario de modelos detectados.

    Returns:
        Tupla (options, default).
    """
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
# Sistema de pausados
# ---------------------------------------------------------------------------
PAUSAS: Dict[str, Dict[str, float]] = {
    prov: {"cuota": 0.0, "lento": 0.0, "diaria": 0.0}
    for prov in ORDEN_FALLBACK
}

_lock_pausas = threading.Lock()


def registrar_pausa(proveedor: str, tipo: str) -> None:
    """Registra una pausa para un proveedor."""
    with _lock_pausas:
        if proveedor in PAUSAS and tipo in PAUSAS[proveedor]:
            PAUSAS[proveedor][tipo] = time.time()
            logger.info(f"Pausa {tipo} registrada para {proveedor}")


def esta_pausado(proveedor: str) -> bool:
    """Verifica si un proveedor está pausado."""
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
    """Maneja errores de API y registra pausas según el tipo."""
    error_lower = error.lower()
    if "429" in error_lower or "rate limit" in error_lower or "quota" in error_lower:
        registrar_pausa(proveedor, "cuota")
    elif "timeout" in error_lower or "slow" in error_lower:
        registrar_pausa(proveedor, "lento")
    elif "daily" in error_lower or "day" in error_lower:
        registrar_pausa(proveedor, "diaria")


# ---------------------------------------------------------------------------
# Funciones de API con retry y backoff
# ---------------------------------------------------------------------------
def con_retry(func, *args, **kwargs):
    """
    Ejecuta una función con reintentos y backoff exponencial.

    Args:
        func: Función a ejecutar.
        *args: Argumentos posicionales.
        **kwargs: Argumentos nombrados.

    Returns:
        Resultado de la función.

    Raises:
        Exception: Si falla tras todos los reintentos.
    """
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
    """Llama a Google Gemini usando el SDK oficial."""
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
# Extracción de datos clave
# ---------------------------------------------------------------------------
def extraer_datos_clave(texto: str) -> List[str]:
    """
    Extrae fechas, cifras, nombres propios y citas del texto.

    Args:
        texto: Texto de entrada.

    Returns:
        Lista de datos clave únicos.
    """
    datos: List[str] = []

    fechas = re.findall(
        r"\b\d{1,2}\s+de\s+[a-záéíóúñ]+\s+de\s+\d{4}\b",
        texto,
        re.IGNORECASE,
    )
    datos.extend(fechas)

    años = re.findall(r"\b\d{4}\b", texto)
    datos.extend(años)

    cifras = re.findall(
        r"\b\d+[.,]?\d*\s*(?:mil|millones|billones|%)?\b",
        texto,
        re.IGNORECASE,
    )
    datos.extend(cifras)

    nombres = re.findall(
        r"\b[A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)+\b",
        texto,
    )
    datos.extend(nombres[:15])

    citas = re.findall(r"[\"']([^\"']{10,80})[\"']", texto)
    datos.extend(citas[:5])

    return list(dict.fromkeys(datos))


def verificar_datos_clave(original: str, humanizado: str, datos: List[str]) -> List[str]:
    """
    Verifica que los datos clave no se pierdan al humanizar.

    Args:
        original: Texto original.
        humanizado: Texto humanizado.
        datos: Lista de datos clave.

    Returns:
        Lista de datos perdidos.
    """
    perdidos = []
    for d in datos:
        if d not in humanizado:
            perdidos.append(d)
    return perdidos


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
    "obviamente", "naturalmente", "lógicamente", "en la era digital",
    "en el contexto de", "en el marco de", "en relación con",
    "en cuanto a", "respecto a", "con respecto a", "por lo que",
    "de modo que", "de manera que", "en tal medida que",
    "dar a entender", "poner de manifiesto", "hacer hincapié",
    "tomar en cuenta", "cobrar relevancia", "adquirir importancia",
    "en la sociedad contemporánea", "en la sociedad actual",
    "en el siglo XXI", "en el mundo moderno", "en el mundo de hoy",
    "en la era de la información", "en la era de la tecnología",
    "en la era de la inteligencia artificial", "en la era digital",
    "en el mundo globalizado", "en el mundo interconectado",
    "en el mundo hiperconectado", "en la era de la conectividad",
    "en la era de la información", "en la era del conocimiento",
    "en la era del dato", "en la era de la inteligencia",
    "en la era de la automatización", "en la era de la digitalización",
    "en la era de la transformación", "en la era de la innovación",
    "en la era de la disrupción", "en la era de la revolución",
    "en la era de la evolución", "en la era de la adaptación",
    "en la era de la resiliencia", "en la era de la sostenibilidad",
    "en la era de la responsabilidad", "en la era de la ética",
    "en la era de la transparencia", "en la era de la confianza",
    "en la era de la seguridad", "en la era de la privacidad",
    "en la era de la protección", "en la era de la defensa",
    "en la era de la vigilancia", "en la era de la monitorización",
    "en la era de la observación", "en la era de la atención",
    "en la era de la concentración", "en la era de la distracción",
    "en la era de la fragmentación", "en la era de la dispersión",
    "en la era de la multiplicidad", "en la era de la variedad",
    "en la era de la diversidad", "en la era de la pluralidad",
    "en la era de la complejidad", "en la era de la simplicidad",
    "en la era de la claridad", "en la era de la opacidad",
    "en la era de la transparencia", "en la era de la opacidad",
    "en la era de la luz", "en la era de la sombra",
    "en la era del día", "en la era de la noche",
    "en la era del amanecer", "en la era del atardecer",
    "en la era del mediodía", "en la era de la medianoche",
    "en la era de la mañana", "en la era de la tarde",
    "en la era de la noche", "en la era de la madrugada",
    "en la era del alba", "en la era del crepúsculo",
    "en la era del ocaso", "en la era de la aurora",
    "en la era de la luz", "en la era de la sombra",
    "en la era del día", "en la era de la noche",
    "en la era del amanecer", "en la era del atardecer",
    "en la era del mediodía", "en la era de la medianoche",
    "en la era de la mañana", "en la era de la tarde",
    "en la era de la noche", "en la era de la madrugada",
    "en la era del alba", "en la era del crepúsculo",
    "en la era del ocaso", "en la era de la aurora",
]

CONECTORES_MANUAL = [
    "asimismo", "no obstante", "por lo tanto", "sin embargo", "además",
    "en consecuencia", "por consiguiente", "en efecto", "de hecho",
    "por otro lado", "en este sentido", "en definitiva",
]


def auditar_texto(texto: str) -> List[str]:
    """
    Audita el texto con 12+ detectores de problemas de humanización.

    Args:
        texto: Texto a auditar.

    Returns:
        Lista de problemas detectados.
    """
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

    if detectar_subordinada(texto):
        problemas.append("Subordinadas excesivamente largas")

    if detectar_coordinada(texto):
        problemas.append("Coordinadas excesivas")

    if detectar_yuxtapuesta(texto):
        problemas.append("Yuxtaposiciones excesivas")

    if detectar_queismo(texto):
        problemas.append("Queísmo detectado")

    if detectar_dequeismo(texto):
        problemas.append("Dequeísmo detectado")

    if detectar_nominalizaciones(texto):
        problemas.append("Nominalizaciones excesivas")

    if detectar_cliches(texto):
        problemas.append(f"Clichés de IA ({len(detectar_cliches(texto))} encontradas)")

    if detectar_redundancias(texto):
        problemas.append(f"Redundancias ({len(detectar_redundancias(texto))} encontradas)")

    if detectar_tecnicismos(texto):
        problemas.append(f"Tecnicismos innecesarios ({len(detectar_tecnicismos(texto))})")

    if detectar_extranjerismos(texto):
        problemas.append(f"Extranjerismos ({len(detectar_extranjerismos(texto))})")

    return problemas


def calcular_ritmo(texto: str) -> float:
    """Calcula el coeficiente de variación (CV) de las longitudes de oraciones."""
    return calcular_burstiness(texto)


# ---------------------------------------------------------------------------
# Generación de gráficos SVG
# ---------------------------------------------------------------------------
def generar_svg_ritmo(longitudes_orig: List[int], longitudes_fin: List[int]) -> str:
    """
    Genera un gráfico SVG de barras comparando ritmo original vs humanizado.

    Args:
        longitudes_orig: Longitudes de oraciones originales.
        longitudes_fin: Longitudes de oraciones humanizadas.

    Returns:
        String con SVG.
    """
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
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'height="{alto_max + 40}" viewBox="0 0 {ancho_total} {alto_max + 40}">'
        f'<text x="0" y="15" font-size="11" fill="#A6ACB6" '
        f'font-family="sans-serif">Gris: original | Cyan: humanizado</text>'
        f'<g transform="translate(5, 25)">{barras}</g>'
        f'<line x1="0" y1="{alto_max + 25}" x2="{ancho_total}" '
        f'y2="{alto_max + 25}" stroke="#2A2F38" stroke-width="1" />'
        f'</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# Pasos del pipeline
# ---------------------------------------------------------------------------
def procesar_bloque(
    texto: str,
    paso: str,
    proveedor: str,
    modelo: str,
    instruccion_medida: str = "",
) -> dict:
    """Procesa un bloque del pipeline según el paso indicado."""
    prompts = {
        "es_en": (PROMPT_EN, TEMPERATURA_INTERMEDIA),
        "en_es": (PROMPT_ES, TEMPERATURA_INTERMEDIA),
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

    if paso == "final":
        system_prompt = con_muestra(
            system_base, PROMPT_FINAL_REGLAS, MUESTRA_ESTILO_TESIS, instruccion_medida
        )
    else:
        system_prompt = system_base

    return llamar_proveedor(proveedor, modelo, system_prompt, texto, temperature)


def revisar_bloque(
    texto: str,
    proveedor: str,
    modelo: str,
    problemas: List[str],
    longitud_original: int,
    datos_clave: List[str],
) -> dict:
    """Revisa y corrige un bloque hasta 3 rondas."""
    if not problemas:
        return {
            "texto": texto,
            "proveedor_usado": proveedor,
            "modelo_usado": modelo,
            "exito": True,
            "error": None,
        }

    texto_actual = texto

    for ronda in range(1, MAX_RONDAS_CORRECCION + 1):
        lista = "\n".join(f"- {p}" for p in problemas)
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

        texto_actual = clean_text(res["texto"])
        nuevos_problemas = auditar_texto(texto_actual)

        if not nuevos_problemas:
            break

        problemas = nuevos_problemas

    return {
        "texto": texto_actual,
        "proveedor_usado": proveedor,
        "modelo_usado": modelo,
        "exito": True,
        "error": None,
    }


def extraer_oraciones_problema(texto: str) -> List[str]:
    """Devuelve las oraciones que violan reglas de detección."""
    oraciones = extraer_oraciones(texto)
    problemas: List[str] = []
    frases_vetadas = [
        "en conclusión", "es fundamental", "cabe destacar", "juega un papel",
        "se ha convertido en", "en el ámbito de", "mediante", "sin embargo",
    ]
    for o in oraciones:
        n = len(o.split())
        primera = o.split()[0] if o.split() else ""
        baja = o.lower()
        if (
            n > 30
            or n < 5
            or primera in ["El", "La", "Los", "Las", "Se"]
            or any(f in baja for f in frases_vetadas)
        ):
            problemas.append(o)
    return problemas


def reescribir_con_detector(texto: str, proveedor: str, modelo: str) -> dict:
    """Reescribe oraciones problemáticas con cambio sintáctico total."""
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
    """Ajusta el texto si hay detectores externos configurados."""
    gptzero_key = leer_secreto("GPTZERO_API_KEY")
    copyleaks_key = leer_secreto("COPYLEAKS_API_KEY")

    if not gptzero_key and not copyleaks_key:
        return {
            "texto": texto,
            "proveedor_usado": proveedor,
            "modelo_usado": modelo,
            "exito": True,
            "error": None,
        }

    texto_actual = texto

    for ronda in range(1, MAX_RONDAS_DETECTORES + 1):
        score_ia = 0.0

        if gptzero_key:
            try:
                headers = {"X-API-KEY": gptzero_key, "Content-Type": "application/json"}
                payload = {"document": texto_actual}
                response = requests.post(
                    "https://api.gptzero.me/v2/predict/text",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    docs = data.get("documents", [])
                    if docs:
                        score_ia = docs[0].get("average_generated_prob", 0.0)
            except Exception as e:
                logger.warning(f"GPTZero error: {e}")

        if score_ia > 0.30:
            res = reescribir_con_detector(texto_actual, proveedor, modelo)
            if res["exito"]:
                texto_actual = clean_text(res["texto"])
            else:
                break
        else:
            break

    return {
        "texto": texto_actual,
        "proveedor_usado": proveedor,
        "modelo_usado": modelo,
        "exito": True,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Plan y bloques
# ---------------------------------------------------------------------------
def armar_plan(
    proveedores_otros: List[str],
    modo_profundo: bool,
    romper_estructura: bool,
    correccion_auto: bool,
) -> List[Dict[str, str]]:
    """Arma el plan de pasos con diversidad de proveedores."""
    plan: List[Dict[str, str]] = []
    idx = 0

    if not proveedores_otros:
        proveedores_otros = ["groq", "openrouter", "nvidia", "deepseek", "gemini"]

    if modo_profundo:
        plan.append({
            "paso": "retro",
            "proveedor": proveedores_otros[idx % len(proveedores_otros)],
        })
        idx += 1

    if romper_estructura:
        plan.append({
            "paso": "estructura",
            "proveedor": proveedores_otros[idx % len(proveedores_otros)],
        })
        idx += 1

    plan.append({"paso": "final", "proveedor": "groq"})

    if correccion_auto:
        plan.append({
            "paso": "correccion",
            "proveedor": proveedores_otros[idx % len(proveedores_otros)],
        })
        idx += 1
        plan.append({
            "paso": "detector",
            "proveedor": proveedores_otros[idx % len(proveedores_otros)],
        })

    return plan


def dividir_en_bloques(texto: str, tamano: int = TAMANO_BLOQUE) -> List[str]:
    """Divide el texto en bloques de aproximadamente tamano palabras."""
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


def procesar_bloque_individual(
    bloque: str,
    plan: List[Dict[str, str]],
    modelo_final: str,
    instruccion_medida: str,
    datos_clave: List[str],
) -> dict:
    """Procesa un bloque individual siguiendo el plan."""
    texto_actual = bloque
    log: List[str] = []

    for etapa in plan:
        paso = etapa["paso"]
        proveedor = etapa["proveedor"]
        modelo = MODELO_POR_PROVEEDOR.get(proveedor, MODELO_POR_PROVEEDOR["groq"])

        if paso in ("retro", "estructura"):
            res = procesar_bloque(
                texto_actual, paso, proveedor, modelo, instruccion_medida
            )
        elif paso == "final":
            res = procesar_bloque(
                texto_actual, "final", proveedor, modelo_final, instruccion_medida
            )
        elif paso == "correccion":
            problemas = auditar_texto(texto_actual)
            res = revisar_bloque(
                texto_actual, proveedor, modelo, problemas,
                contar_palabras(texto_actual), datos_clave,
            )
        elif paso == "detector":
            res = reescribir_con_detector(texto_actual, proveedor, modelo)
        else:
            continue

        if not res["exito"]:
            return {
                "texto": texto_actual,
                "log": log,
                "exito": False,
                "error": res["error"],
            }

        texto_actual = clean_text(res["texto"])
        log.append(f"✓ {paso}: {res['proveedor_usado']}")

    return {"texto": texto_actual, "log": log, "exito": True, "error": None}


# ---------------------------------------------------------------------------
# Pipeline completo
# ---------------------------------------------------------------------------
def procesar(texto: str, config: dict, estado: dict) -> dict:
    """Ejecuta el pipeline completo de humanización."""
    log_pasos: List[str] = []
    inicio_total = time.time()

    proveedores_otros = config.get("proveedores_otros") or [
        "groq", "openrouter", "nvidia", "deepseek", "gemini"
    ]

    datos_clave = extraer_datos_clave(texto)
    num_parrafos = len(extraer_parrafos(texto))
    num_palabras = contar_palabras(texto)
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
                    bloque,
                    plan,
                    config.get("modelo_final", MODELO_POR_PROVEEDOR["groq"]),
                    instruccion_medida,
                    datos_clave,
                )
                futures[future] = i

            resultados: List[Optional[dict]] = [None] * len(bloques)
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
                estado["progreso"] = min(
                    (idx + 1) / len(bloques), 0.95
                )

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
            paso = etapa["paso"]
            proveedor = etapa["proveedor"]
            modelo = MODELO_POR_PROVEEDOR.get(proveedor, MODELO_POR_PROVEEDOR["groq"])

            if paso in ("retro", "estructura"):
                res = procesar_bloque(
                    texto_actual, paso, proveedor, modelo, instruccion_medida
                )
            elif paso == "final":
                res = procesar_bloque(
                    texto_actual, "final", proveedor,
                    config.get("modelo_final", MODELO_POR_PROVEEDOR["groq"]),
                    instruccion_medida,
                )
            elif paso == "correccion":
                problemas = auditar_texto(texto_actual)
                res = revisar_bloque(
                    texto_actual, proveedor, modelo, problemas,
                    num_palabras, datos_clave,
                )
            elif paso == "detector":
                res = reescribir_con_detector(texto_actual, proveedor, modelo)
            else:
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

            texto_actual = clean_text(res["texto"])
            log_pasos.append(f"✓ {paso}: {res['proveedor_usado']}")
            estado["progreso"] = min((i + 1) / len(plan), 0.95)

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
def mostrar_logo(ancho: int = 140) -> None:
    """Muestra el logo de la aplicación."""
    try:
        st.image(LOGO_URL, width=ancho)
    except Exception:
        st.markdown(
            '<div style="font-size:48px;text-align:center;">✍️</div>',
            unsafe_allow_html=True,
        )


def login_screen() -> None:
    """Pantalla de login con diseño completo."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            '<div class="login-container">',
            unsafe_allow_html=True,
        )
        mostrar_logo(LOGO_FONTSIZE)
        st.markdown(
            '<h1 class="login-title">Humanizador Pro</h1>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="login-subtitle">Convierte un texto generado por IA en '
            'prosa natural, con ritmo y voz de persona.</p>',
            unsafe_allow_html=True,
        )

        pwd = st.text_input("Contraseña", type="password", key="login_pwd")
        if st.button("Ingresar", type="primary", use_container_width=True):
            esperada = leer_secreto("APP_PASSWORD") or "manu2026"
            if pwd == esperada:
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
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Cronómetro
# ---------------------------------------------------------------------------
def render_cronometro() -> None:
    """Renderiza el cronómetro en tiempo real con iframe JavaScript."""
    cronometro_html = """
    <div id="crono" class="cronometro-container">Tiempo transcurrido: 0:00</div>
    <script>
    var inicio = Date.now();
    setInterval(function(){
        var t = Math.floor((Date.now() - inicio) / 1000);
        var m = Math.floor(t / 60);
        var s = t % 60;
        var el = document.getElementById("crono");
        if (el) {
            el.textContent = "Tiempo transcurrido: " + m + ":" + (s < 10 ? "0" : "") + s;
        }
    }, 250);
    </script>
    """
    components.html(cronometro_html, height=80)


# ---------------------------------------------------------------------------
# Botón copiar
# ---------------------------------------------------------------------------
def render_boton_copiar(texto: str) -> None:
    """Renderiza el botón de copiar con iframe JavaScript."""
    js_texto = json.dumps(texto)
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
    """Pantalla principal de la aplicación."""
    if not st.session_state.get("logged_in", False):
        login_screen()
        return

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

        disponibles = detectar_modelos()
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
                    st.success(
                        f"✓ {cfg['nombre']}: {MODELO_POR_PROVEEDOR[prov]}"
                    )
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
                st.session_state.texto_entrada = ""
                st.session_state.pop("resultado", None)
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
            lo = [len(o.split()) for o in extraer_oraciones(texto_entrada)]
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
                st.info(
                    "💡 Ejecuta otra pasada con Modo Profundo para reducirlos."
                )
            else:
                st.success("✅ Sin problemas graves en la auditoría.")
        with col_a2:
            st.markdown("### ⏱️ Información del proceso")
            st.metric("Tiempo total", f"{res['duracion']:.1f} segundos")
            st.metric("Pasos ejecutados", len(res.get("log", [])))
            with st.expander("Ver log de proveedores usados"):
                for linea in res.get("log", []):
                    st.write(f'<div class="log-line">{linea}</div>',
                             unsafe_allow_html=True)

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

        estado = {
            "paso": "Iniciando...",
            "progreso": 0.0,
            "res": None,
            "fin": False,
        }

        def worker():
            estado["res"] = procesar(texto_entrada.strip(), config, estado)
            estado["fin"] = True

        hilo = threading.Thread(target=worker, daemon=True)
        hilo.start()

        render_cronometro()

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
            err = (
                resultado.get("error", "Desconocido")
                if resultado
                else "Sin respuesta"
            )
            st.error(f"Error en el pipeline: {err}")
            if resultado and resultado.get("log"):
                with st.expander("Ver log de pasos ejecutados"):
                    for linea in resultado["log"]:
                        st.write(linea)


if __name__ == "__main__":
    main()
