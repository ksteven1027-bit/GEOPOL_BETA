# ===================================================================
# GEOPORTAL WEB - VERSIÓN PREMIUM FINAL (DISEÑO VIAL INTEGRAL)
# Novedades: 
# 1. Tabla Inicial Dinámica (Cálculo en vivo de Distancia y Pendiente).
# 2. Escala Comercial Discreta y Grillas en Plano CAD.
# 3. Flujo Reordenado: Alineamiento -> Perfil Longitudinal -> Memoria -> CAD -> Transversales.
# 4. Solución TypeError 'input must be a scalar' forzando casting float() en PyProj.
# ===================================================================
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import os
import base64
import pickle
import shutil
from io import StringIO
from datetime import datetime
from streamlit_geolocation import streamlit_geolocation
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import numpy as np
import pyproj 
import glob

# Importación de los Motores
from motor_v2_5 import poligonal_3d_v2_5, decimal_a_dms
from motor_abierta import poligonal_abierta_control
from motor_altimetria import calcular_cartera_nivelacion
from motor_proyecciones import MotorCoordenadasIGAC_V2
from motor_volumenes import generar_malla_vacia, calcular_cotas_seccion, calcular_cubicaje_total
from motor_grafico_poligonal import generar_plano_profesional
from motor_exportacion import generar_kml, generar_dxf, generar_shp_zip
from motor_informes import generar_reporte_poligonal_latex, generar_reporte_volumenes_latex, generar_reporte_nivelacion_latex, compilar_latex_a_pdf
from motor_nube_puntos import procesar_archivo_nube, asignar_columnas
from motor_dtm import generar_dtm_curvas, extraer_elevaciones_dtm
from motor_vias import procesar_alineamiento_horizontal, peraltes_por_abscisa
from motor_grafico_vias import generar_plano_vias

st.set_page_config(page_title="GeoPol Web | Plataforma Topográfica", layout="wide")

# ===================================================================
# PLANTILLAS BASE INDEPENDIENTES
# ===================================================================
df_plantilla_cerrada = pd.DataFrame({
    "Estacionado": ['GPS-11', 'P1', 'P2', 'P3', 'P4', 'P5', 'GPS-11'], 
    "Pto_Obs": ['P1', 'P2', 'P3', 'P4', 'P5', 'GPS-11', 'P1'],
    "Hz_G": [275, 249, 191, 281, 246, 188, 282], "Hz_M": [43, 53, 47, 3, 35, 26, 14], "Hz_S": [41.0, 14.0, 17.0, 0.0, 32.0, 50.0, 12.0],
    "Z_G": [89, 90, 90, 89, 89, 89, 89], "Z_M": [40, 0, 13, 50, 58, 21, 40], "Z_S": [53.0, 14.0, 6.0, 53.0, 3.0, 11.0, 46.0],
    "Dist_Inc": [69.249, 50.148, 57.843, 61.563, 75.728, 31.260, 69.250],
    "hi": [1.617, 1.596, 1.575, 1.551, 1.597, 1.541, 1.615], "hr": [1.700, 1.700, 1.700, 1.700, 1.700, 1.700, 1.700],
    "Registro_Fotografico": [False]*7
})

df_plantilla_abierta = pd.DataFrame({
    "Estacionado": ['GPS-09', 'C-1', 'C-2', 'C-3', 'C-4', 'C-5', 'C-6', 'C-7', 'GPS-06'],
    "Pto_Obs":     ['C-1', 'C-2', 'C-3', 'C-4', 'C-5', 'C-6', 'C-7', 'GPS-06', 'GPS-05'],
    "Hz_G": [76, 246, 135, 223, 205, 197, 162, 180, 180], "Hz_M": [56, 58, 51, 25, 20, 17, 49, 0, 0], "Hz_S": [32.0, 41.0, 53.0, 11.0, 14.0, 36.0, 57.0, 0.0, 0.0],
    "Z_G": [81, 89, 89, 89, 90, 89, 90, 90, 90], "Z_M": [4, 45, 30, 39, 14, 43, 33, 0, 0], "Z_S": [20.0, 10.0, 13.0, 21.0, 0.0, 33.0, 19.0, 0.0, 0.0],
    "Dist_Inc": [20.119, 73.699, 116.226, 96.228, 47.085, 32.462, 58.209, 50.000, 50.000],
    "hi": [1.398, 1.470, 1.528, 1.537, 1.534, 1.563, 1.550, 1.500, 1.500], "hr": [1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800, 1.800],
    "Registro_Fotografico": [False]*9
})

df_plantilla_niv_cerrada = pd.DataFrame({
    "Estaca / Punto": ["BM-1", "K0+000", "K0+010", "PC-1", "K0+020", "BM-1"],
    "Vista Atrás (V+)": [1.250, None, None, 1.420, None, None],
    "Vista Intermedia (V-)": [None, 1.100, 1.550, None, 1.320, None],
    "Vista Adelante (V-)": [None, None, None, 0.980, None, 1.685],
    "Registro_Fotografico": [False, False, False, False, False, False]
})

df_plantilla_niv_abierta = pd.DataFrame({
    "Estaca / Punto": ["BM-INICIO", "K0+000", "PC-1", "K0+010", "BM-LLEGADA"],
    "Vista Atrás (V+)": [1.500, None, 1.620, None, None],
    "Vista Intermedia (V-)": [None, 1.200, None, 1.450, None],
    "Vista Adelante (V-)": [None, None, 1.100, None, 2.505],
    "Registro_Fotografico": [False, False, False, False, False]
})

# ===================================================================
# FUNCIONES MATEMÁTICAS PARA GRÁFICOS (PLOTLY + MATPLOTLIB)
# ===================================================================
def detectar_indices_columnas(columnas):
    """
    Deduce qué columna corresponde a Punto/Norte/Este/Cota/Descripción.
    Primero intenta por el nombre de la cabecera; si el archivo no trae
    cabeceras reconocibles, asume el orden PNEZD declarado en la interfaz.
    Devuelve índices ya desplazados en 1 por el centinela "Ninguna".
    """
    alias = {
        "pto": {"punto", "pto", "id", "n_punto", "num", "numero", "número", "point"},
        "n":   {"norte", "n", "y", "north", "northing", "coord_n"},
        "e":   {"este", "e", "x", "east", "easting", "coord_e"},
        "z":   {"cota", "z", "elev", "elevacion", "elevación", "altura", "elevation"},
        "desc": {"desc", "descripcion", "descripción", "code", "codigo", "código", "obs"},
    }
    normalizadas = [str(c).strip().lower() for c in columnas]
    detectado = {}
    for clave, opciones in alias.items():
        for i, nombre in enumerate(normalizadas):
            if nombre in opciones and (i + 1) not in detectado.values():
                detectado[clave] = i + 1
                break

    # Respaldo posicional en orden PNEZD (Punto, Norte, Este, Cota, Descripción)
    respaldo = {"pto": 1, "n": 2, "e": 3, "z": 4, "desc": 5}
    n_cols = len(columnas)
    for clave, idx in respaldo.items():
        detectado.setdefault(clave, idx if idx <= n_cols else 0)

    return detectado


def calcular_intersecciones_seccion(x_vals, y_dis, y_ter):
    x_final, y_dis_final, y_ter_final = [], [], []
    for i in range(len(x_vals) - 1):
        x_final.append(x_vals[i])
        y_dis_final.append(y_dis[i])
        y_ter_final.append(y_ter[i])
        diff1 = y_ter[i] - y_dis[i]
        diff2 = y_ter[i+1] - y_dis[i+1]
        if diff1 * diff2 < 0:
            dx = x_vals[i+1] - x_vals[i]
            frac = abs(diff1) / (abs(diff1) + abs(diff2))
            x_inter = x_vals[i] + (dx * frac)
            y_inter = y_dis[i] + (y_dis[i+1] - y_dis[i]) * frac
            x_final.append(x_inter)
            y_dis_final.append(y_inter)
            y_ter_final.append(y_inter)
    x_final.append(x_vals[-1])
    y_dis_final.append(y_dis[-1])
    y_ter_final.append(y_ter[-1])
    return np.array(x_final), np.array(y_dis_final), np.array(y_ter_final)

def crear_figura_seccion_plotly(df_plot, abs_plot, esp_pav=0.10, esp_base=0.20, esp_sub=0.30):
    x_vals = df_plot['Distancia Eje (m)'].values.tolist()
    y_dis = df_plot['Cota Diseño (m)'].values.tolist()
    y_ter = df_plot['Cota Terreno (m)'].values.tolist()
    x_f, y_dis_f, y_ter_f = calcular_intersecciones_seccion(x_vals, y_dis, y_ter)
    y_min, y_max = np.minimum(y_dis_f, y_ter_f), np.maximum(y_dis_f, y_ter_f)
    
    fig = go.Figure()
    
    # Capas de Corte y Relleno Perfeccionadas (tonexty evita solapamiento)
    fig.add_trace(go.Scatter(x=x_f, y=y_min, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x_f, y=y_dis_f, fill='tonexty', fillcolor='rgba(40, 167, 69, 0.45)', line=dict(width=0), name='Relleno', hoverinfo='skip'))
    
    fig.add_trace(go.Scatter(x=x_f, y=y_dis_f, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x_f, y=y_max, fill='tonexty', fillcolor='rgba(220, 53, 69, 0.45)', line=dict(width=0), name='Corte', hoverinfo='skip'))
    
    # Capas Estructurales (Pavimento, Base, Subbase)
    y_pav = [y - esp_pav for y in y_dis]
    y_base = [y - esp_base for y in y_pav]
    y_sub = [y - esp_sub for y in y_base]
    
    fig.add_trace(go.Scatter(x=np.concatenate([x_vals, x_vals[::-1]]), y=np.concatenate([y_dis, y_pav[::-1]]), fill='toself', fillcolor='rgba(66, 66, 66, 0.8)', line=dict(width=0), name='Pavimento', hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=np.concatenate([x_vals, x_vals[::-1]]), y=np.concatenate([y_pav, y_base[::-1]]), fill='toself', fillcolor='rgba(255, 202, 40, 0.8)', line=dict(width=0), name='Base', hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=np.concatenate([x_vals, x_vals[::-1]]), y=np.concatenate([y_base, y_sub[::-1]]), fill='toself', fillcolor='rgba(141, 110, 99, 0.8)', line=dict(width=0), name='Subbase', hoverinfo='skip'))
    
    # Líneas de Terreno y Diseño (Rasante ROJA)
    fig.add_trace(go.Scatter(x=x_vals, y=y_ter, mode='lines+markers', name='Terreno', line=dict(color='#8D6E63', width=2), marker=dict(size=4, color='#5D4037')))
    fig.add_trace(go.Scatter(x=x_vals, y=y_dis, mode='lines+markers', name='Rasante (Diseño)', line=dict(color='red', width=3), marker=dict(size=4, color='darkred')))
    
    fig.add_vline(x=0, line_dash="dashdot", line_color="black", line_width=1)
    # NOTA: la propiedad font.weight sólo existe en Plotly >= 5.23; se usa
    # negrita HTML para mantener compatibilidad con versiones anteriores.
    fig.add_annotation(x=0, y=max(y_max) + 0.5, text="<b>CL</b>", showarrow=False, font=dict(color="black", size=12))
    
    fig.update_layout(title=dict(text=f'Sección K{int(abs_plot/1000)}+{abs_plot%1000:07.3f}', font=dict(size=14)), xaxis_title='Distancia Eje (m)', yaxis_title='Cota (m)', margin=dict(l=30, r=30, t=40, b=30), plot_bgcolor='rgba(245, 245, 245, 1)', showlegend=True)
    return fig

def generar_grilla_secciones_plt(df_calculado, max_cols=3, esp_pav=0.10, esp_base=0.20, esp_sub=0.30):
    df_clean = df_calculado.dropna(subset=['Cota Terreno (m)', 'Cota Diseño (m)'])
    abscisas = sorted(df_clean['Abscisa (K)'].unique())
    n = len(abscisas)
    if n == 0: return None
    
    rows = int(np.ceil(n / max_cols))
    fig, axes = plt.subplots(nrows=rows, ncols=max_cols, figsize=(15, 3.5 * rows))
    
    if rows == 1 and max_cols == 1: axes = np.array([[axes]])
    elif rows == 1: axes = np.array([axes])
    elif max_cols == 1: axes = axes.reshape(-1, 1)
        
    fig.subplots_adjust(hspace=0.6, wspace=0.3)
    
    for idx, abs_k in enumerate(abscisas):
        # Lógica de ubicación: Columna predominante, llenando de abajo hacia arriba.
        col = idx // rows
        row_from_bottom = idx % rows
        row = rows - 1 - row_from_bottom
        ax = axes[row, col]
        
        df_plot = df_clean[df_clean['Abscisa (K)'] == abs_k].sort_values('Distancia Eje (m)')
        x_vals = df_plot['Distancia Eje (m)'].values.tolist()
        y_dis = df_plot['Cota Diseño (m)'].values.tolist()
        y_ter = df_plot['Cota Terreno (m)'].values.tolist()
        
        x_f, y_dis_f, y_ter_f = calcular_intersecciones_seccion(x_vals, y_dis, y_ter)
        
        # Sombreado perfecto garantizado
        ax.fill_between(x_f, y_dis_f, y_ter_f, where=(y_ter_f >= y_dis_f), color='#DC3545', alpha=0.45, label='Corte', interpolate=True)
        ax.fill_between(x_f, y_dis_f, y_ter_f, where=(y_ter_f <= y_dis_f), color='#28A745', alpha=0.45, label='Relleno', interpolate=True)
        
        # Capas Estructurales
        y_pav = [y - esp_pav for y in y_dis]
        y_base = [y - esp_base for y in y_pav]
        y_sub = [y - esp_sub for y in y_base]
        
        ax.fill_between(x_vals, y_dis, y_pav, color='#424242', label='Pavimento')
        ax.fill_between(x_vals, y_pav, y_base, color='#FFCA28', label='Base')
        ax.fill_between(x_vals, y_base, y_sub, color='#8D6E63', label='Subbase')
        
        ax.plot(x_vals, y_ter, marker='.', color='#8D6E63', label='Terreno', linewidth=1.5)
        # Rasante ROJA
        ax.plot(x_vals, y_dis, marker='.', color='red', label='Rasante', linewidth=2.5)
        
        ax.axvline(x=0, color='black', linestyle='-.', linewidth=1, alpha=0.7)
        
        y_max = np.maximum(y_dis_f, y_ter_f)
        y_min = np.minimum(y_dis_f, y_ter_f)
        rango_y = np.max(y_max) - np.min(y_min) if np.max(y_max) != np.min(y_min) else 1.0
        ax.text(0, np.max(y_max) + (rango_y * 0.05), 'CL', ha='center', va='bottom', fontsize=9, fontweight='bold', color='black')
        
        ax.set_title(f'K{int(abs_k/1000)}+{abs_k%1000:07.3f}', fontsize=11, fontweight='bold', color='#333333', pad=15)
        ax.margins(y=0.2)
        ax.grid(True, linestyle='--', alpha=0.4)
        ax.tick_params(labelsize=9)
        if col == 0: ax.set_ylabel('Cota (m)', fontsize=9)
        if row == rows - 1: ax.set_xlabel('Distancia Eje (m)', fontsize=9)
            
    # Ocultar paneles vacíos
    for r in range(rows):
        for c in range(max_cols):
            idx_cell = c * rows + (rows - 1 - r)
            if idx_cell >= n:
                axes[r, c].set_visible(False)
        
    handles, labels = axes[rows-1, 0].get_legend_handles_labels()
    if handles:
        by_label = dict(zip(labels, handles))
        fig.legend(by_label.values(), by_label.keys(), loc='upper center', ncol=6, bbox_to_anchor=(0.5, 1.02 + (0.1/rows)), frameon=True, fontsize=10)
        
    return fig

def guardar_imagen_masa_plt(df_vol, ruta):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_vol['Abscisa (K)'], df_vol['Masa Acumulada (m³)'], color='#0D47A1', linewidth=2, marker='o', markersize=4, markerfacecolor='#FF8C00')
    ax.fill_between(df_vol['Abscisa (K)'], df_vol['Masa Acumulada (m³)'], 0, color='#0D47A1', alpha=0.2)
    ax.set_title("Diagrama de Masas (Curva Masa)", fontsize=14, fontweight='bold')
    ax.set_xlabel("Abscisa (Distancia en K)", fontsize=11)
    ax.set_ylabel("Volumen Neto Acumulado (m³)", fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.6)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)

def guardar_seccion_plt(df_plot, abs_plot, ruta):
    x_vals = df_plot['Distancia Eje (m)'].values.tolist()
    y_dis = df_plot['Cota Diseño (m)'].values.tolist()
    y_ter = df_plot['Cota Terreno (m)'].values.tolist()
    
    x_f, y_dis_f, y_ter_f = calcular_intersecciones_seccion(x_vals, y_dis, y_ter)
    
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.fill_between(x_f, y_dis_f, y_ter_f, where=(y_ter_f >= y_dis_f), color='#DC3545', alpha=0.45, label='Corte', interpolate=True)
    ax.fill_between(x_f, y_dis_f, y_ter_f, where=(y_ter_f <= y_dis_f), color='#28A745', alpha=0.45, label='Relleno', interpolate=True)
    
    ax.plot(x_vals, y_ter, marker='.', color='#8D6E63', label='Terreno', linewidth=1.5)
    ax.plot(x_vals, y_dis, marker='.', color='red', label='Rasante', linewidth=2)
    
    ax.set_title(f'Sección K{int(abs_plot/1000)}+{abs_plot%1000:07.3f}', fontsize=11, fontweight='bold')
    ax.set_xlabel('Distancia Eje (m)', fontsize=9)
    ax.set_ylabel('Cota (m)', fontsize=9)
    ax.grid(True, linestyle='--', alpha=0.4)
    fig.tight_layout()
    fig.savefig(ruta, dpi=120)
    plt.close(fig)

def guardar_perfil_altimetria_plt(df_niv, ruta):
    df_niv['Cota Ajustada'] = pd.to_numeric(df_niv['Cota Ajustada'], errors='coerce')
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_niv['Estaca / Punto'], df_niv['Cota Ajustada'], color='#FF8C00', marker='o', linewidth=2, markersize=6, markerfacecolor='#0D47A1')
    ax.set_title("Perfil Topográfico Altimétrico", fontsize=14, fontweight='bold')
    ax.set_xlabel("Estaciones de Control", fontsize=11)
    ax.set_ylabel("Elevación Geoidal (msnm)", fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)

