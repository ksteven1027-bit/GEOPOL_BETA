# ===================================================================
# MOTOR MATEMÁTICO - LEVANTAMIENTO PREDIAL Y CATASTRO (IGAC LADM-COL)
# Desarrollado para GeoPol Web
# ===================================================================
import numpy as np
import pandas as pd

def calcular_acimut_distancia(e1, n1, e2, n2):
    """Calcula la distancia plana y el azimut entre dos vértices del lindero."""
    delta_e = e2 - e1
    delta_n = n2 - n1
    distancia = np.sqrt(delta_e**2 + delta_n**2)
    acimut_rad = np.arctan2(delta_e, delta_n)
    
    if acimut_rad < 0:
        acimut_rad += 2 * np.pi
        
    acimut_deg = np.degrees(acimut_rad)
    return acimut_deg, distancia

def decimal_a_dms_string(deg):
    """Convierte grados decimales a formato de texto 0°00'00\""""
    d = int(deg)
    m = int(abs(deg - d) * 60)
    s = (abs(deg - d) - m/60.0) * 3600.0
    return f"{d:02d}°{m:02d}'{s:05.2f}\""

def calcular_area_gauss(este, norte):
    """Calcula el área del polígono (predio) mediante la fórmula de Gauss."""
    n = len(este)
    area = 0.0
    for i in range(n - 1):
        area += (este[i] * norte[i+1]) - (este[i+1] * norte[i])
    return abs(area) / 2.0

def procesar_levantamiento_predial(df_vertices):
    """
    Recibe el DataFrame con los vértices y los datos físicos del predio.
    Devuelve el cuadro oficial de áreas y linderos, y las métricas topológicas.
    """
    if len(df_vertices) < 3:
        raise ValueError("Error de topología: Un predio válido debe tener al menos 3 vértices.")
        
    puntos = df_vertices['Punto'].astype(str).tolist()
    este = df_vertices['Este'].astype(float).tolist()
    norte = df_vertices['Norte'].astype(float).tolist()
    
    # Extraer los nuevos datos jurídicos y físicos
    colindante = df_vertices.get('Colindante', pd.Series(["---"] * len(df_vertices))).astype(str).tolist()
    tipo_lindero = df_vertices.get('Tipo de Lindero', pd.Series(["---"] * len(df_vertices))).astype(str).tolist()
    materializacion = df_vertices.get('Materialización', pd.Series(["---"] * len(df_vertices))).astype(str).tolist()
    
    # Garantizar el cierre del polígono predial copiando el primer vértice al final
    if puntos[0] != puntos[-1] or este[0] != este[-1] or norte[0] != norte[-1]:
        puntos.append(puntos[0])
        este.append(este[0])
        norte.append(norte[0])
        colindante.append(colindante[0])
        tipo_lindero.append(tipo_lindero[0])
        materializacion.append(materializacion[0])
        
    area_m2 = calcular_area_gauss(este, norte)
    area_ha = area_m2 / 10000.0
    perimetro_total = 0.0
    
    cuadro_linderos = []
    
    for i in range(len(puntos) - 1):
        pto_origen = puntos[i]
        pto_destino = puntos[i+1]
        e1, n1 = este[i], norte[i]
        e2, n2 = este[i+1], norte[i+1]
        
        az_deg, dist = calcular_acimut_distancia(e1, n1, e2, n2)
        perimetro_total += dist
        
        cuadro_linderos.append({
            "Vértice": pto_origen,
            "Colindancia (Lado)": f"{pto_origen}-{pto_destino}",
            "Distancia (m)": round(dist, 3),
            "Azimut": decimal_a_dms_string(az_deg),
            "Este (m)": round(e1, 3),
            "Norte (m)": round(n1, 3),
            "Colindante": colindante[i],
            "Tipo de Lindero": tipo_lindero[i],
            "Materialización": materializacion[i]
        })
        
    # Vértice de cierre visual al final de la tabla
    cuadro_linderos.append({
        "Vértice": puntos[-1],
        "Colindancia (Lado)": "-",
        "Distancia (m)": 0.0,
        "Azimut": "-",
        "Este (m)": round(este[-1], 3),
        "Norte (m)": round(norte[-1], 3),
        "Colindante": "-",
        "Tipo de Lindero": "-",
        "Materialización": materializacion[-1]
    })
    
    df_cuadro_areas = pd.DataFrame(cuadro_linderos)
    
    metricas_prediales = {
        "Area_m2": round(area_m2, 3),
        "Area_ha": round(area_ha, 4),
        "Perimetro_m": round(perimetro_total, 3),
        "N_Vertices": len(puntos) - 1
    }
    
    return df_cuadro_areas, metricas_prediales