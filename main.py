import streamlit as st
import requests
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import pytz
import base64

# 1. FUNCIONES DE APOYO
def fmt_clp(v):
    try:
        n = pd.to_numeric(v, errors='coerce')
        return f"${int(n):,}".replace(",", ".") if not pd.isna(n) else "$0"
    except: return "$0"

def formatear_rut(rut):
    rut = str(rut).lower().replace(".", "").replace("-", "").replace(" ", "")
    if not rut: return ""
    cuerpo = rut[:-1]
    dv = rut[-1]
    try:
        if cuerpo:
            cuerpo_fmt = f"{int(cuerpo):,}".replace(",", ".")
            return f"{cuerpo_fmt}-{dv}"
    except: pass
    return rut

@st.cache_data
def cargar_aranceles():
    if not os.path.exists("aranceles.xlsx"): return pd.DataFrame()
    try:
        df = pd.read_excel("aranceles.xlsx")
        df.columns = [c.strip() for c in df.columns]
        for c in ['Bono Fonasa', 'Copago', 'Particular General', 'Particular Preferencial']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        df['display'] = df['Nombre prestación en Fonasa o Particular'].astype(str) + " (" + df['Codigo Ingreso'].astype(str) + ")"
        return df
    except: return pd.DataFrame()

def get_base64_bin(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# 2. IDENTIDAD CORPORATIVA (Colores Manual)
AZUL_PRIMARIO = "#0F8FEF"
VERDE_PRIMARIO = "#23B574"
AZUL_SECUNDARIO = "#102742"

API_BASE_URL = "https://api.policlinicotabancura.cl"

SUCURSAL = {
    "nombre": "POLICLÍNICO TABANCURA",
    "direccion": "Av. Vitacura #8620, Vitacura, Santiago",
    "telefono": "+56 2 2933 6740",
    "web": "https://www.policlinicotabancura.cl",
    "cotizador": "https://cotizador.policlinicotabancura.cl",
    "consulta": "https://consulta.policlinicotabancura.cl"
}

st.set_page_config(page_title="Portal Tabancura", page_icon="🏥", layout="wide")

# CSS para UI/UX
st.markdown(f"""
    <style>
    .stButton>button[kind="primary"] {{ background-color: {AZUL_PRIMARIO} !important; border: none !important; color: white !important; }}
    .btn-verde button {{ background-color: {VERDE_PRIMARIO} !important; color: white !important; border: none !important; }}
    span[data-baseweb="tag"] {{ background-color: {AZUL_PRIMARIO} !important; color: white !important; }}
    .logo-container:hover {{ transform: scale(1.03); transition: 0.3s; }}
    </style>
""", unsafe_allow_html=True)

class TabancuraPDF(FPDF):
    def __init__(self, titulo_doc, orientation='P'):
        super().__init__(orientation=orientation)
        self.titulo_doc = titulo_doc

    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(16, 39, 66)
        self.cell(0, 7, self.clean_txt(SUCURSAL["nombre"]), ln=True, align='L')
        self.set_font('Helvetica', '', 9)
        self.set_text_color(80, 80, 80)
        self.cell(0, 5, self.clean_txt(SUCURSAL["direccion"]), ln=True, align='L')
        self.cell(0, 5, self.clean_txt(f"Teléfono: {SUCURSAL['telefono']}"), ln=True, align='L')
        self.set_y(10)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, self.clean_txt(self.titulo_doc), align='R', ln=True)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150)
        tz_chile = pytz.timezone('America/Santiago')
        hora_chile = datetime.now(tz_chile).strftime('%d/%m/%Y %H:%M')
        self.cell(0, 10, self.clean_txt(f"Pág. {self.page_no()} | Generado: {hora_chile}"), align='C')

    def clean_txt(self, t):
        return str(t).encode('latin-1', 'replace').decode('latin-1')

# 3. ENCABEZADO
with st.container():
    c_logo, c_info = st.columns([1, 4])
    with c_logo:
        if os.path.exists("logo.png"):
            b64 = get_base64_bin("logo.png")
            st.markdown(f'<a href="{SUCURSAL["web"]}" target="_blank" class="logo-container"><img src="data:image/png;base64,{b64}" width="180"></a>', unsafe_allow_html=True)
    with c_info:
        st.title("Gestión de Cotizaciones y Órdenes Médicas")
        st.markdown(f"📍 {SUCURSAL['direccion']} | 📞 {SUCURSAL['telefono']}")
        n1, n2, n3, _ = st.columns([1, 1, 1, 1])
        n1.link_button("🌐 Web", SUCURSAL["web"], use_container_width=True)
        n2.link_button("💰 Cotizador", SUCURSAL["cotizador"], use_container_width=True)
        n3.link_button("📂 Consulta", SUCURSAL["consulta"], use_container_width=True)

