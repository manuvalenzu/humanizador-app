"""
Humanizador pro - Aplicación Streamlit para humanizar textos generados por IA.

Pipeline multi-proveedor con retrotraducción, reestructuración,
auditoría de detectores, reescritura por detector, procesamiento en
bloques paralelos, sistema de pausados y tema oscuro completo.

Autor: Manu
derechos reservados © Humanizador pro, 2026
"""

import re
import html
import hmac
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

/* El encabezado de Streamlit es fijo (~3.75rem): sin este margen tapaba
   la insignia "Elaborado por Manu". */
.block-container {
    padding-top: 4.5rem !important;
    padding-bottom: 3rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 1240px !important;
    margin: 0 auto;
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
    margin-bottom: 1rem;
    width: 100%;
}

.topbar-autor__badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-family: 'Instrument Sans', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--ink-white);
    background-color: var(--surface);
    border: 1px solid var(--border);
    padding: 0.4rem 1rem;
    border-radius: 999px;
}

.topbar-autor__punto {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--human);
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
    margin-bottom: 2rem;
    padding: 1.75rem 2rem;
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 12px;
    box-sizing: border-box;
}

.hero-brand__title {
    margin: 0 0 0.6rem 0;
    padding: 0 !important;
    font-family: 'Instrument Sans', sans-serif;
    font-size: clamp(2.1rem, 3.6vw, 2.9rem);
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: -0.025em;
    color: var(--ink-white);
}

.hero-brand__lead {
    margin: 0 0 0.75rem 0;
    font-size: 1rem;
    line-height: 1.55;
    color: var(--ink-soft);
    width: 100%;
}

.hero-brand__purpose {
    margin: 0 0 1.1rem 0;
    width: 100%;
    max-width: 72ch;
    font-size: 0.98rem;
    line-height: 1.62;
    color: var(--ink);
}

.hero-tip {
    margin-top: 0.5rem;
    padding: 0.9rem 1.15rem;
    background-color: var(--surface-2);
    border: 1px solid var(--border);
    border-left: 3px solid var(--human);
    border-radius: 10px;
    font-size: 0.93rem;
    line-height: 1.55;
    color: var(--ink);
}

.hero-tip__badge {
    display: inline-block;
    color: var(--human);
    font-weight: 700;
    margin-right: 0.35rem;
}

.editor-col-label {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--ink-white);
    margin: 0 0 0.2rem 0;
}

.editor-col-sub {
    font-size: 0.9rem;
    color: var(--ink-soft);
    margin: 0 0 0.75rem 0;
    min-height: 1.4rem;
}

.editor-pie {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    color: var(--ink-soft);
    font-variant-numeric: tabular-nums;
    margin: 0.5rem 0 1rem 0;
}

.stButton > button,
.stFormSubmitButton > button,
[data-testid="stDownloadButton"] > button {
    min-height: 2.9rem;
    border-radius: 10px;
    font-weight: 600;
    font-family: 'Instrument Sans', sans-serif;
    padding: 0.55rem 1rem;
    transition: background-color 180ms ease-out, transform 120ms ease-out, border-color 180ms ease-out;
}

/* Secundario (Limpiar, Cerrar sesión, Descargar) */
.stButton > button,
[data-testid="stDownloadButton"] > button {
    background-color: var(--surface-2);
    color: var(--ink);
    border: 1px solid var(--border);
}

.stButton > button:hover,
[data-testid="stDownloadButton"] > button:hover {
    background-color: var(--surface-3);
    border-color: var(--human);
    color: var(--ink-white);
}

/* Primario (Humanizar texto, Ingresar) */
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"],
.stFormSubmitButton > button {
    background-color: var(--accent);
    color: #111317;
    border: 1px solid var(--accent);
}

.stButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover,
.stFormSubmitButton > button:hover {
    background-color: var(--accent-hover);
    border-color: var(--accent-hover);
    color: #111317;
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

/* Selector amplio: en versiones nuevas de Streamlit cambió el anidado
   de divs y la regla anterior ya no aplicaba (el cuadro salía pequeño). */
.stTextArea textarea {
    height: 440px !important;
    min-height: 440px !important;
    max-height: 440px !important;
    padding: 1.15rem 1.35rem !important;
    font-size: 1.02rem !important;
    line-height: 1.65 !important;
    background-color: var(--surface-2) !important;
    color: var(--ink) !important;
    resize: none !important;
    box-sizing: border-box !important;
}

.stTextArea [data-baseweb="textarea"],
.stTextArea [data-baseweb="base-input"] {
    background-color: var(--surface-2) !important;
    border-color: var(--border) !important;
    border-radius: 10px !important;
}

.stTextArea [data-testid="InputInstructions"] {
    display: none;
}

.stTextInput > div > div > input:focus-visible,
.stTextArea > div > div > textarea:focus-visible {
    border-color: var(--human);
    outline: 2px solid var(--human);
    outline-offset: -2px;
}

.stMetric,
[data-testid="stMetric"] {
    background-color: var(--surface);
    padding: 1.1rem 1.35rem;
    border-radius: 12px;
    border: 1px solid var(--border);
    min-height: 8.25rem;
    box-sizing: border-box;
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
    border-radius: 12px;
    padding: 1.35rem 1.5rem;
    margin-bottom: 1.25rem;
    box-sizing: border-box;
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
    padding: 0 !important;
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
    margin: 0 !important;
    padding: 0 !important;
    list-style: none;
}

.audit-item {
    margin: 0 !important;
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
    margin: 0 0 1rem 0;
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

.logo-box img {
    display: block;
    margin: 0 auto;
}

.login-title {
    text-align: center;
    padding: 0 !important;
    font-family: 'Instrument Sans', sans-serif;
    font-size: clamp(2.1rem, 3.8vw, 2.9rem);
    font-weight: 700;
    color: var(--ink-white);
    margin: 0.4rem 0 0.4rem 0;
    line-height: 1.1;
}

.login-subtitle {
    text-align: center;
    color: var(--ink-soft);
    font-size: 1.05rem;
    margin-bottom: 1.25rem;
    font-family: 'Instrument Sans', sans-serif;
}

.page-footer {
    width: 100%;
    margin-top: 2.5rem;
    padding: 1.1rem 0 0.25rem 0;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: center;
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

/* Etiquetas y controles legibles aunque falte el tema oscuro en config.toml */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
.stSidebar label,
.stSidebar [data-testid="stMarkdownContainer"] p {
    color: var(--ink-soft) !important;
}

.stSidebar h1, .stSidebar h2, .stSidebar h3 {
    color: var(--ink) !important;
    font-size: 1.05rem !important;
}

[data-testid="stForm"] {
    background-color: var(--surface);
    border: 1px solid var(--border) !important;
    border-radius: 12px;
    padding: 1.25rem 1.25rem 1rem 1.25rem;
}

.stTextInput [data-baseweb="input"],
.stTextInput [data-baseweb="base-input"],
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
    background-color: var(--surface-2) !important;
    border-color: var(--border) !important;
    color: var(--ink) !important;
}

.stTextInput input {
    background-color: transparent !important;
    color: var(--ink) !important;
}

[data-baseweb="tag"] {
    background-color: rgba(242, 85, 44, 0.18) !important;
    color: var(--ink) !important;
}

[data-testid="stExpander"] details {
    border-color: var(--border) !important;
    border-radius: 10px;
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
# Constantes de configuración (límite de 4.000 caracteres + ritmo variable)
# ---------------------------------------------------------------------------
# Temperaturas en escala "estándar" (Llama, Qwen, Mistral, Gemini, GPT-OSS).
# Sobre 1,1 esos modelos empiezan a cometer errores de concordancia y a usar
# palabras raras. DeepSeek usa otra escala (su API recomienda 1,3 para
# conversación y traducción, y 1,5 para escritura creativa; por defecto 1,0),
# así que para DeepSeek se multiplica por FACTOR_TEMPERATURA.
TEMPERATURA_FINAL = 1.05          # ajustable en la barra lateral (0,80-1,30)
TEMPERATURA_INTERMEDIA = 0.80
TEMPERATURA_CORRECCION = 0.60
TEMPERATURA_DETECTOR = 0.95
FACTOR_TEMPERATURA = {"deepseek": 1.25}
TEMPERATURA_TOPE = {"deepseek": 1.5}
TEMPERATURA_TOPE_GENERAL = 1.30

# Muestreo por etapa. Antes se usaban frequency 0,70 y presence 0,65 en TODAS
# las etapas: esas penalizaciones castigan cada repetición de una palabra,
# incluidas "de", "la", los nombres propios y los términos técnicos, así que
# el modelo los cambiaba por sinónimos raros o los deformaba. En las etapas
# que deben ser fieles (retrotraducción y corrección) van en cero.
MUESTREO_ETAPA: Dict[str, Dict[str, float]] = {
    "retro":      {"top_p": 0.90, "frequency_penalty": 0.0,  "presence_penalty": 0.0},
    "estructura": {"top_p": 0.92, "frequency_penalty": 0.15, "presence_penalty": 0.10},
    "final":      {"top_p": 0.95, "frequency_penalty": 0.30, "presence_penalty": 0.30},
    "correccion": {"top_p": 0.90, "frequency_penalty": 0.0,  "presence_penalty": 0.0},
    "detector":   {"top_p": 0.95, "frequency_penalty": 0.20, "presence_penalty": 0.20},
}
# Perfil "anti-detector": exactamente los parámetros de la v4, la versión que
# dio 0 % en ZeroGPT y 10 % en QuillBot. Penalizaciones altas en TODAS las
# etapas y sin escala especial para DeepSeek: el texto sale menos predecible
# (eso es lo que miden los detectores), a costa de ser algo menos formal.
# Valores del archivo que dio 0 % en QuillBot (temperatura 1,22; penalizaciones
# 0,78/0,72; top_p 0,96). En retrotraducción y corrección, que deben ser fieles
# al contenido, las penalizaciones se bajan para no deformar nombres ni términos.
MUESTREO_ANTI = {"top_p": 0.96, "frequency_penalty": 0.78, "presence_penalty": 0.72}
# Igual que tu archivo: los mismos valores en todas las etapas.
MUESTREO_ANTI_FIEL = dict(MUESTREO_ANTI)
ETAPAS_FIELES = ("retro", "correccion")
LARGO_MAXIMO_ANTI = 22
TEMPERATURA_ANTI = {"final": 1.22, "retro": 0.96, "estructura": 0.96,
                    "correccion": 0.96, "detector": 1.26}
PERFILES = {
    "anti": "Anti-detector (configuración v4)",
    "profesional": "Profesional (más formal y fluido)",
}
TOP_P = 0.95
FREQUENCY_PENALTY = 0.30
PRESENCE_PENALTY = 0.30

RITMO_MINIMO = 0.46
# Con un tope de 20 palabras y oraciones de 6 a 17, el CV no puede pasar de
# ~0,32 (justo el 0,31 que daba). Para llegar a 0,46 hace falta alguna oración
# larga (24-32) por párrafo: con esa mezcla el CV calculado es 0,53.
LARGO_MAXIMO = 34
CORTA_MIN, CORTA_MAX = 4, 11
PERFIL_ANTI_IA = {
    "media_ideal": 13.5,
    "cv_ideal": 0.56,
    "rango_media": (9.5, 19.0),
}
# Dos candidatos en paralelo para la redacción final: casi no suma tiempo y
# se queda el más natural. Pon 1 si quieres gastar menos cuota.
CANDIDATOS_FINAL = 2
MAX_CARACTERES = 4000
MAX_TOKENS = 2048
TIMEOUT = 30
# Los modelos grandes (NVIDIA, OpenRouter) tardan más en generar 2048 tokens.
TIMEOUT_POR_PROVEEDOR = {"groq": 30, "openrouter": 45, "nvidia": 60, "deepseek": 45, "gemini": 45}
# Plazo total del proceso. Cada llamada ajusta su timeout al tiempo que queda
# y las etapas opcionales se saltan si no alcanzan: ya no se pierde el trabajo.
TIEMPO_MAXIMO_TOTAL = 150
# Tiempo mínimo que debe quedar para iniciar cada etapa. Las previas a la
# redacción final dejan además margen para que la final alcance a correr.
RESERVA_ETAPA = {"retro": 75, "estructura": 75, "final": 15, "ritmo": 12,
                 "correccion": 30, "detector": 15}
TAMANO_BLOQUE = 580
MAX_RONDAS_CORRECCION = 1
MAX_RONDAS_DETECTORES = 2
MAX_RETRIES = 1
# Margen de extensión aceptado en cada etapa respecto de su entrada.
# Si un modelo devuelve un fragmento (o se alarga de más), la etapa se repite
# una vez y, si vuelve a fallar, se descarta y se conserva el texto anterior.
EXTENSION_MIN = 0.85
EXTENSION_MAX = 1.25
BASE_BACKOFF = 1.0
PAUSA_CUOTA = 120
PAUSA_LENTO = 180
PAUSA_DIARIA = 1800
LOGIN_MAX_FALLOS = 5
LOGIN_BLOQUEO = 60

LOGO_URL = "https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png"
LOGO_LOGIN = 310
LOGO_SIDEBAR = 215

GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------
PROVEEDORES: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "nombre": "DeepSeek",
        "clave": "DEEPSEEK_API_KEY",
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "models_endpoint": "https://api.deepseek.com/v1/models",
        "tipo": "openai_compatible",
        "gratis": False,
        "velocidad": "medio",
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
    "gemini": {
        "nombre": "Google Gemini",
        "clave": "GEMINI_API_KEY",
        "endpoint": None,
        "models_endpoint": None,
        "tipo": "gemini_sdk",
        "gratis": True,
        "velocidad": "rapido",
    },
    "groq": {
        "nombre": "Groq",
        "clave": "GROQ_API_KEY",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "models_endpoint": "https://api.groq.com/openai/v1/models",
        "tipo": "openai_compatible",
        "gratis": True,
        "velocidad": "muy_rapido",
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
}

ORDEN_FALLBACK = ["deepseek", "openrouter", "gemini", "groq", "nvidia"]

MODELO_POR_PROVEEDOR: Dict[str, str] = {
    "deepseek": "deepseek-chat",
    "openrouter": "qwen/qwen-2.5-72b-instruct",
    "gemini": GEMINI_MODEL_DEFAULT,
    "groq": "llama-3.3-70b-versatile",
    "nvidia": "mistralai/mistral-large-4-1t-a52b",
}

MODELOS_FIJOS: Dict[str, List[str]] = {
    "deepseek": ["deepseek-chat", "deepseek-flash"],
    "openrouter": [
        "qwen/qwen-2.5-72b-instruct",
        "mistralai/mistral-large",
        "meta-llama/llama-3.3-70b-instruct",
    ],
    "gemini": [GEMINI_MODEL_DEFAULT],
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    "nvidia": [
        "mistralai/mistral-large-4-1t-a52b",
        "deepseek-ai/deepseek-v3",
        "meta/llama-3.3-70b-instruct",
    ],
}

# Se buscan como subcadena: son modelos que no redactan (seguridad,
# embeddings, visión, audio) o variantes por lotes que no responden al momento.
EXCLUIDOS_SUBCADENA = [
    "guard", "embed", "rerank", "retriever", "reward", "moderation",
    "classifier", "whisper", "tts", "speech", "audio", "vision", "pixtral",
    "-vl", "ocr", "image", "imagen", "dall", "sora", "flux", "diffusion",
    "clip", "bert", "tokenizer", ":batch", "parse",
]
# Se buscan como palabra completa: como subcadena excluían IDs válidos.
EXCLUIDOS_PALABRA = ["sd", "vit", "stt", "token", "safety", "filter"]


def es_modelo_de_texto(mid: str) -> bool:
    baja = mid.lower()
    if any(x in baja for x in EXCLUIDOS_SUBCADENA):
        return False
    if set(re.split(r"[-/_.:]", baja)) & set(EXCLUIDOS_PALABRA):
        return False
    return True


# Orden de preferencia para redactar en español: modelos grandes y probados.
# Las variantes pequeñas (8b, 20b, mini, instant) quedan al final.
# Llama 3.3 en español tiende al registro institucional ("respuesta integral",
# "en su articulado"): queda al final, útil solo para pasos intermedios.
PREFERENCIA_MODELOS = [
    "deepseek-chat", "deepseek-v4", "deepseek-flash", "qwen-2.5-72b",
    "mistral-large", "gemini-2.5-flash", "deepseek-v3", "qwen3",
    "gpt-oss-120b", "llama-3.3-70b",
]
MARCAS_PEQUENO = ["8b", "7b", "4b", "3b", "1b", "20b", "mini", "nano", "instant", "lite"]


def rankear_modelos(modelos: List[str]) -> List[str]:
    def clave(m: str) -> Tuple[int, int]:
        baja = m.lower()
        pequeno = int(any(re.search(r"(?<![a-z0-9])" + x + r"(?![a-z0-9])", baja) for x in MARCAS_PEQUENO))
        idx = next((i for i, pat in enumerate(PREFERENCIA_MODELOS) if pat in baja), len(PREFERENCIA_MODELOS))
        return (pequeno, idx)
    return sorted([m for m in modelos if es_modelo_de_texto(m)], key=clave)


FAMILIAS_TEXTO = [
    "llama", "mistral", "qwen", "deepseek", "gemma", "phi", "yi", "mixtral",
    "codellama", "wizard", "zephyr", "nous", "openchat", "starling", "solar",
    "command", "jamba", "dbrx", "falcon", "mpt", "replit", "stable", "vicuna",
    "alpaca", "koala", "orca", "dolphin", "hermes", "openhermes", "tiny",
    "gpt", "claude", "gemini", "grok",
]


# ---------------------------------------------------------------------------
# Muestra de estilo y reglas concisas en español
# ---------------------------------------------------------------------------
MUESTRA_RITMO_NATURAL = """
El diputado Juan Santana impulsa el proyecto "Hijito Corazón" frente al abandono y la desprotección de las personas mayores en Chile. La iniciativa toma como base la Ley Papito Corazón, centrada en cobrar pensiones alimentarias a menores, y busca llevar parte de esa lógica a los derechos de la vejez.

Este problema cruza factores económicos, familiares, jurídicos y de salud. Preocupa sobre todo quienes quedan sin apoyo tras el alta hospitalaria, ya que la falta de respaldo complica su recuperación.

La propuesta crea un procedimiento especial en los Tribunales de Familia, con foco en quienes tienen 80 años o más. También permite exigir deudas alimentarias y retener fondos previsionales, junto con acompañar hospitalizaciones para evitar el aislamiento.

Además, endurece las penas por abandono en casos graves y amplía la información sobre derechos alimenticios en hospitales. Todo esto exige respaldo presupuestario y redes públicas de cuidado, revisando casos de violencia intrafamiliar, abuso o abandono previo.
""".strip()

PROMPT_RETRO = (
    "Retrotraduce este texto español: pásalo a inglés llano y luego vuelve a "
    "un español fluido, profesional y natural, reordenando frases y evitando "
    "cláusulas largas con 'denominada', 'cuyo propósito', 'en este contexto', "
    "'constituye una problemática', 'orientada al cumplimiento', "
    "'estableciendo' o 'destinados a'. Conserva cada dato, cifra, nombre, "
    "ley y año. Devuelve SOLO el texto en español, con los mismos párrafos."
)

PROMPT_ESTRUCTURA = (
    "Eres un editor en español. Escribe en párrafos continuos de 3 a 4 "
    "oraciones bien conectadas. Mezcla frases breves (5 a 9 palabras), "
    "frases directas de 12 a 18 y una oración larga (24 a 32) por párrafo. No encadenes oraciones largas con "
    "gerundios, participios o relativos ('cuyo', 'destinados a', 'orientada "
    "al'). Evita cortes bruscos tipo 'Esto es...' o 'Ellas...' sueltos y no "
    "repitas 'situaciones' ni empieces varias frases con 'También'. Conserva "
    "todos los datos. Devuelve SOLO el texto."
)

PROMPT_FINAL_BASE = (
    "Eres un redactor en español con prosa clara, firme y fluida. Escribe "
    "con naturalidad humana, evitando las fórmulas y estructuras que "
    "QuillBot suele marcar como IA, pero sin dejar frases cortadas o "
    "repetitivas. Entrega SOLO el texto final."
)

PROMPT_FINAL_REGLAS = """
OBLIGATORIO:
1. Escribe en párrafos continuos de 3 a 5 oraciones (separados por línea en blanco). En cada párrafo mezcla tres largos: al menos una frase corta (5-9 palabras), frases directas de 12 a 18 palabras y UNA oración larga y bien construida de 24 a 32 palabras. Sin esa oración larga el ritmo queda parejo.
2. Mantén un tono profesional y claro, sin repetir "situaciones" más de una vez, sin empezar más de una frase con "También", y sin cortes artificiales como "Esto es..." o "Ellas..." sueltos.
3. PROHIBIDO usar: "denominada", "cuyo propósito", "en este contexto", "constituye una problemática", "orientada al cumplimiento", "estableciendo mecanismos", "destinados a facilitar", "de manera oportuna", "además", "sin embargo", "no obstante", "por lo tanto", "en definitiva", "en conclusión", "finalmente", "de esta forma", "de esta manera", "esto se debe a que", "esto genera", "esto facilitará", "en su articulado", "respuesta integral", "creciente problemática", "vulnerabilidad profunda", "especial énfasis", "entramado", "diversas dimensiones", "no solo", "sino que también", "es fundamental", "es esencial", "es crucial", "aspecto crucial", "cabe destacar", "situaciones de vulnerabilidad", "vulneraciones de derechos", "mecanismos institucionales", "obligaciones alimenticias", "proceso acelerado", "trámite específico", "se inspira en", "enfocada en", "centrada en", "más rápida y eficaz", "implementa medidas", "lo que agrava", "abarca aspectos", "establece mecanismos", "una preocupación particular".
4. PROHIBIDO cerrar oraciones con gerundio o participio tras coma.
5. Conserva TODOS los nombres propios, cargos, partidos, leyes, códigos, cifras y matices del original.
6. Registro profesional: cada oración lleva verbo conjugado (nada de frases sueltas tipo apunte) y sin coloquialismos.
7. Usa los términos jurídicos correctos ("procedimiento especial", "pensión de alimentos", "obligación alimentaria"); no los cambies por "trámite" o "ayuda económica".
8. No cambies el sentido de ninguna idea: si el original dice que algo debe considerarse como excepción, no lo conviertas en algo que debe evitarse.
9. No copies datos, nombres ni frases de la muestra: es solo una referencia de ritmo.

Devuelve SOLO el texto final en español limpio, sin encabezados ni explicaciones."""

PROMPT_CORRECCION_BASE = (
    "Eres un corrector editorial en español. Corrige los problemas "
    "detectados para que el texto sea fluido, profesional y pase QuillBot: "
    "parte las oraciones de más de 34 palabras, deja una larga (24-32) por párrafo, elimina 'denominada', 'cuyo "
    "propósito', 'en este contexto', 'constituye una problemática', "
    "'estableciendo', 'destinados a', cortes bruscos ('Esto es...', 'Ellas...'), "
    "repetición de 'situaciones' o de 'También' al inicio, conectores "
    "prohibidos y participios/gerundios tras coma. Conserva todos los datos. "
    "Devuelve SOLO el texto corregido."
)

PROMPT_PARTIR_BASE = (
    "Eres un editor en español. Recibes oraciones largas numeradas. Divide cada "
    "una en DOS oraciones completas, cada una con su propio verbo y sujeto claro, "
    "cortando SOLO en un límite natural: antes de 'que', 'ya que', 'pero', 'y' o "
    "donde termina una idea. Si la segunda oración necesita sujeto, repite el "
    "sustantivo ('El proyecto…', 'La medida…', 'Estas personas…'). PROHIBIDO "
    "empezar con 'Esto es', 'Ello es', 'Ellas', 'Ellos' o 'Así'. No cambies el "
    "sentido, no agregues ideas, no quites datos y no uses conectores como "
    "'Además', 'Asimismo' o 'Finalmente'. Si una oración no se puede dividir "
    "sin forzarla, devuélvela igual. Devuelve SOLO las líneas numeradas como la "
    "lista, con las dos oraciones de cada número en la misma línea."
)

PROMPT_DETECTOR_BASE = (
    "Eres un editor anti-IA en español. Reescribes oraciones que QuillBot "
    "marca o que suenan a informe/plantilla para volverlas fluidas, "
    "profesionales y naturales. Hazlas directas y de largo variado, sin "
    "'denominada', 'cuyo propósito', 'en este contexto', 'constituye una "
    "problemática', 'estableciendo', 'destinados a', 'Esto es...', 'Ellas...', "
    "repetir 'situaciones', conectores prohibidos ni remates con participio o "
    "gerundio tras coma. Conserva todos los datos y nombres. Devuelve SOLO "
    "las líneas reescritas, numeradas igual que la lista."
)


def con_muestra(prompt_base: str, reglas: str, muestra: str, instruccion_medida: str) -> str:
    return f"""{prompt_base}

MUESTRA DE PROSA FLUIDA (solo referencia de ritmo; no copies sus datos):
---
{muestra}
---

{instruccion_medida}

{reglas}"""


# ---------------------------------------------------------------------------
# Prompts del perfil "anti-detector": los del archivo que dio 0 % en QuillBot,
# con reglas para proteger sentido y términos jurídicos
# ---------------------------------------------------------------------------
MUESTRA_ANTI = """
El diputado Juan Santana impulsa el proyecto "Hijito Corazón" frente al abandono de adultos mayores. El tema pesa cada vez más. La propuesta toma como base la Ley Papito Corazón, que apunta al cobro de pensiones alimentarias.

Quedar sin familia al salir del hospital deja a muchos mayores en un aprieto grave. Lo mismo pasa con el maltrato o las trabas legales. El proyecto abre una vía rápida en los Tribunales de Familia para mayores de 80 años.

También permite exigir deudas alimentarias y retener fondos previsionales. En salud, busca acompañar hospitalizaciones y subir las penas por abandono en el Código Penal. Todo requiere respaldo presupuestario y redes públicas de cuidado, revisando casos previos de violencia o abandono.
""".strip()

PROMPT_RETRO_ANTI = (
    "Retrotraduce este texto español: pásalo a inglés llano y luego vuelve a "
    "un español directo y natural, reordenando frases y evitando participios "
    "tras coma (', enfocada en...', ', centrada en...'), 'de manera "
    "oportuna' y giros de informe. Conserva cada dato, cifra, nombre, ley y "
    "año. Devuelve SOLO el texto en español, con los mismos párrafos."
)

PROMPT_ESTRUCTURA_ANTI = (
    "Eres un editor en español. Escribe en párrafos continuos de 3 a 4 "
    "oraciones separadas por punto y seguido. Combina frases cortas "
    "(6 a 10 palabras) con frases directas de 12 a 18 palabras. Evita "
    "enumeraciones simétricas de 3 o 4 elementos, cadenas con 'para...' "
    "repetidas y remates con participio o gerundio tras coma. Conserva todos "
    "los datos. Devuelve SOLO el texto."
)

PROMPT_FINAL_BASE_ANTI = (
    "Eres un redactor en español con prosa clara, firme y natural. Escribe "
    "sin sonar a plantilla ni a informe oficial, evitando las fórmulas y "
    "cadencias que QuillBot suele marcar como IA. Entrega SOLO el texto final."
)

PROMPT_FINAL_REGLAS_ANTI = """
OBLIGATORIO:
1. Escribe en párrafos continuos de 3 a 4 oraciones (separados por línea en blanco), alternando frases cortas (6-10 palabras) con oraciones directas de 12 a 18 palabras.
2. Mantén un tono profesional y claro, sin repetir las mismas palabras ni encadenar oraciones largas con "para...", "lo que..." o participios/gerundios tras coma.
3. PROHIBIDO usar: "además", "sin embargo", "no obstante", "por lo tanto", "en definitiva", "en conclusión", "finalmente", "de esta forma", "de esta manera", "esto se debe a que", "esto genera", "esto facilitará", "en su articulado", "respuesta integral", "creciente problemática", "vulnerabilidad profunda", "especial énfasis", "entramado", "diversas dimensiones", "no solo", "sino que también", "es fundamental", "es esencial", "es crucial", "aspecto crucial", "cabe destacar", "situaciones de vulnerabilidad", "mecanismos institucionales", "obligaciones alimenticias", "proceso acelerado", "trámite específico", "se inspira en", "enfocada en", "centrada en", "de manera oportuna", "más rápida y eficaz", "implementa medidas", "lo que agrava", "abarca aspectos", "establece mecanismos", "una preocupación particular".
4. PROHIBIDO cerrar oraciones con gerundio o participio tras coma.
5. Conserva TODOS los nombres propios, cargos, partidos, leyes, códigos, cifras y matices del original.
6. No uses un sustantivo abstracto como sujeto ("El fenómeno presenta...", "La problemática abarca..."): di quién hace qué.
7. No juntes dos sustantivos casi iguales ("el abandono y la desprotección") ni enumeres más de dos elementos seguidos.
8. No cambies el sentido de ninguna idea y usa los términos jurídicos correctos ("procedimiento especial", "pensión de alimentos", "obligación alimentaria").
9. No copies datos, nombres ni frases de la muestra: es solo una referencia de ritmo.

Devuelve SOLO el texto final en español limpio, sin encabezados ni explicaciones."""

PROMPT_CORRECCION_BASE_ANTI = (
    "Eres un corrector anti-IA en español. Corrige los problemas "
    "detectados para bajar la huella que marca QuillBot, manteniendo "
    "párrafos continuos, ritmo variado (frases cortas de 6-10 palabras y "
    "medias de 12-18), sin conectores prohibidos ni participios/gerundios "
    "tras coma. Conserva todos los datos. Devuelve SOLO el texto corregido."
)

PROMPT_DETECTOR_BASE_ANTI = (
    "Eres un editor anti-IA en español. Reescribes oraciones que QuillBot "
    "marca por sonar a plantilla, informe o estructura artificial. Hazlas "
    "directas, naturales y variadas en largo, sin 'además', 'es crucial', "
    "'es esencial', 'de manera oportuna' ni remates con participio o "
    "gerundio tras coma. Conserva todos los datos y nombres. Devuelve SOLO "
    "las líneas reescritas, numeradas igual que la lista."
)



# ---------------------------------------------------------------------------
# Prompts de la v4 (se conservan como referencia)
# ---------------------------------------------------------------------------
MUESTRA_ESTILO_TESIS_V4 = """
Desde esa fecha, pasado el año 1986, la situación se hace insostenible debido al aumento de personas en el campamento, ya que empiezan a llegar familiares de estos pobladores. Las pocas familias que vivían en Lo Garcés en sus primeros años de formación comienzan a recibir a sus parientes como allegados, de manera que la población comienza a crecer. Al pasar los años el número de familias creció en este sector y esto trajo consigo enfermedades y necesidades por parte de los pobladores.

A los pobladores que llegan al campamento no les interesa la calidad de la vivienda, sino instalarse y tratar de tener una vivienda donde puedan dormir. Lo que esperan es que las autoridades regionales les entreguen alguna vivienda básica para poder instalarse con sus familias. Como se dijo en el capítulo anterior, su prioridad es instalarse en los terrenos para poder vivir.

En el caso del campamento Lo Garcés, el agua y la luz son importantes, ya que las casas no cuentan con medidor ni con un suministro propio en cada vivienda. Esto provoca que las condiciones higiénicas de los pobladores sean precarias. Casi todas las viviendas que tienen suministro eléctrico están colgadas de un tendido, lo cual es un peligro para sus habitantes.

Las ciudades han sido tradicionalmente de dos tipos, diseñadas y proyectadas de manera precisa con un orden predeterminado o desarrolladas con un crecimiento espontáneo sin ningún plan preestablecido. De acuerdo con lo anterior, es necesario comprender cómo la ciudad, a través del uso del suelo, caracteriza todavía los mismos tipos de ciudades antes mencionados.
""".strip()

RASGOS_AUTOR_V4 = (
    "ESTILO OBLIGATORIO:\n"
    "- Toma de la muestra solo el tono: sobrio, concreto, de autor chileno. No "
    "copies sus oraciones largas ni sus conectores.\n"
    "- Mezcla oraciones cortas (6 a 11 palabras) con otras medianas. Cada párrafo "
    "lleva al menos una corta. Nunca tres oraciones seguidas del mismo largo.\n"
    "- Ninguna oración pasa de 35 palabras. Si una idea es larga, pártela con punto seguido.\n"
    "- No encadenes ideas con 'Esto se debe a que', 'De esta forma', 'De esta manera', "
    "'Además', 'Finalmente', 'Asimismo', 'Esto genera', 'Esto facilitará'. Pasa a la "
    "siguiente idea con punto seguido, sin muletilla.\n"
    "- Vocabulario concreto. Evita 'garantizar', 'fortalecer', 'integral', "
    "'entramado', 'diversas dimensiones', 'problemática', 'articulación'.\n"
    "- Párrafos de largo desigual."
)

PROMPT_RETRO_V4 = (
    "Retrotraduce este texto español: primero pásalo a inglés llano conservando "
    "cada dato, cifra, nombre, cita y año; luego vuelve al español natural "
    "reordenando las ideas dentro de cada oración y cambiando los conectores. "
    "No resumas ni omitas nada. No uses calcos del inglés. Devuelve SOLO el texto "
    "final en español, con los mismos párrafos que el original."
)

PROMPT_ESTRUCTURA_V4 = (
    "Eres un editor en español chileno. Parte las oraciones largas en dos o tres "
    "más cortas y deja algunas medianas, para que el largo varíe de verdad. "
    "Quita los conectores de informe ('De esta forma', 'De esta manera', 'Además', "
    "'Finalmente', 'Esto se debe a que') y usa punto seguido. Conserva todos los "
    "datos. Devuelve SOLO el texto."
)

PROMPT_FINAL_BASE_V4 = (
    "Eres el autor de la muestra y reescribes este texto con tu propia voz de "
    "académico chileno. Revisa internamente qué suena a plantilla de IA y "
    "entrega SOLO la versión final en párrafos continuos."
)

PROMPT_FINAL_REGLAS_V4 = """
OBLIGATORIO:
1. Mezcla oraciones cortas (6-11 palabras) con medianas; ninguna de más de 35 palabras.
2. Usa verbos simples ("es", "son", "tiene", "pide", "busca") y evita rodeos ("se erige como", "constituye", "cuenta con", "dispone de", "garantizar", "fortalecer", "contemplar", "facilitar").
3. Prohibido: "no solo", "sino que también", "esto se debe a que", "de esta forma", "de esta manera", "además", "asimismo", "finalmente", "esto genera", "en su articulado", "respuesta integral", "creciente problemática", "entramado", "diversas dimensiones", "especial énfasis", "se sugiere que", "es fundamental", "es esencial", "cabe destacar", "juega un papel", "en conclusión", "en resumen", "lo que permite".
4. Ningún gerundio después de coma (", reconociéndolos...", ", generando...").
5. Conserva todos los datos, nombres, cifras y fechas tal cual. No copies datos ni nombres de la muestra.
6. No termines con una moraleja ni un resumen.

Devuelve SOLO el texto final en español limpio, sin explicaciones."""

PROMPT_CORRECCION_BASE_V4 = (
    "Eres un corrector de estilo en español chileno. Corrige solo los problemas "
    "indicados: parte oraciones largas, agrega oraciones cortas (6-11 palabras), "
    "quita conectores de informe y gerundios tras coma. Conserva los párrafos y "
    "todos los datos. Devuelve SOLO el texto corregido."
)

PROMPT_DETECTOR_BASE_V4 = (
    "Eres un editor de estilo en español. Reescribes oraciones sueltas que "
    "suenan a plantilla (frases hechas, gerundios tras coma, 'no solo... "
    "sino...') con la voz sobria de un académico chileno, con una extensión "
    "parecida a la original y conservando la idea y todos los datos. "
    "Devuelves SOLO las oraciones reescritas, una por línea y numeradas "
    "igual que la lista recibida."
)

def con_muestra_v4(prompt_base: str, reglas: str, muestra: str, instruccion_medida: str) -> str:
    return f"""{prompt_base}

MUESTRA DE ESTILO DE REFERENCIA (imita su registro, ritmo y tono):
---
{muestra}
---

{RASGOS_AUTOR_V4}

{instruccion_medida}

{reglas}"""


def instrucciones_de_medida(num_parrafos: int, num_palabras: int, datos_clave: List[str]) -> str:
    datos_str = ", ".join(datos_clave[:15]) if datos_clave else "ninguno específico"
    min_palabras = int(num_palabras * 0.88)
    max_palabras = int(num_palabras * 1.12)
    min_parrafos = max(1, num_parrafos - 1)
    max_parrafos = num_parrafos + 2
    return (
        f"MEDIDA DEL ORIGINAL: {num_parrafos} párrafos y {num_palabras} palabras. "
        f"El resultado debe tener entre {min_parrafos} y {max_parrafos} párrafos "
        f"continuos y una extensión entre {min_palabras} y {max_palabras} palabras. "
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
# Limpieza de caracteres invisibles, comillas, dashes, puntuación y espacios
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
    texto = texto.replace("«", '"').replace("»", '"')
    return texto


def normalizar_dashes(texto: str) -> str:
    # Rangos (1990–2000, págs. 12–15): se conservan como guion simple.
    # Antes quedaban como "1990, 2000" y se perdía el dato.
    texto = re.sub(r"(\d)\s*[\u2013\u2014]\s*(\d)", r"\1-\2", texto)
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
    texto = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", texto)
    # Ya no se quita "_x_" (rompía URLs, correos y nombres_con_guion) ni los
    # corchetes simples (las citas "[12]" quedaban como "12").
    texto = re.sub(r"^#{1,6}\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\s*[-*+•]\s+", "", texto, flags=re.MULTILINE)
    # Solo listas de 1 o 2 dígitos: "2026. El año..." ya no pierde el año.
    texto = re.sub(r"^\d{1,2}\.\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", texto)
    texto = re.sub(r"~~(.+?)~~", r"\1", texto)
    texto = re.sub(r"\[\[(.+?)\]\]", r"\1", texto)
    return texto


def corregir_elisiones(texto: str) -> str:
    # "y" -> "e" ante palabras con sonido inicial /i/ (i-, hi-), salvo diptongo (hielo, hierba).
    texto = re.sub(
        r"\b([yY])(\s+)(?=[hH]?[iíIÍ](?![aeiouáéíóúAEIOUÁÉÍÓÚ]))",
        lambda m: ("E" if m.group(1) == "Y" else "e") + m.group(2),
        texto,
    )
    # "o" -> "u" ante palabras con sonido inicial /o/ (o-, ho-).
    texto = re.sub(
        r"\b([oO])(\s+)(?=[hH]?[oóOÓ])",
        lambda m: ("U" if m.group(1) == "O" else "u") + m.group(2),
        texto,
    )
    return texto


def corregir_puntuacion(texto: str) -> str:
    texto = re.sub(r",\s*,+", ",", texto)
    texto = re.sub(r"[ \t]+([,;:!?.])", r"\1", texto)
    # Espacio tras la puntuación, salvo en cifras (3,5 / 10:30), URLs y signos seguidos.
    texto = re.sub(r"([,;:!?])(?=[^\s\d/\"'»)\]!?.,;:])", r"\1 ", texto)
    texto = re.sub(r"\(\s+", "(", texto)
    texto = re.sub(r"\s+\)", ")", texto)
    return texto


def corregir_espaciado(texto: str) -> str:
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r" *\n *", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


# Solo se borran muletillas cuya eliminación deja la oración gramatical.
# "no solo... sino que también", "es un aspecto crucial" o "de manera más
# eficiente" ya no se borran a ciegas (rompían la frase): los corrige el modelo.
PATRONES_MULETILLAS = [
    r"^\s*Como (?:modelo de lenguaje|IA|asistente)[^.]*\.\s*",
    r"^\s*Claro[,\s]+(?:aquí tienes|con gusto|por supuesto)[^.]*\.\s*",
    r"^\s*Por supuesto[,!]\s*(?:aquí|a continuación|te\b)[^.]*\.\s*",
    r"^\s*Aquí (?:tiene|está|te presento)[^.]*\.\s*",
    r"[ \t]*\bEn conclusión,[ \t]*",
    r"[ \t]*\bEs importante destacar que[ \t]*",
    r"[ \t]*\bCabe mencionar que[ \t]*",
    r"[ \t]*\bEn el mundo actual,[ \t]*",
    r"[ \t]*\bVale la pena mencionar que[ \t]*",
    r"[ \t]*\bPara navegar con éxito en este entorno,[ \t]*",
    r"[ \t]*\bSin embargo, es importante reconocer que[ \t]*",
    r"[ \t]*\bDe esta forma,[ \t]*",
    r"[ \t]*\bDe esta manera,[ \t]*",
    r"[ \t]*\bEsto se debe a que[ \t]*",
    # Los modelos los siguen usando aunque el prompt los prohíba: se quitan
    # en código. Solo al inicio de oración, donde borrarlos no rompe la frase.
    r"(?:(?<=^)|(?<=\n)|(?<=[.!?] ))(?:Finalmente|En consecuencia|Además|Asimismo|Por otro lado|"
    r"En este sentido|De este modo|Por consiguiente|En definitiva|En resumen|Por último|Por eso|"
    r"Desde una perspectiva \w+|Desde un punto de vista \w+),[ \t]*",
]

SUSTITUCIONES_VERBALES = [
    # Frases que QuillBot y ZeroGPT marcaron en tus pruebas. Se cambian en
    # código porque los modelos no respetan las listas largas del prompt.
    (r"\bresulta igualmente importante\b", "también importa"),
    (r"\bresulta (?:fundamental|esencial|crucial|clave)\b", "es clave"),
    (r"\bes (?:fundamental|esencial|crucial)\b", "es clave"),
    (r"\buna problemática compleja\b", "un problema complejo"),
    (r"\buna problemática\b", "un problema"),
    (r"\bla problemática\b", "el problema"),
    (r"\besta problemática\b", "este problema"),
    (r"\bun fenómeno multidimensional\b", "un problema con muchas aristas"),
    (r"\bmecanismos institucionales\b", "herramientas del Estado"),
    (r"\bobligaciones alimenticias\b", "obligaciones de alimentos"),
    (r"\bderechos alimenticios\b", "derecho de alimentos"),
    (r"\bun enfoque integral\b", "una mirada completa"),
    (r"\brespuesta integral\b", "respuesta completa"),
    (r"\ben el entorno familiar\b", "en la familia"),
    (r"\bconstituye\b", "es"),
    # Antes era ("denominad[ao]s?" -> "llamad[ao]s?"): escribía ese texto literal.
    (r"\bdenominad(o|a|os|as)\b", r"llamad\1"),
    # "cuyo propósito es" -> "y busca" rompía la frase ("una ley y busca...").
    (r"\bcuyo propósito es\b", "que busca"),
    (r"\bse plantea como\b", "busca"),
    (r"\bde manera oportuna\b", "a tiempo"),
    (r"\bse inspira en\b", "toma como base"),
    (r"\babarca aspectos\b", "cruza aspectos"),
    (r"(?:(?<=^)|(?<=\n)|(?<=[.!?] ))(?:No obstante|Sin embargo),\s*", "Pero "),
    (r"\bse sugiere que\b", "conviene que"),
    (r"\bcon especial énfasis en\b", "sobre todo en"),
    (r"\bse erige como\b", "es"),
    (r"\bse plantea como\b", "es"),
    (r"\bcuenta con\b", "tiene"),
    (r"\bdispone de\b", "tiene"),
]

_MARCA = "\x00"


def _preservar_mayuscula(original: str, reemplazo: str) -> str:
    if original[:1].isupper():
        return reemplazo[:1].upper() + reemplazo[1:]
    return reemplazo


def _capitalizar_tras_marca(m: "re.Match") -> str:
    previo = m.group(1)
    separador = " " if previo in (".", "!", "?") else ""
    return previo + separador + m.group(2) + m.group(3).upper()


def clean_text(texto: str) -> str:
    if not texto:
        return ""

    texto = limpiar_caracteres_invisibles(texto)
    texto = normalizar_comillas(texto)
    texto = normalizar_dashes(texto)
    texto = normalizar_espacios_unicode(texto)
    texto = normalizar_elipsis(texto)
    texto = eliminar_markdown(texto)

    # Se marca cada muletilla borrada para poder poner mayúscula si quedó
    # al inicio de una oración ("En conclusión, la..." -> "La...").
    for patron in PATRONES_MULETILLAS:
        texto = re.sub(patron, _MARCA, texto, flags=re.IGNORECASE)
    # Antes este patrón se cambiaba por un espacio y se perdía el punto final.
    texto = re.sub(r"\s*, lo que es fundamental[^.]*\.", ".", texto, flags=re.IGNORECASE)
    texto = re.sub(_MARCA + r"(?:[ \t]*" + _MARCA + r")+", _MARCA, texto)
    texto = re.sub(
        r"(^|[.!?])[ \t]*" + _MARCA + r"[ \t]*([¿¡\"(]?)(\w)",
        _capitalizar_tras_marca,
        texto,
        flags=re.MULTILINE,
    )
    texto = texto.replace(_MARCA, " ")

    for patron, reemplazo in SUSTITUCIONES_VERBALES:
        texto = re.sub(
            patron,
            lambda m, r=reemplazo: _preservar_mayuscula(m.group(0), m.expand(r)),
            texto,
            flags=re.IGNORECASE,
        )

    texto = corregir_elisiones(texto)
    texto = corregir_puntuacion(texto)
    texto = corregir_espaciado(texto)
    return texto


# ---------------------------------------------------------------------------
# Análisis lingüístico y auditoría
# ---------------------------------------------------------------------------
ABREVIATURAS = [
    "Sr.", "Sra.", "Srta.", "Dr.", "Dra.", "Lic.", "Ing.", "Prof.", "etc.",
    "p. ej.", "pág.", "págs.", "núm.", "art.", "arts.", "inc.", "Ud.", "Uds.",
    "aprox.", "vol.", "cap.", "ed.", "et al.", "N.°", "Nº.",
]
_MARCA_PUNTO = "\x01"


def extraer_oraciones(texto: str) -> List[str]:
    # Se protegen las abreviaturas: antes "Dr. Pérez" o "etc." partían la oración.
    protegido = texto
    for abr in ABREVIATURAS:
        protegido = re.sub(
            r"(?<!\w)" + re.escape(abr), abr.replace(".", _MARCA_PUNTO), protegido
        )
    oraciones = re.split(r"(?<=[.!?])\s+", protegido)
    return [o.replace(_MARCA_PUNTO, ".").strip() for o in oraciones if o.strip()]


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
    return bool(re.search(r",\s+\w+(?:[aá]ndo|[eé]ndo)(?:lo|la|los|las|se|le|les|nos)?\b", texto))


def detectar_participios_remate(texto: str) -> bool:
    return bool(
        re.search(
            r",\s+(?:centrad[ao]s?|enfocad[ao]s?|orientad[ao]s?|basad[ao]s?|dirigid[ao]s?|vinculad[ao]s?|destinad[ao]s?)\s+(?:en|a|hacia|por)\b",
            texto,
            flags=re.IGNORECASE,
        )
    )


def detectar_cortes_forzados(texto: str) -> bool:
    return bool(
        re.search(
            r"(?:^|[.!?]\s+)(?:Esto es|Ellas son|Ellos son|Ellas involucran|Ellos involucran)\b",
            texto,
            flags=re.IGNORECASE,
        )
    )


def detectar_sujeto_repetido_seguido(texto: str) -> bool:
    oraciones = extraer_oraciones(texto)
    for i in range(len(oraciones) - 1):
        p1 = [w.lower() for w in re.findall(r"\w+", oraciones[i])[:4]]
        p2 = [w.lower() for w in re.findall(r"\w+", oraciones[i + 1])[:4]]
        if len(p1) >= 2 and len(p2) >= 2 and p1[:2] == p2[:2]:
            return True
    return False


def detectar_enumeracion(texto: str) -> bool:
    return bool(re.search(r"\b\w+,\s+\w+\s+y\s+\w+\b", texto))


def detectar_paralelismo_negativo(texto: str) -> bool:
    patrones = [
        r"\bno (?:se trata )?solo\b.+\bsino\b",
        r"\bno es solo\b.+\bes\b",
        r"\bmás que un[ao]?\b.+\bes un[ao]?\b",
    ]
    baja = texto.lower()
    return any(re.search(p, baja) for p in patrones)


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
    "se erige como", "se plantea como", "constituye un testimonio",
    "juega un rol fundamental", "juega un rol crucial", "juega un rol clave",
    "marca un hito", "un antes y un después", "pone de manifiesto",
    "subraya la importancia", "deja una huella imborrable",
    "panorama en constante evolución", "en enclaves", "enclavado",
    "en el corazón de", "los expertos señalan", "diversos estudios indican",
    "en conclusión", "es fundamental", "cabe destacar", "juega un papel",
    "se ha convertido en", "en el ámbito de", "asimismo", "en definitiva",
    "vale la pena mencionar", "es importante señalar", "cabe mencionar",
    "en el mundo actual", "resulta fundamental", "desempeña un papel crucial",
    "en resumen", "cabe señalar", "es crucial", "es esencial",
    "no puede ignorarse", "merece la pena", "vale destacar",
    "en pocas palabras", "en síntesis", "en suma",
    "a modo de conclusión", "para finalizar", "como conclusión",
    "en última instancia", "en términos generales",
    "en efecto", "por supuesto", "indudablemente", "evidentemente",
    "obviamente", "naturalmente", "lógicamente", "en la era digital",
    "en el marco de", "en tal medida que", "dar a entender",
    "hacer hincapié", "tomar en cuenta", "cobrar relevancia",
    "adquirir importancia", "con el advenimiento", "esto se traduce en",
    "para navegar con éxito", "transformando profundamente",
    "herramientas innovadoras", "revolucionando", "aspecto crucial",
    "de esta forma", "de esta manera", "esto se debe a que",
    "esto genera", "esto facilitará", "en su articulado",
    "respuesta integral", "creciente problemática", "vulnerabilidad profunda",
    "especial énfasis", "entramado", "diversas dimensiones",
    "se sugiere que", "garantizar condiciones", "articulación interinstitucional",
    "financiamiento sostenible", "además", "sin embargo", "no obstante",
    "por lo tanto", "finalmente", "la cual garantiza", "lo cual garantiza",
    "situaciones de abandono", "mecanismos institucionales",
    # "procedimiento especial" y "vulneraciones de derechos" son términos
    # jurídicos correctos: vetarlos obligaba a escribir "trámite específico".
    "obligaciones alimenticias", "herramientas de retención",
    "establecimientos hospitalarios", "medidas efectivas",
    "evidencia la urgencia", "problemática con distintas dimensiones",
    "una preocupación principal", "la iniciativa refuerza",
    "una de las medidas más importantes", "otra medida relevante",
    "la implementación de estas medidas", "es importante considerar",
    "desafíos que van más allá", "proceso acelerado", "trámite específico",
    "se inspira en", "enfocada en", "centrada en",
    "de manera oportuna", "más rápida y eficaz", "implementa medidas",
    "lo que agrava", "abarca aspectos", "establece mecanismos",
    "una preocupación particular", "cuyo propósito", "en este contexto",
    "constituye una problemática", "orientada al cumplimiento",
    "estableciendo mecanismos", "destinados a facilitar",
    "por último", "por eso",
]

CONECTORES_MANUAL = [
    "asimismo", "no obstante", "por lo tanto", "sin embargo", "además",
    "en consecuencia", "por consiguiente", "en efecto", "en definitiva",
    "de esta forma", "de esta manera", "finalmente", "cabe destacar",
    "en este contexto",
]


def _compilar_frases(frases: List[str]) -> "re.Pattern":
    # Con límites de palabra: "en suma" ya no coincide dentro de "en sumario".
    alternativas = "|".join(re.escape(f) for f in sorted(frases, key=len, reverse=True))
    return re.compile(r"\b(?:" + alternativas + r")\b", re.IGNORECASE)


PATRON_VETADAS = _compilar_frases(FRASES_VETADAS_IA)
PATRON_CONECTORES = _compilar_frases(CONECTORES_MANUAL)


def auditar_texto(texto: str) -> List[str]:
    problemas: List[str] = []
    oraciones = extraer_oraciones(texto)
    if len(oraciones) < 3:
        return problemas

    if re.search(r",\s*,", texto):
        problemas.append("Comas duplicadas en la puntuación")

    longitudes = [len(o.split()) for o in oraciones]
    cv = calcular_burstiness(texto)

    if cv < RITMO_MINIMO:
        problemas.append(f"Ritmo parejo (CV={cv:.2f} < {RITMO_MINIMO})")

    for i in range(len(longitudes) - 2):
        tramo = longitudes[i:i + 3]
        if max(tramo) - min(tramo) < 4:
            problemas.append("Tres oraciones seguidas de largo casi igual")
            break

    if not any(CORTA_MIN <= l <= CORTA_MAX for l in longitudes):
        problemas.append("Faltan oraciones cortas (<=11 palabras) para romper la cadencia")

    if any(l > LARGO_MAXIMO for l in longitudes):
        problemas.append(f"Oraciones demasiado largas (>{LARGO_MAXIMO} palabras)")

    encontradas = sorted({m.group(0).lower() for m in PATRON_VETADAS.finditer(texto)})
    if encontradas:
        muestra = ", ".join(f"'{f}'" for f in encontradas[:6])
        problemas.append(f"Frases vetadas de IA ({len(encontradas)}): {muestra}")

    if detectar_paralelismo_negativo(texto):
        problemas.append("Paralelismo negativo ('no solo..., sino...')")

    if detectar_gerundios_remate(texto) or detectar_participios_remate(texto):
        problemas.append("Remate con gerundio o participio tras coma")

    if detectar_cortes_forzados(texto):
        problemas.append("Cortes artificiales al inicio ('Esto es...', 'Ellas...')")

    if detectar_sujeto_repetido_seguido(texto):
        problemas.append("Repetición del mismo sujeto al inicio de dos frases seguidas")

    repeticiones_situaciones = len(re.findall(r"\bsituacion(?:es)?\b", texto, flags=re.IGNORECASE))
    if repeticiones_situaciones > 2:
        problemas.append(f"Repetición excesiva de 'situaciones/situación' ({repeticiones_situaciones})")

    if detectar_enumeracion(texto):
        problemas.append("Enumeraciones simétricas de tres elementos")

    inicios = [o.split()[0] for o in oraciones if o.split()]
    art = [i for i in inicios if i in ["El", "La", "Los", "Las", "Se", "Esto"]]
    if len(inicios) >= 4 and (len(art) / len(inicios)) > 0.35:
        problemas.append("Inicios repetitivos (El/La/Los/Las/Se/Esto > 35%)")

    total_conectores = len(PATRON_CONECTORES.findall(texto))
    if total_conectores > 0:
        problemas.append(f"Conectores de informe detectados ({total_conectores})")

    rep_letrica = detectar_repeticion_letrica(texto)
    if rep_letrica:
        peor = max(rep_letrica.items(), key=lambda x: x[1])
        problemas.append(f"Repetición de '{peor[0]}' al inicio ({peor[1]} veces)")

    return problemas


def puntaje_naturalidad(texto: str) -> int:
    """Evalúa qué tan lejos está el texto de los patrones estadísticos de IA (0-100)."""
    oraciones = extraer_oraciones(texto)
    if len(oraciones) < 2:
        return 0
    longitudes = [len(o.split()) for o in oraciones]
    cv = calcular_burstiness(texto)

    p_cv = min(1.0, cv / PERFIL_ANTI_IA["cv_ideal"])
    cortas = sum(1 for l in longitudes if CORTA_MIN <= l <= CORTA_MAX)
    p_cortas = min(1.0, cortas / max(1, len(oraciones) * 0.25))
    vetadas = len(PATRON_VETADAS.findall(texto))
    p_limpio = max(0.0, 1.0 - vetadas * 0.25)
    remates = sum(
        1 for o in oraciones if detectar_gerundios_remate(o) or detectar_participios_remate(o)
    )
    p_remates = max(0.0, 1.0 - remates * 0.35)

    total = 0.35 * p_cv + 0.20 * p_cortas + 0.30 * p_limpio + 0.15 * p_remates
    return round(100 * total)


# Nombre anterior, por compatibilidad.
puntaje_estilo = puntaje_naturalidad


# ---------------------------------------------------------------------------
# Detección de modelos y mapeo modelo -> proveedor
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def detectar_modelos(_version: int = 11) -> Dict[str, List[str]]:
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

            ids_api = {m.get("id", "") for m in modelos_raw}
            # Primero los modelos fijos que siguen existiendo: antes se tomaban
            # los 15 primeros que devolvía la API (en OpenRouter, al azar).
            for mid in MODELOS_FIJOS[prov]:
                if mid in ids_api:
                    modelos_filtrados.append(mid)

            for m in modelos_raw:
                mid = m.get("id", "")
                if not mid or mid in modelos_filtrados:
                    continue
                if not es_modelo_de_texto(mid):
                    continue
                if any(fam in mid.lower() for fam in FAMILIAS_TEXTO):
                    modelos_filtrados.append(mid)

            ordenados = rankear_modelos(modelos_filtrados)
            disponibles[prov] = ordenados[:15] if ordenados else list(MODELOS_FIJOS[prov])

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
@st.cache_resource(show_spinner=False)
def _estado_pausas_compartido() -> Tuple[Dict[str, Dict[str, float]], threading.Lock]:
    # Streamlit re-ejecuta el script en cada interacción. Un dict a nivel de
    # módulo se reiniciaba cada vez y las pausas no duraban nada.
    pausas = {prov: {"cuota": 0.0, "lento": 0.0, "diaria": 0.0} for prov in ORDEN_FALLBACK}
    return pausas, threading.Lock()


PAUSAS, _lock_pausas = _estado_pausas_compartido()


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


def segundos_de_pausa(proveedor: str) -> int:
    with _lock_pausas:
        if proveedor not in PAUSAS:
            return 0
        ahora = time.time()
        p = PAUSAS[proveedor]
        restantes = [
            dur - (ahora - p[tipo])
            for tipo, dur in (("cuota", PAUSA_CUOTA), ("lento", PAUSA_LENTO), ("diaria", PAUSA_DIARIA))
            if p[tipo]
        ]
    return max(0, int(max(restantes, default=0)))


def manejar_error_api(proveedor: str, error: str, codigo: Optional[int] = None) -> None:
    error_lower = error.lower()
    # Clave inválida o sin permiso: no sirve reintentar en cada etapa.
    if codigo in (401, 403):
        registrar_pausa(proveedor, "diaria")
        return
    # El límite diario también llega como 429, así que se revisa primero.
    if any(s in error_lower for s in ("per day", "daily", "(tpd)", "(rpd)")):
        registrar_pausa(proveedor, "diaria")
    elif "429" in error_lower or "rate limit" in error_lower or "quota" in error_lower:
        registrar_pausa(proveedor, "cuota")
    elif "timeout" in error_lower or "timed out" in error_lower:
        registrar_pausa(proveedor, "lento")


def _es_reintentable(e: Exception) -> bool:
    # Un 400/401/404 no se arregla reintentando: se pasa directo al siguiente proveedor.
    if isinstance(e, requests.HTTPError) and e.response is not None:
        codigo = e.response.status_code
        return codigo == 429 or codigo >= 500
    if isinstance(e, (requests.Timeout, requests.ConnectionError)):
        return True
    codigo = getattr(e, "code", None)  # errores del SDK de Gemini
    return isinstance(codigo, int) and (codigo == 429 or codigo >= 500)


_plazo = threading.local()


def fijar_plazo(limite: Optional[float]) -> None:
    _plazo.limite = limite


def tiempo_restante() -> float:
    limite = getattr(_plazo, "limite", None)
    return float("inf") if limite is None else limite - time.time()


def fijar_perfil(perfil: Optional[str]) -> None:
    _plazo.perfil = perfil


def perfil_actual() -> str:
    return getattr(_plazo, "perfil", None) or "profesional"


def en_hilo_con_plazo(func):
    """Los hilos hijos no heredan el plazo ni el perfil: este envoltorio los pasa."""
    limite = getattr(_plazo, "limite", None)
    perfil = getattr(_plazo, "perfil", None)

    def _envuelta(*args, **kwargs):
        fijar_plazo(limite)
        fijar_perfil(perfil)
        return func(*args, **kwargs)
    return _envuelta


class SinTiempo(Exception):
    pass


def timeout_llamada(proveedor: str) -> float:
    restante = tiempo_restante() - 2
    if restante < 6:
        raise SinTiempo("no queda tiempo para otra llamada")
    return min(TIMEOUT_POR_PROVEEDOR.get(proveedor, TIMEOUT), restante)


def limpiar_respuesta_modelo(texto: Optional[str]) -> str:
    # Modelos con razonamiento (Qwen3, DeepSeek R) devuelven <think>...</think>.
    if not texto:
        return ""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    texto = re.sub(r"^.*?</think>", "", texto, flags=re.DOTALL)
    return texto.strip()


def con_retry(func, *args, **kwargs):
    for intento in range(MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            espera = BASE_BACKOFF * (2 ** intento)
            if (intento >= MAX_RETRIES or not _es_reintentable(e)
                    or tiempo_restante() < espera + 15):
                raise
            logger.warning(f"Reintento {intento + 1} en {espera:.1f}s: {e}")
            time.sleep(espera)


def muestreo_para(etapa: str) -> Dict[str, float]:
    if perfil_actual() == "anti":
        return dict(MUESTREO_ANTI_FIEL if etapa in ETAPAS_FIELES else MUESTREO_ANTI)
    return dict(MUESTREO_ETAPA.get(etapa, MUESTREO_ETAPA["final"]))


def temperatura_para(proveedor: str, temperatura: float, etapa: str = "final") -> float:
    """Convierte la temperatura estándar a la escala de cada proveedor."""
    if perfil_actual() == "anti":
        # La final usa la barra lateral; el resto, valores fijos (como la v4).
        # En la final sí se respeta la escala de DeepSeek: su 1,15 equivale a
        # una temperatura baja en su escala (recomienda 1,3-1,5 para redactar).
        if etapa == "final":
            base = temperatura * FACTOR_TEMPERATURA.get(proveedor, 1.0)
            return round(min(base, TEMPERATURA_TOPE.get(proveedor, TEMPERATURA_TOPE_GENERAL)), 2)
        return round(min(TEMPERATURA_ANTI.get(etapa, temperatura), 1.5), 2)
    ajustada = temperatura * FACTOR_TEMPERATURA.get(proveedor, 1.0)
    return round(min(ajustada, TEMPERATURA_TOPE.get(proveedor, TEMPERATURA_TOPE_GENERAL)), 2)


def llamar_openai_compatible(
    proveedor: str,
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    etapa: str = "final",
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
        "temperature": temperatura_para(proveedor, temperature, etapa),
        **muestreo_para(etapa),
        "max_tokens": MAX_TOKENS,
    }

    def _hacer():
        response = requests.post(
            cfg["endpoint"], headers=headers, json=payload,
            timeout=timeout_llamada(proveedor),
        )
        response.raise_for_status()
        eleccion = response.json()["choices"][0]
        texto = limpiar_respuesta_modelo(eleccion["message"].get("content"))
        if eleccion.get("finish_reason") == "length":
            raise ValueError("respuesta cortada por el límite de tokens")
        return texto

    return con_retry(_hacer)


def llamar_gemini(
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    etapa: str = "final",
) -> str:
    api_key = leer_secreto(PROVEEDORES["gemini"]["clave"])
    if not api_key:
        raise ValueError("GEMINI_API_KEY no configurada")

    def _hacer():
        client = genai.Client(
            api_key=api_key,
            http_options={"timeout": int(timeout_llamada("gemini") * 1000)},
        )
        config = {
            "temperature": temperatura_para("gemini", temperature, etapa),
            **muestreo_para(etapa),
            "max_output_tokens": MAX_TOKENS,
            "system_instruction": system_prompt,
        }
        try:
            response = client.models.generate_content(
                model=modelo, contents=user_prompt, config=config
            )
        except Exception as e:
            if "penalty" not in str(e).lower():
                raise
            config.pop("frequency_penalty")
            config.pop("presence_penalty")
            response = client.models.generate_content(
                model=modelo, contents=user_prompt, config=config
            )
        if not response.text:
            raise ValueError("Gemini devolvió una respuesta vacía o bloqueada")
        return limpiar_respuesta_modelo(response.text)

    return con_retry(_hacer)


def llamar_directo(
    prov: str, modelo: str, system_prompt: str, user_prompt: str, temperature: float,
    etapa: str = "final",
) -> str:
    """Una sola llamada a un proveedor y modelo, sin respaldo."""
    cfg = PROVEEDORES[prov]
    if cfg["tipo"] == "openai_compatible":
        resultado = llamar_openai_compatible(prov, modelo, system_prompt, user_prompt, temperature, etapa)
    else:
        resultado = llamar_gemini(modelo, system_prompt, user_prompt, temperature, etapa)
    if not resultado:
        raise ValueError("Respuesta vacía")
    return resultado


def llamar_proveedor(
    proveedor: str,
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    etapa: str = "final",
) -> dict:
    orden = [proveedor] + [p for p in ORDEN_FALLBACK if p != proveedor]
    ultimo_error = None

    for prov in orden:
        if tiempo_restante() < 10:
            ultimo_error = ultimo_error or "Se acabó el tiempo disponible"
            break
        if esta_pausado(prov):
            continue

        cfg = PROVEEDORES[prov]
        if not leer_secreto(cfg["clave"]):
            continue

        modelo_actual = modelo if prov == proveedor else MODELO_POR_PROVEEDOR[prov]

        try:
            resultado = llamar_directo(prov, modelo_actual, system_prompt, user_prompt, temperature, etapa)

            return {
                "texto": resultado,
                "proveedor_usado": cfg["nombre"],
                "modelo_usado": modelo_actual,
                "exito": True,
                "error": None,
            }
        except SinTiempo:
            ultimo_error = "Se acabó el tiempo disponible"
            break
        except Exception as e:
            detalle = str(e)
            codigo = None
            # str(HTTPError) no trae el cuerpo, que es donde dice "per day" o
            # "TPD": sin esto el límite diario nunca se detectaba.
            if isinstance(e, requests.HTTPError) and e.response is not None:
                codigo = e.response.status_code
                detalle += " " + e.response.text[:300]
            ultimo_error = f"{cfg['nombre']}: {detalle}"
            manejar_error_api(prov, detalle, codigo)
            continue

    if not ultimo_error:
        estados = []
        for prov in ORDEN_FALLBACK:
            nombre = PROVEEDORES[prov]["nombre"]
            if not leer_secreto(PROVEEDORES[prov]["clave"]):
                estados.append(f"{nombre}: sin clave")
            elif esta_pausado(prov):
                estados.append(f"{nombre}: en pausa {segundos_de_pausa(prov)} s más")
        ultimo_error = "Ningún proveedor disponible (" + "; ".join(estados) + ")"

    return {
        "texto": "",
        "proveedor_usado": None,
        "modelo_usado": None,
        "exito": False,
        "error": ultimo_error,
    }


# ---------------------------------------------------------------------------
# Evaluación de modelos: cada modelo reescribe un párrafo de prueba y se mide
# tiempo, extensión, cercanía al estilo del autor y hallazgos de auditoría.
# ---------------------------------------------------------------------------
TEXTO_PRUEBA = (
    "En la actualidad, la urbanización espontánea se ha convertido en un fenómeno de gran "
    "relevancia para las ciudades intermedias de Chile. Este proceso no solo transforma el "
    "paisaje urbano, sino que también genera importantes desafíos sociales. Las familias migran "
    "desde zonas rurales buscando mejores oportunidades laborales. Los campamentos surgen en "
    "terrenos sin planificación ni servicios básicos.\n\n"
    "Es fundamental comprender las causas de este fenómeno para diseñar políticas efectivas. "
    "La falta de vivienda asequible impulsa a las familias a ocupar terrenos de manera informal. "
    "Asimismo, la ausencia de servicios básicos afecta la salud y la calidad de vida, generando "
    "condiciones de vulnerabilidad. Los gobiernos locales enfrentan el reto de integrar estos "
    "asentamientos al tejido urbano."
)
MAX_MODELOS_EVALUAR = 8
PLAZO_EVALUACION = 45


@st.cache_resource(show_spinner=False)
def _evaluacion_compartida() -> Dict[str, Any]:
    return {"fecha": 0.0, "resultados": []}


def evaluar_un_modelo(modelo: str, prov: str) -> dict:
    datos = extraer_datos_clave(TEXTO_PRUEBA)
    medida = instrucciones_de_medida(2, contar_palabras(TEXTO_PRUEBA), datos)
    system = con_muestra(PROMPT_FINAL_BASE, PROMPT_FINAL_REGLAS, MUESTRA_RITMO_NATURAL, medida)
    fila = {"modelo": modelo, "proveedor": PROVEEDORES[prov]["nombre"], "segundos": None,
            "cercania": 0, "hallazgos": None, "apto": False, "nota": -999.0, "error": ""}
    inicio = time.time()
    try:
        texto = clean_text(llamar_directo(prov, modelo, system, TEXTO_PRUEBA, TEMPERATURA_FINAL))
    except Exception as e:
        fila["error"] = str(e)[:120]
        return fila
    seg = time.time() - inicio
    hallazgos = len(auditar_texto(texto))
    cercania = puntaje_naturalidad(texto)
    extension_ok = extension_aceptable(TEXTO_PRUEBA, texto)
    fila.update(segundos=round(seg, 1), cercania=cercania, hallazgos=hallazgos,
                apto=extension_ok and seg <= 35)
    # Prioriza parecerse al autor; descuenta lentitud, hallazgos y extensión mala.
    fila["nota"] = cercania - 3 * hallazgos - max(0.0, seg - 12) - (0 if extension_ok else 25)
    if not extension_ok:
        fila["error"] = "cambió demasiado la extensión"
    return fila


def evaluar_modelos(opciones: List[str], mapa_modelos: Dict[str, str]) -> List[dict]:
    # Se prueba el mejor candidato de cada proveedor y luego los siguientes.
    por_prov: Dict[str, List[str]] = {}
    for m in rankear_modelos(opciones):
        prov = resolver_proveedor_de_modelo(m, mapa_modelos)
        if leer_secreto(PROVEEDORES[prov]["clave"]):
            por_prov.setdefault(prov, []).append(m)
    candidatos: List[Tuple[str, str]] = []
    ronda = 0
    while len(candidatos) < MAX_MODELOS_EVALUAR and any(len(v) > ronda for v in por_prov.values()):
        for prov, lista in por_prov.items():
            if len(lista) > ronda and len(candidatos) < MAX_MODELOS_EVALUAR:
                candidatos.append((lista[ronda], prov))
        ronda += 1

    fijar_plazo(time.time() + PLAZO_EVALUACION)
    with ThreadPoolExecutor(max_workers=4) as ex:
        resultados = list(ex.map(en_hilo_con_plazo(lambda c: evaluar_un_modelo(*c)), candidatos))
    fijar_plazo(None)
    resultados.sort(key=lambda r: (r["apto"], r["nota"]), reverse=True)
    return resultados


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
        r"\d+(?:[.,]\d+)*(?:\s*%|\s+(?:mil(?:lones)?|billones)\b)?", texto, re.IGNORECASE
    )
    datos.extend(c.strip() for c in cifras)
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
    temperatura: Optional[float] = None,
) -> dict:
    prompts = {
        "retro": ((PROMPT_RETRO_ANTI if perfil_actual() == "anti" else PROMPT_RETRO), TEMPERATURA_INTERMEDIA),
        "estructura": ((PROMPT_ESTRUCTURA_ANTI if perfil_actual() == "anti" else PROMPT_ESTRUCTURA), TEMPERATURA_INTERMEDIA),
        "final": ((PROMPT_FINAL_BASE_ANTI if perfil_actual() == "anti" else PROMPT_FINAL_BASE), TEMPERATURA_FINAL),
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
    if temperatura is not None and paso == "final":
        temperature = temperatura
    if paso != "final":
        system_prompt = system_base
    elif perfil_actual() == "anti":
        system_prompt = con_muestra(
            system_base, PROMPT_FINAL_REGLAS_ANTI, MUESTRA_ANTI, instruccion_medida
        )
    else:
        system_prompt = con_muestra(
            system_base, PROMPT_FINAL_REGLAS, MUESTRA_RITMO_NATURAL, instruccion_medida
        )
    return llamar_proveedor(proveedor, modelo, system_prompt, texto, temperature, etapa=paso)


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
            "proveedor_usado": None,
            "modelo_usado": None,
            "exito": True,
            "error": None,
            "omitido": "sin problemas que corregir",
        }

    texto_actual = texto
    problemas_actuales = problemas
    ultimo_res: Optional[dict] = None

    for _ in range(MAX_RONDAS_CORRECCION):
        lista = "\n".join(f"- {p}" for p in problemas_actuales)
        prompt_usuario = (
            f"Texto a corregir:\n---\n{texto_actual}\n---\n\n"
            f"Problemas detectados:\n{lista}\n\n"
            f"Longitud original: {longitud_original} palabras. Mantén entre "
            f"{int(longitud_original * 0.88)} y {int(longitud_original * 1.12)} palabras.\n"
            f"Datos obligatorios: {', '.join(datos_clave[:10])}. No pierdas ninguno.\n\n"
            f"Corrige los problemas listados manteniendo párrafos continuos, registro "
            f"profesional y mezclando frases cortas con frases medias."
        )
        res = llamar_proveedor(
            proveedor, modelo, (PROMPT_CORRECCION_BASE_ANTI if perfil_actual() == "anti" else PROMPT_CORRECCION_BASE), prompt_usuario,
            TEMPERATURA_CORRECCION, etapa="correccion",
        )
        if not res["exito"]:
            # Fallar la corrección no detiene el proceso, pero queda registrado.
            return {
                "texto": texto_actual,
                "proveedor_usado": None,
                "modelo_usado": None,
                "exito": True,
                "error": None,
                "omitido": f"falló ({res['error']})",
            }
        ultimo_res = res

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
        "proveedor_usado": ultimo_res["proveedor_usado"] if ultimo_res else None,
        "modelo_usado": ultimo_res["modelo_usado"] if ultimo_res else None,
        "exito": True,
        "error": None,
    }


def extraer_oraciones_problema(texto: str) -> List[str]:
    oraciones = extraer_oraciones(texto)
    problemas: List[str] = []
    for o in oraciones:
        palabras = o.split()
        n = len(palabras)
        if n == 0:
            continue
        if (
            n > (LARGO_MAXIMO_ANTI if perfil_actual() == "anti" else LARGO_MAXIMO)
            or detectar_gerundios_remate(o)
            or detectar_participios_remate(o)
            or detectar_cortes_forzados(o)
            or detectar_enumeracion(o)
            or detectar_paralelismo_negativo(o)
            or PATRON_VETADAS.search(o)
        ):
            problemas.append(o)
    return problemas


def _reemplazar_flexible(texto: str, original: str, nueva: str) -> Tuple[str, bool]:
    if original in texto:
        return texto.replace(original, nueva, 1), True
    partes = texto.split()
    orig_palabras = original.split()
    for idx in range(len(partes) - len(orig_palabras) + 1):
        ventana = " ".join(partes[idx : idx + len(orig_palabras)])
        if ventana.rstrip(".!?,;") == original.rstrip(".!?,;"):
            antes = " ".join(partes[:idx])
            despues = " ".join(partes[idx + len(orig_palabras) :])
            combinado = " ".join(x for x in (antes, nueva, despues) if x)
            return combinado, True
    return texto, False


def reescribir_con_detector(texto: str, proveedor: str, modelo: str) -> dict:
    """Reescribe solo las oraciones problemáticas y las reemplaza dentro del
    texto. Antes se pedía al modelo "reescribe SOLO estas oraciones" y se tomaba
    su respuesta como el texto completo: quedaban 2 o 3 oraciones."""
    sin_cambios = {
        "texto": texto,
        "proveedor_usado": None,
        "modelo_usado": None,
        "exito": True,
        "error": None,
        "omitido": "ninguna oración que reescribir",
    }
    malas = extraer_oraciones_problema(texto)[:10]
    if not malas:
        return sin_cambios

    lista = "\n".join(f"{i}. {o}" for i, o in enumerate(malas, 1))
    prompt_usuario = (
        f"Contexto (no lo reescribas completo):\n---\n{texto}\n---\n\n"
        f"Reescribe con fluidez y naturalidad SOLO estas {len(malas)} "
        f"oraciones para que no suenen a plantilla y el texto no se sienta "
        f"cortado. Quita 'denominada', 'cuyo propósito', 'en este contexto', "
        f"'constituye una problemática', 'estableciendo', 'destinados a', "
        f"'Esto es...', 'Ellas...', conectores prohibidos, enumeraciones "
        f"simétricas, remates con participio o gerundio tras coma y repetición "
        f"de 'situaciones'. Cada oración debe quedar completa, con verbo, con el "
        f"mismo sentido y con los términos jurídicos correctos. Devuelve "
        f"exactamente {len(malas)} líneas numeradas como la lista, sin "
        f"comentarios:\n{lista}"
    )
    res = llamar_proveedor(
        proveedor, modelo, (PROMPT_DETECTOR_BASE_ANTI if perfil_actual() == "anti" else PROMPT_DETECTOR_BASE), prompt_usuario, TEMPERATURA_DETECTOR,
        etapa="detector",
    )
    if not res["exito"]:
        return {**sin_cambios, "omitido": f"falló ({res['error']})"}

    nuevas: Dict[int, str] = {}
    for linea in res["texto"].splitlines():
        m = re.match(r"\s*(\d+)\s*[.)\-:]\s+(.+)", linea)
        if m:
            nuevas[int(m.group(1))] = clean_text(m.group(2))

    resultado = texto
    reemplazadas = 0
    for i, original in enumerate(malas, 1):
        nueva = nuevas.get(i)
        if not nueva:
            continue
        proporcion = contar_palabras(nueva) / max(1, contar_palabras(original))
        if not 0.6 <= proporcion <= 1.6:
            continue
        resultado, ok = _reemplazar_flexible(resultado, original, nueva)
        if ok:
            reemplazadas += 1

    logger.info(f"Detector: {reemplazadas}/{len(malas)} oraciones reescritas")
    if reemplazadas == 0:
        return {**sin_cambios, "omitido": "el modelo no devolvió reemplazos válidos"}
    return {
        "texto": resultado,
        "proveedor_usado": res["proveedor_usado"],
        "modelo_usado": res["modelo_usado"],
        "exito": True,
        "error": None,
    }


# Solo se parten oraciones con un límite natural donde cortar.
PUNTO_DE_CORTE = re.compile(
    r",\s+(?:que|ya que|lo que|lo cual|y|pero|aunque|mientras|porque|pues)\b|;\s|"
    r"\s(?:ya que|porque|pero)\s", re.IGNORECASE)
# Inicios que delatan un corte forzado ("Esto es al ámbito...", "Ellas involucran...").
INICIO_FORZADO = re.compile(
    r"^(?:Esto|Ello|Eso)\s+(?:es|son|era)\b|^(?:Ellas|Ellos|Así)\b", re.IGNORECASE)


def division_valida(original: str, nueva: str) -> bool:
    partes = extraer_oraciones(nueva)
    if len(partes) < 2:
        return False
    for parte in partes:
        if len(parte.split()) < 4 or INICIO_FORZADO.search(parte) or not parte[:1].isupper():
            return False
    # Mismos datos: ninguna cifra ni nombre propio del original puede perderse.
    datos = set(re.findall(r"\d+|\b[A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+)+", original))
    return all(d in nueva for d in datos)


def partir_oraciones(texto: str, proveedor: str, modelo: str) -> dict:
    """Divide las oraciones más largas en una corta y otra media. Es lo que más
    sube la variación (CV): los modelos tienden a escribir todas de 18-25
    palabras. Solo se acepta si el CV mejora."""
    sin_cambios = {
        "texto": texto, "proveedor_usado": None, "modelo_usado": None,
        "exito": True, "error": None, "omitido": "el ritmo ya es variado",
    }
    cv_antes = calcular_burstiness(texto)
    if cv_antes >= RITMO_MINIMO:
        return sin_cambios
    oraciones = extraer_oraciones(texto)
    longitudes = sorted(len(o.split()) for o in oraciones)
    mediana = longitudes[len(longitudes) // 2]
    dos_mas_largas = set(sorted(oraciones, key=lambda o: len(o.split()), reverse=True)[:2])
    # Se parten las de largo MEDIO, no las más largas: las largas aportan la
    # variación; partirlas en dos medianas deja el ritmo igual de parejo.
    # En una prueba con 19 oraciones, partir 6 medianas llevó el CV de 0,26 a
    # 0,46; partir las 6 más largas, solo a 0,36.
    candidatas = sorted(
        (o for o in oraciones
         if len(o.split()) >= 14 and o not in dos_mas_largas and PUNTO_DE_CORTE.search(o)),
        key=lambda o: abs(len(o.split()) - mediana),
    )
    elegidas = candidatas[:max(2, min(7, len(oraciones) // 3))]
    if not elegidas:
        return {**sin_cambios, "omitido": "no hay oraciones largas que partir"}

    lista = "\n".join(f"{i}. {o}" for i, o in enumerate(elegidas, 1))
    prompt_usuario = (
        f"Divide cada oración en dos. Devuelve exactamente {len(elegidas)} líneas "
        f"numeradas, sin comentarios:\n{lista}"
    )
    res = llamar_proveedor(proveedor, modelo, PROMPT_PARTIR_BASE, prompt_usuario,
                           TEMPERATURA_CORRECCION, etapa="correccion")
    if not res["exito"]:
        return {**sin_cambios, "omitido": f"falló ({res['error']})"}

    nuevas: Dict[int, str] = {}
    for linea in res["texto"].splitlines():
        m = re.match(r"\s*(\d+)\s*[.)\-:]\s+(.+)", linea)
        if m:
            nuevas[int(m.group(1))] = clean_text(m.group(2))

    resultado = texto
    partidas = 0
    for i, original in enumerate(elegidas, 1):
        nueva = nuevas.get(i)
        if not nueva or not division_valida(original, nueva):
            continue
        if not 0.8 <= contar_palabras(nueva) / max(1, contar_palabras(original)) <= 1.3:
            continue
        if original in resultado:
            resultado = resultado.replace(original, nueva, 1)
            partidas += 1

    if partidas == 0 or calcular_burstiness(resultado) <= cv_antes:
        return {**sin_cambios, "omitido": "la división no mejoró el ritmo"}
    logger.info(f"Ritmo: {partidas} oraciones partidas, CV {cv_antes:.2f} -> {calcular_burstiness(resultado):.2f}")
    return {
        "texto": resultado, "proveedor_usado": res["proveedor_usado"],
        "modelo_usado": res["modelo_usado"], "exito": True, "error": None,
    }


def ajustar_con_detectores(texto: str, proveedor: str, modelo: str) -> dict:
    gptzero_key = leer_secreto("GPTZERO_API_KEY")
    if not gptzero_key:
        return {
            "texto": texto,
            "proveedor_usado": None,
            "modelo_usado": None,
            "exito": True,
            "error": None,
            "omitido": "sin GPTZERO_API_KEY",
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
                timeout=25,
            )
            if response.status_code == 200:
                docs = response.json().get("documents", [])
                if docs:
                    score_ia = docs[0].get("average_generated_prob", 0.0)
        except Exception as e:
            logger.warning(f"GPTZero error: {e}")

        if score_ia <= 0.25:
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

    etapa_final = {"paso": "final", "proveedor": proveedor_final, "modelo": modelo_final}
    # Segundo candidato con otro modelo: se queda el que más se parezca al autor.
    # El perfil anti usa un solo candidato, como tu archivo.
    if CANDIDATOS_FINAL > 1 and perfil_actual() != "anti":
        for m in pool_modelos:
            if m != modelo_final:
                etapa_final["alt_proveedor"] = resolver_proveedor_de_modelo(m, mapa_modelos)
                etapa_final["alt_modelo"] = m
                break
    plan.append(etapa_final)

    if correccion_auto:
        prov, mod = _elegir(idx)
        plan.append({"paso": "correccion", "proveedor": prov, "modelo": mod})
        idx += 1
        plan.append({"paso": "detector", "proveedor": proveedor_final, "modelo": modelo_final})
        plan.append({"paso": "ritmo", "proveedor": proveedor_final, "modelo": modelo_final})

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


def extension_aceptable(entrada: str, salida: str) -> bool:
    palabras_entrada = contar_palabras(entrada)
    if palabras_entrada == 0:
        return True
    proporcion = contar_palabras(salida) / palabras_entrada
    return EXTENSION_MIN <= proporcion <= EXTENSION_MAX


def ejecutar_etapa(
    texto_actual: str,
    etapa: Dict[str, str],
    instruccion_medida: str,
    datos_clave: List[str],
) -> dict:
    res = None
    for intento in range(2):
        res = _ejecutar_etapa_simple(texto_actual, etapa, instruccion_medida, datos_clave)
        if not res["exito"] or res.get("omitido"):
            return res
        if extension_aceptable(texto_actual, clean_text(res["texto"])):
            return res
        if etapa["paso"] != "final" or tiempo_restante() < 35:
            break
        logger.warning(
            f"Etapa {etapa['paso']} (intento {intento + 1}) cambió la extensión: "
            f"{contar_palabras(texto_actual)} -> {contar_palabras(res['texto'])} palabras"
        )
    return {
        "texto": texto_actual,
        "proveedor_usado": res["proveedor_usado"],
        "modelo_usado": res["modelo_usado"],
        "exito": True,
        "error": None,
        "descartado": True,
    }


def linea_log(paso: str, res: dict) -> str:
    if res.get("omitido"):
        return f"– {paso}: sin cambios ({res['omitido']})"
    if res.get("descartado"):
        return f"↺ {paso}: descartado por cambiar la extensión (se conservó el texto anterior)"
    return f"✓ {paso}: {res['proveedor_usado']} ({res['modelo_usado']})"


def final_mejor_candidato(texto_actual: str, etapa: Dict[str, str], instruccion_medida: str) -> dict:
    candidatos = [(etapa["proveedor"], etapa["modelo"]), (etapa["alt_proveedor"], etapa["alt_modelo"])]
    with ThreadPoolExecutor(max_workers=len(candidatos)) as ex:
        resultados = list(ex.map(
            en_hilo_con_plazo(
                lambda c: procesar_bloque(
                    texto_actual, "final", c[0], c[1], instruccion_medida, etapa.get("temperatura")
                )
            ),
            candidatos,
        ))
    validos = [
        r for r in resultados
        if r["exito"] and extension_aceptable(texto_actual, clean_text(r["texto"]))
    ]
    if not validos:
        exitosos = [r for r in resultados if r["exito"]]
        return exitosos[0] if exitosos else resultados[0]

    def _nota(r: dict) -> Tuple[int, int]:
        limpio = clean_text(r["texto"])
        return (puntaje_naturalidad(limpio), -len(auditar_texto(limpio)))

    mejor = max(validos, key=_nota)
    logger.info("Final: candidatos %s", [(r["modelo_usado"], _nota(r)) for r in validos])
    return mejor


def _ejecutar_etapa_simple(
    texto_actual: str,
    etapa: Dict[str, str],
    instruccion_medida: str,
    datos_clave: List[str],
) -> dict:
    paso = etapa["paso"]
    proveedor = etapa["proveedor"]
    modelo = etapa["modelo"]
    longitud_actual = contar_palabras(texto_actual)

    if paso == "final" and etapa.get("alt_modelo"):
        return final_mejor_candidato(texto_actual, etapa, instruccion_medida)
    if paso in ("retro", "estructura", "final"):
        return procesar_bloque(
            texto_actual, paso, proveedor, modelo, instruccion_medida, etapa.get("temperatura")
        )

    if paso == "correccion":
        problemas = auditar_texto(texto_actual)
        return revisar_bloque(
            texto_actual, proveedor, modelo, problemas, longitud_actual, datos_clave
        )
    if paso == "detector":
        return reescribir_con_detector(texto_actual, proveedor, modelo)
    if paso == "ritmo":
        return partir_oraciones(texto_actual, proveedor, modelo)

    return {
        "texto": texto_actual,
        "proveedor_usado": None,
        "modelo_usado": None,
        "exito": False,
        "error": f"Paso no soportado: {paso}",
    }


class ProcesoCancelado(Exception):
    pass


def verificar_cancelacion(estado: Optional[dict]) -> None:
    if estado and estado.get("cancelar"):
        raise ProcesoCancelado(
            f"Se superó el tiempo máximo de {TIEMPO_MAXIMO_TOTAL} s. "
            "Prueba con menos pasadas o desactiva Modo Profundo."
        )


def ejecutar_plan(
    texto: str,
    plan: List[Dict[str, str]],
    instruccion_medida: str,
    datos_clave: List[str],
    estado: Optional[dict] = None,
    avance=None,
) -> dict:
    """Corre las etapas. Solo la redacción final es obligatoria: si otra etapa
    falla o no alcanza el tiempo, se registra y se sigue con el texto que hay."""
    texto_actual = texto
    log: List[str] = []
    for i, etapa in enumerate(plan):
        paso = etapa["paso"]
        if paso != "final":
            if estado and estado.get("cancelar"):
                log.append(f"⏱ {paso}: omitido (tiempo agotado)")
                continue
            if tiempo_restante() < RESERVA_ETAPA.get(paso, 15):
                log.append(f"⏱ {paso}: omitido para no pasar el tiempo máximo")
                continue
        if avance:
            avance(i, paso)
        res = ejecutar_etapa(texto_actual, etapa, instruccion_medida, datos_clave)
        if not res["exito"]:
            # Si la final falla pero otra etapa ya reescribió el texto, se entrega
            # ese texto con aviso en vez de perder todo el trabajo.
            if paso == "final" and texto_actual == texto:
                return {"texto": texto_actual, "log": log, "exito": False, "error": res["error"]}
            log.append(f"✗ {paso}: falló y se continuó ({str(res['error'])[:120]})")
            continue
        texto_actual = clean_text(res["texto"])
        log.append(linea_log(paso, res))
    return {"texto": texto_actual, "log": log, "exito": True, "error": None}


def procesar_bloque_individual(
    bloque: str,
    plan: List[Dict[str, str]],
    estado: Optional[dict] = None,
    avance=None,
) -> dict:
    # La medida se calcula por bloque. Con la del texto completo, cada bloque
    # intentaba alcanzar la extensión total y el resultado se inflaba.
    datos_clave = extraer_datos_clave(bloque)
    instruccion_medida = instrucciones_de_medida(
        len(extraer_parrafos(bloque)), contar_palabras(bloque), datos_clave
    )
    return ejecutar_plan(bloque, plan, instruccion_medida, datos_clave, estado, avance)


def copia_estructura(original: str, nuevo: str) -> bool:
    """True si el resultado tiene casi las mismas oraciones, del mismo largo y en
    el mismo orden que el original: el modelo solo parafraseó y los detectores
    siguen reconociendo el borrador."""
    lo = [len(o.split()) for o in extraer_oraciones(original)]
    ln = [len(o.split()) for o in extraer_oraciones(nuevo)]
    if len(lo) < 4 or abs(len(lo) - len(ln)) > max(1, len(lo) // 10):
        return False
    parecidas = sum(1 for a, b in zip(lo, ln) if abs(a - b) <= 4)
    return parecidas / min(len(lo), len(ln)) >= 0.7


def _resultado_error(texto: str, log: List[str], inicio: float, error: str) -> dict:
    return {
        "exito": False, "texto": "", "log": log, "duracion": time.time() - inicio,
        "problemas": [], "ritmo_original": calcular_ritmo(texto), "ritmo_final": 0.0,
        "error": error,
    }


def procesar(texto: str, config: dict, estado: dict) -> dict:
    log_pasos: List[str] = []
    inicio_total = time.time()

    modelo_final = config.get("modelo_final", MODELO_POR_PROVEEDOR["groq"])
    mapa_modelos = config.get("mapa_modelos") or construir_mapa_modelos({})
    proveedor_final = config.get("modelo_final_prov") or resolver_proveedor_de_modelo(
        modelo_final, mapa_modelos
    )
    modelos_otros = config.get("proveedores_otros") or list(MODELO_POR_PROVEEDOR.values())

    plan = armar_plan(
        modelos_otros=modelos_otros,
        mapa_modelos=mapa_modelos,
        modo_profundo=config.get("modo_profundo", False),
        romper_estructura=config.get("romper_estructura", False),
        correccion_auto=config.get("correccion_auto", True),
        modelo_distinto=bool(config.get("modelo_distinto", True)),
        pasadas=int(config.get("pasadas", 1)),
        modelo_final=modelo_final,
        proveedor_final=proveedor_final,
    )

    temperatura_final = float(config.get("temperatura_final", TEMPERATURA_FINAL))
    for etapa in plan:
        if etapa["paso"] == "final":
            etapa["temperatura"] = temperatura_final

    bloques = dividir_en_bloques(texto, TAMANO_BLOQUE)

    if len(bloques) > 1:
        estado["paso"] = f"Procesando {len(bloques)} bloques en paralelo..."
        resultados: List[dict] = [{}] * len(bloques)
        with ThreadPoolExecutor(max_workers=min(3, len(bloques))) as executor:
            futures = {
                executor.submit(en_hilo_con_plazo(procesar_bloque_individual), b, plan, estado): i
                for i, b in enumerate(bloques)
            }
            completados = 0
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    resultados[idx] = future.result()
                except Exception as e:
                    resultados[idx] = {"texto": bloques[idx], "log": [], "exito": False, "error": str(e)}
                completados += 1
                estado["progreso"] = min(completados / len(bloques), 0.95)
        for r in resultados:
            if not r["exito"]:
                return _resultado_error(texto, log_pasos, inicio_total, r["error"])
            log_pasos.extend(r["log"])
        texto_actual = "\n\n".join(r["texto"] for r in resultados)
    else:
        def _avance(i: int, paso: str) -> None:
            estado["paso"] = f"Etapa {i + 1}/{len(plan)}: {paso}"
            estado["progreso"] = min(i / len(plan), 0.95)

        r = procesar_bloque_individual(texto, plan, estado, _avance)
        if not r["exito"]:
            return _resultado_error(texto, r["log"], inicio_total, r["error"])
        texto_actual = r["texto"]
        log_pasos = r["log"]

    texto_actual = clean_text(texto_actual)

    # Si el resultado copia la estructura del original (barras del gráfico casi
    # iguales), se fuerza una reestructuración y una nueva redacción final.
    if copia_estructura(texto, texto_actual) and tiempo_restante() > 45:
        estado["paso"] = "El resultado copiaba la estructura: reestructurando..."
        r1 = procesar_bloque(texto_actual, "estructura", proveedor_final, modelo_final)
        if r1["exito"] and extension_aceptable(texto_actual, clean_text(r1["texto"])):
            reestructurado = clean_text(r1["texto"])
            texto_final_extra = reestructurado
            if tiempo_restante() > 25:
                etapa_final = next((e for e in plan if e["paso"] == "final"), {})
                r2 = procesar_bloque(
                    reestructurado, "final", proveedor_final, modelo_final,
                    instrucciones_de_medida(len(extraer_parrafos(texto)), contar_palabras(texto),
                                            extraer_datos_clave(texto)),
                    etapa_final.get("temperatura"),
                )
                if r2["exito"] and extension_aceptable(reestructurado, clean_text(r2["texto"])):
                    texto_final_extra = clean_text(r2["texto"])
            if not copia_estructura(texto, texto_final_extra):
                texto_actual = texto_final_extra
                log_pasos.append("↻ Reestructuración extra: el resultado copiaba la estructura del original")
            else:
                log_pasos.append("– Reestructuración extra: no logró cambiar la estructura")

    # GPTZero solo si hay clave y tiempo: antes se repetía además el detector.
    if (config.get("correccion_auto", True) and leer_secreto("GPTZERO_API_KEY")
            and tiempo_restante() > 40):
        estado["paso"] = "Verificación final con detectores..."
        res = ajustar_con_detectores(texto_actual, proveedor_final, modelo_final)
        nuevo = clean_text(res["texto"])
        if res["exito"] and not res.get("omitido") and extension_aceptable(texto_actual, nuevo):
            texto_actual = nuevo
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
# Gráfico SVG de ritmo, logo, login, cronómetro y botón copiar
# ---------------------------------------------------------------------------
# components.html se dibuja dentro de un iframe: el CSS global no llega ahí,
# por eso el cronómetro y el botón de copiar salían sin estilo.
ESTILO_IFRAME = """<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;600&display=swap');
body { margin: 0; background: transparent;
       font-family: 'Instrument Sans', -apple-system, sans-serif; }
.cronometro-container { background: #171A1F; padding: 1rem; border-radius: 10px;
       border: 1px solid #2A2F38; text-align: center; font-size: 1.2rem;
       font-variant-numeric: tabular-nums; color: #22D3E6; }
.btn-copiar { background: #F2552C; color: #111317; border: none; height: 46px;
       border-radius: 10px; cursor: pointer; margin: 0; width: 100%;
       font: 600 0.95rem 'Instrument Sans', sans-serif;
       transition: background-color 180ms ease-out; }
.btn-copiar:hover { background: #d94820; }
.btn-copiar:focus-visible { outline: 2px solid #22D3E6; outline-offset: 2px; }
.btn-copiar.copiado { background: #22D3E6; color: #0F1114; }
</style>"""


def _html_iframe(contenido: str, alto: int) -> None:
    # components.html está obsoleto desde Streamlit 1.5x; se usa st.iframe
    # cuando existe y se mantiene compatibilidad con versiones anteriores.
    if hasattr(st, "iframe"):
        st.iframe(contenido, height=alto)
    else:
        components.html(contenido, height=alto)


def generar_svg_ritmo(longitudes_orig: List[int], longitudes_fin: List[int]) -> str:
    if not longitudes_orig and not longitudes_fin:
        return '<p class="editor-col-sub">No hay suficientes oraciones para graficar.</p>'

    ancho, alto = 960, 230
    arriba, abajo, margen = 44, 26, 10
    alto_util = alto - arriba - abajo
    n = max(len(longitudes_orig), len(longitudes_fin))
    tope = max(longitudes_orig + longitudes_fin + [30])
    grupo = (ancho - 2 * margen) / n
    barra = max(2.0, min(16.0, grupo * 0.34))
    separacion = max(1.0, barra * 0.2)

    def _rect(x: float, valor: int, color: str, opacidad: str) -> str:
        h = max(alto_util * valor / tope, 3)
        y = arriba + alto_util - h
        return (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{barra:.1f}" height="{h:.1f}" '
            f'fill="{color}" opacity="{opacidad}" rx="2"/>'
        )

    barras = []
    for i in range(n):
        centro = margen + grupo * i + grupo / 2
        if i < len(longitudes_orig):
            barras.append(_rect(centro - barra - separacion / 2, longitudes_orig[i], "#A6ACB6", "0.5"))
        if i < len(longitudes_fin):
            barras.append(_rect(centro + separacion / 2, longitudes_fin[i], "#22D3E6", "1"))

    base = arriba + alto_util
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {ancho} {alto}" '
        f'role="img" aria-label="Palabras por oración: original frente a humanizado">'
        f'<rect x="{margen}" y="8" width="12" height="12" rx="2" fill="#A6ACB6" opacity="0.5"/>'
        f'<text x="{margen + 18}" y="18" font-size="14" fill="#A6ACB6" '
        f'font-family="Instrument Sans, sans-serif">Original</text>'
        f'<rect x="{margen + 96}" y="8" width="12" height="12" rx="2" fill="#22D3E6"/>'
        f'<text x="{margen + 114}" y="18" font-size="14" fill="#A6ACB6" '
        f'font-family="Instrument Sans, sans-serif">Humanizado</text>'
        f'<text x="{ancho - margen}" y="18" font-size="13" fill="#A6ACB6" text-anchor="end" '
        f'font-family="Instrument Sans, sans-serif">máx. {tope} palabras</text>'
        f'{"".join(barras)}'
        f'<line x1="{margen}" y1="{base}" x2="{ancho - margen}" y2="{base}" '
        f'stroke="#2A2F38" stroke-width="1"/>'
        f'<text x="{margen}" y="{alto - 6}" font-size="13" fill="#A6ACB6" '
        f'font-family="Instrument Sans, sans-serif">Oraciones en orden de aparición</text>'
        f'</svg>'
    )


def mostrar_logo(ancho: int = LOGO_SIDEBAR) -> None:
    # Cada st.markdown es un elemento aparte: abrir un <div> en uno y cerrarlo
    # en otro no envuelve nada, así que el centrado nunca se aplicaba.
    st.markdown(
        f'<div class="logo-box"><img src="{LOGO_URL}" width="{ancho}" '
        f'alt="Humanizador pro"></div>',
        unsafe_allow_html=True,
    )


def render_topbar_autor() -> None:
    st.markdown(
        '<div class="topbar-autor">'
        '<div class="topbar-autor__badge"><span class="topbar-autor__punto"></span>Elaborado por Manu</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_encabezado_principal() -> None:
    st.markdown(
        '<div class="hero-brand">'
        '<h1 class="hero-brand__title">Humanizador pro</h1>'
        '<p class="hero-brand__lead">Manuprime</p>'
        '<p class="hero-brand__purpose">'
        'Humanizador pro tiene como propósito ayudarte a depurar y refinar '
        'borradores generados por IA que ya revisaste y estudiaste, '
        'funcionando como un apoyo formativo para mejorar la claridad, el '
        'ritmo y el criterio de tu propia redacción.'
        '</p>'
        '<div class="hero-tip">'
        '<span class="hero-tip__badge">Tip pro — Usa QuillBot como detector:</span>'
        'Si vas a chequear tu texto con un solo detector antes de cerrarlo, '
        'apóyate en el <strong>detector de IA de QuillBot</strong>. Es más '
        'exigente y certero como termómetro de estilo que otros detectores '
        'más permisivos: obliga a limpiar frases de plantilla y cadencias '
        'mecánicas, aunque recuerda siempre que ningún detector reemplaza tu '
        'propia lectura crítica.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_pie_pagina() -> None:
    st.markdown(
        '<footer class="page-footer">'
        '<p>derechos reservados © Humanizador pro, 2026</p>'
        '</footer>',
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def _estado_login_compartido() -> Tuple[Dict[str, float], threading.Lock]:
    # En session_state bastaba con recargar la página para tener 5 intentos nuevos.
    return {"fallos": 0, "bloqueo_hasta": 0.0}, threading.Lock()


def login_screen() -> None:
    render_topbar_autor()
    _, col2, _ = st.columns([1, 3, 1])
    with col2:
        mostrar_logo(LOGO_LOGIN)
        st.markdown('<h1 class="login-title">Humanizador pro</h1>', unsafe_allow_html=True)
        st.markdown(
            '<p class="login-subtitle">Manuprime</p>',
            unsafe_allow_html=True,
        )

        with st.form("form_login", clear_on_submit=False):
            pwd = st.text_input("Contraseña", type="password", key="login_pwd")
            entrar = st.form_submit_button("Ingresar", type="primary", width="stretch")

        if entrar:
            esperada = leer_secreto("APP_PASSWORD")
            intentos, lock = _estado_login_compartido()
            with lock:
                bloqueado_hasta = intentos["bloqueo_hasta"]
            if not esperada:
                st.error(
                    "Falta configurar APP_PASSWORD en los secrets. "
                    "No se permite login con contraseña por defecto."
                )
            elif time.time() < bloqueado_hasta:
                restante = int(bloqueado_hasta - time.time()) + 1
                st.error(f"Demasiados intentos. Espera {restante} s.")
            elif hmac.compare_digest(pwd.encode("utf-8"), esperada.encode("utf-8")):
                with lock:
                    intentos["fallos"] = 0
                st.session_state.logged_in = True
                st.rerun()
            else:
                with lock:
                    intentos["fallos"] += 1
                    if intentos["fallos"] >= LOGIN_MAX_FALLOS:
                        intentos["bloqueo_hasta"] = time.time() + LOGIN_BLOQUEO
                        intentos["fallos"] = 0
                st.error("Contraseña incorrecta")
    render_pie_pagina()


def render_cronometro(start_ts: Optional[float] = None) -> None:
    if start_ts is None:
        start_ts = time.time()
    # Se pasa el tiempo ya transcurrido, no la hora del servidor: si los relojes
    # del servidor y del navegador difieren, el cronómetro marcaba cualquier cosa.
    transcurrido_ms = max(0.0, time.time() - start_ts) * 1000
    html_crono = ESTILO_IFRAME + f"""
    <div id="crono" class="cronometro-container">Tiempo transcurrido: 0:00</div>
    <script>
    var startTs = Date.now() - {transcurrido_ms:.0f};
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
    _html_iframe(html_crono, 80)


def render_boton_copiar(texto: str) -> None:
    js_texto = json.dumps(texto).replace("</", "<\\/")
    html_copiar = ESTILO_IFRAME + (
        '<button id="btnC" class="btn-copiar">Copiar texto humanizado</button>'
        '<script>'
        'document.getElementById("btnC").addEventListener("click", function(){'
        'var t=' + js_texto + ';'
        'var btn = document.getElementById("btnC");'
        'function ok(){'
        'btn.textContent="Copiado";'
        'btn.classList.add("copiado");'
        'setTimeout(function(){'
        'btn.textContent="Copiar texto humanizado";'
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
    _html_iframe(html_copiar, 50)


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
        if st.button("Cerrar sesión", width="stretch"):
            st.session_state.logged_in = False
            st.rerun()

        st.header("Configuración")

        disponibles = detectar_modelos()
        mapa_modelos = construir_mapa_modelos(disponibles)
        opciones, _ = construir_opciones_y_default(disponibles)
        opciones = rankear_modelos(opciones) or opciones
        # El respaldo de cada proveedor pasa a ser su mejor modelo detectado:
        # así no se cae a un ID fijo que ya no existe.
        for prov, lista in disponibles.items():
            mejores = rankear_modelos(lista)
            if mejores:
                MODELO_POR_PROVEEDOR[prov] = mejores[0]

        perfil = st.selectbox(
            "Perfil de redacción",
            options=list(PERFILES),
            format_func=lambda k: PERFILES[k],
            index=0,
            help="Anti-detector: configuración de la v4 (texto menos predecible, "
                 "más entrecortado). Profesional: más formal y fluido, pero los "
                 "detectores lo marcan más.",
        )
        fijar_perfil(perfil)

        evaluacion = _evaluacion_compartida()
        if st.button("Evaluar mis modelos (≈45 s)", width="stretch",
                     help="Cada modelo reescribe un párrafo de prueba. Se elige el "
                          "de texto más natural, rápido y sin errores."):
            with st.spinner("Probando modelos..."):
                evaluacion["resultados"] = evaluar_modelos(opciones, mapa_modelos)
                evaluacion["fecha"] = time.time()
            aptos = [r["modelo"] for r in evaluacion["resultados"] if r["apto"]]
            if aptos:
                st.session_state.sel_modelo_final = aptos[0]
                st.session_state.sel_modelos_otros = aptos[1:3] or aptos[:1]
            st.rerun()

        # Selección por defecto: la evaluación si existe; si no, el ranking.
        aptos = [r["modelo"] for r in evaluacion["resultados"] if r["apto"] and r["modelo"] in opciones]
        base = aptos + [m for m in opciones if m not in aptos]
        if st.session_state.get("sel_modelo_final") not in opciones:
            st.session_state.sel_modelo_final = base[0] if base else None
        if "sel_modelos_otros" not in st.session_state:
            # Familias distintas a la del modelo final: si todos los pasos usan
            # el mismo tipo de modelo, el texto conserva los mismos hábitos.
            def _familia(m: str) -> str:
                return next((f for f in FAMILIAS_TEXTO if f in m.lower()), m)
            usadas = {_familia(base[0])} if base else set()
            otros: List[str] = []
            for m in base[1:]:
                if _familia(m) not in usadas:
                    otros.append(m)
                    usadas.add(_familia(m))
                if len(otros) == 2:
                    break
            st.session_state.sel_modelos_otros = otros or base[1:3]
        st.session_state.sel_modelos_otros = [
            m for m in st.session_state.sel_modelos_otros if m in opciones
        ]

        modelo_final = st.selectbox(
            "Modelo para la redacción final",
            options=opciones,
            key="sel_modelo_final",
        )
        modelo_final_prov = resolver_proveedor_de_modelo(modelo_final, mapa_modelos)

        modelos_otros = st.multiselect(
            "Modelos para los demás pasos",
            options=opciones,
            key="sel_modelos_otros",
        )

        if evaluacion["resultados"]:
            with st.expander("Resultado de la evaluación", expanded=False):
                st.dataframe(
                    [
                        {
                            "Modelo": r["modelo"],
                            "Naturalidad": f"{r['cercania']}%" if r["segundos"] is not None else "—",
                            "Segundos": r["segundos"] if r["segundos"] is not None else "—",
                            "Hallazgos": r["hallazgos"] if r["hallazgos"] is not None else "—",
                            "Apto": "Sí" if r["apto"] else "No",
                            "Nota": r["error"],
                        }
                        for r in evaluacion["resultados"]
                    ],
                    hide_index=True,
                )

        with st.expander("Modelos conectados", expanded=False):
            for prov in ORDEN_FALLBACK:
                cfg = PROVEEDORES[prov]
                if leer_secreto(cfg["clave"]):
                    st.success(f"{cfg['nombre']}: {MODELO_POR_PROVEEDOR[prov]}")
                else:
                    st.error(f"{cfg['nombre']}: Sin clave")

        st.divider()
        temperatura_final = st.slider(
            "Temperatura de la redacción final", min_value=0.80, max_value=1.30,
            value=TEMPERATURA_ANTI["final"] if perfil == "anti" else TEMPERATURA_FINAL,
            step=0.05, key=f"temp_{perfil}",
            help="Más alta = vocabulario menos previsible. Si el texto sale con "
                 "errores o palabras raras, bájala a 1.00-1.05.",
        )
        # En el perfil anti-detector viene activado, como en el archivo que dio 0 %.
        modo_profundo = st.toggle(
            "Modo Profundo (más lento)", value=(perfil == "anti"), key=f"profundo_{perfil}",
        )
        pasadas = st.slider("Pasadas de humanización", min_value=1, max_value=3, value=1)
        modelo_distinto = st.toggle("Un modelo distinto en cada paso", value=True)
        # En el perfil anti-detector viene activado: sin esta etapa el modelo
        # parafrasea oración por oración y conserva la estructura del borrador.
        romper_estructura = st.toggle(
            "Romper estructura de párrafos", value=(perfil == "anti"), key=f"romper_{perfil}",
        )
        correccion_auto = st.toggle("Revisión y corrección automática", value=True)

        st.divider()
        with st.expander("Cómo usar la app"):
            st.markdown(
                f"1. Pega tu texto (máx. {MAX_CARACTERES} caracteres).\n"
                "2. Ajusta la configuración.\n"
                "3. Pulsa **Humanizar texto**.\n"
                "4. Revisa ritmo y auditoría.\n"
                "5. Copia o descarga el resultado."
            )

    render_topbar_autor()
    render_encabezado_principal()

    col_izq, col_der = st.columns(2, gap="large")

    with col_izq:
        st.markdown('<p class="editor-col-label">Texto original</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="editor-col-sub">Pega aquí el texto generado por IA</p>',
            unsafe_allow_html=True,
        )
        texto_entrada = st.text_area(
            "Pega aquí el texto generado por IA",
            label_visibility="collapsed",
            max_chars=MAX_CARACTERES,
            height=440,
            key="texto_entrada",
        )
        st.markdown(
            f'<div class="editor-pie"><span>{contar_palabras(texto_entrada)} palabras</span>'
            f'<span>{len(texto_entrada)} / {MAX_CARACTERES} caracteres</span></div>',
            unsafe_allow_html=True,
        )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            procesar_btn = st.button(
                "Humanizar texto",
                type="primary",
                width="stretch",
            )
            # Sin "disabled": st.text_area solo envía el texto al salir del cuadro,
            # así que tras pegar el botón seguía bloqueado hasta hacer clic afuera.
            if procesar_btn and not texto_entrada.strip():
                st.warning("Pega un texto antes de humanizar.")
                procesar_btn = False
        with col_b2:
            if st.button("Limpiar", width="stretch"):
                st.session_state._limpiar_entrada = True
                st.session_state.pop("resultado", None)
                st.session_state.pop("crono_start", None)
                st.rerun()

    with col_der:
        st.markdown('<p class="editor-col-label">Texto humanizado</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="editor-col-sub">Resultado con estilo y ritmo revisados</p>',
            unsafe_allow_html=True,
        )
        if st.session_state.get("resultado"):
            res = st.session_state.resultado
            # En una sola línea: una línea en blanco dentro del bloque HTML lo
            # cerraba para el parser de Markdown y los párrafos se salían de la hoja.
            texto_escapado = html.escape(res["texto"]).replace("\n", "<br>")
            st.markdown(
                f'<div class="hoja-papel">{texto_escapado}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="editor-pie"><span>{contar_palabras(res["texto"])} palabras</span>'
                f'<span>{len(res["texto"])} caracteres</span></div>',
                unsafe_allow_html=True,
            )
            render_boton_copiar(res["texto"])
            st.download_button(
                "Descargar resultado",
                data=res["texto"],
                file_name="texto_humanizado.txt",
                mime="text/plain",
                width="stretch",
            )
            st.markdown(
                '<div class="hero-tip"><span class="hero-tip__badge">Siguiente paso:</span>'
                'revisa este texto en el <strong>detector de IA de QuillBot</strong> antes de '
                'cerrarlo. Si marca frases, corrígelas a mano o ejecuta otra pasada, y '
                'confirma que nombres, cifras y términos jurídicos sigan correctos.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="hoja-papel hoja-papel--vacia">'
                'Aquí aparecerá el texto humanizado.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="editor-pie"><span>0 palabras</span><span>0 caracteres</span></div>',
                unsafe_allow_html=True,
            )

    if st.session_state.get("resultado"):
        res = st.session_state.resultado
        cvf = calcular_ritmo(res["texto"])
        cvo = res["ritmo_original"]
        problemas = res.get("problemas") or []

        st.divider()
        st.subheader("Análisis de ritmo y auditoría")

        def _estado_ritmo(cv: float) -> Tuple[str, str]:
            return ("Ritmo variado", "normal") if cv >= RITMO_MINIMO else ("Ritmo parejo", "off")

        m1, m2, m3, m4 = st.columns(4, gap="medium")
        with m4:
            ce_o = puntaje_naturalidad(res.get("texto_original", ""))
            ce_f = puntaje_naturalidad(res["texto"])
            st.metric(
                "Naturalidad anti-IA",
                f"{ce_f}%",
                delta=f"{ce_f - ce_o:+d} pts vs. original",
                delta_color="normal",
            )
        with m1:
            texto_delta, color = _estado_ritmo(cvo)
            st.metric("CV texto original", f"{cvo:.2f}", delta=texto_delta, delta_color=color)
        with m2:
            texto_delta, color = _estado_ritmo(cvf)
            st.metric("CV texto humanizado", f"{cvf:.2f}", delta=texto_delta, delta_color=color)
        with m3:
            st.metric(
                "Tiempo de procesamiento",
                f"{res['duracion']:.1f} s",
                delta=f"{len(res.get('log', []))} etapas",
                delta_color="off",
            )

        st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

        lo = [len(o.split()) for o in extraer_oraciones(res.get("texto_original", ""))]
        lf = [len(o.split()) for o in extraer_oraciones(res["texto"])]
        st.markdown(
            '<div class="audit-panel">'
            '<div class="audit-panel__header">'
            '<h3 class="audit-panel__title">Variación rítmica</h3>'
            '<span class="audit-panel__meta">Palabras por oración</span>'
            '</div>'
            f'{generar_svg_ritmo(lo, lf)}'
            '</div>',
            unsafe_allow_html=True,
        )

        if problemas:
            items_html = "".join(
                '<li class="audit-item"><span class="audit-item__tag">Ajuste</span>'
                f'<span>{html.escape(p)}</span></li>'
                for p in problemas
            )
            cuerpo = f'<ul class="audit-list">{items_html}</ul>'
        else:
            cuerpo = (
                '<div class="audit-ok">Sin observaciones críticas de ritmo o '
                'fórmulas de IA en la auditoría.</div>'
            )
        st.markdown(
            '<div class="audit-panel">'
            '<div class="audit-panel__header">'
            '<h3 class="audit-panel__title">Auditoría de estilo</h3>'
            f'<span class="audit-panel__meta">{len(problemas)} hallazgos</span>'
            '</div>'
            f'{cuerpo}'
            '</div>',
            unsafe_allow_html=True,
        )
        if problemas:
            st.caption(
                "Cada hallazgo es un rasgo que los detectores asocian a texto de IA. "
                "Puedes corregirlo a mano o ejecutar otra pasada."
            )

        if st.session_state.get("historial"):
            with st.expander("Historial de pasadas (anota aquí el % de QuillBot)", expanded=True):
                st.caption(
                    "Un solo resultado no basta: pasa el mismo texto 2 o 3 veces con la "
                    "misma configuración, anota el % de QuillBot de cada una y cambia una "
                    "sola cosa a la vez (modelo o temperatura)."
                )
                editado = st.data_editor(
                    st.session_state.historial, hide_index=True, key="editor_historial",
                    disabled=["Pasada", "Perfil", "Modelo final", "Temperatura", "Naturalidad", "CV"],
                    column_config={"QuillBot %": st.column_config.NumberColumn(min_value=0, max_value=100)},
                )
                st.session_state.historial = list(editado)

        with st.expander("Registro de proveedores y modelos"):
            for linea in res.get("log", []):
                st.markdown(
                    f'<div class="log-line">{html.escape(linea)}</div>',
                    unsafe_allow_html=True,
                )

    if procesar_btn and not st.session_state.get("proceso"):
        config = {
            "modo_profundo": modo_profundo,
            "pasadas": pasadas,
            "modelo_distinto": modelo_distinto,
            "romper_estructura": romper_estructura,
            "correccion_auto": correccion_auto,
            "temperatura_final": temperatura_final,
            "perfil": perfil,
            "modelo_final": modelo_final,
            "modelo_final_prov": modelo_final_prov,
            "proveedores_otros": modelos_otros,
            "mapa_modelos": mapa_modelos,
        }
        texto_proceso = texto_entrada.strip()
        estado = {
            "paso": "Iniciando...", "progreso": 0.0, "res": None, "fin": False,
            "cancelar": False, "texto_original": texto_proceso,
            "perfil": perfil, "temperatura": temperatura_final,
        }

        def worker():
            fijar_plazo(time.time() + TIEMPO_MAXIMO_TOTAL)
            fijar_perfil(config.get("perfil"))
            try:
                estado["res"] = procesar(texto_proceso, config, estado)
            except ProcesoCancelado as e:
                estado["res"] = {"exito": False, "error": str(e)}
            except Exception as e:
                logger.exception("Error inesperado en el proceso")
                estado["res"] = {"exito": False, "error": f"Error inesperado: {e}"}
            finally:
                estado["fin"] = True

        st.session_state.crono_start = time.time()
        # El estado vive en session_state: si el usuario toca algo durante el
        # proceso, el script se reinicia pero retoma el seguimiento en vez de
        # perder el resultado mientras el hilo sigue gastando cuota.
        st.session_state.proceso = estado
        threading.Thread(target=worker, daemon=True).start()

    estado = st.session_state.get("proceso")
    if estado:
        render_cronometro(st.session_state.get("crono_start"))
        barra = st.progress(0)
        estatus = st.empty()
        inicio = st.session_state.get("crono_start", time.time())

        while not estado["fin"]:
            if time.time() - inicio > TIEMPO_MAXIMO_TOTAL + 20:
                estado["cancelar"] = True
                estado["paso"] = "Cancelando (tiempo máximo superado)..."
            barra.progress(min(estado["progreso"], 1.0))
            estatus.markdown(
                f'<div class="status-text">⏳ {html.escape(estado["paso"])} — '
                f'{int(estado["progreso"] * 100)}%</div>',
                unsafe_allow_html=True,
            )
            time.sleep(0.3)

        st.session_state.pop("proceso", None)
        barra.progress(1.0)
        res = estado["res"]
        if res and res.get("exito"):
            estatus.markdown(
                '<div class="status-text">✅ Proceso completado</div>',
                unsafe_allow_html=True,
            )
            res["texto_original"] = estado["texto_original"]
            st.session_state.resultado = res
            modelo_log = next((l.split("(", 1)[-1].rstrip(")") for l in res.get("log", [])
                               if l.startswith("✓ final:")), "—")
            st.session_state.setdefault("historial", []).append({
                "Pasada": len(st.session_state.get("historial", [])) + 1,
                "Perfil": PERFILES.get(estado.get("perfil", ""), "—").split(" (")[0],
                "Modelo final": modelo_log,
                "Temperatura": estado.get("temperatura", "—"),
                "Naturalidad": f"{puntaje_naturalidad(res['texto'])}%",
                "CV": round(calcular_ritmo(res["texto"]), 2),
                "QuillBot %": None,
            })
            st.rerun()
        else:
            estatus.empty()
            error = (res or {}).get("error") or "desconocido"
            st.error(f"❌ Error: {error}")

    render_pie_pagina()


if __name__ == "__main__":
    main()
