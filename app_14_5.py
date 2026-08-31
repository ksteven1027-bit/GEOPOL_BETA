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
import hashlib
import math
import uuid
from io import StringIO
import json
from datetime import datetime, date
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
from motor_informes import (generar_reporte_poligonal_latex, generar_reporte_volumenes_latex,
                            generar_reporte_vias_latex, generar_reporte_predios_latex,
                            generar_reporte_nivelacion_latex, compilar_latex_a_pdf,
                            ORDENES_NIVELACION, FACTORES_MATERIAL, diagnostico_latex,
                            dms_a_segundos)
from modulo_fotos import guardar_foto_estampada
from motor_nube_puntos import procesar_archivo_nube, asignar_columnas
from motor_dtm import generar_dtm_curvas, extraer_elevaciones_dtm
from motor_vias import (procesar_alineamiento_horizontal, peraltes_por_abscisa,
                        radio_minimo, calcular_curvas_verticales, cota_rasante,
                        distancia_visibilidad_parada, K_MAX_DRENAJE)
from motor_grafico_vias import generar_plano_vias
from motor_predios import procesar_levantamiento_predial
from motor_grafico_predios import generar_plano_predial

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

df_plantilla_predios = pd.DataFrame({
    "Punto": ["M1", "M2", "M3", "M4"],
    "Este": [100000.0, 100050.0, 100050.0, 100000.0],
    "Norte": [100000.0, 100000.0, 99950.0, 99950.0],
    "Colindante": ["Vía Pública Principal", "Predio de Juan Pérez", "Lote 004", "Quebrada La Yerbabuena"],
    "Tipo de Lindero": ["Muro medianero", "Cerco de alambre", "Línea imaginaria", "Borde natural"],
    "Materialización": ["Mojón de concreto", "Estaca de madera", "Varilla metálica", "Punto virtual"],
    "Registro_Fotografico": [False, False, False, False]
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
    # copy(): sin esto se modifica in-place el DataFrame que recibió la
    # función cacheada, práctica que Streamlit desaconseja expresamente.
    df_niv = df_niv.copy()
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
# FICHA TÉCNICA, AISLAMIENTO POR SESIÓN Y PUENTE CON EL MOTOR DE INFORMES
# ===================================================================
VERSION_APP = "GeoPol Web 14.0"
AUTORES = ["Kevin Stiven Cubillos Ramirez", "Sergio Eduardo Barbosa Torres"]
TUTOR = "Ing. Edgar Ladino"

# Antes estaba duplicado en el módulo de nubes y en el de poligonales
FICHA_POR_DEFECTO = {
    "nombre_proyecto": "", "localizacion": "", "municipio": "", "departamento": "",
    "fecha_levantamiento": None, "cuadrilla": "", "clima": "Despejado",
    "temperatura": 18.0, "presion": 752.0,
    "equipo_marca": "", "equipo_modelo": "", "equipo_serie": "",
    "equipo_calibracion": None, "equipo_prec_ang": 5.0,
    "equipo_edm_a": 2.0, "equipo_edm_b": 2.0,
    "datum_vertical": "Nivel medio del mar - Buenaventura",
    "punto_amarre": "", "fuente_amarre": "Vértice IGAC",
    "altura_elipsoidal": 2600.0,
    "precision_exigida": 10000, "factor_tolerancia": 2.0,
    "orden_nivelacion": "Tercer orden", "longitud_nivelada_km": 1.0,
    "material_volumenes": "Material común", "capacidad_volqueta": 7.0,
    "acarreo_libre": 100.0,
    "observaciones": ""
}


# ===================================================================
# DESCRIPCIÓN DE LOS MÓDULOS (pestaña "Acerca del Sistema")
# ===================================================================
DESCRIPCION_MODULOS = [
    {
        # No se lista en "Acerca del Sistema": tiene su propia pantalla
        "oculto_en_acerca": True,
        "titulo": "Ficha Técnica del Levantamiento",
        "resumen": (
            "Registro único de los datos que identifican el trabajo: proyecto, "
            "localización, cuadrilla, instrumento y parámetros de cálculo. Encabeza "
            "todos los informes PDF y sustenta la trazabilidad exigida en "
            "interventoría. Diligenciarla antes de calcular evita que los informes "
            "salgan con los campos en blanco."),
        "entradas": ["Nombre del proyecto y localización",
                     "Fecha, cuadrilla y condiciones climáticas",
                     "Marca, modelo, serie y precisiones del equipo",
                     "Punto de amarre y altura elipsoidal de la zona",
                     "Tolerancias exigidas y material predominante"],
        "salidas": ["Encabezado de los tres informes",
                    "Tolerancia angular Ta = k a raíz de n",
                    "Factor de escala combinado",
                    "Corrección por esponjamiento y contracción"],
        "norma": "IGAC - MAGNA-SIRGAS Origen Nacional (EPSG:9377)",
    },
    {
        "titulo": "Módulo de Planimetría - Poligonales",
        "resumen": (
            "Cálculo y compensación de poligonales cerradas y abiertas con control. "
            "Reduce las distancias inclinadas, compensa el error angular, calcula los "
            "azimutes y ajusta las proyecciones por la Regla de la Brújula (Bowditch), "
            "entregando las coordenadas definitivas de cada vértice."),
        "entradas": ["Cartera de campo: ángulos horizontales y cenitales",
                     "Distancias inclinadas, altura de instrumento y de prisma",
                     "Coordenadas de amarre y referencia de orientación",
                     "Sistema de proyección de trabajo"],
        "salidas": ["Coordenadas compensadas y precisión relativa 1:P",
                    "Plano topográfico con rumbos, distancias y escala",
                    "Memoria de proyecciones y compensación",
                    "Exportación a KML, DXF y Shapefile",
                    "Informe PDF con verificación de tolerancias"],
        "norma": "IGAC - Resolución 471 de 2020",
    },
    {
        "titulo": "Módulo de Altimetría - Nivelación Geométrica",
        "resumen": (
            "Nivelación diferencial cerrada y abierta con control. Calcula las alturas "
            "de instrumento, propaga las cotas, evalúa el error de cierre contra la "
            "tolerancia del orden exigido y distribuye la compensación entre las "
            "armadas."),
        "entradas": ["Vistas atrás, intermedias y adelante",
                     "Cota del Banco de Nivel de partida",
                     "Cota de llegada en nivelaciones abiertas",
                     "Orden de nivelación y longitud del circuito"],
        "salidas": ["Cartera compensada con corrección punto por punto",
                    "Error de cierre contrastado con la tolerancia del orden",
                    "Verificación aritmética de la cartera",
                    "Perfil altimétrico e informe PDF"],
        "norma": "RAS - Resolución 0330 de 2017 para diseño por gravedad",
    },
    {
        "titulo": "Módulo de Levantamiento Predial y Catastro (LADM-COL)",
        "resumen": (
            "Módulo especializado para levantamientos prediales que garantiza el "
            "cumplimiento estricto de los lineamientos técnicos del IGAC. "
            "Asegura la interoperabilidad con el modelo LADM-COL para el Catastro "
            "Multipropósito, automatizando la estructuración matemática de linderos "
            "y el cálculo analítico de la cabida superficiaria mediante el Teorema de Gauss."
        ),
        "entradas": ["Vértices del predio (Coordenadas planas o geodésicas vía GPS)",
                     "Identificación del colindante (Vecino)",
                     "Descripción y tipo de lindero",
                     "Materialización del vértice (Mojón, estaca, etc.)"],
        "salidas": ["Cuadro oficial de áreas y linderos (Distancia y Azimut exacto)",
                    "Redacción técnica automatizada del Acta de Colindancia",
                    "Geovisualización predial con etiquetas de colindancia",
                    "Exportación nativa de geometrías a CAD/GIS (DXF, SHP, KML)"],
        "norma": "IGAC - Resoluciones 471 y 529 de 2020",
    },
    {
        "titulo": "Módulo de Volúmenes - Movimiento de Tierras",
        "resumen": (
            "Cubicaje por secciones transversales. Genera la malla de abscisas y "
            "offsets, calcula las cotas de terreno y de diseño, obtiene las áreas de "
            "corte y relleno por el método de áreas medias y construye el diagrama de "
            "masas."),
        "entradas": ["Abscisa inicial y final, intervalos longitudinal y transversal",
                     "Anchos y bombeos izquierdo y derecho",
                     "Cota de rasante inicial y pendiente longitudinal",
                     "Lecturas de mira por punto de la malla"],
        "salidas": ["Áreas y volúmenes de corte y relleno por abscisa",
                    "Diagrama de masas y análisis de acarreo",
                    "Balance real corregido y viajes de volqueta",
                    "Contraste con el método prismoidal y puntos de paso"],
        "norma": "INVÍAS - NSR-10 Título H para excavaciones",
    },
    {
        "titulo": "Módulo de Nube de Puntos",
        "resumen": (
            "Importación y visualización de levantamientos masivos. Lee archivos TXT o "
            "CSV con detección automática del separador, permite emparejar las columnas "
            "del archivo con los campos del sistema y proyecta los puntos sobre "
            "cartografía oficial para validar la georreferenciación de la radiación de "
            "campo."),
        "entradas": ["Archivos TXT o CSV de la libreta electrónica",
                     "Asignación de columnas: punto, este, norte, cota y descripción",
                     "Sistema de proyección de los datos"],
        "salidas": ["Visualización sobre mapa base satelital o cartográfico",
                    "Consolidación de varios archivos en un mismo proyecto",
                    "Base para la generación del modelo digital de terreno"],
        "norma": None,
    },
    {
        "titulo": "Módulo de Diseño Vial",
        "resumen": (
            "Diseño geométrico a partir del modelo digital de terreno. Permite ubicar "
            "los Puntos de Intersección sobre el mapa para definir el alineamiento "
            "horizontal, calcular los elementos de curva, definir la rasante y extraer "
            "el perfil longitudinal para computar volúmenes."),
        "entradas": ["Nube de puntos para generar el modelo digital de terreno",
                     "Puntos de Intersección y radios de curva",
                     "Rasante de diseño y sección tipo"],
        "salidas": ["Alineamiento horizontal con elementos de curva",
                    "Perfil longitudinal extraído del terreno",
                    "Secciones transversales y volúmenes",
                    "Plano de vías con norte y escala gráfica"],
        "norma": "INVÍAS - Manual de Diseño Geométrico de Carreteras",
    },
]

# Destino del botón "Atrás" de cada pantalla
JERARQUIA_NAVEGACION = {
    "Menu_Principal": ("Inicio", "Inicio"),
    "Ficha_Tecnica": ("Menu_Principal", "Menú Principal"),
    "Menu_Poligonales": ("Menu_Principal", "Menú Principal"),
    "Menu_Altimetria": ("Menu_Principal", "Menú Principal"),
    "Nube_Puntos": ("Menu_Principal", "Menú Principal"),
    "Diseno_Vias": ("Menu_Principal", "Menú Principal"),
    "Predios": ("Menu_Principal", "Menú Principal"),
    "Cerrada": ("Menu_Poligonales", "Módulo de Planimetría"),
    "Abierta": ("Menu_Poligonales", "Módulo de Planimetría"),
    "Niv_Cerrada": ("Menu_Altimetria", "Módulo de Altimetría"),
    "Niv_Abierta": ("Menu_Altimetria", "Módulo de Altimetría"),
    "Volumenes": ("Menu_Altimetria", "Módulo de Altimetría"),
}


def boton_atras(destino=None, etiqueta=None):
    """
    Botón de retorno al nivel anterior. Si no se indica destino, lo deduce
    de JERARQUIA_NAVEGACION segun la pantalla activa.
    """
    modo = st.session_state.get("modo_app")
    if destino is None:
        destino, etiqueta = JERARQUIA_NAVEGACION.get(
            modo, ("Menu_Principal", "Menú Principal"))
    col_atras, _ = st.columns([1, 5])
    with col_atras:
        if st.button("Volver a " + etiqueta, use_container_width=True,
                     key="atras_" + str(modo)):
            st.session_state.modo_app = destino
            st.rerun()


def obtener_dir_sesion():
    """
    Directorio privado de esta sesión del navegador.

    En Streamlit Cloud todos los usuarios comparten proceso y disco. Con
    rutas fijas ("Plano_Exportado.png", "Reportes_PDF/") dos usuarios
    concurrentes se sobrescriben el plano y las fotografías entre sí.
    Aislando por sesión el problema desaparece.
    """
    if "_sesion_id" not in st.session_state:
        st.session_state._sesion_id = uuid.uuid4().hex[:12]
    base = os.path.join("Trabajo", st.session_state._sesion_id)
    os.makedirs(base, exist_ok=True)
    return base


def dir_reportes():
    ruta = os.path.join(obtener_dir_sesion(), "Reportes_PDF")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def dir_fotos(subcarpeta, estacion=None):
    partes = [obtener_dir_sesion(), subcarpeta,
              st.session_state.get("proyecto_actual") or "Sin_Proyecto"]
    if estacion is not None:
        partes.append(str(estacion))
    ruta = os.path.join(*partes)
    os.makedirs(ruta, exist_ok=True)
    return ruta


def firma_archivos(rutas):
    """
    Huella del CONTENIDO de unas rutas (tamaño + fecha de modificación).

    st.cache_data usa los argumentos como clave. Si se le pasa solo la ruta
    ("Plano_Exportado.png", siempre igual), al recalcular el levantamiento
    la clave no cambia y devuelve el PDF anterior con el plano viejo.
    Incluyendo esta firma entre los argumentos, la caché se invalida cuando
    la figura cambia de verdad.
    """
    partes = []
    for r in (rutas or []):
        if isinstance(r, (list, tuple)):
            r = r[-1]
        try:
            partes.append(f"{r}:{os.path.getmtime(r):.0f}:{os.path.getsize(r)}")
        except (OSError, TypeError):
            partes.append(f"{r}:ausente")
    return "|".join(partes)


def huella_datos(*dataframes):
    """Hash corto del conjunto de datos, para la trazabilidad del informe."""
    h = hashlib.sha256()
    for df in dataframes:
        try:
            h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
        except Exception:
            h.update(str(df).encode("utf-8", errors="ignore"))
    return h.hexdigest()[:12].upper()


# ===================================================================
# FICHA TÉCNICA -> PARÁMETROS DEL MOTOR DE INFORMES
# ===================================================================
def _texto_fecha(valor):
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    return str(valor) if valor else ""


def construir_metadatos(sistema_referencia=None, huella=""):
    """Traduce la ficha del usuario a las claves que espera el informe."""
    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}
    lugar = ", ".join([x for x in [f["localizacion"], f["municipio"],
                                   f["departamento"]] if x])
    clima = f["clima"]
    if f.get("temperatura") is not None:
        clima += f" — {f['temperatura']:.1f} °C, {f['presion']:.0f} hPa"

    return {
        "Proyecto": f["nombre_proyecto"] or (st.session_state.get("proyecto_actual") or ""),
        "Localización": lugar,
        "Fecha de levantamiento": _texto_fecha(f["fecha_levantamiento"]),
        "Cuadrilla": f["cuadrilla"],
        "Condiciones climáticas": clima,
        "Sistema de referencia": sistema_referencia or "MAGNA-SIRGAS / Origen Nacional (EPSG:9377)",
        "Datum vertical": f["datum_vertical"],
        "Unidad angular": "Grados sexagesimales",
        "Punto de amarre": f["punto_amarre"],
        "Fuente del amarre": f["fuente_amarre"],
        "Versión GeoPol": VERSION_APP,
        "Huella del conjunto de datos": huella,
        "Observaciones": f["observaciones"],
    }


def construir_equipo():
    """Datos del instrumento. Activan el cálculo de tolerancia angular."""
    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}
    return {
        "marca": f["equipo_marca"], "modelo": f["equipo_modelo"],
        "serie": f["equipo_serie"],
        "fecha_calibracion": _texto_fecha(f["equipo_calibracion"]),
        "precision_angular_seg": f["equipo_prec_ang"],
        "edm_a_mm": f["equipo_edm_a"], "edm_b_ppm": f["equipo_edm_b"],
    }


