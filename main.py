import streamlit as st
import requests
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import os
import pytz
import base64

# --- CONFIGURACIÓN E IDENTIDAD ---
AZUL_PRIMARIO = "#0F8FEF" #
VERDE_PRIMARIO = "#23B574" #
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.policlinicotabancura.cl")

SUCURSAL = {
    "nombre": "POLICLÍNICO TABANCURA",
    "direccion": "Av. Vitacura #8620, Vitacura, Santiago",
    "telefono": "+56 2 2933 6740",
    "web": "https://www.policlinicotabancura.cl",
    "cotizador": "https://cotizador.policlinicotabancura.cl",
    "consulta": "https://consulta.policlinicotabancura.cl"
}

st.set_page_config(page_title="Portal Tabancura", page_icon="🏥", layout="wide")

# Funciones de Soporte
def fmt_clp(v):
    try:
        n = pd.to_numeric(v, errors='coerce')
        return f"${int(n):,}".replace(",", ".") if not pd.isna(n) else "$0"
    except: return "$0"

def formatear_rut(rut):
    rut = str(rut).lower().replace(".", "").replace("-", "").replace(" ", "")
    if not rut: return ""
    cuerpo, dv = rut[:-1], rut[-1]
    try:
        if cuerpo:
            return f"{int(cuerpo):,}-{dv}".replace(",", ".")
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
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

# Comunicación API
def actualizar_cotizacion_db(folio, df_ed):
    try:
        requests.post(f"{API_BASE_URL}/cotizaciones/actualizar", 
                      json={"folio": str(folio), "items": df_ed.to_dict(orient='records')}, timeout=5)
    except: pass

def registrar_auditoria(p, df_ed):
    try:
        payload = {
            "rut_paciente": p.get("documento_id"),
            "nombre_paciente": p.get("nombre_paciente"),
            "folio_origen": str(p.get("folio")),
            "cantidad_examenes": len(df_ed),
            "codigos": df_ed['Codigo Ingreso'].astype(str).tolist()
        }
        requests.post(f"{API_BASE_URL}/auditoria/ordenes", json=payload, timeout=5)
    except: pass

