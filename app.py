import streamlit as st
from google import genai
from google.genai import types
import streamlit.components.v1 as components
import json
import re
import unicodedata

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Humanizador Pro", page_icon="✍️", layout="wide")

# ==========================================
# LEE LA CLAVE DESDE LOS SECRETOS DE STREAMLIT
# ==========================================
try:
    MI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    MI_API_KEY = None

# ==========================================
# LÓGICA DE LIMPIEZA (clean_marks.py)
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

def clean_text(s, quotes=True, keep_nbsp=False):
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
        elif unicodedata.category(ch) in ("Cc",) and ch not in "\n\r\t":
            hit("carácter de control")
        elif unicodedata.category(ch) == "Co":
            hit("carácter de uso privado")
        else:
            out.append(ch)
        prev = ch; i += 1
    return "".join(out), counts


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
        st.warning("⚠️ Falta la API Key. Por favor, agrégala en los Secretos de Streamlit.")
        MI_API_KEY = st.text_input("API Key de Gemini", type="password")
    
    st.markdown('<div class="tono-label">Tono del texto:</div>', unsafe_allow_html=True)
    st.markdown('<div class="tono-fijo">Académico Formal (con Toque Humano)</div>', unsafe_allow_html=True)
    tono_seleccionado = "Académico Formal"
    
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
            st.error("⚠️ Falta la API Key.")
        else:
            with st.spinner("Desconstruyendo estructura y reescribiendo con voz humana..."):
                try:
                    client = genai.Client(api_key=MI_API_KEY)

                    # PASO 1: DESTRUIR LA SINTAXIS DE IA (Extracción pura de hechos)
                    prompt_extraccion = """
                    Extrae únicamente las ideas principales, argumentos, datos y citas de este texto en una lista simple de viñetas cortas y directas. 
                    Elimina cualquier introducción, conclusión, adjetivo innecesario o conector. Solo hechos e ideas crudas.
                    """
                    
                    resp_ideas = client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=texto_original,
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_extraccion,
                            temperature=0.3,
                        )
                    )
                    ideas_crudas = resp_ideas.text

                    # PASO 2: RECONSTRUIR SIN NOMINALIZACIÓN (Anti-QuillBot y Anti-ZeroGPT)
                    prompt_redaccion = """
                    Eres un académico escribiendo una columna de opinión clara y directa. Redacta un texto continuo usando ÚNICAMENTE las ideas de la lista que recibirás.

                    REGLAS OBLIGATORIAS PARA SONAR HUMANO:
                    1. PROHIBIDO NOMINALIZAR: No uses sustantivos abstractos donde cabe un verbo.
                       - Mal: "mediante la integración de sistemas que reconfiguran la gestión"
                       - Bien: "al sumar herramientas que cambian cómo se administra la universidad"
                       - Mal: "reside en la generación involuntaria de datos incorrectos"
                       - Bien: "ocurre cuando el sistema inventa datos falsos sin que el usuario lo note"
                    2. SUJETOS CONCRETOS: Habla de personas (profesores, estudiantes, investigadores, facultades) en lugar de conceptos abstractos ("el enfoque", "los riesgos éticos", "las evaluaciones").
                    3. CERO CONECTORES DE IA: Prohibido usar "mediante", "reside en", "reconfiguran", "abarcan", "junto con", "en lugar de insistir en", "deben reorientarse hacia".
                    4. RITMO NATURAL, NO MECÁNICO: No hagas el patrón obvio de "una frase gigante y una frase de 5 palabras". Usa oraciones medianas (12 a 20 palabras) mezcladas con algunas cortas y alguna más larga que incluya una pausa o aclaración natural.
                    5. SIN CIERRE DE MORALEJA: No termines con frases genéricas ni recomendaciones obvias. Termina en el último dato o argumento.
                    6. FORMATO: Solo prosa limpia. Sin negritas, sin listas y sin comillas curvas.

                    Devuelve SOLO el texto final.
                    """

                    response = client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=f"Ideas a desarrollar:\n{ideas_crudas}",
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_redaccion,
                            temperature=1.0,
                            top_p=0.95,
                            top_k=64,
                        )
                    )
                    
                    texto_generado = response.text
                    
                    texto_limpio, reporte_limpieza = clean_text(texto_generado, quotes=True, keep_nbsp=False)
                    
                    st.session_state["texto_humanizado"] = texto_limpio
                    
                    if reporte_limpieza:
                        st.toast("🧹 Limpieza aplicada", icon="✅")
                    
                    st.rerun() 
                    
                except Exception as e:
                    st.error("Ocurrió un error al procesar el texto. Revisa tu conexión o intenta de nuevo en unos minutos.")
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