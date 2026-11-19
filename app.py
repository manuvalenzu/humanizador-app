import streamlit as st
from google import genai
import streamlit.components.v1 as components

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

    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .sidebar-title { font-family: 'Playfair Display', serif; font-size: 1.5rem; color: #E0E0E0; font-weight: 700; line-height: 1.2; margin-bottom: 2rem; }
    .sidebar-title span { color: #D97757; font-size: 2rem; line-height: 0; }

    /* FIRMA SUPERIOR DERECHA CORREGIDA */
    .signature-container {
        display: flex;
        justify-content: flex-end;
        width: 100%;
        margin-top: -2rem; /* Ajuste para que quede bien arriba */
        margin-bottom: 1rem;
        padding-right: 1rem;
    }
    .signature-text {
        font-family: 'Inter', sans-serif;
        font-size: 0.65rem; /* Más pequeña */
        color: #FFFFFF; /* Letras blancas */
        letter-spacing: 0.1em;
        text-transform: uppercase;
        opacity: 0.7; /* Un poco de transparencia para que no sea muy dura */
    }
    </style>
""", unsafe_allow_html=True)

# --- FIRMA SUPERIOR DERECHA ---
st.markdown('<div class="signature-container"><div class="signature-text">Elaborado por Manu</div></div>', unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown('<div class="sidebar-title">PANEL DE<br>CONTROL<span>.</span></div>', unsafe_allow_html=True)
    st.markdown("### Configuración")
    
    if not MI_API_KEY:
        st.warning("⚠️ Falta la API Key. Por favor, agrégala en los Secretos de Streamlit o ingrésala aquí abajo.")
        MI_API_KEY = st.text_input("API Key de Gemini", type="password")
    else:
        st.success("✅ Clave API cargada desde los secretos de Streamlit.")
    
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

col1, col2 = st.columns(2, gap="medium")

with col1:
    st.markdown("#### Texto Original")
    texto_original = st.text_area("Pega tu texto aquí:", height=400, label_visibility="collapsed")

with col2:
    st.markdown("#### Texto Humanizado")
    resultado_container = st.empty()
    resultado_container.text_area("Resultado:", height=400, disabled=True, label_visibility="collapsed")

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
                Eres un editor humano experto. Reescribe el texto para que suene 100% natural.
                REGLAS:
                1. Elimina conectores robóticos: "En primera instancia", "Adicionalmente", "En conclusión", "Cabe destacar".
                2. Cambia el verbo ser rebuscado ("se erige como", "constituye") por "es", "tiene".
                3. Rompe la regla de tres.
                4. Varía el ritmo: mezcla frases cortas y largas.
                5. Inyecta "ruido humano": paréntesis, primera persona, micro-dudas.
                6. NO cambies datos, cifras ni nombres.
                7. Devuelve SOLO el texto final.
                """
                
                response = client.models.generate_content(
                    model=modelo,
                    contents=f"{prompt_sistema}\n\nHumaniza este texto:\n\n{texto_original}"
                )
                
                texto_final = response.text
                
                resultado_container.text_area("Resultado:", value=texto_final, height=400, disabled=False, label_visibility="collapsed")
                st.success("Texto humanizado exitosamente.")
                
                # --- BOTÓN DE COPIAR ---
                components.html(
                    f"""
                    <button id="copyBtn" style="
                        background-color: transparent; border: 1px solid #D97757; color: #D97757;
                        padding: 8px 16px; border-radius: 6px; cursor: pointer;
                        font-family: 'Inter', sans-serif; font-size: 0.9rem; width: 100%; margin-top: 10px;
                    ">📋 Copiar Texto Humanizado</button>
                    <script>
                    document.getElementById('copyBtn').addEventListener('click', function() {{
                        const text = `{texto_final.replace('`', '\\`')}`;
                        navigator.clipboard.writeText(text).then(function() {{
                            document.getElementById('copyBtn').innerHTML = '✅ ¡Copiado!';
                            setTimeout(() => {{ document.getElementById('copyBtn').innerHTML = '📋 Copiar Texto Humanizado'; }}, 2000);
                        }});
                    }});
                    </script>
                    """,
                    height=60,
                )
                
            except Exception as e:
                st.error(f"Error: {e}")
                st.info("Si el error es 503, el servidor de Google está saturado. Intenta con otro modelo.")