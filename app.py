import re
import time
import json
import requests
import streamlit as st
from google import genai


# ---------------------------------------------------------------------------
# Configuración de la página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Humanizador Profundo de Textos IA",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Constantes de configuración
# ---------------------------------------------------------------------------
TEMPERATURA_FINAL = 1.35
TEMPERATURA_INTERMEDIA = 0.85
FREQUENCY_PENALTY = 0.50
PRESENCE_PENALTY = 0.50
TOP_P = 0.85
RITMO_MINIMO = 0.55


# ---------------------------------------------------------------------------
# Proveedores y modelos
# ---------------------------------------------------------------------------
PROVEEDORES = {
    "groq": {
        "nombre": "Groq",
        "clave": "GROQ_API_KEY",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "tipo": "openai_compatible",
    },
    "openrouter": {
        "nombre": "OpenRouter",
        "clave": "OPENROUTER_API_KEY",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "tipo": "openai_compatible",
    },
    "nvidia": {
        "nombre": "NVIDIA",
        "clave": "NVIDIA_API_KEY",
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "tipo": "openai_compatible",
    },
    "deepseek": {
        "nombre": "DeepSeek",
        "clave": "DEEPSEEK_API_KEY",
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "tipo": "openai_compatible",
    },
    "gemini": {
        "nombre": "Google Gemini",
        "clave": "GOOGLE_API_KEY",
        "endpoint": None,
        "tipo": "gemini_sdk",
    },
}

ORDEN_FALLBACK = ["groq", "openrouter", "nvidia", "deepseek", "gemini"]

MODELO_POR_PROVEEDOR = {
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "nvidia": "mistralai/mistral-large-4-1t-a52b",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.0-flash",
}

MODELOS_FIJOS = {
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
    "gemini": ["gemini-2.0-flash"],
}


# ---------------------------------------------------------------------------
# Muestra de estilo integrada (Tesis 2003)
# ---------------------------------------------------------------------------
MUESTRA_ESTILO_TESIS = """
Las ciudades han sido tradicionalmente de dos tipos, diseñadas y proyectadas de manera precisa con un orden predeterminado o desarrolladas con un crecimiento espontáneo sin ningún plan preestablecido. De cualquier manera que éstas sean clasificadas, dentro de estas dos categorías, su expansión y crecimiento han llevado a considerar los mecanismos de control necesarios para regular el uso del suelo y las posibles aplicaciones a que su desarrollo pudiese llegar a generar prospectivamente.

De acuerdo con lo anterior, es necesario comprender cómo la ciudad, a través del uso del suelo, caracteriza todavía en la actualidad los mismos tipos de ciudades antes mencionados y que pueden ser definidos como modelos históricos y antagónicos.

Para plantear una hipótesis al problema del suelo urbano, debemos necesariamente considerar tres factores que intervienen y se afectan mutuamente de acuerdo al uso del espacio territorial de la ciudad.
""".strip()


# ---------------------------------------------------------------------------
# Prompts del sistema
# ---------------------------------------------------------------------------
PROMPT_EN = (
    "Translate this Spanish text into plain, everyday English. Keep EXACTLY the "
    "same paragraphs (same number, same order) and the same level of detail: do "
    "not summarize or skip anything. Keep every fact, name, institution, number, "
    "quote and year exactly as written. Output ONLY the English text."
)

PROMPT_ES = (
    "Pasa este texto del inglés al español natural y directo. Cambia el orden de "
    "las ideas dentro de cada oración y los conectores, pero conserva los mismos "
    "párrafos, en el mismo orden y con la misma extensión. No resumas ni omitas "
    "nada. Conserva todos los datos, nombres, instituciones, cifras, citas y "
    "fechas sin inventar nada. Devuelve SOLO el texto en español."
)

