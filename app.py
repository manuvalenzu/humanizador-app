import streamlit as st
from google import genai
from google.genai import types
import streamlit.components.v1 as components
import requests
import json
import re
import unicodedata

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Humanizador Pro", page_icon="✍️", layout="wide")

# ==========================================
# LEE LAS CLAVES DESDE LOS SECRETOS DE STREAMLIT
# ==========================================
try:
    MI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    MI_API_KEY = None

try:
    MI_GROQ_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    MI_GROQ_KEY = None

# ==========================================
# CLIENTE LIGERO PARA LLAMA 3.3 (GROQ API)
# ==========================================
def llamar_llama_groq(api_key, system_prompt, user_text, temperature=0.95):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": temperature,
        "top_p": 0.95,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=45)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# ==========================================
# CAPA A: LÓGICA DE LIMPIEZA (clean_marks + regla §8 de Humanizer)
# ==========================================
INVISIBLE = {
    0x200B: "zero width space", 0x200C: "zero width non-joiner", 0x200D: "zero width joiner",
    0x200E: "left-to-right mark", 0x200F: "right-to-left mark", 0x2060: "word joiner",
    0x2061: "function application", 0x2062: "invisible times", 0x2063: "invisible separator",
    0x2064: "invisible plus", 0xFEFF: "BOM / zero width no-break space", 0x00AD: "soft hyphen",
    0x061C: "arabic letter mark", 0x115F: "hangul choseong filler", 0x1160: "hangul jungseong filler",
    0x3164: "hangul filler", 0xFFA0: "halfwidth hangul filler",
}
BIDI = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | set(range(0x206A, 0x2070))
ODD_SPACES = {0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009,
              0x200A, 0x202F, 0x205F, 0x3000, 0x2028, 0x2029}