st.divider()

# 4. LÓGICA DE DATOS
if 'tabla_maestra' not in st.session_state: st.session_state.tabla_maestra = pd.DataFrame()
if 'paciente_activo' not in st.session_state: st.session_state.paciente_activo = None
if 'resultados' not in st.session_state: st.session_state.resultados = []

df_aranceles = cargar_aranceles()

with st.form("search_form"):
    st.subheader("🔍 Localizar Paciente")
    c1, c2 = st.columns([1, 2])
    tipo = c1.selectbox("Criterio:", ["RUT", "Folio"])
    val_in = c2.text_input("Identificador:", placeholder="Ej: 22.222.222-2")
    if st.form_submit_button("Consultar Base de Datos"):
        val_b = formatear_rut(val_in) if tipo == "RUT" else val_in
        try:
            path = f"buscar/{val_b}" if tipo == "RUT" else f"folio/{val_b}"
            res = requests.get(f"{API_BASE_URL}/cotizaciones/{path}")
            if res.status_code == 200:
                api_data = res.json() if isinstance(res.json(), list) else [res.json()]
                st.session_state.resultados = api_data
                st.session_state.paciente_activo = None
            else: st.warning("No se encontraron registros.")
        except: st.error("Error de conexión.")

if st.session_state.resultados:
    opcs = {f"Folio {c['folio']} | {c['nombre_paciente']}": c for c in st.session_state.resultados}
    sel = st.selectbox("Registros encontrados:", list(opcs.keys()))
    if st.button("📥 CARGAR DATOS SELECCIONADOS", type="primary", use_container_width=True):
        p = opcs[sel]
        st.session_state.paciente_activo = p
        rd = requests.get(f"{API_BASE_URL}/cotizaciones/detalle/{p['folio']}")
        if rd.status_code == 200:
            df_api = pd.DataFrame(rd.json())
            df_api['codigo_examen'] = df_api['codigo_examen'].astype(str).str.strip()
            df_aranceles['Codigo Ingreso'] = df_aranceles['Codigo Ingreso'].astype(str).str.strip()
            st.session_state.tabla_maestra = pd.merge(df_api[['codigo_examen']], df_aranceles.drop(columns=['display']), left_on='codigo_examen', right_on='Codigo Ingreso', how='left').drop(columns=['codigo_examen'])
            st.rerun()