# ===================================================================
# GENERADORES DE CACHÉ GLOBAL (PDFS)
# ===================================================================
@st.cache_data(show_spinner=False)
def cachear_pdf_volumenes(df_calc_json, df_vol_json, met, p_actual, imprimir_secciones):
    df_calculado_interno = pd.read_json(StringIO(df_calc_json))
    df_vol_interno = pd.read_json(StringIO(df_vol_json))
    
    os.makedirs("Reportes_PDF", exist_ok=True)
    ruta_masa = "Reportes_PDF/Curva_Masa.png"
    guardar_imagen_masa_plt(df_vol_interno, ruta_masa)

    paths_sec = []
    if imprimir_secciones:
        for a_val in sorted(df_calculado_interno['Abscisa (K)'].unique()):
            df_p = df_calculado_interno[df_calculado_interno['Abscisa (K)'] == a_val].copy().dropna(subset=['Cota Terreno (m)', 'Cota Diseño (m)']).sort_values('Distancia Eje (m)')
            if not df_p.empty:
                ruta_s = f"Reportes_PDF/Sec_K{a_val:.3f}.png"
                guardar_seccion_plt(df_p, a_val, ruta_s)
                paths_sec.append((a_val, ruta_s))
    
    autores = ["Kevin Stiven Cubillos Ramirez", "Sergio Eduardo Barbosa Torres"]
    tutor = "Ing. Edgar Ladino"
    tex_vol = generar_reporte_volumenes_latex(df_vol_interno, met, autores, tutor, path_masas=ruta_masa, paths_secciones=paths_sec)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(tex_vol, output_dir="Reportes_PDF", filename=f"Cubicaje_{p_actual}")
    return pdf_bytes, tex_vol, debug_msg

@st.cache_data(show_spinner=False)
def cachear_pdf_altimetria(df_niv_json, met, p_actual, tipo_niv, fotos_paths):
    df_niv_interno = pd.read_json(StringIO(df_niv_json))
    os.makedirs("Reportes_PDF", exist_ok=True)
    ruta_perfil = "Reportes_PDF/Perfil_Nivelacion.png"
    guardar_perfil_altimetria_plt(df_niv_interno, ruta_perfil)
    
    autores = ["Kevin Stiven Cubillos Ramirez", "Sergio Eduardo Barbosa Torres"]
    tutor = "Ing. Edgar Ladino"
    tex_niv = generar_reporte_nivelacion_latex(df_niv_interno, met, tipo_niv, autores, tutor, path_grafico=ruta_perfil, fotos_paths=fotos_paths)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(tex_niv, output_dir="Reportes_PDF", filename=f"Nivelacion_{p_actual}")
    return pdf_bytes, tex_niv, debug_msg

@st.cache_data(show_spinner=False)
def cachear_pdf_poli(df_campo_json, df_ajuste_json, met, p_actual, ruta_p, f_tomadas, t_app):
    df_campo_i = pd.read_json(StringIO(df_campo_json))
    df_ajuste_i = pd.read_json(StringIO(df_ajuste_json))
    autores = ["Kevin Stiven Cubillos Ramirez", "Sergio Eduardo Barbosa Torres"]
    tutor = "Ing. Edgar Ladino"
    data_tex = generar_reporte_poligonal_latex(df_campo_i, df_ajuste_i, met, t_app, autores, tutor, path_grafico=ruta_p, fotos_paths=f_tomadas)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(data_tex, output_dir="Reportes_PDF", filename=f"Reporte_{p_actual}")
    return pdf_bytes, data_tex, debug_msg

# ===================================================================
# GESTOR DE PROYECTOS Y SISTEMA DE GUARDADO LOCAL (.GP)
# ===================================================================

def generar_datos_guardado():
    tipos_seguros = (int, float, str, bool, list, dict, tuple, set, pd.DataFrame, type(None))
    estado_a_guardar = {}
    # vias_df_master_dtm es un derivado de nubes_vias_guardadas: se excluye para
    # no duplicar cientos de miles de filas dentro del archivo .gp
    llaves_prohibidas = ["sel_cargar", "sel_eliminar", "nav", "FormSubmitter", "vias_df_master_dtm"]
    
    for k, v in st.session_state.items():
        if any(k.startswith(prohibida) for prohibida in llaves_prohibidas) or k.startswith("cam_") or k.startswith("editor_"):
            continue
        if isinstance(v, tipos_seguros):
            estado_a_guardar[k] = v
            
    return pickle.dumps(estado_a_guardar)

def cargar_proyecto_desde_archivo(file_bytes, nombre):
    llaves_vitales = ["proyecto_actual", "modo_app"]
    for k in list(st.session_state.keys()):
        if k not in llaves_vitales:
            del st.session_state[k]
            
    st.session_state.proyecto_actual = nombre
    inicializar_variables_proyecto() 
    
    estado_guardado = pickle.loads(file_bytes)
    for k, v in estado_guardado.items():
        if not k.startswith("sel_"):
            st.session_state[k] = v
            
    st.session_state.modo_app = "Menu_Principal"

