import streamlit as st
import requests
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import io

# --- CONFIGURACIÓN SUCURSAL ---
API_BASE_URL = "https://api.policlinicotabancura.cl"
EXCEL_FILE = "aranceles.xlsx"
COLOR_NAVY = [0, 43, 91]
COLOR_GREY = [100, 100, 100]

SUCURSAL = {
    "nombre": "POLICLÍNICO TABANCURA",
    "direccion": "Av. Vitacura #8620, Vitacura, Santiago",
    "telefono": "+56 2 2933 6740",
    "web": "https://www.policlinicotabancura.cl"
}

st.set_page_config(page_title="Portal Tabancura", page_icon="🏥", layout="wide")

# Estilos CSS mejorados para compactar la UI
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stButton>button {{ background-color: #002B5B; color: white; border-radius: 8px; font-weight: 600; width: auto; min-width: 150px; padding: 0.5rem 2rem; }}
    .patient-header {{ background: white; padding: 15px; border-radius: 10px; border-left: 5px solid #002B5B; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }}
    .stTextInput>div>div>input, .stSelectbox>div>div>div {{ padding: 5px 10px; }}
    /* Ajuste de márgenes para los botones debajo de los campos */
    .stFormSubmitButton {{ text-align: left; }}
    </style>
    """, unsafe_allow_html=True)

class TabancuraPDF(FPDF):
    def __init__(self, titulo_doc, orientation='P'):
        super().__init__(orientation=orientation)
        self.titulo_doc = titulo_doc

    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(*COLOR_NAVY)
        self.cell(100, 6, self.clean_txt(SUCURSAL["nombre"]), 0, 0, 'L')
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(*COLOR_GREY)
        self.cell(0, 6, self.clean_txt(self.titulo_doc), 0, 1, 'R')
        self.set_font('Helvetica', '', 8)
        self.cell(100, 4, self.clean_txt(SUCURSAL["direccion"]), 0, 1, 'L')
        self.cell(100, 4, self.clean_txt(f"Tel: {SUCURSAL['telefono']} | {SUCURSAL['web']}"), 0, 1, 'L')
        self.ln(5)
        self.set_draw_color(200, 200, 200)
        line_w = 277 if self.cur_orientation == 'L' else 190
        self.line(10, self.get_y(), line_w + 10, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150)
        self.cell(0, 10, self.clean_txt(f"Pág. {self.page_no()} | Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), 0, 0, 'C')

    def clean_txt(self, t):
        return str(t).encode('latin-1', 'replace').decode('latin-1')

def fmt_clp(v):
    try:
        n = pd.to_numeric(v, errors='coerce')
        return f"${int(n):,}".replace(",", ".") if not pd.isna(n) else "$0"
    except: return "$0"

@st.cache_data
def cargar_aranceles():
    if not os.path.exists(EXCEL_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_excel(EXCEL_FILE)
        df.columns = [c.strip() for c in df.columns]
        for c in ['Bono Fonasa', 'Copago', 'Particular General', 'Particular Preferencial']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df['display'] = df['Nombre prestación en Fonasa o Particular'].astype(str) + " (" + df['Codigo Ingreso'].astype(str) + ")"
        return df
    except: return pd.DataFrame()

# Sesión
if 'tabla_maestra' not in st.session_state: st.session_state.tabla_maestra = pd.DataFrame()
if 'paciente_activo' not in st.session_state: st.session_state.paciente_activo = None
if 'resultados' not in st.session_state: st.session_state.resultados = []

df_aranceles = cargar_aranceles()

st.title("🏥 Gestión Clínica Tabancura")

# --- BÚSQUEDA COMPACTA ---
with st.form("search_form", clear_on_submit=False):
    # Campos en la misma fila pero compactos
    c1, c2 = st.columns([1, 2])
    tipo = c1.selectbox("Buscar por:", ["RUT", "Folio"])
    val = c2.text_input("Identificador:", placeholder="Ej: 12.345.678-9 o Folio")
    # Botón DEBAJO de los campos
    submit_search = st.form_submit_button("🔍 Buscar")

if submit_search:
    if val:
        try:
            path = f"buscar/{val}" if tipo == "RUT" else f"folio/{val}"
            res = requests.get(f"{API_BASE_URL}/cotizaciones/{path}")
            if res.status_code == 200:
                st.session_state.resultados = res.json() if isinstance(res.json(), list) else [res.json()]
                st.session_state.paciente_activo = None
            elif tipo == "RUT":
                st.info("RUT no registrado en Policlínico. Iniciando modo manual.")
                st.session_state.paciente_activo = {"nombre_paciente": "PACIENTE NUEVO", "documento_id": val, "folio": "MANUAL", "fecha_nacimiento": "---"}
                st.session_state.tabla_maestra = pd.DataFrame()
                st.session_state.resultados = []
        except: st.error("Sin conexión con el servidor local.")

# Selección si hay múltiples resultados
if st.session_state.resultados:
    st.write("---")
    opcs = {f"Folio {c['folio']} | {c['nombre_paciente']}": c for c in st.session_state.resultados}
    # Campo arriba
    sel = st.selectbox("Seleccione registro:", list(opcs.keys()))
    # Botón abajo
    if st.button("📥 Cargar Datos"):
        p = opcs[sel]
        st.session_state.paciente_activo = p
        rd = requests.get(f"{API_BASE_URL}/cotizaciones/detalle/{p['folio']}")
        if rd.status_code == 200:
            df_api = pd.DataFrame(rd.json())
            df_api['codigo_examen'] = df_api['codigo_examen'].astype(str).str.strip()
            df_aranceles['Codigo Ingreso'] = df_aranceles['Codigo Ingreso'].astype(str).str.strip()
            st.session_state.tabla_maestra = pd.merge(df_api[['codigo_examen']], df_aranceles.drop(columns=['display']), 
                                                     left_on='codigo_examen', right_on='Codigo Ingreso', how='left').drop(columns=['codigo_examen'])
            st.rerun()

# --- ÁREA DE TRABAJO ---
if st.session_state.paciente_activo:
    p = st.session_state.paciente_activo
    rut_p = p.get("documento_id") or p.get("rut_paciente") or p.get("rut") or "---"
    
    st.markdown(f'''<div class="patient-header">
        <h4 style="margin:0; color:#002B5B;">{p["nombre_paciente"]}</h4>
        <p style="margin:5px 0 0 0; font-size:0.9em;"><b>Folio:</b> {p["folio"]} | <b>RUT:</b> {rut_p} | <b>F. Nac:</b> {p.get("fecha_nacimiento", "---")}</p>
    </div>''', unsafe_allow_html=True)
    
    # Campo de añadir arriba, botón abajo
    extras = st.multiselect("Agregar prestaciones adicionales:", df_aranceles['display'].tolist())
    if st.button("➕ Añadir a la lista"):
        nuevos = df_aranceles[df_aranceles['display'].isin(extras)].drop(columns=['display'])
        st.session_state.tabla_maestra = pd.concat([st.session_state.tabla_maestra, nuevos], ignore_index=True).drop_duplicates()
        st.rerun()

    df_ed = st.data_editor(st.session_state.tabla_maestra, num_rows="dynamic", use_container_width=True)
    st.session_state.tabla_maestra = df_ed

    col1, col2 = st.columns(2)
    with col1:
        # Lógica robusta para generar bytes de PDF
        pdf_c = TabancuraPDF("PRESUPUESTO MÉDICO", orientation='L')
        pdf_c.add_page()
        pdf_c.set_font('Helvetica', 'B', 9); pdf_c.set_fill_color(245, 245, 245)
        pdf_c.cell(0, 10, pdf_c.clean_txt(f" PACIENTE: {p['nombre_paciente']}  |  RUT: {rut_p}  |  FOLIO: {p['folio']}"), 0, 1, 'L', True)
        
        cols_map = {'Fonasa': 'Bono Fonasa', 'Copago': 'Copago', 'P. Gral': 'Particular General', 'P. Pref': 'Particular Preferencial'}
        anchos = [20, 100, 31, 31, 31, 31]
        pdf_c.set_font('Helvetica', 'B', 8); pdf_c.set_fill_color(*COLOR_NAVY); pdf_c.set_text_color(255)
        for i, h in enumerate(['Código', 'Prestación'] + list(cols_map.keys())): pdf_c.cell(anchos[i], 10, pdf_c.clean_txt(h), 1, 0, 'C', True)
        pdf_c.ln()
        
        pdf_c.set_text_color(0); pdf_c.set_font('Helvetica', '', 8)
        tots = {k: 0 for k in cols_map.keys()}
        for _, r in df_ed.iterrows():
            n_full = str(r.get('Nombre prestación en Fonasa o Particular', ''))
            nombre = (n_full[:55] + '...') if len(n_full) > 55 else n_full
            pdf_c.cell(anchos[0], 8, pdf_c.clean_txt(r.get('Codigo Ingreso', '')), 1, 0, 'C')
            pdf_c.cell(anchos[1], 8, pdf_c.clean_txt(nombre), 1, 0, 'L')
            for i, (l, col_ex) in enumerate(cols_map.items()):
                val = pd.to_numeric(r.get(col_ex, 0), errors='coerce') or 0
                tots[l] += val
                pdf_c.cell(anchos[i+2], 8, fmt_clp(val), 1, 0, 'R')
            pdf_c.ln()
        
        # Uso de output() sin argumentos para evitar conflictos de tipos
        try:
            cot_bytes = pdf_c.output()
            if isinstance(cot_bytes, str):
                cot_bytes = cot_bytes.encode('latin-1')
            st.download_button("📄 Descargar Cotización PDF", data=cot_bytes, file_name=f"Cotizacion_{p['folio']}.pdf", mime="application/pdf")
        except: st.error("Error al generar el archivo de cotización.")

    with col2:
        pdf_o = TabancuraPDF("ORDEN CLÍNICA")
        pdf_o.add_page()
        pdf_o.set_font('Helvetica', 'B', 10)
        pdf_o.cell(0, 7, pdf_o.clean_txt(f"Paciente: {p['nombre_paciente']}"), 0, 1)
        pdf_o.cell(0, 7, pdf_o.clean_txt(f"RUT: {rut_p}"), 0, 1)
        pdf_o.ln(5)
        pdf_o.set_fill_color(*COLOR_NAVY); pdf_o.set_text_color(255)
        pdf_o.cell(35, 10, "CÓDIGO", 1, 0, 'C', True); pdf_o.cell(155, 10, "PRESTACIÓN", 1, 1, 'C', True)
        pdf_o.set_text_color(0); pdf_o.set_font('Helvetica', '', 10)
        for _, r in df_ed.iterrows():
            n_ord = str(r.get('Nombre prestación en Fonasa o Particular', ''))
            n_ord = (n_ord[:80] + '...') if len(n_ord) > 80 else n_ord
            pdf_o.cell(35, 8, pdf_o.clean_txt(r.get('Codigo Ingreso', '')), 1, 0, 'C')
            pdf_o.cell(155, 8, pdf_o.clean_txt(n_ord), 1, 1, 'L')
        
        pdf_o.ln(30)
        curr_y = pdf_o.get_y()
        pdf_o.line(70, curr_y, 140, curr_y)
        pdf_o.cell(0, 8, pdf_o.clean_txt("Firma y Timbre Médico"), 0, 1, 'C')
        
        try:
            ord_bytes = pdf_o.output()
            if isinstance(ord_bytes, str):
                ord_bytes = ord_bytes.encode('latin-1')
            st.download_button("⚕️ Descargar Orden PDF", data=ord_bytes, file_name=f"Orden_{p['folio']}.pdf", mime="application/pdf")
        except: st.error("Error al generar el archivo de orden.")