import streamlit as st
from google import genai
from google.genai import types
import streamlit.components.v1 as components
import requests
import statistics
import time
import json
import re
import hmac
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

    ultimo_error = ""
    for modelo in modelos[:3]:
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
        }
        for intento in range(2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
            except requests.RequestException as e:
                ultimo_error = f"Groq ({modelo}) sin respuesta: {e}"
                break
            # Si el modelo no acepta las penalizaciones, se reintenta sin ellas
            if resp.status_code == 400 and "penalty" in resp.text and intento == 0:
                payload.pop("frequency_penalty", None)
                payload.pop("presence_penalty", None)
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
    r = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", r, flags=re.MULTILINE)  # viñetas
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
]
PATRON_ENUMERACION = re.compile(
    r"\b[\wáéíóúñü]+(?: [\wáéíóúñü]+){0,2}, [\wáéíóúñü]+(?: [\wáéíóúñü]+){0,2},? (?:y|e) [\wáéíóúñü]+",
    re.IGNORECASE,
)
PATRON_GERUNDIO = re.compile(r", ([\wáéíóúñ]+(?:ando|iendo|yendo))\b", re.IGNORECASE)


def dividir_oraciones(texto):
    partes = re.split(r"(?<=[.!?])\s+", texto.strip())
    return [p for p in partes if len(p.split()) >= 2]


