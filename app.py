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
    
    /* ARREGLO PARA EL BOTÓN DE ABRIR LA BARRA LATERAL */
    [data-testid="collapsedControl"] {
        display: block !important;
        color: #D97757 !important; 
        background-color: #1E293B !important;
        border-radius: 50% !important;
        padding: 5px !important;
    }

    .block-container { padding-top: 2rem !important; }
    
    /* ESTILOS PARA LA PANTALLA DE LOGIN */
    .login-title { font-size: 2rem !important; color: #F5F5F5; text-align: center; margin-bottom: 0.5rem; margin-top: 1rem; }
    .login-intro { font-size: 1rem; color: #A0A0A0; text-align: center; max-width: 400px; line-height: 1.5; margin: 0 auto 2rem auto; }

    /* CAJA DE CONTRASEÑA */
    .stTextInput>div>div>input {
        background-color: #16181D !important; border: 1px solid #2A2D35 !important;
        color: #FFFFFF !important; border-radius: 8px !important;
        padding: 0.8rem !important; text-align: center; 
    }
    .stTextInput>div>div>input:focus { border-color: #D97757 !important; box-shadow: 0 0 0 1px #D97757 !important; }
    
    .stTextInput>label { display: flex; justify-content: center; color: #A0A0A0 !important; }

    /* ESTILOS GENERALES DE LA APP */
    .header-title { font-size: 2.2rem !important; color: #F5F5F5; margin-bottom: 0.2rem; margin-top: -1rem; }
    .header-subtitle { font-size: 0.95rem; color: #888888; margin-bottom: 1.5rem; }
    h4 { font-family: 'Inter', sans-serif !important; color: #E0E0E0 !important; font-weight: 500 !important; font-size: 1rem !important; margin-bottom: 0.5rem !important; letter-spacing: 0.02em; }

    /* CAJAS DE TEXTO (LETRAS BLANCAS) */
    .stTextArea textarea {
        font-family: 'Inter', sans-serif; font-size: 1rem; line-height: 1.6;
        background-color: #16181D !important; border: 1px solid #2A2D35 !important;
        border-radius: 8px !important; color: #FFFFFF !important; 
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

    /* --- AJUSTES DE LA BARRA LATERAL --- */
    [data-testid="stSidebar"] { background-color: #0B0D10; border-right: 1px solid #1F2228; }
    
    /* RADIO BUTTONS (LETRAS BLANCAS) */
    .stRadio label p { color: #FFFFFF !important; font-size: 0.95rem !important; }
    
    /* CUADRO DE MOTOR PERSONALIZADO */
    .motor-box {
        background-color: #1E293B; border-left: 4px solid #3B82F6; 
        padding: 1rem; border-radius: 6px; margin-top: 0.5rem; margin-bottom: 1.5rem;
    }
    .motor-box strong { color: #E0E0E0; font-size: 0.95rem; }
    .motor-box p { color: #9CA3AF; font-size: 0.85rem; margin-top: 0.3rem; margin-bottom: 0; font-style: italic; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} 

    .signature-container { display: flex; justify-content: flex-end; width: 100%; margin-top: -2rem; margin-bottom: 1rem; padding-right: 1rem; }
    .signature-text { font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #FFFFFF; letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.7; }

    /* --- PIE DE PÁGINA --- */
    .footer-container {
        text-align: center; margin-top: 4rem; padding-top: 1.5rem;
        border-top: 1px solid #1F2228; color: #666; font-size: 0.85rem;
    }
    .footer-disclaimer {
        max-width: 800px; margin: 0 auto 1rem auto;
        color: #888; font-size: 0.8rem; line-height: 1.5; font-style: italic;
    }
    .footer-copyright {
        color: #FFFFFF; opacity: 0.8; font-size: 0.8rem;
    }

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

# --- FIRMA SUPERIOR DERECHA ---
st.markdown('<div class="signature-container"><div class="signature-text">Elaborado por Manu</div></div>', unsafe_allow_html=True)

# --- BARRA LATERAL ---
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
    
    # SELECTOR DE TONO PROFESIONAL
    tono_seleccionado = st.radio(
        "Selecciona el tono del texto:",
        ["Académico Formal", "Estudiante Universitario", "Profesional / Trabajador"]
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("Cerrar Sesión"):
        del st.session_state["password_correct"]
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.markdown('<div class="header-title">Humanizador de Textos</div>', unsafe_allow_html=True)
st.markdown('<div class="header-subtitle">Refina textos generados por IA para darles una voz auténticamente humana.</div>', unsafe_allow_html=True)

st.info("🔒 Tu texto se procesa con Gemini de Google. Por seguridad, no pegues datos personales ni confidenciales.")

# Inicializamos el estado
if "texto_humanizado" not in st.session_state:
    st.session_state["texto_humanizado"] = ""

# Función para limpiar textos
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
        max_chars=5000, # LÍMITE DE SEGURIDAD
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

# --- BOTONES DE ACCIÓN ---
st.markdown("<br>", unsafe_allow_html=True) 

col_btn1, col_btn2 = st.columns([3, 1])

with col_btn1:
    if st.button("Refinar Texto", use_container_width=True, type="primary"):
        if not texto_original.strip():
            st.warning("Por favor, pega un texto primero.")
        elif not MI_API_KEY:
            st.error("⚠️ Falta la API Key.")
        else:
            with st.spinner(f"Aplicando reescritura profunda (Tono: {tono_seleccionado})..."):
                try:
                    client = genai.Client(api_key=MI_API_KEY)
                    
                    # PROMPT AGRESIVO: No limpia, REESCRIBE desde cero.
                    base_rules = """
                    Eres un redactor humano experto. Tu tarea NO es limpiar el texto, sino REESCRIBIRLO COMPLETAMENTE desde cero con tus propias palabras.
                    Imagina que leíste el texto original, cerraste el documento, y ahora tienes que explicar la misma idea a un colega, manteniendo los mismos datos y el mismo nivel de formalidad.
                    
                    REGLAS DE REESCRITURA HUMANA:
                    1. Destruye la estructura original: No copies las mismas oraciones. Cambia el orden de las ideas si es necesario.
                    2. Prohibido el vocabulario de IA: No uses "crucial", "pivotal", "testimonio", "sinergia", "panorama", "entramado", "fomentar", "potenciar", "destacar", "vibrante", "hito", "clave", "es fundamental".
                    3. Prohibido usar el verbo "ser" de forma rebuscada: Cambia "se erige como", "constituye", "representa un" por "es", "tiene", "sirve para".
                    4. Rompe la "Regla de Tres": Si hay listas de tres adjetivos o ideas, deja solo dos o una. No forces el ritmo.
                    5. Elimina los gerundios de relleno al final de las frases: "..., reflejando", "..., destacando". Corta la frase o di la idea directo.
                    6. Evita los paralelismos negativos: "No solo X, sino también Y".
                    7. PROHIBIDO usar emojis, negritas mecánicas, viñetas o comillas curvas.
                    8. NO cambies los datos, cifras, nombres ni citas. Si el texto original menciona una ley o un autor, mantenlo intacto.
                    9. Devuelve SOLO el texto final reescrito, sin saludos ni explicaciones.
                    """
                    
                    if tono_seleccionado == "Académico Formal":
                        prompt_sistema = base_rules + """
                        TONO: Académico Formal (Para tesis, papers, docentes).
                        - Usa un vocabulario rico y formal (ej. "no obstante", "asimismo").
                        - Usa la primera persona del plural (ej. "como sociedad", "nos lleva a pensar").
                        - Introduce alguna pregunta retórica reflexiva para romper el ritmo.
                        - Mantén una estructura de párrafos irregular pero coherente.
                        """
                    elif tono_seleccionado == "Profesional / Trabajador":
                        prompt_sistema = base_rules + """
                        TONO: Profesional / Trabajador (Para informes, correos corporativos, propuestas).
                        - Sé directo y ejecutivo. Ve al grano.
                        - Usa un lenguaje claro, persuasivo pero sin ser informal.
                        - Puedes usar frases cortas para dar énfasis (ej. "El resultado es claro.", "Aquí hay un problema.").
                        - Agrega algún toque de opinión personal profesional (ej. "Mi recomendación es...", "A mi juicio...").
                        """
                    else:
                        prompt_sistema = base_rules + """
                        TONO: Estudiante Universitario (Para ensayos, foros, trabajos de clase).
                        - Usa un vocabulario académico pero natural.
                        - Usa conectores humanos (ej. "A fin de cuentas...", "Lo cierto es que...").
                        - Puedes usar la primera persona del singular ocasionalmente para dar opinión (ej. "Considero que...", "A mi parecer...").
                        - Rompe la estructura rígida: mezcla frases cortas con largas.
                        - Usa paréntesis para aclaraciones (como si estuvieras pensando en voz alta).
                        """
                    
                    response = client.models.generate_content(
                        model="gemini-3.5-flash-lite", # Dejamos solo el modelo rebelde
                        contents=texto_original,
                        config=types.GenerateContentConfig(
                            system_instruction=prompt_sistema, 
                            temperature=0.9, # Temperatura alta para forzar la creatividad
                        )
                    )
                    
                    st.session_state["texto_humanizado"] = response.text
                    st.rerun() 
                    
                except Exception as e:
                    st.error("Ocurrió un error al procesar el texto. Revisa tu conexión o intenta de nuevo en unos minutos.")
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

# --- PIE DE PÁGINA PRINCIPAL ---
st.markdown("""
    <div class="footer-container">
        <div class="footer-disclaimer">
            Humanizador Pro es una herramienta de apoyo diseñada para optimizar y pulir la redacción de textos. Los resultados generados deben ser revisados y validados por el usuario, quien asume la responsabilidad total sobre el contenido final y el uso que le dé.
        </div>
        <div class="footer-copyright">®Humanizadormanu derechos reservados © 2026</div>
    </div>
""", unsafe_allow_html=True)