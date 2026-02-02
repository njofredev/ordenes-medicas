import streamlit as st
import requests
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os

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

# Estilos CSS para mejorar la estética y compactar elementos
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stButton>button {{ background-color: #002B5B; color: white; border-radius: 8px; font-weight: 600; width: 100%; }}
    .patient-header {{ background: white; padding: 15px; border-radius: 10px; border-left: 5px solid #002B5B; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }}
    .stTextInput>div>div>input, .stSelectbox>div>div>div {{ padding: 5px 10px; }}
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

if 'tabla_maestra' not in st.session_state: st.session_state.tabla_maestra = pd.DataFrame()
if 'paciente_activo' not in st.session_state: st.session_state.paciente_activo = None
if 'resultados' not in st.session_state: st.session_state.resultados = []

df_aranceles = cargar_aranceles()

st.title("🏥 Gestión Clínica Tabancura")

with st.form("search_form", clear_on_submit=False):
    c1, c2, c3 = st.columns([1, 2, 1])
    tipo = c1.selectbox("Buscar por:", ["RUT", "Folio"])
    val = c2.text_input("Identificador:", placeholder="Ej: 12.345.678-9 o Folio")
    submit_search = c3.form_submit_button("🔍 Buscar")

if submit_search:
    if val:
        try:
            path = f"buscar/{val}" if tipo == "RUT" else f"folio/{val}"
            res = requests.get(f"{API_BASE_URL}/cotizaciones/{path}")
            if res.status_code == 200:
                st.session_state.resultados = res.json() if isinstance(res.json(), list) else [res.json()]
                st.session_state.paciente_activo = None
            elif tipo == "RUT":
                st.info("RUT no registrado. Iniciando orden manual.")
                st.session_state.paciente_activo = {"nombre_paciente": "PACIENTE NUEVO", "documento_id": val, "folio": "MANUAL", "fecha_nacimiento": "---"}
                st.session_state.tabla_maestra = pd.DataFrame()
                st.session_state.resultados = []
        except: st.error("Error de conexión con la API.")

if st.session_state.resultados:
    st.write("---")
    r1, r2 = st.columns([3, 1])
    opcs = {f"Folio {c['folio']} | {c['nombre_paciente']}": c for c in st.session_state.resultados}
    sel = r1.selectbox("Seleccione el registro exacto:", list(opcs.keys()))
    if r2.button("📥 Cargar Datos"):
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

if st.session_state.paciente_activo:
    p = st.session_state.paciente_activo
    rut_p = p.get("documento_id") or p.get("rut_paciente") or p.get("rut") or "---"
    
    st.markdown(f'''<div class="patient-header">
        <h4 style="margin:0; color:#002B5B;">{p["nombre_paciente"]}</h4>
        <p style="margin:5px 0 0 0; font-size:0.9em;"><b>Folio:</b> {p["folio"]} | <b>RUT:</b> {rut_p} | <b>F. Nac:</b> {p.get("fecha_nacimiento", "---")}</p>
    </div>''', unsafe_allow_html=True)
    
    a1, a2 = st.columns([3, 1])
    extras = a1.multiselect("Agregar exámenes adicionales:", df_aranceles['display'].tolist())
    if a2.button("➕ Añadir"):
        nuevos = df_aranceles[df_aranceles['display'].isin(extras)].drop(columns=['display'])
        st.session_state.tabla_maestra = pd.concat([st.session_state.tabla_maestra, nuevos], ignore_index=True).drop_duplicates()
        st.rerun()

    df_ed = st.data_editor(st.session_state.tabla_maestra, num_rows="dynamic", use_container_width=True)
    st.session_state.tabla_maestra = df_ed

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 GENERAR COTIZACIÓN"):
            pdf = TabancuraPDF("PRESUPUESTO MÉDICO", orientation='L')
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 9); pdf.set_fill_color(245, 245, 245)
            info = f" PACIENTE: {p['nombre_paciente']}  |  RUT: {rut_p}  |  FOLIO: {p['folio']}"
            pdf.cell(0, 10, pdf.clean_txt(info), 0, 1, 'L', True)
            
            cols_map = {'Fonasa': 'Bono Fonasa', 'Copago': 'Copago', 'P. Gral': 'Particular General', 'P. Pref': 'Particular Preferencial'}
            anchos = [20, 100, 31, 31, 31, 31]
            pdf.set_font('Helvetica', 'B', 8); pdf.set_fill_color(*COLOR_NAVY); pdf.set_text_color(255)
            for i, h in enumerate(['Código', 'Prestación'] + list(cols_map.keys())): pdf.cell(anchos[i], 10, pdf.clean_txt(h), 1, 0, 'C', True)
            pdf.ln()
            
            pdf.set_text_color(0); pdf.set_font('Helvetica', '', 8)
            tots = {k: 0 for k in cols_map.keys()}
            for _, r in df_ed.iterrows():
                n_full = str(r.get('Nombre prestación en Fonasa o Particular', ''))
                nombre = (n_full[:55] + '...') if len(n_full) > 55 else n_full
                pdf.cell(anchos[0], 8, pdf.clean_txt(r.get('Codigo Ingreso', '')), 1, 0, 'C')
                pdf.cell(anchos[1], 8, pdf.clean_txt(nombre), 1, 0, 'L')
                for i, (l, col_ex) in enumerate(cols_map.items()):
                    val = pd.to_numeric(r.get(col_ex, 0), errors='coerce') or 0
                    tots[l] += val
                    pdf.cell(anchos[i+2], 8, fmt_clp(val), 1, 0, 'R')
                pdf.ln()
            
            pdf.set_font('Helvetica', 'B', 9); pdf.set_fill_color(235, 235, 235)
            pdf.cell(anchos[0] + anchos[1], 10, "TOTALES ESTIMADOS", 1, 0, 'R', True)
            for l in cols_map.keys(): pdf.cell(31, 10, fmt_clp(tots[l]), 1, 0, 'R', True)
            
            # CORRECCIÓN AQUÍ: Usamos encode para asegurar que siempre sean bytes
            pdf_output = pdf.output()
            pdf_bytes = pdf_output if isinstance(pdf_output, bytes) else pdf_output.encode('latin-1')
            st.download_button("📥 Descargar Cotización", data=pdf_bytes, file_name=f"Cotizacion_{p['folio']}.pdf", mime="application/pdf")

    with col2:
        if st.button("⚕️ GENERAR ORDEN MÉDICA"):
            pdf = TabancuraPDF("ORDEN CLÍNICA")
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 7, pdf.clean_txt(f"Paciente: {p['nombre_paciente']}"), 0, 1)
            pdf.cell(0, 7, pdf.clean_txt(f"RUT: {rut_p}"), 0, 1)
            pdf.ln(5)
            pdf.set_fill_color(*COLOR_NAVY); pdf.set_text_color(255)
            pdf.cell(35, 10, "CÓDIGO", 1, 0, 'C', True); pdf.cell(155, 10, "PRESTACIÓN", 1, 1, 'C', True)
            pdf.set_text_color(0); pdf.set_font('Helvetica', '', 10)
            for _, r in df_ed.iterrows():
                n_ord = str(r.get('Nombre prestación en Fonasa o Particular', ''))
                n_ord = (n_ord[:80] + '...') if len(n_ord) > 80 else n_ord
                pdf.cell(35, 8, pdf.clean_txt(r.get('Codigo Ingreso', '')), 1, 0, 'C')
                pdf.cell(155, 8, pdf.clean_txt(n_ord), 1, 1, 'L')
            
            pdf.ln(30)
            curr_y = pdf.get_y()
            pdf.line(70, curr_y, 140, curr_y)
            pdf.cell(0, 8, pdf.clean_txt("Firma y Timbre Médico"), 0, 1, 'C')
            
            # CORRECCIÓN AQUÍ: Usamos encode para asegurar que siempre sean bytes
            pdf_output = pdf.output()
            orden_bytes = pdf_output if isinstance(pdf_output, bytes) else pdf_output.encode('latin-1')
            st.download_button("📥 Descargar Orden", data=orden_bytes, file_name=f"Orden_{p['folio']}.pdf", mime="application/pdf")