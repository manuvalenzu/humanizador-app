# --- PIE DE PÁGINA MEJORADO ---
st.markdown("""
    <style>
    .footer-container {
        text-align: center;
        margin-top: 4rem;
        padding-top: 1rem;
        border-top: 1px solid #1F2228; /* Una línea sutil arriba */
        color: #666;
        font-size: 0.8rem;
    }
    .footer-links {
        color: #888;
        text-decoration: none;
        margin: 0 10px;
    }
    .footer-links:hover {
        color: #D97757; /* Naranja al pasar el mouse */
    }
    </style>
    
    <div class="footer-container">
        <div style="margin-bottom: 0.5rem;">
            <span class="footer-links">Términos y Condiciones</span> | 
            <span class="footer-links">Privacidad</span> | 
            <span class="footer-links">Contacto</span>
        </div>
        <div>
            ®Humanizadormanu derechos reservados © 2026
        </div>
    </div>
""", unsafe_allow_html=True)