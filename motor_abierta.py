# ===================================================================
# MOTOR MATEMÁTICO - POLIGONAL ABIERTA ENLAZADA (VERSIÓN 4.7)
# Novedades: Soporte para orientación mixta (Coordenadas vs Azimut)
#            tanto en la estación de arranque como en la de llegada.
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

def poligonal_abierta_control(estacionado, punto_obs, ang_h_dms, ang_z_dms, dist_inc, hi, hr, 
                              coord_arranque, coord_llegada, 
                              coord_ref_arranque=None, az_arranque_dms=None, 
                              coord_ref_llegada=None, az_llegada_dms=None):
    m = len(estacionado)
    if m < 3:
        raise ValueError("Se necesitan al menos 3 registros para calcular una poligonal enlazada.")

    # 1. CÁLCULO O LECTURA DEL AZIMUT DE ARRANQUE
    if coord_ref_arranque is not None:
        delta_e_arr = coord_ref_arranque[0] - coord_arranque[0]
        delta_n_arr = coord_ref_arranque[1] - coord_arranque[1]
        az_ref_arranque = math.degrees(math.atan2(delta_e_arr, delta_n_arr)) % 360.0
    elif az_arranque_dms is not None:
        az_ref_arranque = dms_a_decimal(*az_arranque_dms)
    else:
        raise ValueError("Error: Debe proveer coordenada de referencia de arranque o un Azimut manual.")

    # 2. CÁLCULO O LECTURA DEL AZIMUT DE LLEGADA (CIERRE)
    if coord_ref_llegada is not None:
        delta_e_lleg = coord_ref_llegada[0] - coord_llegada[0]
        delta_n_lleg = coord_ref_llegada[1] - coord_llegada[1]
        az_ref_llegada = math.degrees(math.atan2(delta_e_lleg, delta_n_lleg)) % 360.0
    elif az_llegada_dms is not None:
        az_ref_llegada = dms_a_decimal(*az_llegada_dms)
    else:
        raise ValueError("Error: Debe proveer coordenada de referencia de llegada o un Azimut manual.")

    # 3. PREPARACIÓN Y REDUCCIÓN DE DISTANCIAS
    ang_h_dec = [dms_a_decimal(*a) for a in ang_h_dms]
    ang_z_dec = [dms_a_decimal(*a) for a in ang_z_dms]
    
    dist_horiz = []
    desniveles_crudos = []
    for i in range(m):
        z_rad = math.radians(ang_z_dec[i])
        dist_horiz.append(dist_inc[i] * math.sin(z_rad))
        desniveles_crudos.append((dist_inc[i] * math.cos(z_rad)) + hi[i] - hr[i])

    # 4. SEGUIMIENTO DE AZIMUTS Y ERROR ANGULAR
    azimuts_crudos = []
    az_actual = (az_ref_arranque + ang_h_dec[0]) % 360.0
    azimuts_crudos.append(az_actual)
    
    for i in range(1, m):
        az_actual = (azimuts_crudos[i-1] + 180.0 + ang_h_dec[i]) % 360.0
        azimuts_crudos.append(az_actual)
        
    az_calc_final = azimuts_crudos[-1]
    error_angular = az_calc_final - az_ref_llegada
    
    if error_angular > 180: error_angular -= 360.0
    elif error_angular < -180: error_angular += 360.0
        
    corr_ang = error_angular / m
    ang_h_ajustados = [a - corr_ang for a in ang_h_dec]
    
    azimuts_ajus = []
    az_actual = (az_ref_arranque + ang_h_ajustados[0]) % 360.0
    azimuts_ajus.append(az_actual)
    for i in range(1, m):
        az_actual = (azimuts_ajus[i-1] + 180.0 + ang_h_ajustados[i]) % 360.0
        azimuts_ajus.append(az_actual)

    # 5. PROYECCIONES Y ERROR LINEAL
    departures_crudos = [dist_horiz[i] * math.sin(math.radians(azimuts_ajus[i])) for i in range(m-1)]
    latitudes_crudos = [dist_horiz[i] * math.cos(math.radians(azimuts_ajus[i])) for i in range(m-1)]
    desniveles_recorrido = desniveles_crudos[:m-1]
    
    perimetro_h = sum(dist_horiz[:m-1])
    
    suma_dep, suma_lat, suma_desniv = sum(departures_crudos), sum(latitudes_crudos), sum(desniveles_recorrido)
    teorico_dep = coord_llegada[0] - coord_arranque[0]
    teorico_lat = coord_llegada[1] - coord_arranque[1]
    teorico_desniv = coord_llegada[2] - coord_arranque[2]
    
    error_e = suma_dep - teorico_dep
    error_n = suma_lat - teorico_lat
    error_v = suma_desniv - teorico_desniv
    error_lineal = math.sqrt(error_e**2 + error_n**2)
    
    precision_horizontal = perimetro_h / error_lineal if error_lineal != 0 else 0
    precision_vertical = perimetro_h / abs(error_v) if error_v != 0 else 0

    # 6. AJUSTE DE BOWDITCH
    dep_ajus, lat_ajus, desniv_ajus = [], [], []
    for i in range(m-1):
        dep_ajus.append(departures_crudos[i] - (error_e / perimetro_h) * dist_horiz[i])
        lat_ajus.append(latitudes_crudos[i] - (error_n / perimetro_h) * dist_horiz[i])
        desniv_ajus.append(desniveles_recorrido[i] - (error_v / perimetro_h) * dist_horiz[i])

    dep_ajus_col = dep_ajus + [0.0]
    lat_ajus_col = lat_ajus + [0.0]
    dv_ajus_col = desniv_ajus + [0.0]

    # 7. COORDENADAS AJUSTADAS
    coord_x, coord_y, coord_z = [coord_arranque[0]], [coord_arranque[1]], [coord_arranque[2]]
    for i in range(m-1):
        coord_x.append(coord_x[-1] + dep_ajus[i])
        coord_y.append(coord_y[-1] + lat_ajus[i])
        coord_z.append(coord_z[-1] + desniv_ajus[i])

    # 8. CONSTRUCCIÓN DE CARTERAS
    df_campo = pd.DataFrame({
        'Estacionado': estacionado, 'Pto_Obs': punto_obs,
        'Angulo_Hz': [decimal_a_dms(a) for a in ang_h_dec], 'Ang_Cenital': [decimal_a_dms(a) for a in ang_z_dec],
        'Dist_Inc': [round(d, 3) for d in dist_inc], 'hi': hi, 'hr': hr,
        'Dist_Horiz': [round(dh, 3) for dh in dist_horiz], 'Desnivel_Crudo': [round(dv, 3) for dv in desniveles_crudos]
    })
    
    df_ajuste = pd.DataFrame({
        'Estacionado': estacionado, 'Pto_Obs': punto_obs,
        'Ang_Hz_Ajus': [decimal_a_dms(a) for a in ang_h_ajustados], 'Azimut_Línea': [decimal_a_dms(a) for a in azimuts_ajus],
        'Dep_Ajus (E)': [round(d, 3) for d in dep_ajus_col], 'Lat_Ajus (N)': [round(l, 3) for l in lat_ajus_col],
        'X_Estacion': [round(c, 3) for c in coord_x], 'Y_Estacion': [round(c, 3) for c in coord_y],
        'Z_Estacion': [round(c, 3) for c in coord_z]
    })
    
    metricas = {
        "perimetro": perimetro_h, "origen_azimut": f"Arranque: {decimal_a_dms(az_ref_arranque)} | Llegada: {decimal_a_dms(az_ref_llegada)}",
        "err_ang_ant": error_angular, "err_ang_des": 0.0, "err_e_ant": error_e, "err_e_des": 0.0,
        "err_n_ant": error_n, "err_n_des": 0.0, "err_h_ant": error_lineal, "err_h_des": 0.0,
        "err_v_ant": error_v, "err_v_des": 0.0, "prec_h": precision_horizontal, "prec_v": precision_vertical
    }
    return df_campo, df_ajuste, metricas