def param_ficha(clave):
    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}
    return f.get(clave)


def coords_desde_ajuste(df_ajuste):
    """Vértices (Este, Norte) para el cálculo de área por Gauss."""
    try:
        pts = [(float(r["X_Estacion"]), float(r["Y_Estacion"]))
               for _, r in df_ajuste.iterrows()]
    except (KeyError, TypeError, ValueError):
        return None
    # En una poligonal cerrada el último vértice repite el primero
    if len(pts) > 2 and math.isclose(pts[0][0], pts[-1][0], abs_tol=1e-6) \
       and math.isclose(pts[0][1], pts[-1][1], abs_tol=1e-6):
        pts = pts[:-1]
    return pts if len(pts) >= 3 else None


def este_medio(df_ajuste):
    """Este representativo de la zona, para el factor de escala combinado."""
    try:
        return float(pd.to_numeric(df_ajuste["X_Estacion"], errors="coerce").mean())
    except (KeyError, TypeError, ValueError):
        return None


def lados_para_memoria(met, df_campo, df_ajuste, modo):
    """
    Lados (nombre, distancia horizontal, azimut) para la memoria de
    proyecciones de Bowditch del informe.

    Solo aplica a POLIGONAL CERRADA: en una abierta la suma de proyecciones
    no debe ser cero sino el desnivel entre los puntos de control conocidos,
    y la tabla reportaría un cierre falso.

    Prioriza met["lados"], que motor_v2_5 entrega sin redondear. La
    reconstrucción desde los DataFrames es un respaldo, pero Dist_Horiz
    viene redondeado a milímetro y en poligonales muy precisas eso mueve
    el cierre lo suficiente como para contradecir las métricas: por eso
    solo se acepta si reproduce el error de cierre dentro de 0,1 mm.
    """
    if modo != "Cerrada":
        return None

    lados = met.get("lados")
    if lados:
        return [{"lado": l["lado"], "distancia": l["distancia"],
                 "azimut": l["azimut"]} for l in lados]

    try:
        if "Dist_Horiz" not in df_campo.columns or "Azimut_Línea" not in df_ajuste.columns:
            return None
        recon = []
        for i in range(1, len(df_ajuste)):
            az = dms_a_segundos(df_ajuste.iloc[i]["Azimut_Línea"]) / 3600.0
            recon.append({
                "lado": f"{df_ajuste.iloc[i]['Estacionado']}-{df_ajuste.iloc[i]['Pto_Obs']}",
                "distancia": float(df_campo.iloc[i]["Dist_Horiz"]),
                "azimut": az})
        sum_e = sum(l["distancia"] * math.sin(math.radians(l["azimut"])) for l in recon)
        sum_n = sum(l["distancia"] * math.cos(math.radians(l["azimut"])) for l in recon)
        if abs(sum_e - float(met["err_e_ant"])) > 1e-4 or \
           abs(sum_n - float(met["err_n_ant"])) > 1e-4:
            return None   # no reproduce el cierre reportado: mejor omitir la tabla
        return recon
    except Exception:
        return None


def secciones_para_prismoidal(df_calculado, df_volumenes):
    """
    Construye la lista de secciones que el informe usa para contrastar
    áreas medias contra el método prismoidal y para localizar los puntos
    de paso (abscisas donde la cota roja se anula).

    Por abscisa se necesitan:
      area      : área neta con signo, (+) corte y (-) relleno
      cota_roja : diferencia terreno - diseño medida EN EL EJE
      ancho     : ancho total de la sección levantada
    """
    try:
        salida = []
        for _, fila in df_volumenes.iterrows():
            abscisa = float(fila['Abscisa (K)'])
            sec = df_calculado[df_calculado['Abscisa (K)'] == abscisa].dropna(
                subset=['Cota Terreno (m)', 'Cota Diseño (m)'])
            if sec.empty:
                continue
            eje = sec[sec['Distancia Eje (m)'] == 0.0]
            if eje.empty:
                cota_roja = float(sec['Cota Terreno (m)'].mean()
                                  - sec['Cota Diseño (m)'].mean())
            else:
                cota_roja = float(eje['Cota Terreno (m)'].iloc[0]
                                  - eje['Cota Diseño (m)'].iloc[0])
            salida.append({
                "abscisa": abscisa,
                "area": float(fila['Área Corte (m²)'] - fila['Área Relleno (m²)']),
                "cota_roja": round(cota_roja, 4),
                "ancho": float(sec['Distancia Eje (m)'].max()
                               - sec['Distancia Eje (m)'].min()),
            })
        return salida if len(salida) >= 2 else None
    except (KeyError, TypeError, ValueError):
        return None


def ficha_incompleta():
    """Campos mínimos sin diligenciar, para avisar antes de compilar."""
    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}
    faltan = []
    if not f["nombre_proyecto"]: faltan.append("Nombre del proyecto")
    if not f["localizacion"]: faltan.append("Localización")
    if not f["fecha_levantamiento"]: faltan.append("Fecha de levantamiento")
    if not f["cuadrilla"]: faltan.append("Cuadrilla")
    if not f["equipo_marca"]: faltan.append("Marca del equipo")
    return faltan



# ===================================================================
# GENERADORES DE CACHÉ GLOBAL (PDFS)
# ===================================================================
@st.cache_data(show_spinner=False)
def cachear_pdf_volumenes(df_calculado_interno, df_vol_interno, met, p_actual,
                          imprimir_secciones, salida, metadatos, equipo, params):
    """
    Se reciben DataFrames en vez del ida y vuelta por JSON: st.cache_data
    los usa como clave sin problema y se evita la pérdida de tipos del
    round-trip to_json / read_json.

    metadatos, equipo y params vienen de la Ficha Técnica y forman parte
    de la clave de caché, de modo que al editarla el informe se regenera.
    """
    ruta_masa = os.path.join(salida, "Curva_Masa.png")
    guardar_imagen_masa_plt(df_vol_interno, ruta_masa)

    paths_sec = []
    if imprimir_secciones:
        for a_val in sorted(df_calculado_interno['Abscisa (K)'].unique()):
            df_p = df_calculado_interno[df_calculado_interno['Abscisa (K)'] == a_val].copy().dropna(subset=['Cota Terreno (m)', 'Cota Diseño (m)']).sort_values('Distancia Eje (m)')
            if not df_p.empty:
                ruta_s = os.path.join(salida, f"Sec_K{a_val:.3f}.png")
                guardar_seccion_plt(df_p, a_val, ruta_s)
                paths_sec.append((a_val, ruta_s))

    # El motor acumula internamente: aquí se le entrega el volumen neto
    # POR TRAMO, no la columna 'Volumen Neto (m³)' que ya viene acumulada.
    abscisas, vol_netos = None, None
    try:
        neto_tramo = (df_vol_interno['Vol. Corte (m³)'].fillna(0)
                      - df_vol_interno['Vol. Relleno (m³)'].fillna(0))
        abscisas = df_vol_interno['Abscisa (K)'].astype(float).tolist()
        vol_netos = neto_tramo.astype(float).tolist()
    except Exception:
        abscisas, vol_netos = None, None

    secciones = secciones_para_prismoidal(df_calculado_interno, df_vol_interno)

    tex_vol = generar_reporte_volumenes_latex(
        df_vol_interno, met, AUTORES, TUTOR,
        path_masas=ruta_masa, paths_secciones=paths_sec,
        directorio_salida=salida,
        metadatos=metadatos, equipo=equipo,
        material=params["material"],
        capacidad_volqueta=params["capacidad_volqueta"],
        acarreo_libre=params["acarreo_libre"],
        abscisas=abscisas, volumenes_netos=vol_netos,
        secciones=secciones)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(
        tex_vol, output_dir=salida, filename=f"Cubicaje_{p_actual}")
    return pdf_bytes, tex_vol, debug_msg

@st.cache_data(show_spinner=False)
def cachear_pdf_vias(df_curvas, df_vertical, df_transicion, df_curvas_v,
                     df_cubicaje, met_vol,
                     p_actual, salida, firma, metadatos, equipo, params,
                     paths_sec_tuple=()):
    """
    Informe del diseño geométrico vial. 'firma' incorpora las figuras del
    plano y del perfil: si cambian, la caché se invalida y no se reutiliza
    un PDF con un trazado antiguo.
    """
    tex_vias = generar_reporte_vias_latex(
        df_curvas, df_vertical, AUTORES, TUTOR,
        df_transicion=df_transicion,
        df_curvas_verticales=df_curvas_v,
        df_cubicaje=df_cubicaje,
        metricas_volumen=met_vol,
        v_diseno=params["v_diseno"],
        ancho_calzada=params["ancho_calzada"],
        ancho_carril=params["ancho_carril"],
        n_carriles_giran=params["n_carriles_giran"],
        bombeo=params["bombeo"],
        peralte_max=params["peralte_max"],
        pendiente_max=params["pendiente_max"],
        pendiente_min=params["pendiente_min"],
        radio_minimo_admisible=params["radio_minimo"],
        path_planta=params.get("path_planta"),
        path_perfil=params.get("path_perfil"),
        path_masas=params.get("path_masas"),
        paths_secciones=list(paths_sec_tuple) or None,
        directorio_salida=salida,
        metadatos=metadatos, equipo=equipo)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(
        tex_vias, output_dir=salida, filename=f"Diseno_Vial_{p_actual}")
    return pdf_bytes, tex_vias, debug_msg


@st.cache_data(show_spinner=False)
def cachear_pdf_altimetria(df_niv_interno, met, p_actual, tipo_niv, fotos_paths,
                           salida, firma_fotos, metadatos, equipo, params, bm):
    ruta_perfil = os.path.join(salida, "Perfil_Nivelacion.png")
    guardar_perfil_altimetria_plt(df_niv_interno, ruta_perfil)

    tex_niv = generar_reporte_nivelacion_latex(
        df_niv_interno, met, tipo_niv, AUTORES, TUTOR,
        path_grafico=ruta_perfil, fotos_paths=fotos_paths,
        directorio_salida=salida,
        metadatos=metadatos, equipo=equipo,
        longitud_km=params["longitud_km"], orden=params["orden"],
        bm_partida=bm)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(
        tex_niv, output_dir=salida, filename=f"Nivelacion_{p_actual}")
    return pdf_bytes, tex_niv, debug_msg

@st.cache_data(show_spinner=False)
def cachear_pdf_poli(df_campo_i, df_ajuste_i, met, p_actual, ruta_p, f_tomadas, t_app,
                     salida, firma_figs, metadatos, equipo, params, coords, este_ref,
                     lados):
    titulo = ("Poligonal Cerrada" if t_app == "Cerrada"
              else "Poligonal Abierta con Control")
    data_tex = generar_reporte_poligonal_latex(
        df_campo_i, df_ajuste_i, met, titulo, AUTORES, TUTOR,
        path_grafico=ruta_p, fotos_paths=f_tomadas,
        directorio_salida=salida,
        metadatos=metadatos, equipo=equipo,
        coords_poligono=coords, lados=lados,
        este_referencia=este_ref,
        altura_elipsoidal=params["altura_elipsoidal"],
        precision_exigida=params["precision_exigida"],
        factor_tolerancia=params["factor_tolerancia"])
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(
        data_tex, output_dir=salida, filename=f"Reporte_{p_actual}")
    return pdf_bytes, data_tex, debug_msg

@st.cache_data(show_spinner=False)
def cachear_pdf_predios(df_linderos, met_predios, p_actual, ruta_p, f_tomadas, salida, firma_figs, metadatos, equipo):
    data_tex = generar_reporte_predios_latex(
        df_linderos, met_predios, AUTORES, TUTOR, path_grafico=ruta_p, 
        fotos_paths=f_tomadas, directorio_salida=salida, metadatos=metadatos, equipo=equipo)
    pdf_bytes, pdf_path, debug_msg = compilar_latex_a_pdf(data_tex, output_dir=salida, filename=f"Reporte_Predial_{p_actual}")
    return pdf_bytes, data_tex, debug_msg

# ===================================================================
# GESTOR DE PROYECTOS Y SISTEMA DE GUARDADO LOCAL (.GP)
# ===================================================================

def generar_datos_guardado():
    tipos_seguros = (int, float, str, bool, list, dict, tuple, set, pd.DataFrame, type(None))
    estado_a_guardar = {}
    # vias_df_master_dtm es un derivado de nubes_vias_guardadas: se excluye para
    # no duplicar cientos de miles de filas dentro del archivo .gp
    # _sesion_id identifica el directorio privado de ESTE navegador: si
    # viajara dentro del .gp, al cargarlo en otra sesión apuntaría a
    # carpetas ajenas.
    llaves_prohibidas = ["sel_cargar", "sel_eliminar", "nav", "FormSubmitter",
                         "vias_df_master_dtm", "_sesion_id", "fw_"]

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
        "vias_map_nonce": 0,
        "vias_vista": None,
        "df_reporte_curvas": None,
        "df_dibujo_eje": None,
        "vias_dtm_bounds": None,
        "vias_dtm_ruta": None,
        "vias_df_master_dtm": None,
        "vias_mapeo_dtm": {},
        "vias_df_vertical": None,
        "vias_pts_fuera_dtm": 0,
        "vias_df_transicion": None,
        "vias_df_curvas_v": None,
        "vias_lv_manual": {},
        "vias_pdf_bytes": None,
        "vias_tex_code": None,
        "vias_debug_msg": None,
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
        "df_predios_campo": df_plantilla_predios.copy(),
        "calc_predios": False,
        "df_cuadro_linderos": None,
        "met_predios": None,
        "df_malla_vol": None,
        "proyecto_actual": None,
        "ficha_tecnica": dict(FICHA_POR_DEFECTO)
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