def auditar_texto(texto):
    """Devuelve (lista_de_problemas, métricas)."""
    problemas = []
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

    if len(oraciones) >= 5:
        inicios = [o.split()[0].lower().strip(",.") for o in oraciones]
        for palabra in set(inicios):
            if inicios.count(palabra) >= 3 and inicios.count(palabra) / len(inicios) > 0.25:
                problemas.append(f'Muchas oraciones empiezan con "{palabra}". Varía los inicios.')

    if oraciones:
        ultima = oraciones[-1].lower()
        if re.search(r"\b(debe|deben|deberá|necesario|desafío|reto|futuro|oportunidad|clave|en definitiva)\b", ultima):
            problemas.append(f'La última oración suena a moraleja: "{oraciones[-1][:90]}". Termina con un dato concreto.')

    metricas["problemas"] = len(problemas)
    return problemas, metricas

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@600;700&display=swap');

    .stApp { background-color: #0F1115; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif !important; color: #F5F5F5 !important; font-weight: 600 !important; }
    
    [data-testid="collapsedControl"] {
        display: block !important; color: #D97757 !important; 
        background-color: #1E293B !important; border-radius: 50% !important; padding: 5px !important;
    }

    .block-container { padding-top: 2rem !important; }
    
    .login-title { font-size: 2rem !important; color: #F5F5F5; text-align: center; margin-bottom: 0.5rem; margin-top: 1rem; }
    .login-intro { font-size: 1rem; color: #A0A0A0; text-align: center; max-width: 400px; line-height: 1.5; margin: 0 auto 2rem auto; }

    .stTextInput>div>div>input {
        background-color: #16181D !important; border: 1px solid #2A2D35 !important;
        color: #FFFFFF !important; border-radius: 8px !important;
        padding: 0.8rem !important; text-align: center; 
    }
    .stTextInput>div>div>input:focus { border-color: #D97757 !important; box-shadow: 0 0 0 1px #D97757 !important; }
    .stTextInput>label { display: flex; justify-content: center; color: #A0A0A0 !important; }

    .header-title { font-size: 2.2rem !important; color: #F5F5F5; margin-bottom: 0.2rem; margin-top: -1rem; }
    .header-subtitle { font-size: 0.95rem; color: #888888; margin-bottom: 1.5rem; }
    h4 { font-family: 'Inter', sans-serif !important; color: #E0E0E0 !important; font-weight: 500 !important; font-size: 1rem !important; margin-bottom: 0.5rem !important; letter-spacing: 0.02em; }

    .stTextArea textarea, 
    .stTextArea textarea:disabled,
    .stTextArea textarea[disabled] {
        font-family: 'Inter', sans-serif !important; 
        font-size: 1rem !important; 
        line-height: 1.6 !important;
        background-color: #16181D !important; 
        border: 1px solid #2A2D35 !important;
        border-radius: 8px !important; 
        color: #FFFFFF !important; 
        -webkit-text-fill-color: #FFFFFF !important;
        opacity: 1 !important;
        box-shadow: none !important; 
        padding: 1.2rem !important;
    }
    .stTextArea textarea:focus { border-color: #D97757 !important; box-shadow: 0 0 0 1px #D97757 !important; }

    .stButton>button {
        background-color: transparent !important; color: #E0E0E0 !important;
        font-family: 'Inter', sans-serif; font-weight: 500; font-size: 1rem;
        border: 1px solid #2A2D35; border-radius: 6px; padding: 0.6rem 2rem;
        transition: all 0.2s ease; width: 100%;
    }
    .stButton>button:hover { border-color: #D97757 !important; color: #D97757 !important; background-color: rgba(217, 119, 87, 0.05) !important; }

    .stButton>button[kind="primary"] {
        background-color: #D97757 !important; color: #FFFFFF !important; border: none !important;
    }
    .stButton>button[kind="primary"]:hover { background-color: #c56544 !important; }

    [data-testid="stSidebar"] { background-color: #0B0D10; border-right: 1px solid #1F2228; }
    
    .tono-label {
        color: #A0A0A0; font-size: 0.9rem; font-weight: 500; margin-bottom: 0.2rem;
    }
    .tono-fijo {
        color: #FFFFFF; font-size: 0.88rem; font-weight: 600; padding: 0.5rem; 
        background-color: #16181D; border-radius: 6px; border: 1px solid #2A2D35;
    }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} 

    .signature-container { display: flex; justify-content: flex-end; width: 100%; margin-top: -2rem; margin-bottom: 1rem; padding-right: 1rem; }
    .signature-text { font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #FFFFFF; letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.7; }

    .footer-container {
        text-align: center; margin-top: 4rem; padding-top: 1.5rem;
        border-top: 1px solid #1F2228; color: #666; font-size: 0.85rem;
    }
    .footer-disclaimer {
        max-width: 800px; margin: 0 auto 1rem auto;
        color: #888; font-size: 0.8rem; line-height: 1.5; font-style: italic;
    }
    .footer-copyright { color: #FFFFFF; opacity: 0.8; font-size: 0.8rem; }

    @media (max-width: 768px) {
        .header-title { font-size: 1.8rem !important; }
        .stButton>button { padding: 0.8rem; font-size: 1rem; }
        .login-title { font-size: 1.6rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. SEGURIDAD Y PANTALLA DE BIENVENIDA ---
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

    if not st.session_state.get("password_correct"):
        col_izq, col_centro, col_der = st.columns([1, 2, 1])
        with col_centro:
            col_logo_izq, col_logo_centro, col_logo_der = st.columns([1, 1, 1])
            with col_logo_centro:
                st.image("https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png", width="stretch")

            st.markdown("""
                <div class="login-title">Humanizador Pro</div>
                <div class="login-intro">
                    Bienvenido. Esta herramienta transforma textos generados por IA en textos naturales, auténticos y con verdadera voz humana.
                </div>
            """, unsafe_allow_html=True)

            st.text_input("Ingresa la contraseña para acceder", type="password", key="password_input")
            st.button("Ingresar", on_click=verify_password, width="stretch", type="primary")

            if "password_correct" in st.session_state and not st.session_state["password_correct"]:
                st.error("😕 Contraseña incorrecta. Intenta de nuevo.")

        st.markdown("""
            <div class="footer-container">
                <div class="footer-disclaimer">
                    Humanizador Pro es una herramienta de apoyo diseñada para optimizar y pulir la redacción de textos. Los resultados generados deben ser revisados y validados por el usuario, quien asume la responsabilidad total sobre el contenido final y el uso que le dé.
                </div>
                <div class="footer-copyright">®Humanizadormanu derechos reservados © 2026</div>
            </div>
        """, unsafe_allow_html=True)
        return False
    return True

if not check_password():
    st.stop()

# ==========================================
# A PARTIR DE AQUÍ ES LA APP NORMAL
# ==========================================

st.markdown('<div class="signature-container"><div class="signature-text">Elaborado por Manu</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    col_logo_izq, col_logo_centro, col_logo_der = st.columns([1, 1, 1])
    with col_logo_centro:
        st.image("https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png", width=100)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Configuración")

    if not MI_API_KEY:
        st.warning("⚠️ Falta GEMINI_API_KEY en Secretos.")
        MI_API_KEY = st.text_input("API Key de Gemini", type="password").strip()

    if not MI_GROQ_KEY:
        st.info("💡 Agrega GROQ_API_KEY para activar el modo híbrido.")
        MI_GROQ_KEY = st.text_input("API Key de Groq (Opcional)", type="password").strip()

    solo_groq = False
    if MI_GROQ_KEY:
        solo_groq = st.toggle(
            "Modo Solo Groq (Ahorrar cuota Gemini)",
            value=True,
            help="Usa Groq para todo el flujo y evita el límite diario de Gemini. Gemini queda solo como respaldo.",
        )

    st.markdown('<div class="tono-label">Flujo activo:</div>', unsafe_allow_html=True)
    if MI_GROQ_KEY:
        try:
            modelos_disponibles = obtener_modelos_groq_activos(MI_GROQ_KEY)
            modelo_principal = modelos_disponibles[0] if modelos_disponibles else "Groq Auto"
            if solo_groq:
                st.markdown(f'<div class="tono-fijo">Solo Groq ({modelo_principal})</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="tono-fijo">Gemini → {modelo_principal}</div>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="tono-fijo">Groq (Auto) + Gemini</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="tono-fijo">Solo Gemini (Estándar)</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    usar_retrotraduccion = st.toggle(
        "Capa B: Retrotraducción ES→EN→ES",
        value=True,
        help="Desconstruye el texto vía inglés antes de la redacción final.",
    )
    usar_auditoria = st.toggle(
        "Capa C: Auditoría y corrección automática",
        value=True,
        help="Revisa el resultado (ritmo, muletillas, enumeraciones, gerundios, cierre) y lo corrige hasta 2 veces.",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Cerrar Sesión"):
        st.session_state.pop("password_correct", None)
        st.rerun()

st.markdown('<div class="header-title">Humanizador de Textos</div>', unsafe_allow_html=True)
st.markdown('<div class="header-subtitle">Refina textos generados por IA para darles una voz auténticamente humana.</div>', unsafe_allow_html=True)

st.session_state.setdefault("texto_humanizado", "")
st.session_state.setdefault("avisos", [])
st.session_state.setdefault("auditoria", None)

def limpiar_textos():
    st.session_state["texto_humanizado"] = ""
    st.session_state["input_original_key"] = ""
    st.session_state["avisos"] = []
    st.session_state["auditoria"] = None

col1, col2 = st.columns(2, gap="medium")

with col1:
    st.markdown("#### Texto Original")
    texto_original = st.text_area(
        "Pega tu texto aquí:", height=400, label_visibility="collapsed",
        max_chars=5000, key="input_original_key",
    )

with col2:
    st.markdown("#### Texto Humanizado")
    st.text_area(
        "Resultado:", value=st.session_state["texto_humanizado"], height=400,
        disabled=True, label_visibility="collapsed",
    )

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# PROMPTS
# ==========================================
PROMPT_EN = (
    "Translate this Spanish text into blunt, everyday English. "
    "Break long academic sentences into plain statements. Keep every fact, name, number, quote and year. "
    "Output ONLY the English text."
)
PROMPT_ES = (
    "Pasa este texto del inglés al español como apuntes de borrador claros y directos. "
    "Cambia el orden de las ideas dentro de cada párrafo y conserva todos los datos, nombres, cifras, citas y fechas sin inventar nada. "
    "Devuelve SOLO el borrador en español."
)
PROMPT_PARAFRASIS = (
    "Reescribe este texto cambiando el orden de las cláusulas, los conectores y los límites de las oraciones. "
    "Conserva todos los hechos, nombres, fechas, citas y cifras sin inventar nada. Devuelve SOLO el texto."
)
PROMPT_FINAL = """
Eres un ensayista que escribe en español natural, directo y sin adornos de plantilla. Reescribe el borrador conservando todos los hechos, nombres, fechas, cifras y citas, pero eliminando por completo la cadencia de IA.

REGLAS ESTRICTAS (NO ROMPER NINGUNA):
1. DIVISIÓN OBLIGATORIA DE ENUMERACIONES: si el borrador enumera 3 o 4 elementos en una sola frase ("A, B, C y D"), QUEDA PROHIBIDO dejarlos juntos. Repártelos en dos oraciones con verbos distintos.
   - Mal: "Hay sobredependencia tecnológica, desigualdad en el acceso, sesgo algorítmico y riesgos de privacidad."
   - Bien: "El sesgo de los algoritmos y el manejo de datos privados preocupan a las facultades. A eso se le agrega que no todos acceden por igual y algunos alumnos dependen demasiado del programa."
2. PROHIBIDO CERRAR ORACIONES CON PARES SIMÉTRICOS ("...la enseñanza y la investigación"). Di una sola acción concreta o separa en frases con distinto verbo.
3. EXPRESIONES VETADAS (NO USES NINGUNA): "al tiempo que", "a esto se suma", "herramientas como", "a su vez", "ante este panorama", "entre los que destacan", "cabe destacar", "es fundamental", "es crucial", "enfrenta un reto", "enfoque centrado en", "fomentar", "abordar", "mediante", "reside en", "en este sentido", "en este contexto", "por otro lado", "no solo... sino también", "juega un papel", "hoy en día", "cada vez más", "panorama", "paradigma", "potenciar", "integral", "clave para", "en conclusión", "en definitiva".
4. CERO GERUNDIOS DE REMATE: prohibido cerrar una frase con coma + gerundio ("..., promoviendo..."). Usa punto seguido y un verbo conjugado.
5. SIN CIERRE CON MORALEJA: no termines con recomendaciones, desafíos futuros ni "es una oportunidad, pero...". Termina en el último hecho o cita concreta.
6. VOZ REAL: habla de personas concretas (profesores, estudiantes, investigadores) haciendo cosas reales. Usa verbos simples (cambia, sirve, falla, obliga, pide, usa, deja).
7. RITMO IRREGULAR: alterna sin patrón fijo frases muy cortas (5 a 9 palabras) con frases medianas y alguna larga (25 a 35 palabras) con un inciso natural entre comas. Que dos oraciones seguidas casi nunca tengan el mismo largo.
8. INICIOS VARIADOS: no empieces dos oraciones seguidas con la misma palabra ni con el sujeto en la misma posición. A veces abre con un complemento ("En 2023, ...", "Para muchos docentes, ...").
9. VOCABULARIO: prefiere la palabra común sobre la culta ("usar" en vez de "utilizar", "hacer" en vez de "llevar a cabo", "por eso" en vez de "por consiguiente").
10. FORMATO: solo prosa en párrafos. Sin rayas largas (— o –), sin negritas, sin listas, sin títulos y sin comillas curvas.

Devuelve ÚNICAMENTE el texto final en español, sin comentarios ni saludos.
"""
PROMPT_CORRECCION = """
Eres un corrector de estilo. Te paso un texto y una lista de problemas detectados por una revisión automática.
Corrige SOLO esos problemas, con cambios mínimos, y deja intacto todo lo demás.
No agregues información, no elimines datos, cifras, nombres ni citas, y no añadas conclusiones.
Formato: solo prosa en párrafos, sin rayas largas, sin negritas, sin listas.
Devuelve ÚNICAMENTE el texto corregido.
"""

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
            aviso = f"⚡ {errores[0][:160]} Se usó el otro proveedor como respaldo."
            if aviso not in avisos:
                avisos.append(aviso)
        return resultado
    raise RuntimeError(" | ".join(errores) or "No hay ningún proveedor configurado.")


col_btn1, col_btn2 = st.columns([3, 1])

with col_btn1:
    if st.button("Refinar Texto", width="stretch", type="primary"):
        if not texto_original.strip():
            st.warning("Por favor, pega un texto primero.")
        elif not MI_API_KEY and not MI_GROQ_KEY:
            st.error("⚠️ Falta configurar al menos una API Key (Gemini o Groq).")
        else:
            avisos = []
            with st.spinner("Desconstruyendo, redactando y auditando el texto..."):
                try:
                    client = genai.Client(api_key=MI_API_KEY) if MI_API_KEY else None
                    pref_b = "groq" if (solo_groq or client is None) else "gemini"

                    # 0. CAPA A EN ENTRADA
                    texto_base, _ = clean_text(texto_original)

                    # 1. CAPA B: retrotraducción o paráfrasis
                    if usar_retrotraduccion:
                        texto_en, _ = generar(PROMPT_EN, texto_base, 0.7, pref_b, client, avisos)
                        borrador, _ = generar(PROMPT_ES, texto_en, 0.9, pref_b, client, avisos)
                    else:
                        borrador, _ = generar(PROMPT_PARAFRASIS, texto_base, 0.95, pref_b, client, avisos)

                    # 2. REDACCIÓN FINAL (Groq primero si existe: mezclar modelos rompe patrones)
                    pref_final = "groq" if MI_GROQ_KEY else "gemini"
                    texto_generado, modelo_final = generar(PROMPT_FINAL, borrador, 1.0, pref_final, client, avisos)
                    texto_generado, _ = clean_text(texto_generado)

                    # 3. CAPA C: auditoría en código + corrección puntual (máx. 2 rondas)
                    problemas_iniciales, _ = auditar_texto(texto_generado)
                    if usar_auditoria:
                        for ronda in range(2):
                            problemas, _ = auditar_texto(texto_generado)
                            if not problemas:
                                break
                            lista = "\n".join(f"- {p}" for p in problemas)
                            try:
                                corregido, _ = generar(
                                    PROMPT_CORRECCION,
                                    f"PROBLEMAS DETECTADOS:\n{lista}\n\nTEXTO:\n{texto_generado}",
                                    0.8, pref_final, client, avisos,
                                )
                            except Exception as e_corr:
                                avisos.append(f"⚠️ No se pudo hacer la corrección automática ({e_corr}).")
                                break
                            corregido, _ = clean_text(corregido)
                            # Solo se acepta si mejora y no recorta demasiado el texto
                            nuevos, _ = auditar_texto(corregido)
                            if len(nuevos) < len(problemas) and len(corregido) > 0.7 * len(texto_generado):
                                texto_generado = corregido
                            else:
                                break

                    # 4. CAPA A EN SALIDA
                    texto_limpio, _ = clean_text(texto_generado)
                    problemas_finales, metricas = auditar_texto(texto_limpio)

                    st.session_state["texto_humanizado"] = texto_limpio
                    st.session_state["avisos"] = avisos
                    st.session_state["auditoria"] = {
                        "antes": len(problemas_iniciales),
                        "despues": problemas_finales,
                        "metricas": metricas,
                    }
                    st.toast(f"✅ Procesado con {modelo_final}", icon="✨")
                    st.rerun()

                except Exception as e:
                    st.error(f"Error técnico detallado: {e}")

with col_btn2:
    st.button("Limpiar Textos", on_click=limpiar_textos, width="stretch")

for aviso in st.session_state["avisos"]:
    st.warning(aviso)

if st.session_state["texto_humanizado"]:
    # Escapa "</" para que un texto con "</script>" no rompa el HTML del botón
    texto_json = json.dumps(st.session_state["texto_humanizado"]).replace("</", "<\\/")
    html_boton = f"""
        <button id="copyBtn" style="
            background-color: transparent; border: 1px solid #D97757; color: #D97757;
            padding: 10px 16px; border-radius: 6px; cursor: pointer;
            font-family: 'Inter', sans-serif; font-size: 0.95rem; width: 100%;
            transition: all 0.2s ease;
        ">📋 Copiar Texto Humanizado</button>
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
                btn.innerHTML = '✅ ¡Copiado!';
                btn.style.borderColor = '#4CAF50'; btn.style.color = '#4CAF50';
                setTimeout(() => {{
                    btn.innerHTML = '📋 Copiar Texto Humanizado';
                    btn.style.borderColor = '#D97757'; btn.style.color = '#D97757';
                }}, 2000);
            }});
        }});
        </script>
        """
    # st.iframe reemplaza a components.html en Streamlit nuevo; se mantiene respaldo para versiones viejas
    if hasattr(st, "iframe"):
        st.iframe(html_boton, height=70)
    else:
        components.html(html_boton, height=70)

    aud = st.session_state.get("auditoria")
    if aud:
        pendientes = aud["despues"]
        titulo = ("🔎 Auditoría: sin problemas pendientes" if not pendientes
                  else f"🔎 Auditoría: {len(pendientes)} punto(s) para revisar a mano")
        with st.expander(titulo):
            m = aud["metricas"]
            st.markdown(
                f"Problemas antes de corregir: **{aud['antes']}** · después: **{len(pendientes)}** · "
                f"oraciones: **{m.get('oraciones', 0)}** · variación de ritmo: **{m.get('variacion_ritmo', 0)}** "
                "(sobre 0.40 es un ritmo natural)"
            )
            for p in pendientes:
                st.markdown(f"- {p}")
            st.caption("Ningún detector es infalible. Leer el texto y ajustarlo con tus propias palabras sigue siendo lo que más ayuda.")

st.markdown("""
    <div class="footer-container">
        <div class="footer-disclaimer">
            Humanizador Pro es una herramienta de apoyo diseñada para optimizar y pulir la redacción de textos. Los resultados generados deben ser revisados y validados por el usuario, quien asume la responsabilidad total sobre el contenido final y el uso que le dé.
        </div>
        <div class="footer-copyright">®Humanizadormanu derechos reservados © 2026</div>
    </div>
""", unsafe_allow_html=True)
