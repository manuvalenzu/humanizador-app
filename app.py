"""
Humanizador pro - Aplicación Streamlit para humanizar textos generados por IA.

Pipeline multi-proveedor con retrotraducción, reestructuración,
auditoría de detectores, reescritura por detector, procesamiento en
bloques paralelos, sistema de pausados y tema oscuro completo.

Autor: Manu
derechos reservados © Humanizador pro, 2026
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
    page_title="Humanizador pro",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/manuvalenzu/humanizador-app",
        "Report a bug": "https://github.com/manuvalenzu/humanizador-app/issues",
        "About": "Humanizador pro — derechos reservados © Humanizador pro, 2026.",
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
# Tema oscuro CSS (manteniendo colores del logo: #22D3E6 y #F2552C)
# ---------------------------------------------------------------------------
CSS_TEMA = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap');

:root {
    --bg: #0F1114;
    --surface: #171A1F;
    --surface-2: #20242B;
    --surface-3: #2A2F38;
    --ink: #ECEEF1;
    --ink-white: #FFFFFF;
    --ink-soft: #A6ACB6;
    --accent: #F2552C;
    --accent-hover: #d94820;
    --human: #22D3E6;
    --success: #22C55E;
    --warning: #F59E0B;
    --error: #EF4444;
    --border: #2A2F38;
}

html, body {
    overflow-x: clip;
    width: 100%;
}

html, body, .stApp {
    background-color: var(--bg);
    color: var(--ink);
    font-family: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    padding-top: 0.75rem !important;
    padding-bottom: 4.5rem !important;
    max-width: 100% !important;
}

.stApp header {
    background-color: var(--surface);
    border-bottom: none;
}

.stSidebar {
    background-color: var(--surface);
    border-right: 1px solid var(--border);
    padding-top: 0.75rem;
}

.stSidebar > div {
    background-color: var(--surface);
}

.stSidebarHeader {
    background-color: var(--surface);
}

h1, h2, h3, h4, h5, h6 {
    color: var(--ink);
    font-family: 'Instrument Sans', sans-serif;
    font-weight: 600;
    overflow-wrap: break-word;
    min-width: 0;
}

.topbar-autor {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    padding: 0 0 0.5rem 0;
    margin-bottom: 0.75rem;
    width: 100%;
}

.topbar-autor__badge {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    color: var(--ink-white);
    background-color: var(--surface);
    border: 1px solid var(--border);
    padding: 0.42rem 1.05rem;
    border-radius: 999px;
}

.logo-box {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    width: 100%;
    margin: 0.25rem auto 1rem auto;
    text-align: center;
}

.logo-box [data-testid="stImage"],
.logo-box [data-testid="stImage"] > div,
.logo-box [data-testid="stImage"] > div > div,
.logo-box [data-testid="stImage"] img {
    margin-left: auto !important;
    margin-right: auto !important;
    display: block !important;
}

.logo-box img {
    border-radius: 18px;
    object-fit: contain;
    max-width: 100%;
}

.hero-brand {
    width: 100%;
    margin-bottom: 1.25rem;
    padding: 1.25rem 1.5rem;
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
}

.hero-brand__title {
    margin: 0 0 0.45rem 0;
    font-family: 'Instrument Sans', sans-serif;
    font-size: clamp(2.65rem, 4.6vw, 3.85rem);
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: -0.025em;
    color: var(--ink-white);
}

.hero-brand__lead {
    margin: 0 0 0.6rem 0;
    font-size: 1.04rem;
    line-height: 1.55;
    color: var(--ink-soft);
    width: 100%;
}

.hero-brand__purpose {
    margin: 0;
    width: 100%;
    font-size: 0.98rem;
    line-height: 1.62;
    color: var(--ink-white);
}

.editor-col-label {
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--ink-white);
    margin: 0 0 0.3rem 0;
}

.editor-col-sub {
    font-size: 0.9rem;
    color: var(--ink-soft);
    margin: 0 0 0.65rem 0;
}

.stButton > button,
.stFormSubmitButton > button {
    background-color: var(--accent);
    color: #111317;
    border: 1px solid var(--accent);
    border-radius: 10px;
    font-weight: 600;
    font-family: 'Instrument Sans', sans-serif;
    padding: 0.55rem 1rem;
    transition: background-color 180ms ease-out, transform 120ms ease-out, border-color 180ms ease-out;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover {
    background-color: var(--accent-hover);
    border-color: var(--accent-hover);
    transform: translateY(-1px);
}

.stButton > button:active,
.stFormSubmitButton > button:active {
    transform: translateY(1px);
}

.stButton > button:focus-visible,
.stFormSubmitButton > button:focus-visible {
    outline: 2px solid var(--human);
    outline-offset: 2px;
}

.stButton > button:disabled {
    background-color: var(--surface-3);
    border-color: var(--border);
    color: var(--ink-soft);
    opacity: 0.55;
    cursor: not-allowed;
    transform: none;
}

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
.stMultiSelect > div > div > div,
.stNumberInput > div > div > input {
    background-color: var(--surface-2);
    color: var(--ink);
    border: 1px solid var(--border);
    border-radius: 10px;
    font-family: 'Instrument Sans', sans-serif;
}

.stTextArea > div > div > textarea {
    height: 440px !important;
    min-height: 440px !important;
    max-height: 440px !important;
    padding: 1.15rem 1.35rem !important;
    font-size: 1.02rem !important;
    line-height: 1.65 !important;
}

.stTextInput > div > div > input:focus-visible,
.stTextArea > div > div > textarea:focus-visible {
    border-color: var(--human);
    outline: 2px solid var(--human);
    outline-offset: -2px;
}

.stMetric {
    background-color: var(--surface);
    padding: 1.1rem 1.25rem;
    border-radius: 10px;
    border: 1px solid var(--border);
}

[data-testid="stMetricValue"] {
    color: var(--human);
    font-family: 'Instrument Sans', sans-serif;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}

[data-testid="stMetricLabel"] {
    color: var(--ink-soft);
    font-family: 'Instrument Sans', sans-serif;
}

[data-testid="stMetricDelta"] {
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}

.stDivider {
    border-color: var(--border);
    margin: 1.5rem 0;
}

.stExpander {
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
}

.stExpander > div {
    background-color: var(--surface);
    color: var(--ink);
}

.stAlert {
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--ink);
}

[data-testid="stAlertContainer"] {
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
}

.stProgress > div > div > div > div {
    background-color: var(--accent);
}

.stProgress > div > div > div {
    background-color: var(--surface-3);
}

.stCaption {
    color: var(--ink-soft);
    font-family: 'Instrument Sans', sans-serif;
}

[data-testid="stDownloadButton"] > button {
    background-color: var(--surface-2);
    color: var(--ink);
    border: 1px solid var(--border);
}

[data-testid="stDownloadButton"] > button:hover {
    background-color: var(--surface-3);
    border-color: var(--human);
}

a {
    color: var(--human);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

a:focus-visible {
    outline: 2px solid var(--human);
    outline-offset: 2px;
}

code, pre {
    background-color: var(--surface-2);
    color: var(--human);
    border-radius: 4px;
    font-family: 'Courier New', monospace;
}

.audit-panel {
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.35rem 1.5rem;
}

.audit-panel__header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border);
}

.audit-panel__title {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--ink);
}

.audit-panel__meta {
    font-size: 0.875rem;
    color: var(--ink-soft);
    font-variant-numeric: tabular-nums;
}

.audit-list {
    display: grid;
    gap: 0.55rem;
    margin: 0;
    padding: 0;
    list-style: none;
}

.audit-item {
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
    padding: 0.65rem 0.85rem;
    border-radius: 6px;
    background-color: var(--surface-2);
    font-size: 0.9375rem;
    line-height: 1.45;
    color: var(--ink);
}

.audit-item__tag {
    flex-shrink: 0;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    background-color: rgba(242, 85, 44, 0.16);
    color: var(--accent);
}

.audit-ok {
    padding: 0.85rem 1rem;
    border-radius: 6px;
    background-color: rgba(34, 211, 230, 0.1);
    color: var(--human);
    font-weight: 500;
}

.cronometro-container {
    background-color: var(--surface);
    padding: 1rem;
    border-radius: 10px;
    border: 1px solid var(--border);
    text-align: center;
    font-family: 'Instrument Sans', sans-serif;
    font-size: 1.2rem;
    font-variant-numeric: tabular-nums;
    color: var(--human);
}

.hoja-papel {
    background-color: var(--surface-2);
    padding: 1.15rem 1.35rem;
    border-radius: 10px;
    font-family: 'Instrument Sans', sans-serif;
    font-size: 1.02rem;
    line-height: 1.65;
    color: var(--ink);
    height: 440px;
    min-height: 440px;
    max-height: 440px;
    width: 100%;
    overflow-y: auto;
    white-space: pre-wrap;
    border: 1px solid var(--border);
    box-sizing: border-box;
}

.hoja-papel--vacia {
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    font-family: 'Instrument Sans', sans-serif;
    font-size: 0.98rem;
    color: var(--ink-soft);
    white-space: normal;
}

.hoja-papel::-webkit-scrollbar {
    width: 8px;
}

.hoja-papel::-webkit-scrollbar-track {
    background: var(--surface-2);
}

.hoja-papel::-webkit-scrollbar-thumb {
    background: var(--surface-3);
    border-radius: 4px;
}

.btn-copiar {
    background-color: var(--accent);
    color: #111317;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 10px;
    cursor: pointer;
    margin-top: 0.75rem;
    width: 100%;
    font-weight: 600;
    font-size: 0.95rem;
    font-family: 'Instrument Sans', sans-serif;
    transition: background-color 180ms ease-out, transform 120ms ease-out;
}

.btn-copiar:hover {
    background-color: var(--accent-hover);
    transform: translateY(-1px);
}

.btn-copiar:focus-visible {
    outline: 2px solid var(--human);
    outline-offset: 2px;
}

.btn-copiar.copiado {
    background-color: var(--human);
    color: #0F1114;
}

.login-container {
    text-align: center;
    padding: 0.25rem 0 0.75rem 0;
}

.login-title {
    font-family: 'Instrument Sans', sans-serif;
    font-size: clamp(2.4rem, 4.2vw, 3.25rem);
    font-weight: 700;
    color: var(--ink-white);
    margin: 0.4rem 0 0.4rem 0;
    line-height: 1.1;
}

.login-subtitle {
    color: var(--ink-soft);
    font-size: 1.05rem;
    margin-bottom: 1.25rem;
    font-family: 'Instrument Sans', sans-serif;
}

.page-footer {
    width: 100%;
    margin-top: 2.25rem;
    padding: 1rem 9.5rem 0.5rem 0;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: flex-end;
    align-items: center;
    color: var(--ink-soft);
    font-size: 0.875rem;
    font-family: 'Instrument Sans', sans-serif;
    box-sizing: border-box;
}

.page-footer p {
    margin: 0;
}

.status-text {
    color: var(--human);
    font-family: 'Instrument Sans', sans-serif;
    font-size: 0.95rem;
    margin-top: 0.5rem;
}

.log-line {
    color: var(--ink-soft);
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    padding: 0.25rem 0;
}

@media (prefers-reduced-motion: reduce) {
    .stButton > button,
    .stFormSubmitButton > button,
    .btn-copiar {
        transition: background-color 150ms linear;
        transform: none;
    }
    .stButton > button:hover,
    .stButton > button:active,
    .stFormSubmitButton > button:hover,
    .stFormSubmitButton > button:active,
    .btn-copiar:hover {
        transform: none;
    }
}
</style>
"""
st.markdown(CSS_TEMA, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Constantes de configuración (velocidad ágil + alta variación anti-detección)
# ---------------------------------------------------------------------------
TEMPERATURA_FINAL = 1.35
TEMPERATURA_INTERMEDIA = 0.90
TEMPERATURA_DETECTOR = 1.28
FREQUENCY_PENALTY = 0.55
PRESENCE_PENALTY = 0.55
TOP_P = 0.85
RITMO_MINIMO = 0.56
MAX_CARACTERES = 4000
MAX_TOKENS = 2048
TIMEOUT = 25
TAMANO_BLOQUE = 580
MAX_RONDAS_CORRECCION = 1
MAX_RONDAS_DETECTORES = 1
MAX_RETRIES = 1
BASE_BACKOFF = 1.0
PAUSA_CUOTA = 120
PAUSA_LENTO = 180
PAUSA_DIARIA = 1800

LOGO_URL = "https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png"
LOGO_LOGIN = 310
LOGO_SIDEBAR = 215

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
# Muestra de estilo y criterios extraídos de la tesis 2003 (Talca)
# ---------------------------------------------------------------------------
MUESTRA_ESTILO_TESIS = """
Las ciudades han sido históricamente de dos tipos, diseñadas y proyectadas de manera precisa con un orden predeterminado o desarrolladas con un crecimiento espontáneo sin ningún plan preestablecido. De cualquier manera que se clasifiquen, dentro de estas dos categorías, su expansión y crecimiento obligan a considerar los mecanismos de control necesarios para regular el uso del suelo y las posibles consecuencias que su desarrollo pueda generar con el tiempo.

De acuerdo con lo anterior, es necesario comprender cómo la ciudad, a través del uso del suelo, mantiene vigentes esos mismos modelos históricos y antagónicos. Para plantear una hipótesis frente al problema del suelo urbano, debemos considerar los factores que intervienen y se afectan mutuamente dentro del espacio urbano.
""".strip()

PROMPT_RETRO = (
    "Retrotraduce este texto español: primero pásalo a inglés llano conservando "
    "cada dato, cifra, nombre, cita y año; luego vuelve al español natural "
    "reordenando las ideas dentro de cada oración y cambiando los conectores. "
    "No resumas ni omitas nada. No uses calcos literales ni palabras forzadas. "
    "Devuelve SOLO el texto final en español."
)

PROMPT_ESTRUCTURA = (
    "Eres un editor humano. Rompe la estructura mecánica del texto: "
    "1) Divide párrafos densos en bloques de 2 a 3 oraciones. "
    "2) Ninguna oración puede superar 32 palabras. "
    "3) Al menos el 35% de las oraciones deben tener entre 5 y 9 palabras. "
    "4) Alterna oraciones cortas y largas sin repetir la misma extensión seguida. "
    "5) No repitas la misma palabra al inicio de varias oraciones. "
    "Conserva el significado y todos los datos. Devuelve SOLO el texto."
)

PROMPT_FINAL_BASE = (
    "Eres un escritor y analista con voz propia, clara y natural. "
    "Redacta la versión final con ritmo variable, vocabulario preciso y "
    "sin fórmulas de IA."
)

PROMPT_FINAL_REGLAS = """
BURSTINESS EXTREMA Y NATURALIDAD (obligatorio):
1. Alterna oraciones cortas (5-9 palabras) con largas (22-32 palabras).
2. NUNCA dos oraciones seguidas de largo similar (diferencia mínima 7 palabras).
3. NUNCA tres oraciones seguidas de estructura parecida.
4. Máximo 20% de oraciones empezando con El/La/Los/Las/Se, y nunca repitas la misma palabra inicial ("Las...", "El...", "La...") más de 2 veces.
5. No repitas ideas ni uses gerundios de remate al final de una oración ("...llevando así a...", "...permitiendo también...").

PROHIBIDO (no aparezca NUNCA):
- "asimismo", "no obstante", "por lo tanto", "sin embargo", "además".
- "en conclusión", "es fundamental", "cabe destacar", "juega un papel", "se ha convertido en", "en el ámbito de", "mediante", "es crucial", "es esencial", "es importante abordar", "en este sentido", "en última instancia", "a través de".
- Calcos o palabras forzadas como "luxosos", "RETURN OF INVERSION", "frivolidades" o "saciedad" fuera de contexto.
- Cierres de relleno tipo "creo firmemente en todo esto siempre".

PUNTUACIÓN:
- Usa punto y coma (;) al menos 2 veces.
- Usa paréntesis () o guion largo (—) cuando aporten precisión.
- Nunca pongas dos comas seguidas.

DATOS: conserva TODAS las fechas, nombres, cifras y citas TAL CUAL.

Devuelve SOLO el texto reescrito en español limpio, sin explicaciones."""

PROMPT_CORRECCION_BASE = (
    "Eres un corrector de estilo. Corrige SOLO las frases vetadas, erratas "
    "o problemas listados manteniendo el ritmo irregular y las oraciones "
    "cortas. Devuelve SOLO el texto corregido."
)

PROMPT_DETECTOR_BASE = (
    "Eres un editor que reescribe oraciones sospechosas de IA con cambio "
    "sintáctico real: parte oraciones largas (>32 palabras), cambia la "
    "estructura, evita inicios repetidos y elimina fórmulas de IA. Conserva "
    "el sentido y los datos. Devuelve SOLO el texto completo en español limpio."
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
    min_palabras = int(num_palabras * 0.90)
    max_palabras = int(num_palabras * 1.12)
    min_parrafos = max(1, num_parrafos - 1)
    max_parrafos = num_parrafos + 2
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
# Limpieza y control anti-corrupción de texto
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
    texto = re.sub(r",\s*,+", ",", texto)
    texto = re.sub(r"\s+([,;:!?])", r"\1", texto)
    texto = re.sub(r"([,;:!?])(?!\s)", r"\1 ", texto)
    texto = re.sub(r",\s*,+", ",", texto)
    texto = re.sub(r"\(\s+", "(", texto)
    texto = re.sub(r"\s+\)", ")", texto)
    return texto


def corregir_espaciado(texto: str) -> str:
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def es_texto_corrupto(texto: str) -> bool:
    """Detecta solo colapsos reales de tokens, scripts no latinos o ruido extremo."""
    if not texto or len(texto.strip()) < 15:
        return True

    no_latinos = re.findall(r"[\u0400-\u04FF\u0600-\u06FF\u0E00-\u0E7F\u4E00-\u9FFF]", texto)
    if len(no_latinos) >= 2:
        return True

    palabras = re.findall(r"[A-Za-zÁÉÍÓÚÜáéíóúüÑñ]{12,}", texto)
    sin_vocal = [
        p for p in palabras if not re.search(r"[aeiouáéíóúüAEIOUÁÉÍÓÚÜ]", p)
    ]
    if len(sin_vocal) >= 3:
        return True

    raros = re.findall(r"[^\w\s.,;:!?¿¡\"'()\-–—%$€/@#&+=*áéíóúüñÁÉÍÓÚÜÑ]", texto)
    if len(raros) > max(10, int(len(texto) * 0.05)):
        return True

    return False


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

    texto = re.sub(r"\bmjores\b", "mejores", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bRETURN OF INVERSION\b", "retorno de la inversión (ROI)", texto)
    texto = re.sub(r"\bproductos luxosos\b", "productos de lujo", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\bluxosos\b", "de lujo", texto, flags=re.IGNORECASE)

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
    return {p: c for p, c in Counter(inicios).items() if c > 2 and len(p) > 2}


FRASES_VETADAS_IA = [
    "en conclusión", "es fundamental", "cabe destacar", "juega un papel",
    "se ha convertido en", "en el ámbito de", "mediante", "asimismo",
    "no obstante", "por lo tanto", "sin embargo", "además", "en definitiva",
    "vale la pena mencionar", "es importante señalar", "cabe mencionar",
    "en el mundo actual", "en la actualidad", "en este sentido",
    "resulta fundamental", "desempeña un papel crucial", "en resumen",
    "por otro lado", "cabe señalar", "es crucial", "es esencial",
    "es importante abordar", "a través de",
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
    "de manera radical", "alterando significativamente", "nuevo paradigma",
    "aspecto clave", "se abre paso", "en este entorno", "para navegar este entorno",
    "herramienta fundamental", "uno de los desafíos más significativos",
    "para mantenerse competitivos", "lo que realmente importa",
    "en un entorno laboral cada vez más exigente", "en constante cambio",
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

    if re.search(r",\s*,", texto):
        problemas.append("Comas duplicadas en la puntuación")

    if re.search(r"\bpasa por\s+\w+(?:ando|endo)\b", texto.lower()):
        problemas.append("Uso de 'pasa por + gerundio' (usar infinitivo)")

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

    if any(l > 35 for l in longitudes):
        problemas.append("Oraciones demasiado largas (>35 palabras)")

    if not any(l < 10 for l in longitudes):
        problemas.append("Ninguna oración corta (<10 palabras)")

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
    if len(inicios) > 0 and (len(art) / len(inicios)) > 0.25:
        problemas.append("Inicios repetitivos (El/La/Los/Las/Se > 25%)")

    parrafos = extraer_parrafos(texto)
    for p in parrafos:
        op = extraer_oraciones(p)
        if len(op) >= 3:
            lp = [len(o.split()) for o in op]
            if max(lp) - min(lp) < 5:
                problemas.append("Párrafos planos (oraciones de largo parecido)")
                break

    total_conectores = sum(texto_lower.count(c) for c in CONECTORES_MANUAL)
    if total_conectores > len(oraciones) * 0.10:
        problemas.append(f"Conectores de manual en exceso ({total_conectores})")

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
        headers["X-Title"] = "Humanizador pro"

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

            if es_texto_corrupto(resultado):
                raise ValueError("Respuesta corrupta o con tokens mezclados")

            return {
                "texto": resultado,
                "proveedor_usado": cfg["nombre"],
                "modelo_usado": modelo_actual,
                "exito": True,
                "error": None,