def inicializar_variables_proyecto():
    defaults = {
        "modo_app": "Inicio", 
        "calc_cerrada": False, "calc_abierta": False, 
        "calc_niv_cerrada": False, "calc_niv_abierta": False, 
        "calc_vol": False,
        "nubes_guardadas": {}, 
        "nubes_vias_guardadas": {},
        "poli_archivos_c": {},
        "poli_archivos_a": {},
        "proy_guardada": 0,
        "pis_vias": [],
        "last_click_id": None,
        "df_reporte_curvas": None,
        "df_dibujo_eje": None,
        "vias_dtm_bounds": None,
        "vias_dtm_ruta": None,
        "vias_df_master_dtm": None,
        "vias_mapeo_dtm": {},
        "vias_df_vertical": None,
        "vias_pts_fuera_dtm": 0,
        "vias_df_perfil": None,
        "vias_df_malla": None,
        "vias_df_vol_calc": None,
        "vias_met_vol": None,
        "vias_calc_vol": False,
        "c_n_ini": 102340.641, "c_e_ini": 87677.229, "c_z_ini": 100.0,
        "c_n_ref": 102295.280, "c_e_ref": 87588.109, "c_z_ref": 100.0,
        "c_az_g": 243, "c_az_m": 1, "c_az_s": 28.0,
        "c_tipo_amarre": "Dos Coordenadas Conocidas", "c_tipo_ang": "exterior",
        "a_n_ini": 102562.748, "a_e_ini": 86138.390, "a_z_ini": 2565.979,
        "a_n_ref_arr": 102578.559, "a_e_ref_arr": 86236.815, "a_z_ref_arr": 2569.150,
        "a_n_fin": 102379.463, "a_e_fin": 85957.573, "a_z_fin": 2565.807,
        "a_n_ref_lleg": 102478.065, "a_e_ref_lleg": 86007.693, "a_z_ref_lleg": 2566.112,
        "a_azA_g": 76, "a_azA_m": 56, "a_azA_s": 32.0, "a_azL_g": 250, "a_azL_m": 15, "a_azL_s": 10.0,
        "a_tipo_amarre_arr": "Dos Coordenadas Conocidas", "a_tipo_amarre_lleg": "Dos Coordenadas Conocidas",
        "vol_abs_ini": 0.0, "vol_abs_fin": 40.0, "vol_int_long": 10.0, "vol_ancho_izq": 6.0, "vol_ancho_der": 6.0,
        "vol_int_transv": 2.0, "vol_bom_izq": -2.0, "vol_bom_der": -2.0,
        "vol_cota_ras": 500.000, "vol_pend": 0.500, "vol_hi_ini": 504.000,
        "niv_cota_datum_c": 100.000, "niv_cota_datum_a": 500.000, "niv_cota_llegada": 499.520,
        "df_cerrada_campo": df_plantilla_cerrada.copy(), 
        "df_abierta_campo": df_plantilla_abierta.copy(), 
        "df_niv_cerrada_campo": df_plantilla_niv_cerrada.copy(),
        "df_niv_abierta_campo": df_plantilla_niv_abierta.copy(),
        "df_malla_vol": None, 
        "proyecto_actual": None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def crear_nuevo_proyecto(nombre):
    llaves_vitales = ["proyecto_actual", "modo_app"]
    for k in list(st.session_state.keys()):
        if k not in llaves_vitales:
            del st.session_state[k]
            
    st.session_state.proyecto_actual = nombre
    st.session_state.modo_app = "Menu_Principal"
    inicializar_variables_proyecto()

# ===================================================================
# INICIALIZACIÓN DE MOTORES
# ===================================================================
@st.cache_resource
def iniciar_motor_coordenadas():
    return MotorCoordenadasIGAC_V2()

motor_igac = iniciar_motor_coordenadas()
inicializar_variables_proyecto()
st.query_params.clear()

@st.cache_data(show_spinner=False)
def obtener_b64_imagen(ruta):
    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def mostrar_icono(nombre_archivo, fallback_emoji="", width=120, hover_effect=True, shadow=True, border_radius="30px"):
    ruta = os.path.join("Iconos", nombre_archivo)
    if not os.path.exists(ruta):
        ruta_alt = ruta.replace(".png", ".svg") if nombre_archivo.endswith(".png") else ruta.replace(".svg", ".png")
        if os.path.exists(ruta_alt): ruta = ruta_alt
        else:
            if fallback_emoji:
                st.markdown(f"<div style='text-align:center; font-size:{width*0.7}px;'>{fallback_emoji}</div>", unsafe_allow_html=True)
            return

    b64 = obtener_b64_imagen(ruta)
    mime_type = "image/svg+xml" if ruta.endswith(".svg") else "image/png"
    css_class = f"icono-{nombre_archivo.replace('.','-')}"
    
    html = f"<style>.{css_class} {{ width: {width}px; border-radius: {border_radius}; display: block; margin: 0 auto; cursor: default;"
    if shadow: html += "box-shadow: 0 8px 16px rgba(0,0,0,0.2);"
    if hover_effect and shadow: html += f"}} .{css_class}:hover {{ transform: scale(1.05) translateY(-5px); box-shadow: 0 12px 20px rgba(0,0,0,0.3); "
    html += "}</style>"
    
    img_html = f'<img src="data:{mime_type};base64,{b64}" class="{css_class}">'
    st.markdown(f'{html}<div style="text-align:center;">{img_html}</div><br>', unsafe_allow_html=True)

def renderizar_banner_proyecto():
    if st.session_state.get("proyecto_actual"):
        with st.container():
            st.markdown(f"""
            <div style='background-color: #E3F2FD; padding: 15px; border-radius: 10px; border-left: 8px solid #2196F3; margin-bottom: 15px;'>
                <h4 style='color: #0D47A1; margin: 0;'>Espacio de Trabajo Activo: {st.session_state.get("proyecto_actual")}</h4>
                <p style='margin: 0; color: #1565C0; font-size: 14px;'>Asegúrese de descargar el archivo de seguridad local para preservar su progreso.</p>
            </div>
            """, unsafe_allow_html=True)
            
            datos_gp = generar_datos_guardado()
            st.download_button(
                label="Descargar Copia de Seguridad (.gp)",
                data=datos_gp,
                file_name=f"{st.session_state.get('proyecto_actual')}.gp",
                mime="application/octet-stream",
                use_container_width=True,
                type="primary"
            )
            st.markdown("<br>", unsafe_allow_html=True)

# ===================================================================
# BARRA LATERAL (SIDEBAR)
# ===================================================================
with st.sidebar:
    mostrar_icono("logo_geopol.svg", "", width=220, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("---")
    
    if st.session_state.get("proyecto_actual"):
        st.info(f"**Proyecto Activo:**\n### {st.session_state.get('proyecto_actual')}")
        
        datos_gp = generar_datos_guardado()
        st.download_button(
            label="Guardar Proyecto Localmente (.gp)",
            data=datos_gp,
            file_name=f"{st.session_state.get('proyecto_actual')}.gp",
            mime="application/octet-stream",
            use_container_width=True,
            type="primary"
        )
            
        if st.button("Cerrar Proyecto", use_container_width=True):
            st.session_state.proyecto_actual = None
            st.session_state.modo_app = "Inicio"
            st.rerun()
        st.markdown("---")
        
    st.markdown("### Navegación de Módulos")
    if st.button("Inicio", use_container_width=True):
        st.session_state.modo_app = "Inicio"
        st.rerun()
        
    if st.session_state.get("proyecto_actual"):
        if st.button("Menú Principal", use_container_width=True):
            st.session_state.modo_app = "Menu_Principal"
            st.rerun()
        if st.button("Módulo de Planimetría", use_container_width=True):
            st.session_state.modo_app = "Menu_Poligonales"
            st.rerun()
        if st.button("Módulo de Altimetría", use_container_width=True):
            st.session_state.modo_app = "Menu_Altimetria"
            st.rerun()
        if st.button("Módulo Nube de Puntos", use_container_width=True):
            st.session_state.modo_app = "Nube_Puntos"
            st.rerun()
        if st.button("Módulo Diseño Vial", use_container_width=True):
            st.session_state.modo_app = "Diseno_Vias"
            st.rerun()

    st.markdown("---")
    mostrar_icono("logo_udistrital.png", "", width=160, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("<p style='text-align:center; font-size:12px; color:gray;'>Kevin Cubillos & Sergio Barbosa</p>", unsafe_allow_html=True)


if st.session_state.modo_app in ["Inicio", "Menu_Principal"]:
    col_logo, col_info = st.columns([1, 4])
    with col_logo:
        mostrar_icono("logo_udistrital.png", "", width=180, hover_effect=False, shadow=False, border_radius="0px")
    with col_info:
        st.markdown("## **UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS**")
        st.markdown("#### **Facultad Tecnológica - Ingeniería Civil**")
        st.markdown("**Trabajo de Grado:** Desarrollo de un Geoportal Web para la Automatización del Cálculo de datos Topográficos")
        
        st.markdown("""
        <div style='background-color: #f8f9fa; padding: 12px; border-radius: 8px; border-left: 5px solid #FF8C00; margin-top: 10px;'>
            <span style='color: #0D47A1; font-size: 15px;'><b>Tutor:</b> Ing. Edgar Ladino &nbsp; | &nbsp; <b>Autores:</b> Kevin Stiven Cubillos Ramirez & Sergio Eduardo Barbosa Torres</span>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("---")

# ===================================================================
# PANTALLAS DE NAVEGACIÓN
# ===================================================================
if st.session_state.modo_app == "Inicio":
    col_hero1, col_hero2, col_hero3 = st.columns([1, 2, 1])
    with col_hero2:
        mostrar_icono("logo_geopol.svg", "", width=350, hover_effect=False, shadow=False)
        st.markdown("<h3 style='text-align: center; color: #4A4A4A; margin-top: -30px; font-weight: 600;'>Plataforma Integral de Ingeniería Topográfica</h3>", unsafe_allow_html=True)
    
    st.markdown("---")
    tab_proyectos, tab_sobre, tab_equipo = st.tabs(["Gestor de Proyectos", "Acerca del Sistema", "Equipo de Desarrollo"])
    
    with tab_proyectos:
        st.markdown("### Centro de Trabajo")
        st.caption("Cree un nuevo entorno de trabajo en blanco o restaure el estado de un proyecto cargando su archivo local (.gp).")
        
        col_new, col_load = st.columns(2)
        with col_new:
            st.success("**Iniciar Nuevo Proyecto**")
            nuevo_nombre = st.text_input("Asignar nombre del proyecto:")
            if st.button("Crear Espacio de Trabajo", use_container_width=True):
                if nuevo_nombre.strip() == "": st.warning("Advertencia: Debe asignar una nomenclatura válida al proyecto.")
                else: crear_nuevo_proyecto(nuevo_nombre.strip()); st.rerun()
        with col_load:
            st.info("**Restaurar Copia de Seguridad**")
            archivo_gp = st.file_uploader("Importar archivo de proyecto de GeoPol Web (.gp)", type=['gp'])
            if archivo_gp is not None:
                if st.button("Cargar Espacio de Trabajo", use_container_width=True): 
                    nombre_base = archivo_gp.name.replace(".gp", "")
                    cargar_proyecto_desde_archivo(archivo_gp.getvalue(), nombre_base)
                    st.rerun()

    with tab_sobre:
        col_txt, col_img = st.columns([2, 1])
        with col_txt:
            st.markdown("### Arquitectura del Geoportal Web")
            st.write("El procesamiento de datos topográficos en gabinete representa históricamente un segmento crítico y susceptible a desviaciones sistemáticas. GeoPol Web se consolida como una solución integral que estandariza y automatiza estos procedimientos operativos.")
            st.markdown("### Características Técnicas")
            st.markdown("- Motor Matemático 2D y Renderizado Planimétrico Automatizado.\n- Interpolación de Superficies y Diseño Civil 3D en Tiempo Real.\n- Generación Niva de Reportes Académicos e Ingeniería en formato LaTeX.\n- Exportación e Interoperabilidad hacia Entornos GIS y CAD Industriales.")
        with col_img:
            mostrar_icono("planimetria.png", "", width=250, shadow=False)
            mostrar_icono("volumenes.png", "", width=250, shadow=False)

    with tab_equipo:
        st.markdown("<h3 style='text-align:center;'>Dirección y Estructuración del Proyecto</h3><br>", unsafe_allow_html=True)
        col_k, col_s, col_e = st.columns(3)
        with col_k:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #f8f9fa; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            mostrar_icono("kevin.png", "", width=120, shadow=False)
            st.markdown("### Kevin Cubillos")
            st.caption("Desarrollador Core & Co-Autor")
            st.write("Investigador adscrito a la Universidad Distrital. Dirección de la arquitectura en Python y desarrollo del ecosistema integral de procesamiento topográfico.")
            st.markdown("</div>", unsafe_allow_html=True)
        with col_s:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #f8f9fa; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            mostrar_icono("sergio.png", "", width=120, shadow=False)
            st.markdown("### Sergio Barbosa")
            st.caption("Co-Autor & Analista Espacial")
            st.write("Investigador adscrito a la Universidad Distrital. Estructuración del marco de aseguramiento de calidad geométrica y estandarización hacia parámetros GIS/CAD.")
            st.markdown("</div>", unsafe_allow_html=True)
        with col_e:
            st.markdown("<div style='text-align:center; padding: 20px; background-color: #fff4e6; border-radius: 15px; border: 2px solid #FF8C00; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
            mostrar_icono("edgar.png", "", width=120, shadow=False)
            st.markdown("### Ing. Edgar Ladino")
            st.caption("Director del Proyecto de Grado")
            st.write("Dirección académica e institucional, proporcionando el marco metodológico base para la consolidación tecnológica y viabilidad del sistema experto.")
            st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.modo_app == "Menu_Principal":
    st.markdown("<h4 style='text-align: center; color: gray;'>Seleccione el Entorno de Trabajo Operativo</h4><br>", unsafe_allow_html=True)
    col_disc1, col_disc2, col_disc3, col_disc4 = st.columns(4)
    with col_disc1:
        mostrar_icono("planimetria.png", "", width=180)
        if st.button("Planimetría", use_container_width=True): st.session_state.modo_app = "Menu_Poligonales"; st.rerun()
    with col_disc2:
        mostrar_icono("altimetria.png", "", width=180)
        if st.button("Altimetría", use_container_width=True): st.session_state.modo_app = "Menu_Altimetria"; st.rerun()
    with col_disc3:
        mostrar_icono("nube_puntos.png", "", width=180)
        if st.button("Nube de Puntos", use_container_width=True): st.session_state.modo_app = "Nube_Puntos"; st.rerun()
    with col_disc4:
        mostrar_icono("volumenes.png", "", width=180)
        if st.button("Diseño Vial", use_container_width=True): st.session_state.modo_app = "Diseno_Vias"; st.rerun()

elif st.session_state.modo_app == "Menu_Poligonales":
    st.markdown("<h3 style='text-align: center; color: #4A4A4A;'>Análisis Planimétrico (Poligonales)</h3><br>", unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        mostrar_icono("poligonal_cerrada.png", "", width=240)
        if st.button("Ejecutar Circuito Cerrado", use_container_width=True): st.session_state.modo_app = "Cerrada"; st.rerun()
    with colB:
        mostrar_icono("poligonal_abierta.png", "", width=240)
        if st.button("Ejecutar Poligonal Abierta", use_container_width=True): st.session_state.modo_app = "Abierta"; st.rerun()

elif st.session_state.modo_app == "Menu_Altimetria":
    st.markdown("<h3 style='text-align: center; color: #4A4A4A;'>Control Altimétrico y Análisis Vertical</h3><br>", unsafe_allow_html=True)
    colA, colB, colC = st.columns(3)
    with colA:
        mostrar_icono("niv_cerrada.png", "", width=180)
        if st.button("Nivelación de Circuito Cerrado", use_container_width=True): st.session_state.modo_app = "Niv_Cerrada"; st.rerun()
    with colB:
        mostrar_icono("niv_abierta.png", "", width=180)
        if st.button("Nivelación de Circuito Abierto", use_container_width=True): st.session_state.modo_app = "Niv_Abierta"; st.rerun()
    with colC:
        mostrar_icono("volumenes.png", "", width=180)
        if st.button("Cálculo de Volúmenes y Diseño", use_container_width=True): st.session_state.modo_app = "Volumenes"; st.rerun()

# ===================================================================
# MÓDULO DE NUBE DE PUNTOS (GIS MULTI-ARCHIVO INDEPENDIENTE)
# ===================================================================
elif st.session_state.modo_app == "Nube_Puntos":
    renderizar_banner_proyecto()
    st.title("Sistema de Información Espacial (Nubes de Puntos)")
    st.markdown("Plataforma de visualización para la importación y consolidación de archivos topográficos masivos. Permite validar georreferenciación de la radiación de campo sobre cartografía oficial base.")
    
    lista_proyecciones_disp = list(motor_igac.transformadores.keys())
    nombre_proyeccion = st.selectbox("Configuración del Sistema de Referencia Geodésico:", lista_proyecciones_disp, index=st.session_state.get("proy_guardada", 0))
    st.session_state.proy_guardada = lista_proyecciones_disp.index(nombre_proyeccion)
    trans_to_wgs = motor_igac.transformadores_inversos[nombre_proyeccion]

    st.markdown("---")
    st.subheader("1. Importación de Archivos de Campo")
    st.info("Nota Técnica Operativa: Permite anexar series de archivos de coordenadas delimitados (.csv, .txt). Se consolidarán automáticamente en memoria. Formato recomendado de tabulación: PNEZD (Punto, Norte, Este, Elevación, Descripción).")
    
    archivos_nube = st.file_uploader("Arrastre o seleccione sus bases de datos espaciales", type=['csv', 'txt'], accept_multiple_files=True)
    
    if archivos_nube:
        for archivo in archivos_nube:
            if archivo.name not in st.session_state.nubes_guardadas:
                try:
                    df_temp = procesar_archivo_nube(archivo)
                    st.session_state.nubes_guardadas[archivo.name] = df_temp
                except Exception as e:
                    st.error(f"Error crítico en la lectura del archivo '{archivo.name}': {e}")
                    
    if st.session_state.nubes_guardadas:
        st.markdown("**Estado de Memoria (Archivos Cargados):**")
        nombres_archivos = list(st.session_state.nubes_guardadas.keys())
        total_puntos = sum(len(df) for df in st.session_state.nubes_guardadas.values())
        st.success(f"Se han consolidado {len(nombres_archivos)} documento(s) con una sumatoria global de {total_puntos} vectores.")
        
        for n_arch in nombres_archivos:
            c_info, c_btn = st.columns([5, 1])
            c_info.write(f"{n_arch} - ({len(st.session_state.nubes_guardadas[n_arch])} registros)")
            if c_btn.button("Remover", key=f"del_{n_arch}"):
                del st.session_state.nubes_guardadas[n_arch]
                st.rerun()
                
        if st.button("Purgar Memoria Total", type="secondary"):
            st.session_state.nubes_guardadas = {}
            st.rerun()

    if st.session_state.nubes_guardadas:
        st.markdown("---")
        st.subheader("2. Emparejamiento Paramétrico de Columnas")
        st.caption("Verifique la correcta asignación de cabeceras vectoriales para cada archivo estructurado en la memoria.")
        
        mapeo_archivos = {}
        for n_arch, df_bruto in st.session_state.nubes_guardadas.items():
            with st.expander(f"Asignación estructural: {n_arch} ({len(df_bruto)} entidades)", expanded=(len(st.session_state.nubes_guardadas)==1)):
                st.dataframe(df_bruto.head(5), use_container_width=True)
                cols = ["Ninguna"] + list(df_bruto.columns)
                idx_auto = detectar_indices_columnas(list(df_bruto.columns))
                c1, c2, c3, c4, c5 = st.columns(5)
                
                col_pto = c1.selectbox("Identificador (Punto)", cols, index=idx_auto["pto"], key=f"pto_{n_arch}")
                col_e = c2.selectbox("Este (Coordenada X)", cols, index=idx_auto["e"], key=f"e_{n_arch}")
                col_n = c3.selectbox("Norte (Coordenada Y)", cols, index=idx_auto["n"], key=f"n_{n_arch}")
                col_z = c4.selectbox("Elevación (Cota Z)", cols, index=idx_auto["z"], key=f"z_{n_arch}")
                col_desc = c5.selectbox("Descripción / Código", cols, index=idx_auto["desc"], key=f"desc_{n_arch}")
                
                mapeo_archivos[n_arch] = {"pto": col_pto, "e": col_e, "n": col_n, "z": col_z, "desc": col_desc}
        
        st.markdown("---")
        st.subheader("3. Mapeo y Parametrización Visual")
        
        col_vis1, col_vis2 = st.columns(2)
        with col_vis1:
            modo_vista = st.radio("Configuración de Motor de Renderizado:", 
                                ["Rendimiento Óptimo (Agrupación / Clúster Espacial)", 
                                 "Detalle de Alta Precisión (Renderizado Individual Analítico)"], 
                                horizontal=False)
            
            generar_dtm = st.checkbox("Interpolar Modelo Digital de Terreno (TIN) y Mapear Curvas de Nivel", value=False)
            
        with col_vis2:
            opciones_mapa = {
                "ESRI Satélite (Alta Resolución)": {"tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "attr": "Esri"},
                "Google Híbrido (Satélite + Vías)": {"tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "attr": "Google"},
                "OpenStreetMap (Catastro)": {"tiles": "OpenStreetMap", "attr": None},
                "Modo Oscuro (Analítico CartoDB)": {"tiles": "CartoDB dark_matter", "attr": None}
            }
            tipo_mapa = st.selectbox("Capa Base Geoespacial:", list(opciones_mapa.keys()), key="map_nube")
        
        if st.button("Ejecutar Construcción Espacial Multicapa", type="primary", use_container_width=True):
            archivos_invalidos = []
            for n_arch, map_val in mapeo_archivos.items():
                if map_val["e"] == "Ninguna" or map_val["n"] == "Ninguna":
                    archivos_invalidos.append(n_arch)
                    
            if archivos_invalidos:
                st.warning(f"Error de Integridad: Configuración vectorial incompleta para los componentes Este y Norte en: {', '.join(archivos_invalidos)}")
            else:
                with st.spinner("Compilando transformación geodésica y empaquetando sistema de control de capas..."):
                    todas_latitudes = []
                    todas_longitudes = []
                    
                    t_tiles = opciones_mapa[tipo_mapa]["tiles"]
                    t_attr = opciones_mapa[tipo_mapa]["attr"]
                    
                    if t_attr: mapa_nube = folium.Map(zoom_start=18, max_zoom=22, tiles=t_tiles, attr=t_attr)
                    else: mapa_nube = folium.Map(zoom_start=18, max_zoom=22, tiles=t_tiles)
                    
                    colores_archivos = ['#FF8C00', '#0D47A1', '#E53935', '#43A047', '#8E24AA', '#FDD835']
                    color_idx = 0
                    
                    dfs_para_dtm = []

                    for nombre_archivo, map_val in mapeo_archivos.items():
                        df_bruto = st.session_state.nubes_guardadas[nombre_archivo]
                        df_limpio = asignar_columnas(
                            df_bruto, 
                            None if map_val["pto"] == "Ninguna" else map_val["pto"],
                            map_val["e"],
                            map_val["n"],
                            None if map_val["z"] == "Ninguna" else map_val["z"],
                            None if map_val["desc"] == "Ninguna" else map_val["desc"]
                        )
                        
                        if generar_dtm:
                            dfs_para_dtm.append(df_limpio)
                        
                        color_actual = colores_archivos[color_idx % len(colores_archivos)]
                        color_idx += 1
                        
                        fg = folium.FeatureGroup(name=nombre_archivo)
                        
                        if "Agrupación" in modo_vista:
                            parent = MarkerCluster(name=nombre_archivo).add_to(fg)
                            radio_p = 5
                        else:
                            parent = fg
                            radio_p = 2
                        
                        for idx, row in df_limpio.iterrows():
                            # Fix TYPE: force to float
                            lon_wgs, lat_wgs = trans_to_wgs.transform(float(row['Este']), float(row['Norte']))
                            todas_latitudes.append(lat_wgs)
                            todas_longitudes.append(lon_wgs)
                            
                            html_popup = f"<b>Documento Origen:</b> {nombre_archivo}<br><b>ID Entidad:</b> {row['Punto']}<br><b>E [X]:</b> {float(row['Este']):.3f}<br><b>N [Y]:</b> {float(row['Norte']):.3f}<br><b>Cota [Z]:</b> {float(row['Cota']):.3f}<br><b>Código/Descr.:</b> {row['Descripcion']}"
                            folium.CircleMarker(
                                location=[lat_wgs, lon_wgs],
                                radius=radio_p,
                                color=color_actual,
                                fill=True,
                                fill_color=color_actual,
                                fill_opacity=0.8,
                                popup=folium.Popup(html_popup, max_width=300),
                                tooltip=str(row['Punto'])
                            ).add_to(parent)
                            
                        fg.add_to(mapa_nube)
                        
                    if generar_dtm and dfs_para_dtm:
                        df_master_dtm = pd.concat(dfs_para_dtm, ignore_index=True)
                        if (df_master_dtm['Cota'] != 0.0).any():
                            try:
                                ruta_dtm = "Reportes_PDF/dtm_overlay.png"
                                bounds_dtm = generar_dtm_curvas(df_master_dtm, ruta_dtm, trans_to_wgs)
                                folium.raster_layers.ImageOverlay(
                                    image=ruta_dtm,
                                    bounds=bounds_dtm,
                                    opacity=0.85,
                                    name="Modelo Digital de Terreno (TIN)"
                                ).add_to(mapa_nube)
                            except Exception as e:
                                st.error(f"Imposible generar superficie TIN: {e}")
                        else:
                            st.warning("No se encontraron cotas (Z) válidas para generar las curvas de nivel.")
                    
                    if todas_latitudes and todas_longitudes:
                        mapa_nube.fit_bounds([
                            [min(todas_latitudes), min(todas_longitudes)],
                            [max(todas_latitudes), max(todas_longitudes)]
                        ])
                        
                    folium.LayerControl().add_to(mapa_nube)
                    st_folium(mapa_nube, width=1100, height=650, returned_objects=[])

# ===================================================================
# MÓDULO DE VOLÚMENES Y DISEÑO 3D (BÁSICO)
# ===================================================================
elif st.session_state.modo_app in ["Volumenes"]:
    renderizar_banner_proyecto()
    st.title("Diseño de Obra Civil y Computo de Volúmenes 3D")
    
    st.header("1. Parametrización Geométrica Base")
    col_img, col_params = st.columns([1, 2.5])
    with col_img:
        mostrar_icono("seccion_tipica.png", "", width=220, hover_effect=False, shadow=False)
        st.caption("Diagrama Estructural: Sección Típica Transversal")

    with col_params:
        tab_eje, tab_sec, tab_datum, tab_est = st.tabs(["Alineamiento y Estacionamiento", "Parámetros de Sección Típica", "Condicionantes de Elevación", "Capas Estructurales"])
        with tab_eje:
            c1, c2, c3 = st.columns(3)
            abs_ini = c1.number_input("Abscisa (Estación) Inicial (K)", value=0.0, step=10.0, format="%.3f")
            abs_fin = c2.number_input("Abscisa (Estación) Final (K)", value=40.0, step=10.0, format="%.3f")
            int_long = c3.number_input("Intervalo de Generación Longitudinal (m)", value=10.0, step=5.0, format="%.3f")
        with tab_sec:
            c1, c2, c3 = st.columns(3)
            ancho_izq = c1.number_input("Desplazamiento Calzada Izquierda (m)", value=3.6, step=1.0, format="%.3f")
            ancho_der = c2.number_input("Desplazamiento Calzada Derecha (m)", value=3.6, step=1.0, format="%.3f")
            int_transv = c3.number_input("Intervalo Muestral Transversal (m)", value=2.0, step=1.0, format="%.3f")
            bom_izq = c1.number_input("Inclinación Bombeo Izquierdo (%)", value=-2.0, step=0.5, format="%.3f")
            bom_der = c2.number_input("Inclinación Bombeo Derecho (%)", value=-2.0, step=0.5, format="%.3f")
        with tab_datum:
            c1, c2 = st.columns(2)
            cota_rasante_ini = c1.number_input("Cota Inicial Eje Proyecto (Rasante)", value=500.000, format="%.3f")
            pend_long = c1.number_input("Gradiente Longitudinal Proyecto (%)", value=0.500, step=0.5, format="%.3f")
            hi_ini = c2.number_input("Elevación Inicial Instrumental (BM/HI)", value=504.000, format="%.3f")
        with tab_est:
            c1, c2, c3 = st.columns(3)
            esp_pav = c1.number_input("Espesor Pavimento (m)", value=0.10, step=0.05, format="%.2f")
            esp_base = c2.number_input("Espesor Base (m)", value=0.20, step=0.05, format="%.2f")
            esp_sub = c3.number_input("Espesor Subbase (m)", value=0.30, step=0.05, format="%.2f")
            st.session_state.esp_pav = esp_pav
            st.session_state.esp_base = esp_base
            st.session_state.esp_sub = esp_sub

    if st.button("Ejecutar Generación de Malla de Levantamiento", type="secondary", use_container_width=True):
        try:
            st.session_state.cota_rasante_ini_mem = cota_rasante_ini
            st.session_state.pend_long_mem = pend_long
            st.session_state.abs_ini_mem = abs_ini
            st.session_state.bom_izq_memory = bom_izq
            st.session_state.bom_der_memory = bom_der
            
            st.session_state.df_malla_vol = generar_malla_vacia(abs_ini, abs_fin, int_long, ancho_izq, ancho_der, int_transv, hi_ini)
            for i, row in st.session_state.df_malla_vol.iterrows():
                abs_k = row['Abscisa (K)']
                dist = row['Distancia Eje (m)']
                terr_base = 502.0 - (abs_k / 10.0) * 1.2
                terr_elev = terr_base - (dist * 0.15) 
                current_hi = 504.0 if abs_k < 30.0 else 501.0
                st.session_state.df_malla_vol.at[i, 'Lectura Mira (-)'] = round(current_hi - terr_elev, 3)
            st.session_state.calc_vol = False
        except Exception as e:
            st.error(f"Falla computacional en la matriz: {e}")

    if st.session_state.get("df_malla_vol") is not None:
        st.markdown("---")
        st.header("2. Ingreso Analítico de Cartera (Cálculos Dinámicos)")
        
        if "editor_vol_key" in st.session_state:
            cambios = st.session_state["editor_vol_key"]
            if "edited_rows" in cambios:
                for idx_str, row_changes in cambios["edited_rows"].items():
                    for col, val in row_changes.items():
                        st.session_state.df_malla_vol.loc[int(idx_str), col] = val
                        
        df_calculado = calcular_cotas_seccion(
            st.session_state.df_malla_vol, st.session_state.bom_izq_memory, st.session_state.bom_der_memory,
            st.session_state.cota_rasante_ini_mem, st.session_state.pend_long_mem, st.session_state.abs_ini_mem
        )
        st.session_state.df_malla_vol = df_calculado.copy()
        
        def highlight_eje(row): return ['background-color: rgba(255, 235, 59, 0.3)'] * len(row) if row.get('Distancia Eje (m)', 1) == 0.0 else [''] * len(row)
        
        st.session_state.df_malla_vol = st.data_editor(
            st.session_state.df_malla_vol.style.apply(highlight_eje, axis=1), 
            key="editor_vol_key", num_rows="dynamic", use_container_width=True,
            disabled=["Abscisa (K)", "Distancia Eje (m)", "Cota Terreno (m)", "Cota Diseño (m)"],
            column_config={
                "Abscisa (K)": st.column_config.NumberColumn(format="%.3f"),
                "Distancia Eje (m)": st.column_config.NumberColumn(format="%.3f"),
                "Altura Inst. (HI)": st.column_config.NumberColumn(format="%.3f"),
                "Lectura Mira (-)": st.column_config.NumberColumn(format="%.3f"),
                "Cota Terreno (m)": st.column_config.NumberColumn(format="%.3f"),
                "Cota Diseño (m)": st.column_config.NumberColumn(format="%.3f")
            }
        )

        st.markdown("### Superficie 3D: Modelado de Terreno y Estructura de Diseño")
        pivot_diseno = df_calculado.pivot_table(index='Abscisa (K)', columns='Distancia Eje (m)', values='Cota Diseño (m)', dropna=False)
        pivot_terreno = df_calculado.pivot_table(index='Abscisa (K)', columns='Distancia Eje (m)', values='Cota Terreno (m)', dropna=False)
        
        fig3d = go.Figure()
        fig3d.add_trace(go.Surface(z=pivot_diseno.values, x=pivot_diseno.columns.values, y=pivot_diseno.index.values, colorscale=[[0, 'rgba(176, 190, 197, 0.95)'], [1, 'rgba(176, 190, 197, 0.95)']], opacity=0.95, name='Capa Diseño Vial', showscale=False))
        if not np.isnan(pivot_terreno.values).all():
            fig3d.add_trace(go.Surface(z=pivot_terreno.values, x=pivot_diseno.columns.values, y=pivot_diseno.index.values, colorscale='YlOrBr', opacity=0.75, name='Capa Terreno Original', showscale=False))
        fig3d.update_layout(scene=dict(aspectmode='manual', aspectratio=dict(x=1, y=2.5, z=0.5)), margin=dict(l=0, r=0, b=0, t=0), height=550)
        st.plotly_chart(fig3d, use_container_width=True)

        if st.button("Ejecutar Análisis de Movimiento de Tierras (Cubicaje)", type="primary", use_container_width=True):
            try:
                res_df, metricas = calcular_cubicaje_total(df_calculado)
                if 'Volumen Neto (m³)' in res_df.columns:
                    res_df['Masa Acumulada (m³)'] = res_df['Volumen Neto (m³)'].cumsum()
                else:
                    v_neto = res_df['Vol. Corte (m³)'].fillna(0) - res_df['Vol. Relleno (m³)'].fillna(0)
                    res_df['Masa Acumulada (m³)'] = v_neto.cumsum()
                
                st.session_state.df_vol_calc = res_df
                st.session_state.met_vol = metricas
                st.session_state.calc_vol = True
            except Exception as e:
                st.error(f"Falla detectada en la consistencia numérica de las matrices. Asegure entradas continuas. Diagnóstico: {e}")

    if st.session_state.calc_vol:
        st.success("Integración matemática completada. Áreas y volúmenes parametrizados correctamente.")
        met = st.session_state.met_vol
        df_vol_final = st.session_state.df_vol_calc
        
        colA, colB, colC = st.columns(3)
        colA.metric("Volumen de Excavación (Corte Total)", f"{met['Corte_Total']:.3f} m³")
        colB.metric("Volumen de Terraplén (Relleno Total)", f"{met['Relleno_Total']:.3f} m³")
        colC.metric("Balance de Compensación Volumétrico", f"{met['Volumen_Neto']:.3f} m³", delta="Superávit Operativo" if met['Volumen_Neto']>0 else "Déficit Estructural", delta_color="off")
        
        st.subheader("Cuadro Consolidado de Cómputo de Volúmenes")
        st.dataframe(df_vol_final.style.format("{:.3f}"), use_container_width=True)
        
        st.markdown("---")
        st.subheader("Análisis Longitudinal: Diagrama Curva Masa")
        fig_masa = go.Figure()
        fig_masa.add_trace(go.Scatter(x=df_vol_final['Abscisa (K)'], y=df_vol_final['Masa Acumulada (m³)'], mode='lines+markers', fill='tozeroy', line=dict(color='#0D47A1', width=3), marker=dict(size=8, color='#FF8C00')))
        fig_masa.update_layout(xaxis_title='Abscisa / Estacionamiento', yaxis_title='Volumen Neto Compensado (m³)', height=450, plot_bgcolor='rgba(245, 245, 245, 0.8)')
        st.plotly_chart(fig_masa, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Análisis Transversal: Secciones Generadas")
        abs_plot = st.selectbox("Indique abscisa a inspeccionar analíticamente:", df_calculado['Abscisa (K)'].unique())
        df_plot = df_calculado[df_calculado['Abscisa (K)'] == abs_plot].copy().dropna(subset=['Cota Terreno (m)', 'Cota Diseño (m)']).sort_values(by='Distancia Eje (m)').reset_index(drop=True)
        
        if not df_plot.empty:
            fig_visual = crear_figura_seccion_plotly(df_plot, abs_plot, st.session_state.get('esp_pav', 0.1), st.session_state.get('esp_base', 0.2), st.session_state.get('esp_sub', 0.3))
            fig_visual.update_layout(height=550)
            st.plotly_chart(fig_visual, use_container_width=True)
            
            fig_grilla_vol = generar_grilla_secciones_plt(df_calculado, 3, st.session_state.get('esp_pav', 0.1), st.session_state.get('esp_base', 0.2), st.session_state.get('esp_sub', 0.3))
            if fig_grilla_vol:
                st.pyplot(fig_grilla_vol)

        st.markdown("---")
        with st.expander("Consolidación y Exportación Técnica (PDF / Código LaTeX)", expanded=True):
            st.info("El protocolo de generación ensamblará automáticamente las memorias de cálculo evaluadas.")
            if st.button("Compilar Documento Estructural de Ingeniería", type="primary", use_container_width=True, key="btn_vol"):
                with st.spinner("Procesando dependencias gráficas y compilando protocolo LaTeX..."):
                    df_calc_json = df_calculado.to_json()
                    df_vol_json = df_vol_final.to_json()
                    p_act = st.session_state.get('proyecto_actual') or "Proyecto"
                    
                    pdf_bytes, tex_vol, debug_msg = cachear_pdf_volumenes(df_calc_json, df_vol_json, met, p_act, False)
                    
                    st.session_state.vol_pdf_bytes = pdf_bytes
                    st.session_state.vol_tex_code = tex_vol
                    st.session_state.vol_debug_msg = debug_msg
            
            if st.session_state.get('vol_pdf_bytes'):
                st.success("Compilación en formato PDF ejecutada sin incidencias técnicas.")
                b64_pdf = base64.b64encode(st.session_state.vol_pdf_bytes).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
            elif st.session_state.get('vol_tex_code'):
                st.warning(f"Error de Integración: Ausencia del motor local TeX Live. Diagnóstico: {st.session_state.vol_debug_msg}")
                st.download_button("Descargar Código Base (.TEX)", st.session_state.vol_tex_code, f"Cubicaje_{st.session_state.get('proyecto_actual')}.tex", "text/plain", use_container_width=True)

# ------------------ MÓDULOS DE NIVELACIÓN NORMAL ------------------
elif st.session_state.modo_app in ["Niv_Cerrada", "Niv_Abierta"]:
    renderizar_banner_proyecto()
            
    if st.session_state.modo_app == "Niv_Cerrada":
        st.title("Red Altimétrica: Nivelación Geométrica de Circuito Cerrado")
        st.header("1. Cota de Referencia y Anclaje Inicial")
        st.session_state.niv_cota_datum_c = st.number_input("Elevación Inicial Asignada (Banco de Nivel 1)", value=st.session_state.niv_cota_datum_c, format="%.3f")
        cota_datum = st.session_state.niv_cota_datum_c
        cota_llegada = None 
        st.header("2. Ingreso Estructurado de Cartera Altimétrica")
        
        st.session_state.df_niv_cerrada_campo = st.data_editor(
            st.session_state.df_niv_cerrada_campo, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={"Registro_Fotografico": st.column_config.CheckboxColumn("Registro Fotográfico")}
        )
        df_niv_activo = st.session_state.df_niv_cerrada_campo
    else:
        st.title("Red Altimétrica: Nivelación Geométrica Lineal (Circuito Abierto con Control)")
        col1, col2 = st.columns(2)
        with col1:
            st.header("1. Cota de Referencia Inicial")
            st.session_state.niv_cota_datum_a = st.number_input("Elevación Inicial Asignada (Banco de Nivel Partida)", value=st.session_state.niv_cota_datum_a, format="%.3f")
            cota_datum = st.session_state.niv_cota_datum_a
        with col2:
            st.header("2. Punto de Amarre y Control de Cierre")
            st.session_state.niv_cota_llegada = st.number_input("Elevación Conocida de Amarre (Banco de Nivel Llegada)", value=st.session_state.niv_cota_llegada, format="%.3f")
            cota_llegada = st.session_state.niv_cota_llegada
        st.header("3. Ingreso Estructurado de Cartera Altimétrica")
        
        st.session_state.df_niv_abierta_campo = st.data_editor(
            st.session_state.df_niv_abierta_campo, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={"Registro_Fotografico": st.column_config.CheckboxColumn("Registro Fotográfico")}
        )
        df_niv_activo = st.session_state.df_niv_abierta_campo

    estaciones_con_foto_niv = df_niv_activo[df_niv_activo["Registro_Fotografico"] == True]["Estaca / Punto"].unique()
    if len(estaciones_con_foto_niv) > 0:
        st.markdown("---")
        st.header("Módulo Analítico: Captura de Evidencias en Terreno")
        tabs = st.tabs([f"Estación {est}" for est in estaciones_con_foto_niv])
        secuencia_fotos = [{"paso": 1, "sufijo": "Placa-Punto"}, {"paso": 2, "sufijo": "Norte"}, {"paso": 3, "sufijo": "Este"}, {"paso": 4, "sufijo": "Sur"}, {"paso": 5, "sufijo": "Oeste"}]
        
        for i, est in enumerate(estaciones_con_foto_niv):
            with tabs[i]:
                estado_paso = f"paso_foto_niv_{est}"
                if estado_paso not in st.session_state: st.session_state[estado_paso] = 0
                paso_actual = st.session_state[estado_paso]
                if paso_actual < 5:
                    st.progress(paso_actual / 5.0)
                    foto = st.camera_input(f"Capturar placa en {secuencia_fotos[paso_actual]['sufijo']}", key=f"cam_niv_{est}_{paso_actual}")
                    if foto is not None:
                        dir_fotos = os.path.join("Fotos_Nivelacion", st.session_state.get("proyecto_actual") or "Sin_Proyecto", str(est))
                        os.makedirs(dir_fotos, exist_ok=True)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        with open(os.path.join(dir_fotos, nombre), "wb") as f: f.write(foto.getbuffer())
                        st.session_state[estado_paso] += 1
                        st.rerun()
                else: st.success("Captura de inspección completada satisfactoriamente.")

    if st.button("Ejecutar Computación de Red Altimétrica", type="primary"):
        try:
            puntos = df_niv_activo["Estaca / Punto"].tolist()
            v_atras = df_niv_activo["Vista Atrás (V+)"].tolist()
            v_intermedia = df_niv_activo["Vista Intermedia (V-)"].tolist()
            v_adelante = df_niv_activo["Vista Adelante (V-)"].tolist()
            
            res_df, metricas = calcular_cartera_nivelacion(puntos, v_atras, v_intermedia, v_adelante, cota_datum, cota_llegada)
            
            if st.session_state.modo_app == "Niv_Cerrada":
                st.session_state.df_niv_calc_cerrada = res_df
                st.session_state.met_niv_cerrada = metricas
                st.session_state.calc_niv_cerrada = True
            else:
                st.session_state.df_niv_calc_abierta = res_df
                st.session_state.met_niv_abierta = metricas
                st.session_state.calc_niv_abierta = True
                
        except Exception as e:
            st.error(f"Se identificó un fallo de integridad en el cálculo: {e}")

    calc_niv_done = st.session_state.calc_niv_cerrada if st.session_state.modo_app == "Niv_Cerrada" else st.session_state.calc_niv_abierta
    if calc_niv_done:
        st.success("Operación computacional exitosa. Errores de cierre compensados.")
        met = st.session_state.met_niv_cerrada if st.session_state.modo_app == "Niv_Cerrada" else st.session_state.met_niv_abierta
        df_calc = st.session_state.df_niv_calc_cerrada if st.session_state.modo_app == "Niv_Cerrada" else st.session_state.df_niv_calc_abierta
        
        pdf_bytes_key = 'niv_cerrada_pdf_bytes' if st.session_state.modo_app == "Niv_Cerrada" else 'niv_abierta_pdf_bytes'
        tex_code_key = 'niv_cerrada_tex_code' if st.session_state.modo_app == "Niv_Cerrada" else 'niv_abierta_tex_code'
        debug_msg_key = 'niv_cerrada_debug_msg' if st.session_state.modo_app == "Niv_Cerrada" else 'niv_abierta_debug_msg'

        st.subheader("Evaluación Analítica de Cierre Altimétrico")
        df_rep_niv = pd.DataFrame({
            "Parámetro Evaluado": ["Sumatoria Vista Atrás (V+)", "Sumatoria Vista Adelante (V-)", "Cota Final Inicial (Previo Ajuste)", "Cota Teórica Operacional", "Desviación de Cierre (m)", "Desviación de Cierre (mm)"],
            "Valor Obtenido": [f"{met['sum_vista_atras']:.3f} m", f"{met['sum_vista_adelante']:.3f} m", f"{met['cota_final_cruda']:.3f} m", f"{met['cota_teorica_final']:.3f} m", f"{met['error_cierre_m']:.4f} m", f"{met['error_cierre_mm']:.1f} mm"]
        })
        st.table(df_rep_niv)
        
        st.subheader("Matriz de Cotas Definitivas Compensadas")
        st.dataframe(df_calc.drop(columns=["Registro_Fotografico"], errors="ignore"), use_container_width=True)
        
        st.markdown("---")
        st.subheader("Perfil Topográfico Longitudinal")
        df_plot = df_calc[['Estaca / Punto', 'Cota Ajustada']].copy()
        df_plot['Cota Ajustada'] = df_plot['Cota Ajustada'].astype(float)
        
        fig_perf = go.Figure()
        fig_perf.add_trace(go.Scatter(x=df_plot['Estaca / Punto'], y=df_plot['Cota Ajustada'], mode='lines+markers', line=dict(color='#FF8C00', width=3), marker=dict(size=10)))
        fig_perf.update_layout(xaxis_title='Estaciones Control', yaxis_title='Elevación (msnm)', height=450)
        st.plotly_chart(fig_perf, use_container_width=True)

        @st.cache_data(show_spinner=False)
        def cachear_pdf_altimetria(df_niv_json, met, p_actual, tipo_niv, fotos_paths):
            df_niv_interno = pd.read_json(StringIO(df_niv_json))
            os.makedirs("Reportes_PDF", exist_ok=True)
            ruta_perfil = "Reportes_PDF/Perfil_Nivelacion.png"
            guardar_perfil_altimetria_plt(df_niv_interno, ruta_perfil)
            
            autores = ["Kevin Stiven Cubillos Ramirez", "Sergio Eduardo Barbosa Torres"]
            tutor = "Ing. Edgar Ladino"
            
            tex_niv = generar_reporte_nivelacion_latex(df_niv_interno, met, tipo_niv, autores, tutor, path_grafico=ruta_perfil, fotos_paths=fotos_paths)
            pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(tex_niv, output_dir="Reportes_PDF", filename=f"Nivelacion_{p_actual}")
            return pdf_bytes, tex_niv, debug_msg

        st.markdown("---")
        with st.expander("Consolidación y Exportación Técnica (PDF / Código LaTeX)", expanded=True):
            st.info("El motor LaTeX estructurará el informe técnico formal incluyendo la proyección altimétrica compensada.")
            
            if st.button("Compilar Documento Estructural de Ingeniería", type="primary", use_container_width=True, key="btn_niv"):
                with st.spinner("Procesando componentes espaciales e inviniendo motor LaTeX..."):
                    dir_fotos_proy = os.path.join("Fotos_Nivelacion", st.session_state.get("proyecto_actual") or "Sin_Proyecto")
                    fotos_tomadas = glob.glob(f"{dir_fotos_proy}/*/*.jpg")
                    tipo_niv = "Nivelación Geométrica Cerrada" if st.session_state.modo_app == "Niv_Cerrada" else "Nivelación Geométrica de Abierta Lineal"
                    p_act = st.session_state.get('proyecto_actual') or 'Altimetria'
                    
                    df_niv_json = df_calc.to_json()
                    pdf_bytes, tex_niv, debug_msg = cachear_pdf_altimetria(df_niv_json, met, p_act, tipo_niv, fotos_tomadas)
                    
                    st.session_state[pdf_bytes_key] = pdf_bytes
                    st.session_state[tex_code_key] = tex_niv
                    st.session_state[debug_msg_key] = debug_msg
                    
            if st.session_state.get(pdf_bytes_key):
                st.success("Ensamblaje documental completado exitosamente.")
                b64_pdf = base64.b64encode(st.session_state[pdf_bytes_key]).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
            elif st.session_state.get(tex_code_key):
                st.warning(f"Error de Integración: Ausencia del motor local TeX Live. Diagnóstico: {st.session_state[debug_msg_key]}")

# ===================================================================
# ENTORNO DE CÁLCULO DE POLIGONALES (PLANIMETRÍA)
# ===================================================================
elif st.session_state.modo_app in ["Cerrada", "Abierta"]:
    renderizar_banner_proyecto()
    
    if st.session_state.modo_app == "Cerrada":
        st.title("Red Planimétrica: Red de Circuito Cerrado")
    else:
        st.title("Red Planimétrica: Poligonal Lineal con Puntos de Control")
            
    lista_proyecciones_disp = list(motor_igac.transformadores.keys())
    nombre_proyeccion = st.selectbox("Sistema de Coordenadas Geodésico Principal:", lista_proyecciones_disp, index=st.session_state.get("proy_guardada", 0))
    st.session_state.proy_guardada = lista_proyecciones_disp.index(nombre_proyeccion)

    st.subheader(f"Interfaz de Satélite -> Transformación Cartográfica: {nombre_proyeccion}")
    col_gps1, col_gps2 = st.columns([1, 2])
    with col_gps1: location = streamlit_geolocation()
    
    with col_gps2:
        if location and location['latitude'] is not None:
            lat_gps, lon_gps, alt_gps = location['latitude'], location['longitude'], location['altitude'] or 100.0
            resultados_conversion = motor_igac.convertir_coordenada(lat_gps, lon_gps)
            x_plana = resultados_conversion[nombre_proyeccion]["Este"]
            y_plana = resultados_conversion[nombre_proyeccion]["Norte"]
            
            st.success(f"Posición Satelital Identificada: Lat {lat_gps:.9f}°, Lon {lon_gps:.9f}°")
            
            if st.session_state.modo_app == "Cerrada": opciones_destino = ["Punto Base Principal (Ocupado)", "Punto de Referencia Acimutal (Línea Base)"]
            else: opciones_destino = ["Punto Ocupado Inicial (Arranque)", "Referencia Atrás (Visual Arranque)", "Punto Ocupado Final (Llegada)", "Referencia Adelante (Visual Llegada)"]
                
            destino = st.selectbox("Asignar coordenada calculada al parámetro:", opciones_destino)
            if st.button("Inyectar Posición Local al Sistema", type="primary"):
                if destino == "Punto Base Principal (Ocupado)": 
                    st.session_state.c_e_ini, st.session_state.c_n_ini, st.session_state.c_z_ini = x_plana, y_plana, alt_gps
                elif destino == "Punto de Referencia Acimutal (Línea Base)": 
                    st.session_state.c_e_ref, st.session_state.c_n_ref, st.session_state.c_z_ref = x_plana, y_plana, alt_gps
                elif destino == "Ocupado Inicial (Arranque)": 
                    st.session_state.a_e_ini, st.session_state.a_n_ini, st.session_state.a_z_ini = x_plana, y_plana, alt_gps
                elif destino == "Referencia Atrás (Visual Arranque)": 
                    st.session_state.a_e_ref_arr, st.session_state.a_n_ref_arr, st.session_state.a_z_ref_arr = x_plana, y_plana, alt_gps
                elif destino == "Ocupado Final (Llegada)": 
                    st.session_state.a_e_fin, st.session_state.a_n_fin, st.session_state.a_z_fin = x_plana, y_plana, alt_gps
                elif destino == "Referencia Adelante (Visual Llegada)": 
                    st.session_state.a_e_ref_lleg, st.session_state.a_n_ref_lleg, st.session_state.a_z_ref_lleg = x_plana, y_plana, alt_gps
                st.rerun() 
        else: st.caption("Receptando señal GPS del hardware local...")

    st.markdown("---")
    
    if st.session_state.modo_app == "Cerrada":
        st.header("1. Parámetros Geométricos Iniciales")
        st.session_state.c_tipo_amarre = st.radio("Metodología de amarre inicial:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"], index=0 if st.session_state.c_tipo_amarre=="Dos Coordenadas Conocidas" else 1)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("Base Principal (Ocupado)")
            st.session_state.c_n_ini = st.number_input("Norte (Y)", value=st.session_state.c_n_ini, format="%.3f")
            st.session_state.c_e_ini = st.number_input("Este (X)", value=st.session_state.c_e_ini, format="%.3f")
            st.session_state.c_z_ini = st.number_input("Elevación (Z)", value=st.session_state.c_z_ini, format="%.3f")
        with col2:
            if st.session_state.c_tipo_amarre == "Dos Coordenadas Conocidas":
                st.subheader("Referencia de Amarre")
                st.session_state.c_n_ref = st.number_input("Norte Ref (Y)", value=st.session_state.c_n_ref, format="%.3f")
                st.session_state.c_e_ref = st.number_input("Este Ref (X)", value=st.session_state.c_e_ref, format="%.3f")
                st.session_state.c_z_ref = st.number_input("Cota Ref (Z)", value=st.session_state.c_z_ref, format="%.3f")
                azimut_input = None
            else:
                st.subheader("Azimut Lineal de Base")
                st.session_state.c_az_g = st.number_input("Grados (°)", value=st.session_state.c_az_g, step=1)
                st.session_state.c_az_m = st.number_input("Minutos (')", value=st.session_state.c_az_m, step=1)
                st.session_state.c_az_s = st.number_input("Segundos (\")", value=st.session_state.c_az_s, format="%.2f")
                azimut_input = (st.session_state.c_az_g, st.session_state.c_az_m, st.session_state.c_az_s)
        with col3:
            st.subheader("Lógica Computacional")
            st.session_state.c_tipo_ang = st.selectbox("Sentido de Inflexión de Ángulos", ["exterior", "interior"], index=0 if st.session_state.c_tipo_ang=="exterior" else 1)
            
        st.header("2. Ingreso Estructurado de Cartera Angular")
        
        with st.expander("Importar datos desde archivos espaciales (.csv, .txt)", expanded=False):
            archivos_poli_c = st.file_uploader("Seleccione archivos de levantamiento", type=['csv', 'txt'], accept_multiple_files=True, key="upl_c")
            if archivos_poli_c:
                for archivo in archivos_poli_c:
                    if archivo.name not in st.session_state.poli_archivos_c:
                        try:
                            st.session_state.poli_archivos_c[archivo.name] = procesar_archivo_nube(archivo)
                        except Exception as e:
                            st.error(f"Error procesando {archivo.name}: {e}")
                            
            if st.session_state.poli_archivos_c:
                mapeo_poli_c = {}
                for n_arch, df_bruto in st.session_state.poli_archivos_c.items():
                    st.write(f"**Documento:** {n_arch}")
                    cols = ["Ninguna"] + list(df_bruto.columns)
                    
                    c1, c2, c3, c4, c5 = st.columns(5)
                    m_est = c1.selectbox("Estacionado", cols, key=f"est_{n_arch}")
                    m_obs = c2.selectbox("Punto Observado", cols, key=f"obs_{n_arch}")
                    m_dist = c3.selectbox("Distancia Inclinada", cols, key=f"dist_{n_arch}")
                    m_hi = c4.selectbox("Altura Inst. (hi)", cols, key=f"hi_{n_arch}")
                    m_hr = c5.selectbox("Altura Prisma (hr)", cols, key=f"hr_{n_arch}")
                    
                    c6, c7, c8, c9, c10, c11 = st.columns(6)
                    m_hz_g = c6.selectbox("Hz Grados", cols, key=f"hzg_{n_arch}")
                    m_hz_m = c7.selectbox("Hz Minutos", cols, key=f"hzm_{n_arch}")
                    m_hz_s = c8.selectbox("Hz Segundos", cols, key=f"hzs_{n_arch}")
                    m_z_g = c9.selectbox("Z Grados", cols, key=f"zg_{n_arch}")
                    m_z_m = c10.selectbox("Z Minutos", cols, key=f"zm_{n_arch}")
                    m_z_s = c11.selectbox("Z Segundos", cols, key=f"zs_{n_arch}")
                    
                    mapeo_poli_c[n_arch] = {
                        "est": m_est, "obs": m_obs, "dist": m_dist, "hi": m_hi, "hr": m_hr,
                        "hz_g": m_hz_g, "hz_m": m_hz_m, "hz_s": m_hz_s,
                        "z_g": m_z_g, "z_m": m_z_m, "z_s": m_z_s
                    }
                
                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("Consolidar e Inyectar a Matriz", type="primary", key="inyectar_c"):
                    try:
                        df_final = pd.DataFrame()
                        for n_arch, map_val in mapeo_poli_c.items():
                            df_b = st.session_state.poli_archivos_c[n_arch]
                            df_temp = pd.DataFrame()
                            df_temp['Estacionado'] = df_b[map_val['est']] if map_val['est'] != 'Ninguna' else ""
                            df_temp['Pto_Obs'] = df_b[map_val['obs']] if map_val['obs'] != 'Ninguna' else ""
                            df_temp['Hz_G'] = pd.to_numeric(df_b[map_val['hz_g']], errors='coerce').fillna(0) if map_val['hz_g'] != 'Ninguna' else 0
                            df_temp['Hz_M'] = pd.to_numeric(df_b[map_val['hz_m']], errors='coerce').fillna(0) if map_val['hz_m'] != 'Ninguna' else 0
                            df_temp['Hz_S'] = pd.to_numeric(df_b[map_val['hz_s']], errors='coerce').fillna(0) if map_val['hz_s'] != 'Ninguna' else 0.0
                            df_temp['Z_G'] = pd.to_numeric(df_b[map_val['z_g']], errors='coerce').fillna(0) if map_val['z_g'] != 'Ninguna' else 0
                            df_temp['Z_M'] = pd.to_numeric(df_b[map_val['z_m']], errors='coerce').fillna(0) if map_val['z_m'] != 'Ninguna' else 0
                            df_temp['Z_S'] = pd.to_numeric(df_b[map_val['z_s']], errors='coerce').fillna(0) if map_val['z_s'] != 'Ninguna' else 0.0
                            df_temp['Dist_Inc'] = pd.to_numeric(df_b[map_val['dist']], errors='coerce').fillna(0) if map_val['dist'] != 'Ninguna' else 0.0
                            df_temp['hi'] = pd.to_numeric(df_b[map_val['hi']], errors='coerce').fillna(0) if map_val['hi'] != 'Ninguna' else 0.0
                            df_temp['hr'] = pd.to_numeric(df_b[map_val['hr']], errors='coerce').fillna(0) if map_val['hr'] != 'Ninguna' else 0.0
                            df_temp['Registro_Fotografico'] = False
                            
                            df_final = pd.concat([df_final, df_temp], ignore_index=True)
                        
                        st.session_state.df_cerrada_campo = df_final
                        st.success("Datos importados exitosamente. Revise la matriz de cálculo inferior.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error en la consolidación. Verifique las columnas asignadas: {e}")
                        
                if c_btn2.button("Limpiar Memoria de Archivos", key="limpiar_c"):
                    st.session_state.poli_archivos_c = {}
                    st.rerun()

        st.session_state.df_cerrada_campo = st.data_editor(
            st.session_state.df_cerrada_campo, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={"Registro_Fotografico": st.column_config.CheckboxColumn("Registro Fotográfico")}
        )

    else:
        st.header("1. Parámetros Geométricos Globales")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Eje de Arranque Base")
            st.session_state.a_tipo_amarre_arr = st.radio("Metodología Inicial:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"], index=0 if st.session_state.a_tipo_amarre_arr=="Dos Coordenadas Conocidas" else 1)
            st.markdown("**Posición Instrumental Principal**")
            st.session_state.a_n_ini = st.number_input("Norte Inicial", value=st.session_state.a_n_ini, format="%.3f")
            st.session_state.a_e_ini = st.number_input("Este Inicial", value=st.session_state.a_e_ini, format="%.3f")
            st.session_state.a_z_ini = st.number_input("Cota Inicial", value=st.session_state.a_z_ini, format="%.3f")
            
            if st.session_state.a_tipo_amarre_arr == "Dos Coordenadas Conocidas":
                st.markdown("**Posición de Control Atrás**")
                st.session_state.a_n_ref_arr = st.number_input("Norte Ref. Posterior", value=st.session_state.a_n_ref_arr, format="%.3f")
                st.session_state.a_e_ref_arr = st.number_input("Este Ref. Posterior", value=st.session_state.a_e_ref_arr, format="%.3f")
                st.session_state.a_z_ref_arr = st.number_input("Cota Ref. Posterior", value=st.session_state.a_z_ref_arr, format="%.3f")
                azimut_arr_input = None
            else:
                st.markdown("**Vector Azimutal de Origen**")
                st.session_state.a_azA_g = st.number_input("Grados Origen (°)", value=st.session_state.a_azA_g, step=1)
                st.session_state.a_azA_m = st.number_input("Minutos Origen (')", value=st.session_state.a_azA_m, step=1)
                st.session_state.a_azA_s = st.number_input("Segundos Origen (\")", value=st.session_state.a_azA_s, format="%.2f")
                azimut_arr_input = (st.session_state.a_azA_g, st.session_state.a_azA_m, st.session_state.a_azA_s)

        with col2:
            st.subheader("Eje de Llegada de Cierre")
            st.session_state.a_tipo_amarre_lleg = st.radio("Metodología de Cierre:", ["Dos Coordenadas Conocidas", "Una Coordenada y Azimut"], index=0 if st.session_state.a_tipo_amarre_lleg=="Dos Coordenadas Conocidas" else 1)
            st.markdown("**Posición Instrumental Final**")
            st.session_state.a_n_fin = st.number_input("Norte Terminal", value=st.session_state.a_n_fin, format="%.3f")
            st.session_state.a_e_fin = st.number_input("Este Terminal", value=st.session_state.a_e_fin, format="%.3f")
            st.session_state.a_z_fin = st.number_input("Cota Terminal", value=st.session_state.a_z_fin, format="%.3f")
            
            if st.session_state.a_tipo_amarre_lleg == "Dos Coordenadas Conocidas":
                st.markdown("**Posición de Control Superior**")
                st.session_state.a_n_ref_lleg = st.number_input("Norte Ref. Frontal", value=st.session_state.a_n_ref_lleg, format="%.3f")
                st.session_state.a_e_ref_lleg = st.number_input("Este Ref. Frontal", value=st.session_state.a_e_ref_lleg, format="%.3f")
                st.session_state.a_z_ref_lleg = st.number_input("Cota Ref. Frontal", value=st.session_state.a_z_ref_lleg, format="%.3f")
                azimut_lleg_input = None
            else:
                st.markdown("**Vector Azimutal de Enlace**")
                st.session_state.a_azL_g = st.number_input("Grados Cierre (°)", value=st.session_state.a_azL_g, step=1)
                st.session_state.a_azL_m = st.number_input("Minutos Cierre (')", value=st.session_state.a_azL_m, step=1)
                st.session_state.a_azL_s = st.number_input("Segundos Cierre (\")", value=st.session_state.a_azL_s, format="%.2f")
                azimut_lleg_input = (st.session_state.a_azL_g, st.session_state.a_azL_m, st.session_state.a_azL_s)

        st.header("2. Ingreso Estructurado de Cartera Angular")
        
        with st.expander("Importar datos desde archivos espaciales (.csv, .txt)", expanded=False):
            archivos_poli_a = st.file_uploader("Seleccione archivos de levantamiento", type=['csv', 'txt'], accept_multiple_files=True, key="upl_a")
            if archivos_poli_a:
                for archivo in archivos_poli_a:
                    if archivo.name not in st.session_state.poli_archivos_a:
                        try:
                            st.session_state.poli_archivos_a[archivo.name] = procesar_archivo_nube(archivo)
                        except Exception as e:
                            st.error(f"Error procesando {archivo.name}: {e}")
                            
            if st.session_state.poli_archivos_a:
                mapeo_poli_a = {}
                for n_arch, df_bruto in st.session_state.poli_archivos_a.items():
                    st.write(f"**Documento:** {n_arch}")
                    cols = ["Ninguna"] + list(df_bruto.columns)
                    
                    c1, c2, c3, c4, c5 = st.columns(5)
                    m_est = c1.selectbox("Estacionado", cols, key=f"a_est_{n_arch}")
                    m_obs = c2.selectbox("Punto Observado", cols, key=f"a_obs_{n_arch}")
                    m_dist = c3.selectbox("Distancia Inclinada", cols, key=f"a_dist_{n_arch}")
                    m_hi = c4.selectbox("Altura Inst. (hi)", key=f"a_hi_{n_arch}")
                    m_hr = c5.selectbox("Altura Prisma (hr)", cols, key=f"a_hr_{n_arch}")
                    
                    c6, c7, c8, c9, c10, c11 = st.columns(6)
                    m_hz_g = c6.selectbox("Hz Grados", cols, key=f"a_hzg_{n_arch}")
                    m_hz_m = c7.selectbox("Hz Minutos", cols, key=f"a_hzm_{n_arch}")
                    m_hz_s = c8.selectbox("Hz Segundos", cols, key=f"a_hzs_{n_arch}")
                    m_z_g = c9.selectbox("Z Grados", cols, key=f"a_zg_{n_arch}")
                    m_z_m = c10.selectbox("Z Minutos", cols, key=f"a_zm_{n_arch}")
                    m_z_s = c11.selectbox("Z Segundos", cols, key=f"a_zs_{n_arch}")
                    
                    mapeo_poli_a[n_arch] = {
                        "est": m_est, "obs": m_obs, "dist": m_dist, "hi": m_hi, "hr": m_hr,
                        "hz_g": m_hz_g, "hz_m": m_hz_m, "hz_s": m_hz_s,
                        "z_g": m_z_g, "z_m": m_z_m, "z_s": m_z_s
                    }
                
                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("Consolidar e Inyectar a Matriz", type="primary", key="inyectar_a"):
                    try:
                        df_final = pd.DataFrame()
                        for n_arch, map_val in mapeo_poli_a.items():
                            df_b = st.session_state.poli_archivos_a[n_arch]
                            df_temp = pd.DataFrame()
                            df_temp['Estacionado'] = df_b[map_val['est']] if map_val['est'] != 'Ninguna' else ""
                            df_temp['Pto_Obs'] = df_b[map_val['obs']] if map_val['obs'] != 'Ninguna' else ""
                            df_temp['Hz_G'] = pd.to_numeric(df_b[map_val['hz_g']], errors='coerce').fillna(0) if map_val['hz_g'] != 'Ninguna' else 0
                            df_temp['Hz_M'] = pd.to_numeric(df_b[map_val['hz_m']], errors='coerce').fillna(0) if map_val['hz_m'] != 'Ninguna' else 0
                            df_temp['Hz_S'] = pd.to_numeric(df_b[map_val['hz_s']], errors='coerce').fillna(0) if map_val['hz_s'] != 'Ninguna' else 0.0
                            df_temp['Z_G'] = pd.to_numeric(df_b[map_val['z_g']], errors='coerce').fillna(0) if map_val['z_g'] != 'Ninguna' else 0
                            df_temp['Z_M'] = pd.to_numeric(df_b[map_val['z_m']], errors='coerce').fillna(0) if map_val['z_m'] != 'Ninguna' else 0
                            df_temp['Z_S'] = pd.to_numeric(df_b[map_val['z_s']], errors='coerce').fillna(0) if map_val['z_s'] != 'Ninguna' else 0.0
                            df_temp['Dist_Inc'] = pd.to_numeric(df_b[map_val['dist']], errors='coerce').fillna(0) if map_val['dist'] != 'Ninguna' else 0.0
                            df_temp['hi'] = pd.to_numeric(df_b[map_val['hi']], errors='coerce').fillna(0) if map_val['hi'] != 'Ninguna' else 0.0
                            df_temp['hr'] = pd.to_numeric(df_b[map_val['hr']], errors='coerce').fillna(0) if map_val['hr'] != 'Ninguna' else 0.0
                            df_temp['Registro_Fotografico'] = False
                            
                            df_final = pd.concat([df_final, df_temp], ignore_index=True)
                        
                        st.session_state.df_abierta_campo = df_final
                        st.success("Datos importados exitosamente. Revise la matriz de cálculo inferior.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error en la consolidación. Verifique las columnas asignadas: {e}")
                        
                if c_btn2.button("Limpiar Memoria de Archivos", key="limpiar_a"):
                    st.session_state.poli_archivos_a = {}
                    st.rerun()

        st.session_state.df_abierta_campo = st.data_editor(
            st.session_state.df_abierta_campo, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={"Registro_Fotografico": st.column_config.CheckboxColumn("Registro Fotográfico")}
        )

    df_activo = st.session_state.df_cerrada_campo if st.session_state.modo_app == "Cerrada" else st.session_state.df_abierta_campo
    estaciones_con_foto = df_activo[df_activo["Registro_Fotografico"] == True]["Estacionado"].unique()
    
    if len(estaciones_con_foto) > 0:
        st.markdown("---")
        st.header("Módulo Analítico: Captura de Evidencias en Terreno")
        tabs = st.tabs([f"Estación Operacional {est}" for est in estaciones_con_foto])
        secuencia_fotos = [{"paso": 1, "sufijo": "Punto Central"}, {"paso": 2, "sufijo": "Visual Norte"}, {"paso": 3, "sufijo": "Visual Este"}, {"paso": 4, "sufijo": "Visual Sur"}, {"paso": 5, "sufijo": "Visual Oeste"}]
        
        for i, est in enumerate(estaciones_con_foto):
            with tabs[i]:
                estado_paso = f"paso_foto_{est}"
                if estado_paso not in st.session_state: st.session_state[estado_paso] = 0
                paso_actual = st.session_state[estado_paso]
                if paso_actual < 5:
                    st.progress(paso_actual / 5.0)
                    foto = st.camera_input(f"Capturar evidencia: {secuencia_fotos[paso_actual]['sufijo']}", key=f"cam_{est}_{paso_actual}")
                    if foto is not None:
                        dir_fotos = os.path.join("Fotos_Cartera", st.session_state.get("proyecto_actual") or "Sin_Proyecto", str(est))
                        os.makedirs(dir_fotos, exist_ok=True)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        with open(os.path.join(dir_fotos, nombre), "wb") as f: f.write(foto.getbuffer())
                        st.session_state[estado_paso] += 1
                        st.rerun()
                else: st.success("Capturas de inspección registradas en la base del sistema.")

    if st.button("Ejecutar Cálculo Topográfico", type="primary"):
        df_calculo = st.session_state.df_cerrada_campo if st.session_state.modo_app == "Cerrada" else st.session_state.df_abierta_campo
        try:
            estacionado, punto_obs = df_calculo["Estacionado"].tolist(), df_calculo["Pto_Obs"].tolist()
            ang_h = list(zip(df_calculo["Hz_G"], df_calculo["Hz_M"], df_calculo["Hz_S"]))
            ang_z = list(zip(df_calculo["Z_G"], df_calculo["Z_M"], df_calculo["Z_S"]))
            d_inc, hi, hr = df_calculo["Dist_Inc"].tolist(), df_calculo["hi"].tolist(), df_calculo["hr"].tolist()
            
            if st.session_state.modo_app == "Cerrada":
                res_c, res_a, res_m = poligonal_3d_v2_5(
                    estacionado, punto_obs, ang_h, ang_z, d_inc, hi, hr, 
                    (st.session_state.c_e_ini, st.session_state.c_n_ini, st.session_state.c_z_ini), 
                    (st.session_state.c_e_ref, st.session_state.c_n_ref, st.session_state.c_z_ref) if st.session_state.c_tipo_amarre == "Dos Coordenadas Conocidas" else None, 
                    azimut_input if st.session_state.c_tipo_amarre != "Dos Coordenadas Conocidas" else None, 
                    st.session_state.c_tipo_ang)
                st.session_state.df_ajuste_cerrada = res_a
                st.session_state.metricas_cerrada = res_m
                st.session_state.calc_cerrada = True
            else:
                res_c, res_a, res_m = poligonal_abierta_control(
                    estacionado, punto_obs, ang_h, ang_z, d_inc, hi, hr, 
                    (st.session_state.a_e_ini, st.session_state.a_n_ini, st.session_state.a_z_ini), 
                    (st.session_state.a_e_fin, st.session_state.a_n_fin, st.session_state.a_z_fin), 
                    (st.session_state.a_e_ref_arr, st.session_state.a_n_ref_arr, st.session_state.a_z_ref_arr) if st.session_state.a_tipo_amarre_arr == "Dos Coordenadas Conocidas" else None, 
                    azimut_arr_input, 
                    (st.session_state.a_e_ref_lleg, st.session_state.a_n_ref_lleg, st.session_state.a_z_ref_lleg) if st.session_state.a_tipo_amarre_lleg == "Dos Coordenadas Conocidas" else None, 
                    azimut_lleg_input)
                st.session_state.df_ajuste_abierta = res_a
                st.session_state.metricas_abierta = res_m
                st.session_state.calc_abierta = True
                
        except Exception as e:
            st.error(f"Integridad matemática comprometida: {e}")

    calc_done = st.session_state.calc_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.calc_abierta
    if calc_done:
        st.success("Análisis matemático y estabilización de vértices ejecutado correctamente.")
        met = st.session_state.metricas_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.metricas_abierta
        df_ajuste = st.session_state.df_ajuste_cerrada if st.session_state.modo_app == "Cerrada" else st.session_state.df_ajuste_abierta
        df_campo = st.session_state.df_cerrada_campo if st.session_state.modo_app == "Cerrada" else st.session_state.df_abierta_campo
        
        pdf_bytes_key = 'cerrada_pdf_bytes' if st.session_state.modo_app == "Cerrada" else 'abierta_pdf_bytes'
        tex_code_key = 'cerrada_tex_code' if st.session_state.modo_app == "Cerrada" else 'abierta_tex_code'
        debug_msg_key = 'cerrada_debug_msg' if st.session_state.modo_app == "Cerrada" else 'abierta_debug_msg'

        st.subheader("Reporte General de Tolerancias Topográficas")
        df_comparativo = pd.DataFrame({
            "Parámetro Analizado": ["Error Analítico Angular", "Error Diferencial Este (X)", "Error Diferencial Norte (Y)", "Desfase Vertical Elevacional (Z)", "Desviación Lineal Geodésica", "Grado de Precisión Plana", "Grado de Precisión Altimétrica"],
            "Magnitud Preliminar": [decimal_a_dms(met["err_ang_ant"]), f"{met['err_e_ant']:.5f} m", f"{met['err_n_ant']:.5f} m", f"{met.get('err_v_ant', 0):.5f} m", f"{met['err_h_ant']:.5f} m", f"1 en {int(met['prec_h']) if met['prec_h'] != 0 else 0}", f"1 en {int(met.get('prec_v', 0)) if met.get('prec_v', 0) != 0 else 0}"],
            "Magnitud Optimizada": [decimal_a_dms(met["err_ang_des"]), f"{met['err_e_des']:.5f} m", f"{met['err_n_des']:.5f} m", f"{met.get('err_v_des', 0):.5f} m", f"{met['err_h_des']:.5f} m", "Ajuste Numérico Preciso", "Ajuste Numérico Preciso"]
        })
        st.table(df_comparativo)
        
        colA, colB = st.columns(2)
        with colA: st.dataframe(df_campo.drop(columns=["Registro_Fotografico"], errors="ignore"), use_container_width=True)
        with colB: st.dataframe(df_ajuste, use_container_width=True)

        st.markdown("---")
        st.subheader("Renderización de Plano Topográfico Base")
        tipo_plano = "Planigrafía General: Arquitectura de Red Cerrada" if st.session_state.modo_app == "Cerrada" else "Planigrafía General: Línea Vectorial Abierta"
        
        try:
            fig_plano = generar_plano_profesional(df_ajuste, titulo=tipo_plano)
            st.pyplot(fig_plano)
            ruta_plano_export = "Plano_Exportado.png"
            fig_plano.savefig(ruta_plano_export, dpi=300, bbox_inches='tight')
        except Exception as e:
            st.error(f"Imposible renderizar el diagrama de contorno (CAD-Link): {e}")
            ruta_plano_export = None

        with st.expander("Consolidación y Exportación Técnica (PDF / Código LaTeX)", expanded=True):
            st.markdown("Formatos soportados para programas paramétricos de terceros y reportes de obra:")
            col_kml, col_dxf, col_shp, col_tex = st.columns(4)
            
            trans_to_wgs = motor_igac.transformadores_inversos[nombre_proyeccion]
            data_kml = generar_kml(df_ajuste, trans_to_wgs)
            data_dxf = generar_dxf(df_ajuste)
            data_shp = generar_shp_zip(df_ajuste, nombre_proyeccion)
            
            if st.button("Compilar Documento Estructural de Ingeniería", type="primary", use_container_width=True, key="btn_poli"):
                with st.spinner("Procesando componentes espaciales e inviniendo motor LaTeX..."):
                    dir_fotos_proy = os.path.join("Fotos_Cartera", st.session_state.get("proyecto_actual") or "Sin_Proyecto")
                    fotos_tomadas = glob.glob(f"{dir_fotos_proy}/*/*.jpg")
                    p_act = st.session_state.get('proyecto_actual') or 'Poli'
                    
                    pdf_bytes, data_tex, debug_msg = cachear_pdf_poli(df_campo.to_json(), df_ajuste.to_json(), met, p_act, ruta_plano_export, fotos_tomadas, st.session_state.modo_app)
                    
                    st.session_state[pdf_bytes_key] = pdf_bytes
                    st.session_state[tex_code_key] = data_tex
                    st.session_state[debug_msg_key] = debug_msg

            if st.session_state.get(pdf_bytes_key):
                st.success("Ensamblaje documental completado exitosamente.")
                b64_pdf = base64.b64encode(st.session_state[pdf_bytes_key]).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
            elif st.session_state.get(tex_code_key) and not st.session_state.get(pdf_bytes_key):
                st.warning(f"Error de Integración: Ausencia del motor local TeX Live. Diagnóstico:\n{st.session_state[debug_msg_key]}")
            
            with col_kml: st.download_button(label="Vector .KML (Google Earth)", data=data_kml, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_Plano.kml", mime="application/vnd.google-earth.kml+xml", use_container_width=True)
            with col_dxf: st.download_button(label="Plano .DXF (AutoCAD)", data=data_dxf, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_CAD.dxf", mime="application/dxf", use_container_width=True)
            with col_shp: st.download_button(label="Base Espacial .ZIP (Shapefile)", data=data_shp, file_name=f"{st.session_state.get('proyecto_actual') or 'Poli'}_GIS.zip", mime="application/zip", use_container_width=True)
            with col_tex: 
                if st.session_state.get(pdf_bytes_key):
                    st.download_button(label="Descargar Documento Final PDF", data=st.session_state[pdf_bytes_key], file_name=f"Reporte_{st.session_state.get('proyecto_actual') or 'Poli'}.pdf", mime="application/pdf", use_container_width=True)
                elif st.session_state.get(tex_code_key):
                    st.download_button(label="Descargar Código Base (.TEX)", data=st.session_state[tex_code_key], file_name=f"Reporte_{st.session_state.get('proyecto_actual') or 'Poli'}.tex", mime="text/plain", use_container_width=True)

        st.markdown("---")
        st.subheader(f"Geolocalización Dinámica en Servidor Base ({nombre_proyeccion})")
        
        opciones_mapa = {
            "ESRI Satélite (Alta Resolución)": {"tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "attr": "Esri"},
            "Google Híbrido (Satélite + Vías)": {"tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "attr": "Google"},
            "OpenStreetMap (Catastro)": {"tiles": "OpenStreetMap", "attr": None},
            "Modo Oscuro (Analítico CartoDB)": {"tiles": "CartoDB dark_matter", "attr": None}
        }
        
        tipo_mapa = st.selectbox("Capa Base Geoespacial:", list(opciones_mapa.keys()))
        t_tiles = opciones_mapa[tipo_mapa]["tiles"]
        t_attr = opciones_mapa[tipo_mapa]["attr"]
        
        coordenadas_mapa, latitudes, longitudes = [], [], []
        
        for idx, row in df_ajuste.iterrows():
            lon_wgs, lat_wgs = trans_to_wgs.transform(row['X_Estacion'], row['Y_Estacion'])
            coordenadas_mapa.append((lat_wgs, lon_wgs))
            latitudes.append(lat_wgs)
            longitudes.append(lon_wgs)
            
        centro_lat = sum(latitudes)/len(latitudes)
        centro_lon = sum(longitudes)/len(longitudes)
        
        if t_attr: mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=19, max_zoom=21, tiles=t_tiles, attr=t_attr)
        else: mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=19, max_zoom=21, tiles=t_tiles)
            
        folium.PolyLine(locations=coordenadas_mapa, color="blue", weight=3, opacity=0.8).add_to(mapa)
        
        for idx, row in df_ajuste.iterrows():
            if st.session_state.modo_app == "Cerrada" and idx == len(df_ajuste)-1 and row['Estacionado'] == df_ajuste.iloc[0]['Estacionado']: continue
            folium.Marker(location=coordenadas_mapa[idx], popup=f"<b>Punto de Control: {row['Estacionado']}</b><br>Z: {row['Z_Estacion']:.3f} m", tooltip=row['Estacionado'], icon=folium.Icon(color="red", icon="info-sign")).add_to(mapa)
        
        if latitudes and longitudes:
            mapa.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]])
            
        st_folium(mapa, width=1100, height=550)

# ===================================================================
# NUEVO MÓDULO: DISEÑO GEOMÉTRICO DE VÍAS (ALINEAMIENTO HORIZONTAL Y VERTICAL)
# ===================================================================
elif st.session_state.modo_app == "Diseno_Vias":
    renderizar_banner_proyecto()
    st.title("Diseño Geométrico de Vías (Integración 3D)")
    st.markdown("Establezca los Puntos de Intersección (PI) sobre el modelo geoespacial para definir el alineamiento en planta, defina la rasante y extraiga el perfil longitudinal automáticamente para computar volúmenes.")
    
    lista_proyecciones_disp = list(motor_igac.transformadores.keys())
    nombre_proyeccion = st.selectbox("Configuración del Sistema de Referencia Geodésico:", lista_proyecciones_disp, index=st.session_state.get("proy_guardada", 0))
    st.session_state.proy_guardada = lista_proyecciones_disp.index(nombre_proyeccion)
    trans_to_wgs = motor_igac.transformadores_inversos[nombre_proyeccion]
    trans_to_local = motor_igac.transformadores[nombre_proyeccion]

    st.markdown("---")
    st.subheader("1. Modelo Digital de Terreno (Superficie Base)")
    st.info("Nota Técnica Operativa: Carga múltiple habilitada para bases de datos espaciales. Formato recomendado: PNEZD.")
    
    archivos_vias = st.file_uploader("Importar Documentos Base (Topografía Original)", type=['csv', 'txt'], accept_multiple_files=True, key="upl_dtm_vias")
    
    if archivos_vias:
        for archivo in archivos_vias:
            if archivo.name not in st.session_state.nubes_vias_guardadas:
                try:
                    df_temp = procesar_archivo_nube(archivo)
                    st.session_state.nubes_vias_guardadas[archivo.name] = df_temp
                except Exception as e:
                    st.error(f"Error crítico en la lectura del archivo '{archivo.name}': {e}")
                    
    mapeo_dtm = {}
    if st.session_state.nubes_vias_guardadas:
        st.markdown("**Estado de Memoria (Capas Topográficas):**")
        nombres_archivos = list(st.session_state.nubes_vias_guardadas.keys())
        
        for n_arch in nombres_archivos:
            c_info, c_btn = st.columns([5, 1])
            c_info.write(f"📄 {n_arch} - ({len(st.session_state.nubes_vias_guardadas[n_arch])} registros)")
            if c_btn.button("Remover", key=f"del_vias_{n_arch}"):
                del st.session_state.nubes_vias_guardadas[n_arch]
                st.rerun()

        for n_arch, df_bruto in st.session_state.nubes_vias_guardadas.items():
            with st.expander(f"Asignación paramétrica: {n_arch}", expanded=False):
                st.dataframe(df_bruto.head(5), use_container_width=True)
                cols = ["Ninguna"] + list(df_bruto.columns)
                idx_auto = detectar_indices_columnas(list(df_bruto.columns))
                c1, c2, c3 = st.columns(3)
                col_e = c1.selectbox("Este (Coordenada X)", cols, index=idx_auto["e"], key=f"v_e_{n_arch}")
                col_n = c2.selectbox("Norte (Coordenada Y)", cols, index=idx_auto["n"], key=f"v_n_{n_arch}")
                col_z = c3.selectbox("Elevación (Cota Z)", cols, index=idx_auto["z"], key=f"v_z_{n_arch}")
                mapeo_dtm[n_arch] = {"e": col_e, "n": col_n, "z": col_z}
                
        # El mapeo se conserva en sesión para reutilizarlo en la extracción del perfil
        st.session_state.vias_mapeo_dtm = mapeo_dtm

        if st.button("Generar Curvas de Nivel (TIN)", type="secondary", use_container_width=True):
            dfs_validos = []
            for n_arch, map_val in mapeo_dtm.items():
                if map_val["e"] != "Ninguna" and map_val["n"] != "Ninguna" and map_val["z"] != "Ninguna":
                    df_limpio = asignar_columnas(st.session_state.nubes_vias_guardadas[n_arch], None, map_val["e"], map_val["n"], map_val["z"], None)
                    dfs_validos.append(df_limpio)

            if dfs_validos:
                with st.spinner("Triangulando modelo digital de terreno..."):
                    try:
                        os.makedirs("Reportes_PDF", exist_ok=True)
                        df_master = pd.concat(dfs_validos, ignore_index=True)
                        ruta_dtm_vias = "Reportes_PDF/dtm_vias_overlay.png"
                        bounds_vias = generar_dtm_curvas(df_master, ruta_dtm_vias, trans_to_wgs)
                        
                        # Se guarda la nube maestra YA MAPEADA para que la extracción
                        # del perfil use exactamente las mismas columnas que el TIN.
                        st.session_state.vias_df_master_dtm = df_master
                        st.session_state.vias_dtm_bounds = bounds_vias
                        st.session_state.vias_dtm_ruta = ruta_dtm_vias
                        
                        # FIX ZOOM TERRENO: Forzar zoom y limpiar la memoria antigua
                        st.session_state.force_dtm_zoom = True
                        if "vias_map_center" in st.session_state: del st.session_state["vias_map_center"]
                        if "vias_map_zoom" in st.session_state: del st.session_state["vias_map_zoom"]
                        
                        st.success("Modelo espacial generado. La superficie ha sido enrutada al visor de diseño.")
                    except Exception as e:
                        st.error(f"Falla técnica procesando el terreno: {e}")
            else:
                st.warning("Verifique las columnas asignadas. Se requieren Este, Norte y Elevación.")

    st.markdown("---")
    st.subheader("2. Alineamiento Horizontal en Planta")
    
    col_v, col_espacio = st.columns([1, 3])
    v_dis = col_v.number_input("Velocidad de Diseño (km/h)", value=60, step=10, min_value=20, max_value=120)

    # DISPOSICIÓN VERTICAL: el mapa ocupa todo el ancho y la matriz de vértices
    # queda debajo, para poder leer las columnas sin recorte lateral.
    col_mapa = st.container()
    col_datos = st.container()

    # FIX TypeError: las filas nuevas del data_editor llegan con Este/Norte en None.
    # Todo lo que consuma coordenadas debe trabajar sobre esta lista filtrada.
    def _coord_valida(valor):
        try:
            v = float(valor)
            return not np.isnan(v)
        except (TypeError, ValueError):
            return False

    pis_validos = [p for p in st.session_state.pis_vias
                   if _coord_valida(p.get('Este')) and _coord_valida(p.get('Norte'))]
    pis_incompletos = len(st.session_state.pis_vias) - len(pis_validos)

    def _normalizar_registros(registros):
        """
        Convierte NaN y tipos de numpy a equivalentes nativos comparables.
        Sin esto, comparar registros con NaN daría siempre 'distinto'
        (NaN != NaN) y el st.rerun() entraría en bucle infinito.
        """
        limpios = []
        for reg in registros:
            fila = {}
            for k, v in reg.items():
                if v is None:
                    fila[k] = None
                elif isinstance(v, (float, np.floating)):
                    fila[k] = None if np.isnan(v) else round(float(v), 6)
                elif isinstance(v, (int, np.integer)):
                    fila[k] = float(v)
                else:
                    fila[k] = v
            limpios.append(fila)
        return limpios

    with col_mapa:
        opciones_mapa = {
            "ESRI Satélite (Alta Resolución)": {"tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "attr": "Esri"},
            "Google Híbrido (Satélite + Vías)": {"tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "attr": "Google"},
            "OpenStreetMap (Catastro y Vías)": {"tiles": "OpenStreetMap", "attr": None},
            "OpenTopoMap (Topográfico)": {"tiles": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", "attr": "OpenTopoMap"},
            "CartoDB Positron (Claro)": {"tiles": "CartoDB positron", "attr": None},
            "CartoDB Dark Matter (Oscuro)": {"tiles": "CartoDB dark_matter", "attr": None}
        }
        tipo_mapa = st.selectbox("Capa Base Geoespacial:", list(opciones_mapa.keys()), key="map_vias_base")
        t_tiles = opciones_mapa[tipo_mapa]["tiles"]
        t_attr = opciones_mapa[tipo_mapa]["attr"]
        
        if st.session_state.get('vias_dtm_bounds'):
            c_lupa, c_ver, c_opac = st.columns([1.2, 1, 1.5])
            if c_lupa.button("🔎 Centrar vista en el Modelo (TIN)", use_container_width=True):
                st.session_state.force_dtm_zoom = True
                st.rerun()
            # Ocultar el raster acelera muchísimo el mapa mientras se marcan los PI:
            # el PNG del TIN se incrusta en base64 dentro del HTML en cada recarga.
            ver_tin = c_ver.checkbox("Ver TIN", value=True, key="chk_ver_tin")
            opacidad_tin = c_opac.slider("Opacidad TIN", 0.0, 1.0, 0.65, 0.05, key="sld_opac_tin")
        else:
            ver_tin, opacidad_tin = True, 0.65

        # CÁMARA PERSISTENTE
        # La vista deja de perseguir al último PI. Se conserva exactamente donde
        # el usuario la dejó (vias_map_center / vias_map_zoom) y sólo se reencuadra
        # cuando se genera el TIN o se pulsa el botón de la lupa.
        if st.session_state.get('vias_map_center') and not st.session_state.get('force_dtm_zoom'):
            centro_mapa = st.session_state.vias_map_center
            zoom_mapa = st.session_state.get('vias_map_zoom', 17)
        elif st.session_state.get('vias_dtm_bounds'):
            b = st.session_state.vias_dtm_bounds
            centro_mapa = [(b[0][0] + b[1][0]) / 2.0, (b[0][1] + b[1][1]) / 2.0]
            zoom_mapa = 16
        elif pis_validos:
            # Encuadre inicial sobre el primer vértice válido (sólo la primera vez)
            primer_pi = pis_validos[0]
            lon_wgs, lat_wgs = trans_to_wgs.transform(float(primer_pi['Este']), float(primer_pi['Norte']))
            centro_mapa = [lat_wgs, lon_wgs]
            zoom_mapa = 17
        else:
            centro_mapa = [4.6377, -74.1234]
            zoom_mapa = 15

        mapa_diseno = folium.Map(location=centro_mapa, zoom_start=zoom_mapa, max_zoom=22, tiles=t_tiles, attr=t_attr)
        
        # Plugins de Folium
        from folium.plugins import MeasureControl, Draw, Fullscreen
        mapa_diseno.add_child(MeasureControl(position='topleft', primary_length_unit='meters', secondary_length_unit='miles', primary_area_unit='sqmeters'))
        
        # Configuramos Draw para que solo permita poner Marcadores (Los PIs)
        opciones_dibujo = {'polyline': False, 'polygon': False, 'rectangle': False, 'circle': False, 'marker': True, 'circlemarker': False}
        mapa_diseno.add_child(Draw(export=False, position='topleft', draw_options=opciones_dibujo))
        
        mapa_diseno.add_child(Fullscreen(position='topright'))

        # Grupos de capas
        fg_dtm = folium.FeatureGroup(name="Superficie Terreno (TIN)", show=True)
        fg_pis = folium.FeatureGroup(name="Vértices Geométricos (PIs)", show=True)
        fg_eje = folium.FeatureGroup(name="Eje Vial Proyectado", show=True)

        # Cargar DTM (TIN)
        if st.session_state.get('vias_dtm_bounds') and st.session_state.get('vias_dtm_ruta'):
            if ver_tin and os.path.exists(st.session_state.vias_dtm_ruta):
                folium.raster_layers.ImageOverlay(
                    image=st.session_state.vias_dtm_ruta,
                    bounds=st.session_state.vias_dtm_bounds,
                    opacity=opacidad_tin,
                    name="Raster TIN",
                    interactive=False
                ).add_to(fg_dtm)
            
            # Zoom estricto SÓLO cuando se acaba de crear el TIN o se presiona el botón de la Lupa
            if st.session_state.get('force_dtm_zoom'):
                mapa_diseno.fit_bounds(st.session_state.vias_dtm_bounds)
                st.session_state.force_dtm_zoom = False
        
        # Cargar Ejes y PIs
        if pis_validos:
            lats_pis, lons_pis = [], []
            for i, pi in enumerate(pis_validos):
                lon, lat = trans_to_wgs.transform(float(pi['Este']), float(pi['Norte']))
                lats_pis.append(lat)
                lons_pis.append(lon)
                radio_pi = pi.get('Radio')
                radio_txt = f"{float(radio_pi):.3f}" if _coord_valida(radio_pi) else "sin definir"
                cota_pi = pi.get('Elevacion')
                cota_txt = f"{float(cota_pi):.3f}" if _coord_valida(cota_pi) else "0.000"
                lbl = f"Vértice: {pi['PI']}<br>R: {radio_txt} m<br>Z: {cota_txt} m"
                folium.Marker([lat, lon], popup=lbl, tooltip=pi['PI'], icon=folium.Icon(color="orange", icon="info-sign")).add_to(fg_pis)
            
            folium.PolyLine(list(zip(lats_pis, lons_pis)), color="orange", weight=2, dash_array="5, 10").add_to(fg_pis)
            
            if st.session_state.get('df_dibujo_eje') is not None:
                eje_latlons = []
                for _, row in st.session_state.df_dibujo_eje.iterrows():
                    # FIX SCALAR ERROR: Forzamos la conversión a float()
                    lon, lat = trans_to_wgs.transform(float(row['Este']), float(row['Norte']))
                    eje_latlons.append([lat, lon])
                folium.PolyLine(eje_latlons, color="blue", weight=4, opacity=0.8, tooltip="Eje Vial Proyectado").add_to(fg_eje)
                
            if st.session_state.get('df_reporte_curvas') is not None:
                for _, row in st.session_state.df_reporte_curvas.iterrows():
                    if pd.notna(row.get('E_PC (m)')):
                        lon_pc, lat_pc = trans_to_wgs.transform(row['E_PC (m)'], row['N_PC (m)'])
                        folium.CircleMarker([lat_pc, lon_pc], radius=4, color="green", fill=True, tooltip="PC (Principio Curva)").add_to(fg_eje)
                        lon_pt, lat_pt = trans_to_wgs.transform(row['E_PT (m)'], row['N_PT (m)'])
                        folium.CircleMarker([lat_pt, lon_pt], radius=4, color="red", fill=True, tooltip="PT (Principio Tangencia)").add_to(fg_eje)

        fg_dtm.add_to(mapa_diseno)
        fg_pis.add_to(mapa_diseno)
        fg_eje.add_to(mapa_diseno)
        folium.LayerControl(collapsed=True, position='topright').add_to(mapa_diseno)

        map_data = st_folium(mapa_diseno, width=1100, height=600, key="st_folium_vias",
                             returned_objects=["last_active_drawing"])

        # NOTA: deliberadamente NO se piden "center" ni "zoom". Al solicitarlos,
        # streamlit-folium relanza el script en CADA arrastre o zoom del mapa,
        # lo que con el TIN cargado hacía imposible encuadrar la vista.
        # La posición se conserva anclándola al último punto insertado (abajo),
        # que por definición ya está dentro del encuadre actual del usuario.

        if map_data and map_data.get("last_active_drawing"):
            drawing = map_data["last_active_drawing"]
            if drawing["geometry"]["type"] == "Point":
                coords = drawing["geometry"]["coordinates"]
                lon, lat = coords[0], coords[1]
                click_id = f"draw-{lat}-{lon}"
                
                if st.session_state.get("last_click_id") != click_id:
                    st.session_state.last_click_id = click_id
                    este, norte = trans_to_local.transform(lon, lat)
                    # La cámara se ancla en el punto recién marcado: como ese punto
                    # está dentro del encuadre actual, el mapa no da ningún salto.
                    st.session_state.vias_map_center = [lat, lon]
                    nuevo_pi = {
                        "PI": f"PI-{len(st.session_state.pis_vias)+1}",
                        "Este": round(este, 3),
                        "Norte": round(norte, 3),
                        "Elevacion": 0.000,
                        "Radio": 50.0 
                    }
                    st.session_state.pis_vias.append(nuevo_pi)
                    st.rerun()

    with col_datos:
        st.markdown("---")
        st.markdown("#### Matriz de Vértices Geométricos (PI)")
        st.caption("Para desplazar un vértice analíticamente o ajustar su elevación, edite la matriz a continuación.")
        c_purga, c_vacio = st.columns([1, 3])
        if c_purga.button("Purgar Vértices Geométricos", type="secondary", use_container_width=True):
            st.session_state.pis_vias = []
            st.session_state.df_dibujo_eje = None
            st.session_state.df_reporte_curvas = None
            st.session_state.vias_df_vertical = None
            st.session_state.vias_df_perfil = None
            st.session_state.vias_df_malla = None
            st.session_state.vias_df_vol_calc = None
            st.session_state.vias_met_vol = None
            st.session_state.vias_calc_vol = False
            st.session_state.last_click_id = None
            st.rerun()
            
        if st.session_state.pis_vias:
            df_pis = pd.DataFrame(st.session_state.pis_vias)
            
            # FIX: Cálculo a prueba de celdas vacías (NaN) en la tabla
            distancias, pendientes = [], []
            for i in range(len(df_pis)):
                if i < len(df_pis) - 1:
                    try:
                        e1, n1 = float(df_pis.iloc[i].get('Este', 0)), float(df_pis.iloc[i].get('Norte', 0))
                        e2, n2 = float(df_pis.iloc[i+1].get('Este', 0)), float(df_pis.iloc[i+1].get('Norte', 0))
                        z1 = float(df_pis.iloc[i].get('Elevacion', 0.0))
                        z2 = float(df_pis.iloc[i+1].get('Elevacion', 0.0))
                        
                        if pd.isna(e1) or pd.isna(e2):
                            dist, pend = 0.0, 0.0
                        else:
                            dist = np.sqrt((e2 - e1)**2 + (n2 - n1)**2)
                            pend = ((z2 - z1) / dist * 100) if dist > 0 else 0.0
                        distancias.append(dist)
                        pendientes.append(pend)
                    except:
                        distancias.append(0.0); pendientes.append(0.0)
                else:
                    distancias.append(0.0); pendientes.append(0.0)
            
            df_pis['Dist. Sig (m)'] = distancias
            df_pis['Pend. Sig (%)'] = pendientes
            
            df_pis_editado = st.data_editor(
                df_pis, 
                num_rows="dynamic", 
                use_container_width=True,
                disabled=["PI", "Dist. Sig (m)", "Pend. Sig (%)"], 
                key="editor_pis_vias",
                column_config={
                    "Este": st.column_config.NumberColumn(format="%.3f"),
                    "Norte": st.column_config.NumberColumn(format="%.3f"),
                    "Elevacion": st.column_config.NumberColumn("Cota (Z)", format="%.3f"),
                    "Radio": st.column_config.NumberColumn(format="%.3f"),
                    "Dist. Sig (m)": st.column_config.NumberColumn(format="%.3f"),
                    "Pend. Sig (%)": st.column_config.NumberColumn(format="%.3f")
                }
            )
            
            df_to_save = df_pis_editado.drop(columns=['Dist. Sig (m)', 'Pend. Sig (%)'], errors='ignore')
            # Renumeración: al agregar filas en el editor el campo PI queda vacío
            # (está deshabilitado) y el procesamiento fallaba con PI = None.
            df_to_save = df_to_save.reset_index(drop=True)
            df_to_save['PI'] = [f"PI-{i+1}" for i in range(len(df_to_save))]

            # FIX "hay que escribir la cota dos veces":
            # El mapa y sus marcadores se dibujan ANTES que esta tabla, así que al
            # guardar el valor sin más, la vista seguía mostrando el dato anterior y
            # parecía que la edición no se había registrado. Ahora se detecta el
            # cambio real y se relanza el script: un solo ingreso actualiza todo.
            registros_nuevos = _normalizar_registros(df_to_save.to_dict('records'))
            if registros_nuevos != _normalizar_registros(st.session_state.pis_vias):
                st.session_state.pis_vias = registros_nuevos
                st.rerun()

            if pis_incompletos:
                st.warning(f"{pis_incompletos} vértice(s) sin coordenadas completas: no se dibujan ni se procesan hasta que llene Este y Norte.")

            st.caption("Los anchos de carril, bombeos y espesores estructurales se definen en el paso 3.")

            if st.button("Procesar Geometría Vial", type="primary", use_container_width=True):
                try:
                    df_rep, df_dibujo, df_vert = procesar_alineamiento_horizontal(pd.DataFrame(st.session_state.pis_vias), v_diseno=v_dis)
                    st.session_state.df_reporte_curvas = df_rep
                    st.session_state.df_dibujo_eje = df_dibujo
                    st.session_state.vias_df_vertical = df_vert
                    # El eje cambió: los volúmenes previos dejan de ser válidos
                    st.session_state.vias_calc_vol = False
                    st.session_state.vias_df_perfil = None
                    st.session_state.vias_df_malla = None
                    st.session_state.vias_df_vol_calc = None
                    st.session_state.vias_met_vol = None
                    st.success("Trazado en planta y PIVs generados correctamente. Recalcule el perfil en el paso 3.")
                    st.rerun()
                except ValueError as e:
                    st.error(f"Inconsistencia Geométrica Detectada: {e}")
                except Exception as e:
                    st.error(f"Falla de configuración paramétrica: {e}")

    # =================================================================
    # SECCIÓN 3: DISEÑO VERTICAL Y PERFIL LONGITUDINAL
    # =================================================================
    if st.session_state.get('vias_df_vertical') is not None:
        st.markdown("---")
        st.subheader("3. Diseño Vertical y Perfil Longitudinal")
        
        # Validaciones de Norma INVIAS
        st.markdown("#### Validaciones Normativas de Gradiente Longitudinal (INVIAS)")
        max_slope = 8.0 
        min_slope = 0.5 
        df_v_val = st.session_state.vias_df_vertical
        # La última fila es el cierre artificial (pendiente 0), no es un tramo real
        for i in range(len(df_v_val) - 1):
            m = float(df_v_val.iloc[i]['Pendiente Salida (%)'])
            tramo = f"Tramo {i+1} ({df_v_val.iloc[i]['Vértice PIV']} → {df_v_val.iloc[i+1]['Vértice PIV']})"
            if abs(m) > max_slope:
                st.error(f"{tramo}: Pendiente de {m:.3f}% excede el máximo permitido ({max_slope}%).")
            elif abs(m) < min_slope:
                st.warning(f"{tramo}: Pendiente de {m:.3f}% no cumple el mínimo para drenaje longitudinal ({min_slope}%).")
            else:
                st.success(f"{tramo}: Pendiente de {m:.3f}% conforme a INVIAS.")

        st.markdown("**Tabla Dinámica de Rasante Vertical (PIVs)**")
        df_mostrar_v = st.session_state.vias_df_vertical.drop(columns=['Abscisa'], errors='ignore')
        st.dataframe(df_mostrar_v.style.format({
            "Elevación (Z)": "{:.3f}",
            "Pendiente Salida (%)": "{:.3f}",
            "Longitud Tramo (m)": "{:.3f}"
        }), use_container_width=True)

        st.markdown("#### Parámetros de Extracción y Sección Estructural")
        col_v3, col_v4, col_v5, col_v6, col_v7 = st.columns(5)
        intervalo_abs = col_v3.number_input("Intervalo de Abscisado (m)", value=10.0, min_value=1.0, format="%.1f")
        ancho_izq = col_v4.number_input("Carril Izquierdo (m)", value=3.6, format="%.3f")
        ancho_der = col_v5.number_input("Carril Derecho (m)", value=3.6, format="%.3f")
        bom_izq = col_v6.number_input("Bombeo Izquierdo (%)", value=-2.0, format="%.3f")
        bom_der = col_v7.number_input("Bombeo Derecho (%)", value=-2.0, format="%.3f")
        
        col_est1, col_est2, col_est3, col_est4 = st.columns(4)
        esp_pav_via = col_est1.number_input("Espesor Pavimento (m)", value=0.10, step=0.05, format="%.2f", key="p_via")
        esp_base_via = col_est2.number_input("Espesor Base (m)", value=0.20, step=0.05, format="%.2f", key="b_via")
        esp_sub_via = col_est3.number_input("Espesor Subbase (m)", value=0.30, step=0.05, format="%.2f", key="s_via")
        long_trans = col_est4.number_input("Long. Transición Peralte (m)", value=30.0, step=5.0, min_value=1.0, format="%.1f", key="lt_via",
                                           help="Desarrollo del peralte: tramo antes del PC y después del PT donde la sección pasa del bombeo al peralte pleno.")
        st.session_state.vias_long_trans = long_trans
        
        st.session_state.esp_pav_via = esp_pav_via
        st.session_state.esp_base_via = esp_base_via
        st.session_state.esp_sub_via = esp_sub_via
        st.session_state.ancho_izq = ancho_izq
        st.session_state.ancho_der = ancho_der
        st.session_state.bom_izq_via = bom_izq
        st.session_state.bom_der_via = bom_der

        if st.button("Extraer Terreno y Construir Perfil 3D", type="primary", use_container_width=True):
            if not st.session_state.nubes_vias_guardadas:
                st.error("Error: Debe importar un archivo topográfico (Nube de puntos con cotas) en el Paso 1 para extraer el terreno.")
            else:
                with st.spinner("Escaneando Malla DTM y Densificando Eje..."):
                    # Se reutiliza la nube maestra generada con el TIN. Si aún no
                    # existe, se reconstruye con el MAPEO DEL USUARIO (antes se
                    # tomaban las columnas 1,2,3 por posición, lo que cruzaba
                    # Este/Norte en archivos PNEZD).
                    df_master_dtm = st.session_state.get('vias_df_master_dtm')

                    if df_master_dtm is None or df_master_dtm.empty:
                        mapeo_guardado = st.session_state.get('vias_mapeo_dtm', {})
                        dfs_tmp = []
                        for n_arch, df_bruto in st.session_state.nubes_vias_guardadas.items():
                            m = mapeo_guardado.get(n_arch)
                            if not m or "Ninguna" in (m["e"], m["n"], m["z"]):
                                continue
                            dfs_tmp.append(asignar_columnas(df_bruto, None, m["e"], m["n"], m["z"], None))
                        if dfs_tmp:
                            df_master_dtm = pd.concat(dfs_tmp, ignore_index=True)
                            st.session_state.vias_df_master_dtm = df_master_dtm

                    if df_master_dtm is None or df_master_dtm.empty:
                        st.error("No hay una nube válida en memoria. Asigne las columnas Este/Norte/Cota y genere el TIN en el Paso 1.")
                        st.stop()

                    x_eje = st.session_state.df_dibujo_eje['Este'].values
                    y_eje = st.session_state.df_dibujo_eje['Norte'].values
                    dist_acum = np.zeros(len(x_eje))
                    dist_acum[1:] = np.sqrt(np.diff(x_eje)**2 + np.diff(y_eje)**2)
                    dist_acum = np.cumsum(dist_acum)
                    
                    max_dist = dist_acum[-1]
                    abscisas = np.arange(0, max_dist, intervalo_abs)
                    if len(abscisas) == 0 or abscisas[-1] != max_dist:
                        abscisas = np.append(abscisas, max_dist)
                        
                    x_interp = np.interp(abscisas, dist_acum, x_eje)
                    y_interp = np.interp(abscisas, dist_acum, y_eje)
                    
                    azimuths = np.zeros(len(x_interp))
                    for i in range(len(x_interp)-1):
                        azimuths[i] = np.arctan2(x_interp[i+1] - x_interp[i], y_interp[i+1] - y_interp[i])
                    azimuths[-1] = azimuths[-2] if len(azimuths) > 1 else 0

                    # FIX LADOS: con az = arctan2(dE, dN), el vector de avance es
                    # (sin az, cos az). La normal IZQUIERDA es (-cos az, sin az) y
                    # la DERECHA es (cos az, -sin az). Antes estaban intercambiadas,
                    # lo que aplicaba anchos y bombeos asimétricos al lado contrario.
                    x_izq = x_interp - ancho_izq * np.cos(azimuths)
                    y_izq = y_interp + ancho_izq * np.sin(azimuths)
                    x_der = x_interp + ancho_der * np.cos(azimuths)
                    y_der = y_interp - ancho_der * np.sin(azimuths)
                    
                    z_ter_centro, fuera_c = extraer_elevaciones_dtm(x_interp, y_interp, df_master_dtm, retornar_mascara=True)
                    z_ter_izq, fuera_i = extraer_elevaciones_dtm(x_izq, y_izq, df_master_dtm, retornar_mascara=True)
                    z_ter_der, fuera_d = extraer_elevaciones_dtm(x_der, y_der, df_master_dtm, retornar_mascara=True)

                    n_fuera = int(np.count_nonzero(fuera_c | fuera_i | fuera_d))
                    st.session_state.vias_pts_fuera_dtm = n_fuera
                    
                    df_vert = st.session_state.vias_df_vertical.sort_values('Abscisa')
                    z_diseno = np.interp(abscisas, df_vert['Abscisa'].values, df_vert['Elevación (Z)'].values)
                    
                    df_perfil = pd.DataFrame({'Abscisa': abscisas, 'Cota Terreno': z_ter_centro, 'Cota Diseño': z_diseno})

                    # PERALTE EN LAS SECCIONES: antes se aplicaba el bombeo constante
                    # en todo el trazado, así que el peralte calculado en el cuadro de
                    # curvas nunca llegaba a la geometría transversal.
                    m_izq_arr, m_der_arr = peraltes_por_abscisa(
                        abscisas, st.session_state.get('df_reporte_curvas'),
                        bombeo_izq=bom_izq, bombeo_der=bom_der,
                        long_transicion=long_trans
                    )
                    df_perfil['Pend. Transv. Izq (%)'] = m_izq_arr
                    df_perfil['Pend. Transv. Der (%)'] = m_der_arr
                    st.session_state.vias_df_perfil = df_perfil
                    
                    malla_transversal = []
                    for i, row in df_perfil.iterrows():
                        abs_k = row['Abscisa']
                        z_ter_c = z_ter_centro[i]
                        z_ter_i = z_ter_izq[i]
                        z_ter_d = z_ter_der[i]
                        z_dis = row['Cota Diseño']
                        
                        malla_transversal.append({'Abscisa (K)': abs_k, 'Distancia Eje (m)': -abs(ancho_izq), 'Cota Terreno (m)': z_ter_i, 'Cota Diseño (m)': z_dis + (abs(ancho_izq) * m_izq_arr[i] / 100.0)})
                        malla_transversal.append({'Abscisa (K)': abs_k, 'Distancia Eje (m)': 0.0, 'Cota Terreno (m)': z_ter_c, 'Cota Diseño (m)': z_dis})
                        malla_transversal.append({'Abscisa (K)': abs_k, 'Distancia Eje (m)': abs(ancho_der), 'Cota Terreno (m)': z_ter_d, 'Cota Diseño (m)': z_dis + (abs(ancho_der) * m_der_arr[i] / 100.0)})
                        
                    df_malla_generada = pd.DataFrame(malla_transversal)
                    res_df, metricas = calcular_cubicaje_total(df_malla_generada)
                    
                    if 'Volumen Neto (m³)' in res_df.columns:
                        res_df['Masa Acumulada (m³)'] = res_df['Volumen Neto (m³)'].cumsum()
                    else:
                        res_df['Masa Acumulada (m³)'] = (res_df['Vol. Corte (m³)'].fillna(0) - res_df['Vol. Relleno (m³)'].fillna(0)).cumsum()
                    
                    st.session_state.vias_df_malla = df_malla_generada
                    st.session_state.vias_df_vol_calc = res_df
                    st.session_state.vias_met_vol = metricas
                    st.session_state.vias_calc_vol = True
                    st.success("Extracción completada.")

                    if n_fuera > 0:
                        st.warning(
                            f"Cobertura parcial del modelo: {n_fuera} punto(s) del corredor quedaron fuera "
                            f"del TIN y se completaron por vecino más cercano. Los volúmenes en esos sectores "
                            f"son estimativos; amplíe la nube de puntos para un cubicaje definitivo."
                        )

        if st.session_state.get('vias_calc_vol'):
            # Gráfico de Perfil con Hatching y PIVs
            fig_perfil = go.Figure()
            df_p = st.session_state.vias_df_perfil
            df_v = st.session_state.vias_df_vertical
            
            x_prof = df_p['Abscisa'].tolist()
            z_ter_prof = df_p['Cota Terreno'].tolist()
            z_dis_prof = df_p['Cota Diseño'].tolist()

            x_f_prof, z_dis_f_prof, z_ter_f_prof = calcular_intersecciones_seccion(x_prof, z_dis_prof, z_ter_prof)
            z_min_prof = np.minimum(z_dis_f_prof, z_ter_f_prof)
            z_max_prof = np.maximum(z_dis_f_prof, z_ter_f_prof)

            fig_perfil.add_trace(go.Scatter(
                x=np.concatenate([x_f_prof, x_f_prof[::-1]]),
                y=np.concatenate([z_max_prof, z_dis_f_prof[::-1]]),
                fill='toself', fillcolor='rgba(220, 53, 69, 0.3)', line=dict(width=0), name='Vol. Corte', hoverinfo='skip'
            ))
            fig_perfil.add_trace(go.Scatter(
                x=np.concatenate([x_f_prof, x_f_prof[::-1]]),
                y=np.concatenate([z_dis_f_prof, z_min_prof[::-1]]),
                fill='toself', fillcolor='rgba(40, 167, 69, 0.3)', line=dict(width=0), name='Vol. Relleno', hoverinfo='skip'
            ))

            fig_perfil.add_trace(go.Scatter(x=df_p['Abscisa'], y=df_p['Cota Terreno'], mode='lines', name='Terreno Natural (Eje)', line=dict(color='#8D6E63', width=2)))
            fig_perfil.add_trace(go.Scatter(x=df_p['Abscisa'], y=df_p['Cota Diseño'], mode='lines', name='Rasante (Alineamiento Vertical)', line=dict(color='#E53935', width=3)))
            fig_perfil.add_trace(go.Scatter(x=df_v['Abscisa'], y=df_v['Elevación (Z)'], mode='markers+text', name='PIV (Vértice Vertical)', marker=dict(size=10, color='black', symbol='triangle-up'), text=df_v['Vértice PIV'], textposition="top center"))
            
            for i in range(len(df_v)-1):
                x_mid = (df_v.iloc[i]['Abscisa'] + df_v.iloc[i+1]['Abscisa']) / 2
                y_mid = (df_v.iloc[i]['Elevación (Z)'] + df_v.iloc[i+1]['Elevación (Z)']) / 2
                m = df_v.iloc[i]['Pendiente Salida (%)']
                L = df_v.iloc[i]['Longitud Tramo (m)']
                if L > 0:
                    fig_perfil.add_annotation(x=x_mid, y=y_mid, text=f"L={L:.3f}m<br>m={m:.3f}%", showarrow=True, arrowhead=2, arrowcolor='black', ax=0, ay=-40)

            fig_perfil.update_layout(title="Perfil Topográfico Longitudinal Extraído (Sombreado)", xaxis_title="Abscisa de Ruta (m)", yaxis_title="Elevación Geoidal (msnm)", height=500)
            st.plotly_chart(fig_perfil, use_container_width=True)

    # =================================================================
    # SECCIÓN 4: MEMORIAS DE CÁLCULO
    # =================================================================
    if st.session_state.get('df_reporte_curvas') is not None:
        st.markdown("---")
        st.subheader("4. Memoria de Cálculo Geométrico (Alineamiento Horizontal)")
        st.dataframe(st.session_state.df_reporte_curvas, use_container_width=True)

    # =================================================================
    # SECCIÓN 5: PLANO CAD
    # =================================================================
    if st.session_state.get('df_dibujo_eje') is not None:
        st.markdown("---")
        st.subheader("5. Planimetría de Diseño (Arquitectura CAD)")
        try:
            ancho_t = st.session_state.get('ancho_izq', 3.6) + st.session_state.get('ancho_der', 3.6)
            fig_vias = generar_plano_vias(st.session_state.df_dibujo_eje, st.session_state.df_reporte_curvas, pd.DataFrame(st.session_state.pis_vias), st.session_state.get('vias_df_vertical'), ancho_calzada=ancho_t)
            st.pyplot(fig_vias)
            
            ruta_export_vias = "Plano_Vias.png"
            fig_vias.savefig(ruta_export_vias, dpi=300, bbox_inches='tight')
            with open(ruta_export_vias, "rb") as f:
                btn_dl = st.download_button(
                    label="Descargar Plano CAD de Planta (.PNG Alta Resolución)",
                    data=f,
                    file_name=f"Diseno_Planta_{st.session_state.get('proyecto_actual', 'Vias')}.png",
                    mime="image/png",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Falla en el motor de renderizado CAD: {e}")

    # =================================================================
    # SECCIÓN 6: VOLÚMENES Y SECCIONES
    # =================================================================
    if st.session_state.get('vias_calc_vol'):
        st.markdown("---")
        st.subheader("6. Secciones Transversales y Volúmenes")
        
        met = st.session_state.vias_met_vol
        df_vol_final = st.session_state.vias_df_vol_calc
        
        colA, colB, colC = st.columns(3)
        colA.metric("Corte de Excavación", f"{met['Corte_Total']:.3f} m³")
        colB.metric("Relleno de Terraplén", f"{met['Relleno_Total']:.3f} m³")
        colC.metric("Balance Volumétrico", f"{met['Volumen_Neto']:.3f} m³")
        
        fig_masa = go.Figure()
        fig_masa.add_trace(go.Scatter(x=df_vol_final['Abscisa (K)'], y=df_vol_final['Masa Acumulada (m³)'], mode='lines+markers', fill='tozeroy', line=dict(color='#0D47A1', width=3)))
        fig_masa.update_layout(title="Diagrama de Transporte de Masas", xaxis_title="Abscisado (K)", yaxis_title="Volumen Neto Acumulado (m³)", height=350)
        st.plotly_chart(fig_masa, use_container_width=True)
        
        st.markdown("---")
        st.markdown("**Inspección de Secciones (Bottom-Up y Mosaico)**")
        abs_plot = st.selectbox("Inspección Geométrica Individual:", st.session_state.vias_df_malla['Abscisa (K)'].unique(), key='vias_sec')
        
        # Verificación visible del peralte aplicado en la abscisa seleccionada
        df_perf_sel = st.session_state.vias_df_perfil
        if df_perf_sel is not None and 'Pend. Transv. Izq (%)' in df_perf_sel.columns:
            fila_sel = df_perf_sel[np.isclose(df_perf_sel['Abscisa'], abs_plot)]
            if not fila_sel.empty:
                mi = float(fila_sel.iloc[0]['Pend. Transv. Izq (%)'])
                md = float(fila_sel.iloc[0]['Pend. Transv. Der (%)'])
                bom_ref = float(st.session_state.get('bom_izq_via', -2.0))
                estado = "Peralte (curva)" if abs(abs(mi) - abs(bom_ref)) > 0.01 else "Bombeo (recta)"
                cm1, cm2, cm3 = st.columns(3)
                cm1.metric("Pend. transversal Izq", f"{mi:.3f} %")
                cm2.metric("Pend. transversal Der", f"{md:.3f} %")
                cm3.metric("Estado de la sección", estado)
        
        df_plot_sec = st.session_state.vias_df_malla[st.session_state.vias_df_malla['Abscisa (K)'] == abs_plot].copy().sort_values(by='Distancia Eje (m)').reset_index(drop=True)
        e_p = st.session_state.get('esp_pav_via', 0.1)
        e_b = st.session_state.get('esp_base_via', 0.2)
        e_s = st.session_state.get('esp_sub_via', 0.3)
        
        fig_sec = crear_figura_seccion_plotly(df_plot_sec, abs_plot, e_p, e_b, e_s)
        st.plotly_chart(fig_sec, use_container_width=True)
        
        # Generador de Grilla Completa
        fig_grilla_vias = generar_grilla_secciones_plt(st.session_state.vias_df_malla, 3, e_p, e_b, e_s)
        if fig_grilla_vias:
            st.pyplot(fig_grilla_vias)