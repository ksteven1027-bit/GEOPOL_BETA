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


def peraltes_por_abscisa(abscisas, df_reporte, bombeo_izq=-2.0, bombeo_der=-2.0,
                         long_transicion=30.0):
    """
    Devuelve la pendiente transversal (%) de cada costado para cada abscisa.

    En recta rige el bombeo. Entre PC y PT rige el peralte pleno de la curva:
    toda la sección bascula hacia el interior, de modo que el borde exterior
    sube (+e) y el interior baja (-e) respecto del eje. Entre ambos estados se
    interpola linealmente a lo largo de 'long_transicion' metros antes del PC y
    después del PT (desarrollo del peralte).

    Convención de signo: negativo = el borde cae respecto del eje.
    """
    abscisas = np.asarray(abscisas, dtype=float)
    bombeo_izq = float(bombeo_izq)
    bombeo_der = float(bombeo_der)

    m_izq = np.full(abscisas.shape, bombeo_izq, dtype=float)
    m_der = np.full(abscisas.shape, bombeo_der, dtype=float)

    if df_reporte is None or len(df_reporte) == 0 or "Abs_PC (m)" not in df_reporte.columns:
        return m_izq, m_der

    lt = max(float(long_transicion), 1e-6)

    for _, r in df_reporte.iterrows():
        e = abs(float(r.get("Peralte (%)", 0.0)))
        pc = float(r["Abs_PC (m)"])
        pt = float(r["Abs_PT (m)"])
        sentido = str(r.get("Sentido", "Der"))

        # Curva a la derecha -> interior derecho: cae la derecha, sube la izquierda
        if sentido.upper().startswith("D"):
            e_izq, e_der = e, -e
        else:
            e_izq, e_der = -e, e

        # Factor de desarrollo: 0 en recta, 1 en peralte pleno
        factor = np.zeros(abscisas.shape, dtype=float)
        pleno = (abscisas >= pc) & (abscisas <= pt)
        entrada = (abscisas >= pc - lt) & (abscisas < pc)
        salida = (abscisas > pt) & (abscisas <= pt + lt)

        factor[pleno] = 1.0
        factor[entrada] = (abscisas[entrada] - (pc - lt)) / lt
        factor[salida] = ((pt + lt) - abscisas[salida]) / lt

        afectadas = factor > 0
        m_izq[afectadas] = bombeo_izq + factor[afectadas] * (e_izq - bombeo_izq)
        m_der[afectadas] = bombeo_der + factor[afectadas] * (e_der - bombeo_der)

    return np.round(m_izq, 3), np.round(m_der, 3)


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

            # Pendiente del tramo medida sobre el EJE (coherente con la rasante)
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
                "Pendiente (%)": round(m_tramo, 3),
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

    abs_format_list = [formato_abscisa(a) for a in abscisas_pi]

    df_reporte = pd.DataFrame(reporte_curvas)
    df_dibujo = pd.DataFrame({"Este": coordenadas_eje_e, "Norte": coordenadas_eje_n})

    df_vertical = pd.DataFrame({
        "Vértice PIV": df_pis["PI"].tolist(),
        "Abscisa": abscisas_pi,
        "Abscisa (Formato)": abs_format_list,
        "Elevación (Z)": cotas_pi,
        "Pendiente Salida (%)": pendientes_salida,
        "Longitud Tramo (m)": longitudes_tramo,
    })

    return df_reporte, df_dibujo, df_vertical
