import streamlit as st
from google import genai
from google.genai import types
import streamlit.components.v1 as components
import json

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Humanizador Pro", page_icon="✍️", layout="wide")

# ==========================================
# LEE LA CLAVE DESDE LOS SECRETOS DE STREAMLIT
# ==========================================
try:
    MI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    MI_API_KEY = None

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@600;700&display=swap');

    .stApp { background-color: #0F1115; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif !important; color: #F5F5F5 !important; font-weight: 600 !important; }
    
    /* ESTILOS PARA LA PANTALLA DE LOGIN */
    .login-title { font-size: 2rem !important; color: #F5F5F5; text-align: center; margin-bottom: 0.5rem; margin-top: 1rem; }
    .login-intro { font-size: 1rem; color: #A0A0A0; text-align: center; max-width: 400px; line-height: 1.5; margin: 0 auto 2rem auto; }

    /* CAJA DE CONTRASEÑA */
    .stTextInput>div>div>input {
        background-color: #16181D !important; border: 1px solid #2A2D35 !important;
        color: #E0E0E0 !important; border-radius: 8px !important;
        padding: 0.8rem !important; text-align: center; 
    }
    .stTextInput>div>div>input:focus { border-color: #D97757 !important; box-shadow: 0 0 0 1px #D97757 !important; }
    
    .stTextInput>label { display: flex; justify-content: center; color: #A0A0A0 !important; }

    /* ESTILOS GENERALES DE LA APP */
    .header-title { font-size: 2.2rem !important; color: #F5F5F5; margin-bottom: 0.2rem; }
    .header-subtitle { font-size: 0.95rem; color: #888888; margin-bottom: 2rem; }
    h4 { font-family: 'Inter', sans-serif !important; color: #E0E0E0 !important; font-weight: 500 !important; font-size: 1rem !important; margin-bottom: 0.5rem !important; letter-spacing: 0.02em; }

    .stTextArea textarea {
        font-family: 'Inter', sans-serif; font-size: 1rem; line-height: 1.6;
        background-color: #16181D !important; border: 1px solid #2A2D35 !important;
        border-radius: 8px !important; color: #E0E0E0 !important;
        box-shadow: none !important; padding: 1.2rem !important;
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
    .stSelectbox [data-baseweb="select"] { background-color: #16181D !important; border: 1px solid #2A2D35 !important; color: #E0E0E0 !important; border-radius: 6px !important; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} 
    
    .sidebar-title { font-family: 'Playfair Display', serif; font-size: 1.5rem; color: #E0E0E0; font-weight: 700; line-height: 1.2; margin-bottom: 2rem; }
    .sidebar-title span { color: #D97757; font-size: 2rem; line-height: 0; }

    .signature-container { display: flex; justify-content: flex-end; width: 100%; margin-top: -2rem; margin-bottom: 1rem; padding-right: 1rem; }
    .signature-text { font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #FFFFFF; letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.7; }

    /* PIE DE PÁGINA (DERECHOS RESERVADOS) */
    .footer-text { text-align: center; color: #666; font-size: 0.8rem; margin-top: 3rem; margin-bottom: 2rem; }

    /* --- RESPONSIVE (MÓVILES) --- */
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

        st.markdown('<div class="footer-text">®Humanizadormanu derechos reservados</div>', unsafe_allow_html=True)
            
        return False
    else:
        return True

if not check_password():
    st.stop()

# ==========================================
# A PARTIR DE AQUÍ ES LA APP NORMAL
# ==========================================

# --- FIRMA SUPERIOR DERECHA ---
st.markdown('<div class="signature-container"><div class="signature-text">Elaborado por Manu</div></div>', unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png", width=60)
    
    st.markdown('<div class="sidebar-title">PANEL DE<br>CONTROL<span>.</span></div>', unsafe_allow_html=True)
    st.markdown("### Configuración")
    
    if not MI_API_KEY:
        st.warning("⚠️ Falta la API Key. Por favor, agrégala en los Secretos de Streamlit.")
        MI_API_KEY = st.text_input("API Key de Gemini", type="password")
    
    st.markdown("#### Elige un modelo API")
    
    # MENÚ ACTUALIZADO: Solo los 2 modelos que mejor funcionan
    opciones_modelos = {
        "gemini-3.5-flash-lite": "El más rápido y evade detectores (Recomendado)",
        "gemini-3.6-flash": "Ideal para textos formales y largos"
    }
    
    modelo_seleccionado = st.selectbox(
        "Modelo:",
        list(opciones_modelos.keys()),
        index=0,
        format_func=lambda x: f"{x} - {opciones_modelos[x]}"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("Cerrar Sesión"):
        del st.session_state["password_correct"]
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.markdown('<div class="header-title">Humanizador de Textos</div>', unsafe_allow_html=True)
st.markdown('<div class="header-subtitle">Refina textos generados por IA para darles una voz auténticamente humana.</div>', unsafe_allow_html=True)

st.info("🔒 Tu texto se procesa con Gemini de Google. Por seguridad, no pegues datos personales ni confidenciales.")

# Inicializamos el estado del texto original y humanizado
if "texto_original" not in st.session_state:
    st.session_state["texto_original"] = ""
if "texto_humanizado" not in st.session_state:
    st.session_state["texto_humanizado"] = ""

# Función para limpiar los textos
def limpiar_textos():
    st.session_state["texto_original"] = ""
    st.session_state["texto_humanizado"] = ""

col1, col2 = st.columns(2, gap="medium")

with col1:
    st.markdown("#### Texto Original")
    texto_original = st.text_area(
        "Pega tu texto aquí:", 
        value=st.session_state["texto_original"],
        height=400, 
        max_chars=5000, 
        label_visibility="collapsed",
        key="input_original"
    )
    st.session_state["texto_original"] = texto_original

with col2:
    st.markdown("#### Texto Humanizado")
    st.text_area(
        "Resultado:", 
        value=st.session_state["texto_humanizado"], 
        height=400, 
        disabled=True, 
        label_visibility="collapsed"
    )

# --- BOTONES DE ACCIÓN ---
st.markdown("<br>", unsafe_allow_html=True) 

col_btn1, col_btn2 = st.columns([3, 1])

with col_btn1:
    if st.button("Refinar Texto", use_container_width=True, type="primary"):
        if not st.session_state["texto_original"].strip():
            st.warning("Por favor, pega un texto primero.")
        elif not MI_API_KEY:
            st.error("⚠️ Falta la API Key.")
        else:
            with st.spinner("Aplicando reglas editoriales..."):
                try:
                    client = genai.Client(api_key=MI_API_KEY)
                    
                    # PROMPT ANTI-DETECTORES (El que funcionó al 0%)
                    prompt_sistema = """
                    Actúa como un estudiante universitario escribiendo un ensayo de forma muy natural. Tu objetivo es reescribir el texto para que pase como 100% humano ante los detectores de IA.
                    Sigue estas reglas estrictamente:
                    1. Rompe la estructura robótica: no uses párrafos perfectos, mezcla frases muy cortas con frases largas.
                    2. Usa conectores informales pero académicos (ej. "A fin de cuentas...", "Ojo, no se trata de...", "Lo cierto es que...").
                    3. Introduce "ruido humano": usa paréntesis para aclaraciones, haz alguna pregunta retórica al lector, y usa la primera persona del plural de vez en cuando (ej. "como sociedad...").
                    4. NUNCA uses estas palabras: "Adicionalmente", "En conclusión", "Es fundamental", "Se erige como", "Cabe destacar", "En resumen".
                    5. Mantén EXACTAMENTE los mismos datos, cifras, nombres y hechos del texto original. No inventes información nueva.
                    6. Devuelve SOLO el texto final, sin saludos ni explicaciones.
                    """
                    
                    response = client.models.generate_content(
                        model=modelo_seleccionado,
                        contents=st.session_state["texto_original"],
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_sistema,
                            temperature=0.85, 
                        )
                    )
                    
                    st.session_state["texto_humanizado"] = response.text
                    st.rerun() 
                    
                except Exception as e:
                    st.error("Ocurrió un error al procesar el texto. Revisa tu conexión o intenta con otro modelo.")
                    print(f"Error técnico: {e}")

with col_btn2:
    st.button("Limpiar Textos", on_click=limpiar_textos, use_container_width=True)

# --- BOTÓN DE COPIAR ---
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

# --- PIE DE PÁGINA (DERECHOS RESERVADOS) ---
st.markdown('<div class="footer-text">®Humanizadormanu derechos reservados</div>', unsafe_allow_html=True)