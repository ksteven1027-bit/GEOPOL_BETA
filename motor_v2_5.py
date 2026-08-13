# ===================================================================
# CÁLCULO DE POLIGONAL CERRADA - VERSIÓN 3.3 (MOTOR DINÁMICO)
# Novedades: Lógica de bucles dinámicos adaptables a cualquier tamaño de tabla.
# ===================================================================
import math
import pandas as pd

def dms_a_decimal(grados, minutes, segundos):
    signo = -1 if grados < 0 else 1
    return signo * (abs(grados) + minutes / 60.0 + segundos / 3600.0)

def decimal_a_dms(decimal):
    signo = "-" if decimal < 0 else ""
    decimal = abs(decimal)
    grados = int(decimal)
    minutes_float = (decimal - grados) * 60
    minutes = int(minutes_float)
    segundos = (minutes_float - minutes) * 60
    return f"{signo}{grados}° {minutes}' {segundos:.2f}\""

def poligonal_3d_v2_5(estacionado, punto_obs, ang_h_dms, ang_z_dms, dist_inc, hi, hr, 
                      coord_iniciales, coord_referencia=None, azimut_ref_dms=None, tipo_angulo='exterior'):
    m = len(estacionado)
    if m < 3:
        raise ValueError("Se necesitan al menos 3 registros (1 de orientación y 2 de circuito) para calcular.")
    
    # 1. CÁLCULO O ASIGNACIÓN DEL AZIMUT DE REFERENCIA INICIAL
    if coord_referencia is not None and coord_referencia[0] is not None:
        delta_e = coord_referencia[0] - coord_iniciales[0]
        delta_n = coord_referencia[1] - coord_iniciales[1]
        azimut_referencia = math.degrees(math.atan2(delta_e, delta_n)) % 360.0
        origen_azimut = f"Calculado automáticamente: {decimal_a_dms(azimut_referencia)}"
    elif azimut_ref_dms is not None:
        azimut_referencia = dms_a_decimal(*azimut_ref_dms)
        origen_azimut = f"Ingresado manualmente: {decimal_a_dms(azimut_referencia)}"
    else:
        raise ValueError("Debe proporcionar coordenadas de referencia o un azimut manual.")

    # Convertir listas de GMS a decimales
    ang_h_dec = [dms_a_decimal(*a) for a in ang_h_dms]
    ang_z_dec = [dms_a_decimal(*a) for a in ang_z_dms]
    
    # Reducción de distancias y desniveles crudos
    dist_horiz = []
    desniveles_crudos = []
    for i in range(m):
        z_rad = math.radians(ang_z_dec[i])
        dist_horiz.append(dist_inc[i] * math.sin(z_rad))
        desniveles_crudos.append((dist_inc[i] * math.cos(z_rad)) + hi[i] - hr[i])

    # Aislamiento del circuito (desde el registro 1 hasta el final)
    ang_h_poligono = ang_h_dec[1:]
    n_lados = len(ang_h_poligono)
    
    tipo = tipo_angulo.strip().lower()
    suma_teorica = (n_lados - 2) * 180.0 if tipo == 'interior' else (n_lados + 2) * 180.0
    
    # Errores angulares antes del ajuste
    error_angular = sum(ang_h_poligono) - suma_teorica
    corr_ang = error_angular / n_lados
    ang_h_ajustados_pol = [a - corr_ang for a in ang_h_poligono]
    
    # Azimut de la primera línea real de la poligonal
    azimut_inicial_linea = (azimut_referencia + ang_h_dec[0]) % 360.0
    
    # ¡NUEVO!: Generación dinámica del orden de recorrido físico de las líneas
    orden_recorrido = [m - 1] + list(range(1, m - 1))
    
    azimuts_tramos = {m - 1: azimut_inicial_linea}
    for idx in range(len(orden_recorrido) - 1):
        actual = orden_recorrido[idx + 1]
        previo = orden_recorrido[idx]
        azimuts_tramos[actual] = (azimuts_tramos[previo] + 180.0 + ang_h_ajustados_pol[idx]) % 360.0
        
    # Cálculo de Proyecciones Crudas
    departures_crudos = {i: dist_horiz[i] * math.sin(math.radians(azimuts_tramos[i])) for i in orden_recorrido}
    latitudes_crudos = {i: dist_horiz[i] * math.cos(math.radians(azimuts_tramos[i])) for i in orden_recorrido}
    desniveles_pol = {i: desniveles_crudos[i] for i in orden_recorrido}
    
    perimetro_h = sum(dist_horiz[i] for i in orden_recorrido)
    error_dep = sum(departures_crudos.values())
    error_lat = sum(latitudes_crudos.values())
    error_lineal = math.sqrt(error_dep**2 + error_lat**2)
    precision_horizontal = perimetro_h / error_lineal if error_lineal != 0 else 0
    
    error_vertical = sum(desniveles_pol.values())
    precision_vertical = perimetro_h / abs(error_vertical) if error_vertical != 0 else 0

    # Ajuste Regla de la Brújula (Bowditch)
    dep_ajus, lat_ajus, desniveles_ajus = {}, {}, {}
    for i in orden_recorrido:
        dep_ajus[i] = departures_crudos[i] - (error_dep / perimetro_h) * dist_horiz[i]
        lat_ajus[i] = latitudes_crudos[i] - (error_lat / perimetro_h) * dist_horiz[i]
        desniveles_ajus[i] = desniveles_pol[i] - (error_vertical / perimetro_h) * dist_horiz[i]

    # ¡NUEVO!: Cálculo dinámico de coordenadas sin nombres fijos de estaciones
    punto_inicio = estacionado[m - 1]
    coord_estaciones = {punto_inicio: (coord_iniciales[0], coord_iniciales[1], coord_iniciales[2])}
    
    for i in orden_recorrido:
        est_actual = estacionado[i]
        obs_actual = punto_obs[i]
        if est_actual in coord_estaciones:
            coord_estaciones[obs_actual] = (
                coord_estaciones[est_actual][0] + dep_ajus[i],
                coord_estaciones[est_actual][1] + lat_ajus[i],
                coord_estaciones[est_actual][2] + desniveles_ajus[i]
            )

    # Reconstrucción ordenada de las listas para armar el DataFrame final
    az_completos_str = [decimal_a_dms(azimut_referencia)] + [decimal_a_dms(azimuts_tramos[i]) for i in range(1, m)]
    ang_ajustados_str = ["- [Visual Ref]"] + [decimal_a_dms(a) for a in ang_h_ajustados_pol]
    dep_ajus_col = [0.0] + [dep_ajus[i] for i in range(1, m)]
    lat_ajus_col = [0.0] + [lat_ajus[i] for i in range(1, m)]
    dv_ajus_col = [0.0] + [desniveles_ajus[i] for i in range(1, m)]
    
    x_col, y_col, z_col = [], [], []
    for est in estacionado:
        if est in coord_estaciones:
            x_col.append(coord_estaciones[est][0])
            y_col.append(coord_estaciones[est][1])
            z_col.append(coord_estaciones[est][2])
        else:
            x_col.append(coord_iniciales[0])
            y_col.append(coord_iniciales[1])
            z_col.append(coord_iniciales[2])

    df_campo = pd.DataFrame({
        'Estacionado': estacionado, 'Pto_Obs': punto_obs,
        'Angulo_Hz': [decimal_a_dms(a) for a in ang_h_dec], 'Ang_Cenital (Z)': [decimal_a_dms(a) for a in ang_z_dec],
        'Dist_Inclinada': [round(d, 3) for d in dist_inc], 'hi': hi, 'hr': hr,
        'Dist_Horiz': [round(dh, 3) for dh in dist_horiz], 'Desnivel_Crudo': [round(dv, 3) for dv in desniveles_crudos]
    })
    
    df_ajuste = pd.DataFrame({
        'Estacionado': estacionado, 'Pto_Obs': punto_obs,
        'Ang_Hz_Ajus': ang_ajustados_str, 'Azimut_Línea': az_completos_str,
        'Dep_Ajus (E)': [round(d, 3) for d in dep_ajus_col], 'Lat_Ajus (N)': [round(l, 3) for l in lat_ajus_col],
        'X_Estacion': [round(c, 3) for c in x_col], 'Y_Estacion': [round(c, 3) for c in y_col],
        'Desnivel_Ajus': [round(dv, 3) for dv in dv_ajus_col], 'Z_Estacion': [round(c, 3) for c in z_col]
    })
    
    # Datos por lado SIN redondear, en el orden físico del recorrido.
    # Los necesita el informe LaTeX para la memoria de proyecciones de
    # Bowditch: tomarlos del DataFrame introduce el redondeo a milímetro
    # de Dist_Horiz y el cierre no coincide con el que se reporta aquí.
    lados_circuito = [
        {"lado": f"{estacionado[i]}-{punto_obs[i]}",
         "distancia": dist_horiz[i],
         "azimut": azimuts_tramos[i],
         "delta_e": departures_crudos[i],
         "delta_n": latitudes_crudos[i]}
        for i in orden_recorrido
    ]

    # Empaquetamos las métricas técnicas solicitadas
    metricas = {
        "perimetro": perimetro_h, "origen_azimut": origen_azimut,
        "lados": lados_circuito, "tipo_circuito": "cerrado",
        "err_ang_ant": error_angular, "err_ang_des": (sum(ang_h_ajustados_pol) - suma_teorica),
        "err_e_ant": error_dep, "err_e_des": sum(dep_ajus.values()),
        "err_n_ant": error_lat, "err_n_des": sum(lat_ajus.values()),
        "err_h_ant": error_lineal, "err_h_des": math.sqrt(sum(dep_ajus.values())**2 + sum(lat_ajus.values())**2),
        "err_v_ant": error_vertical, "err_v_des": sum(desniveles_ajus.values()),
        "prec_h": precision_horizontal, "prec_v": precision_vertical
    }
    
    return df_campo, df_ajuste, metricas