NBSP = 0x00A0
QUOTES = {"“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "‚": "'"}

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
            hit("raya de IA (em/en dash)"); out.append(", ")
        elif unicodedata.category(ch) in ("Cc",) and ch not in "\n\r\t":
            hit("carácter de control")
        elif unicodedata.category(ch) == "Co":
            hit("carácter de uso privado")
        else:
            out.append(ch)
        prev = ch; i += 1

    resultado = "".join(out)
    resultado = re.sub(r" +,", ",", resultado)
    resultado = re.sub(r"  +", " ", resultado)
    return resultado.strip(), counts


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
        color: #FFFFFF; font-size: 1rem; font-weight: 600; padding: 0.5rem; 
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
        if st.session_state["password_input"] == st.secrets.get("APP_PASSWORD", "manu2026"):
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
        col_izq, col_centro, col_der = st.columns([1, 2, 1])
        with col_centro:
            col_logo_izq, col_logo_centro, col_logo_der = st.columns([1, 1, 1])
            with col_logo_centro:
                st.image("https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png", use_container_width=True)
            
            st.markdown("""
                <div class="login-title">Humanizador Pro</div>
                <div class="login-intro">
                    Bienvenido. Esta herramienta transforma textos generados por IA en textos naturales, auténticos y con verdadera voz humana.
                </div>
            """, unsafe_allow_html=True)
            
            st.text_input("Ingresa la contraseña para acceder", type="password", key="password_input")
            st.button("Ingresar", on_click=verify_password, use_container_width=True, type="primary")
            
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
    else:
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
        MI_API_KEY = st.text_input("API Key de Gemini", type="password")

    if not MI_GROQ_KEY:
        st.info("💡 Agrega GROQ_API_KEY para activar Llama 3.3 en la Capa B.")
        MI_GROQ_KEY = st.text_input("API Key de Groq (Opcional)", type="password")
    
    st.markdown('<div class="tono-label">Motor activo:</div>', unsafe_allow_html=True)
    if MI_GROQ_KEY:
        st.markdown('<div class="tono-fijo">Híbrido: Llama 3.3 + Gemini</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="tono-fijo">Solo Gemini (Estándar)</div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    usar_retrotraduccion = st.toggle(
        "Capa B: Retrotraducción ES→EN→ES",
        value=True,
        help="Rompe la distribución estadística de tokens usando Llama 3.3 (si hay clave de Groq) antes de la auditoría final."
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("Cerrar Sesión"):
        del st.session_state["password_correct"]
        st.rerun()

st.markdown('<div class="header-title">Humanizador de Textos</div>', unsafe_allow_html=True)
st.markdown('<div class="header-subtitle">Refina textos generados por IA para darles una voz auténticamente humana.</div>', unsafe_allow_html=True)

if "texto_humanizado" not in st.session_state:
    st.session_state["texto_humanizado"] = ""

def limpiar_textos():
    st.session_state["texto_humanizado"] = ""
    st.session_state["input_original_key"] = "" 

col1, col2 = st.columns(2, gap="medium")

with col1:
    st.markdown("#### Texto Original")
    texto_original = st.text_area(
        "Pega tu texto aquí:", 
        height=400, 
        label_visibility="collapsed",
        max_chars=5000,
        key="input_original_key"
    )

with col2:
    st.markdown("#### Texto Humanizado")
    st.text_area(
        "Resultado:", 
        value=st.session_state["texto_humanizado"], 
        height=400, 
        disabled=True, 
        label_visibility="collapsed"
    )

st.markdown("<br>", unsafe_allow_html=True) 

col_btn1, col_btn2 = st.columns([3, 1])

with col_btn1:
    if st.button("Refinar Texto", use_container_width=True, type="primary"):
        if not texto_original.strip():
            st.warning("Por favor, pega un texto primero.")
        elif not MI_API_KEY:
            st.error("⚠️ Falta la API Key de Gemini.")
        else:
            motor_texto = "Llama 3.3 (Capa B) + Gemini (Humanizer)" if MI_GROQ_KEY else "Gemini (Capa B + Humanizer)"
            with st.spinner(f"Procesando con {motor_texto}..."):
                try:
                    client = genai.Client(api_key=MI_API_KEY)

                    # 0. CAPA A EN ENTRADA: Limpiar marcas invisibles antes de procesar
                    texto_base, _ = clean_text(texto_original, quotes=True, keep_nbsp=False, strip_dashes=True)

                    prompt_en = "Translate the following Spanish text into plain, direct English. Preserve all facts, names, dates, and numbers. Output ONLY the English translation."
                    prompt_es = """
                    Traduce este texto al español natural y directo, como si lo escribiera un investigador o columnista.
                    Cambia el orden de las cláusulas y los conectores. Preserva todos los datos, nombres, fechas y cifras sin inventar nada.
                    Devuelve SOLO el texto en español.
                    """
                    prompt_parafrasis = """
                    Reescribe el siguiente texto usando palabras y estructuras sintácticas sustancialmente distintas.
                    Cambia el orden de las cláusulas, los conectores y los límites de las oraciones.
                    Preserva todos los hechos, cifras, nombres y términos técnicos. No agregues ni quites información.
                    Devuelve SOLO el texto reescrito.
                    """

                    # 1. CAPA B: RUPTURA ESTADÍSTICA (Con Llama 3.3 si hay GROQ_API_KEY, si no con Gemini)
                    if MI_GROQ_KEY:
                        if usar_retrotraduccion:
                            texto_en = llamar_llama_groq(MI_GROQ_KEY, prompt_en, texto_base, temperature=0.7)
                            borrador = llamar_llama_groq(MI_GROQ_KEY, prompt_es, texto_en, temperature=0.95)
                        else:
                            borrador = llamar_llama_groq(MI_GROQ_KEY, prompt_parafrasis, texto_base, temperature=1.0)
                    else:
                        if usar_retrotraduccion:
                            resp_en = client.models.generate_content(
                                model="gemini-3.6-flash",
                                contents=texto_base,
                                config=types.GenerateContentConfig(system_instruction=prompt_en, temperature=0.7)
                            )
                            resp_borrador = client.models.generate_content(
                                model="gemini-3.6-flash",
                                contents=resp_en.text,
                                config=types.GenerateContentConfig(system_instruction=prompt_es, temperature=0.95, top_p=0.95)
                            )
                            borrador = resp_borrador.text
                        else:
                            resp_borrador = client.models.generate_content(
                                model="gemini-3.6-flash",
                                contents=texto_base,
                                config=types.GenerateContentConfig(system_instruction=prompt_parafrasis, temperature=1.0, top_p=0.95)
                            )
                            borrador = resp_borrador.text

                    # 2. AUDITORÍA Y REESCRITURA HUMANIZER (Gemini)
                    prompt_humanizer = """
                    Eres un editor humano experto aplicando una auditoría estricta de estilo. Tu trabajo es reescribir el borrador para eliminar TODA huella de redacción de IA, conservando exactamente los mismos hechos, datos, nombres y citas.

                    ELIMINA SIN EXCEPCIÓN ESTOS PATRONES:
                    1. Tríos forzados (§6): Si ves listas de 3 verbos o 3 sustantivos ("diseñar, elaborar y ajustar"; "buscar, ordenar y analizar"), rómpelas. Usa 1 o 2 elementos, o sepáralos en oraciones distintas.
                    2. Contrastes prefabricados (§1): Elimina "No se trata solo de X, sino de Y", "abre posibilidades, pero plantea riesgos". Di el hecho directamente.
                    3. Cierres con moraleja (§2 y §13): Si la última oración suena a conclusión genérica o recomendación ("Ningún avance reemplazará...", "El desafío consiste en..."), bórrala o reemplázala por el último dato concreto.
                    4. Fórmulas vacías y muletillas de IA (§3 y §12): Prohibido usar "A su vez", "Ante este panorama", "entre los que destacan", "que no se pueden ignorar", "cabe destacar", "es fundamental", "fomentar", "abordar", "integral", "clave", "crucial", "mediante", "reside en".
                    5. Gerundios de remate (§15): Elimina cláusulas pegadas al final con gerundio ("..., dejando de lado...", "..., promoviendo la equidad").
                    6. Nominalización y verbos inflados (§18): Usa verbos simples y concretos (es, son, tiene, hace, cambia) y sujetos reales (profesores, estudiantes, universidades) en lugar de conceptos abstractos.
                    7. Rayas y formato (§8 y §19): Cero rayas largas (— o –), cero negritas, cero listas, cero comillas curvas.

                    RITMO HUMANO:
                    - Alterna de forma natural oraciones cortas (6 a 10 palabras) con oraciones medianas y alguna larga. Que no suene mecánico ni simétrico.
                    - Escribe como una persona real que va al grano, no como un folleto institucional.

                    Devuelve ÚNICAMENTE el texto final limpio, sin saludos ni explicaciones.
                    """

                    response = client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=borrador,
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_humanizer,
                            temperature=1.05,
                            top_p=0.95,
                            top_k=64,
                        )
                    )
                    
                    texto_generado = response.text
                    
                    # 3. CAPA A EN SALIDA: Limpieza final determinista
                    texto_limpio, reporte_limpieza = clean_text(
                        texto_generado, quotes=True, keep_nbsp=False, strip_dashes=True
                    )
                    
                    st.session_state["texto_humanizado"] = texto_limpio
                    
                    if reporte_limpieza:
                        st.toast("🧹 Limpieza Capa A aplicada", icon="✅")
                    
                    st.rerun() 
                    
                except Exception as e:
                    st.error("Ocurrió un error al procesar el texto. Revisa tus API Keys o intenta de nuevo en unos minutos.")
                    print(f"Error técnico: {e}")

