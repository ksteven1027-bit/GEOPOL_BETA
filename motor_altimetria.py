# ===================================================================
# MOTOR MATEMÁTICO - NIVELACIÓN GEOMÉTRICA (ALTIMETRÍA V3.0)
# Novedades: Soporte unificado para Nivelaciones Cerradas y Abiertas.
# ===================================================================
import pandas as pd

def calcular_cartera_nivelacion(puntos, v_atras, v_intermedia, v_adelante, cota_datum, cota_llegada=None):
    n = len(puntos)
    hi = [None] * n
    cotas_crudas = [None] * n
    cotas_ajustadas = [None] * n
    correcciones = [0.0] * n

    cotas_crudas[0] = float(cota_datum)
    cotas_ajustadas[0] = float(cota_datum)
    hi_actual = None
    
    # Contar total de armadas (cambios de estación) basados en las Vistas Atrás
    total_setups = sum([1 for va in v_atras if pd.notna(va) and str(va).strip() != "" and float(va) > 0])
    
    # PRIMERA PASADA: Cálculo de cotas crudas (sin ajuste)
    for i in range(n):
        va = float(v_atras[i]) if pd.notna(v_atras[i]) and str(v_atras[i]).strip() != "" else 0.0
        vi = float(v_intermedia[i]) if pd.notna(v_intermedia[i]) and str(v_intermedia[i]).strip() != "" else 0.0
        vd = float(v_adelante[i]) if pd.notna(v_adelante[i]) and str(v_adelante[i]).strip() != "" else 0.0
        
        if i > 0:
            if vi > 0:
                cotas_crudas[i] = hi_actual - vi
            elif vd > 0:
                cotas_crudas[i] = hi_actual - vd
            else:
                cotas_crudas[i] = cotas_crudas[i-1]
                
        if va > 0:
            hi_actual = cotas_crudas[i] + va
            hi[i] = hi_actual

    # ---------------------------------------------------------
    # LÓGICA DE CIERRE: Cerrada vs Abierta
    # Si no hay cota de llegada, debe cerrar en el Datum inicial
    cota_teorica_final = float(cota_llegada) if cota_llegada is not None else float(cota_datum)
    # ---------------------------------------------------------

    cota_final_cruda = cotas_crudas[-1]
    error_cierre = cota_final_cruda - cota_teorica_final
    
    # Factor de corrección por armada (Signo contrario al error)
    corr_por_setup = -error_cierre / total_setups if total_setups > 0 else 0
    
    # SEGUNDA PASADA: Aplicar compensación proporcional
    active_setup = 0
    for i in range(n):
        va = float(v_atras[i]) if pd.notna(v_atras[i]) and str(v_atras[i]).strip() != "" else 0.0
        vi = float(v_intermedia[i]) if pd.notna(v_intermedia[i]) and str(v_intermedia[i]).strip() != "" else 0.0
        vd = float(v_adelante[i]) if pd.notna(v_adelante[i]) and str(v_adelante[i]).strip() != "" else 0.0
        
        if i > 0:
            if vi > 0 or vd > 0:
                correcciones[i] = active_setup * corr_por_setup
            else:
                correcciones[i] = correcciones[i-1]
            cotas_ajustadas[i] = cotas_crudas[i] + correcciones[i]
        
        if va > 0:
            active_setup += 1
            
    # CONSTRUCCIÓN DE CARTERA
    df_resultado = pd.DataFrame({
        "Estaca / Punto": puntos,
        "Vista Atrás (+)": [round(x, 3) if pd.notna(x) and str(x).strip() != "" else "" for x in v_atras],
        "Altura Inst. (HI)": [round(x, 3) if x is not None else "" for x in hi],
        "Vista Intermedia (-)": [round(x, 3) if pd.notna(x) and str(x).strip() != "" else "" for x in v_intermedia],
        "Vista Adelante (-)": [round(x, 3) if pd.notna(x) and str(x).strip() != "" else "" for x in v_adelante],
        "Cota Calculada": [f"{x:.3f}" for x in cotas_crudas],
        "Corrección (m)": [f"{x:.4f}" for x in correcciones],
        "Cota Ajustada": [f"{x:.3f}" for x in cotas_ajustadas]
    })
    
    sum_va = sum([float(x) for x in v_atras if pd.notna(x) and str(x).strip() != ""])
    sum_vd = sum([float(x) for x in v_adelante if pd.notna(x) and str(x).strip() != ""])
    
    metricas = {
        "sum_vista_atras": round(sum_va, 3),
        "sum_vista_adelante": round(sum_vd, 3),
        "cota_final_cruda": round(cota_final_cruda, 3),
        "cota_teorica_final": round(cota_teorica_final, 3),
        "cota_final_ajustada": round(cotas_ajustadas[-1], 3),
        "error_cierre_m": error_cierre,
        "error_cierre_mm": error_cierre * 1000
    }
    
    return df_resultado, metricas