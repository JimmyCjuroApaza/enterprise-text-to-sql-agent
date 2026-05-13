import streamlit as st
import psycopg2
import pandas as pd
import requests
import re

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y BD
# ==========================================
st.set_page_config(page_title="Text-to-SQL AI", page_icon="🤖", layout="wide")

DB_USER = "postgres"
DB_PASSWORD = "cjuro"  
DB_NAME = "pagila"
DB_HOST = "localhost"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO_LLM = "deepseek-coder:6.7b"

# ==========================================
# FUNCIONES NÚCLEO 
# ==========================================
@st.cache_data(show_spinner=False)
def obtener_esquema_db():
    conexion = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST)
    cursor = conexion.cursor()
    query_esquema = """
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' ORDER BY table_name;
    """
    cursor.execute(query_esquema)
    resultados = cursor.fetchall()
    
    esquema_txt = ""
    tabla_actual = ""
    for fila in resultados:
        tabla, columna, tipo = fila
        if tabla != tabla_actual:
            esquema_txt += f"\nTabla: {tabla}\n"
            tabla_actual = tabla
        esquema_txt += f" - {columna} ({tipo})\n"
    
    cursor.close()
    conexion.close()
    return esquema_txt

def generar_sql(pregunta, esquema):
    
    prompt = f"""
    Eres un Arquitecto de Datos experto en PostgreSQL.
    Aquí tienes el esquema de mi base de datos:
    {esquema}

    =======================================================
    ⚠️ DICCIONARIO DE DATOS Y REGLAS ESTRICTAS DE NEGOCIO ⚠️
    =======================================================
    - UBICACIÓN DEL CLIENTE: Para saber el país o ciudad de un cliente, es OBLIGATORIO usar la ruta exacta: rental -> customer -> address -> city -> country.
    - PROHIBICIÓN: ¡ESTÁ ESTRICTAMENTE PROHIBIDO usar la tabla 'store' o 'inventory' para buscar el país de un cliente! Solo usa 'store' si se pregunta por una sucursal.
    - OBJETIVO: Responde ÚNICAMENTE con código SQL válido. Sin explicaciones.

    Pregunta: {pregunta}
        """
        
    payload = {"model": MODELO_LLM, "prompt": prompt, "stream": False, "temperature": 0.0}
    respuesta = requests.post(OLLAMA_URL, json=payload)
    return re.sub(r"```sql\n|```", "", respuesta.json()["response"]).strip()

def ejecutar_consulta_df(sql):
    conexion = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST)
    # Pandas ejecuta el SQL y lo convierte directamente en un DataFrame (Tabla)
    df = pd.read_sql_query(sql, conexion)
    conexion.close()
    return df

# ==========================================
# INTERFAZ DE USUARIO (FRONTEND)
# ==========================================
st.title("🤖 Agente Text-to-SQL Empresarial")
st.markdown("Consulta la base de datos privada **Pagila** en lenguaje natural. Procesado localmente con *DeepSeek-Coder*.")

# Cargamos el esquema en segundo plano
esquema = obtener_esquema_db()

# Caja de texto para el gerente
pregunta_usuario = st.text_area("¿Qué deseas saber sobre el negocio?", placeholder="Ej: Muestra el top 5 de películas más rentadas.")

# Botón de acción
if st.button("Ejecutar Consulta", type="primary"):
    if pregunta_usuario:
        # Dividimos la pantalla en dos columnas
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("🧠 Generando SQL con DeepSeek...")
            sql_generado = generar_sql(pregunta_usuario, esquema)
            st.success("Código generado:")
            st.code(sql_generado, language="sql")
            
        with col2:
            st.info("🚀 Ejecutando en PostgreSQL...")
            try:
                df_resultado = ejecutar_consulta_df(sql_generado)
                st.success(f"Consulta exitosa. Se encontraron {len(df_resultado)} registros.")
                # st.dataframe dibuja una tabla interactiva hermosa
                st.dataframe(df_resultado, use_container_width=True)
            except Exception as e:
                st.error(f"Error al ejecutar SQL en la base de datos: {e}")
    else:
        st.warning("Por favor, escribe una pregunta primero.")