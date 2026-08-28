# ===================================================================
# MOTOR DE DISEÑO VIAL - ALINEAMIENTO HORIZONTAL Y VERTICAL
# Desarrollado para GeoPol Web
# Actualizado: Enfoque riguroso de precisión a 3 decimales
#
# CORRECCIONES APLICADAS:
#  1. La "Pendiente (%)" del cuadro de curvas ahora se calcula sobre la
#     diferencia de ABSCISAS (eje real) y no sobre la distancia plana
#     PI-PI. Antes las dos tablas mostraban valores distintos para el
#     mismo tramo.
#  2. decimal_a_dms_string es robusto ante negativos y ante el acarreo
#     de 60.00" / 60' producido por el redondeo.
#  3. Saneamiento de entrada: se descartan filas sin coordenadas, se
#     fuerza el tipo numérico y se renumeran los PI.
#  4. Verificación de traslape entre tangentes de curvas contiguas, no
#     sólo contra la distancia bruta PI-PI.
#  5. Coeficiente de fricción transversal variable con la velocidad de
#     diseño (antes fijo en 0.14) y cálculo de radio mínimo.
#  6. Garantía de monotonía en las abscisas de los PIV para que la
#     interpolación de la rasante nunca se invierta.
# ===================================================================
import numpy as np
import pandas as pd