with col_btn2:
    st.button("Limpiar Textos", on_click=limpiar_textos, use_container_width=True)

if st.session_state["texto_humanizado"]:
    texto_json = json.dumps(st.session_state["texto_humanizado"])
    components.html(
        f"""
        <button id="copyBtn" style="
            background-color: transparent; border: 1px solid #D97757; color: #D97757;
            padding: 10px 16px; border-radius: 6px; cursor: pointer;
            font-family: 'Inter', sans-serif; font-size: 0.95rem; width: 100%; 
            transition: all 0.2s ease;
        ">📋 Copiar Texto Humanizado</button>
        <script>
        document.getElementById('copyBtn').addEventListener('click', function() {{
            const text = {texto_json};
            navigator.clipboard.writeText(text).then(function() {{
                document.getElementById('copyBtn').innerHTML = '✅ ¡Copiado!';
                document.getElementById('copyBtn').style.borderColor = '#4CAF50';
                document.getElementById('copyBtn').style.color = '#4CAF50';
                setTimeout(() => {{ 
                    document.getElementById('copyBtn').innerHTML = '📋 Copiar Texto Humanizado'; 
                    document.getElementById('copyBtn').style.borderColor = '#D97757';
                    document.getElementById('copyBtn').style.color = '#D97757';
                }}, 2000);
            }});
        }});
        </script>
        """,
        height=70, 
    )

st.markdown("""
    <div class="footer-container">
        <div class="footer-disclaimer">
            Humanizador Pro es una herramienta de apoyo diseñada para optimizar y pulir la redacción de textos. Los resultados generados deben ser revisados y validados por el usuario, quien asume la responsabilidad total sobre el contenido final y el uso que le dé.
        </div>
        <div class="footer-copyright">®Humanizadormanu derechos reservados © 2026</div>
    </div>
""", unsafe_allow_html=True)