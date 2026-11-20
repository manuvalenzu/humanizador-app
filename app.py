import streamlit as st
from google import genai
from google.genai import types
import streamlit.components.v1 as components
import json

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Humanizador Pro", page_icon="✍️", layout="centered")

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
    .login-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        margin-top: 2vh; 
        margin-bottom: 1rem;
    }
    .login-title {
        font-size: 2rem !important;
        color: #F5F5F5;
        margin-bottom: 0.5rem;
        margin-top: 1rem;
    }
    .login-intro {
        font-size: 1rem;
        color: #A0A0A0;
        max-width: 400px;
        line-height: 1.5;
        margin-bottom: 1rem;
    }

    /* CAJA DE CONTRASEÑA */
    .stTextInput>div>div>input {
        background-color: #16181D !important; 
        border: 1px solid #2A2D35 !important;
        color: #E0E0E0 !important;
        border-radius: 8px !important;
        padding: 0.8rem !important;
        text-align: center; 
    }
    .stTextInput>div>div>input:focus {
        border-color: #D97757 !important;
        box-shadow: 0 0 0 1px #D97757 !important;
    }
    
    /* Etiqueta de la contraseña centrada */
    .stTextInput>label {
        display: flex;
        justify-content: center;
        color: #A0A0A0 !important;
    }

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

    [data-testid="stSidebar"] { background-color: #0B0D10; border-right: 1px solid #1F2228; }
    .stSelectbox [data-baseweb="select"] { background-color: #16181D !important; border: 1px solid #2A2D35 !important; color: #E0E0E0 !important; border-radius: 6px !important; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} 
    
    .sidebar-title { font-family: 'Playfair Display', serif; font-size: 1.5rem; color: #E0E0E0; font-weight: 700; line-height: 1.2; margin-bottom: 2rem; }
    .sidebar-title span { color: #D97757; font-size: 2rem; line-height: 0; }

    .signature-container {
        display: flex; justify-content: flex-end; width: 100%;
        margin-top: -2rem; margin-bottom: 1rem; padding-right: 1rem;
    }
    .signature-text {
        font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #FFFFFF; 
        letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.7; 
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. SEGURIDAD Y PANTALLA DE BIENVENIDA ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets.get("APP_PASSWORD", "manu2026"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
        
        # 1. MOSTRAMOS EL LOGO CON LA URL RAW EXACTA
        col_logo1, col_logo2, col_logo3 = st.columns([1, 1, 1])
        with col_logo2:
            url_logo = "https://raw.githubusercontent.com/manuvalenzu/humanizador-app/main/logo.png"
            st.image(url_logo, use_container_width=True)

        # 2. TÍTULO E INTRO
        st.markdown("""
            <div class="login-container">
                <div class="login-title">Humanizador Pro</div>
                <div class="login-intro">
                    Bienvenido. Esta herramienta transforma textos generados por IA en textos naturales, auténticos y con verdadera voz humana.
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # 3. CAJA DE CONTRASEÑA
        col1, col2, col3 = st.columns([1, 2, 1]) 
        with col2:
            st.text_input("Ingresa la contraseña para acceder", type="password", on_change=password_entered, key="password")
        
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("😕 Contraseña incorrecta. Intenta de nuevo.")
            
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
    st.markdown('<div class="sidebar-title">PANEL DE<br>CONTROL<span>.</span></div>', unsafe_allow_html=True)
    st.markdown("### Configuración")
    
    if not MI_API_KEY:
        st.warning("⚠️ Falta la API Key. Por favor, agrégala en los Secretos de Streamlit.")
        MI_API_KEY = st.text_input("API Key de Gemini", type="password")
    
    modelo = st.selectbox(
        "Modelo",
        ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"],
        index=0
    )
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption("Nota: Si el servicio está saturado (Error 503), cambia el modelo.")

# --- ÁREA PRINCIPAL ---
st.markdown('<div class="header-title">Humanizador de Textos</div>', unsafe_allow_html=True)
st.markdown('<div class="header-subtitle">Refina textos generados por IA para darles una voz auténticamente humana.</div>', unsafe_allow_html=True)

# Aviso legal de privacidad
st.info("🔒 Tu texto se procesa con Gemini de Google. Por seguridad, no pegues datos personales ni confidenciales.")

col1, col2 = st.columns(2, gap="medium")

with col1:
    st.markdown("#### Texto Original")
    texto_original = st.text_area("Pega tu texto aquí:", height=400, max_chars=5000, label_visibility="collapsed")

with col2:
    st.markdown("#### Texto Humanizado")
    if "texto_humanizado" not in st.session_state:
        st.session_state["texto_humanizado"] = ""
    
    st.text_area("Resultado:", value=st.session_state["texto_humanizado"], height=400, disabled=True, label_visibility="collapsed")

# --- BOTÓN DE ACCIÓN ---
st.markdown("<br>", unsafe_allow_html=True) 
if st.button("Refinar Texto", use_container_width=True):
    if not texto_original.strip():
        st.warning("Por favor, pega un texto primero.")
    elif not MI_API_KEY:
        st.error("⚠️ Falta la API Key.")
    else:
        with st.spinner("Aplicando reglas editoriales..."):
            try:
                client = genai.Client(api_key=MI_API_KEY)
                
                prompt_sistema = """
                Eres un editor humano experto. Tu tarea es reescribir el texto para que suene 100% natural y humano, adaptándote al tipo de texto que recibas.
                
                REGLAS GENERALES:
                1. Elimina conectores robóticos: "En primera instancia", "Adicionalmente", "En conclusión", "Cabe destacar".
                2. Cambia el verbo ser rebuscado ("se erige como", "constituye") por "es", "tiene".
                3. Rompe la regla de tres.
                4. Varía el ritmo: mezcla frases cortas y largas.
                5. NO cambies datos, cifras ni nombres.
                6. Devuelve SOLO el texto final.

                REGLAS SEGÚN EL TIPO DE TEXTO:
                - Si es un ENSAYO ACADÉMICO o texto formal: Mantén un tono serio, profesional y culto. NO uses coloquialismos como "Ojo", "Spoiler", "Onda", ni uses paréntesis informales. El "ruido humano" debe ser académico (ej. "En mi opinión...", "Resulta interesante notar que...").
                - Si es un texto informal, blog o redes sociales: Inyecta "ruido humano" coloquial (paréntesis, primera persona, micro-dudas).
                """
                
                response = client.models.generate_content(
                    model=modelo,
                    contents=texto_original,
                    config=types.GenerateContentConfig(
                        system_instruction=prompt_sistema,
                        temperature=0.7,
                    )
                )
                
                st.session_state["texto_humanizado"] = response.text
                st.rerun() 
                
            except Exception as e:
                st.error("Ocurrió un error al procesar el texto. Revisa tu conexión o intenta con otro modelo.")
                print(f"Error técnico: {e}")

# --- BOTÓN DE COPIAR ---
if st.session_state["texto_humanizado"]:
    texto_json = json.dumps(st.session_state["texto_humanizado"])
    components.html(
        f"""
        <button id="copyBtn" style="
            background-color: transparent; border: 1px solid #D97757; color: #D97757;
            padding: 10px 16px; border-radius: 6px; cursor: pointer;
            font-family: 'Inter', sans-serif; font-size: 0.95rem; width: 100%; margin-top: 10px;
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
        height=60,
    )