PROMPT_ESTRUCTURA = (
    "Eres un editor humano experto en reestructuración de textos. Tu tarea es "
    "romper completamente la estructura de párrafos del texto recibido: "
    "1) DIVIDE párrafos largos en varios más cortos. "
    "2) VARÍA EXTREMADAMENTE la longitud de las oraciones: mezcla oraciones muy "
    "cortas (4-7 palabras) con otras muy largas (30-40 palabras). "
    "3) CAMBIA la arquitectura de cada párrafo. "
    "4) MUEVE piezas dentro de cada oración. "
    "5) ROMPE paralelismos. "
    "6) NUNCA dos oraciones seguidas de largo similar. "
    "7) NUNCA tres oraciones seguidas de estructura parecida. "
    "Mantén el significado original intacto. Devuelve SOLO el texto reestructurado."
)

PROMPT_FINAL = f"""Eres un escritor académico con estilo propio. Tu tarea es la redacción final de un texto que debe sonar completamente humano.

MUESTRA DE ESTILO DE REFERENCIA (imita este registro, ritmo y tono):
---
{MUESTRA_ESTILO_TESIS}
---

REGLAS OBLIGATORIAS DE BURSTINESS EXTREMA:
1. Alterna oraciones cortas (5-10 palabras) con oraciones largas (25-40 palabras).
2. NUNCA dos oraciones seguidas de largo similar (diferencia mínima de 8 palabras).
3. NUNCA tres oraciones seguidas de estructura parecida.
4. Máximo 20% de oraciones empezando con El/La/Los/Las/Se.

PALABRAS Y FRASES PROHIBIDAS:
- "asimismo", "no obstante", "por lo tanto", "sin embargo", "además" (máximo 1 vez cada uno en todo el texto).
- "en conclusión", "es fundamental", "cabe destacar", "juega un papel", "se ha convertido en", "en el ámbito de", "mediante".
- Moralejas al final: termina SIEMPRE con datos concretos, no con reflexiones generales.

PUNTUACIÓN OBLIGATORIA:
- Usa punto y coma (;) al menos 2 veces en el texto.
- Usa paréntesis para citas o aclaraciones.
- Usa guiones largos (—) para digresiones breves.

CONSERVACIÓN DE DATOS:
- Conserva TODAS las fechas, nombres, cifras y citas TAL CUAL aparecen en el original.

ESTILO ACADÉMICO:
- Tono impersonal: "es necesario comprender", "debemos necesariamente considerar".
- Transición lógica entre párrafos.

Devuelve SOLO el texto reescrito, sin explicaciones ni comentarios."""