# CSS Corporativo
st.markdown(f"""
    <style>
    .stButton>button[kind="primary"] {{ background-color: {AZUL_PRIMARIO} !important; color: white !important; }}
    .btn-verde button {{ background-color: {VERDE_PRIMARIO} !important; color: white !important; }}
    span[data-baseweb="tag"] {{ background-color: {AZUL_PRIMARIO} !important; color: white !important; }}
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
        hora = datetime.now(pytz.timezone('America/Santiago')).strftime('%d/%m/%Y %H:%M')
        self.cell(0, 10, self.clean_txt(f"Pág. {self.page_no()} | Generado: {hora}"), align='C')

    def clean_txt(self, t):
        return str(t).encode('latin-1', 'replace').decode('latin-1')

# --- ENCABEZADO GLOBAL ---
with st.container():
    c_logo, c_info = st.columns([1, 4])
    with c_logo:
        b64 = get_base64_bin("logo.png")
        if b64: st.markdown(f'<a href="{SUCURSAL["web"]}" target="_blank"><img src="data:image/png;base64,{b64}" width="180"></a>', unsafe_allow_html=True)
    with c_info:
        st.title("Gestión de Cotizaciones y Órdenes Médicas")
        st.markdown(f"📍 {SUCURSAL['direccion']} | 📞 {SUCURSAL['telefono']}")
        n1, n2, n3, _ = st.columns([1, 1, 1, 2])
        n1.link_button("🌐 Sitio Web", SUCURSAL["web"], use_container_width=True)
        n2.link_button("💰 Cotizador", SUCURSAL["cotizador"], use_container_width=True)
        n3.link_button("📂 Consulta", SUCURSAL["consulta"], use_container_width=True)

st.divider()
tab_gestion, tab_historial = st.tabs(["📋 Gestión de Órdenes", "🕒 Historial de Auditoría"])

with tab_gestion:
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
                    st.session_state.resultados = res.json() if isinstance(res.json(), list) else [res.json()]
                else: st.warning("Sin resultados.")
            except: st.error("Error de conexión API.")

    if st.session_state.resultados:
        opcs = {f"Folio {c['folio']} | {c['nombre_paciente']}": c for c in st.session_state.resultados}
        sel = st.selectbox("Seleccione registro:", list(opcs.keys()))
        if st.button("📥 CARGAR DATOS", type="primary", use_container_width=True):
            p = opcs[sel]
            st.session_state.paciente_activo = p
            rd = requests.get(f"{API_BASE_URL}/cotizaciones/detalle/{p['folio']}")
            if rd.status_code == 200:
                df_api = pd.DataFrame(rd.json())
                df_aranceles['Codigo Ingreso'] = df_aranceles['Codigo Ingreso'].astype(str).str.strip()
                st.session_state.tabla_maestra = pd.merge(df_api[['codigo_examen']], df_aranceles.drop(columns=['display']), left_on='codigo_examen', right_on='Codigo Ingreso', how='left').drop(columns=['codigo_examen'])
                st.rerun()

    if st.session_state.paciente_activo:
        p = st.session_state.paciente_activo
        st.success(f"📌 **Paciente:** {p['nombre_paciente']} | **RUT:** {formatear_rut(p.get('documento_id'))}")
        
        extras = st.multiselect("Añadir prestaciones:", df_aranceles['display'].tolist())
        st.markdown('<div class="btn-verde">', unsafe_allow_html=True)
        if st.button("Añadir a la Orden Médica", use_container_width=True):
            nuevos = df_aranceles[df_aranceles['display'].isin(extras)].drop(columns=['display'])
            st.session_state.tabla_maestra = pd.concat([st.session_state.tabla_maestra, nuevos], ignore_index=True).drop_duplicates()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.info("💡 **Ayuda:** Doble clic para editar. Seleccione filas a la izquierda y presione 'Supr' para borrar.")
        df_ed = st.data_editor(st.session_state.tabla_maestra, num_rows="dynamic", width="stretch")
        st.session_state.tabla_maestra = df_ed

        st.write("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 GENERAR PRESUPUESTO PDF", use_container_width=True):
                actualizar_cotizacion_db(p['folio'], df_ed)
                pdf = TabancuraPDF("PRESUPUESTO MÉDICO", orientation='L')
                pdf.add_page()
                pdf.set_font('Helvetica', 'B', 10); pdf.set_fill_color(245, 245, 245)
                pdf.cell(0, 10, pdf.clean_txt(f" PACIENTE: {p['nombre_paciente']} | RUT: {formatear_rut(p.get('documento_id'))}"), ln=1, fill=True)
                pdf.ln(2)
                cols_map = {'Fonasa': 'Bono Fonasa', 'Copago': 'Copago', 'P. Gral': 'Particular General', 'P. Pref': 'Particular Preferencial'}
                pdf.set_font('Helvetica', 'B', 8); pdf.set_fill_color(16, 39, 66); pdf_c = pdf; pdf_c.set_text_color(255)
                pdf_c.cell(20, 10, "Cód.", 1, 0, 'C', True)
                pdf_c.cell(100, 10, "Prestación", 1, 0, 'C', True)
                for k in cols_map.keys(): pdf_c.cell(31, 10, k, 1, 0, 'C', True)
                pdf_c.ln()
                pdf_c.set_text_color(0); pdf_c.set_font('Helvetica', '', 8)
                tots = {k: 0 for k in cols_map.values()}
                for _, r in df_ed.iterrows():
                    pdf_c.cell(20, 8, pdf_c.clean_txt(r.get('Codigo Ingreso', '')), 1, 0, 'C')
                    pdf_c.cell(100, 8, pdf_c.clean_txt(str(r.get('Nombre prestación en Fonasa o Particular', ''))[:55]), 1, 0, 'L')
                    for c_map in cols_map.values():
                        v = pd.to_numeric(r.get(c_map, 0), errors='coerce') or 0
                        tots[c_map] += v
                        pdf_c.cell(31, 8, fmt_clp(v), 1, 0, 'R')
                    pdf_c.ln()
                pdf_c.set_font('Helvetica', 'B', 9); pdf_c.set_fill_color(230, 230, 230)
                pdf_c.cell(120, 10, "TOTAL ESTIMADO", 1, 0, 'R', True)
                for c_map in cols_map.values(): pdf_c.cell(31, 10, fmt_clp(tots[c_map]), 1, 0, 'R', True)
                
                out = pdf_c.output(dest='S')
                data_pdf = bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode('latin-1')
                st.download_button("📥 Descargar Presupuesto", data=data_pdf, file_name=f"Presupuesto_{p['folio']}.pdf", mime="application/pdf", use_container_width=True)

        with col2:
            if st.button("⚕️ GENERAR ORDEN CLÍNICA", use_container_width=True):
                registrar_auditoria(p, df_ed)
                pdf_o = TabancuraPDF("ORDEN CLÍNICA")
                pdf_o.add_page()
                pdf_o.set_font('Helvetica', 'B', 10); pdf_o.set_fill_color(245, 245, 245)
                pdf_o.cell(0, 10, pdf_o.clean_txt(f" PACIENTE: {p['nombre_paciente']} | RUT: {formatear_rut(p.get('documento_id'))}"), ln=1, fill=True)
                pdf_o.ln(5)
                pdf_o.set_fill_color(16, 39, 66); pdf_o.set_text_color(255)
                pdf_o.cell(35, 10, "CÓDIGO", 1, 0, 'C', True); pdf_o.cell(155, 10, "PRESTACIÓN", 1, 1, 'C', True)
                pdf_o.set_text_color(0); pdf_o.set_font('Helvetica', '', 10)
                for _, r in df_ed.iterrows():
                    pdf_o.cell(35, 8, pdf_o.clean_txt(r.get('Codigo Ingreso', '')), 1, 0, 'C')
                    pdf_o.cell(155, 8, pdf_o.clean_txt(str(r.get('Nombre prestación en Fonasa o Particular', ''))[:80]), 1, 1, 'L')
                pdf_o.ln(25); pdf_o.line(70, pdf_o.get_y(), 140, pdf_o.get_y())
                pdf_o.cell(0, 8, pdf_o.clean_txt("Firma y Timbre Médico"), 0, 1, 'C')
                
                out_o = pdf_o.output(dest='S')
                data_ord = bytes(out_o) if isinstance(out_o, (bytes, bytearray)) else out_o.encode('latin-1')
                st.download_button("📥 Descargar Orden", data=data_ord, file_name=f"Orden_{p['folio']}.pdf", mime="application/pdf", use_container_width=True)

with tab_historial:
    st.subheader("🕒 Registro Histórico de Órdenes Generadas")
    if st.button("🔄 Actualizar Historial"):
        try:
            resp = requests.get(f"{API_BASE_URL}/auditoria/historial")
            if resp.status_code == 200:
                df_hist = pd.DataFrame(resp.json())
                if not df_hist.empty:
                    df_hist['fecha_emision'] = pd.to_datetime(df_hist['fecha_emision']).dt.strftime('%d/%m/%Y %H:%M')
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)
                else: st.info("No hay registros aún.")
            else: st.error(f"Error API: {resp.text}")
        except Exception as e: st.error(f"Error conexión: {e}")