# Fricción transversal máxima aproximada según velocidad de diseño.
# (Manual de Diseño Geométrico INVIAS - valores de referencia).
# Verifique contra la tabla oficial vigente antes de usar en producción.
_V_TABLA = [30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
_F_TABLA = [0.17, 0.17, 0.16, 0.15, 0.14, 0.14, 0.13, 0.12, 0.11, 0.09]


def coeficiente_friccion(v_diseno):
    """Devuelve el coeficiente de fricción transversal para la velocidad dada."""
    return float(np.interp(float(v_diseno), _V_TABLA, _F_TABLA))


def radio_minimo(v_diseno, e_max=8.0):
    """Radio mínimo absoluto: R = V^2 / (127 * (e_max + f))."""
    f = coeficiente_friccion(v_diseno)
    return (float(v_diseno) ** 2) / (127.0 * ((float(e_max) / 100.0) + f))


def calcular_acimut_distancia(e1, n1, e2, n2):
    """Calcula la distancia plana y el acimut entre dos coordenadas."""
    delta_e = e2 - e1
    delta_n = n2 - n1
    distancia = np.sqrt(delta_e**2 + delta_n**2)
    acimut_rad = np.arctan2(delta_e, delta_n)

    if acimut_rad < 0:
        acimut_rad += 2 * np.pi

    acimut_deg = np.degrees(acimut_rad)
    return acimut_deg, distancia


def decimal_a_dms_string(deg):
    """
    Convierte grados decimales a formato de texto 0°00'00.00".
    Maneja valores negativos y el acarreo por redondeo (60.00" -> 1').
    """
    signo = "-" if deg < 0 else ""
    deg = abs(float(deg))

    d = int(deg)
    resto_min = (deg - d) * 60.0
    m = int(resto_min)
    s = (resto_min - m) * 60.0

    # Acarreo por redondeo a 2 decimales de segundo
    if round(s, 2) >= 60.0:
        s = 0.0
        m += 1
    if m >= 60:
        m = 0
        d += 1

    return f"{signo}{d:02d}°{m:02d}'{s:05.2f}\""


def formato_abscisa(valor):
    """Devuelve la abscisa en formato K0+000.000."""
    valor = float(valor)
    return f"K{int(valor / 1000)}+{valor % 1000:07.3f}"


def _sanear_pis(df_pis):
    """
    Limpia la matriz de PIs: fuerza tipos numéricos, elimina filas sin
    coordenadas, descarta vértices duplicados consecutivos y renumera.
    """
    df = df_pis.copy().reset_index(drop=True)

    for col, defecto in (("Este", None), ("Norte", None), ("Elevacion", 0.0), ("Radio", 0.0)):
        if col not in df.columns:
            if defecto is None:
                raise ValueError(f"La matriz de vértices no contiene la columna obligatoria '{col}'.")
            df[col] = defecto
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Elevacion"] = df["Elevacion"].fillna(0.0)
    df["Radio"] = df["Radio"].fillna(0.0)

    # Se descartan filas vacías creadas al agregar renglones en el editor
    df = df.dropna(subset=["Este", "Norte"]).reset_index(drop=True)

    # Elimina vértices repetidos consecutivos (clics dobles sobre el mapa)
    if len(df) > 1:
        conservar = [True] + [
            not (
                np.isclose(df.loc[i, "Este"], df.loc[i - 1, "Este"], atol=1e-4)
                and np.isclose(df.loc[i, "Norte"], df.loc[i - 1, "Norte"], atol=1e-4)
            )
            for i in range(1, len(df))
        ]
        df = df[conservar].reset_index(drop=True)

    df["PI"] = [f"PI-{i + 1}" for i in range(len(df))]
    return df


# ---------------------------------------------------------------
# TRANSICIÓN DEL PERALTE - Formulación INVIAS 2008 (numeral 3.2)
#
#            a · bw · (ef - ei)
#      L =  --------------------
#                   Δs
#
#   a  = ancho de calzada que gira = w · n
#   w  = ancho de carril (m)
#   n  = número de carriles que giran
#   bw = factor de ajuste por número de carriles girados
#   Δs = pendiente relativa máxima de la rampa de peraltes (%)
#
#   N (longitud de aplanamiento) = L · bombeo / e
#
#   Reparto: 70% de L en recta y 30% dentro de la curva, de modo que en
#   el PC y el PT el peralte vale 0.70·e.
# ---------------------------------------------------------------

# Tabla: pendiente relativa máxima de la rampa de peraltes (%) vs Velocidad Específica
_V_RAMPA = [20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130]
_DS_RAMPA = [1.36, 1.28, 0.96, 0.77, 0.60, 0.55, 0.50, 0.47, 0.44, 0.41, 0.38, 0.38]

# Tabla: factor de ajuste bw según número de carriles que giran
_N_CARRILES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
_BW_FACTOR = [1.00, 0.83, 0.75, 0.70, 0.67, 0.64]


def pendiente_relativa_rampa(v_especifica):
    """Δs máxima (%) de la rampa de peraltes según la velocidad específica."""
    return float(np.interp(float(v_especifica), _V_RAMPA, _DS_RAMPA))


def factor_ajuste_carriles(n_carriles):
    """Factor bw de ajuste por número de carriles que giran."""
    return float(np.interp(float(n_carriles), _N_CARRILES, _BW_FACTOR))


def longitud_transicion_peralte(peralte, ancho_carril=3.65, n_carriles_giran=1.0,
                                v_especifica=60, bombeo=2.0):
    """
    Longitud de transición (L) y de aplanamiento (N) según INVIAS 2008.
    Devuelve un diccionario con todos los parámetros intermedios para que
    puedan mostrarse en la memoria de cálculo.
    """
    e = abs(float(peralte))
    b = abs(float(bombeo))
    a = float(ancho_carril) * float(n_carriles_giran)
    bw = factor_ajuste_carriles(n_carriles_giran)
    ds = pendiente_relativa_rampa(v_especifica)

    L = (a * bw * e) / ds if ds > 0 else 0.0
    N = (L * b / e) if e > 0 else 0.0

    return {
        "L": round(L, 3), "N": round(N, 3), "LT": round(L + N, 3),
        "a": round(a, 3), "bw": round(bw, 3), "delta_s": round(ds, 3),
        "e": round(e, 3), "bombeo": round(b, 3),
    }


def _rampa_borde_exterior(s, pc, pt, e, b, L, N, reparto_recta=0.70):
    """
    Peralte (%) del borde EXTERIOR en la abscisa s, según los puntos
    principales A-B-C-D-E del desarrollo del peralte del manual.
    Signo: negativo = el borde cae respecto del eje.
    """
    # Entrada
    b_in = pc - reparto_recta * L      # B: borde exterior en 0%
    a_in = b_in - N                    # A: bombeo normal
    e_in = b_in + L                    # E: peralte pleno
    # Salida (simétrica)
    e_out = pt - (1.0 - reparto_recta) * L
    b_out = e_out + L
    a_out = b_out + N

    if s < a_in or s > a_out:
        return -b
    if s < b_in:                       # A -> B : de -bombeo a 0
        return -b * (b_in - s) / N if N > 0 else 0.0
    if s <= e_in:                      # B -> E : de 0 a +e
        return e * (s - b_in) / L if L > 0 else e
    if s < e_out:                      # peralte pleno
        return e
    if s <= b_out:                     # E -> B : de +e a 0
        return e * (b_out - s) / L if L > 0 else 0.0
    return -b * (s - b_out) / N if N > 0 else 0.0   # B -> A : de 0 a -bombeo


def peraltes_por_abscisa(abscisas, df_reporte, bombeo_izq=-2.0, bombeo_der=-2.0,
                         ancho_carril=3.65, n_carriles_giran=1.0, v_diseno=60,
                         reparto_recta=0.70, retornar_detalle=False):
    """
    Devuelve la pendiente transversal (%) de cada costado para cada abscisa,
    desarrollando el peralte según la formulación INVIAS.

    En recta rige el bombeo. El borde exterior asciende por la rampa hasta el
    peralte pleno; el borde interior conserva su bombeo hasta que el exterior
    lo iguala en magnitud, y a partir de ahí acompaña simétricamente el giro.

    Convención de signo: negativo = el borde cae respecto del eje.
    """
    abscisas = np.asarray(abscisas, dtype=float)
    b_izq = abs(float(bombeo_izq))
    b_der = abs(float(bombeo_der))

    m_izq = np.full(abscisas.shape, -b_izq, dtype=float)
    m_der = np.full(abscisas.shape, -b_der, dtype=float)
    detalle = []

    if df_reporte is None or len(df_reporte) == 0 or "Abs_PC (m)" not in df_reporte.columns:
        return (m_izq, m_der, pd.DataFrame(detalle)) if retornar_detalle else (m_izq, m_der)

    for _, r in df_reporte.iterrows():
        e = abs(float(r.get("Peralte (%)", 0.0)))
        pc = float(r["Abs_PC (m)"])
        pt = float(r["Abs_PT (m)"])
        sentido = str(r.get("Sentido", "Der"))
        # Curva a la derecha -> el exterior es el costado izquierdo
        exterior_es_izq = sentido.upper().startswith("D")
        b_ext = b_izq if exterior_es_izq else b_der
        b_int = b_der if exterior_es_izq else b_izq

        par = longitud_transicion_peralte(e, ancho_carril, n_carriles_giran, v_diseno, b_ext)
        L, N = par["L"], par["N"]
        if L <= 0:
            continue

        for i, s in enumerate(abscisas):
            m_ext = _rampa_borde_exterior(s, pc, pt, e, b_ext, L, N, reparto_recta)
            # Sólo se sobrescribe donde esta curva realmente actúa
            if abs(m_ext + b_ext) < 1e-9:
                continue
            m_int = -b_int if m_ext < b_int else -m_ext

            if exterior_es_izq:
                m_izq[i], m_der[i] = m_ext, m_int
            else:
                m_der[i], m_izq[i] = m_ext, m_int

        detalle.append({
            "Vértice (PI)": r.get("Vértice (PI)", ""),
            "Sentido": sentido,
            "Peralte e (%)": par["e"],
            "Bombeo (%)": par["bombeo"],
            "a = w·n (m)": par["a"],
            "bw": par["bw"],
            "Δs (%)": par["delta_s"],
            "Long. Transición L (m)": par["L"],
            "Long. Aplanamiento N (m)": par["N"],
            "Desarrollo total LT (m)": par["LT"],
            "Abscisa A entrada": formato_abscisa(max(pc - reparto_recta * L - N, 0.0)),
            "Abscisa E entrada": formato_abscisa(pc + (1 - reparto_recta) * L),
            "Abscisa E salida": formato_abscisa(pt - (1 - reparto_recta) * L),
            "Abscisa A salida": formato_abscisa(pt + reparto_recta * L + N),
        })

    m_izq, m_der = np.round(m_izq, 3), np.round(m_der, 3)
    if retornar_detalle:
        return m_izq, m_der, pd.DataFrame(detalle)
    return m_izq, m_der


def procesar_alineamiento_horizontal(df_pis, v_diseno=60, e_max=8.0):
    """
    Recibe un DataFrame con Puntos de Intersección (PI), incluyendo Elevaciones.
    Calcula Geometría horizontal, Peraltes y Geometría Vertical (Rasante).
    Mantiene 3 decimales estrictos en todas las exportaciones numéricas.

    Devuelve: (df_reporte_curvas, df_dibujo_eje, df_vertical)
    """
    df_pis = _sanear_pis(df_pis)

    if len(df_pis) < 2:
        raise ValueError("Se requieren al menos 2 PIs (Arranque y Llegada) para trazar un alineamiento.")

    f_transv = coeficiente_friccion(v_diseno)
    r_min = radio_minimo(v_diseno, e_max)

    reporte_curvas = []
    coordenadas_eje_e = []
    coordenadas_eje_n = []

    abscisas_pi = []
    cotas_pi = []
    pendientes_salida = []

    abscisa_actual = 0.0

    # El primer punto es el inicio (K0+000)
    e_ant, n_ant = float(df_pis.iloc[0]["Este"]), float(df_pis.iloc[0]["Norte"])
    cota_ant = float(df_pis.iloc[0]["Elevacion"])

    coordenadas_eje_e.append(e_ant)
    coordenadas_eje_n.append(n_ant)
    abscisas_pi.append(abscisa_actual)
    cotas_pi.append(cota_ant)

    for i in range(1, len(df_pis) - 1):
        pi_actual = df_pis.iloc[i]["PI"]
        e_pi = float(df_pis.iloc[i]["Este"])
        n_pi = float(df_pis.iloc[i]["Norte"])
        cota_pi = float(df_pis.iloc[i]["Elevacion"])
        radio = float(df_pis.iloc[i]["Radio"])

        e_sig, n_sig = float(df_pis.iloc[i + 1]["Este"]), float(df_pis.iloc[i + 1]["Norte"])

        # Geometría de entrada y salida
        az_ent, dist_ent = calcular_acimut_distancia(e_ant, n_ant, e_pi, n_pi)
        az_sal, dist_sal = calcular_acimut_distancia(e_pi, n_pi, e_sig, n_sig)

        # Ángulo de Deflexión
        delta_deg = az_sal - az_ent
        if delta_deg > 180:
            delta_deg -= 360
        if delta_deg < -180:
            delta_deg += 360

        sentido = "Der" if delta_deg > 0 else "Izq"
        delta_rad = np.radians(abs(delta_deg))

        if radio > 0 and abs(delta_deg) > 1e-6:
            # Elementos geométricos de la curva circular simple
            tangente = radio * np.tan(delta_rad / 2)
            longitud_curva = radio * delta_rad
            externa = radio * ((1 / np.cos(delta_rad / 2)) - 1)
            ordenada_media = radio * (1 - np.cos(delta_rad / 2))
            cuerda_larga = 2 * radio * np.sin(delta_rad / 2)
            grado_curvatura = np.degrees(2 * np.arcsin(5.0 / radio)) if radio >= 5.0 else 0.0

            # dist_ent ya viene descontada por la curva anterior porque
            # (e_ant, n_ant) es el PT precedente, no el PI precedente.
            if tangente > dist_ent:
                raise ValueError(
                    f"Radio excesivo en {pi_actual}: la tangente ({tangente:.3f} m) supera la longitud "
                    f"disponible de entrada ({dist_ent:.3f} m). Reduzca el radio o separe los vértices."
                )

            # Verificación de traslape con la curva siguiente
            radio_sig = float(df_pis.iloc[i + 1]["Radio"]) if (i + 2) < len(df_pis) else 0.0
            if radio_sig > 0:
                az_sig, _ = calcular_acimut_distancia(
                    e_sig, n_sig,
                    float(df_pis.iloc[i + 2]["Este"]), float(df_pis.iloc[i + 2]["Norte"]),
                )
                d_sig = az_sig - az_sal
                if d_sig > 180:
                    d_sig -= 360
                if d_sig < -180:
                    d_sig += 360
                tang_sig = radio_sig * np.tan(np.radians(abs(d_sig)) / 2)
                if (tangente + tang_sig) > dist_sal:
                    raise ValueError(
                        f"Traslape de curvas entre {pi_actual} y {df_pis.iloc[i + 1]['PI']}: la suma de "
                        f"tangentes ({tangente + tang_sig:.3f} m) supera la distancia entre vértices "
                        f"({dist_sal:.3f} m)."
                    )
            elif tangente > dist_sal:
                raise ValueError(
                    f"Radio excesivo en {pi_actual}: la tangente ({tangente:.3f} m) supera la "
                    f"distancia de salida ({dist_sal:.3f} m)."
                )

            # Estacionamiento sobre el eje curvo
            abs_pc = abscisa_actual + (dist_ent - tangente)
            abs_pt = abs_pc + longitud_curva
            # La abscisa del PI se mide sobre el eje: se acota dentro de la curva
            abs_pi = min(abs_pc + tangente, abs_pt)

            # Coordenadas exactas del PC y PT
            e_pc = e_ant + (dist_ent - tangente) * np.sin(np.radians(az_ent))
            n_pc = n_ant + (dist_ent - tangente) * np.cos(np.radians(az_ent))
            e_pt = e_pi + tangente * np.sin(np.radians(az_sal))
            n_pt = n_pi + tangente * np.cos(np.radians(az_sal))

            # Peralte teórico (INVIAS): e = (V^2/(127*R) - f) * 100
            peralte_calc = ((float(v_diseno) ** 2) / (127 * radio)) * 100 - (f_transv * 100)
            peralte_final = max(2.0, min(peralte_calc, float(e_max)))

            # Centro de la curva
            az_centro = az_ent + 90 if sentido == "Der" else az_ent - 90
            e_centro = e_pc + radio * np.sin(np.radians(az_centro))
            n_centro = n_pc + radio * np.cos(np.radians(az_centro))

            # Densificación vectorial del eje
            num_puntos = max(int(longitud_curva / 2), 10)
            angulos = np.linspace(
                np.radians(az_centro + 180),
                np.radians(az_centro + 180 + (abs(delta_deg) if sentido == "Der" else -abs(delta_deg))),
                num_puntos,
            )

            for ang in angulos:
                coordenadas_eje_e.append(e_centro + radio * np.sin(ang))
                coordenadas_eje_n.append(n_centro + radio * np.cos(ang))

            delta_dms = decimal_a_dms_string(abs(delta_deg)) + f" {sentido[0]}"

            # Pendiente de ENTRADA al vértice, medida sobre el EJE (coherente con
            # la rasante). La de salida se completa al final, cuando ya se conoce
            # la abscisa del vértice siguiente.
            dx_absc = abs_pi - abscisas_pi[-1]
            dz_tramo = cota_pi - cota_ant
            m_tramo = (dz_tramo / dx_absc * 100) if dx_absc > 1e-9 else 0.0

            reporte_curvas.append({
                "Vértice (PI)": pi_actual,
                "Deflexión (Δ)": delta_dms,
                "Radio (m)": round(radio, 3),
                "Grado Curv. (Gc)": round(grado_curvatura, 3),
                "Tangente (m)": round(tangente, 3),
                "Long. Curva (m)": round(longitud_curva, 3),
                "Externa (m)": round(externa, 3),
                "Ord. Media (m)": round(ordenada_media, 3),
                "Cuerda Larga (m)": round(cuerda_larga, 3),
                "Peralte (%)": round(peralte_final, 3),
                "Pend. Entrada (%)": round(m_tramo, 3),
                "Pend. Salida (%)": 0.000,   # se completa al cerrar el alineamiento
                "Abscisa PC": formato_abscisa(abs_pc),
                "Abscisa PI": formato_abscisa(abs_pi),
                "Abscisa PT": formato_abscisa(abs_pt),
                # Valores numéricos necesarios para aplicar el peralte en las
                # secciones transversales (la versión de texto no es operable)
                "Abs_PC (m)": round(abs_pc, 3),
                "Abs_PT (m)": round(abs_pt, 3),
                "Sentido": sentido,
                "E_PI (m)": round(e_pi, 3), "N_PI (m)": round(n_pi, 3),
                "E_PC (m)": round(e_pc, 3), "N_PC (m)": round(n_pc, 3),
                "E_PT (m)": round(e_pt, 3), "N_PT (m)": round(n_pt, 3),
                "Cumple R_min": "NO" if radio < r_min else "SI",
            })

            abscisas_pi.append(round(abs_pi, 3))
            cotas_pi.append(round(cota_pi, 3))
            abscisa_actual = abs_pt
            e_ant, n_ant = e_pt, n_pt
            cota_ant = cota_pi

        else:
            # Vértice sin curva: continuidad en tangente
            abscisa_actual += dist_ent
            abscisas_pi.append(round(abscisa_actual, 3))
            cotas_pi.append(round(cota_pi, 3))
            e_ant, n_ant = e_pi, n_pi
            cota_ant = cota_pi
            coordenadas_eje_e.append(e_pi)
            coordenadas_eje_n.append(n_pi)

    # Último PI (Llegada)
    e_final, n_final = float(df_pis.iloc[-1]["Este"]), float(df_pis.iloc[-1]["Norte"])
    cota_final = float(df_pis.iloc[-1]["Elevacion"])
    az_ent, dist_final = calcular_acimut_distancia(e_ant, n_ant, e_final, n_final)

    abs_pi_final = abscisa_actual + dist_final

    abscisas_pi.append(round(abs_pi_final, 3))
    cotas_pi.append(round(cota_final, 3))
    coordenadas_eje_e.append(e_final)
    coordenadas_eje_n.append(n_final)

    # Garantía de monotonía estricta (protege la interpolación de la rasante)
    for i in range(1, len(abscisas_pi)):
        if abscisas_pi[i] <= abscisas_pi[i - 1]:
            abscisas_pi[i] = round(abscisas_pi[i - 1] + 0.001, 3)

    # Cuadro Rasante Vertical
    longitudes_tramo = []
    for i in range(len(abscisas_pi) - 1):
        dx = abscisas_pi[i + 1] - abscisas_pi[i]
        dz = cotas_pi[i + 1] - cotas_pi[i]
        m = (dz / dx * 100) if dx > 1e-9 else 0.0
        pendientes_salida.append(round(m, 3))
        longitudes_tramo.append(round(dx, 3))

    pendientes_salida.append(0.000)  # Ajuste de cierre final
    longitudes_tramo.append(0.000)

    # Pendiente de ENTRADA a cada PIV: es la de salida del vértice anterior.
    pendientes_entrada = [0.000] + pendientes_salida[:-1]

    abs_format_list = [formato_abscisa(a) for a in abscisas_pi]

    df_reporte = pd.DataFrame(reporte_curvas)

    # Se completa la pendiente de salida de cada curva a partir de la rasante,
    # de modo que el cuadro de curvas y la tabla de PIVs no puedan discrepar.
    if not df_reporte.empty:
        pos_piv = {nombre: i for i, nombre in enumerate(df_pis["PI"].tolist())}
        df_reporte["Pend. Salida (%)"] = [
            pendientes_salida[pos_piv[v]] if v in pos_piv else 0.000
            for v in df_reporte["Vértice (PI)"]
        ]
    df_dibujo = pd.DataFrame({"Este": coordenadas_eje_e, "Norte": coordenadas_eje_n})

    df_vertical = pd.DataFrame({
        "Vértice PIV": df_pis["PI"].tolist(),
        "Abscisa": abscisas_pi,
        "Abscisa (Formato)": abs_format_list,
        "Elevación (Z)": cotas_pi,
        "Pendiente Entrada (%)": pendientes_entrada,
        "Pendiente Salida (%)": pendientes_salida,
        "Longitud Tramo (m)": longitudes_tramo,
    })

    return df_reporte, df_dibujo, df_vertical


# ===================================================================
# CURVAS VERTICALES PARABÓLICAS — INVIAS 2008, capítulo 4
# -------------------------------------------------------------------
# Los tramos consecutivos de rasante se enlazan con parábolas de eje
# vertical cuando la diferencia algebraica de pendientes supera el 1%
# en carreteras pavimentadas (2% en las demás).
#
# Parámetro de curvatura:      K = L / |A|
#   L = longitud de la curva vertical (m)
#   A = diferencia algebraica de pendientes (%),  A = g2 - g1
#
# Ecuación de la parábola simétrica, con x medido desde el PCV:
#       y(x) = y_PCV + (g1/100)·x + (A / (200·L))·x²
#
# Externa (corrimiento vertical en el PIV):   E = |A|·L / 800
#
# CRITERIOS DE LONGITUD MÍNIMA
#   Seguridad (visibilidad de parada), caso DP < L, que es el adoptado
#   por el Manual porque cubre al otro:
#       Convexa:  L = A·DP² / (100·(√(2·h1) + √(2·h2))²)
#                 con h1 = 1.08 m (ojo del conductor) y h2 = 0.60 m
#                 (obstáculo)  ->  L = A·DP² / 658.4
#       Cóncava:  L = A·DP² / (122 + 3.5·DP)
#                 (faros a 0.60 m y divergencia de 1°)
#   Operación:  L = 0.6 · VCV   (evita el cambio súbito de pendiente)
#   Drenaje:    K ≤ 50 en curvas en zona de corte
# ===================================================================

# Alturas normativas para la visibilidad de parada
_H1_OJO = 1.08
_H2_OBSTACULO = 0.60
# (√(2·1.08) + √(2·0.60))² = 658.4 al pasar A a porcentaje
_CTE_CONVEXA = 100.0 * (np.sqrt(2 * _H1_OJO) + np.sqrt(2 * _H2_OBSTACULO)) ** 2

# Coeficiente de fricción longitudinal para la distancia de parada
_V_FRIC_L = [30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
_F_LONGITUDINAL = [0.400, 0.380, 0.360, 0.340, 0.325, 0.310, 0.305, 0.300, 0.295, 0.290]

# K máximo por drenaje (AASHTO 2004, adoptado por el Manual)
K_MAX_DRENAJE = 50.0


def coeficiente_friccion_longitudinal(v_especifica):
    """Coeficiente de fricción longitudinal para la velocidad dada."""
    return float(np.interp(float(v_especifica), _V_FRIC_L, _F_LONGITUDINAL))


# Distancia de visibilidad de parada tabulada (Manual INVIAS, terreno plano)
_V_DP = [30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
_DP_TABLA = [35, 50, 65, 85, 105, 130, 160, 185, 220, 250]


def distancia_visibilidad_parada(v_especifica, pendiente=0.0, tiempo_reaccion=2.5,
                                 usar_tabla=True):
    """
    Distancia de visibilidad de parada (m).

    Por defecto se toman los valores TABULADOS del Manual, que son los
    que dan origen a los K mínimos publicados. Cuando se declara una
    pendiente distinta de cero, o se pide explícitamente, se emplea la
    expresión analítica:

        DP = (V·t)/3.6 + V² / (254·(f_l + i/100))

    donde i es la pendiente longitudinal en % (positiva en ascenso, que
    acorta la distancia; negativa en descenso, que la alarga).
    """
    v = float(v_especifica)
    i = float(pendiente)

    if usar_tabla and abs(i) < 1e-9:
        return float(np.interp(v, _V_DP, _DP_TABLA))

    f_l = coeficiente_friccion_longitudinal(v)
    denom = 254.0 * (f_l + i / 100.0)
    if denom <= 0:
        denom = 254.0 * f_l          # descenso muy fuerte: se acota
    return (v * float(tiempo_reaccion)) / 3.6 + (v ** 2) / denom


def longitud_minima_curva_vertical(a_abs, v_especifica, tipo, dp=None):
    """
    Longitud mínima (m) por seguridad y por operación.
    Devuelve (L_seguridad, L_operacion, DP, K_min_seguridad).
    """
    a_abs = abs(float(a_abs))
    dp = float(dp) if dp is not None else distancia_visibilidad_parada(v_especifica)

    if str(tipo).lower().startswith("conv"):
        k_min = (dp ** 2) / _CTE_CONVEXA
    else:
        k_min = (dp ** 2) / (122.0 + 3.5 * dp)

    l_seguridad = k_min * a_abs
    l_operacion = 0.6 * float(v_especifica)
    return l_seguridad, l_operacion, dp, k_min


def _redondear_arriba(valor, paso):
    paso = float(paso)
    if paso <= 0:
        return float(valor)
    return float(np.ceil(float(valor) / paso) * paso)


def calcular_curvas_verticales(df_vertical, v_diseno=60, pavimentada=True,
                               longitudes_adoptadas=None, redondeo=10.0,
                               dp_manual=None):
    """
    Calcula la curva vertical parabólica simétrica de cada PIV interior.

    df_vertical         : tabla de PIVs de procesar_alineamiento_horizontal
    longitudes_adoptadas: dict {nombre_PIV: L} para imponer longitudes
    redondeo            : múltiplo al que se redondea L hacia arriba
    dp_manual           : distancia de visibilidad de parada impuesta

    Devuelve un DataFrame con la memoria de cálculo de cada curva.
    """
    if df_vertical is None or len(df_vertical) < 3:
        return pd.DataFrame()

    df = df_vertical.reset_index(drop=True)
    umbral_a = 1.0 if pavimentada else 2.0
    longitudes_adoptadas = longitudes_adoptadas or {}

    filas = []
    for i in range(1, len(df) - 1):
        nombre = df.loc[i, "Vértice PIV"]
        x_piv = float(df.loc[i, "Abscisa"])
        y_piv = float(df.loc[i, "Elevación (Z)"])
        g1 = float(df.loc[i - 1, "Pendiente Salida (%)"])
        g2 = float(df.loc[i, "Pendiente Salida (%)"])
        a_alg = g2 - g1

        # Espacio disponible hasta los vértices contiguos
        tang_ant = x_piv - float(df.loc[i - 1, "Abscisa"])
        tang_sig = float(df.loc[i + 1, "Abscisa"]) - x_piv
        l_max_geom = 2.0 * min(tang_ant, tang_sig)

        if abs(a_alg) < umbral_a:
            filas.append({
                "Vértice PIV": nombre,
                "Abscisa PIV": round(x_piv, 3),
                "Cota PIV": round(y_piv, 3),
                "Pend. Entrada (%)": round(g1, 3),
                "Pend. Salida (%)": round(g2, 3),
                "A (%)": round(a_alg, 3),
                "Tipo": "Sin curva",
                "DP (m)": 0.0, "K mín": 0.0,
                "L seguridad (m)": 0.0, "L operación (m)": 0.0,
                "L adoptada (m)": 0.0, "K adoptado": 0.0,
                "Abscisa PCV": "", "Abscisa PTV": "",
                "Cota PCV": round(y_piv, 3), "Cota PTV": round(y_piv, 3),
                "Externa E (m)": 0.0,
                "Abscisa crítica": "", "Cota crítica": "",
                "Cumple drenaje": "N/A",
                "Observación": f"|A| = {abs(a_alg):.3f}% < {umbral_a:.0f}%: no requiere curva vertical.",
            })
            continue

        tipo = "Convexa" if a_alg < 0 else "Cóncava"
        l_seg, l_ope, dp, k_min = longitud_minima_curva_vertical(
            a_alg, v_diseno, tipo, dp=dp_manual)

        if nombre in longitudes_adoptadas and longitudes_adoptadas[nombre]:
            l_adop = float(longitudes_adoptadas[nombre])
            origen = "impuesta por el proyectista"
        else:
            l_adop = _redondear_arriba(max(l_seg, l_ope), redondeo)
            origen = "mínima normativa redondeada"

        obs = []
        if l_adop > l_max_geom > 0:
            l_adop = float(np.floor(l_max_geom / max(redondeo, 1e-9)) * max(redondeo, 1e-9))
            l_adop = max(l_adop, 0.0)
            obs.append(f"Longitud recortada a {l_adop:.3f} m por traslape con los "
                       f"vértices contiguos: revise la separación entre PIV.")
        if l_adop < l_seg - 1e-6:
            obs.append(f"No cumple el criterio de seguridad (exige {l_seg:.3f} m).")
        if l_adop < l_ope - 1e-6:
            obs.append(f"No cumple el criterio de operación (exige {l_ope:.3f} m).")

        k_adop = l_adop / abs(a_alg) if abs(a_alg) > 1e-9 else 0.0
        cumple_dren = "SI" if k_adop <= K_MAX_DRENAJE else "NO"
        if cumple_dren == "NO":
            obs.append(f"K = {k_adop:.3f} supera el máximo de {K_MAX_DRENAJE:.0f} "
                       f"por drenaje en zona de corte.")

        x_pcv = x_piv - l_adop / 2.0
        x_ptv = x_piv + l_adop / 2.0
        y_pcv = y_piv - (g1 / 100.0) * (l_adop / 2.0)
        y_ptv = y_piv + (g2 / 100.0) * (l_adop / 2.0)
        externa = abs(a_alg) * l_adop / 800.0

        # Punto crítico (cresta o batea): dy/dx = 0
        x_crit_txt, y_crit_txt = "", ""
        if abs(a_alg) > 1e-9:
            x_rel = -g1 * l_adop / a_alg
            if 0.0 < x_rel < l_adop:
                y_crit = y_pcv + (g1 / 100.0) * x_rel + (a_alg / (200.0 * l_adop)) * x_rel ** 2
                x_crit_txt = formato_abscisa(x_pcv + x_rel)
                y_crit_txt = round(y_crit, 3)

        filas.append({
            "Vértice PIV": nombre,
            "Abscisa PIV": round(x_piv, 3),
            "Cota PIV": round(y_piv, 3),
            "Pend. Entrada (%)": round(g1, 3),
            "Pend. Salida (%)": round(g2, 3),
            "A (%)": round(a_alg, 3),
            "Tipo": tipo,
            "DP (m)": round(dp, 3),
            "K mín": round(k_min, 3),
            "L seguridad (m)": round(l_seg, 3),
            "L operación (m)": round(l_ope, 3),
            "L adoptada (m)": round(l_adop, 3),
            "K adoptado": round(k_adop, 3),
            "Abscisa PCV": formato_abscisa(x_pcv),
            "Abscisa PTV": formato_abscisa(x_ptv),
            "Cota PCV": round(y_pcv, 3),
            "Cota PTV": round(y_ptv, 3),
            "Externa E (m)": round(externa, 3),
            "Abscisa crítica": x_crit_txt,
            "Cota crítica": y_crit_txt,
            "Cumple drenaje": cumple_dren,
            "Observación": " ".join(obs) if obs else f"Curva {tipo.lower()} conforme ({origen}).",
            # Auxiliares numéricos para el cálculo de la rasante
            "_x_pcv": x_pcv, "_x_ptv": x_ptv, "_y_pcv": y_pcv,
            "_g1": g1, "_a": a_alg, "_L": l_adop,
        })

    return pd.DataFrame(filas)


def cota_rasante(abscisas, df_vertical, df_curvas_verticales=None):
    """
    Elevación de la rasante en cada abscisa.

    Sin curvas verticales interpola linealmente entre PIVs. Con ellas,
    sustituye el tramo comprendido entre PCV y PTV por la parábola
    correspondiente, de modo que el perfil, las cotas de diseño y el
    cubicaje reflejen el acuerdo vertical real y no el vértice anguloso.
    """
    abscisas = np.asarray(abscisas, dtype=float)
    df_v = df_vertical.sort_values("Abscisa")
    z = np.interp(abscisas, df_v["Abscisa"].to_numpy(dtype=float),
                  df_v["Elevación (Z)"].to_numpy(dtype=float))

    if df_curvas_verticales is None or df_curvas_verticales.empty:
        return z
    if "_L" not in df_curvas_verticales.columns:
        return z

    for _, r in df_curvas_verticales.iterrows():
        L = float(r["_L"])
        if L <= 0:
            continue
        x_pcv, x_ptv = float(r["_x_pcv"]), float(r["_x_ptv"])
        y_pcv, g1, a = float(r["_y_pcv"]), float(r["_g1"]), float(r["_a"])

        dentro = (abscisas >= x_pcv) & (abscisas <= x_ptv)
        if not np.any(dentro):
            continue
        x_rel = abscisas[dentro] - x_pcv
        z[dentro] = y_pcv + (g1 / 100.0) * x_rel + (a / (200.0 * L)) * x_rel ** 2

    return z