if st.session_state.paciente_activo:
    p = st.session_state.paciente_activo
    rut_fmt = formatear_rut(p.get("documento_id") or p.get("rut_paciente") or "---")
    st.success(f"📌 **Paciente:** {p['nombre_paciente']} | **RUT:** {rut_fmt}")
    
    st.subheader("➕ Agregar Prestaciones Adicionales")
    extras = st.multiselect("Buscar exámenes en arancel:", df_aranceles['display'].tolist())
    st.markdown('<div class="btn-verde">', unsafe_allow_html=True)
    if st.button("Añadir a la Orden Médica", use_container_width=True):
        nuevos = df_aranceles[df_aranceles['display'].isin(extras)].drop(columns=['display'])
        st.session_state.tabla_maestra = pd.concat([st.session_state.tabla_maestra, nuevos], ignore_index=True).drop_duplicates()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.subheader("📝 Edición de Aranceles y Detalles")
    st.info("💡 **Ayuda:** Doble clic para editar celdas. Para eliminar filas, selecciónelas a la izquierda y presione 'Supr'.")
    df_ed = st.data_editor(st.session_state.tabla_maestra, num_rows="dynamic", width="stretch")
    st.session_state.tabla_maestra = df_ed

    st.write("---")
    col1, col2 = st.columns(2)
    
    # Lógica de descarga CORREGIDA para entornos Coolify/Linux
    with col1:
        if st.button("📄 GENERAR PRESUPUESTO PDF", use_container_width=True):
            pdf_c = TabancuraPDF("PRESUPUESTO MÉDICO", orientation='L')
            pdf_c.add_page()
            pdf_c.set_font('Helvetica', 'B', 10); pdf_c.set_fill_color(245, 245, 245)
            pdf_c.cell(0, 10, pdf_c.clean_txt(f" PACIENTE: {p['nombre_paciente']} | RUT: {rut_fmt}"), ln=1, fill=True)
            pdf_c.ln(2)
            cols_map = {'Fonasa': 'Bono Fonasa', 'Copago': 'Copago', 'P. Gral': 'Particular General', 'P. Pref': 'Particular Preferencial'}
            pdf_c.set_font('Helvetica', 'B', 8); pdf_c.set_fill_color(16, 39, 66); pdf_c.set_text_color(255)
            pdf_c.cell(20, 10, "Cód.", 1, 0, 'C', True)
            pdf_c.cell(100, 10, "Prestación", 1, 0, 'C', True)
            for k in cols_map.keys(): pdf_c.cell(31, 10, k, 1, 0, 'C', True)
            pdf_c.ln()
            pdf_c.set_text_color(0); pdf_c.set_font('Helvetica', '', 8)
            tots = {k: 0 for k in cols_map.values()}
            for _, r in df_ed.iterrows():
                pdf_c.cell(20, 8, pdf_c.clean_txt(r.get('Codigo Ingreso', '')), 1, 0, 'C')
                pdf_c.cell(100, 8, pdf_c.clean_txt(str(r.get('Nombre prestación en Fonasa o Particular', ''))[:55]), 1, 0, 'L')
                for col_ex in cols_map.values():
                    v = pd.to_numeric(r.get(col_ex, 0), errors='coerce') or 0
                    tots[col_ex] += v
                    pdf_c.cell(31, 8, fmt_clp(v), 1, 0, 'R')
                pdf_c.ln()
            pdf_c.set_font('Helvetica', 'B', 9); pdf_c.set_fill_color(230, 230, 230)
            pdf_c.cell(120, 10, "TOTAL ESTIMADO", 1, 0, 'R', True)
            for col_ex in cols_map.values(): pdf_c.cell(31, 10, fmt_clp(tots[col_ex]), 1, 0, 'R', True)
            
            # CORRECCIÓN DE BYTES
            out = pdf_c.output(dest='S')
            data_pdf = bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode('latin-1')
            st.download_button("📥 Descargar Presupuesto", data=data_pdf, file_name=f"Presupuesto_{p['folio']}.pdf", mime="application/pdf", use_container_width=True)

    with col2:
        if st.button("⚕️ GENERAR ORDEN CLÍNICA", use_container_width=True):
            pdf_o = TabancuraPDF("ORDEN CLÍNICA")
            pdf_o.add_page()
            pdf_o.set_font('Helvetica', 'B', 10); pdf_o.set_fill_color(245, 245, 245)
            pdf_o.cell(0, 10, pdf_o.clean_txt(f" PACIENTE: {p['nombre_paciente']} | RUT: {rut_fmt}"), ln=1, fill=True)
            pdf_o.ln(5)
            pdf_o.set_fill_color(16, 39, 66); pdf_o.set_text_color(255)
            pdf_o.cell(35, 10, "CÓDIGO", 1, 0, 'C', True); pdf_o.cell(155, 10, "PRESTACIÓN", 1, 1, 'C', True)
            pdf_o.set_text_color(0); pdf_o.set_font('Helvetica', '', 10)
            for _, r in df_ed.iterrows():
                pdf_o.cell(35, 8, pdf_o.clean_txt(r.get('Codigo Ingreso', '')), 1, 0, 'C')
                pdf_o.cell(155, 8, pdf_o.clean_txt(str(r.get('Nombre prestación en Fonasa o Particular', ''))[:80]), 1, 1, 'L')
            pdf_o.ln(25); pdf_o.line(70, pdf_o.get_y(), 140, pdf_o.get_y())
            pdf_o.cell(0, 8, pdf_o.clean_txt("Firma y Timbre Médico"), 0, 1, 'C')
            
            # CORRECCIÓN DE BYTES
            out_o = pdf_o.output(dest='S')
            data_ord = bytes(out_o) if isinstance(out_o, (bytes, bytearray)) else out_o.encode('latin-1')
            st.download_button("📥 Descargar Orden", data=data_ord, file_name=f"Orden_{p['folio']}.pdf", mime="application/pdf", use_container_width=True)