PROMPT_CORRECCION = (
    "Eres un corrector de estilo académico. Revisa el texto y corrige SOLO los "
    "problemas específicos que se te indiquen en la auditoría. REGLAS: "
    "1) NO resumas ni omitas nada. "
    "2) NO cambies la extensión del texto. "
    "3) Corrige únicamente los problemas detectados. "
    "4) Mantén el significado original intacto. "
    "Devuelve SOLO el texto corregido."
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def leer_secreto(nombre: str) -> str:
    """Lee una clave desde st.secrets. Devuelve string vacío si no existe."""
    valor = st.secrets.get(nombre, "")
    if valor is None:
        return ""
    return str(valor).strip()


def detectar_modelos() -> list:
    """Detecta qué proveedores tienen clave configurada. Devuelve lista de ids."""
    disponibles = []
    for prov in ORDEN_FALLBACK:
        cfg = PROVEEDORES[prov]
        if leer_secreto(cfg["clave"]):
            disponibles.append(prov)
    return disponibles


def clean_text(texto: str) -> str:
    """Elimina patrones residuales típicos de IA y normaliza espacios."""
    if not texto:
        return ""
    patrones = [
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
    resultado = texto
    for patron in patrones:
        resultado = re.sub(patron, " ", resultado, flags=re.IGNORECASE)
    resultado = re.sub(r"\s{2,}", " ", resultado).strip()
    return resultado


# ---------------------------------------------------------------------------
# Llamadas a APIs
# ---------------------------------------------------------------------------
def llamar_openai_compatible(
    proveedor: str,
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> str:
    """Llama a una API compatible con el formato de OpenAI."""
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
        headers["X-Title"] = "Humanizador Profundo"

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
        "max_tokens": 4096,
    }

    response = requests.post(
        cfg["endpoint"],
        headers=headers,
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def llamar_gemini(
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> str:
    """Llama a Google Gemini usando el SDK oficial."""
    api_key = leer_secreto(PROVEEDORES["gemini"]["clave"])
    if not api_key:
        raise ValueError("GOOGLE_API_KEY no configurada")

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


def llamar_proveedor(
    proveedor: str,
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> dict:
    """
    Llama a un proveedor con fallback automático al siguiente disponible.
    Devuelve dict con: texto, proveedor_usado, modelo_usado, exito, error.
    """
    orden = [proveedor] + [p for p in ORDEN_FALLBACK if p != proveedor]
    ultimo_error = None

    for prov in orden:
        cfg = PROVEEDORES[prov]
        if not leer_secreto(cfg["clave"]):
            continue

        modelo_actual = MODELO_POR_PROVEEDOR[prov] if prov != proveedor else modelo

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

            return {
                "texto": resultado,
                "proveedor_usado": cfg["nombre"],
                "modelo_usado": modelo_actual,
                "exito": True,
                "error": None,
            }
        except Exception as e:
            ultimo_error = f"{cfg['nombre']}: {str(e)}"
            continue

    return {
        "texto": "",
        "proveedor_usado": None,
        "modelo_usado": None,
        "exito": False,
        "error": ultimo_error or "Ningún proveedor disponible",
    }


# ---------------------------------------------------------------------------
# Pasos del pipeline
# ---------------------------------------------------------------------------
def procesar_bloque(
    texto: str,
    paso: str,
    proveedor: str,
    modelo: str,
    problemas: list = None,
) -> dict:
    """Procesa un bloque del pipeline según el paso indicado."""
    prompts = {
        "es_en": (PROMPT_EN, TEMPERATURA_INTERMEDIA),
        "en_es": (PROMPT_ES, TEMPERATURA_INTERMEDIA),
        "estructura": (PROMPT_ESTRUCTURA, TEMPERATURA_INTERMEDIA),
        "final": (PROMPT_FINAL, TEMPERATURA_FINAL),
    }

    if paso not in prompts:
        return {
            "texto": texto,
            "proveedor_usado": None,
            "modelo_usado": None,
            "exito": False,
            "error": f"Paso desconocido: {paso}",
        }

    system_prompt, temperature = prompts[paso]

    if paso == "final" or paso == "estructura":
        user_prompt = texto
    else:
        user_prompt = texto

    return llamar_proveedor(
        proveedor=proveedor,
        modelo=modelo,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
    )


def revisar_bloque(texto: str, proveedor: str, modelo: str, problemas: list) -> dict:
    """Revisa y corrige un bloque según los problemas detectados en la auditoría."""
    if not problemas:
        return {
            "texto": texto,
            "proveedor_usado": proveedor,
            "modelo_usado": modelo,
            "exito": True,
            "error": None,
        }

    lista_problemas = "\n".join(f"- {p}" for p in problemas)
    prompt_usuario = (
        f"Texto a corregir:\n---\n{texto}\n---\n\n"
        f"Problemas detectados:\n{lista_problemas}\n\n"
        f"Corrige SOLO estos problemas sin resumir ni cambiar la extensión."
    )

    return llamar_proveedor(
        proveedor=proveedor,
        modelo=modelo,
        system_prompt=PROMPT_CORRECCION,
        user_prompt=prompt_usuario,
        temperature=TEMPERATURA_INTERMEDIA,
    )


# ---------------------------------------------------------------------------
# Auditoría automática (12 detectores)
# ---------------------------------------------------------------------------
def auditar_texto(texto: str) -> list:
    """Audita el texto y devuelve una lista de problemas detectados."""
    problemas = []
    oraciones = [o.strip() for o in re.split(r"[.!?]+", texto) if o.strip()]
    if len(oraciones) < 2:
        return problemas

    longitudes = [len(o.split()) for o in oraciones]
    media = sum(longitudes) / len(longitudes)
    varianza = sum((l - media) ** 2 for l in longitudes) / len(longitudes)
    cv = (varianza ** 0.5) / media if media > 0 else 0

    if cv < RITMO_MINIMO:
        problemas.append(f"Ritmo parejo (CV={cv:.2f} < {RITMO_MINIMO})")

    for i in range(len(longitudes) - 2):
        if (
            abs(longitudes[i] - longitudes[i + 1]) < 3
            and abs(longitudes[i + 1] - longitudes[i + 2]) < 3
        ):
            problemas.append("Tres oraciones seguidas de largo similar")
            break

    if any(l > 38 for l in longitudes):
        problemas.append("Oraciones demasiado largas (>38 palabras)")

    if not any(l < 9 for l in longitudes):
        problemas.append("Ninguna oración corta (<9 palabras)")

    frases_vetadas = [
        "en conclusión",
        "es fundamental",
        "cabe destacar",
        "juega un papel",
        "se ha convertido en",
        "en el ámbito de",
        "mediante",
    ]
    texto_lower = texto.lower()
    if any(frase in texto_lower for frase in frases_vetadas):
        problemas.append("Frases vetadas de IA detectadas")

    if re.search(r"\b\w+,\s+\w+\s+y\s+\w+\b", texto):
        problemas.append("Enumeraciones de tres elementos")

    if re.search(r",\s+\w+ando\b", texto):
        problemas.append("Gerundios de remate tras coma")

    inicios = [o.split()[0] for o in oraciones if o.split()]
    inicios_articulos = [i for i in inicios if i in ["El", "La", "Los", "Las", "Se"]]
    if len(inicios) > 0 and (len(inicios_articulos) / len(inicios)) > 0.30:
        problemas.append("Inicios repetitivos (El/La/Los/Las/Se > 30%)")

    parrafos = texto.split("\n\n")
    for p in parrafos:
        oraciones_p = [o.strip() for o in re.split(r"[.!?]+", p) if o.strip()]
        if len(oraciones_p) >= 3:
            longitudes_p = [len(o.split()) for o in oraciones_p]
            if max(longitudes_p) - min(longitudes_p) < 5:
                problemas.append("Párrafos planos (todas las oraciones de largo parecido)")
                break

    conectores = ["asimismo", "no obstante", "por lo tanto", "sin embargo", "además"]
    for conector in conectores:
        if texto_lower.count(conector) > 1:
            problemas.append(f"Conector '{conector}' en exceso (>1 vez)")
            break

    puntuacion = texto.count(";") + texto.count("—") + texto.count("(")
    if puntuacion < 3:
        problemas.append("Falta de puntuación variada (;, —, ())")

    if re.search(
        r"(en definitiva|en resumen|finalmente|como conclusión)\s*[,\.]",
        texto_lower,
    ):
        problemas.append("Moralejas o resúmenes al final")

    return problemas


def calcular_ritmo(texto: str) -> float:
    """Calcula el coeficiente de variación (CV) de las longitudes de oraciones."""
    oraciones = [o.strip() for o in re.split(r"[.!?]+", texto) if o.strip()]
    if len(oraciones) < 2:
        return 0.0
    longitudes = [len(o.split()) for o in oraciones]
    media = sum(longitudes) / len(longitudes)
    if media == 0:
        return 0.0
    varianza = sum((l - media) ** 2 for l in longitudes) / len(longitudes)
    return (varianza ** 0.5) / media


def generar_svg_ritmo(longitudes: list) -> str:
    """Genera un gráfico SVG de barras con las longitudes de las oraciones."""
    if not longitudes:
        return "<p>No hay suficientes oraciones para graficar.</p>"

    max_l = max(max(longitudes), 40)
    ancho_barra = max(2, min(20, 600 // len(longitudes)))
    alto_max = 100
    barras = ""

    for i, l in enumerate(longitudes):
        h = max(int((l / max_l) * alto_max), 2)
        color = "#ef4444" if l > 38 or l < 9 else "#3b82f6"
        barras += (
            f'<rect x="{i * (ancho_barra + 2)}" y="{alto_max - h}" '
            f'width="{ancho_barra}" height="{h}" fill="{color}" rx="2" />'
        )

    ancho_total = len(longitudes) * (ancho_barra + 2) + 10
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'height="{alto_max + 30}" viewBox="0 0 {ancho_total} {alto_max + 30}">'
        f'<text x="0" y="15" font-size="12" fill="#666" font-family="sans-serif">'
        f'Longitud de oraciones (Azul: normal, Rojo: &lt;9 o &gt;38 palabras)</text>'
        f'<g transform="translate(5, 20)">{barras}</g>'
        f'</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# Pipeline completo
# ---------------------------------------------------------------------------
def procesar(
    texto: str,
    config: dict,
    status_callback=None,
    progress_callback=None,
) -> dict:
    """
    Ejecuta el pipeline completo de humanización.
    config: dict con claves modo_profundo, pasadas, modelo_distinto,
            romper_estructura, correccion_auto, modelo_final, proveedores_otros.
    Devuelve dict con: exito, texto, log, duracion, problemas, ritmo_original, ritmo_final.
    """
    log_pasos = []
    texto_actual = texto
    inicio_total = time.time()

    proveedores_otros = config.get("proveedores_otros", ["openrouter", "nvidia", "deepseek", "gemini"])
    if not proveedores_otros:
        proveedores_otros = ["openrouter", "nvidia", "deepseek", "gemini"]

    paso_idx = 0

    def obtener_proveedor(idx: int) -> tuple:
        if config.get("modelo_distinto", True):
            prov = proveedores_otros[idx % len(proveedores_otros)]
        else:
            prov = proveedores_otros[0]
        return prov, MODELO_POR_PROVEEDOR[prov]

    total_pasos_estimados = (
        (3 if config.get("modo_profundo", True) else 1)
        + (1 if config.get("romper_estructura", True) else 0)
        + 1
        + (1 if config.get("correccion_auto", True) else 0)
    )
    paso_actual = 0

    for pasada in range(1, config.get("pasadas", 2) + 1):
        if status_callback:
            status_callback(f"Pasada {pasada}/{config.get('pasadas', 2)} iniciada...")

        if config.get("modo_profundo", True):
            paso_actual += 1
            if progress_callback:
                progress_callback(min(paso_actual / total_pasos_estimados, 0.95))
            if status_callback:
                status_callback("Traduciendo ES → EN...")

            prov, mod = obtener_proveedor(paso_idx)
            paso_idx += 1
            res_paso = procesar_bloque(texto_actual, "es_en", prov, mod)
            if not res_paso["exito"]:
                return {
                    "exito": False,
                    "texto": "",
                    "log": log_pasos,
                    "duracion": time.time() - inicio_total,
                    "problemas": [],
                    "ritmo_original": calcular_ritmo(texto),
                    "ritmo_final": 0.0,
                    "error": f"Error en ES→EN: {res_paso['error']}",
                }
            texto_actual = clean_text(res_paso["texto"])
            log_pasos.append(
                f"✓ Pasada {pasada} ES→EN: {res_paso['proveedor_usado']} ({res_paso['modelo_usado']})"
            )

            paso_actual += 1
            if progress_callback:
                progress_callback(min(paso_actual / total_pasos_estimados, 0.95))
            if status_callback:
                status_callback("Traduciendo EN → ES...")

            prov, mod = obtener_proveedor(paso_idx)
            paso_idx += 1
            res_paso = procesar_bloque(texto_actual, "en_es", prov, mod)
            if not res_paso["exito"]:
                return {
                    "exito": False,
                    "texto": "",
                    "log": log_pasos,
                    "duracion": time.time() - inicio_total,
                    "problemas": [],
                    "ritmo_original": calcular_ritmo(texto),
                    "ritmo_final": 0.0,
                    "error": f"Error en EN→ES: {res_paso['error']}",
                }
            texto_actual = clean_text(res_paso["texto"])
            log_pasos.append(
                f"✓ Pasada {pasada} EN→ES: {res_paso['proveedor_usado']} ({res_paso['modelo_usado']})"
            )

        if config.get("romper_estructura", True):
            paso_actual += 1
            if progress_callback:
                progress_callback(min(paso_actual / total_pasos_estimados, 0.95))
            if status_callback:
                status_callback("Reestructurando párrafos...")

            prov, mod = obtener_proveedor(paso_idx)
            paso_idx += 1
            res_paso = procesar_bloque(texto_actual, "estructura", prov, mod)
            if not res_paso["exito"]:
                return {
                    "exito": False,
                    "texto": "",
                    "log": log_pasos,
                    "duracion": time.time() - inicio_total,
                    "problemas": [],
                    "ritmo_original": calcular_ritmo(texto),
                    "ritmo_final": 0.0,
                    "error": f"Error en Estructura: {res_paso['error']}",
                }
            texto_actual = clean_text(res_paso["texto"])
            log_pasos.append(
                f"✓ Pasada {pasada} Estructura: {res_paso['proveedor_usado']} ({res_paso['modelo_usado']})"
            )

        paso_actual += 1
        if progress_callback:
            progress_callback(min(paso_actual / total_pasos_estimados, 0.95))
        if status_callback:
            status_callback("Redacción final académica...")

        res_paso = procesar_bloque(
            texto_actual, "final", "groq", config.get("modelo_final", MODELO_POR_PROVEEDOR["groq"])
        )
        if not res_paso["exito"]:
            return {
                "exito": False,
                "texto": "",
                "log": log_pasos,
                "duracion": time.time() - inicio_total,
                "problemas": [],
                "ritmo_original": calcular_ritmo(texto),
                "ritmo_final": 0.0,
                "error": f"Error en Final: {res_paso['error']}",
            }
        texto_actual = clean_text(res_paso["texto"])
        log_pasos.append(
            f"✓ Pasada {pasada} Final: {res_paso['proveedor_usado']} ({res_paso['modelo_usado']})"
        )

    if config.get("correccion_auto", True):
        paso_actual += 1
        if progress_callback:
            progress_callback(0.98)
        if status_callback:
            status_callback("Ejecutando corrección automática...")

        problemas = auditar_texto(texto_actual)
        if problemas:
            res_paso = revisar_bloque(
                texto_actual, "gemini", MODELO_POR_PROVEEDOR["gemini"], problemas
            )
            if res_paso["exito"]:
                texto_actual = clean_text(res_paso["texto"])
                log_pasos.append(
                    f"✓ Corrección automática: {res_paso['proveedor_usado']} ({res_paso['modelo_usado']})"
                )
            else:
                log_pasos.append(f"⚠ Corrección fallida: {res_paso['error']}")
        else:
            log_pasos.append("✓ Auditoría: No se detectaron problemas graves.")

    duracion = time.time() - inicio_total
    return {
        "exito": True,
        "texto": texto_actual,
        "log": log_pasos,
        "duracion": duracion,
        "problemas": auditar_texto(texto_actual),
        "ritmo_original": calcular_ritmo(texto),
        "ritmo_final": calcular_ritmo(texto_actual),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def login_screen():
    """Pantalla de login con contraseña."""
    st.markdown(
        """
        <div style="text-align: center; padding: 40px 0;">
            <h1 style="font-size: 48px;">✍️</h1>
            <h2>Humanizador Profundo de Textos IA</h2>
            <p style="color: #666;">Acceso restringido. Introduce la contraseña para continuar.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("Contraseña", type="password", key="login_pwd")
        if st.button("Ingresar", type="primary", use_container_width=True):
            password_esperada = leer_secreto("APP_PASSWORD")
            if not password_esperada:
                password_esperada = "manu2026"
            if pwd == password_esperada:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")


# ---------------------------------------------------------------------------
# Interfaz principal
# ---------------------------------------------------------------------------
def main():
    """Pantalla principal de la aplicación."""
    if not st.session_state.get("logged_in", False):
        login_screen()
        return

    with st.sidebar:
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

        st.header("⚙️ Configuración")

        modelo_final = st.selectbox(
            "Modelo para la redacción final",
            options=MODELOS_FIJOS["groq"],
            index=0,
        )

        proveedores_disponibles = detectar_modelos()
        modelos_otros_pasos = st.multiselect(
            "Modelos para los demás pasos",
            options=proveedores_disponibles,
            default=proveedores_disponibles,
        )

        with st.expander("Modelos conectados", expanded=False):
            for prov in ORDEN_FALLBACK:
                cfg = PROVEEDORES[prov]
                if leer_secreto(cfg["clave"]):
                    st.success(f"✓ {cfg['nombre']}: {MODELO_POR_PROVEEDOR[prov]}")
                else:
                    st.error(f"✗ {cfg['nombre']}: Sin clave")

        st.divider()
        modo_profundo = st.toggle("🔥 Modo Profundo", value=True)
        pasadas = st.slider("Pasadas de humanización", min_value=1, max_value=3, value=2)
        modelo_distinto = st.toggle("Un modelo distinto en cada paso", value=True)
        romper_estructura = st.toggle("Romper estructura de párrafos", value=True)
        correccion_auto = st.toggle("Revisión y corrección automática", value=True)

        st.divider()
        with st.expander("📋 Cómo usar la app"):
            st.markdown(
                "1. Pega tu texto en el panel izquierdo.\n"
                "2. Ajusta la configuración en esta barra lateral.\n"
                "3. Haz clic en **Humanizar texto**.\n"
                "4. Revisa el gráfico de ritmo y la auditoría abajo.\n"
                "5. Copia el resultado o descárgalo."
            )

    st.title("✍️ Humanizador Profundo de Textos IA")
    st.caption(
        "Pipeline multi-proveedor con retrotraducción, reestructuración y "
        "auditoría de 12 puntos."
    )

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("📝 Texto original")
        texto_entrada = st.text_area(
            "Pega aquí el texto generado por IA",
            height=400,
            key="texto_entrada",
        )
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            procesar_btn = st.button(
                "🚀 Humanizar texto",
                type="primary",
                use_container_width=True,
                disabled=not texto_entrada.strip(),
            )
        with col_btn2:
            if st.button("🗑️ Limpiar", use_container_width=True):
                st.session_state.texto_entrada = ""
                if "resultado" in st.session_state:
                    del st.session_state.resultado
                st.rerun()

    with col_der:
        st.subheader("✨ Texto humanizado")
        if st.session_state.get("resultado"):
            res = st.session_state.resultado

            st.markdown(
                f"""
                <div style="background-color: #fdf6e3; padding: 24px; border-radius: 8px; border: 1px solid #e0d6c2; font-family: 'Georgia', 'Times New Roman', serif; font-size: 16px; line-height: 1.7; min-height: 400px; color: #333; white-space: pre-wrap;">{res['texto']}</div>
                """,
                unsafe_allow_html=True,
            )

            texto_json = json.dumps(res["texto"])
            st.markdown(
                f"""
                <script>
                function copiarTexto() {{
                    navigator.clipboard.writeText({texto_json}).then(function() {{
                        alert('¡Texto copiado al portapapeles!');
                    }});
                }}
                </script>
                <button onclick="copiarTexto()" style="background-color: #f0f0f0; border: 1px solid #ccc; padding: 10px 20px; border-radius: 6px; cursor: pointer; margin-top: 12px; width: 100%; font-weight: bold; color: #333;">📋 Copiar texto humanizado</button>
                """,
                unsafe_allow_html=True,
            )

            st.download_button(
                "📥 Descargar resultado",
                data=res["texto"],
                file_name="texto_humanizado.txt",
                mime="text/plain",
                use_container_width=True,
            )

    if st.session_state.get("resultado"):
        res = st.session_state.resultado
        st.divider()
        st.subheader("📊 Análisis de Ritmo y Auditoría")

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("### Ritmo del texto original")
            longitudes_orig = [
                len(o.split()) for o in re.split(r"[.!?]+", texto_entrada) if o.strip()
            ]
            st.markdown(generar_svg_ritmo(longitudes_orig), unsafe_allow_html=True)
            st.metric("Coeficiente de Variación (CV)", f"{res['ritmo_original']:.2f}")

        with col_r2:
            st.markdown("### Ritmo del texto humanizado")
            longitudes_fin = [
                len(o.split()) for o in re.split(r"[.!?]+", res["texto"]) if o.strip()
            ]
            st.markdown(generar_svg_ritmo(longitudes_fin), unsafe_allow_html=True)
            cv_final = calcular_ritmo(res["texto"])
            delta_txt = "Mejorado" if cv_final >= RITMO_MINIMO else "Bajo"
            st.metric("Coeficiente de Variación (CV)", f"{cv_final:.2f}", delta=delta_txt)

        st.divider()
        col_aud1, col_aud2 = st.columns(2)
        with col_aud1:
            st.markdown("### 🔍 Problemas detectados")
            if res.get("problemas"):
                for prob in res["problemas"]:
                    st.warning(f"⚠️ {prob}")
                st.info(
                    "💡 Revisa manualmente estos puntos o ejecuta otra pasada "
                    "con 'Modo Profundo' activado."
                )
            else:
                st.success("✅ No se detectaron problemas graves en la auditoría.")

        with col_aud2:
            st.markdown("### ⏱️ Información del proceso")
            st.metric("Tiempo total", f"{res['duracion']:.1f} segundos")
            st.metric("Pasos ejecutados", len(res.get("log", [])))
            with st.expander("Ver log de proveedores usados"):
                for paso_log in res.get("log", []):
                    st.write(paso_log)

    if procesar_btn:
        config = {
            "modo_profundo": modo_profundo,
            "pasadas": pasadas,
            "modelo_distinto": modelo_distinto,
            "romper_estructura": romper_estructura,
            "correccion_auto": correccion_auto,
            "modelo_final": modelo_final,
            "proveedores_otros": modelos_otros_pasos,
        }

        progress_bar = st.progress(0)
        status_text = st.empty()

        def status_callback(msg):
            status_text.text(msg)

        def progress_callback(val):
            progress_bar.progress(val)

        with st.spinner("Ejecutando pipeline multi-proveedor..."):
            resultado = procesar(
                texto=texto_entrada.strip(),
                config=config,
                status_callback=status_callback,
                progress_callback=progress_callback,
            )

        progress_bar.progress(1.0)
        status_text.text("¡Proceso completado!")
        time.sleep(0.5)
        progress_bar.empty()
        status_text.empty()

        if resultado["exito"]:
            st.session_state.resultado = resultado
            st.rerun()
        else:
            st.error(f"Error en el pipeline: {resultado.get('error', 'Desconocido')}")
            if resultado.get("log"):
                with st.expander("Ver log de pasos ejecutados"):
                    for linea in resultado["log"]:
                        st.write(linea)


if __name__ == "__main__":
    main()