# Capturar navegación desde imágenes clickeables
if "nav" in st.query_params:
    st.session_state.modo_app = st.query_params["nav"]
st.query_params.clear()

@st.cache_data(show_spinner=False)
def obtener_b64_imagen(ruta):
    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def mostrar_icono(nombre_archivo, fallback_emoji="", width=120, hover_effect=True, shadow=True, border_radius="30px", link_nav=None):
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

    html = f"<style>.{css_class} {{ width: {width}px; border-radius: {border_radius}; display: block; margin: 0 auto; cursor: pointer;"
    if shadow: html += "box-shadow: 0 8px 16px rgba(0,0,0,0.2);"
    if hover_effect and shadow: html += f"}} .{css_class}:hover {{ transform: scale(1.05) translateY(-5px); box-shadow: 0 12px 20px rgba(0,0,0,0.3); "
    html += "}</style>"

    img_html = f'<img src="data:{mime_type};base64,{b64}" class="{css_class}">'
    
    # Si la imagen tiene un destino, la envolvemos en un enlace HTML
    if link_nav:
        img_html = f'<a href="/?nav={link_nav}" target="_self">{img_html}</a>'
        
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
# BARRA LATERAL (SIDEBAR OMNIPRESENTE)
# ===================================================================
with st.sidebar:
    mostrar_icono("logo_geopol.svg", "", width=220, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("---")

    # 1. GESTIÓN DEL PROYECTO ACTUAL
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

    # 2. NAVEGACIÓN BÁSICA
    st.markdown("### Navegación Principal")
    if st.button("🏠 Inicio", use_container_width=True):
        st.session_state.modo_app = "Inicio"
        st.rerun()

    # 3. ACCESOS DIRECTOS A MÓDULOS (Solo visibles con proyecto activo)
    if st.session_state.get("proyecto_actual"):
        if st.button("🎛️ Menú de Módulos", use_container_width=True):
            st.session_state.modo_app = "Menu_Principal"
            st.rerun()
            
        etiqueta_ficha = "📋 Ficha Técnica" + (" (!)" if ficha_incompleta() else "")
        if st.button(etiqueta_ficha, use_container_width=True):
            st.session_state.modo_app = "Ficha_Tecnica"
            st.rerun()

        st.markdown("---")
        st.markdown("### Accesos Directos")
        
        with st.expander("📐 Módulo de Planimetría", expanded=False):
            if st.button("Poligonal Cerrada", use_container_width=True):
                st.session_state.modo_app = "Cerrada"
                st.rerun()
            if st.button("Poligonal Abierta", use_container_width=True):
                st.session_state.modo_app = "Abierta"
                st.rerun()

        with st.expander("⛰️ Módulo de Altimetría", expanded=False):
            if st.button("Nivelación Cerrada", use_container_width=True):
                st.session_state.modo_app = "Niv_Cerrada"
                st.rerun()
            if st.button("Nivelación Abierta", use_container_width=True):
                st.session_state.modo_app = "Niv_Abierta"
                st.rerun()
            if st.button("Cálculo de Volúmenes", use_container_width=True):
                st.session_state.modo_app = "Volumenes"
                st.rerun()

        with st.expander("🏡 Módulo Predial (IGAC)", expanded=False):
            if st.button("Levantamiento Predial", use_container_width=True):
                st.session_state.modo_app = "Predios"
                st.rerun()

        with st.expander("🛣️ Geomática y Diseño 3D", expanded=False):
            if st.button("Nube de Puntos", use_container_width=True):
                st.session_state.modo_app = "Nube_Puntos"
                st.rerun()
            if st.button("Diseño Geométrico Vial", use_container_width=True):
                st.session_state.modo_app = "Diseno_Vias"
                st.rerun()

    # 4. PIE DE PÁGINA (Siempre visible)
    st.markdown("---")
    mostrar_icono("logo_udistrital.png", "", width=160, hover_effect=False, shadow=False, border_radius="0px")
    st.markdown("<p style='text-align:center; font-size:12px; color:gray;'>Kevin Cubillos & Sergio Barbosa</p>", unsafe_allow_html=True)


# ===================================================================
# PANTALLAS PRINCIPALES (ENRUTAMIENTO CENTRAL)
# ===================================================================
if st.session_state.modo_app in ["Inicio", "Menu_Principal"]:
    col_logo, col_info = st.columns([1, 4])
    with col_logo:
        mostrar_icono("logo_udistrital.png", "", width=180, hover_effect=False, shadow=False, border_radius="0px")
    with col_info:
        st.markdown("## **UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS**")
        st.markdown("#### **Facultad Tecnológica - Ingeniería Civil**")
        st.markdown("**Trabajo de Grado:** Estructuración de un ecosistema computacional para la interoperabilidad espacial y el análisis algorítmico en geomática civil")

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
        st.markdown("<h3 style='text-align: center; color: #4A4A4A; margin-top: -30px; font-weight: 600;'>Máxima precisión al alcance de tus manos</h3>", unsafe_allow_html=True)

    st.markdown("---")
    tab_proyectos, tab_sobre, tab_equipo = st.tabs(["Gestor de Proyectos", "Acerca del Sistema", "Equipo de Desarrollo"])

    with tab_proyectos:
        st.markdown("### Centro de Trabajo")
        st.caption("Cree un nuevo entorno de trabajo en blanco o restaure el estado de un proyecto cargando su archivo local (.gp).")

        col_new, col_load = st.columns(2)
        with col_new:
            st.success("**Iniciar Nuevo Proyecto**")
            with st.form("form_nuevo_proyecto"):
                nuevo_nombre = st.text_input("Asignar nombre del proyecto:")
                if st.form_submit_button("Crear Espacio de Trabajo", use_container_width=True):
                    if nuevo_nombre.strip() == "": 
                        st.warning("Advertencia: Debe asignar una nomenclatura válida al proyecto.")
                    else: 
                        crear_nuevo_proyecto(nuevo_nombre.strip())
                        st.rerun()
        with col_load:
            st.info("**Restaurar Copia de Seguridad**")
            archivo_gp = st.file_uploader("Importar archivo de proyecto de GeoPol Web (.gp)", type=['gp'])
            if archivo_gp is not None:
                if st.button("Cargar Espacio de Trabajo", use_container_width=True): 
                    nombre_base = archivo_gp.name.replace(".gp", "")
                    cargar_proyecto_desde_archivo(archivo_gp.getvalue(), nombre_base)
                    st.rerun()

    with tab_sobre:
        st.markdown("### El Geoportal Web")
        st.write(
            "El procesamiento de datos topográficos en oficina ha sido "
            "históricamente un segmento crítico del trabajo de ingeniería y, a la "
            "vez, el más expuesto a errores sistemáticos. La cartera se transcribe a "
            "mano a una hoja de cálculo, el ajuste se resuelve con fórmulas "
            "improvisadas que rara vez quedan documentadas, el plano se dibuja en un "
            "programa distinto y el informe se redacta en un software ofimático. Cada salto entre "
            "herramientas es una oportunidad de que un dato se pierda, se redondee de "
            "más o deje de corresponder con el resto del documento.")
        st.write(
            "GeoPol Web reúne ese recorrido completo en una sola plataforma: desde la "
            "captura en campo, con fotografías estampadas que sirven de evidencia, "
            "hasta la emisión del informe técnico formal con sus memorias de cálculo. "
            "Los mismos números que se calculan son los que se dibujan y los que se "
            "imprimen, de modo que el documento final no puede contradecir al "
            "procesamiento que lo originó.")

        st.markdown("### Qué lo distingue")
        st.markdown(
            "**Normativa colombiana de fábrica.** Trabaja sobre MAGNA-SIRGAS Origen "
            "Nacional (EPSG:9377) conforme a la Resolución 471 de 2020 del IGAC, y "
            "evalúa los resultados frente a las exigencias del RAS, el INVÍAS y la "
            "NSR-10. Las herramientas de propósito general llegan con parámetros "
            "genéricos que hay que configurar, y esa configuración rara vez queda "
            "registrada en el informe.")
        st.markdown(
            "**El informe emite un dictamen, no un volcado de tablas.** Cada cierre se "
            "contrasta con su tolerancia y el documento declara si cumple o no, con la "
            "fórmula aplicada a la vista. La ficha del levantamiento, la "
            "identificación del equipo con su calibración y la huella del conjunto de "
            "datos encabezan el documento, que es lo que sustenta la trazabilidad "
            "exigida en interventoría.")
        st.markdown(
            "**Correcciones que suelen omitirse.** Reduce las distancias de terreno al "
            "plano de proyección mediante el factor de escala combinado, y corrige el "
            "balance de tierras por esponjamiento y contracción del material. Un corte "
            "no rellena su propio volumen: pasarlo por alto subestima el material que "
            "hay que mover, y esa diferencia se paga en obra.")
        st.markdown(
            "**Sin instalación y sin licencias.** Se ejecuta en el navegador, también "
            "desde el teléfono en campo. El proyecto completo se guarda en un archivo "
            "que el usuario descarga y conserva, sin depender de una cuenta ni de un "
            "servidor ajeno.")
        st.markdown(
            "**Los datos no quedan encerrados.** Exporta a KML, DXF y Shapefile, y "
            "entrega también el código fuente LaTeX del informe, de modo que el "
            "trabajo puede continuarse en cualquier entorno GIS o CAD.")
        st.markdown(
            "**Notación colombiana en todo el documento.** Coma decimal y punto para "
            "los miles, de forma consistente en tablas, gráficas e informes.")

        st.markdown("---")
        st.markdown("### Módulos de la Plataforma")
        st.caption("Despliegue cada módulo para conocer su alcance, los datos que "
                   "requiere y los productos que entrega.")

        for modulo in DESCRIPCION_MODULOS:
            if modulo.get("oculto_en_acerca"):
                continue
            with st.expander(modulo["titulo"], expanded=False):
                st.write(modulo["resumen"])
                col_ent, col_sal = st.columns(2)
                with col_ent:
                    st.markdown("**Datos que requiere**")
                    st.markdown("\n".join("- " + x for x in modulo["entradas"]))
                with col_sal:
                    st.markdown("**Productos que entrega**")
                    st.markdown("\n".join("- " + x for x in modulo["salidas"]))
                if modulo.get("norma"):
                    st.caption("Referencia normativa: " + modulo["norma"])

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
    boton_atras()
    st.markdown("<h4 style='text-align: center; color: gray;'>Seleccione el Entorno de Trabajo Operativo</h4><br>", unsafe_allow_html=True)
    
    col_disc1, col_disc2, col_disc3 = st.columns(3)
    with col_disc1:
        mostrar_icono("planimetria.png", "", width=160, link_nav="Menu_Poligonales")
        if st.button("Planimetría", use_container_width=True): st.session_state.modo_app = "Menu_Poligonales"; st.rerun()
    with col_disc2:
        mostrar_icono("altimetria.png", "", width=292, link_nav="Menu_Altimetria")
        if st.button("Altimetría", use_container_width=True): st.session_state.modo_app = "Menu_Altimetria"; st.rerun()
    with col_disc3:
        mostrar_icono("levantamiento_predial.png", "🏡", width=290, link_nav="Predios")
        if st.button("Levantamiento Predial", use_container_width=True): st.session_state.modo_app = "Predios"; st.rerun()
        
    st.markdown("<br>", unsafe_allow_html=True)
    col_disc4, col_disc5, col_disc6 = st.columns(3)
    with col_disc4:
        mostrar_icono("nube_puntos.png", "", width=160, link_nav="Nube_Puntos")
        if st.button("Nube de Puntos", use_container_width=True): st.session_state.modo_app = "Nube_Puntos"; st.rerun()
    with col_disc5:
        mostrar_icono("volumenes.png", "", width=160, link_nav="Diseno_Vias")
        if st.button("Diseño Vial", use_container_width=True): st.session_state.modo_app = "Diseno_Vias"; st.rerun()

    if st.session_state.pop("ficha_recien_guardada", False):
        st.success("Ficha Técnica guardada. Seleccione el módulo con el que desea trabajar.")

    st.markdown("---")
    faltantes_ficha = ficha_incompleta()
    if faltantes_ficha:
        st.warning("**La Ficha Técnica del Levantamiento está incompleta.** Sin ella "
                   "los informes salen con el encabezado en blanco. Faltan: "
                   + ", ".join(faltantes_ficha))
    else:
        st.success("Ficha Técnica del Levantamiento diligenciada.")
    if st.button("Abrir Ficha Técnica del Levantamiento", use_container_width=True,
                 type="primary" if faltantes_ficha else "secondary"):
        st.session_state.modo_app = "Ficha_Tecnica"
        st.rerun()

# ===================================================================
# MÓDULO DE FICHA TÉCNICA DEL LEVANTAMIENTO
# ===================================================================
elif st.session_state.modo_app == "Ficha_Tecnica":
    renderizar_banner_proyecto()
    boton_atras()
    st.title("Ficha Técnica del Levantamiento")
    st.markdown("Estos datos encabezan **todos** los informes PDF que genere la "
                "plataforma. Son los que sustentan la trazabilidad exigida en "
                "interventoría: sin ellos el informe sale con los campos en blanco.")

    faltantes = ficha_incompleta()
    if faltantes:
        st.warning("Campos mínimos sin diligenciar: " + ", ".join(faltantes))
    else:
        st.success("Ficha completa. Los informes saldrán con el encabezado lleno.")

    f = {**FICHA_POR_DEFECTO, **st.session_state.get("ficha_tecnica", {})}

    with st.form("form_ficha_tecnica"):
        tab_proy, tab_eq, tab_ref, tab_par = st.tabs([
            "Proyecto y Cuadrilla", "Equipo Topográfico",
            "Referencia y Amarre", "Parámetros de Cálculo"])

        # ---------------- Proyecto ----------------
        with tab_proy:
            c1, c2 = st.columns(2)
            nombre_proyecto = c1.text_input(
                "Nombre del proyecto",
                value=f["nombre_proyecto"] or (st.session_state.get("proyecto_actual") or ""),
                placeholder="Levantamiento topográfico Sede Tecnológica")
            fecha_lev = c2.date_input(
                "Fecha de levantamiento",
                value=f["fecha_levantamiento"] or date.today())

            st.markdown("**Localización**")
            c1, c2, c3 = st.columns(3)
            localizacion = c1.text_input("Sector / vereda / dirección",
                                         value=f["localizacion"],
                                         placeholder="Carrera 7 con Calle 40 Sur")
            municipio = c2.text_input("Municipio", value=f["municipio"],
                                      placeholder="Bogotá D.C.")
            departamento = c3.text_input("Departamento", value=f["departamento"],
                                         placeholder="Cundinamarca")

            st.markdown("**Cuadrilla y condiciones**")
            cuadrilla = st.text_input(
                "Integrantes de la cuadrilla",
                value=f["cuadrilla"],
                placeholder="Topógrafo: ... | Cadeneros: ... | Anotador: ...")
            c1, c2, c3 = st.columns(3)
            opciones_clima = ["Despejado", "Parcialmente nublado", "Nublado",
                              "Llovizna", "Lluvia", "Neblina"]
            clima = c1.selectbox(
                "Condiciones climáticas", opciones_clima,
                index=opciones_clima.index(f["clima"]) if f["clima"] in opciones_clima else 0)
            temperatura = c2.number_input("Temperatura (°C)", value=float(f["temperatura"]),
                                          step=0.5, format="%.1f")
            presion = c3.number_input("Presión (hPa)", value=float(f["presion"]),
                                      step=1.0, format="%.0f")
            st.caption("Temperatura y presión son los valores con los que se aplicó "
                       "la corrección atmosférica del equipo.")

            observaciones = st.text_area(
                "Observaciones generales", value=f["observaciones"], height=80,
                placeholder="Incidencias de campo, obstrucciones, repeticiones...")

        # ---------------- Equipo ----------------
        with tab_eq:
            st.markdown("**Instrumento utilizado**")
            c1, c2, c3 = st.columns(3)
            equipo_marca = c1.text_input("Marca", value=f["equipo_marca"],
                                         placeholder="Leica / Topcon / South")
            equipo_modelo = c2.text_input("Modelo", value=f["equipo_modelo"],
                                          placeholder="TS07")
            equipo_serie = c3.text_input("Número de serie", value=f["equipo_serie"])

            st.markdown("**Precisiones nominales y calibración**")
            c1, c2, c3 = st.columns(3)
            equipo_calib = c1.date_input("Fecha del certificado de calibración",
                                         value=f["equipo_calibracion"] or date.today())
            equipo_prec_ang = c2.number_input(
                "Precisión angular (segundos)", value=float(f["equipo_prec_ang"]),
                min_value=0.1, max_value=60.0, step=0.5, format="%.1f")
            c3.markdown("&nbsp;")
            c3.caption("La precisión angular define la tolerancia "
                       "Ta = k · a · √n del informe de poligonal.")

            c1, c2 = st.columns(2)
            equipo_edm_a = c1.number_input("Precisión EDM — término fijo (mm)",
                                           value=float(f["equipo_edm_a"]),
                                           step=0.5, format="%.1f")
            equipo_edm_b = c2.number_input("Precisión EDM — término proporcional (ppm)",
                                           value=float(f["equipo_edm_b"]),
                                           step=0.5, format="%.1f")

        # ---------------- Referencia ----------------
        with tab_ref:
            st.markdown("**Sistema de referencia**")
            st.info("El sistema horizontal se toma automáticamente de la proyección "
                    "que selecciones en cada módulo de cálculo.")
            datum_vertical = st.text_input("Datum vertical", value=f["datum_vertical"])

            st.markdown("**Amarre del levantamiento**")
            c1, c2 = st.columns(2)
            punto_amarre = c1.text_input(
                "Código del punto de amarre", value=f["punto_amarre"],
                placeholder="BM-IGAC-4521 / GPS-11")
            opciones_fuente = ["Vértice IGAC", "GNSS estático", "GNSS RTK",
                               "Red geodésica municipal", "Arbitrario / local"]
            fuente_amarre = c2.selectbox(
                "Fuente del amarre", opciones_fuente,
                index=opciones_fuente.index(f["fuente_amarre"])
                if f["fuente_amarre"] in opciones_fuente else 0)

            altura_elipsoidal = st.number_input(
                "Altura elipsoidal media de la zona (m)",
                value=float(f["altura_elipsoidal"]), step=10.0, format="%.1f")
            st.caption("Necesaria para el factor de escala combinado. Es la altura "
                       "sobre el elipsoide (h = H + ondulación geoidal), no la cota "
                       "sobre el nivel del mar. En la sabana de Bogotá ronda los 2.600 m.")

        # ---------------- Parámetros ----------------
        with tab_par:
            st.markdown("**Planimetría**")
            c1, c2 = st.columns(2)
            precision_exigida = c1.number_input(
                "Precisión relativa exigida (1 : P)",
                value=int(f["precision_exigida"]), min_value=500,
                max_value=100000, step=500)
            factor_tolerancia = c2.number_input(
                "Factor k de tolerancia angular", value=float(f["factor_tolerancia"]),
                min_value=0.5, max_value=5.0, step=0.5, format="%.1f")
            st.caption("k = 1 exigente · k = 2 estándar en obra civil · k = 3 expedito.")

            st.markdown("**Altimetría**")
            c1, c2 = st.columns(2)
            ordenes = list(ORDENES_NIVELACION.keys())
            orden_nivelacion = c1.selectbox(
                "Orden de nivelación exigido", ordenes,
                index=ordenes.index(f["orden_nivelacion"])
                if f["orden_nivelacion"] in ordenes else ordenes.index("Tercer orden"))
            longitud_nivelada_km = c2.number_input(
                "Longitud total nivelada (km)",
                value=float(f["longitud_nivelada_km"]), min_value=0.0,
                step=0.1, format="%.3f")
            st.caption("La tolerancia altimétrica es e = k·√K, con K en kilómetros. "
                       "La cartera de nivelación no registra distancias, por eso hay "
                       "que indicar aquí la longitud del circuito.")

            st.markdown("**Movimiento de tierras**")
            c1, c2, c3 = st.columns(3)
            materiales = list(FACTORES_MATERIAL.keys())
            material_volumenes = c1.selectbox(
                "Material predominante", materiales,
                index=materiales.index(f["material_volumenes"])
                if f["material_volumenes"] in materiales else 0)
            capacidad_volqueta = c2.number_input(
                "Capacidad de volqueta (m³)", value=float(f["capacidad_volqueta"]),
                min_value=1.0, step=0.5, format="%.1f")
            acarreo_libre = c3.number_input(
                "Distancia de acarreo libre (m)", value=float(f["acarreo_libre"]),
                min_value=0.0, step=10.0, format="%.0f")
            st.caption("El material determina el esponjamiento y la contracción con "
                       "los que se corrige el balance volumétrico real.")

        guardado = st.form_submit_button("Guardar Ficha Técnica",
                                         type="primary", use_container_width=True)

    if guardado:
        st.session_state.ficha_tecnica = {
            "nombre_proyecto": nombre_proyecto.strip(),
            "localizacion": localizacion.strip(),
            "municipio": municipio.strip(),
            "departamento": departamento.strip(),
            "fecha_levantamiento": fecha_lev,
            "cuadrilla": cuadrilla.strip(),
            "clima": clima, "temperatura": temperatura, "presion": presion,
            "equipo_marca": equipo_marca.strip(),
            "equipo_modelo": equipo_modelo.strip(),
            "equipo_serie": equipo_serie.strip(),
            "equipo_calibracion": equipo_calib,
            "equipo_prec_ang": equipo_prec_ang,
            "equipo_edm_a": equipo_edm_a, "equipo_edm_b": equipo_edm_b,
            "datum_vertical": datum_vertical.strip(),
            "punto_amarre": punto_amarre.strip(),
            "fuente_amarre": fuente_amarre,
            "altura_elipsoidal": altura_elipsoidal,
            "precision_exigida": int(precision_exigida),
            "factor_tolerancia": factor_tolerancia,
            "orden_nivelacion": orden_nivelacion,
            "longitud_nivelada_km": longitud_nivelada_km,
            "material_volumenes": material_volumenes,
            "capacidad_volqueta": capacidad_volqueta,
            "acarreo_libre": acarreo_libre,
            "observaciones": observaciones.strip(),
        }
        st.cache_data.clear()   # los PDFs cacheados llevan la ficha anterior
        st.session_state.ficha_recien_guardada = True
        # Al guardar se devuelve al usuario a la selección de módulos
        st.session_state.modo_app = "Menu_Principal"
        st.rerun()

    st.markdown("---")
    with st.expander("Vista previa del encabezado que verá el informe"):
        previa = construir_metadatos(huella="(se calcula al compilar)")
        st.dataframe(
            pd.DataFrame({"Campo": list(previa.keys()),
                          "Valor": [v if v else "sin diligenciar"
                                    for v in previa.values()]}),
            use_container_width=True, hide_index=True)

    with st.expander("Estado del motor LaTeX en este servidor"):
        diag = diagnostico_latex()
        if not diag["pdflatex"]:
            st.error("No hay pdflatex instalado. Añade packages.txt al repositorio.")
        elif diag["criticos"]:
            st.error(diag["mensaje"])
        elif diag["faltantes"]:
            st.warning(diag["mensaje"])
        else:
            st.success(diag["mensaje"])
        if diag["faltantes"]:
            st.caption("Contenido recomendado para packages.txt:")
            st.code(diag["packages_txt"], language="text")

elif st.session_state.modo_app == "Menu_Poligonales":
    boton_atras()
    st.markdown("<h3 style='text-align: center; color: #4A4A4A;'>Análisis Planimétrico (Poligonales)</h3><br>", unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        mostrar_icono("poligonal_cerrada.png", "", width=240, link_nav="Cerrada")
        if st.button("Ejecutar Circuito Cerrado", use_container_width=True): st.session_state.modo_app = "Cerrada"; st.rerun()
    with colB:
        mostrar_icono("poligonal_abierta.png", "", width=240, link_nav="Abierta")
        if st.button("Ejecutar Poligonal Abierta", use_container_width=True): st.session_state.modo_app = "Abierta"; st.rerun()

elif st.session_state.modo_app == "Menu_Altimetria":
    boton_atras()
    st.markdown("<h3 style='text-align: center; color: #4A4A4A;'>Control Altimétrico y Análisis Vertical</h3><br>", unsafe_allow_html=True)
    colA, colB, colC = st.columns(3)
    with colA:
        mostrar_icono("niv_cerrada.png", "", width=182, link_nav="Niv_Cerrada")
        if st.button("Nivelación de Circuito Cerrado", use_container_width=True): st.session_state.modo_app = "Niv_Cerrada"; st.rerun()
    with colB:
        mostrar_icono("niv_abierta.png", "", width=360, link_nav="Niv_Abierta")
        if st.button("Nivelación de Circuito Abierto", use_container_width=True): st.session_state.modo_app = "Niv_Abierta"; st.rerun()
    with colC:
        mostrar_icono("volumenes.png", "", width=180, link_nav="Volumenes")
        if st.button("Cálculo de Volúmenes y Diseño", use_container_width=True): st.session_state.modo_app = "Volumenes"; st.rerun()

# ===================================================================
# NUEVO MÓDULO: LEVANTAMIENTO PREDIAL Y CATASTRO (LADM-COL)
# ===================================================================

elif st.session_state.modo_app == "Predios":
    renderizar_banner_proyecto()
    boton_atras()
    st.title("Levantamiento Predial y Catastro (LADM-COL)")
    st.markdown("Estructuración de linderos, cálculo de áreas por determinantes y verificación de cierre, conforme a las Resoluciones 471 y 529 de 2020 del IGAC.")

    lista_proyecciones_disp = list(motor_igac.transformadores.keys())
    nombre_proyeccion = st.selectbox("Sistema de Coordenadas Geodésico Principal:", lista_proyecciones_disp, index=st.session_state.get("proy_guardada", 0))
    st.session_state.proy_guardada = lista_proyecciones_disp.index(nombre_proyeccion)
    trans_to_wgs = motor_igac.transformadores_inversos[nombre_proyeccion]

    st.subheader(f"Interfaz de Satélite -> Transformación Cartográfica: {nombre_proyeccion}")
    col_gps1, col_gps2 = st.columns([1, 2])
    
    with col_gps1: 
        # Retiramos el 'key' ya que la librería no lo soporta
        location = streamlit_geolocation()
    
    with col_gps2:
        if location and location['latitude'] is not None:
            # LÓGICA DE DESBLOQUEO: Comparamos si esta coordenada es la que acabamos de guardar
            if st.session_state.get("ultimo_gps_registrado") == location:
                st.info("✅ Vértice añadido a la tabla. Desplácese al siguiente punto y presione el ícono del GPS para tomar una nueva lectura.")
            else:
                lat_gps, lon_gps, alt_gps = location['latitude'], location['longitude'], location['altitude'] or 100.0
                resultados_conversion = motor_igac.convertir_coordenada(lat_gps, lon_gps)
                x_plana = resultados_conversion[nombre_proyeccion]["Este"]
                y_plana = resultados_conversion[nombre_proyeccion]["Norte"]
                
                st.success(f"Posición Satelital Identificada: Lat {lat_gps:.9f}°, Lon {lon_gps:.9f}°")
                
                if st.button("Añadir Coordenada Local como Vértice del Predio", type="primary"):
                    nuevo_vertice = {
                        "Punto": f"M{len(st.session_state.df_predios_campo) + 1}", 
                        "Este": round(x_plana, 3), 
                        "Norte": round(y_plana, 3),
                        "Colindante": "---",
                        "Tipo de Lindero": "---",
                        "Materialización": "---",
                        "Registro_Fotografico": False
                    }
                    st.session_state.df_predios_campo = pd.concat([st.session_state.df_predios_campo, pd.DataFrame([nuevo_vertice])], ignore_index=True)
                    
                    # Guardamos la huella de esta lectura para evitar que el botón se quede "pegado"
                    st.session_state.ultimo_gps_registrado = location
                    st.rerun() 
        else: 
            st.caption("Receptando señal GPS del hardware local...")

    # -----------------------------------------------------------
    # IMPORTADOR DE CARTERA PREDIAL BASE (.TXT / .CSV) O PLANTILLA
    # -----------------------------------------------------------
    with st.expander("📂 Importar Documento Base o Cargar Datos de Ejemplo", expanded=False):
        st.markdown("Sube un archivo de coordenadas desde tu colector (.txt, .csv), o carga los datos precargados si deseas realizar una prueba rápida del módulo.")
        
        col_up1, col_up2 = st.columns([2, 1])
        
        with col_up1:
            archivo_predial = st.file_uploader("Cargar levantamiento desde colector", type=["txt", "csv"], key="up_predios")
            if archivo_predial is not None:
                try:
                    df_cargado = pd.read_csv(archivo_predial, sep=None, engine='python')
                    columnas_txt = df_cargado.columns.tolist()
                    
                    st.success("✅ Archivo leído correctamente. Por favor, asigne las columnas correspondientes:")
                    
                    idx_pto = columnas_txt.index(next((c for c in columnas_txt if "PUNTO" in c.upper() or "ID" in c.upper() or "VERTICE" in c.upper()), columnas_txt[0])) if columnas_txt else 0
                    idx_este = columnas_txt.index(next((c for c in columnas_txt if "ESTE" in c.upper() or "X" == c.upper()), columnas_txt[1] if len(columnas_txt)>1 else 0)) if columnas_txt else 0
                    idx_norte = columnas_txt.index(next((c for c in columnas_txt if "NORTE" in c.upper() or "Y" == c.upper()), columnas_txt[2] if len(columnas_txt)>2 else 0)) if columnas_txt else 0
                    
                    c1, c2, c3 = st.columns(3)
                    with c1: col_pto = st.selectbox("Columna Vértice", columnas_txt, index=idx_pto)
                    with c2: col_este = st.selectbox("Columna Este (X)", columnas_txt, index=idx_este)
                    with c3: col_norte = st.selectbox("Columna Norte (Y)", columnas_txt, index=idx_norte)
                    
                    if st.button("Procesar e Inyectar Archivo", type="primary"):
                        nuevos_datos = []
                        for idx, row in df_cargado.iterrows():
                            nuevos_datos.append({
                                "Punto": str(row[col_pto]),
                                "Este": float(row[col_este]),
                                "Norte": float(row[col_norte]),
                                "Colindante": str(row.get("Colindante", "---")),
                                "Tipo de Lindero": str(row.get("Tipo de Lindero", "---")),
                                "Materialización": str(row.get("Materialización", "---")),
                                "Registro_Fotografico": False
                            })
                        
                        st.session_state.df_predios_campo = pd.DataFrame(nuevos_datos)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar el archivo. Verifique el formato. Detalle: {e}")
                    
        with col_up2:
            st.write("") 
            st.write("") 
            if st.button("Restaurar Datos de Ejemplo", use_container_width=True):
                st.session_state.df_predios_campo = df_plantilla_predios.copy()
                st.rerun()

    # -----------------------------------------------------------
    # MATRIZ INTERACTIVA (SIN EL 'KEY' PARA EVITAR CONFLICTOS)
    # -----------------------------------------------------------
    st.subheader("1. Vértices del Lindero")
    st.session_state.df_predios_campo = st.data_editor(
        st.session_state.df_predios_campo, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Este": st.column_config.NumberColumn(format="%.3f"),
            "Norte": st.column_config.NumberColumn(format="%.3f"),
            "Colindante": st.column_config.TextColumn("Colindante (Vecino)"),
            "Tipo de Lindero": st.column_config.TextColumn("Tipo de Lindero"),
            "Materialización": st.column_config.TextColumn("Materialización (Mojón)"),
            "Registro_Fotografico": st.column_config.CheckboxColumn("Registro Fotográfico")
        }
    )
    st.info("💡 **Consejo de seguridad:** Para evitar la pérdida de datos ante una recarga accidental de la página o fallos de internet, recuerda utilizar el botón **'Descargar Copia de Seguridad (.gp)'** periódicamente.")

    # -----------------------------------------------------------
    # MÓDULO DE FOTOS PREDIALES (EVIDENCIA EN TERRENO)
    # -----------------------------------------------------------
    estaciones_con_foto = st.session_state.df_predios_campo[st.session_state.df_predios_campo["Registro_Fotografico"] == True]["Punto"].unique()

    if len(estaciones_con_foto) > 0:
        st.markdown("---")
        st.header("Módulo Analítico: Captura de Evidencias en Terreno")
        tabs = st.tabs([f"Vértice {est}" for est in estaciones_con_foto])
        secuencia_fotos = [{"paso": 1, "sufijo": "Punto Central"}, {"paso": 2, "sufijo": "Visual Norte"}, {"paso": 3, "sufijo": "Visual Este"}, {"paso": 4, "sufijo": "Visual Sur"}, {"paso": 5, "sufijo": "Visual Oeste"}]

        for i, est in enumerate(estaciones_con_foto):
            with tabs[i]:
                estado_paso = f"paso_foto_predio_{est}"
                if estado_paso not in st.session_state: st.session_state[estado_paso] = 0
                paso_actual = st.session_state[estado_paso]
                if paso_actual < 5:
                    st.progress(paso_actual / 5.0)
                    foto = st.camera_input(f"Capturar evidencia: {secuencia_fotos[paso_actual]['sufijo']}", key=f"cam_predio_{est}_{paso_actual}")
                    if foto is not None:
                        carpeta = dir_fotos("Fotos_Predios", est)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        
                        # Extraer coordenadas GPS del vértice para quemarlas en la foto
                        row_est = st.session_state.df_predios_campo[st.session_state.df_predios_campo["Punto"] == est].iloc[0]
                        lat_stamp, lon_stamp = None, None
                        try:
                            lon_stamp, lat_stamp = trans_to_wgs.transform(float(row_est['Este']), float(row_est['Norte']))
                        except: pass

                        guardar_foto_estampada(
                            foto, os.path.join(carpeta, nombre), est,
                            secuencia_fotos[paso_actual]['sufijo'],
                            latitud=lat_stamp, longitud=lon_stamp,
                            proyecto=param_ficha("nombre_proyecto") or st.session_state.get("proyecto_actual"))
                        st.session_state[estado_paso] += 1
                        st.rerun()
                else: st.success("Capturas de inspección registradas en la base del sistema.")

    if st.button("Ejecutar Cálculo Predial", type="primary", use_container_width=True):
        try:
            df_linderos, metricas_predio = procesar_levantamiento_predial(st.session_state.df_predios_campo)
            st.session_state.df_cuadro_linderos = df_linderos
            st.session_state.met_predios = metricas_predio
            st.session_state.calc_predios = True
            st.success("Análisis topológico y cálculo de áreas ejecutado correctamente.")
        except Exception as e:
            st.error(f"Error de integridad en el polígono: {e}")

    if st.session_state.get('calc_predios'):
        met = st.session_state.met_predios
        df_linderos = st.session_state.df_cuadro_linderos

        st.markdown("---")
        st.header("2. Resultados del Levantamiento Predial")
        colA, colB, colC = st.columns(3)
        colA.metric("Área Total (m²)", f"{met['Area_m2']:,.3f} m²")
        colB.metric("Área Total (Hectáreas)", f"{met['Area_ha']:,.4f} ha")
        colC.metric("Perímetro del Predio", f"{met['Perimetro_m']:,.3f} m")

        st.subheader("Cuadro de Áreas y Linderos (Lineamientos IGAC)")
        st.dataframe(df_linderos, use_container_width=True)

        st.markdown("---")
        st.subheader(f"3. Geovisualización Espacial ({nombre_proyeccion})")
        
        opciones_mapa = {
            "ESRI Satélite (Alta Resolución)": {"tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", "attr": "Esri"},
            "Google Híbrido (Satélite + Vías)": {"tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "attr": "Google"},
            "OpenStreetMap (Catastro)": {"tiles": "OpenStreetMap", "attr": None}
        }
        tipo_mapa = st.selectbox("Capa Base Geoespacial:", list(opciones_mapa.keys()), key="mapa_predios")
        t_tiles = opciones_mapa[tipo_mapa]["tiles"]
        t_attr = opciones_mapa[tipo_mapa]["attr"]
        
        coordenadas_mapa, latitudes, longitudes = [], [], []
        
        for idx, row in df_linderos.iloc[:-1].iterrows():
            try:
                lon_wgs, lat_wgs = trans_to_wgs.transform(float(row['Este (m)']), float(row['Norte (m)']))
                coordenadas_mapa.append([lat_wgs, lon_wgs])
                latitudes.append(lat_wgs)
                longitudes.append(lon_wgs)
            except Exception:
                pass
                
        if latitudes and longitudes:
            centro_lat = sum(latitudes)/len(latitudes)
            centro_lon = sum(longitudes)/len(longitudes)
            
            if t_attr: mapa_predio = folium.Map(location=[centro_lat, centro_lon], zoom_start=18, max_zoom=21, tiles=t_tiles, attr=t_attr)
            else: mapa_predio = folium.Map(location=[centro_lat, centro_lon], zoom_start=18, max_zoom=21, tiles=t_tiles)
                
            folium.Polygon(locations=coordenadas_mapa, color="#FF8C00", weight=3, fill=True, fill_color="#FF8C00", fill_opacity=0.3).add_to(mapa_predio)
            
            for idx, row in df_linderos.iloc[:-1].iterrows():
                lon_wgs, lat_wgs = trans_to_wgs.transform(float(row['Este (m)']), float(row['Norte (m)']))
                folium.Marker(
                    location=[lat_wgs, lon_wgs], 
                    popup=f"<b>Vértice: {row['Vértice']}</b><br>E: {row['Este (m)']} m<br>N: {row['Norte (m)']} m", 
                    tooltip=row['Vértice'], 
                    icon=folium.Icon(color="red", icon="info-sign")
                ).add_to(mapa_predio)
            
            mapa_predio.fit_bounds([[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]])
            st_folium(mapa_predio, width=1100, height=550, key="folium_predios")
        
# -----------------------------------------------------------
        # 4. RENDERIZACIÓN DE PLANO PREDIAL CAD (IGAC)
        # -----------------------------------------------------------
        st.markdown("---")
        st.subheader("4. Planimetría del Predio (Arquitectura CAD)")
        
        # Inyección del selector de papel
        col_formato, col_vacia = st.columns([1, 1])
        with col_formato:
            formato_plano = st.selectbox(
                "Seleccione el Formato de Papel:", 
                [
                    "A4 (21 x 29.7 cm) - Carta", 
                    "A3 (29.7 x 42 cm) - Tabloide", 
                    "A2 (42 x 59.4 cm) - Medio Pliego", 
                    "A1 (59.4 x 84.1 cm) - Pliego", 
                    "A0 (84.1 x 118.9 cm) - Gran Formato"
                ],
                index=0,
                help="Aumente el formato si las etiquetas o el cuadro de coordenadas se amontonan."
            )

        try:
            # Se añade el parámetro formato_papel a la función
            fig_predio = generar_plano_predial(
                st.session_state.df_predios_campo, 
                st.session_state.df_cuadro_linderos, 
                st.session_state.met_predios,
                formato_papel=formato_plano
            )
            st.pyplot(fig_predio)
            
            # Exportar el Plano para el Usuario
            os.makedirs(dir_reportes(), exist_ok=True)
            ruta_export_predio = os.path.join(dir_reportes(), "Plano_Predial.png")
            fig_predio.savefig(ruta_export_predio, dpi=300, bbox_inches='tight')
            plt.close(fig_predio)
            
            with open(ruta_export_predio, "rb") as f:
                st.download_button(
                    label="Descargar Plano Predial y Cuadro de Áreas (.PNG Alta Resolución)",
                    data=f,
                    file_name=f"Plano_Predial_{st.session_state.get('proyecto_actual', 'Proyecto')}.png",
                    mime="image/png",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Falla en el motor de renderizado CAD Predial: {e}")

# -----------------------------------------------------------
        # 5. EXPORTACIÓN TÉCNICA (PDF, KML, DXF, SHP)
        # -----------------------------------------------------------
        st.markdown("---")
        with st.expander("Consolidación y Exportación Técnica (PDF / CAD / GIS)", expanded=True):
            st.markdown("Formatos soportados para plataformas paramétricas de terceros (Catastro, AutoCAD, Google Earth):")
            col_kml, col_dxf, col_shp, col_tex = st.columns(4)
            
            # Preparar el dataframe temporal engañando a las variables para la exportación estandarizada
            df_export_predio = st.session_state.df_predios_campo.copy()
            df_export_predio = df_export_predio.rename(columns={"Punto": "Estacionado", "Este": "X_Estacion", "Norte": "Y_Estacion"})
            df_export_predio['Z_Estacion'] = 0.0
            
            trans_to_wgs = motor_igac.transformadores_inversos[nombre_proyeccion]
            data_kml = generar_kml(df_export_predio, trans_to_wgs)
            data_dxf = generar_dxf(df_export_predio)
            data_shp = generar_shp_zip(df_export_predio, nombre_proyeccion)
            
            if ficha_incompleta():
                st.warning("Ficha Técnica incompleta: " + ", ".join(ficha_incompleta()) + ". El informe saldrá con esos campos en blanco.")
                
            if st.button("Compilar Documento Estructural de Catastro", type="primary", use_container_width=True, key="btn_predios"):
                with st.spinner("Procesando linderos, fotografías e inviniendo motor LaTeX..."):
                    dir_fotos_proy = dir_fotos("Fotos_Predios")
                    fotos_tomadas = sorted(glob.glob(os.path.join(dir_fotos_proy, "*", "*.jpg")))
                    p_act = st.session_state.get('proyecto_actual') or 'Predio'
                    salida = dir_reportes()
                    metadatos = construir_metadatos(
                        sistema_referencia=nombre_proyeccion,
                        huella=huella_datos(st.session_state.df_cuadro_linderos))
                    
                    # Firma archivos para evitar caché de planos viejos
                    firma = firma_archivos([ruta_export_predio] + list(fotos_tomadas))
                    
                    pdf_bytes, data_tex, debug_msg = cachear_pdf_predios(
                        st.session_state.df_cuadro_linderos, met, p_act, ruta_export_predio,
                        fotos_tomadas, salida, firma, metadatos, construir_equipo())
                    
                    st.session_state.predios_pdf_bytes = pdf_bytes
                    st.session_state.predios_tex_code = data_tex
                    st.session_state.predios_debug_msg = debug_msg

            if st.session_state.get('predios_pdf_bytes'):
                st.success("Informe Catastral ensamblado exitosamente.")
                b64_pdf = base64.b64encode(st.session_state.predios_pdf_bytes).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
            elif st.session_state.get('predios_tex_code') and not st.session_state.get('predios_pdf_bytes'):
                st.warning(f"Error de Integración: Ausencia del motor local TeX Live. Diagnóstico:\n{st.session_state.get('predios_debug_msg')}")
            
            with col_kml: st.download_button(label="Linderos .KML (Google Earth)", data=data_kml, file_name=f"{st.session_state.get('proyecto_actual') or 'Predio'}_Linderos.kml", mime="application/vnd.google-earth.kml+xml", use_container_width=True)
            with col_dxf: st.download_button(label="Plano Predial .DXF (AutoCAD)", data=data_dxf, file_name=f"{st.session_state.get('proyecto_actual') or 'Predio'}_CAD.dxf", mime="application/dxf", use_container_width=True)
            with col_shp: st.download_button(label="Base Espacial .ZIP (Shapefile)", data=data_shp, file_name=f"{st.session_state.get('proyecto_actual') or 'Predio'}_GIS.zip", mime="application/zip", use_container_width=True)
            with col_tex: 
                if st.session_state.get('predios_pdf_bytes'):
                    st.download_button(label="Descargar Documento Final PDF", data=st.session_state['predios_pdf_bytes'], file_name=f"Reporte_Predial_{st.session_state.get('proyecto_actual') or 'Predio'}.pdf", mime="application/pdf", use_container_width=True)
                elif st.session_state.get('predios_tex_code'):
                    st.download_button(label="Descargar Código Base (.TEX)", data=st.session_state['predios_tex_code'], file_name=f"Reporte_Predial_{st.session_state.get('proyecto_actual') or 'Predio'}.tex", mime="text/plain", use_container_width=True)
            
# ===================================================================
# MÓDULO DE NUBE DE PUNTOS (GIS MULTI-ARCHIVO INDEPENDIENTE)
# ===================================================================
elif st.session_state.modo_app == "Nube_Puntos":
    renderizar_banner_proyecto()
    boton_atras()
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
                col_e = c2.selectbox("Coordenada X", cols, index=idx_auto["e"], key=f"e_{n_arch}")
                col_n = c3.selectbox("Coordenada Y", cols, index=idx_auto["n"], key=f"n_{n_arch}")
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
                                ruta_dtm = os.path.join(dir_reportes(), "dtm_overlay.png")
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
    boton_atras()
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
                # 'Volumen Neto (m³)' que devuelve motor_volumenes YA es
                # acumulado (Vol. Acumulado Corte - Vol. Acumulado Relleno).
                # Aplicarle .cumsum() encima acumulaba dos veces y la curva
                # masa terminaba en 942 m3 donde el valor real era 328,8.
                v_neto_tramo = (res_df['Vol. Corte (m³)'].fillna(0)
                                - res_df['Vol. Relleno (m³)'].fillna(0))
                res_df['Volumen Neto Tramo (m³)'] = v_neto_tramo.round(3)
                res_df['Masa Acumulada (m³)'] = v_neto_tramo.cumsum().round(3)

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
            if ficha_incompleta():
                st.warning("Ficha Técnica incompleta: " + ", ".join(ficha_incompleta())
                           + ". El informe saldrá con esos campos en blanco.")

            if st.button("Compilar Documento Estructural de Ingeniería", type="primary", use_container_width=True, key="btn_vol"):
                with st.spinner("Procesando dependencias gráficas y compilando protocolo LaTeX..."):
                    p_act = st.session_state.get('proyecto_actual') or "Proyecto"
                    salida = dir_reportes()
                    metadatos = construir_metadatos(
                        huella=huella_datos(df_calculado, df_vol_final))
                    params_vol = {
                        "material": param_ficha("material_volumenes"),
                        "capacidad_volqueta": param_ficha("capacidad_volqueta"),
                        "acarreo_libre": param_ficha("acarreo_libre"),
                    }

                    pdf_bytes, tex_vol, debug_msg = cachear_pdf_volumenes(
                        df_calculado, df_vol_final, met, p_act, False,
                        salida, metadatos, construir_equipo(), params_vol)

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
    boton_atras()

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
        st.info("💡 **Consejo de seguridad:** Para evitar la pérdida de datos ante una recarga accidental de la página o fallos de internet, recuerda utilizar el botón **'Descargar Copia de Seguridad (.gp)'** periódicamente.")
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
        st.info("💡 **Consejo de seguridad:** Para evitar la pérdida de datos ante una recarga accidental de la página o fallos de internet, recuerda utilizar el botón **'Descargar Copia de Seguridad (.gp)'** periódicamente.")

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
                        carpeta = dir_fotos("Fotos_Nivelacion", est)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        # Estampa estación, orientación, fecha y proyecto sobre la
                        # imagen. Si falla, guarda la foto sin estampar.
                        guardar_foto_estampada(
                            foto, os.path.join(carpeta, nombre), est,
                            secuencia_fotos[paso_actual]['sufijo'],
                            proyecto=param_ficha("nombre_proyecto")
                                     or st.session_state.get("proyecto_actual"))
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

        # Aquí había una segunda definición de cachear_pdf_altimetria que
        # tapaba a la global. Eliminada: se usa la del encabezado.
        st.markdown("---")
        with st.expander("Consolidación y Exportación Técnica (PDF / Código LaTeX)", expanded=True):
            st.info("El motor LaTeX estructurará el informe técnico formal incluyendo la proyección altimétrica compensada.")

            if ficha_incompleta():
                st.warning("Ficha Técnica incompleta: " + ", ".join(ficha_incompleta())
                           + ". El informe saldrá con esos campos en blanco.")

            if st.button("Compilar Documento Estructural de Ingeniería", type="primary", use_container_width=True, key="btn_niv"):
                with st.spinner("Procesando componentes espaciales e inviniendo motor LaTeX..."):
                    dir_fotos_proy = dir_fotos("Fotos_Nivelacion")
                    fotos_tomadas = sorted(glob.glob(os.path.join(dir_fotos_proy, "*", "*.jpg")))
                    tipo_niv = "Nivelación Geométrica Cerrada" if st.session_state.modo_app == "Niv_Cerrada" else "Nivelación Geométrica de Abierta Lineal"
                    p_act = st.session_state.get('proyecto_actual') or 'Altimetria'
                    salida = dir_reportes()
                    metadatos = construir_metadatos(huella=huella_datos(df_calc))
                    params_niv = {"longitud_km": param_ficha("longitud_nivelada_km"),
                                  "orden": param_ficha("orden_nivelacion")}
                    bm_partida = {"codigo": param_ficha("punto_amarre"),
                                  "cota": f"{float(cota_datum):.3f}",
                                  "entidad": param_ficha("fuente_amarre")}

                    pdf_bytes, tex_niv, debug_msg = cachear_pdf_altimetria(
                        df_calc, met, p_act, tipo_niv, fotos_tomadas,
                        salida, firma_archivos(fotos_tomadas),
                        metadatos, construir_equipo(), params_niv, bm_partida)

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
    boton_atras()

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
        st.info("💡 **Consejo de seguridad:** Para evitar la pérdida de datos ante una recarga accidental de la página o fallos de internet, recuerda utilizar el botón **'Descargar Copia de Seguridad (.gp)'** periódicamente.")

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
        st.info("💡 **Consejo de seguridad:** Para evitar la pérdida de datos ante una recarga accidental de la página o fallos de internet, recuerda utilizar el botón **'Descargar Copia de Seguridad (.gp)'** periódicamente.")

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
                        carpeta = dir_fotos("Fotos_Cartera", est)
                        nombre = f"{est}_{secuencia_fotos[paso_actual]['paso']}_{secuencia_fotos[paso_actual]['sufijo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                        # Estampa estación, orientación, fecha y proyecto sobre la
                        # imagen. Si falla, guarda la foto sin estampar.
                        guardar_foto_estampada(
                            foto, os.path.join(carpeta, nombre), est,
                            secuencia_fotos[paso_actual]['sufijo'],
                            proyecto=param_ficha("nombre_proyecto")
                                     or st.session_state.get("proyecto_actual"))
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
            ruta_plano_export = os.path.join(dir_reportes(), "Plano_Exportado.png")
            fig_plano.savefig(ruta_plano_export, dpi=300, bbox_inches='tight')
            # Sin close() cada rerun de esta pantalla deja una figura viva
            plt.close(fig_plano)
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

            if ficha_incompleta():
                st.warning("Ficha Técnica incompleta: " + ", ".join(ficha_incompleta())
                           + ". El informe saldrá con esos campos en blanco.")

            if st.button("Compilar Documento Estructural de Ingeniería", type="primary", use_container_width=True, key="btn_poli"):
                with st.spinner("Procesando componentes espaciales e inviniendo motor LaTeX..."):
                    dir_fotos_proy = dir_fotos("Fotos_Cartera")
                    fotos_tomadas = sorted(glob.glob(os.path.join(dir_fotos_proy, "*", "*.jpg")))
                    p_act = st.session_state.get('proyecto_actual') or 'Poli'
                    salida = dir_reportes()
                    metadatos = construir_metadatos(
                        sistema_referencia=nombre_proyeccion,
                        huella=huella_datos(df_campo, df_ajuste))
                    params_poli = {
                        "altura_elipsoidal": param_ficha("altura_elipsoidal"),
                        "precision_exigida": param_ficha("precision_exigida"),
                        "factor_tolerancia": param_ficha("factor_tolerancia"),
                    }
                    # La firma incluye plano y fotos: si cambian, la caché se
                    # invalida y no se reutiliza un PDF con el plano viejo.
                    firma = firma_archivos([ruta_plano_export] + list(fotos_tomadas))

                    pdf_bytes, data_tex, debug_msg = cachear_pdf_poli(
                        df_campo, df_ajuste, met, p_act, ruta_plano_export,
                        fotos_tomadas, st.session_state.modo_app,
                        salida, firma, metadatos, construir_equipo(), params_poli,
                        coords_desde_ajuste(df_ajuste), este_medio(df_ajuste),
                        lados_para_memoria(met, df_campo, df_ajuste,
                                           st.session_state.modo_app))

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
    boton_atras()
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
            c_info.write(f" {n_arch} - ({len(st.session_state.nubes_vias_guardadas[n_arch])} registros)")
            if c_btn.button("Remover", key=f"del_vias_{n_arch}"):
                del st.session_state.nubes_vias_guardadas[n_arch]
                st.rerun()

        for n_arch, df_bruto in st.session_state.nubes_vias_guardadas.items():
            with st.expander(f"Asignación paramétrica: {n_arch}", expanded=False):
                st.dataframe(df_bruto.head(5), use_container_width=True)
                cols = ["Ninguna"] + list(df_bruto.columns)
                idx_auto = detectar_indices_columnas(list(df_bruto.columns))
                c1, c2, c3 = st.columns(3)
                col_e = c1.selectbox("Coordenada X", cols, index=idx_auto["e"], key=f"v_e_{n_arch}")
                col_n = c2.selectbox("Coordenada Y", cols, index=idx_auto["n"], key=f"v_n_{n_arch}")
                col_z = c3.selectbox("Elevación (Cota Z)", cols, index=idx_auto["z"], key=f"v_z_{n_arch}")
                mapeo_dtm[n_arch] = {"e": col_e, "n": col_n, "z": col_z}

        # El mapeo se conserva en sesión para reutilizarlo en la extracción del perfil
        st.session_state.vias_mapeo_dtm = mapeo_dtm

        if st.button("Generar Curvas de Nivel (TIN)", type="primary", use_container_width=True):
            dfs_validos = []
            for n_arch, map_val in mapeo_dtm.items():
                if map_val["e"] != "Ninguna" and map_val["n"] != "Ninguna" and map_val["z"] != "Ninguna":
                    df_limpio = asignar_columnas(st.session_state.nubes_vias_guardadas[n_arch], None, map_val["e"], map_val["n"], map_val["z"], None)
                    dfs_validos.append(df_limpio)

            if dfs_validos:
                with st.spinner("Triangulando modelo digital de terreno..."):
                    try:
                        os.makedirs(dir_reportes(), exist_ok=True)
                        df_master = pd.concat(dfs_validos, ignore_index=True)
                        ruta_dtm_vias = os.path.join(dir_reportes(), "dtm_vias_overlay.png")
                        bounds_vias = generar_dtm_curvas(df_master, ruta_dtm_vias, trans_to_wgs)

                        # Se guarda la nube maestra YA MAPEADA para que la extracción
                        # del perfil use exactamente las mismas columnas que el TIN.
                        st.session_state.vias_df_master_dtm = df_master
                        st.session_state.vias_dtm_bounds = bounds_vias
                        st.session_state.vias_dtm_ruta = ruta_dtm_vias

                        # Al crear el TIN se fuerza el encuadre extendido sobre él
                        st.session_state.force_dtm_zoom = True
                        st.session_state.vias_vista = None

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
            if c_lupa.button(" Centrar vista en el Modelo (TIN)", use_container_width=True):
                st.session_state.force_dtm_zoom = True
                st.rerun()
            # Ocultar el raster acelera muchísimo el mapa mientras se marcan los PI:
            # el PNG del TIN se incrusta en base64 dentro del HTML en cada recarga.
            ver_tin = c_ver.checkbox("Ver TIN", value=True, key="chk_ver_tin")
            opacidad_tin = c_opac.slider("Opacidad TIN", 0.0, 1.0, 0.65, 0.05, key="sld_opac_tin")
        else:
            ver_tin, opacidad_tin = True, 0.65

        # VISTA CONGELADA
        # CAUSA DEL REMONTADO: 'location' se alimentaba del centro devuelto por el
        # propio mapa, así que cambiaba en cada recarga; streamlit-folium detectaba
        # un mapa distinto y lo volvía a montar (de ahí el salto al primer punto).
        # Ahora la vista inicial se fija UNA vez en 'vias_vista' y sólo se recalcula
        # de forma deliberada: al generar el TIN o al pulsar la lupa. Entre recargas
        # el mapa es idéntico, el componente no se remonta y el encuadre y los
        # trazos del usuario se conservan en el navegador.
        if st.session_state.get('force_dtm_zoom') and st.session_state.get('vias_dtm_bounds'):
            b = st.session_state.vias_dtm_bounds
            st.session_state.vias_vista = {
                "centro": [(b[0][0] + b[1][0]) / 2.0, (b[0][1] + b[1][1]) / 2.0],
                "zoom": 16,
                "fit": b          # encuadre extendido sobre la extensión del TIN
            }
            st.session_state.force_dtm_zoom = False

        if not st.session_state.get('vias_vista'):
            if st.session_state.get('vias_dtm_bounds'):
                b = st.session_state.vias_dtm_bounds
                st.session_state.vias_vista = {
                    "centro": [(b[0][0] + b[1][0]) / 2.0, (b[0][1] + b[1][1]) / 2.0],
                    "zoom": 16, "fit": b
                }
            elif pis_validos:
                lon_wgs, lat_wgs = trans_to_wgs.transform(float(pis_validos[0]['Este']),
                                                          float(pis_validos[0]['Norte']))
                st.session_state.vias_vista = {"centro": [lat_wgs, lon_wgs], "zoom": 17, "fit": None}
            else:
                st.session_state.vias_vista = {"centro": [4.6377, -74.1234], "zoom": 15, "fit": None}

        centro_mapa = st.session_state.vias_vista["centro"]
        zoom_mapa = st.session_state.vias_vista["zoom"]

        mapa_diseno = folium.Map(location=centro_mapa, zoom_start=zoom_mapa, max_zoom=22, tiles=t_tiles, attr=t_attr)

        # Plugins de Folium
        from folium.plugins import MeasureControl, Draw, Fullscreen
        mapa_diseno.add_child(MeasureControl(position='topleft', primary_length_unit='meters', secondary_length_unit='miles', primary_area_unit='sqmeters'))

        # Draw: SÓLO polilínea. La línea se va dibujando en el navegador clic a clic,
        # sin recargar la página, y cada vértice se convierte luego en un PI.
        opciones_dibujo = {'polyline': True, 'polygon': False, 'rectangle': False,
                           'circle': False, 'marker': False, 'circlemarker': False}
        mapa_diseno.add_child(Draw(export=False, position='topleft', draw_options=opciones_dibujo))

        mapa_diseno.add_child(Fullscreen(position='topright'))

        # Grupos de capas
        fg_dtm = folium.FeatureGroup(name="Superficie Terreno (TIN)", show=True)
        fg_pis = folium.FeatureGroup(name="Vértices Geométricos (PIs)", show=True)
        fg_eje = folium.FeatureGroup(name="Eje Vial Proyectado", show=True)
        fg_rotulos = folium.FeatureGroup(name="Rótulos de Vértices", show=True)

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

            # Encuadre extendido sobre el TIN. Se aplica SIEMPRE que la vista lo
            # tenga registrado, no una sola vez: así el mapa generado es idéntico
            # entre recargas y el componente no se remonta. Leaflet sólo lo ejecuta
            # al montar, de modo que no interfiere con el zoom manual del usuario.
            if st.session_state.vias_vista.get("fit"):
                mapa_diseno.fit_bounds(st.session_state.vias_vista["fit"])

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
                lbl = (f"<b>{pi['PI']}</b><br>Este: {float(pi['Este']):.3f} m<br>"
                       f"Norte: {float(pi['Norte']):.3f} m<br>R: {radio_txt} m<br>Z: {cota_txt} m")
                folium.Marker([lat, lon], popup=folium.Popup(lbl, max_width=260), tooltip=pi['PI'],
                              icon=folium.Icon(color="orange", icon="info-sign")).add_to(fg_pis)

                # Etiqueta permanente con el nombre del vértice (no requiere pasar el
                # cursor por encima). Se coloca en su propia capa para poder ocultarla.
                folium.Marker(
                    [lat, lon],
                    icon=folium.DivIcon(
                        icon_size=(0, 0),
                        icon_anchor=(-14, 10),
                        html=('<div style="display:inline-block;white-space:nowrap;'
                              'background:#FFFFFF;border:2px solid #FF8C00;border-radius:4px;'
                              'padding:1px 6px;font-size:12px;font-weight:700;color:#0D47A1;'
                              'font-family:Arial,Helvetica,sans-serif;'
                              f'box-shadow:0 1px 3px rgba(0,0,0,0.35);">{pi["PI"]}</div>')
                    )
                ).add_to(fg_rotulos)

            # Trazado del eje tal como se marcó en la polilínea: se mantiene visible
            # después de finalizar, en trazo continuo y con los vértices numerados.
            if len(lats_pis) > 1:
                folium.PolyLine(list(zip(lats_pis, lons_pis)), color="#FF8C00", weight=4,
                                opacity=0.95, tooltip="Trazado de vértices (poligonal PI-PI)").add_to(fg_pis)

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
        fg_rotulos.add_to(mapa_diseno)
        folium.LayerControl(collapsed=True, position='topright').add_to(mapa_diseno)


        # La clave incluye un testigo: al incrementarlo, Streamlit crea un componente
        # NUEVO y con él una capa de dibujo vacía. Es la única forma de borrar de
        # verdad la polilínea, que vive en el navegador y no en el servidor.
        nonce_mapa = st.session_state.get('vias_map_nonce', 0)
        map_data = st_folium(mapa_diseno, width=1100, height=600,
                             key=f"st_folium_vias_{nonce_mapa}",
                             returned_objects=["all_drawings"])

        # TRAZADO CONTINUO
        # all_drawings refleja el estado ACTUAL de la capa de dibujo, así que se lee
        # directamente: si el usuario edita o borra vértices con las herramientas del
        # mapa, el conteo se actualiza solo. (Acumularlos en sesión impedía borrarlos.)
        dibujos = (map_data or {}).get("all_drawings") or []
        puntos_dibujados = []
        for d in dibujos:
            if not isinstance(d, dict):
                continue
            geom = d.get("geometry", {}) or {}
            tipo = geom.get("type")
            if tipo == "LineString":
                # Cada vértice de la polilínea es un PI, en el orden trazado
                puntos_dibujados.extend(geom.get("coordinates", []))
            elif tipo == "Point":
                puntos_dibujados.append(geom["coordinates"])

        c_fin, c_desc, c_info = st.columns([1.2, 1, 2])
        if c_fin.button(f"Finalizar trazado ({len(puntos_dibujados)} pts)",
                        type="primary", use_container_width=True,
                        disabled=(len(puntos_dibujados) == 0),
                        help="Carga de una sola vez todos los vértices de la polilínea."):
            nuevos = []
            n_previos = len(st.session_state.pis_vias)
            for coord in puntos_dibujados:
                lon, lat = float(coord[0]), float(coord[1])
                este, norte = trans_to_local.transform(lon, lat)
                nuevos.append({
                    "PI": f"PI-{n_previos + len(nuevos) + 1}",
                    "Este": round(este, 3),
                    "Norte": round(norte, 3),
                    "Elevacion": 0.000,
                    "Radio": 50.0
                })
            st.session_state.pis_vias.extend(nuevos)
            st.session_state.vias_trazado_cargado = len(nuevos)

            # Al remontar el componente la vista se reinicia; se reencuadra sobre el
            # eje recién trazado para que no salte a la posición inicial.
            lats = [float(c[1]) for c in puntos_dibujados]
            lons = [float(c[0]) for c in puntos_dibujados]
            if len(puntos_dibujados) >= 2 and (max(lats) > min(lats) or max(lons) > min(lons)):
                st.session_state.vias_vista = {
                    "centro": [(min(lats) + max(lats)) / 2.0, (min(lons) + max(lons)) / 2.0],
                    "zoom": 17,
                    "fit": [[min(lats), min(lons)], [max(lats), max(lons)]]
                }
            else:
                st.session_state.vias_vista = {"centro": [lats[0], lons[0]], "zoom": 18, "fit": None}

            # Capa de dibujo limpia: el eje pasa a dibujarlo la aplicación
            st.session_state.vias_map_nonce = nonce_mapa + 1
            st.rerun()

        if c_desc.button("Borrar trazado", use_container_width=True,
                         disabled=(len(puntos_dibujados) == 0),
                         help="Elimina del mapa la polilínea aún no cargada."):
            st.session_state.vias_map_nonce = nonce_mapa + 1
            st.rerun()

        if puntos_dibujados:
            c_info.info(f"{len(puntos_dibujados)} vértice(s) trazados. Continúe la polilínea o "
                        f"pulse Finalizar trazado para cargarlos todos de una vez.")
        else:
            c_info.caption("Trace el eje con la herramienta de POLILÍNEA (barra superior izquierda): cada clic añade "
                           "un vértice y la línea se dibuja sola. Doble clic para cerrar el trazado.")

        if st.session_state.get('vias_trazado_cargado'):
            st.success(f"{st.session_state.vias_trazado_cargado} vértice(s) incorporados a la matriz.")
            st.session_state.vias_trazado_cargado = 0

    with col_datos:
        st.markdown("---")
        st.markdown("#### Matriz de Vértices Geométricos (PI)")
        st.caption("Para desplazar un vértice analíticamente o ajustar su elevación, edite la matriz a continuación.")
        c_purga, c_vacio = st.columns([1, 3])
        if c_purga.button("Purgar Vértices Geométricos", type="secondary", use_container_width=True):
            st.session_state.pis_vias = []
            st.session_state.vias_map_nonce = st.session_state.get('vias_map_nonce', 0) + 1
            st.session_state.vias_vista = None
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

            # COHERENCIA DE PENDIENTES:
            # Antes esta columna usaba la distancia RECTA entre PIs, mientras que la
            # Tabla Dinámica de Rasante Vertical mide sobre el EJE (las curvas acortan
            # el recorrido respecto de la poligonal PI-PI). Por eso ambas tablas
            # mostraban valores distintos para el mismo tramo.
            # Ahora las dos se alimentan del mismo motor: la longitud y la pendiente
            # provienen del abscisado real del eje.
            longitudes, pendientes, base_eje = [], [], False
            try:
                _, _, _df_v_prev = procesar_alineamiento_horizontal(df_pis, v_diseno=v_dis)
                if len(_df_v_prev) == len(df_pis):
                    longitudes = _df_v_prev['Longitud Tramo (m)'].tolist()
                    pendientes = _df_v_prev['Pendiente Salida (%)'].tolist()
                    base_eje = True
            except Exception:
                base_eje = False

            if not base_eje:
                # Respaldo geométrico mientras el trazado no sea procesable
                # (radio excesivo, vértices incompletos, menos de 2 PIs...).
                longitudes, pendientes = [], []
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
                            longitudes.append(round(dist, 3))
                            pendientes.append(round(pend, 3))
                        except Exception:
                            longitudes.append(0.0); pendientes.append(0.0)
                    else:
                        longitudes.append(0.0); pendientes.append(0.0)

            df_pis['Longitud Tramo (m)'] = longitudes
            df_pis['Pendiente Salida (%)'] = pendientes

            df_pis_editado = st.data_editor(
                df_pis, 
                num_rows="dynamic", 
                use_container_width=True,
                disabled=["PI", "Longitud Tramo (m)", "Pendiente Salida (%)"], 
                key="editor_pis_vias",
                column_config={
                    "Este": st.column_config.NumberColumn(format="%.3f"),
                    "Norte": st.column_config.NumberColumn(format="%.3f"),
                    "Elevacion": st.column_config.NumberColumn("Cota (Z)", format="%.3f"),
                    "Radio": st.column_config.NumberColumn(format="%.3f"),
                    "Longitud Tramo (m)": st.column_config.NumberColumn(format="%.3f"),
                    "Pendiente Salida (%)": st.column_config.NumberColumn(format="%.3f")
                }
            )

            if base_eje:
                st.caption("Longitud y pendiente medidas sobre el eje (incluyen el acortamiento por curvas): coinciden con la Tabla Dinámica de Rasante Vertical.")
            else:
                st.caption("Valores provisionales sobre la poligonal PI-PI: el trazado aún no es procesable. Se ajustarán al eje real al procesar la geometría.")

            df_to_save = df_pis_editado.drop(columns=['Longitud Tramo (m)', 'Pendiente Salida (%)',
                                                      'Dist. Sig (m)', 'Pend. Sig (%)'], errors='ignore')
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
            l_tr = float(df_v_val.iloc[i]['Longitud Tramo (m)'])
            tramo = (f"Tramo {i+1} · {df_v_val.iloc[i]['Vértice PIV']}  "
                     f"{df_v_val.iloc[i+1]['Vértice PIV']} (L = {l_tr:.3f} m)")
            if abs(m) > max_slope:
                st.error(f"{tramo}: pendiente de {m:.3f}% excede el máximo permitido ({max_slope}%).")
            elif abs(m) < min_slope:
                st.warning(f"{tramo}: pendiente de {m:.3f}% no cumple el mínimo para drenaje longitudinal ({min_slope}%).")
            else:
                st.success(f"{tramo}: pendiente de {m:.3f}% conforme a INVIAS.")

        st.caption("Cada pendiente corresponde al tramo que **sale** del primer vértice indicado. "
                   "En el cuadro de curvas, la columna «Pend. Entrada (%)» de un vértice es la pendiente "
                   "del tramo anterior y la columna «Pend. Salida (%)» es esta misma.")

        st.markdown("**Tabla Dinámica de Rasante Vertical (PIVs)**")
        df_mostrar_v = st.session_state.vias_df_vertical.drop(columns=['Abscisa'], errors='ignore')
        st.dataframe(df_mostrar_v.style.format({
            "Elevación (Z)": "{:.3f}",
            "Pendiente Entrada (%)": "{:.3f}",
            "Pendiente Salida (%)": "{:.3f}",
            "Longitud Tramo (m)": "{:.3f}"
        }), use_container_width=True)

        # -------------------------------------------------------------
        # CURVAS VERTICALES PARABÓLICAS (INVIAS 2008, capítulo 4)
        # -------------------------------------------------------------
        st.markdown("#### Curvas Verticales Parabólicas")
        st.caption("Los tramos de rasante se enlazan con parábolas simétricas cuando la diferencia "
                   "algebraica de pendientes supera el umbral normativo. K = L / |A|.")

        col_cv1, col_cv2, col_cv3 = st.columns(3)
        tipo_sup = col_cv1.selectbox("Tipo de superficie", ["Pavimentada (|A| > 1%)",
                                                            "No pavimentada (|A| > 2%)"],
                                     key="sup_via")
        pavimentada = tipo_sup.startswith("Pavimentada")
        redondeo_lv = col_cv2.selectbox("Redondeo de L (m)", [1.0, 5.0, 10.0, 20.0],
                                        index=2, key="red_via",
                                        help="La longitud mínima normativa se redondea hacia arriba a este múltiplo.")
        dp_ref = distancia_visibilidad_parada(v_dis)
        col_cv3.metric("Distancia de visibilidad de parada", f"{dp_ref:.2f} m",
                       help="Valor tabulado del Manual para la velocidad de diseño.")

        df_cv = calcular_curvas_verticales(
            st.session_state.vias_df_vertical, v_diseno=v_dis,
            pavimentada=pavimentada, redondeo=redondeo_lv,
            longitudes_adoptadas=st.session_state.get('vias_lv_manual', {}))

        if df_cv is not None and not df_cv.empty:
            cols_vista = ["Vértice PIV", "Tipo", "A (%)", "L seguridad (m)", "L operación (m)",
                          "L adoptada (m)", "K adoptado", "Abscisa PCV", "Abscisa PTV",
                          "Externa E (m)", "Cumple drenaje"]
            df_edit_cv = df_cv[cols_vista].copy()

            st.caption("Puede imponer una longitud mayor en «L adoptada (m)»; el resto de columnas se recalcula.")
            df_cv_editado = st.data_editor(
                df_edit_cv, use_container_width=True, key="editor_cv_vias",
                disabled=[c for c in cols_vista if c != "L adoptada (m)"],
                column_config={
                    "A (%)": st.column_config.NumberColumn(format="%.3f"),
                    "L seguridad (m)": st.column_config.NumberColumn(format="%.3f"),
                    "L operación (m)": st.column_config.NumberColumn(format="%.3f"),
                    "L adoptada (m)": st.column_config.NumberColumn(format="%.3f", min_value=0.0),
                    "K adoptado": st.column_config.NumberColumn(format="%.3f"),
                    "Externa E (m)": st.column_config.NumberColumn(format="%.3f"),
                })

            # Se guardan sólo las longitudes que el usuario modificó
            nuevas_lv = {}
            for _, fila in df_cv_editado.iterrows():
                original = df_cv[df_cv["Vértice PIV"] == fila["Vértice PIV"]]
                if original.empty:
                    continue
                l_ori = float(original.iloc[0]["L adoptada (m)"])
                l_new = float(fila["L adoptada (m)"] or 0.0)
                if abs(l_new - l_ori) > 1e-6:
                    nuevas_lv[fila["Vértice PIV"]] = l_new
            if nuevas_lv != {k: v for k, v in st.session_state.get('vias_lv_manual', {}).items()
                             if k in df_cv["Vértice PIV"].tolist()}:
                if nuevas_lv:
                    st.session_state.vias_lv_manual = {
                        **st.session_state.get('vias_lv_manual', {}), **nuevas_lv}
                    st.rerun()

            if st.session_state.get('vias_lv_manual'):
                if st.button("Restablecer longitudes normativas", key="reset_lv"):
                    st.session_state.vias_lv_manual = {}
                    st.rerun()

            st.session_state.vias_df_curvas_v = df_cv

            # Dictámenes por curva
            for _, r in df_cv.iterrows():
                if r["Tipo"] == "Sin curva":
                    st.info(f"{r['Vértice PIV']}: {r['Observación']}")
                elif ("No cumple" in r["Observación"] or "recortada" in r["Observación"]
                      or r["Cumple drenaje"] == "NO"):
                    st.error(f"{r['Vértice PIV']} ({r['Tipo']}, A = {r['A (%)']:.3f}%): {r['Observación']}")
                else:
                    st.success(f"{r['Vértice PIV']} ({r['Tipo']}, A = {r['A (%)']:.3f}%): "
                               f"L = {r['L adoptada (m)']:.3f} m, K = {r['K adoptado']:.3f}. {r['Observación']}")
        else:
            st.session_state.vias_df_curvas_v = None
            st.info("La rasante no tiene vértices intermedios: no se requieren curvas verticales.")
        st.markdown("#### Parámetros de Extracción y Sección Estructural")
        col_v3, col_v4, col_v5, col_v6, col_v7 = st.columns(5)
        intervalo_abs = col_v3.number_input("Intervalo de Abscisado (m)", value=10.0, min_value=1.0, format="%.1f")
        ancho_izq = col_v4.number_input("Carril Izquierdo (m)", value=3.6, format="%.3f")
        ancho_der = col_v5.number_input("Carril Derecho (m)", value=3.6, format="%.3f")
        bom_izq = col_v6.number_input("Bombeo Izquierdo (%)", value=-2.0, format="%.3f")
        bom_der = col_v7.number_input("Bombeo Derecho (%)", value=-2.0, format="%.3f")

        col_est1, col_est2, col_est3 = st.columns(3)
        esp_pav_via = col_est1.number_input("Espesor Pavimento (m)", value=0.10, step=0.05, format="%.2f", key="p_via")
        esp_base_via = col_est2.number_input("Espesor Base (m)", value=0.20, step=0.05, format="%.2f", key="b_via")
        esp_sub_via = col_est3.number_input("Espesor Subbase (m)", value=0.30, step=0.05, format="%.2f", key="s_via")

        st.markdown("#### Transición del Peralte (INVIAS 2008, numeral 3.2)")
        st.caption("L = a · bw · (ef − ei) / Δs, con a = w·n y Δs tomada de la tabla de pendiente relativa máxima de la rampa de peraltes.")
        col_t1, col_t2, col_t3 = st.columns(3)
        w_carril = col_t1.number_input("Ancho de carril w (m)", value=3.65, step=0.05, min_value=2.5, max_value=4.5, format="%.2f", key="w_via",
                                       help="Ancho del carril usado para el cálculo de la rampa de peraltes.")
        n_giran = col_t2.selectbox("Carriles que giran (n)", [1.0, 1.5, 2.0, 2.5, 3.0, 3.5], index=0, key="ngiro_via",
                                   help="Para calzada de dos carriles con giro alrededor del eje, n = 1.")
        reparto = col_t3.slider("Reparto de L en recta (%)", 50, 100, 70, 5, key="rep_via",
                                help="Porcentaje de la longitud de transición desarrollado antes del PC. El manual usa 70%.") / 100.0
        st.session_state.vias_w_carril = w_carril
        st.session_state.vias_n_giran = n_giran

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

                    # RASANTE CON ACUERDOS VERTICALES: entre PCV y PTV la cota de
                    # diseño la da la parábola, no la recta que une los PIV. Sin esto
                    # el perfil conservaría el vértice anguloso y el cubicaje quedaría
                    # sobrestimado en las convexas y subestimado en las cóncavas.
                    df_vert = st.session_state.vias_df_vertical.sort_values('Abscisa')
                    z_diseno = cota_rasante(abscisas, df_vert,
                                            st.session_state.get('vias_df_curvas_v'))

                    df_perfil = pd.DataFrame({'Abscisa': abscisas, 'Cota Terreno': z_ter_centro, 'Cota Diseño': z_diseno})

                    # PERALTE EN LAS SECCIONES: antes se aplicaba el bombeo constante
                    # en todo el trazado, así que el peralte calculado en el cuadro de
                    # curvas nunca llegaba a la geometría transversal.
                    # La longitud de transición L y la de aplanamiento N se calculan
                    # automáticamente por curva con la formulación del manual.
                    m_izq_arr, m_der_arr, df_trans = peraltes_por_abscisa(
                        abscisas, st.session_state.get('df_reporte_curvas'),
                        bombeo_izq=bom_izq, bombeo_der=bom_der,
                        ancho_carril=w_carril, n_carriles_giran=n_giran,
                        v_diseno=v_dis, reparto_recta=reparto,
                        retornar_detalle=True
                    )
                    st.session_state.vias_df_transicion = df_trans
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

                    # Misma corrección que en el módulo de volúmenes: la
                    # columna del motor ya viene acumulada.
                    v_neto_tramo = (res_df['Vol. Corte (m³)'].fillna(0)
                                    - res_df['Vol. Relleno (m³)'].fillna(0))
                    res_df['Volumen Neto Tramo (m³)'] = v_neto_tramo.round(3)
                    res_df['Masa Acumulada (m³)'] = v_neto_tramo.cumsum().round(3)

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

            # Puntos singulares de los acuerdos verticales
            df_cvp = st.session_state.get('vias_df_curvas_v')
            if df_cvp is not None and not df_cvp.empty and '_L' in df_cvp.columns:
                act = df_cvp[df_cvp['_L'] > 0]
                if not act.empty:
                    fig_perfil.add_trace(go.Scatter(
                        x=act['_x_pcv'], y=act['Cota PCV'], mode='markers', name='PCV',
                        marker=dict(size=9, color='#2E7D32', symbol='circle')))
                    fig_perfil.add_trace(go.Scatter(
                        x=act['_x_ptv'], y=act['Cota PTV'], mode='markers', name='PTV',
                        marker=dict(size=9, color='#C62828', symbol='circle')))
                    for _, rc in act.iterrows():
                        fig_perfil.add_annotation(
                            x=float(rc['Abscisa PIV']), y=float(rc['Cota PIV']),
                            text=f"{rc['Tipo']}<br>L={float(rc['L adoptada (m)']):.1f} m · K={float(rc['K adoptado']):.1f}",
                            showarrow=False, yshift=26, font=dict(size=9, color='#0D47A1'))

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

        df_tr = st.session_state.get('vias_df_transicion')
        if df_tr is not None and not df_tr.empty:
            st.markdown("**Desarrollo del Peralte — INVIAS 2008, numeral 3.2**")
            st.caption("L = a · bw · (ef − ei) / Δs   ·   N = L · bombeo / e   ·   Puntos A-B-C-D(PC/PT)-E")
            st.dataframe(df_tr, use_container_width=True)

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

            # El plano se escribe en el directorio de la sesión, no en el de
            # trabajo: con varios usuarios simultáneos en Streamlit Cloud dos
            # sesiones se sobrescribían el mismo archivo.
            os.makedirs(dir_reportes(), exist_ok=True)
            ruta_export_vias = os.path.join(dir_reportes(), "Plano_Vias.png")
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

    # =================================================================
    # SECCIÓN 7: INFORME TÉCNICO DEL DISEÑO VIAL
    # =================================================================
    if st.session_state.get('df_reporte_curvas') is not None:
        st.markdown("---")
        st.subheader("7. Informe Técnico del Diseño Geométrico (PDF)")

        faltantes_v = ficha_incompleta()
        if faltantes_v:
            st.warning("La Ficha Técnica tiene campos sin diligenciar (" +
                       ", ".join(faltantes_v) + "). El informe se generará con esos "
                       "campos en blanco.")

        c_op1, c_op2 = st.columns(2)
        incluir_sec_vias = c_op1.checkbox("Anexar secciones transversales",
                                          value=False, key="chk_sec_vias",
                                          help="Añade una plancha por cada abscisa. Alarga la compilación.")
        incluir_vol_vias = c_op2.checkbox("Incluir cubicaje del corredor",
                                          value=True, key="chk_vol_vias",
                                          disabled=not st.session_state.get('vias_calc_vol'))

        if st.button("Generar Informe de Diseño Vial", type="primary", use_container_width=True):
            with st.spinner("Componiendo memorias y compilando LaTeX..."):
                try:
                    salida = dir_reportes()
                    os.makedirs(salida, exist_ok=True)
                    p_act = st.session_state.get('proyecto_actual') or 'Vias'

                    # --- Figuras del informe ---
                    ruta_planta_inf = os.path.join(salida, "Plano_Vias.png")
                    if not os.path.exists(ruta_planta_inf):
                        ancho_t = (st.session_state.get('ancho_izq', 3.6)
                                   + st.session_state.get('ancho_der', 3.6))
                        fig_tmp = generar_plano_vias(
                            st.session_state.df_dibujo_eje,
                            st.session_state.df_reporte_curvas,
                            pd.DataFrame(st.session_state.pis_vias),
                            st.session_state.get('vias_df_vertical'),
                            ancho_calzada=ancho_t)
                        fig_tmp.savefig(ruta_planta_inf, dpi=200, bbox_inches='tight')
                        plt.close(fig_tmp)

                    ruta_perfil_inf = None
                    ruta_masas_inf = None
                    paths_sec_vias = []
                    df_cub = None
                    met_v = None

                    if st.session_state.get('vias_calc_vol') and incluir_vol_vias:
                        df_cub = st.session_state.vias_df_vol_calc
                        met_v = st.session_state.vias_met_vol

                        ruta_masas_inf = os.path.join(salida, "Masas_Vias.png")
                        guardar_imagen_masa_plt(df_cub, ruta_masas_inf)

                        # Perfil longitudinal terreno vs rasante
                        df_pf = st.session_state.vias_df_perfil
                        fig_pf, ax_pf = plt.subplots(figsize=(10, 4))
                        ax_pf.plot(df_pf['Abscisa'], df_pf['Cota Terreno'],
                                   color='#8D6E63', lw=1.8, label='Terreno natural')
                        ax_pf.plot(df_pf['Abscisa'], df_pf['Cota Diseño'],
                                   color='#E53935', lw=2.2, label='Rasante')
                        ax_pf.fill_between(df_pf['Abscisa'], df_pf['Cota Terreno'],
                                           df_pf['Cota Diseño'],
                                           where=(df_pf['Cota Terreno'] >= df_pf['Cota Diseño']),
                                           color='#DC3545', alpha=0.25, label='Corte')
                        ax_pf.fill_between(df_pf['Abscisa'], df_pf['Cota Terreno'],
                                           df_pf['Cota Diseño'],
                                           where=(df_pf['Cota Terreno'] < df_pf['Cota Diseño']),
                                           color='#28A745', alpha=0.25, label='Relleno')
                        ax_pf.set_xlabel("Abscisa (m)", fontweight='bold')
                        ax_pf.set_ylabel("Elevación (msnm)", fontweight='bold')
                        ax_pf.set_title("Perfil Longitudinal", fontsize=13, fontweight='bold')
                        ax_pf.grid(True, linestyle='--', alpha=0.6)
                        ax_pf.legend(loc='best', fontsize=8)
                        fig_pf.tight_layout()
                        ruta_perfil_inf = os.path.join(salida, "Perfil_Vias.png")
                        fig_pf.savefig(ruta_perfil_inf, dpi=150)
                        plt.close(fig_pf)

                        if incluir_sec_vias and st.session_state.get('vias_df_malla') is not None:
                            dfm = st.session_state.vias_df_malla
                            for a_val in sorted(dfm['Abscisa (K)'].unique()):
                                df_p = (dfm[dfm['Abscisa (K)'] == a_val].copy()
                                        .dropna(subset=['Cota Terreno (m)', 'Cota Diseño (m)'])
                                        .sort_values('Distancia Eje (m)'))
                                if not df_p.empty:
                                    r_s = os.path.join(salida, f"SecVia_K{a_val:.3f}.png")
                                    guardar_seccion_plt(df_p, a_val, r_s)
                                    paths_sec_vias.append((a_val, r_s))

                    # --- Parámetros normativos ---
                    r_min_adm = radio_minimo(v_dis, 8.0)
                    params_vias = {
                        "v_diseno": float(v_dis),
                        "ancho_calzada": float(st.session_state.get('ancho_izq', 3.6)
                                               + st.session_state.get('ancho_der', 3.6)),
                        "ancho_carril": float(st.session_state.get('vias_w_carril', 3.65)),
                        "n_carriles_giran": float(st.session_state.get('vias_n_giran', 1.0)),
                        "bombeo": abs(float(st.session_state.get('bom_izq_via', -2.0))),
                        "peralte_max": 8.0,
                        "pendiente_max": 8.0,
                        "pendiente_min": 0.5,
                        "radio_minimo": r_min_adm,
                        "path_planta": ruta_planta_inf,
                        "path_perfil": ruta_perfil_inf,
                        "path_masas": ruta_masas_inf,
                    }

                    metadatos_v = construir_metadatos(
                        sistema_referencia=nombre_proyeccion,
                        huella=huella_datos(st.session_state.df_reporte_curvas,
                                            st.session_state.vias_df_vertical))

                    firma_v = firma_archivos([p for p in [ruta_planta_inf, ruta_perfil_inf,
                                                          ruta_masas_inf] if p]
                                             + [r for _, r in paths_sec_vias])

                    pdf_v, tex_v, dbg_v = cachear_pdf_vias(
                        st.session_state.df_reporte_curvas,
                        st.session_state.vias_df_vertical,
                        st.session_state.get('vias_df_transicion'),
                        st.session_state.get('vias_df_curvas_v'),
                        df_cub, met_v, p_act, salida, firma_v,
                        metadatos_v, construir_equipo(), params_vias,
                        tuple(paths_sec_vias))

                    st.session_state.vias_pdf_bytes = pdf_v
                    st.session_state.vias_tex_code = tex_v
                    st.session_state.vias_debug_msg = dbg_v
                except Exception as e:
                    st.error(f"Falla generando el informe: {e}")

        if st.session_state.get('vias_pdf_bytes'):
            st.success("Informe compilado correctamente.")
            cd1, cd2 = st.columns(2)
            cd1.download_button(
                "Descargar Informe (.PDF)",
                data=st.session_state.vias_pdf_bytes,
                file_name=f"Diseno_Vial_{st.session_state.get('proyecto_actual', 'Proyecto')}.pdf",
                mime="application/pdf", use_container_width=True)
            cd2.download_button(
                "Descargar Fuente (.TEX)",
                data=(st.session_state.get('vias_tex_code') or "").encode('utf-8'),
                file_name=f"Diseno_Vial_{st.session_state.get('proyecto_actual', 'Proyecto')}.tex",
                mime="text/plain", use_container_width=True)
        elif st.session_state.get('vias_debug_msg'):
            st.error("No fue posible compilar el PDF.")
            with st.expander("Detalle del compilador LaTeX"):
                st.code(st.session_state.vias_debug_msg)