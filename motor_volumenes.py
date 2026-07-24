# ===================================================================
# MOTOR DE VOLÚMENES Y SECCIONES TRANSVERSALES (FINAL)
# Desarrollado para Geoportal Web
# Novedades: Eliminación de columnas redundantes, cálculo implícito
# de rasantes y optimización de memoria.
# ===================================================================
import pandas as pd
import numpy as np

def generar_malla_vacia(abs_ini, abs_fin, int_long, ancho_izq, ancho_der, int_transv, hi_ini):
    """Autogenera la malla sin columnas redundantes, inyectando solo el Datum Topográfico."""
    abscisas = np.arange(abs_ini, abs_fin + 0.001, int_long)
    
    off_izq = np.arange(-ancho_izq, 0, int_transv)
    off_der = np.arange(0, ancho_der + 0.001, int_transv)
    offsets = np.unique(np.concatenate((off_izq, off_der, [-ancho_izq, ancho_der, 0.0])))
    offsets = np.sort(offsets)

    datos = []
    es_primera_fila = True
    
    for abs_k in abscisas:
        for offset in offsets:
            datos.append({
                "Abscisa (K)": round(abs_k, 3),
                "Distancia Eje (m)": round(float(offset), 3),
                "Altura Inst. (HI)": round(hi_ini, 3) if es_primera_fila else None, 
                "Lectura Mira (-)": None,
                "Cota Terreno (m)": None, 
                "Cota Diseño (m)": None   
            })
            es_primera_fila = False
            
    return pd.DataFrame(datos)

def calcular_cotas_seccion(df, bombeo_izq, bombeo_der, cota_rasante_ini, pend_long, abs_ini):
    """Transformación matemática a cotas reales (Calcula la rasante dinámicamente)."""
    df = df.copy()
    
    # Propagación del HI hacia abajo (Forward Fill)
    df['Altura Inst. (HI)'] = pd.to_numeric(df['Altura Inst. (HI)'], errors='coerce').ffill()
    
    # 1. COTA TERRENO (Topografía)
    lectura = pd.to_numeric(df['Lectura Mira (-)'], errors='coerce')
    df['Cota Terreno (m)'] = df['Altura Inst. (HI)'] - lectura
    
    # 2. COTA DISEÑO (Rasante Dinámica + Bombeo)
    distancias = pd.to_numeric(df['Distancia Eje (m)'], errors='coerce')
    abscisas = pd.to_numeric(df['Abscisa (K)'], errors='coerce')
    
    # La cota rasante del eje se calcula matemáticamente en segundo plano
    cotas_eje = cota_rasante_ini + (abscisas - abs_ini) * (pend_long / 100.0)
    
    cond_izq = distancias < 0
    cond_der = distancias > 0
    
    desnivel = np.zeros(len(df))
    desnivel[cond_izq] = np.abs(distancias[cond_izq]) * (bombeo_izq / 100.0)
    desnivel[cond_der] = np.abs(distancias[cond_der]) * (bombeo_der / 100.0)
    
    df['Cota Diseño (m)'] = cotas_eje + desnivel
    
    df['Cota Terreno (m)'] = df['Cota Terreno (m)'].round(3)
    df['Cota Diseño (m)'] = df['Cota Diseño (m)'].round(3)
    
    return df

def calcular_areas_seccion(offsets, cotas_terreno, cotas_diseno):
    """Algoritmo de Áreas Medias con detección de intersecciones (Puntos de Paso)."""
    area_corte = 0.0
    area_relleno = 0.0
    
    idx_sort = np.argsort(offsets)
    off = np.array(offsets)[idx_sort]
    terr = np.array(cotas_terreno)[idx_sort]
    dis = np.array(cotas_diseno)[idx_sort]
    
    for i in range(len(off) - 1):
        dx = off[i+1] - off[i]
        if dx <= 0: continue
            
        y1 = terr[i] - dis[i]
        y2 = terr[i+1] - dis[i+1]
        
        if y1 >= 0 and y2 >= 0:
            area_corte += 0.5 * (y1 + y2) * dx
        elif y1 <= 0 and y2 <= 0:
            area_relleno += 0.5 * (abs(y1) + abs(y2)) * dx
        else:
            denominador = (abs(y1) + abs(y2))
            dx1 = dx * abs(y1) / denominador if denominador != 0 else 0
            dx2 = dx - dx1
            area1 = 0.5 * abs(y1) * dx1
            area2 = 0.5 * abs(y2) * dx2
            
            if y1 > 0:
                area_corte += area1
                area_relleno += area2
            else:
                area_relleno += area1
                area_corte += area2
                
    return area_corte, area_relleno

def calcular_cubicaje_total(df_calculado):
    """Genera el reporte volumétrico final para el DataFrame procesado."""
    df = df_calculado.dropna(subset=['Distancia Eje (m)', 'Cota Terreno (m)', 'Cota Diseño (m)'])
    
    abscisas = sorted(df['Abscisa (K)'].unique())
    resultados = []
    
    for abs_actual in abscisas:
        datos_sec = df[df['Abscisa (K)'] == abs_actual]
        if len(datos_sec) < 2: continue 
        
        a_corte, a_relleno = calcular_areas_seccion(
            datos_sec['Distancia Eje (m)'].tolist(),
            datos_sec['Cota Terreno (m)'].tolist(),
            datos_sec['Cota Diseño (m)'].tolist()
        )
        resultados.append({
            'Abscisa (K)': abs_actual,
            'Área Corte (m²)': round(a_corte, 3),
            'Área Relleno (m²)': round(a_relleno, 3),
            'Vol. Corte (m³)': 0.0,
            'Vol. Relleno (m³)': 0.0,
            'Vol. Acumulado Corte': 0.0,
            'Vol. Acumulado Relleno': 0.0
        })
        
    df_res = pd.DataFrame(resultados)
    
    if not df_res.empty:
        for i in range(1, len(df_res)):
            L = df_res.loc[i, 'Abscisa (K)'] - df_res.loc[i-1, 'Abscisa (K)']
            df_res.loc[i, 'Vol. Corte (m³)'] = 0.5 * (df_res.loc[i, 'Área Corte (m²)'] + df_res.loc[i-1, 'Área Corte (m²)']) * L
            df_res.loc[i, 'Vol. Relleno (m³)'] = 0.5 * (df_res.loc[i, 'Área Relleno (m²)'] + df_res.loc[i-1, 'Área Relleno (m²)']) * L
            
        df_res['Vol. Acumulado Corte'] = df_res['Vol. Corte (m³)'].cumsum()
        df_res['Vol. Acumulado Relleno'] = df_res['Vol. Relleno (m³)'].cumsum()
        df_res['Volumen Neto (m³)'] = df_res['Vol. Acumulado Corte'] - df_res['Vol. Acumulado Relleno']
        df_res = df_res.round(3)
        
        metricas = {
            "Corte_Total": round(df_res['Vol. Corte (m³)'].sum(), 3),
            "Relleno_Total": round(df_res['Vol. Relleno (m³)'].sum(), 3),
            "Volumen_Neto": round(df_res['Volumen Neto (m³)'].iloc[-1], 3)
        }
    else:
        metricas = {"Corte_Total": 0.0, "Relleno_Total": 0.0, "Volumen_Neto": 0.0}
        
    return df_res, metricas