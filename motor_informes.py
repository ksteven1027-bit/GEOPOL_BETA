# ===================================================================
# MOTOR DE GENERACIÓN DE INFORMES TÉCNICOS EN LATEX
# Desarrollado para Geoportal Web (GeoPol)
# Universidad Distrital Francisco José de Caldas
# -------------------------------------------------------------------
# Módulo único y autocontenido. Organización interna:
#
#   BLOQUE 1  Constantes geodésicas y utilidades angulares
#   BLOQUE 2  Análisis de poligonal (tolerancias, factor de escala,
#             proyecciones, área de Gauss)
#   BLOQUE 3  Análisis de nivelación (tolerancias, cuadre de cartera,
#             colimación, distribución del error, pendientes)
#   BLOQUE 4  Análisis de volúmenes (esponjamiento, prismoidal,
#             puntos de paso, curva masa, acarreo)
#   BLOQUE 5  Renderizado LaTeX (escapado, tablas, cajas, KPIs)
#   BLOQUE 6  Preámbulo y portada
#   BLOQUE 7  Generadores de informe (poligonal, nivelación, volúmenes)
#   BLOQUE 8  Compilación a PDF
#
# Uso mínimo:
#   codigo = generar_reporte_poligonal_latex(df_campo, df_ajuste,
#                metricas, "Poligonal Cerrada", autores, tutor)
#   pdf, ruta, msg = compilar_latex_a_pdf(codigo, "Reportes_PDF",
#                                         "Informe_Poligonal")
# ===================================================================
import math
import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd


# -------------------------------------------------------------------
# CONSTANTES GEODÉSICAS
# -------------------------------------------------------------------
GRS80_A = 6378137.0                 # Semieje mayor GRS80 / WGS84 [m]
GRS80_F = 1.0 / 298.257222101       # Achatamiento GRS80
GRS80_E2 = 2 * GRS80_F - GRS80_F ** 2

# MAGNA-SIRGAS / Origen Nacional (EPSG:9377) - Transversa de Mercator
EPSG_9377 = {
    "nombre": "MAGNA-SIRGAS / Origen-Nacional",
    "epsg": 9377,
    "lat_origen": 4.0,          # grados N
    "meridiano_central": -73.0,  # grados
    "k0": 0.9992,
    "falso_este": 5_000_000.0,
    "falso_norte": 2_000_000.0,
}

M2_POR_FANEGADA = 6400.0    # Fanegada catastral (Cundinamarca / Bogotá)
M2_POR_HECTAREA = 10000.0


# ===================================================================
# 1. UTILIDADES ANGULARES
# ===================================================================
# =================================================================
# BLOQUE 0 - DETECCIÓN DE CAPACIDADES DE LATEX
# =================================================================
# En un servidor con TeX Live mínimo (Streamlit Cloud, contenedores
# ligeros) faltan paquetes y la compilación aborta con
# "File `siunitx.sty' not found". En vez de fallar, el motor detecta
# qué hay instalado y genera un .tex adaptado: si falta siunitx
# formatea los números en Python, si falta tcolorbox dibuja las cajas
# con xcolor, etc. El informe pierde algo de acabado pero SIEMPRE sale.
#
# Para el acabado completo, instala los paquetes que indica
# diagnostico_latex()["packages_txt"].
# =================================================================

# .sty -> paquete apt de Debian/Ubuntu que lo provee
_PAQUETES_APT = {
    "siunitx": "texlive-science",
    "tcolorbox": "texlive-latex-extra",
    "titlesec": "texlive-latex-extra",
    "enumitem": "texlive-latex-extra",
    "csquotes": "texlive-latex-extra",
    "lastpage": "texlive-latex-extra",
    "threeparttable": "texlive-latex-extra",
    "transparent": "texlive-latex-extra",
    "microtype": "texlive-latex-recommended",
    "booktabs": "texlive-latex-recommended",
    "eso-pic": "texlive-latex-recommended",
    "caption": "texlive-latex-recommended",
    "xcolor": "texlive-latex-recommended",
    "float": "texlive-latex-recommended",
    "tikz": "texlive-pictures",
    "lmodern": "lmodern",
}

# Sin estos el informe no se puede generar de ninguna forma
_IMPRESCINDIBLES = ("geometry", "graphicx", "fancyhdr", "longtable", "xcolor")

_CAPACIDADES = None


def capacidades_latex(refrescar=False, forzar=None):
    """
    Devuelve {'siunitx': True, 'tcolorbox': False, ...}.
    Se consulta una sola vez y se cachea.

    forzar: dict para pruebas, p.ej. {'siunitx': False} simula su ausencia.
    """
    global _CAPACIDADES
    if forzar is not None:
        base = dict(_CAPACIDADES or {})
        if not base:
            base = capacidades_latex()
        base.update(forzar)
        return base
    if _CAPACIDADES is not None and not refrescar:
        return _CAPACIDADES

    paquetes = list(_PAQUETES_APT) + list(_IMPRESCINDIBLES)
    disponibles = {p: False for p in paquetes}

    if shutil.which("kpsewhich"):
        try:
            # Una sola llamada para todos: kpsewhich acepta varios argumentos
            proc = subprocess.run(
                ["kpsewhich"] + [f"{p}.sty" for p in paquetes],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30)
            encontrados = {os.path.basename(l).lower()
                           for l in proc.stdout.splitlines() if l.strip()}
            for p in paquetes:
                disponibles[p] = f"{p}.sty".lower() in encontrados
        except Exception:
            pass

    _CAPACIDADES = disponibles
    return _CAPACIDADES


def diagnostico_latex(caps=None):
    """
    Informe legible del estado de LaTeX. Pensado para mostrarlo en la
    interfaz de Streamlit cuando la compilación falla o se degrada.
    """
    caps = caps or capacidades_latex()
    faltan = sorted(p for p, ok in caps.items() if not ok)
    criticos = [p for p in faltan if p in _IMPRESCINDIBLES]
    apt = sorted({_PAQUETES_APT[p] for p in faltan if p in _PAQUETES_APT})

    base_apt = ["texlive-latex-base", "texlive-latex-recommended",
                "texlive-lang-spanish", "texlive-fonts-recommended"]
    recomendado = sorted(set(base_apt + apt + ["texlive-latex-extra",
                                               "texlive-science",
                                               "texlive-pictures", "lmodern"]))

    if not faltan:
        mensaje = "Instalación de LaTeX completa: el informe saldrá con el acabado íntegro."
    elif criticos:
        mensaje = ("Faltan paquetes imprescindibles (" + ", ".join(criticos) +
                   "). No es posible generar el PDF.")
    else:
        mensaje = ("Faltan " + str(len(faltan)) + " paquetes opcionales (" +
                   ", ".join(faltan) + "). El informe se generará en modo "
                   "compatible, con acabado reducido.")

    return {
        "pdflatex": shutil.which("pdflatex") is not None,
        "disponibles": sorted(p for p, ok in caps.items() if ok),
        "faltantes": faltan,
        "criticos": criticos,
        "apt_faltantes": apt,
        "mensaje": mensaje,
        "packages_txt": "\n".join(recomendado) + "\n",
    }


# -----------------------------------------------------------------
# Degradación del código LaTeX cuando faltan paquetes
# -----------------------------------------------------------------
def _num_es(texto):
    """1234.5678 -> 1.234,5678 (formato colombiano, sin siunitx)."""
    t = str(texto).strip()
    m = re.fullmatch(r"([+-]?)(\d+)(?:\.(\d+))?", t)
    if not m:
        return t
    signo, ent, dec = m.group(1), m.group(2), m.group(3)
    ent_fmt = f"{int(ent):,}".replace(",", ".")
    return signo + ent_fmt + ("," + dec if dec else "")


# El orden importa: las unidades compuestas se resuelven primero
_UNIDADES_SIN_SIUNITX = [
    (r"\cubic\metre", r"m\textsuperscript{3}"),
    (r"\square\metre", r"m\textsuperscript{2}"),
    (r"\milli\metre", "mm"),
    (r"\kilo\metre", "km"),
    (r"\centi\metre", "cm"),
    (r"\metre", "m"),
    (r"\percent", r"\%"),
    (r"\degree", r"\textdegree{}"),
]


def _degradar_latex(tex, caps=None):
    """
    Adapta el código generado a lo que el servidor tiene instalado.
    Se aplica al final de cada generador de informe.
    """
    caps = caps or capacidades_latex()

    if not caps.get("siunitx", False):
        def _si(m):
            valor, unidad = m.group(1), m.group(2)
            for cmd, txt in _UNIDADES_SIN_SIUNITX:
                unidad = unidad.replace(cmd, txt)
            unidad = unidad.strip()
            return _num_es(valor) + (r"\," + unidad if unidad else "")
        tex = re.sub(r"\\SI\{([^{}]*)\}\{([^{}]*)\}", _si, tex)
        tex = re.sub(r"\\num\{([^{}]*)\}", lambda m: _num_es(m.group(1)), tex)

    if not caps.get("enumitem", False):
        # \begin{itemize}[leftmargin=1.2em] -> \begin{itemize}
        tex = re.sub(r"(\\begin\{(?:itemize|enumerate|description)\})\[[^\]]*\]",
                     r"\1", tex)

    return tex


# =================================================================
# BLOQUE 1 - UTILIDADES ANGULARES
# =================================================================
def dms_a_segundos(valor):
    """
    Convierte un ángulo a segundos de arco. Acepta:
      - float/int  -> se interpreta como GRADOS decimales
      - "12 34 56.7", "12-34-56.7", "12:34:56.7"
      - "12°34'56.7\"" (con o sin símbolos)
    Devuelve float (segundos). Conserva el signo.
    """
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float, np.number)):
        return float(valor) * 3600.0

    txt = str(valor).strip()
    if not txt:
        return 0.0
    signo = -1.0 if txt.lstrip().startswith("-") else 1.0
    # Normaliza cualquier separador a espacio
    limpio = (txt.replace("°", " ").replace("º", " ").replace("'", " ")
                 .replace('"', " ").replace("’", " ").replace("”", " ")
                 .replace("-", " ").replace(":", " ").replace("d", " ")
                 .replace("m", " ").replace("s", " "))
    partes = [p for p in limpio.split() if p]
    try:
        nums = [abs(float(p)) for p in partes]
    except ValueError:
        return 0.0
    if not nums:
        return 0.0
    g = nums[0] if len(nums) > 0 else 0.0
    m = nums[1] if len(nums) > 1 else 0.0
    s = nums[2] if len(nums) > 2 else 0.0
    if len(nums) == 1:
        # Un solo número: se asume grados decimales
        return signo * g * 3600.0
    return signo * (g * 3600.0 + m * 60.0 + s)


def segundos_a_dms(segundos, decimales=1):
    """Formatea segundos de arco como G° MM' SS.s\" (texto plano, sin LaTeX)."""
    signo = "-" if segundos < 0 else ""
    seg = abs(float(segundos))
    g = int(seg // 3600)
    m = int((seg - g * 3600) // 60)
    s = seg - g * 3600 - m * 60
    return f"{signo}{g}° {m:02d}' {s:0{4 + decimales}.{decimales}f}\""


# ===================================================================
# 2. POLIGONAL: TOLERANCIAS Y DICTAMEN
# ===================================================================
# =================================================================
# BLOQUE 2 - ANÁLISIS DE POLIGONAL
# =================================================================
def tolerancia_angular(precision_equipo_seg, n_vertices, factor=2.0):
    """
    Tolerancia angular Ta = k * a * sqrt(n)
      precision_equipo_seg : precisión angular nominal del equipo ["], p.ej. 5
      n_vertices           : número de vértices (estaciones) del circuito
      factor k             : 1.0 exigente, 2.0 estándar en obra civil, 3.0 expedito
    """
    n = max(int(n_vertices), 1)
    return float(factor) * float(precision_equipo_seg) * math.sqrt(n)


def evaluar_cierre_angular(err_angular, precision_equipo_seg=5.0,
                           n_vertices=1, factor=2.0):
    """
    Compara el error angular observado contra la tolerancia calculada.
    'err_angular' puede venir como string DMS o como grados decimales.
    """
    err_seg = dms_a_segundos(err_angular)
    tol_seg = tolerancia_angular(precision_equipo_seg, n_vertices, factor)
    cumple = abs(err_seg) <= tol_seg
    razon = abs(err_seg) / tol_seg if tol_seg > 0 else float("inf")
    return {
        "error_seg": err_seg,
        "error_dms": segundos_a_dms(err_seg),
        "tolerancia_seg": tol_seg,
        "tolerancia_dms": segundos_a_dms(tol_seg),
        "cumple": cumple,
        "razon_uso": razon,          # <1 cumple; 0.5 = usa la mitad de la tolerancia
        "estado": "ok" if razon <= 0.7 else ("alerta" if cumple else "critico"),
        "formula": r"T_a = k \cdot a \sqrt{n}",
        "parametros": {"k": factor, "a": precision_equipo_seg, "n": int(n_vertices)},
    }


def evaluar_cierre_lineal(err_lineal, perimetro, precision_exigida=10000):
    """
    Evalúa el cierre lineal contra una precisión relativa exigida (1:P).
    Devuelve también la tolerancia lineal equivalente en metros.
    """
    perimetro = float(perimetro)
    tol_m = perimetro / float(precision_exigida) if precision_exigida > 0 else 0.0
    prec_obtenida = (perimetro / abs(err_lineal)) if err_lineal else float("inf")
    cumple = abs(err_lineal) <= tol_m
    return {
        "error_m": float(err_lineal),
        "tolerancia_m": tol_m,
        "precision_obtenida": prec_obtenida,
        "precision_exigida": precision_exigida,
        "cumple": cumple,
        "estado": "ok" if cumple else "critico",
    }


def azimut_error_cierre(err_e, err_n):
    """
    Azimut (desde el Norte, sentido horario) del vector de error de cierre.
    Indica la DIRECCIÓN del error: un lado con azimut similar es sospechoso
    de tener la distancia mal medida.
    """
    if abs(err_e) < 1e-12 and abs(err_n) < 1e-12:
        return {"azimut_grados": None, "azimut_dms": "---", "magnitud": 0.0}
    az = math.degrees(math.atan2(float(err_e), float(err_n))) % 360.0
    mag = math.hypot(float(err_e), float(err_n))
    return {
        "azimut_grados": az,
        "azimut_dms": segundos_a_dms(az * 3600.0),
        "magnitud": mag,
    }


def lado_sospechoso(err_e, err_n, azimutes_lados, tolerancia_grados=8.0):
    """
    azimutes_lados: dict {nombre_lado: azimut_en_grados}
    Devuelve los lados cuyo azimut (o su recíproco) coincide con la dirección
    del error de cierre. Técnica clásica de detección de error de distancia.
    """
    info = azimut_error_cierre(err_e, err_n)
    if info["azimut_grados"] is None or not azimutes_lados:
        return []
    az_err = info["azimut_grados"]
    candidatos = []
    for nombre, az in azimutes_lados.items():
        for az_test in (float(az) % 360.0, (float(az) + 180.0) % 360.0):
            dif = abs((az_test - az_err + 180.0) % 360.0 - 180.0)
            if dif <= tolerancia_grados:
                candidatos.append({"lado": nombre, "azimut": float(az), "desviacion": dif})
                break
    return sorted(candidatos, key=lambda d: d["desviacion"])


# ===================================================================
# 3. FACTOR DE ESCALA COMBINADO (crítico para EPSG:9377)
# ===================================================================
def radio_medio_curvatura(lat_grados):
    """Radio medio de curvatura Rm = sqrt(M*N) del elipsoide GRS80."""
    lat = math.radians(float(lat_grados))
    s2 = math.sin(lat) ** 2
    w = math.sqrt(1 - GRS80_E2 * s2)
    N = GRS80_A / w                              # radio primer vertical
    M = GRS80_A * (1 - GRS80_E2) / (w ** 3)      # radio meridiano
    return math.sqrt(M * N)


def factor_escala_combinado(este, altura_elipsoidal, lat_grados=4.0, proy=EPSG_9377):
    """
    Factor combinado = factor de escala de cuadrícula x factor de elevación.
    Convierte DISTANCIA DE TERRENO -> DISTANCIA DE CUADRÍCULA:
        D_cuadricula = D_terreno * factor_combinado

    este                : coordenada Este de la zona de trabajo [m]
    altura_elipsoidal   : altura sobre el elipsoide [m] (h = H + N_ondulacion)
    """
    Rm = radio_medio_curvatura(lat_grados)
    x = (float(este) - proy["falso_este"]) / proy["k0"]
    k_cuadricula = proy["k0"] * (1.0 + x ** 2 / (2.0 * Rm ** 2)
                                + x ** 4 / (24.0 * Rm ** 4))
    k_elevacion = Rm / (Rm + float(altura_elipsoidal))
    k_comb = k_cuadricula * k_elevacion
    return {
        "radio_medio": Rm,
        "distancia_meridiano_central": x,
        "factor_cuadricula": k_cuadricula,
        "factor_elevacion": k_elevacion,
        "factor_combinado": k_comb,
        "ppm": (k_comb - 1.0) * 1e6,
        "proyeccion": proy["nombre"],
        "epsg": proy["epsg"],
    }


def aplicar_factor_escala(distancias_terreno, factor_combinado):
    """Devuelve lista de tuplas (D_terreno, D_cuadricula, delta)."""
    out = []
    for d in distancias_terreno:
        dg = float(d) * factor_combinado
        out.append((float(d), dg, dg - float(d)))
    return out


# ===================================================================
# 4. GEOMETRÍA: ÁREA, PERÍMETRO, PROYECCIONES
# ===================================================================
def area_gauss(coords):
    """
    Área por el método de Gauss (dobles áreas / shoelace).
    coords: lista de (este, norte) en orden del polígono, sin repetir el 1er punto.
    """
    pts = [(float(e), float(n)) for e, n in coords]
    if len(pts) < 3:
        return {"area_m2": 0.0, "area_ha": 0.0, "area_fanegadas": 0.0,
                "perimetro_m": 0.0, "sentido": "indefinido"}
    doble = 0.0
    perim = 0.0
    n_p = len(pts)
    for i in range(n_p):
        e1, n1 = pts[i]
        e2, n2 = pts[(i + 1) % n_p]
        doble += (e1 * n2 - e2 * n1)
        perim += math.hypot(e2 - e1, n2 - n1)
    area = abs(doble) / 2.0
    return {
        "area_m2": area,
        "area_ha": area / M2_POR_HECTAREA,
        "area_fanegadas": area / M2_POR_FANEGADA,
        "perimetro_m": perim,
        "sentido": "antihorario" if doble > 0 else "horario",
        "n_vertices": n_p,
    }


def tabla_proyecciones(lados):
    """
    Memoria de cálculo de proyecciones y compensación por regla de la brújula
    (Bowditch). Es la tabla que un interventor pide para auditar el ajuste.

    lados: lista de dicts {'lado': 'A-B', 'distancia': 45.32, 'azimut': 128.5432}
           (azimut en GRADOS decimales)
    Devuelve dict con 'filas' y 'resumen'.
    """
    filas = []
    sum_d = 0.0
    for L in lados:
        d = float(L["distancia"])
        az = math.radians(float(L["azimut"]))
        de = d * math.sin(az)
        dn = d * math.cos(az)
        sum_d += d
        filas.append({"lado": L.get("lado", ""), "distancia": d,
                      "azimut": float(L["azimut"]), "delta_e": de, "delta_n": dn})

    err_e = sum(f["delta_e"] for f in filas)
    err_n = sum(f["delta_n"] for f in filas)

    for f in filas:
        prop = f["distancia"] / sum_d if sum_d > 0 else 0.0
        f["corr_e"] = -err_e * prop
        f["corr_n"] = -err_n * prop
        f["delta_e_aj"] = f["delta_e"] + f["corr_e"]
        f["delta_n_aj"] = f["delta_n"] + f["corr_n"]

    return {
        "filas": filas,
        "resumen": {
            "perimetro": sum_d,
            "error_e": err_e,
            "error_n": err_n,
            "error_lineal": math.hypot(err_e, err_n),
            "suma_corr_e": sum(f["corr_e"] for f in filas),
            "suma_corr_n": sum(f["corr_n"] for f in filas),
            "delta_e_aj_total": sum(f["delta_e_aj"] for f in filas),
            "delta_n_aj_total": sum(f["delta_n_aj"] for f in filas),
        },
        "metodo": "Regla de la Brújula (Bowditch)",
    }


def estadisticos_red(distancias):
    """Indicadores baratos de calidad geométrica de la red."""
    d = [float(x) for x in distancias if x is not None and float(x) > 0]
    if not d:
        return {}
    return {
        "n_lados": len(d),
        "longitud_total": sum(d),
        "lado_medio": float(np.mean(d)),
        "lado_min": min(d),
        "lado_max": max(d),
        "relacion_max_min": max(d) / min(d),
        "desv_std": float(np.std(d, ddof=1)) if len(d) > 1 else 0.0,
    }


# ===================================================================
# 5. NIVELACIÓN
# ===================================================================
# mm por sqrt(K en km). VERIFICAR contra la especificación IGAC vigente
# antes de usar en producción; se dejan configurables a propósito.
ORDENES_NIVELACION = {
    "Primer orden - Clase I":  4.0,
    "Primer orden - Clase II": 5.0,
    "Segundo orden - Clase I": 6.0,
    "Segundo orden - Clase II": 8.0,
    "Tercer orden":            12.0,
    "Expedito / configuración": 20.0,
}


# =================================================================
# BLOQUE 3 - ANÁLISIS DE NIVELACIÓN
# =================================================================
def tolerancia_nivelacion(longitud_km, orden="Tercer orden"):
    """Tolerancia e = k * sqrt(K) [mm], con K en kilómetros."""
    k = ORDENES_NIVELACION.get(orden, 12.0)
    K = max(float(longitud_km), 0.0)
    return {"k": k, "K_km": K, "tolerancia_mm": k * math.sqrt(K), "orden": orden}


def evaluar_cierre_altimetrico(error_cierre_mm, longitud_km, orden="Tercer orden"):
    tol = tolerancia_nivelacion(longitud_km, orden)
    err = abs(float(error_cierre_mm))
    cumple = err <= tol["tolerancia_mm"]
    razon = err / tol["tolerancia_mm"] if tol["tolerancia_mm"] > 0 else float("inf")
    return {
        "error_mm": float(error_cierre_mm),
        "tolerancia_mm": tol["tolerancia_mm"],
        "orden": orden,
        "k": tol["k"],
        "K_km": tol["K_km"],
        "cumple": cumple,
        "razon_uso": razon,
        "estado": "ok" if razon <= 0.7 else ("alerta" if cumple else "critico"),
        "formula": r"e_{tol} = k \sqrt{K}",
    }


def chequeo_aritmetico_cartera(sum_vista_atras, sum_vista_adelante,
                               cota_inicial, cota_final_cruda, tol=1e-4):
    """
    Control clásico de revisión de cartera:
        Sigma(V+) - Sigma(V-) debe ser igual a (Cota final - Cota inicial)
    Si no cierra, hay un error de transcripción o de suma, NO de campo.
    """
    lado_izq = float(sum_vista_atras) - float(sum_vista_adelante)
    lado_der = float(cota_final_cruda) - float(cota_inicial)
    dif = lado_izq - lado_der
    return {
        "sigma_mas": float(sum_vista_atras),
        "sigma_menos": float(sum_vista_adelante),
        "diferencia_sumatorias": lado_izq,
        "diferencia_cotas": lado_der,
        "discrepancia": dif,
        "cuadra": abs(dif) <= tol,
        "estado": "ok" if abs(dif) <= tol else "critico",
        "mensaje": ("La cartera cuadra aritméticamente." if abs(dif) <= tol else
                    "La cartera NO cuadra: existe un error de suma o transcripción, "
                    "independiente del error de cierre de campo."),
    }


def correccion_curvatura_refraccion(distancia_m):
    """
    C&R = 0.0675 * K^2  [m], con K en km. Se resta a la lectura de mira.
    Solo relevante en visuales largas (> ~100 m).
    """
    K = float(distancia_m) / 1000.0
    return 0.0675 * K ** 2


def balance_visuales(dist_atras, dist_adelante):
    """
    El desbalance entre distancias atrás/adelante es lo que deja pasar el
    error de colimación. Se busca desbalance ~ 0.
    """
    sa = sum(float(x) for x in dist_atras)
    sd = sum(float(x) for x in dist_adelante)
    total = sa + sd
    desb = sa - sd
    return {
        "suma_atras": sa,
        "suma_adelante": sd,
        "desbalance_m": desb,
        "desbalance_pct": (abs(desb) / total * 100.0) if total > 0 else 0.0,
        "longitud_total_m": total,
        "longitud_total_km": total / 1000.0,
        "visual_max_atras": max((float(x) for x in dist_atras), default=0.0),
        "visual_max_adelante": max((float(x) for x in dist_adelante), default=0.0),
        "estado": "ok" if total > 0 and abs(desb) / total <= 0.02 else "alerta",
    }


def distribuir_error_altimetrico(puntos, error_cierre_m, modo="distancia"):
    """
    Reparte el error de cierre y devuelve la corrección PUNTO POR PUNTO
    (es lo que hoy falta en el informe: se dice que se distribuyó, pero no
    cuánto le tocó a cada punto).

    puntos: lista de dicts {'punto': 'BM-1', 'cota_cruda': 2550.123,
                            'distancia_acum': 120.5}
    modo  : 'distancia' (proporcional a la distancia acumulada)
            'estaciones' (proporcional al número de cambios)
    """
    n = len(puntos)
    if n == 0:
        return []
    if modo == "distancia":
        total = float(puntos[-1].get("distancia_acum", 0.0)) or 1.0
        pesos = [float(p.get("distancia_acum", 0.0)) / total for p in puntos]
    else:
        pesos = [(i + 1) / n for i in range(n)]

    salida = []
    for p, w in zip(puntos, pesos):
        corr = -float(error_cierre_m) * w
        salida.append({
            "punto": p.get("punto", ""),
            "distancia_acum": float(p.get("distancia_acum", 0.0)),
            "cota_cruda": float(p.get("cota_cruda", 0.0)),
            "peso": w,
            "correccion_m": corr,
            "correccion_mm": corr * 1000.0,
            "cota_ajustada": float(p.get("cota_cruda", 0.0)) + corr,
        })
    return salida


def pendientes_entre_puntos(puntos):
    """
    Pendiente (%) entre puntos consecutivos. Es el dato que conecta el informe
    de nivelación con el diseño por gravedad (RAS: alcantarillado / acueducto).
    puntos: lista de dicts {'punto','cota','distancia_acum'}
    """
    out = []
    for a, b in zip(puntos, puntos[1:]):
        dh = float(b.get("distancia_acum", 0.0)) - float(a.get("distancia_acum", 0.0))
        dz = float(b.get("cota", 0.0)) - float(a.get("cota", 0.0))
        pend = (dz / dh * 100.0) if dh else 0.0
        out.append({
            "tramo": f"{a.get('punto','')} - {b.get('punto','')}",
            "dist_horizontal": dh,
            "desnivel": dz,
            "pendiente_pct": pend,
            "sentido": "descendente" if dz < 0 else ("ascendente" if dz > 0 else "plano"),
        })
    return out


# ===================================================================
# 6. VOLÚMENES / MOVIMIENTO DE TIERRAS
# ===================================================================
# Valores orientativos. Deben ajustarse con el estudio geotécnico del proyecto.
FACTORES_MATERIAL = {
    "Material común":  {"esponjamiento": 0.25, "contraccion": 0.10},
    "Arcilla":         {"esponjamiento": 0.35, "contraccion": 0.10},
    "Arena / grava":   {"esponjamiento": 0.12, "contraccion": 0.05},
    "Conglomerado":    {"esponjamiento": 0.30, "contraccion": 0.08},
    "Roca fracturada": {"esponjamiento": 0.50, "contraccion": 0.00},
    "Roca maciza":     {"esponjamiento": 0.60, "contraccion": 0.00},
}


# =================================================================
# BLOQUE 4 - ANÁLISIS DE VOLÚMENES
# =================================================================
def balance_volumetrico_corregido(corte_banco, relleno_compactado,
                                  material="Material común",
                                  factores=None):
    """
    El balance geométrico (corte - relleno) NO es el balance real:
      - El corte se mide en BANCO y se transporta SUELTO (esponja).
      - El relleno se mide COMPACTADO y exige más volumen de banco (contrae).

    Devuelve el volumen de banco realmente necesario y el balance real.
    """
    f = factores or FACTORES_MATERIAL.get(material, FACTORES_MATERIAL["Material común"])
    esp = float(f["esponjamiento"])
    con = float(f["contraccion"])

    corte_banco = float(corte_banco)
    relleno_compactado = float(relleno_compactado)

    corte_suelto = corte_banco * (1.0 + esp)
    # Banco necesario para conformar el relleno compactado
    factor_compactacion = 1.0 / (1.0 - con) if con < 1.0 else 1.0
    relleno_en_banco = relleno_compactado * factor_compactacion

    balance_geom = corte_banco - relleno_compactado
    balance_real = corte_banco - relleno_en_banco

    return {
        "material": material,
        "esponjamiento": esp,
        "contraccion": con,
        "factor_compactacion": factor_compactacion,
        "corte_banco": corte_banco,
        "corte_suelto": corte_suelto,
        "relleno_compactado": relleno_compactado,
        "relleno_en_banco": relleno_en_banco,
        "balance_geometrico": balance_geom,
        "balance_real": balance_real,
        "volumen_botadero": max(balance_real, 0.0),
        "volumen_prestamo": max(-balance_real, 0.0),
        "diferencia_vs_geometrico": balance_real - balance_geom,
    }


def viajes_volqueta(volumen_suelto_m3, capacidad_m3=7.0, factor_llenado=0.90):
    """Número de viajes de volqueta. El dato más usado en obra."""
    cap_efectiva = float(capacidad_m3) * float(factor_llenado)
    if cap_efectiva <= 0:
        return {"viajes": 0, "capacidad_efectiva": 0.0}
    viajes = math.ceil(float(volumen_suelto_m3) / cap_efectiva)
    return {
        "volumen_suelto": float(volumen_suelto_m3),
        "capacidad_nominal": float(capacidad_m3),
        "factor_llenado": float(factor_llenado),
        "capacidad_efectiva": cap_efectiva,
        "viajes": int(viajes),
    }


def volumen_areas_medias(a1, a2, longitud):
    """V = L/2 * (A1 + A2)"""
    return float(longitud) / 2.0 * (float(a1) + float(a2))


def volumen_prismoidal(a1, am, a2, longitud):
    """V = L/6 * (A1 + 4*Am + A2). Requiere el área de la sección MEDIA real."""
    return float(longitud) / 6.0 * (float(a1) + 4.0 * float(am) + float(a2))


def correccion_prismoidal(longitud, h1, h2, w1, w2):
    """
    Corrección prismoidal clásica (se RESTA al volumen por áreas medias):
        Cp = (L/12) * (h1 - h2) * (w1 - w2)
    h = cota roja (altura en el eje), w = ancho de la sección.
    """
    return float(longitud) / 12.0 * (float(h1) - float(h2)) * (float(w1) - float(w2))


def comparar_metodos_volumen(secciones):
    """
    Compara Áreas Medias vs Prismoidal y reporta la diferencia porcentual.
    Justifica técnicamente el método elegido ante interventoría.

    secciones: lista de dicts {'abscisa','area','area_media'(opc),
                               'cota_roja'(opc),'ancho'(opc)}
    """
    v_medias = 0.0
    v_prism = 0.0
    detalle = []
    for s1, s2 in zip(secciones, secciones[1:]):
        L = abs(float(s2["abscisa"]) - float(s1["abscisa"]))
        a1, a2 = float(s1["area"]), float(s2["area"])
        vm = volumen_areas_medias(a1, a2, L)

        if s1.get("area_media") is not None:
            vp = volumen_prismoidal(a1, float(s1["area_media"]), a2, L)
        elif all(k in s1 and k in s2 for k in ("cota_roja", "ancho")):
            vp = vm - correccion_prismoidal(L, s1["cota_roja"], s2["cota_roja"],
                                            s1["ancho"], s2["ancho"])
        else:
            vp = vm  # sin datos suficientes, coinciden

        v_medias += vm
        v_prism += vp
        detalle.append({"desde": s1["abscisa"], "hasta": s2["abscisa"],
                        "longitud": L, "v_areas_medias": vm, "v_prismoidal": vp,
                        "diferencia": vm - vp})

    dif = v_medias - v_prism
    anchos = [s.get("ancho") for s in secciones if s.get("ancho") is not None]
    ancho_constante = bool(anchos) and (max(anchos) - min(anchos)) < 1e-6
    return {
        "detalle": detalle,
        "ancho_constante": ancho_constante,
        "ancho_seccion": anchos[0] if anchos else None,
        "total_areas_medias": v_medias,
        "total_prismoidal": v_prism,
        "diferencia_m3": dif,
        "diferencia_pct": (dif / v_medias * 100.0) if v_medias else 0.0,
        "metodo_conservador": "Áreas Medias" if v_medias >= v_prism else "Prismoidal",
    }


def puntos_de_paso(secciones):
    """
    Abscisas donde la sección cambia de corte a relleno (cota roja = 0).
    Se obtienen por interpolación lineal. Son abscisas de control en obra.
    secciones: lista de dicts {'abscisa','cota_roja'}  (+ corte, - relleno)
    """
    out = []
    for s1, s2 in zip(secciones, secciones[1:]):
        h1, h2 = float(s1["cota_roja"]), float(s2["cota_roja"])
        if h1 == 0.0:
            out.append({"abscisa": float(s1["abscisa"]), "tipo": "cota roja nula"})
        if h1 * h2 < 0:
            x1, x2 = float(s1["abscisa"]), float(s2["abscisa"])
            absc = x1 + (x2 - x1) * abs(h1) / (abs(h1) + abs(h2))
            out.append({
                "abscisa": absc,
                "tipo": "corte a relleno" if h1 > 0 else "relleno a corte",
                # Coma decimal, para no mezclar notaciones en el documento
                "entre": f"{x1:.2f} -- {x2:.2f}".replace(".", ","),
            })
    return out


def curva_masa(abscisas, volumenes_netos):
    """
    Volumen acumulado. volumenes_netos: (+) corte, (-) relleno por tramo.
    Devuelve listas alineadas (abscisa, acumulado).
    """
    acum = []
    total = 0.0
    for v in volumenes_netos:
        total += float(v)
        acum.append(total)
    return {"abscisas": [float(a) for a in abscisas],
            "acumulado": acum,
            "ordenada_final": total,
            "maximo": max(acum) if acum else 0.0,
            "minimo": min(acum) if acum else 0.0}


def analisis_acarreo(abscisas, acumulado, distancia_acarreo_libre=100.0,
                     estacion_m=20.0):
    """
    Análisis de acarreo sobre el diagrama de masas. Esto es lo que se PAGA:
      - Puntos de compensación (cruces por cero del acumulado)
      - Volumen compensado por lazo
      - Distancia media de transporte = área del lazo / volumen del lazo
      - Sobreacarreo = (dist. media - acarreo libre) * volumen  [m3-estación]

    estacion_m: longitud de la estación de sobreacarreo (INVÍAS suele usar
                m3-km o m3-estación; ajustar al pliego del contrato).
    """
    x = [float(a) for a in abscisas]
    y = [float(v) for v in acumulado]
    if len(x) < 2:
        return {"lazos": [], "resumen": {}}

    # Cruces por cero -> puntos de compensación
    cruces = [x[0]]
    for i in range(len(y) - 1):
        if y[i] == 0.0:
            cruces.append(x[i])
        elif y[i] * y[i + 1] < 0:
            t = abs(y[i]) / (abs(y[i]) + abs(y[i + 1]))
            cruces.append(x[i] + (x[i + 1] - x[i]) * t)
    cruces.append(x[-1])
    cruces = sorted(set(round(c, 4) for c in cruces))

    lazos = []
    for a, b in zip(cruces, cruces[1:]):
        # Sub-muestreo del lazo
        xs = [a] + [xi for xi in x if a < xi < b] + [b]
        ys = [float(np.interp(xi, x, y)) for xi in xs]
        if len(xs) < 2:
            continue
        area = float(np.trapezoid(np.abs(ys), xs)) if hasattr(np, "trapezoid") \
            else float(np.trapz(np.abs(ys), xs))
        vol = max(abs(v) for v in ys)
        if vol < 1e-9:
            continue
        dist_media = area / vol
        sobre = max(dist_media - float(distancia_acarreo_libre), 0.0)
        lazos.append({
            "desde": a, "hasta": b, "longitud": b - a,
            "tipo": "corte compensa relleno" if max(ys) > 0 else "relleno alimentado por corte",
            "volumen_compensado": vol,
            "area_diagrama": area,
            "distancia_media_transporte": dist_media,
            "excede_acarreo_libre": sobre > 0,
            "sobreacarreo_m3_m": sobre * vol,
            "sobreacarreo_m3_estacion": (sobre * vol / estacion_m) if estacion_m else 0.0,
        })

    ord_final = y[-1]
    return {
        "puntos_compensacion": cruces[1:-1],
        "lazos": lazos,
        "resumen": {
            "n_lazos": len(lazos),
            "volumen_total_compensado": sum(l["volumen_compensado"] for l in lazos),
            "sobreacarreo_total_m3_estacion": sum(l["sobreacarreo_m3_estacion"] for l in lazos),
            "distancia_acarreo_libre": float(distancia_acarreo_libre),
            "ordenada_final": ord_final,
            "volumen_botadero": max(ord_final, 0.0),
            "volumen_prestamo": max(-ord_final, 0.0),
        },
    }


# Un diccionario recorrido en bucle NO sirve: al reemplazar "\" por
# "\textbackslash{}" las llaves recién insertadas se volverían a escapar en la
# siguiente iteración. Hay que sustituir en UNA SOLA PASADA con regex.
_MAPA_ESCAPE = {
    # --- Caracteres reservados de LaTeX ---
    "\\": r"\textbackslash{}",
    "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "<": r"\textless{}", ">": r"\textgreater{}", "|": r"\textbar{}",
    # --- Símbolos habituales en topografía: se TRANSLITERAN, no se borran ---
    "\u00b0": r"\textdegree{}",          # grado
    "\u00b1": r"$\pm$",                  # mas/menos
    "\u00b2": r"\textsuperscript{2}",    # cuadrado
    "\u00b3": r"\textsuperscript{3}",    # cubico
    "\u00d7": r"$\times$", "\u00f7": r"$\div$",
    "\u00b5": r"$\mu$",
    "\u2206": r"$\Delta$", "\u0394": r"$\Delta$", "\u03a3": r"$\Sigma$",
    "\u03b1": r"$\alpha$", "\u03b2": r"$\beta$", "\u03b3": r"$\gamma$",
    "\u03b8": r"$\theta$", "\u03c6": r"$\varphi$", "\u03c0": r"$\pi$",
    "\u2248": r"$\approx$", "\u2264": r"$\leq$", "\u2265": r"$\geq$",
    "\u2260": r"$\neq$", "\u221a": r"$\sqrt{}$",
    "\u2013": "--", "\u2014": "---",
    "\u2018": "`", "\u2019": "'", "\u201c": "``", "\u201d": "''",
    "\u2032": r"$'$", "\u2033": r"$''$",   # minutos y segundos de arco
    "\u2212": r"$-$", "\u2026": r"\ldots{}", "\u00a0": "~",
    "\u00bd": r"$1/2$", "\u00bc": r"$1/4$", "\u2030": r"\textperthousand{}",
}
_RE_ESCAPE = re.compile("|".join(re.escape(k) for k in _MAPA_ESCAPE))

# Rangos de emoji / pictogramas que pdfLaTeX no puede representar.
_RE_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF"   # emoticones, pictogramas, transporte, simbolos
    "\U00002600-\U000027BF"    # simbolos misceláneos y dingbats
    "\U0001F1E6-\U0001F1FF"    # banderas
    "\U0000FE00-\U0000FE0F"    # selectores de variación
    "\U00002190-\U000021FF"    # flechas
    "\U00002B00-\U00002BFF]+"  # flechas y formas
)


# =================================================================
# BLOQUE 5 - RENDERIZADO LATEX
# =================================================================
def limpiar_emojis(texto):
    """
    Elimina SOLO emojis y pictogramas irrepresentables en pdfLaTeX.
    A diferencia de un filtro por categoría Unicode, conserva el ASCII
    completo (^, |, $) y los símbolos técnicos (°, ±, m², Delta), que se
    transliteran después en escapar_latex().

    Resuelve de forma general el caso de columnas como '📸 Tomar_Fotos',
    en lugar de depender de que el nombre coincida exactamente.
    """
    if not isinstance(texto, str):
        texto = str(texto)
    texto = _RE_EMOJI.sub("", texto)
    texto = "".join(ch for ch in texto
                    if ord(ch) < 128 or unicodedata.category(ch)
                    not in ("Cc", "Cf", "Cs", "Co", "Cn"))
    return re.sub(r"\s+", " ", texto).strip()


def escapar_latex(texto):
    """
    Escapa texto arbitrario para LaTeX en UNA sola pasada.
    Seguro con barras invertidas, llaves, emojis y símbolos técnicos.
    """
    if texto is None:
        return "---"
    if not isinstance(texto, str):
        texto = str(texto)
    texto = limpiar_emojis(texto)
    return _RE_ESCAPE.sub(lambda m: _MAPA_ESCAPE[m.group(0)], texto)


def limpiar_columnas_df(df):
    """Quita columnas de widgets/emoji y normaliza los encabezados."""
    df = df.copy()
    a_borrar = [c for c in df.columns
                if limpiar_emojis(str(c)).lower() in ("tomar_fotos", "tomar fotos", "")]
    if a_borrar:
        df = df.drop(columns=a_borrar, errors="ignore")
    df.columns = [limpiar_emojis(str(c)) for c in df.columns]
    return df


# ===================================================================
# 2. FORMATO NUMÉRICO POR COLUMNA
# ===================================================================
# En lugar de forzar 3 decimales a TODO (abscisas, ángulos, coordenadas y
# volúmenes necesitan precisiones distintas), se define un perfil por columna.
FORMATOS_POR_DEFECTO = {
    # patrón regex en el nombre de columna -> (decimales, formato siunitx)
    r"abscis|pk|k\d":                (2, "4.2"),
    r"norte|este|coord|^n$|^e$":     (3, "7.3"),
    r"cota|elevaci|z$|altura":       (3, "4.3"),
    r"^dist|distanc|longitud":       (3, "4.3"),
    r"area|área":                    (2, "4.2"),
    r"volumen|vol_|corte|relleno":   (2, "6.2"),
    r"azimut|ángulo|angulo|rumbo":   (4, "3.4"),
    r"correc|error":                 (4, "1.4"),
    r"pendiente|%|porcent":          (2, "3.2"),
}


def decidir_formato(nombre_col, formatos=None):
    """Devuelve (decimales, table-format) para una columna dada."""
    tabla = dict(FORMATOS_POR_DEFECTO)
    if formatos:
        tabla.update(formatos)
    nombre = str(nombre_col).lower()
    for patron, val in tabla.items():
        if re.search(patron, nombre):
            return val
    return (3, "5.3")


def numero_plano(val, decimales=3):
    """
    Número con punto decimal, SIN separador de miles.
    siunitx se encarga de mostrarlo como 1.234,567 (formato colombiano).
    Esto reemplaza el hack .replace(',','X').replace('.',',').replace('X','.')
    """
    try:
        return f"{float(val):.{decimales}f}"
    except (TypeError, ValueError):
        return "{---}"


# ===================================================================
# 3. TABLAS: longtable + siunitx (reemplaza dividir_y_generar_tablas)
# ===================================================================
# -----------------------------------------------------------------
# Ancho estimado de columnas y partición en vertical
# -----------------------------------------------------------------
# El informe se mantiene SIEMPRE en vertical. Cuando una tabla no cabe
# a lo ancho de la caja de texto, se parte en varias tablas repitiendo
# las columnas identificadoras, de modo que cada parte siga siendo
# legible por sí sola.

# Caja de texto útil en letterpaper con márgenes de 2,5 cm: 16,59 cm
# (medido con \the\textwidth). Se deja ~0,3 cm de margen de seguridad.
ANCHO_TEXTO_CM = 16.1

# Anchos medidos con \settowidth en \footnotesize (~9 pt), no estimados.
# El encabezado va en NEGRITA, un 17 % más ancha que la redonda; medirlo
# con la constante del texto normal hacía que las tablas se desbordaran:
#   "Correccion Este" redonda  -> 2,247 cm  => 0,1498 cm por carácter
#   "Correccion Este" negrita  -> 2,605 cm  => 0,1736 cm por carácter
#   "0123456789"     redonda   -> 1,625 cm  => 0,1625 cm por dígito
_CM_POR_DIGITO = 0.1625
_CM_POR_CARACTER = 0.1498
_CM_POR_CARACTER_TITULO = 0.1745
# \tabcolsep vale 4 pt a cada lado de la celda: 8 pt = 0,281 cm.
_RELLENO_CELDA_CM = 0.30

# Una columna de texto más ancha que esto pasa a p{} y ajusta línea,
# en lugar de forzar la partición de toda la tabla.
ANCHO_TEXTO_MAX_CM = 4.2


def _ancho_estimado_cm(encabezado, celdas, es_numerica=False):
    """Ancho que ocupará una columna, en centímetros."""
    largo_datos = max((len(str(c)) for c in celdas), default=0)
    cm_dato = _CM_POR_DIGITO if es_numerica else _CM_POR_CARACTER
    ancho_datos = largo_datos * cm_dato
    ancho_titulo = len(str(encabezado)) * _CM_POR_CARACTER_TITULO
    return max(ancho_datos, ancho_titulo) + _RELLENO_CELDA_CM


def _particionar_columnas(columnas, anchos, id_cols, ancho_max):
    """
    Reparte las columnas en bloques que quepan en vertical.
    Las primeras 'id_cols' se repiten en cada bloque como referencia.

    Devuelve una lista de listas de nombres de columna.
    """
    id_cols = max(0, min(int(id_cols), len(columnas) - 1))
    base = list(columnas[:id_cols])
    resto = list(columnas[id_cols:])
    ancho_base = sum(anchos[c] for c in base)

    # Si las columnas de referencia se comen la página, se reducen
    while len(base) > 1 and ancho_base > 0.45 * ancho_max:
        base.pop()
        ancho_base = sum(anchos[c] for c in base)

    if ancho_base + sum(anchos[c] for c in resto) <= ancho_max:
        return [base + resto]          # cabe entera, no hay que partir

    bloques, actual, ancho_actual = [], [], ancho_base
    for col in resto:
        w = anchos[col]
        # Siempre al menos una columna de datos por bloque, aunque se pase
        if actual and ancho_actual + w > ancho_max:
            bloques.append(base + actual)
            actual, ancho_actual = [col], ancho_base + w
        else:
            actual.append(col)
            ancho_actual += w
    if actual:
        bloques.append(base + actual)
    return bloques


def tabla_larga(df, caption, label, formatos=None, notas=None,
                id_cols=1, ancho_max_cm=None, caps=None, **_obsoletos):
    """
    Tabla en formato VERTICAL siempre.

    - Se parte entre páginas repitiendo el encabezado (longtable).
    - Si no cabe a lo ancho, se divide en varias tablas rotuladas
      "(Parte i de n)", repitiendo en cada una las 'id_cols' primeras
      columnas para no perder la referencia de cada fila.
    - Las columnas de texto muy largas ajustan línea con p{} en lugar
      de provocar más particiones.
    - Con siunitx alinea por la coma decimal; sin él, a la derecha.

    id_cols: cuántas columnas iniciales se repiten en cada parte
             (1 para 'Estación'/'Punto'/'Lado', 2 para pares de abscisas).

    Acepta y descarta 'forzar_landscape' y 'max_col_portrait' por
    compatibilidad con la versión anterior: ya no se usa horizontal.
    """
    caps = caps or capacidades_latex()
    usa_siunitx = caps.get("siunitx", False)
    ancho_max = float(ancho_max_cm or ANCHO_TEXTO_CM)

    df = limpiar_columnas_df(df)
    if df.empty:
        return "\\textit{Sin registros para mostrar.}\n"

    cols = list(df.columns)
    es_numerica = {c: pd.api.types.is_numeric_dtype(df[c]) for c in cols}

    # --- Texto ya formateado de cada celda (para medir y para imprimir) ---
    texto = {}
    for c in cols:
        col_txt = []
        for val in df[c]:
            if pd.isna(val):
                col_txt.append("{---}" if (es_numerica[c] and usa_siunitx) else "---")
            elif es_numerica[c]:
                dec, _ = decidir_formato(c, formatos)
                crudo = numero_plano(val, dec)
                col_txt.append(crudo if usa_siunitx else _num_es(crudo))
            else:
                col_txt.append(escapar_latex(val))
        texto[c] = col_txt

    # --- Ancho estimado y columnas de texto que deben ajustar línea ---
    anchos, ajusta_linea = {}, {}
    for c in cols:
        w = _ancho_estimado_cm(c, texto[c], es_numerica[c])
        if not es_numerica[c] and w > ANCHO_TEXTO_MAX_CM:
            ajusta_linea[c] = True
            w = ANCHO_TEXTO_MAX_CM
        else:
            ajusta_linea[c] = False
        anchos[c] = w

    bloques = _particionar_columnas(cols, anchos, id_cols, ancho_max)
    total = len(bloques)

    salida = []
    for i, bloque in enumerate(bloques):
        titulo = caption if total == 1 else f"{caption} (Parte {i+1} de {total})"
        etiqueta = label if total == 1 else f"{label}_p{i+1}"
        # Las notas solo en la última parte, para no repetirlas
        nota_bloque = notas if (notas and i == total - 1) else None
        salida.append(_una_tabla(df, bloque, texto, es_numerica, ajusta_linea,
                                 anchos, titulo, etiqueta, nota_bloque,
                                 formatos, usa_siunitx))
        if i < total - 1:
            salida.append(r"\vspace{0.4cm}")
    return "\n".join(salida) + "\n"


def _table_format_real(valores, dec):
    """
    Calcula el table-format de siunitx a partir de los datos REALES de la
    columna. Un valor fijo reserva un número de dígitos que puede quedarse
    corto (27760.00 no cabe en table-format=4.2) y siunitx se desborda.
    """
    enteros, negativo = 1, False
    for v in valores:
        t = str(v).strip()
        if t.startswith("-"):
            negativo, t = True, t[1:]
        if not t or not t[0].isdigit():
            continue
        enteros = max(enteros, len(t.split(".")[0]))
    return ("+" if negativo else "") + f"{enteros}.{dec}"


def _una_tabla(df, cols, texto, es_numerica, ajusta_linea, anchos,
               caption, label, notas, formatos, usa_siunitx):
    """Emite un único longtable con el subconjunto de columnas indicado."""
    especificacion = []
    for c in cols:
        if ajusta_linea[c]:
            especificacion.append(r">{\raggedright\arraybackslash}p{"
                                  + f"{anchos[c]:.2f}" + "cm}")
        elif es_numerica[c] and usa_siunitx:
            dec, _ = decidir_formato(c, formatos)
            tf = _table_format_real(texto[c], dec)
            especificacion.append(f"S[table-format={tf}]")
        elif es_numerica[c]:
            especificacion.append("r")
        else:
            especificacion.append("l")

    out = [r"\begingroup", r"\footnotesize", r"\setlength{\tabcolsep}{4pt}",
           r"\begin{longtable}{" + " ".join(especificacion) + "}",
           f"  \\caption{{{escapar_latex(caption)}}}\\label{{tab:{label}}} \\\\",
           r"  \toprule"]

    heads = []
    for c in cols:
        txt = f"\\textcolor{{white}}{{\\bfseries {escapar_latex(c)}}}"
        heads.append("{" + txt + "}"
                     if (usa_siunitx and es_numerica[c] and not ajusta_linea[c])
                     else txt)
    fila_head = "  \\rowcolor{GeoBlue}\n  " + " & ".join(heads) + r" \\"

    n = len(cols)
    out += [fila_head, r"  \midrule", r"  \endfirsthead",
            r"  \multicolumn{" + str(n) + r"}{l}{\footnotesize\itshape "
            r"Continuación de la tabla \thetable} \\",
            r"  \toprule", fila_head, r"  \midrule", r"  \endhead",
            r"  \midrule",
            r"  \multicolumn{" + str(n) + r"}{r}{\footnotesize\itshape "
            r"Continúa en la página siguiente} \\",
            r"  \endfoot", r"  \bottomrule"]
    if notas:
        out.append(r"  \multicolumn{" + str(n) + r"}{p{0.9\linewidth}}{\footnotesize "
                   + escapar_latex(notas) + r"} \\")
    out.append(r"  \endlastfoot")

    for i in range(len(df)):
        celdas = [texto[c][i] for c in cols]
        color = r"\rowcolor{GeoBlue!5}" if i % 2 == 0 else r"\rowcolor{white}"
        out.append(f"  {color}")
        out.append("  " + " & ".join(celdas) + r" \\")

    out += [r"\end{longtable}", r"\endgroup"]
    return "\n".join(out)


_ESTILO_CAJA = {"ok": "cajaOk", "alerta": "cajaAlerta", "critico": "cajaCritico"}
_COLOR_CAJA = {"ok": "GeoGreen", "alerta": "GeoAmber", "critico": "GeoRed"}
_ETIQUETA = {"ok": "CUMPLE", "alerta": "CUMPLE CON OBSERVACIONES", "critico": "NO CUMPLE"}




def caja_dictamen(titulo, cuerpo, estado="ok", etiqueta=None, caps=None):
    """Caja coloreada con el veredicto. Sin tcolorbox usa un marco de xcolor."""
    caps = caps or capacidades_latex()
    tag = etiqueta or _ETIQUETA.get(estado, "")
    color = _COLOR_CAJA.get(estado, "GeoAmber")

    if caps.get("tcolorbox", False):
        env = _ESTILO_CAJA.get(estado, "cajaAlerta")
        head = f"{escapar_latex(titulo)} \\hfill \\normalfont\\small [{escapar_latex(tag)}]"
        return (f"\\begin{{{env}}}{{{head}}}\n{cuerpo}\n\\end{{{env}}}\n")

    return ("\\begin{center}\n"
            "\\setlength{\\fboxrule}{0.8pt}\\setlength{\\fboxsep}{6pt}\n"
            f"\\fcolorbox{{{color}}}{{{color}!6}}{{%\n"
            "  \\parbox{0.92\\textwidth}{%\n"
            f"    \\textcolor{{{color}}}{{\\bfseries {escapar_latex(titulo)}}}"
            f" \\hfill \\textcolor{{{color}}}{{\\small [{escapar_latex(tag)}]}}\\\\[4pt]\n"
            f"    {cuerpo}}}}}\n"
            "\\end{center}\n")


def panel_kpi(items, columnas=3, caps=None):
    """Tarjetas de indicadores. Sin tcolorbox usa minipages enmarcados."""
    caps = caps or capacidades_latex()
    mapa = {"ok": "GeoGreen", "alerta": "GeoAmber", "critico": "GeoRed"}

    if caps.get("tcolorbox", False):
        out = [r"\begin{tcbraster}[raster columns=" + str(columnas) +
               r", raster equal height, raster row skip=3mm, raster column skip=3mm]"]
        for it in items:
            color = mapa.get(it.get("estado", "neutro"), "GeoBlue")
            out.append(r"\begin{tcolorbox}[kpi={" + color + "}]")
            out.append(r"{\footnotesize\bfseries " + escapar_latex(it["titulo"]) + r"}\\[2pt]")
            out.append(r"{\LARGE\bfseries " + it["valor"] + r"}")
            if it.get("sub"):
                out.append(r"\\[2pt]{\scriptsize " + escapar_latex(it["sub"]) + r"}")
            out.append(r"\end{tcolorbox}")
        out.append(r"\end{tcbraster}")
        return "\n".join(out) + "\n"

    ancho = round(0.96 / columnas - 0.02, 3)
    out = [r"\begin{center}",
           r"\setlength{\fboxrule}{0.8pt}\setlength{\fboxsep}{5pt}"]
    for i, it in enumerate(items):
        color = mapa.get(it.get("estado", "neutro"), "GeoBlue")
        cuerpo = (r"\centering {\scriptsize\bfseries "
                  + escapar_latex(it["titulo"]) + r"}\\[3pt]"
                  + r"{\large\bfseries " + it["valor"] + r"}")
        if it.get("sub"):
            cuerpo += r"\\[2pt]{\tiny " + escapar_latex(it["sub"]) + r"}"
        out.append(f"\\fcolorbox{{{color}}}{{{color}!6}}{{%")
        out.append(r"  \parbox[c][1.9cm][c]{" + str(ancho) + r"\textwidth}{"
                   + cuerpo + r"}}")
        out.append(r"\\[3mm]" if (i + 1) % columnas == 0 else r"\hfill")
    out.append(r"\end{center}")
    return "\n".join(out) + "\n"


def tabla_cumplimiento(filas, caption="Verificación de cumplimiento normativo"):
    """
    Checklist con semáforo.
    filas: lista de dicts {'criterio','obtenido','tolerancia','estado','norma'}
    """
    simbolo = {"ok": r"\textcolor{GeoGreen}{$\blacksquare$ Cumple}",
               "alerta": r"\textcolor{GeoAmber}{$\blacksquare$ Observación}",
               "critico": r"\textcolor{GeoRed}{$\blacksquare$ No cumple}"}
    out = [r"\begin{table}[H]", r"  \centering",
           f"  \\caption{{{escapar_latex(caption)}}}",
           r"  \small",
           r"  \begin{tabular}{p{4.6cm} r r l l}",
           r"    \toprule",
           r"    \rowcolor{GeoBlue}",
           r"    \textcolor{white}{\bfseries Criterio} & "
           r"\textcolor{white}{\bfseries Obtenido} & "
           r"\textcolor{white}{\bfseries Tolerancia} & "
           r"\textcolor{white}{\bfseries Estado} & "
           r"\textcolor{white}{\bfseries Referencia} \\",
           r"    \midrule"]
    for i, f in enumerate(filas):
        if i % 2 == 0:
            out.append(r"    \rowcolor{GeoBlue!5}")
        out.append("    " + " & ".join([
            escapar_latex(f.get("criterio", "")),
            escapar_latex(f.get("obtenido", "")),
            escapar_latex(f.get("tolerancia", "")),
            simbolo.get(f.get("estado", "alerta"), ""),
            escapar_latex(f.get("norma", "")),
        ]) + r" \\")
    out += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(out) + "\n"


# ===================================================================
# 5. BLOQUES NUEVOS DE CONTENIDO
# ===================================================================
def ficha_metadatos(meta, caps=None):
    """Ficha de trazabilidad al inicio del informe."""
    caps = caps or capacidades_latex()
    out = [r"\section*{Ficha técnica del levantamiento}",
           r"\addcontentsline{toc}{section}{Ficha técnica del levantamiento}"]
    if caps.get("tcolorbox", False):
        out.append(r"\begin{tcolorbox}[ficha]")
    else:
        out.append(r"\noindent{\color{GeoBlue}\rule{\textwidth}{1pt}}\par\medskip")
    out.append(r"\begin{description}[leftmargin=!,labelwidth=4.2cm,style=nextline,"
               r"font=\bfseries\color{GeoBlue},itemsep=1pt]")
    for k, v in meta.items():
        out.append(f"  \\item[{escapar_latex(k)}] {escapar_latex(v)}")
    out.append(r"\end{description}")
    if caps.get("tcolorbox", False):
        out.append(r"\end{tcolorbox}")
    else:
        out.append(r"\noindent{\color{GeoBlue}\rule{\textwidth}{1pt}}\par\medskip")
    return "\n".join(out) + "\n"


EJEMPLO_METADATOS = {
    "Proyecto": "",
    "Localización": "",
    "Fecha de levantamiento": "",
    "Cuadrilla": "",
    "Condiciones climáticas": "",
    "Equipo utilizado": "",
    "Serie / calibración": "",
    "Precisión angular nominal": "",
    "Precisión EDM": "",
    "Sistema de referencia": "MAGNA-SIRGAS / Origen Nacional (EPSG:9377)",
    "Datum vertical": "Nivel medio del mar - Buenaventura",
    "Unidad angular": "Grados sexagesimales",
    "Punto de amarre": "",
    "Fuente del amarre": "",
    "Versión GeoPol": "",
    "Huella del conjunto de datos": "",
}


def ficha_equipo_a_metadatos(equipo):
    """Convierte un dict de equipo en las claves de la ficha."""
    return {
        "Equipo utilizado": f"{equipo.get('marca','')} {equipo.get('modelo','')}".strip(),
        "Serie / calibración": (f"S/N {equipo.get('serie','---')} - certificado "
                                f"{equipo.get('fecha_calibracion','sin registro')}"),
        "Precisión angular nominal": f"{equipo.get('precision_angular_seg','---')}\"",
        "Precisión EDM": (f"{equipo.get('edm_a_mm','---')} mm + "
                          f"{equipo.get('edm_b_ppm','---')} ppm"),
    }


def bloque_firmas(roles=None):
    """Espacio de firmas y aprobación. Un informe técnico sin esto no se radica."""
    roles = roles or ["Elaboró (Topógrafo)", "Revisó (Director de Proyecto)",
                      "Aprobó (Interventoría)"]
    out = [r"\vspace{1.5cm}", r"\noindent"]
    ancho = round(0.94 / len(roles), 3)
    for r_ in roles:
        out.append(r"\begin{minipage}[t]{" + str(ancho) + r"\textwidth}")
        out.append(r"  \centering \vspace{1.2cm} \rule{0.9\linewidth}{0.4pt}\\[2pt]")
        out.append(r"  {\footnotesize " + escapar_latex(r_) + r"}\\[1pt]")
        out.append(r"  {\scriptsize Nombre / M.P.\ / Fecha}")
        out.append(r"\end{minipage}\hfill")
    return "\n".join(out) + "\n"


def control_versiones(filas):
    """filas: lista de dicts {'version','fecha','descripcion','autor'}"""
    out = [r"\begin{table}[H]", r"  \centering \small",
           r"  \caption{Control de versiones del documento}",
           r"  \begin{tabular}{c c p{7cm} l}", r"    \toprule",
           r"    \rowcolor{GeoBlue}",
           r"    \textcolor{white}{\bfseries Ver.} & \textcolor{white}{\bfseries Fecha} & "
           r"\textcolor{white}{\bfseries Descripción} & \textcolor{white}{\bfseries Autor} \\",
           r"    \midrule"]
    for i, f in enumerate(filas):
        if i % 2 == 0:
            out.append(r"    \rowcolor{GeoBlue!5}")
        out.append("    " + " & ".join([escapar_latex(f.get("version", "")),
                                        escapar_latex(f.get("fecha", "")),
                                        escapar_latex(f.get("descripcion", "")),
                                        escapar_latex(f.get("autor", ""))]) + r" \\")
    out += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(out) + "\n"


def monografia_vertices(vertices, caps=None):
    """Monografía por vértice: sin esto las coordenadas no son recuperables."""
    caps = caps or capacidades_latex()
    tcb = caps.get("tcolorbox", False)
    out = [r"\subsection{Monografía de vértices materializados}"]
    for v in vertices:
        titulo = "Vértice " + escapar_latex(v.get("nombre", ""))
        if tcb:
            out.append(r"\begin{tcolorbox}[ficha, title={" + titulo + r"}]")
        else:
            out.append(r"\subsubsection*{" + titulo + r"}")
            out.append(r"\noindent{\color{GeoBlue!60}\rule{\textwidth}{0.5pt}}")
        out.append(r"\begin{description}[leftmargin=!,labelwidth=3.4cm,"
                   r"font=\bfseries\footnotesize\color{GeoBlue},itemsep=0pt]")
        out.append(r"  \item[Coordenadas planas] E "
                   + numero_plano(v.get("este", 0), 3) + r" m \quad N "
                   + numero_plano(v.get("norte", 0), 3) + r" m")
        if v.get("cota") is not None:
            out.append(r"  \item[Cota] " + numero_plano(v.get("cota", 0), 3) + r" m")
        if v.get("lat") is not None:
            out.append(r"  \item[Coordenadas geográficas] "
                       + escapar_latex(str(v.get("lat"))) + r" / "
                       + escapar_latex(str(v.get("lon"))))
        out.append(r"  \item[Monumentación] " + escapar_latex(v.get("monumentacion", "---")))
        out.append(r"  \item[Material de placa] " + escapar_latex(v.get("material", "---")))
        out.append(r"  \item[Descripción] " + escapar_latex(v.get("descripcion", "---")))
        out.append(r"\end{description}")
        if tcb:
            out.append(r"\end{tcolorbox}")
    return "\n".join(out) + "\n"


# ===================================================================
# 6. PREÁMBULO v2
# ===================================================================
# =================================================================
# BLOQUE 5B - GESTIÓN DE FIGURAS
# =================================================================
# Por qué existe este bloque:
#
#  1. RESOLUCIÓN DE RUTAS. pdflatex resuelve las rutas de
#     \includegraphics respecto a su directorio de trabajo, NO respecto
#     a la ubicación del .tex. Al compilar con -output-directory, el
#     .tex queda en Reportes_PDF/ pero la ruta "graficos/plano.png" se
#     busca desde el CWD del proceso. En un servidor (Streamlit, Flask,
#     WSGI) el CWD casi nunca es la raíz del proyecto, así que la imagen
#     no aparece y LaTeX aborta o deja el hueco en blanco.
#     Solución: todas las figuras se COPIAN o se GENERAN dentro de
#     <directorio_salida>/figuras/ y pdflatex se ejecuta con
#     cwd=<directorio_salida>.
#
#  2. RUTAS CON ESPACIOS O ACENTOS. \includegraphics{C:/Mis Planos/a.png}
#     falla. Al materializar las figuras con un nombre saneado el
#     problema desaparece y el .tex queda portable.
#
#  3. FIGURAS EN MEMORIA. Una app web genera los planos como objetos
#     matplotlib/plotly, no como archivos. Antes había que guardarlos a
#     mano; ahora se pasan tal cual.
# =================================================================

_EXT_RASTER = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")
_EXT_VECTOR = (".pdf", ".eps", ".ps")


def _nombre_seguro(texto, por_defecto="figura"):
    """Nombre de archivo ASCII, sin espacios ni acentos, seguro para LaTeX."""
    txt = unicodedata.normalize("NFKD", str(texto))
    txt = txt.encode("ascii", "ignore").decode("ascii")
    txt = re.sub(r"[^a-zA-Z0-9_\-]", "_", txt)
    txt = re.sub(r"_+", "_", txt).strip("_")
    return txt or por_defecto


class GestorFiguras:
    """
    Materializa cualquier figura dentro de <directorio_salida>/<subcarpeta>
    y devuelve la ruta relativa lista para \\includegraphics.

    Acepta:
      - matplotlib Figure o Axes      -> se guarda en PDF vectorial
      - plotly Figure                 -> requiere kaleido
      - PIL.Image                     -> PNG
      - numpy.ndarray                 -> PNG
      - bytes / BytesIO               -> se escriben tal cual
      - cadena base64 o data URI      -> se decodifica
      - ruta a un archivo existente   -> se copia con nombre saneado
      - None                          -> devuelve None (sin error)

    Ejemplo:
        gestor = GestorFiguras("Reportes_PDF")
        ruta = gestor.registrar(fig_matplotlib, "plano_red")
        # -> "figuras/plano_red.pdf"
    """

    def __init__(self, directorio_salida="Reportes_PDF", subcarpeta="figuras",
                 dpi=200, vectorial=True, cerrar_matplotlib=True):
        self.directorio_salida = str(directorio_salida)
        self.subcarpeta = subcarpeta
        self.dpi = int(dpi)
        self.vectorial = bool(vectorial)
        self.cerrar_matplotlib = bool(cerrar_matplotlib)
        self.destino = os.path.join(self.directorio_salida, subcarpeta)
        os.makedirs(self.destino, exist_ok=True)
        self.registradas = []   # [(nombre, ruta_relativa)]
        self.fallidas = []      # [(nombre, motivo)]
        self._contador = {}

    # -------------------------------------------------------------
    def registrar(self, figura, nombre="figura", vectorial=None):
        """Devuelve la ruta relativa para \\includegraphics, o None."""
        if figura is None:
            return None
        base = self._nombre_unico(nombre)
        try:
            ruta_abs = self._materializar(figura, base,
                                          self.vectorial if vectorial is None
                                          else bool(vectorial))
        except Exception as e:
            self.fallidas.append((nombre, f"{type(e).__name__}: {e}"))
            return None
        if ruta_abs is None:
            self.fallidas.append((nombre, "tipo de figura no reconocido "
                                          "o archivo inexistente"))
            return None
        rel = f"{self.subcarpeta}/{os.path.basename(ruta_abs)}"
        self.registradas.append((nombre, rel))
        return rel

    def registrar_varias(self, figuras, prefijo="figura"):
        """Para listas de fotos o de secciones. Descarta las que fallen."""
        if not figuras:
            return []
        return [r for r in
                (self.registrar(f, f"{prefijo}_{i+1}")
                 for i, f in enumerate(figuras)) if r]

    def registrar_secciones(self, pares, prefijo="seccion"):
        """pares: [(abscisa, figura), ...] -> [(abscisa, ruta_relativa), ...]"""
        if not pares:
            return []
        salida = []
        for absc, fig in pares:
            r = self.registrar(fig, f"{prefijo}_{_nombre_seguro(absc)}")
            if r:
                salida.append((absc, r))
        return salida

    def resumen(self):
        return {"registradas": len(self.registradas),
                "fallidas": self.fallidas,
                "directorio": self.destino}

    # -------------------------------------------------------------
    def _nombre_unico(self, nombre):
        base = _nombre_seguro(nombre)
        n = self._contador.get(base, 0)
        self._contador[base] = n + 1
        return base if n == 0 else f"{base}_{n}"

    def _materializar(self, figura, base, vectorial):
        # --- 1. Rutas y cadenas -----------------------------------
        if isinstance(figura, (str, bytes)) or hasattr(figura, "__fspath__"):
            if isinstance(figura, str) and figura.strip().startswith("data:image"):
                import base64
                cabecera, datos = figura.split(",", 1)
                ext = ".png"
                if "jpeg" in cabecera or "jpg" in cabecera:
                    ext = ".jpg"
                return self._escribir_bytes(base64.b64decode(datos), base, ext)
            if isinstance(figura, bytes):
                return self._escribir_bytes(figura, base, self._sniff(figura))
            origen = os.fspath(figura)
            if os.path.exists(origen):
                ext = os.path.splitext(origen)[1].lower() or ".png"
                destino = os.path.join(self.destino, base + ext)
                shutil.copyfile(origen, destino)
                return destino
            return None

        # --- 2. Buffers -------------------------------------------
        if hasattr(figura, "getvalue"):
            datos = figura.getvalue()
            if isinstance(datos, bytes):
                return self._escribir_bytes(datos, base, self._sniff(datos))
            return None

        # --- 3. matplotlib ----------------------------------------
        fig_mpl = None
        if hasattr(figura, "savefig"):
            fig_mpl = figura
        elif hasattr(figura, "get_figure") and callable(figura.get_figure):
            fig_mpl = figura.get_figure()          # Axes
        if fig_mpl is not None and hasattr(fig_mpl, "savefig"):
            ext = ".pdf" if vectorial else ".png"
            destino = os.path.join(self.destino, base + ext)
            fig_mpl.savefig(destino, format=ext.lstrip("."),
                            dpi=self.dpi, bbox_inches="tight",
                            facecolor="white", edgecolor="none")
            if self.cerrar_matplotlib:
                # Imprescindible en apps web: matplotlib acumula figuras
                # y agota memoria tras unos cientos de informes.
                try:
                    import matplotlib.pyplot as plt
                    plt.close(fig_mpl)
                except Exception:
                    pass
            return destino

        # --- 4. plotly --------------------------------------------
        if hasattr(figura, "write_image"):
            ext = ".pdf" if vectorial else ".png"
            destino = os.path.join(self.destino, base + ext)
            figura.write_image(destino, scale=2)   # requiere kaleido
            return destino

        # --- 5. PIL -----------------------------------------------
        if hasattr(figura, "save") and hasattr(figura, "mode"):
            destino = os.path.join(self.destino, base + ".png")
            figura.save(destino)
            return destino

        # --- 6. numpy ---------------------------------------------
        if isinstance(figura, np.ndarray):
            destino = os.path.join(self.destino, base + ".png")
            try:
                import matplotlib.pyplot as plt
                plt.imsave(destino, figura)
            except Exception:
                from PIL import Image
                Image.fromarray(figura).save(destino)
            return destino

        return None

    def _escribir_bytes(self, datos, base, ext):
        destino = os.path.join(self.destino, base + ext)
        with open(destino, "wb") as f:
            f.write(datos)
        return destino

    @staticmethod
    def _sniff(datos):
        """Deduce la extensión por la firma binaria."""
        if datos[:4] == b"%PDF":
            return ".pdf"
        if datos[:8] == b"\x89PNG\r\n\x1a\n":
            return ".png"
        if datos[:3] == b"\xff\xd8\xff":
            return ".jpg"
        if datos[:6] in (b"GIF87a", b"GIF89a"):
            return ".gif"
        return ".png"


def figura_no_disponible(descripcion):
    """
    Marcador visible cuando una figura no pudo generarse.
    Es preferible a que LaTeX aborte la compilación por un archivo
    ausente, y deja constancia en el informe de que faltó el gráfico.
    """
    return ("\\begin{cajaAlerta}{Figura no disponible}\n"
            "No fue posible incorporar la figura: "
            + escapar_latex(descripcion) + ". "
            "Verifique que el gráfico se haya generado correctamente en la "
            "aplicación antes de exportar el informe.\n"
            "\\end{cajaAlerta}\n")


# =================================================================
# BLOQUE 6 - PREÁMBULO Y PORTADA
# =================================================================
def preambulo_v2(ruta_logo="Iconos/logo_geopol.png",
                 babel_opciones="spanish,es-tabla",
                 subcarpeta_figuras="figuras", caps=None):
    r"""
    Preámbulo adaptativo: solo carga los paquetes realmente instalados.
    Con la instalación completa el acabado es íntegro; con TeX Live
    mínimo el informe sale igual, con acabado reducido, en lugar de
    abortar con "File `siunitx.sty' not found".
    """
    caps = caps or capacidades_latex()
    hay = lambda p: caps.get(p, False)

    tex = []
    tex.append(r"\documentclass[11pt,letterpaper]{article}")
    tex.append(r"\usepackage[utf8]{inputenc}")
    tex.append(r"\usepackage[T1]{fontenc}")
    if hay("lmodern"):
        tex.append(r"\usepackage{lmodern}")
        if hay("microtype"):
            tex.append(r"\usepackage{microtype}")
    elif hay("microtype"):
        # Sin fuentes escalables microtype no puede expandir
        tex.append(r"\usepackage[expansion=false]{microtype}")
    tex.append(r"\usepackage[" + babel_opciones + r"]{babel}")
    tex.append(r"\usepackage[margin=2.5cm]{geometry}")
    tex.append(r"\usepackage{amsmath,amssymb}")
    tex.append(r"\usepackage{longtable}")
    tex.append(r"\usepackage{array}")   # columnas p{} con \raggedright
    tex.append(r"\usepackage{graphicx}")
    tex.append(r"\graphicspath{{./}{" + subcarpeta_figuras + r"/}}")
    tex.append(r"\usepackage{fancyhdr}")
    tex.append(r"\usepackage[table]{xcolor}")

    # pdflscape ya no se carga: el informe se mantiene siempre vertical
    for paq in ("booktabs", "float", "caption", "threeparttable",
                "enumitem", "csquotes", "titlesec",
                "siunitx", "lastpage", "tikz"):
        if hay(paq):
            tex.append(r"\usepackage{" + paq + r"}")
    if hay("tcolorbox"):
        tex.append(r"\usepackage[most]{tcolorbox}")
    if hay("eso-pic"):
        tex.append(r"\usepackage{eso-pic}")
    if hay("transparent"):
        tex.append(r"\usepackage{transparent}")

    # Sustitutos mínimos de lo que falte
    if not hay("float"):
        # Sin float no existe [H]; se aproxima con [!ht]
        tex.append(r"\providecommand{\H}{}")
    if not hay("csquotes"):
        tex.append(r"\providecommand{\enquote}[1]{``#1''}")
    if not hay("booktabs"):
        tex.append(r"\providecommand{\toprule}{\hline}")
        tex.append(r"\providecommand{\midrule}{\hline}")
        tex.append(r"\providecommand{\bottomrule}{\hline}")

    tex.append(r"\usepackage{hyperref}")   # siempre el último

    # --- Paleta ---
    tex.append(r"\definecolor{GeoOrange}{HTML}{FF8C00}")
    tex.append(r"\definecolor{GeoBlue}{HTML}{0D47A1}")
    tex.append(r"\definecolor{GeoGreen}{HTML}{2E7D32}")
    tex.append(r"\definecolor{GeoAmber}{HTML}{E65100}")
    tex.append(r"\definecolor{GeoRed}{HTML}{C62828}")
    tex.append(r"\definecolor{GeoGray}{HTML}{455A64}")

    if hay("siunitx"):
        # group-digits=integer es imprescindible: por defecto siunitx agrupa
        # también la parte decimal y un azimut de 158.7525 grados se imprimía
        # como "158,752.5" en lugar de "158,7525".
        tex.append(r"\sisetup{output-decimal-marker={,}, group-separator={.},"
                   r" group-digits=integer, group-minimum-digits=4,"
                   r" detect-weight=true, detect-family=true,"
                   r" table-align-text-before=false}")

    if hay("titlesec"):
        tex.append(r"\titleformat{\section}[hang]"
                   r"{\normalfont\Large\bfseries\color{GeoBlue}}"
                   r"{\thesection}{0.7em}{}[{\color{GeoOrange}\titlerule[1.2pt]}]")
        tex.append(r"\titleformat{\subsection}[hang]"
                   r"{\normalfont\large\bfseries\color{GeoGray}}{\thesubsection}{0.6em}{}")
        tex.append(r"\titlespacing*{\section}{0pt}{16pt}{8pt}")

    if hay("caption"):
        tex.append(r"\captionsetup{font=small, labelfont={bf,color=GeoBlue}}")
        tex.append(r"\captionsetup[table]{position=top, skip=4pt}")
        tex.append(r"\captionsetup[figure]{position=bottom}")

    if hay("tcolorbox"):
        tex.append(r"\tcbset{cajabase/.style={enhanced, breakable, sharp corners=downhill,"
                   r" boxrule=0.4pt, left=3mm, right=3mm, top=2mm, bottom=2mm,"
                   r" fonttitle=\bfseries\color{white}, attach boxed title to top left="
                   r"{xshift=3mm, yshift=-2mm}, boxed title style={sharp corners, boxrule=0pt}}}")
        for nombre, color in (("cajaOk", "GeoGreen"), ("cajaAlerta", "GeoAmber"),
                              ("cajaCritico", "GeoRed")):
            tex.append(r"\newtcolorbox{" + nombre + r"}[1]{cajabase, colback="
                       + color + r"!4, colframe=" + color + r", coltitle=white,"
                       r" title={#1}, boxed title style={colback=" + color + r"}}")
        tex.append(r"\tcbset{ficha/.style={enhanced, breakable, colback=GeoBlue!3, "
                   r"colframe=GeoBlue!60, boxrule=0.4pt, sharp corners, "
                   r"fonttitle=\bfseries\color{white}, coltitle=white, "
                   r"colbacktitle=GeoBlue, left=3mm, right=3mm}}")
        tex.append(r"\tcbset{kpi/.style n args={1}{enhanced, sharp corners, "
                   r"colback=#1!6, colframe=#1, boxrule=0.9pt, halign=center, "
                   r"valign=center, left=1mm, right=1mm, top=2mm, bottom=2mm, "
                   r"fontupper=\color{#1!75!black}}}")

    if ruta_logo and os.path.exists(ruta_logo) and hay("eso-pic"):
        logo = ruta_logo.replace("\\", "/")
        transp = (r"\transparent{0.06}" if hay("transparent") else "")
        tex.append(r"\AddToShipoutPictureBG{\AtPageCenter{\makebox[0pt]{"
                   + transp + r"\includegraphics[width=12cm]{" + logo + r"}}}}")

    tex.append(r"\hypersetup{colorlinks=true, linkcolor=GeoBlue, urlcolor=GeoOrange,"
               r" pdfborder={0 0 0}}")
    tex.append(r"\pagestyle{fancy}")
    tex.append(r"\fancyhf{}")
    tex.append(r"\fancyhead[L]{\footnotesize\textcolor{GeoBlue}{\textbf{GeoPol Web}}"
               r" -- Reporte Técnico}")
    tex.append(r"\fancyhead[R]{\footnotesize Universidad Distrital F.J.C.}")
    if hay("lastpage"):
        tex.append(r"\fancyfoot[C]{\footnotesize\thepage\ de \pageref{LastPage}}")
    else:
        tex.append(r"\fancyfoot[C]{\footnotesize\thepage}")
    tex.append(r"\renewcommand{\headrulewidth}{0.4pt}")
    tex.append(r"\renewcommand{\footrulewidth}{0.4pt}")
    tex.append(r"\setlength{\parskip}{4pt}")
    # Margen de maniobra al justificar: evita líneas desbordadas
    # cuando faltan patrones de silabación o hay palabras largas.
    tex.append(r"\setlength{\emergencystretch}{3em}")
    tex.append(r"\renewcommand{\arraystretch}{1.15}")
    return "\n".join(tex)


def portada_v2(titulo, autores, tutor, subtitulo=None, lema=None, caps=None):
    """Portada. Sin tikz omite las bandas de color, el resto es idéntico."""
    caps = caps or capacidades_latex()
    lema = lema or r"\enquote{Máxima precisión al alcance de tus manos}"
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    fecha = f"{meses[datetime.now().month - 1]} de {datetime.now().year}"

    tex = [r"\begin{document}", r"\begin{titlepage}", r"\thispagestyle{empty}"]

    if caps.get("tikz", False):
        tex += [r"\begin{tikzpicture}[remember picture,overlay]",
                r"  \fill[GeoBlue] (current page.north west) rectangle "
                r"([yshift=-4cm]current page.north east);",
                r"  \fill[GeoOrange] ([yshift=-4cm]current page.north west) rectangle "
                r"([yshift=-4.5cm]current page.north east);",
                r"  \fill[GeoBlue!5] (current page.south west) rectangle "
                r"([yshift=4cm]current page.south east);",
                r"\end{tikzpicture}",
                r"\vspace*{-2cm}", r"\begin{center}",
                r"  \textcolor{white}{\Huge\bfseries GEOPORTAL WEB (GeoPol)} \\[0.4cm]",
                r"  \textcolor{white}{\large\itshape " + lema + r"} \\[2.6cm]"]
    else:
        # Sin tikz: banda con \colorbox, mismo efecto sin el paquete
        tex += [r"\begin{center}",
                r"  \colorbox{GeoBlue}{\parbox{\textwidth}{\vspace{6mm}\centering"
                r" \textcolor{white}{\Huge\bfseries GEOPORTAL WEB (GeoPol)}\\[4pt]"
                r" \textcolor{white}{\large\itshape " + lema + r"}\vspace{6mm}}}\\[2pt]",
                r"  \textcolor{GeoOrange}{\rule{\textwidth}{4pt}} \\[2.6cm]"]

    tex += [r"  \vspace{2cm}",
            r"  {\LARGE\bfseries INFORME TÉCNICO DE INGENIERÍA} \\[0.4cm]",
            r"  {\Large\bfseries " + escapar_latex(titulo) + r"} \\[0.3cm]"]
    if subtitulo:
        tex.append(r"  {\large\color{GeoGray} " + escapar_latex(subtitulo) + r"} \\[1.6cm]")
    else:
        tex.append(r"  \vspace{1.6cm}")

    tex += [r"  \begin{flushleft}",
            r"    \Large\bfseries Autores del Procesamiento:\\[0.2cm]"]
    for a in autores:
        tex.append(r"    \large $\bullet$ " + escapar_latex(a) + r" \\[0.1cm]")
    tex += [r"    \vspace{0.8cm}",
            r"    \Large\bfseries Tutor -- Director de Proyecto:\\[0.2cm]",
            r"    \large $\bullet$ " + escapar_latex(tutor),
            r"  \end{flushleft}", r"  \vfill",
            r"  \textbf{UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS}\\[0.2cm]",
            r"  Facultad Tecnológica \\ Ingeniería Civil \\[0.2cm]",
            f"  Bogotá D.C. -- {fecha}",
            r"\end{center}", r"\end{titlepage}",
            r"\tableofcontents", r"\newpage"]
    return "\n".join(tex)


def obtener_contenido_informe(tipo_trabajo):
    c = {}
    if "Poligonal" in tipo_trabajo:
        c["intro"] = (
            r"El presente informe documenta el establecimiento de una red de apoyo "
            r"planimétrico. La materialización de estos vértices constituye la base "
            r"fundamental para el levantamiento de detalles, garantizando que la "
            r"cartografía resultante cumpla con las precisiones requeridas para el "
            r"diseño geométrico y la estructuración de proyectos de ingeniería.")
        c["objetivos"] = (
            r"\begin{itemize}[leftmargin=1.2em,itemsep=2pt]"
            r"\item \textbf{General:} calcular y compensar la red planimétrica "
            r"obtenida en campo para determinar las coordenadas definitivas."
            r"\item \textbf{Específicos:}"
            r"\begin{itemize}[itemsep=1pt]"
            r"\item Cuantificar el error de cierre angular y lineal del circuito "
            r"y contrastarlo contra la tolerancia admisible."
            r"\item Aplicar el ajuste correspondiente según la tolerancia permitida."
            r"\item Determinar el factor de escala combinado y reducir las "
            r"distancias de terreno al plano de proyección."
            r"\item Vincular el levantamiento al sistema oficial de coordenadas."
            r"\end{itemize}\end{itemize}")
        c["marco"] = (
            r"El procesamiento se rige por las especificaciones técnicas del "
            r"\textbf{Instituto Geográfico Agustín Codazzi (IGAC)}. Toda la "
            r"información espacial se encuentra referida al sistema oficial de "
            r"Colombia, \textbf{MAGNA-SIRGAS (Origen Nacional, EPSG:9377)}, en "
            r"cumplimiento de la Resolución 471 de 2020. "
            r"Por tratarse de una proyección Transversa de Mercator con factor de "
            r"escala en el meridiano central $k_0 = 0{,}9992$, las distancias "
            r"medidas sobre el terreno deben reducirse al plano de proyección "
            r"mediante el factor de escala combinado antes de cualquier "
            r"comparación de cierre. Los errores de cierre angular se evalúan "
            r"frente a tolerancias del tipo $T_a = k\,a\sqrt{n}$.")
        c["compensacion"] = (
            r"\subsection{Método de compensación empleado}"
            r"La compensación de la poligonal cerrada se ejecuta mediante la "
            r"\textbf{Regla de la Brújula}, también conocida como \textbf{método "
            r"de Bowditch}. Este procedimiento parte del supuesto de que los "
            r"errores accidentales cometidos en la medición de ángulos y de "
            r"distancias son de magnitud comparable, por lo que el error de "
            r"cierre en proyecciones se distribuye entre los lados del circuito "
            r"de forma \emph{proporcional a la longitud de cada lado}: los lados "
            r"más largos, al haber acumulado mayor oportunidad de error, reciben "
            r"una corrección mayor."
            r"\par\medskip "
            r"Una vez verificado que el error de cierre angular se encuentra "
            r"dentro de la tolerancia admisible y compensados los ángulos "
            r"interiores, se calculan las proyecciones de cada lado a partir de "
            r"su azimut y su distancia horizontal:"
            r"\begin{equation}"
            r"\Delta E_i = D_i \sin \alpha_i \qquad "
            r"\Delta N_i = D_i \cos \alpha_i"
            r"\end{equation}"
            r"En un circuito cerrado la suma algebraica de las proyecciones debe "
            r"ser nula. Las sumatorias residuales constituyen los errores de "
            r"cierre en proyecciones, $e_E = \sum \Delta E_i$ y "
            r"$e_N = \sum \Delta N_i$, cuya resultante es el error lineal de "
            r"cierre $e_L = \sqrt{e_E^2 + e_N^2}$. La corrección que la Regla de "
            r"la Brújula asigna a cada lado es:"
            r"\begin{equation}"
            r"C_{E_i} = -e_E \cdot \frac{D_i}{\sum D} \qquad "
            r"C_{N_i} = -e_N \cdot \frac{D_i}{\sum D}"
            r"\end{equation}"
            r"donde $D_i$ es la longitud del lado y $\sum D$ el perímetro de la "
            r"poligonal. Aplicadas las correcciones, las proyecciones ajustadas "
            r"suman cero y el polígono cierra geométricamente, permitiendo el "
            r"cálculo de las coordenadas definitivas de cada vértice por "
            r"acumulación sucesiva a partir del punto de amarre. La calidad del "
            r"trabajo se expresa mediante la precisión relativa "
            r"$P = \sum D / e_L$, contrastada contra la exigencia del proyecto.")
    elif "Nivelacion" in tipo_trabajo or "Altimetria" in tipo_trabajo:
        c["intro"] = (
            r"El control vertical es un componente crítico en el desarrollo de "
            r"infraestructura. Este documento detalla el procedimiento de "
            r"nivelación geométrica ejecutado para trasladar y establecer cotas "
            r"de alta precisión en los puntos de control del proyecto.")
        c["objetivos"] = (
            r"\begin{itemize}[leftmargin=1.2em,itemsep=2pt]"
            r"\item \textbf{General:} determinar las elevaciones ajustadas a "
            r"partir de un Banco de Nivel (BM) de cota conocida."
            r"\item \textbf{Específicos:}"
            r"\begin{itemize}[itemsep=1pt]"
            r"\item Verificar el cuadre aritmético de la cartera antes de "
            r"evaluar el error de campo."
            r"\item Calcular el error de cierre y contrastarlo con la tolerancia "
            r"del orden de nivelación exigido."
            r"\item Distribuir el error proporcionalmente y reportar la "
            r"corrección aplicada punto por punto."
            r"\item Generar el perfil altimétrico y las pendientes de diseño."
            r"\end{itemize}\end{itemize}")
        c["marco"] = (
            r"La metodología altimétrica se basa en la nivelación diferencial "
            r"geométrica. El error de cierre se evalúa mediante "
            r"$e_{tol} = k\sqrt{K}$, con $K$ en kilómetros y $k$ dependiente del "
            r"orden de nivelación. En visuales largas se considera la corrección "
            r"conjunta por curvatura y refracción, $C\!\&\!R = 0{,}0675\,K^2$ "
            r"metros. El control riguroso de cotas es de estricto cumplimiento "
            r"para el diseño de sistemas por gravedad: en redes de alcantarillado "
            r"y acueducto las pendientes mínimas y máximas están estipuladas en "
            r"el \textbf{Reglamento Técnico del Sector de Agua Potable y "
            r"Saneamiento Básico (RAS)}.")
    elif "Volumen" in tipo_trabajo or "Cubicaje" in tipo_trabajo:
        c["intro"] = (
            r"La cuantificación del movimiento de tierras es determinante para la "
            r"viabilidad financiera y logística de una obra. Este informe expone "
            r"las memorias de cálculo volumétrico, analizando las áreas "
            r"transversales, la compensación longitudinal de masas y el balance "
            r"real de material una vez consideradas las propiedades del suelo.")
        c["objetivos"] = (
            r"\begin{itemize}[leftmargin=1.2em,itemsep=2pt]"
            r"\item \textbf{General:} calcular los volúmenes de corte y relleno "
            r"requeridos para la conformación del proyecto."
            r"\item \textbf{Específicos:}"
            r"\begin{itemize}[itemsep=1pt]"
            r"\item Cuantificar el área transversal en cada abscisa."
            r"\item Contrastar el método de áreas medias contra el prismoidal."
            r"\item Corregir el balance por esponjamiento y contracción."
            r"\item Construir el diagrama de masas y determinar distancias "
            r"medias de transporte, sobreacarreo, préstamo y botadero."
            r"\end{itemize}\end{itemize}")
        c["marco"] = (
            r"El cálculo volumétrico se realiza bajo el \textbf{Método de las "
            r"Áreas Medias}, $V = \frac{L}{2}(A_1 + A_2)$, contrastado con el "
            r"\textbf{método prismoidal}, $V = \frac{L}{6}(A_1 + 4A_m + A_2)$, "
            r"cuya diferencia se reporta explícitamente. El volumen geométrico no "
            r"corresponde al volumen real transportado: el material de corte se "
            r"mide en banco y se transporta suelto (esponjamiento), mientras que "
            r"el relleno se recibe compactado (contracción). Los criterios de "
            r"compensación, acarreo libre y disposición de sobrantes se alinean "
            r"con las Especificaciones Generales de Construcción de Carreteras "
            r"del \textbf{INVÍAS}; cuando el movimiento "
            r"involucra excavaciones para cimentaciones se atiende el Título H de "
            r"la \textbf{NSR-10}.")
    return c


# ===================================================================
# 1. POLIGONAL
# ===================================================================
# =================================================================
# BLOQUE 7 - GENERADORES DE INFORME
# =================================================================
def generar_reporte_poligonal_latex(df_campo, df_ajuste, metricas, tipo_poligonal,
                                    autores, tutor, path_grafico=None, fotos_paths=None,
                                    # --- nuevos, todos opcionales ---
                                    equipo=None, metadatos=None, lados=None,
                                    coords_poligono=None, vertices=None,
                                    precision_exigida=10000, factor_tolerancia=2.0,
                                    este_referencia=None, altura_elipsoidal=None,
                                    lat_referencia=4.65, ruta_logo="Iconos/logo_geopol.png",
                                    directorio_salida="Reportes_PDF", gestor=None):
    # path_grafico y fotos_paths admiten rutas U objetos de figura
    # (matplotlib, plotly, PIL, numpy, bytes, base64).
    caps = capacidades_latex()
    gestor = gestor or GestorFiguras(directorio_salida)
    tex = [preambulo_v2(ruta_logo=ruta_logo,
                        subcarpeta_figuras=gestor.subcarpeta)]
    tex.append(portada_v2(tipo_poligonal, autores, tutor,
                             subtitulo="Red de apoyo planimétrico"))

    # ---------- Ficha de trazabilidad ----------
    meta = dict(EJEMPLO_METADATOS)
    if equipo:
        meta.update(ficha_equipo_a_metadatos(equipo))
    if metadatos:
        meta.update(metadatos)

    # ---------- Cálculos de tolerancia ----------
    n_vert = len(df_ajuste) if df_ajuste is not None else 0
    prec_eq = float((equipo or {}).get("precision_angular_seg", 5.0))
    perimetro = float(metricas.get("perimetro", 0.0)) or None

    proy = tabla_proyecciones(lados) if lados else None
    if proy and not perimetro:
        perimetro = proy["resumen"]["perimetro"]

    ang = evaluar_cierre_angular(metricas.get("err_ang_ant", 0),
                                    prec_eq, n_vert, factor_tolerancia)
    err_h = float(metricas.get("err_h_ant", 0.0))
    lin = (evaluar_cierre_lineal(err_h, perimetro, precision_exigida)
           if perimetro else None)
    azi = azimut_error_cierre(metricas.get("err_e_ant", 0.0),
                                 metricas.get("err_n_ant", 0.0))
    area = area_gauss(coords_poligono) if coords_poligono else None
    fe = (factor_escala_combinado(este_referencia, altura_elipsoidal, lat_referencia)
          if este_referencia and altura_elipsoidal is not None else None)

    # ---------- Panel de indicadores ----------
    kpis = []
    prec_h = float(metricas.get("prec_h", 0) or 0)
    kpis.append({"titulo": "Precisión planimétrica",
                 "valor": f"1:{int(prec_h)}" if prec_h else "---",
                 "sub": f"exigida 1:{precision_exigida}",
                 "estado": (lin or {}).get("estado", "alerta")})
    kpis.append({"titulo": "Error angular", "valor": ang["error_dms"],
                 "sub": f"tolerancia {ang['tolerancia_dms']}", "estado": ang["estado"]})
    kpis.append({"titulo": "Error lineal de cierre",
                 "valor": numero_plano(err_h, 4).replace(".", ",") + " m",
                 "sub": (f"azimut {azi['azimut_dms']}" if azi["azimut_grados"] is not None
                         else ""), "estado": "neutro"})
    if area:
        kpis.append({"titulo": "Área del polígono",
                     "valor": f"{area['area_ha']:.4f}".replace(".", ",") + " ha",
                     "sub": f"{area['area_fanegadas']:.3f}".replace(".", ",")
                            + " fanegadas", "estado": "neutro"})
        kpis.append({"titulo": "Perímetro",
                     "valor": f"{area['perimetro_m']:.3f}".replace(".", ",") + " m",
                     "sub": f"{area['n_vertices']} vértices", "estado": "neutro"})
    if fe:
        kpis.append({"titulo": "Factor combinado",
                     "valor": f"{fe['factor_combinado']:.7f}".replace(".", ","),
                     "sub": f"{fe['ppm']:.1f} ppm".replace(".", ","), "estado": "neutro"})
    textos = obtener_contenido_informe("Poligonal")
    tex.append(r"\section{Introducción}")
    tex.append(textos["intro"])
    tex.append(r"\subsection{Objetivos del Procesamiento}")
    tex.append(textos["objetivos"])
    tex.append(r"\section{Marco Teórico y Referencia Normativa}")
    tex.append(textos["marco"])
    tex.append(textos["compensacion"])
    tex.append(r"\subsection{Metodología de Procesamiento Automático}")
    tex.append(r"El conjunto de datos brutos fue sometido a rutinas de depuración y "
               r"compensación matricial a través del motor algorítmico de "
               r"\textbf{GeoPol}.")

    # Ficha técnica: va después del marco teórico y antes del trabajo de campo
    tex.append(ficha_metadatos(meta))

    # ---------- Campo ----------
    tex.append(r"\section{Trabajo de Campo: Registro de Observaciones}")
    tex.append(tabla_larga(df_campo, "Cartera de observaciones brutas", "campo"))

    if fotos_paths:
        tex.append(_mosaico_fotos(gestor, fotos_paths,
                                  "Mosaico de registro fotográfico de estaciones",
                                  "Registro Fotográfico Panorámico"))

    # ---------- Errores y tolerancias ----------
    tex.append(r"\section{Cálculo, Análisis de Errores y Compensación}")

    filas_cumpl = [{"criterio": "Cierre angular", "obtenido": ang["error_dms"],
                    "tolerancia": ang["tolerancia_dms"], "estado": ang["estado"],
                    "norma": f"Ta = {factor_tolerancia:g}·{prec_eq:g}\"·√{n_vert}"}]
    if lin:
        filas_cumpl.append({"criterio": "Cierre lineal",
                            "obtenido": f"{lin['error_m']:.4f} m".replace(".", ","),
                            "tolerancia": f"{lin['tolerancia_m']:.4f} m".replace(".", ","),
                            "estado": lin["estado"],
                            "norma": f"1:{precision_exigida}"})
    tex.append(tabla_cumplimiento(filas_cumpl))

    tex.append(_tabla_metricas_cierre(metricas))

    if lin:
        cuerpo = (f"Se obtuvo una precisión relativa de 1:{int(lin['precision_obtenida'])} "
                  f"frente a la exigencia de 1:{precision_exigida}. "
                  f"El vector de error de cierre tiene magnitud "
                  f"\\SI{{{azi['magnitud']:.4f}}}{{\\metre}}")
        if azi["azimut_grados"] is not None:
            cuerpo += f" y azimut {escapar_latex(azi['azimut_dms'])}"
        cuerpo += "."
        if lados:
            susp = lado_sospechoso(metricas.get("err_e_ant", 0),
                                      metricas.get("err_n_ant", 0),
                                      {L["lado"]: L["azimut"] for L in lados})
            if susp:
                cuerpo += (" Los lados con azimut concordante con esa dirección "
                           f"({escapar_latex(', '.join(s['lado'] for s in susp[:3]))}) "
                           "deben verificarse por posible error de distancia.")
        tex.append(caja_dictamen("Dictamen sobre la precisión planimétrica",
                                    cuerpo, lin["estado"]))

    # ---------- Memoria de proyecciones ----------
    if proy:
        tex.append(r"\subsection{Memoria de proyecciones y compensación}")
        df_p = pd.DataFrame([{
            "Lado": f["lado"], "Distancia": f["distancia"], "Azimut": f["azimut"],
            "Delta Este": f["delta_e"], "Delta Norte": f["delta_n"],
            "Correccion Este": f["corr_e"], "Correccion Norte": f["corr_n"],
            "Delta Este ajustado": f["delta_e_aj"],
            "Delta Norte ajustado": f["delta_n_aj"]} for f in proy["filas"]])
        tex.append(tabla_larga(
            df_p, f"Proyecciones y compensación — {proy['metodo']}", "proyecciones",
            notas="Las correcciones se distribuyen proporcionalmente a la longitud "
                  "de cada lado. La suma de proyecciones ajustadas debe ser nula."))

        est = estadisticos_red([L["distancia"] for L in lados])
        tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt]")
        tex.append(r"\item Lados: " + str(est["n_lados"])
                   + r"; longitud total \SI{" + f"{est['longitud_total']:.3f}"
                   + r"}{\metre}; lado medio \SI{" + f"{est['lado_medio']:.3f}"
                   + r"}{\metre}.")
        tex.append(r"\item Relación lado máximo/mínimo: "
                   + f"{est['relacion_max_min']:.2f}".replace(".", ",")
                   + r" (valores altos indican geometría desfavorable).")
        tex.append(r"\end{itemize}")

    # ---------- Factor de escala ----------
    if fe:
        tex.append(r"\subsection{Reducción al plano de proyección}")
        tex.append(r"Factor de escala de cuadrícula "
                   + f"{fe['factor_cuadricula']:.8f}".replace(".", ",")
                   + r", factor de elevación "
                   + f"{fe['factor_elevacion']:.8f}".replace(".", ",")
                   + r", \textbf{factor combinado} "
                   + f"{fe['factor_combinado']:.8f}".replace(".", ",")
                   + f" ({fe['ppm']:.1f} ppm). ".replace(".", ",")
                   + r"Este factor multiplica la distancia de terreno para "
                     r"obtener la distancia de cuadrícula.")
        if lados:
            pares = aplicar_factor_escala([L["distancia"] for L in lados],
                                             fe["factor_combinado"])
            df_fe = pd.DataFrame([{"Lado": lados[i]["lado"],
                                   "Distancia terreno": p[0],
                                   "Distancia cuadricula": p[1],
                                   "Diferencia": p[2]} for i, p in enumerate(pares)])
            tex.append(tabla_larga(df_fe,
                                      "Reducción de distancias de terreno a cuadrícula",
                                      "factor_escala"))

    # ---------- Área ----------
    if area:
        tex.append(r"\subsection{Área y perímetro}")
        tex.append(r"Área calculada por el método de Gauss: \SI{"
                   + f"{area['area_m2']:.3f}" + r"}{\square\metre} "
                   + r"($\equiv$ \num{" + f"{area['area_ha']:.4f}" + r"} ha "
                   + r"$\equiv$ \num{" + f"{area['area_fanegadas']:.4f}"
                   + r"} fanegadas). Perímetro \SI{"
                   + f"{area['perimetro_m']:.3f}" + r"}{\metre}. "
                   + f"Sentido de digitalización: {area['sentido']}.")

    tex.append(r"\subsection{Cartera Final de Coordenadas Ajustadas}")
    tex.append(tabla_larga(df_ajuste, "Coordenadas compensadas de la red", "ajuste"))

    if vertices:
        tex.append(monografia_vertices(vertices))

    # Panel de indicadores: cierra la secuencia de resultados numéricos y
    # da paso al plano. Va aquí, no tras el índice, para que continúe la
    # información en lugar de ocupar una página suelta.
    tex.append(r"\subsection{Resumen de Indicadores del Levantamiento}")
    tex.append(panel_kpi(kpis, columnas=3))

    if path_grafico:
        tex.append(_figura(gestor, path_grafico,
                           f"Plano As-Built de la {tipo_poligonal}",
                           "Esquema Geométrico de la Red Planimétrica",
                           nombre="plano_red"))

    # ---------- Conclusiones ----------
    tex.append(r"\section{Conclusiones y Dictamen Técnico}")
    tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=3pt]")
    tex.append(r"\item " + evaluar_precision(prec_h))
    tex.append(r"\item " + ("El cierre angular se encuentra dentro de la tolerancia "
                            if ang["cumple"] else
                            "El cierre angular EXCEDE la tolerancia admisible ")
               + r"($" + f"{ang['razon_uso']*100:.0f}" + r"\%$ de la tolerancia).")
    if fe:
        tex.append(r"\item Las distancias fueron reducidas al plano de proyección "
                   r"EPSG:9377 con un factor combinado de "
                   + f"{fe['factor_combinado']:.8f}".replace(".", ",") + r".")
    tex.append(r"\item El procesamiento fue automatizado mediante \textbf{GeoPol Web}, "
               r"garantizando la trazabilidad requerida en interventoría.")
    tex.append(r"\end{itemize}")

    tex.append(bloque_firmas())
    tex.append(r"\end{document}")
    # Adapta el resultado a los paquetes realmente instalados
    return _degradar_latex("\n".join(tex), caps)


# ===================================================================
# 2. NIVELACIÓN
# ===================================================================
def generar_reporte_nivelacion_latex(df_calc, metricas, tipo_nivelacion, autores, tutor,
                                     path_grafico=None, fotos_paths=None,
                                     # --- nuevos, opcionales ---
                                     equipo=None, metadatos=None,
                                     longitud_km=None, orden="Tercer orden",
                                     dist_atras=None, dist_adelante=None,
                                     puntos_correccion=None, puntos_pendiente=None,
                                     bm_partida=None,
                                     ruta_logo="Iconos/logo_geopol.png",
                                     directorio_salida="Reportes_PDF", gestor=None):
    caps = capacidades_latex()
    gestor = gestor or GestorFiguras(directorio_salida)
    tex = [preambulo_v2(ruta_logo=ruta_logo,
                        subcarpeta_figuras=gestor.subcarpeta)]
    tex.append(portada_v2(f"Informe Técnico de Altimetría", autores, tutor,
                             subtitulo=tipo_nivelacion))

    meta = dict(EJEMPLO_METADATOS)
    if equipo:
        meta.update(ficha_equipo_a_metadatos(equipo))
    if bm_partida:
        meta["Punto de amarre"] = (f"{bm_partida.get('codigo','')} — cota "
                                   f"{bm_partida.get('cota','')} m")
        meta["Fuente del amarre"] = bm_partida.get("entidad", "")
    if metadatos:
        meta.update(metadatos)

    # ---------- Análisis ----------
    err_mm = float(metricas.get("error_cierre_mm", 0.0))
    bal = (balance_visuales(dist_atras, dist_adelante)
           if dist_atras and dist_adelante else None)
    K = longitud_km if longitud_km is not None else (bal["longitud_total_km"] if bal else 0.0)
    niv = evaluar_cierre_altimetrico(err_mm, K, orden)
    chq = chequeo_aritmetico_cartera(
        metricas.get("sum_vista_atras", 0), metricas.get("sum_vista_adelante", 0),
        metricas.get("cota_inicial", metricas.get("cota_teorica_final", 0)),
        metricas.get("cota_final_cruda", 0))

    kpis = [
        {"titulo": "Error de cierre",
         "valor": f"{err_mm:.1f} mm".replace(".", ","),
         "sub": f"tolerancia {niv['tolerancia_mm']:.1f} mm".replace(".", ","),
         "estado": niv["estado"]},
        {"titulo": "Orden de nivelación", "valor": f"k = {niv['k']:g}",
         "sub": niv["orden"], "estado": "neutro"},
        {"titulo": "Longitud nivelada",
         "valor": f"{niv['K_km']:.3f} km".replace(".", ","),
         "sub": "K en la fórmula de tolerancia", "estado": "neutro"},
        {"titulo": "Cuadre aritmético",
         "valor": ("correcto" if chq["cuadra"] else "incorrecto"),
         "sub": f"discrepancia {chq['discrepancia']*1000:.2f} mm".replace(".", ","),
         "estado": chq["estado"]},
    ]
    if bal:
        kpis.append({"titulo": "Balance de visuales",
                     "valor": f"{bal['desbalance_pct']:.2f} %".replace(".", ","),
                     "sub": f"desbalance {bal['desbalance_m']:.1f} m".replace(".", ","),
                     "estado": bal["estado"]})
    textos = obtener_contenido_informe("Nivelacion")
    tex.append(r"\section{Introducción}")
    tex.append(textos["intro"])
    tex.append(r"\subsection{Objetivos}")
    tex.append(textos["objetivos"])
    tex.append(r"\section{Marco Teórico y Normativo}")
    tex.append(textos["marco"])
    if "Cerrada" in tipo_nivelacion:
        tex.append(r"Al tratarse de una nivelación cerrada, el circuito inicia y "
                   r"termina en el mismo punto de control, por lo que el error de "
                   r"cierre corresponde a la discrepancia respecto a la cota de partida.")
    else:
        tex.append(r"Al tratarse de una nivelación abierta con control, la línea "
                   r"inicia en un Banco de Nivel conocido y cierra sobre un Banco "
                   r"de Nivel distinto de cota igualmente conocida.")

    # Ficha técnica: va después del marco teórico
    tex.append(ficha_metadatos(meta))

    tex.append(r"\section{Cartera Altimétrica Compensada}")
    tex.append(tabla_larga(df_calc, "Cartera de nivelación procesada", "nivelacion"))

    if fotos_paths:
        tex.append(_mosaico_fotos(gestor, fotos_paths,
                                  "Mosaico de registro fotográfico de placas y BMs",
                                  "Registro Fotográfico de Puntos Verticales"))

    # ---------- Verificaciones ----------
    tex.append(r"\section{Análisis de Errores y Compensación Altimétrica}")
    filas = [
        {"criterio": "Cuadre aritmético de cartera",
         "obtenido": f"{chq['discrepancia']*1000:.2f} mm".replace(".", ","),
         "tolerancia": "0,10 mm", "estado": chq["estado"],
         "norma": "ΣV+ − ΣV− = ΔCota"},
        {"criterio": "Error de cierre altimétrico",
         "obtenido": f"{err_mm:.1f} mm".replace(".", ","),
         "tolerancia": f"{niv['tolerancia_mm']:.1f} mm".replace(".", ","),
         "estado": niv["estado"], "norma": f"e = k√K — {orden}"},
    ]
    if bal:
        filas.append({"criterio": "Balance de visuales atrás/adelante",
                      "obtenido": f"{bal['desbalance_pct']:.2f} %".replace(".", ","),
                      "tolerancia": "2,00 %", "estado": bal["estado"],
                      "norma": "Control de colimación"})
    tex.append(tabla_cumplimiento(filas))

    tex.append(caja_dictamen(
        "Verificación aritmética de la cartera",
        escapar_latex(chq["mensaje"]) + r" $\Sigma V^{+} = \SI{"
        + f"{chq['sigma_mas']:.3f}" + r"}{\metre}$, $\Sigma V^{-} = \SI{"
        + f"{chq['sigma_menos']:.3f}" + r"}{\metre}$.", chq["estado"]))

    tex.append(caja_dictamen(
        f"Dictamen sobre el cierre altimétrico ({escapar_latex(orden)})",
        f"El error de cierre de \\SI{{{abs(err_mm):.1f}}}{{\\milli\\metre}} representa el "
        f"{niv['razon_uso']*100:.0f}\\% de la tolerancia admisible de "
        f"\\SI{{{niv['tolerancia_mm']:.1f}}}{{\\milli\\metre}} para una longitud "
        f"nivelada de \\SI{{{niv['K_km']:.3f}}}{{\\kilo\\metre}}.",
        niv["estado"]))

    if bal:
        tex.append(r"\subsection{Control de colimación y visuales}")
        tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=1pt]")
        tex.append(r"\item Suma de distancias vista atrás: \SI{"
                   + f"{bal['suma_atras']:.1f}" + r"}{\metre}; vista adelante: \SI{"
                   + f"{bal['suma_adelante']:.1f}" + r"}{\metre}.")
        tex.append(r"\item Desbalance: \SI{" + f"{bal['desbalance_m']:.1f}"
                   + r"}{\metre} (" + f"{bal['desbalance_pct']:.2f}".replace(".", ",")
                   + r"\%). Un desbalance reducido minimiza la propagación del "
                     r"error de colimación.")
        tex.append(r"\item Visual más larga: \SI{"
                   + f"{max(bal['visual_max_atras'], bal['visual_max_adelante']):.1f}"
                   + r"}{\metre}; corrección por curvatura y refracción asociada: \SI{"
                   + f"{correccion_curvatura_refraccion(max(bal['visual_max_atras'], bal['visual_max_adelante'])):.5f}"
                   + r"}{\metre}.")
        tex.append(r"\end{itemize}")

    if puntos_correccion:
        det = distribuir_error_altimetrico(puntos_correccion,
                                              float(metricas.get("error_cierre_m", 0.0)))
        tex.append(r"\subsection{Distribución del error punto por punto}")
        df_c = pd.DataFrame([{"Punto": d["punto"],
                              "Distancia acumulada": d["distancia_acum"],
                              "Cota cruda": d["cota_cruda"],
                              "Correccion mm": d["correccion_mm"],
                              "Cota ajustada": d["cota_ajustada"]} for d in det])
        tex.append(tabla_larga(df_c, "Corrección altimétrica aplicada por punto",
                                  "correcciones",
                                  notas="La corrección se distribuye proporcionalmente "
                                        "a la distancia acumulada."))

    if puntos_pendiente:
        pend = pendientes_entre_puntos(puntos_pendiente)
        tex.append(r"\subsection{Pendientes resultantes}")
        df_pe = pd.DataFrame([{"Tramo": p["tramo"],
                               "Distancia horizontal": p["dist_horizontal"],
                               "Desnivel": p["desnivel"],
                               "Pendiente %": p["pendiente_pct"],
                               "Sentido": p["sentido"]} for p in pend])
        tex.append(tabla_larga(df_pe, "Pendientes entre puntos consecutivos",
                                  "pendientes",
                                  notas="Verificar contra las pendientes mínima y "
                                        "máxima admisibles del RAS para diseño por "
                                        "gravedad."))

    # Panel de indicadores: cierra la secuencia de resultados numéricos y da
    # paso al perfil. Va aquí, no tras el índice, para que continúe la
    # información en lugar de ocupar una página suelta.
    tex.append(r"\subsection{Resumen de Indicadores del Levantamiento}")
    tex.append(panel_kpi(kpis, columnas=3))

    if path_grafico:
        tex.append(_figura(gestor, path_grafico,
                           "Perfil altimétrico de la línea de nivelación compensada "
                           "(exageración vertical aplicada)",
                           "Perfil Topográfico de Nivelación",
                           nombre="perfil_nivelacion"))

    tex.append(r"\section{Conclusiones}")
    tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=3pt]")
    tex.append(r"\item " + escapar_latex(chq["mensaje"]))
    tex.append(r"\item " + ("El cierre altimétrico cumple la tolerancia del "
                            if niv["cumple"] else
                            "El cierre altimétrico NO cumple la tolerancia del ")
               + escapar_latex(orden) + r".")
    tex.append(r"\item El ajuste se distribuyó proporcionalmente en los puntos de "
               r"cambio, obteniendo cotas definitivas aptas para obra civil.")
    tex.append(r"\end{itemize}")

    tex.append(bloque_firmas())
    tex.append(r"\end{document}")
    # Adapta el resultado a los paquetes realmente instalados
    return _degradar_latex("\n".join(tex), caps)


# ===================================================================
# 3. VOLÚMENES
# ===================================================================
def generar_reporte_volumenes_latex(df_cubicaje, metricas, autores, tutor,
                                    path_grafico=None, path_masas=None,
                                    paths_secciones=None,
                                    # --- nuevos, opcionales ---
                                    equipo=None, metadatos=None,
                                    material="Material común", secciones=None,
                                    abscisas=None, volumenes_netos=None,
                                    acarreo_libre=100.0, estacion_m=20.0,
                                    capacidad_volqueta=7.0,
                                    ruta_logo="Iconos/logo_geopol.png",
                                    directorio_salida="Reportes_PDF", gestor=None):
    # path_grafico, path_masas y paths_secciones admiten rutas U objetos.
    # paths_secciones: [(abscisa, figura), ...]
    caps = capacidades_latex()
    gestor = gestor or GestorFiguras(directorio_salida)
    tex = [preambulo_v2(ruta_logo=ruta_logo,
                        subcarpeta_figuras=gestor.subcarpeta)]
    tex.append(portada_v2("Memorias de Cálculo y Diseño Vial", autores, tutor,
                             subtitulo="Cubicaje de volúmenes y movimiento de tierras"))

    meta = dict(EJEMPLO_METADATOS)
    meta["Material predominante"] = material
    if equipo:
        meta.update(ficha_equipo_a_metadatos(equipo))
    if metadatos:
        meta.update(metadatos)

    corte = float(metricas.get("Corte_Total", 0.0))
    relleno = float(metricas.get("Relleno_Total", 0.0))
    bal = balance_volumetrico_corregido(corte, relleno, material)
    viaj = viajes_volqueta(bal["corte_suelto"], capacidad_volqueta)
    cmp_ = comparar_metodos_volumen(secciones) if secciones else None
    cm = (curva_masa(abscisas, volumenes_netos)
          if abscisas and volumenes_netos else None)
    acar = (analisis_acarreo(cm["abscisas"], cm["acumulado"], acarreo_libre, estacion_m)
            if cm else None)

    kpis = [
        {"titulo": "Corte (banco)",
         "valor": f"{corte:,.0f}".replace(",", ".") + " m³", "estado": "neutro"},
        {"titulo": "Relleno (compactado)",
         "valor": f"{relleno:,.0f}".replace(",", ".") + " m³", "estado": "neutro"},
        {"titulo": "Balance real",
         "valor": f"{bal['balance_real']:,.0f}".replace(",", ".") + " m³",
         "sub": ("excedente a botadero" if bal["balance_real"] > 0
                 else "requiere préstamo"),
         "estado": "alerta" if abs(bal["balance_real"]) > 0.05 * max(corte, 1) else "ok"},
        {"titulo": "Corte suelto a transportar",
         "valor": f"{bal['corte_suelto']:,.0f}".replace(",", ".") + " m³",
         "sub": f"esponjamiento {bal['esponjamiento']*100:.0f} %", "estado": "neutro"},
        {"titulo": "Viajes de volqueta", "valor": f"{viaj['viajes']:,}".replace(",", "."),
         "sub": f"capacidad {capacidad_volqueta:g} m³", "estado": "neutro"},
        {"titulo": "Balance geométrico",
         "valor": f"{bal['balance_geometrico']:,.0f}".replace(",", ".") + " m³",
         "sub": "sin corregir (referencia)", "estado": "neutro"},
    ]

    textos = obtener_contenido_informe("Volumen")
    tex.append(r"\section{Introducción}")
    tex.append(textos["intro"])
    tex.append(r"\subsection{Objetivos}")
    tex.append(textos["objetivos"])
    tex.append(r"\section{Marco Teórico y Normativo}")
    tex.append(textos["marco"])

    # Ficha técnica: va después del marco teórico
    tex.append(ficha_metadatos(meta))

    # ---------- Balance corregido ----------
    tex.append(r"\section{Balance Volumétrico Real}")
    tex.append(caja_dictamen(
        f"Corrección por esponjamiento y contracción — {escapar_latex(material)}",
        f"El balance geométrico (\\SI{{{bal['balance_geometrico']:.2f}}}{{\\cubic\\metre}}) "
        f"no representa el material realmente movido. Con un esponjamiento de "
        f"{bal['esponjamiento']*100:.0f}\\%, los "
        f"\\SI{{{bal['corte_banco']:.2f}}}{{\\cubic\\metre}} de corte en banco equivalen a "
        f"\\SI{{{bal['corte_suelto']:.2f}}}{{\\cubic\\metre}} sueltos para transporte. "
        f"Con una contracción de {bal['contraccion']*100:.0f}\\%, conformar "
        f"\\SI{{{bal['relleno_compactado']:.2f}}}{{\\cubic\\metre}} compactados exige "
        f"\\SI{{{bal['relleno_en_banco']:.2f}}}{{\\cubic\\metre}} en banco. "
        f"El \\textbf{{balance real}} es de "
        f"\\SI{{{bal['balance_real']:.2f}}}{{\\cubic\\metre}}: "
        + ("excedente a disponer en botadero." if bal["balance_real"] > 0
           else "déficit que exige material de préstamo."),
        estado="alerta"))

    tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=2pt]")
    tex.append(r"\item Factor de compactación aplicado: "
               + f"{bal['factor_compactacion']:.4f}".replace(".", ",") + r".")
    tex.append(r"\item Volumen a botadero: \SI{" + f"{bal['volumen_botadero']:.2f}"
               + r"}{\cubic\metre}; material de préstamo: \SI{"
               + f"{bal['volumen_prestamo']:.2f}" + r"}{\cubic\metre}.")
    tex.append(r"\item Transporte estimado: " + f"{viaj['viajes']:,}".replace(",", ".")
               + r" viajes de volqueta de \SI{" + f"{viaj['capacidad_nominal']:.1f}"
               + r"}{\cubic\metre} (factor de llenado "
               + f"{viaj['factor_llenado']:.2f}".replace(".", ",") + r").")
    tex.append(r"\item Diferencia frente al balance geométrico: \SI{"
               + f"{bal['diferencia_vs_geometrico']:.2f}" + r"}{\cubic\metre}.")
    tex.append(r"\end{itemize}")

    tex.append(r"\section{Cuadro de Movimiento de Tierras}")
    tex.append(tabla_larga(df_cubicaje, "Cuadro generalizado de cubicaje", "cubicaje"))

    # ---------- Métodos ----------
    if cmp_:
        tex.append(r"\section{Contraste de Métodos de Cálculo}")
        tex.append(r"Diferencia entre áreas medias y método prismoidal: \SI{"
                   + f"{cmp_['diferencia_m3']:.2f}" + r"}{\cubic\metre} ("
                   + f"{cmp_['diferencia_pct']:.2f}".replace(".", ",")
                   + r"\%). Método más conservador: \textbf{"
                   + escapar_latex(cmp_["metodo_conservador"]) + r"}.")

        if cmp_.get("ancho_constante"):
            ancho_txt = (f"\\SI{{{cmp_['ancho_seccion']:.2f}}}{{\\metre}}"
                         if cmp_.get("ancho_seccion") else "constante")
            tex.append(
                r"\begin{quote}\small\textbf{Nota sobre la corrección "
                r"prismoidal.} La corrección prismoidal se evalúa mediante "
                r"$C_p = \frac{L}{12}(h_1 - h_2)(w_1 - w_2)$, donde $h$ es la "
                r"cota roja en el eje y $w$ el ancho de la sección. En el "
                r"presente proyecto la plataforma se diseñó con un ancho de "
                r"sección uniforme de " + ancho_txt + r", de modo que "
                r"$w_1 = w_2$ en todos los tramos y el término $(w_1 - w_2)$ "
                r"se anula. En consecuencia, ambos métodos arrojan "
                r"\textbf{resultados idénticos por construcción geométrica}, "
                r"y la diferencia nula que muestra la tabla no obedece a una "
                r"omisión del cálculo sino a la propia geometría del diseño. "
                r"La verificación se conserva en el informe porque deja "
                r"constancia de que el contraste fue ejecutado, y porque "
                r"cualquier variación futura del ancho de banca "
                r"---sobreanchos en curva, ensanchamientos o transiciones--- "
                r"haría que la corrección dejara de ser nula y quedaría "
                r"reflejada automáticamente en esta misma tabla.\end{quote}")
        df_m = pd.DataFrame(cmp_["detalle"]).rename(columns={
            "desde": "Abscisa inicial", "hasta": "Abscisa final",
            "longitud": "Longitud", "v_areas_medias": "Volumen areas medias",
            "v_prismoidal": "Volumen prismoidal", "diferencia": "Diferencia"})
        tex.append(tabla_larga(df_m, "Áreas medias frente a método prismoidal",
                                  "metodos", id_cols=2))

        pp = puntos_de_paso(secciones)
        if pp:
            tex.append(r"\subsection{Puntos de paso}")
            df_pp = pd.DataFrame([{"Abscisa": p["abscisa"], "Transición": p["tipo"],
                                   "Entre abscisas": p.get("entre", "")} for p in pp])
            tex.append(tabla_larga(
                df_pp, "Abscisas de transición entre corte y relleno", "puntos_paso",
                notas="Abscisas de control en obra: la cota roja se anula."))

    # Panel de indicadores: cierra la secuencia de resultados numéricos y da
    # paso al diagrama de masas. Va aquí, no tras el índice, para que continúe
    # la información en lugar de ocupar una página suelta.
    tex.append(r"\section{Resumen de Indicadores del Movimiento de Tierras}")
    tex.append(panel_kpi(kpis, columnas=3))

    # ---------- Curva masa y acarreo ----------
    if path_masas:
        tex.append(r"\section{Diagrama de Masas (Curva Masa)}")
        tex.append(r"Evolución del volumen acumulado en función de la abscisa.")
        tex.append(_figura(gestor, path_masas,
                           "Diagrama de masas para compensación longitudinal",
                           None, nombre="curva_masa"))

    if acar:
        tex.append(r"\section{Análisis de Acarreo}")
        tex.append(r"Distancia de acarreo libre considerada: \SI{"
                   + f"{acarreo_libre:.0f}" + r"}{\metre}. "
                   + f"Se identificaron {acar['resumen']['n_lazos']} lazos de "
                   + f"compensación y {len(acar['puntos_compensacion'])} puntos de "
                   + r"compensación.")
        df_a = pd.DataFrame(acar["lazos"]).rename(columns={
            "desde": "Abscisa inicial", "hasta": "Abscisa final",
            "longitud": "Longitud", "tipo": "Tipo",
            "volumen_compensado": "Volumen compensado",
            "area_diagrama": "Area diagrama",
            "distancia_media_transporte": "Distancia media transporte",
            "excede_acarreo_libre": "Excede acarreo libre",
            "sobreacarreo_m3_m": "Sobreacarreo m3-m",
            "sobreacarreo_m3_estacion": "Sobreacarreo m3-estacion"})
        tex.append(tabla_larga(
            df_a, "Análisis de acarreo por lazos del diagrama de masas", "acarreo",
            notas="La distancia media de transporte es el cociente entre el área "
                  "del lazo y su volumen compensado. El sobreacarreo corresponde "
                  "al transporte que excede la distancia de acarreo libre.",
            id_cols=2))
        tex.append(caja_dictamen(
            "Resumen de acarreo y disposición de material",
            f"Volumen total compensado: "
            f"\\SI{{{acar['resumen']['volumen_total_compensado']:.2f}}}{{\\cubic\\metre}}. "
            f"Sobreacarreo acumulado: "
            f"\\num{{{acar['resumen']['sobreacarreo_total_m3_estacion']:.2f}}} "
            f"m\\textsuperscript{{3}}-estación de \\SI{{{estacion_m:.0f}}}{{\\metre}}. "
            f"Volumen a botadero: "
            f"\\SI{{{acar['resumen']['volumen_botadero']:.2f}}}{{\\cubic\\metre}}; "
            f"material de préstamo: "
            f"\\SI{{{acar['resumen']['volumen_prestamo']:.2f}}}{{\\cubic\\metre}}.",
            estado="alerta"))

    if path_grafico:
        tex.append(_figura(gestor, path_grafico,
                           "Planta del alineamiento del proyecto",
                           "Alineamiento del Proyecto", nombre="planta_alineamiento"))

    tex.append(r"\section{Conclusiones y Dictamen Técnico}")
    tex.append(r"\begin{itemize}[leftmargin=1.2em,itemsep=3pt]")
    tex.append(r"\item " + evaluar_volumen(bal["balance_real"], corte, relleno))
    tex.append(r"\item El balance corregido difiere del geométrico en \SI{"
               + f"{bal['diferencia_vs_geometrico']:.2f}" + r"}{\cubic\metre}; "
               r"emplear el balance geométrico subestimaría la necesidad de material.")
    if cmp_:
        tex.append(r"\item La diferencia entre métodos de cálculo es de "
                   + f"{cmp_['diferencia_pct']:.2f}".replace(".", ",") + r"\%.")
    tex.append(r"\item El \textbf{diagrama de masas} identifica los puntos críticos "
               r"y la distribución longitudinal del material.")
    tex.append(r"\end{itemize}")

    # ---------- Anexo de secciones ----------
    if paths_secciones:
        tex.append(_anexo_secciones(gestor, paths_secciones))

    tex.append(bloque_firmas())
    tex.append(r"\end{document}")
    # Adapta el resultado a los paquetes realmente instalados
    return _degradar_latex("\n".join(tex), caps)


# ===================================================================
# AUXILIARES DE MAQUETACIÓN
# ===================================================================
def _figura(gestor, figura, caption, titulo_seccion=None,
            nombre="figura", ancho=0.95):
    """
    Inserta una figura. 'figura' puede ser una ruta o un objeto en memoria
    (matplotlib, plotly, PIL, numpy, bytes, base64): el gestor lo
    materializa dentro de <directorio_salida>/figuras/.
    Si no se pudo obtener, emite un marcador en lugar de romper la
    compilación por un archivo ausente.
    """
    out = []
    if titulo_seccion:
        out.append(r"\section{" + escapar_latex(titulo_seccion) + r"}")
    ruta = gestor.registrar(figura, nombre)
    if ruta is None:
        out.append(figura_no_disponible(caption))
        return "\n".join(out)
    out += [r"\begin{figure}[H]", r"  \centering",
            r"  \includegraphics[width=" + f"{ancho}" + r"\textwidth,"
            r" keepaspectratio]{" + ruta + r"}",
            r"  \caption{" + escapar_latex(caption) + r"}",
            r"\end{figure}"]
    return "\n".join(out)


def _mosaico_fotos(gestor, fotos, caption, titulo, max_fotos=6):
    """Mosaico 2xN con minipage: evita el desbordamiento del margen."""
    rutas = gestor.registrar_varias(list(fotos)[:max_fotos], "foto")
    out = [r"\subsection{" + escapar_latex(titulo) + r"}"]
    if not rutas:
        out.append(figura_no_disponible(caption))
        return "\n".join(out)
    out += [r"\begin{figure}[H]", r"  \centering"]
    for i, ruta in enumerate(rutas):
        out.append(r"  \begin{minipage}{0.47\textwidth}\centering")
        out.append(r"    \includegraphics[width=\linewidth, height=5cm, "
                   r"keepaspectratio]{" + ruta + r"}")
        out.append(r"  \end{minipage}")
        out.append(r"  \\[0.4cm]" if i % 2 == 1 else r"  \hfill")
    out += [r"  \caption{" + escapar_latex(caption) + r"}", r"\end{figure}"]
    return "\n".join(out)


def _anexo_secciones(gestor, secciones, por_plancha=8):
    """secciones: [(abscisa, figura), ...]. La figura puede ser objeto o ruta."""
    pares = gestor.registrar_secciones(sorted(secciones, key=lambda x: x[0]))
    out = [r"\newpage",
           r"\section{Anexo Gráfico: Perfiles de Secciones Transversales}"]
    if not pares:
        out.append(figura_no_disponible("secciones transversales"))
        return "\n".join(out)
    planchas = [pares[i:i + por_plancha] for i in range(0, len(pares), por_plancha)]
    for j, chunk in enumerate(planchas):
        out += [r"\begin{figure}[H]", r"  \centering"]
        for i, (absc, ruta) in enumerate(chunk):
            out.append(r"  \begin{minipage}{0.47\textwidth}\centering")
            out.append(r"    \includegraphics[width=\linewidth, "
                       r"keepaspectratio]{" + ruta + r"}\\")
            out.append(r"    {\scriptsize Abscisa " + escapar_latex(str(absc)) + r"}")
            out.append(r"  \end{minipage}")
            out.append(r"  \\[0.35cm]" if i % 2 == 1 else r"  \hfill")
        out += [r"  \caption{Secciones transversales --- plancha " + str(j + 1) + r"}",
                r"\end{figure}"]
        if j < len(planchas) - 1:
            out.append(r"\newpage")
    return "\n".join(out)


# ===================================================================
# DICTÁMENES (versión con \textbf válido dentro de las cajas)
# ===================================================================
def evaluar_precision(prec_h):
    if prec_h <= 0:
        return ("La poligonal presenta un error matemático crítico o no logró cerrar. "
                "Es obligatorio revisar la cartera de campo y garantizar el amarre "
                "correcto de los datos.")
    if prec_h < 1000:
        return (f"Se obtuvo una precisión de 1:{int(prec_h)}, calificada como "
                r"\textbf{DEFICIENTE}. No cumple los estándares mínimos para "
                "levantamientos topográficos convencionales; se recomienda revisar "
                "los ángulos observados o repetir la medición en campo.")
    if prec_h < 5000:
        return (f"Se obtuvo una precisión de 1:{int(prec_h)}, calificada como "
                r"\textbf{BAJA}. Aceptable únicamente para levantamientos rurales "
                "expeditos o estimaciones preliminares.")
    if prec_h < 15000:
        return (f"Se obtuvo una precisión de 1:{int(prec_h)}, calificada como "
                r"\textbf{BUENA}. Cumple los estándares para levantamientos urbanos "
                "y diseño de obras civiles de rigor intermedio.")
    return (f"Se obtuvo una precisión de 1:{int(prec_h)}, calificada como "
            r"\textbf{ALTA}. Aplicable a redes de control de alta exigencia e "
            "infraestructura pesada.")


def evaluar_volumen(neto, corte, relleno):
    if neto > 0:
        return ("El balance volumétrico exige transporte de material excedentario "
                "hacia un sitio de disposición final (botadero).")
    if neto < 0:
        return ("El diseño requiere importación de material de préstamo, dado que "
                "el relleno supera el material obtenido por excavación.")
    return ("El diseño presenta compensación volumétrica prácticamente perfecta, "
            "optimizando costos de movimiento de tierras y transporte.")


def _tabla_metricas_cierre(metricas):
    out = [r"\begin{table}[H]", r"  \centering \small",
           r"  \caption{Métricas de cierre geométrico previas al ajuste}",
           r"  \begin{tabular}{l S[table-format=2.5]}", r"    \toprule",
           r"    \rowcolor{GeoBlue}",
           r"    \textcolor{white}{\bfseries Parámetro analizado} & "
           r"{\textcolor{white}{\bfseries Magnitud}} \\", r"    \midrule"]
    filas = [
        (r"Error horizontal Este ($e_x$) [m]", metricas.get("err_e_ant", 0)),
        (r"Error horizontal Norte ($e_y$) [m]", metricas.get("err_n_ant", 0)),
        (r"Error vertical ($\Delta Z$) [m]", metricas.get("err_v_ant", 0)),
        (r"Error lineal de cierre ($e_L$) [m]", metricas.get("err_h_ant", 0)),
    ]
    for i, (nombre, val) in enumerate(filas):
        if i % 2 == 0:
            out.append(r"    \rowcolor{GeoBlue!5}")
        out.append(f"    {nombre} & {numero_plano(val, 5)} \\\\")
    out.append(r"    \midrule")
    out.append(r"    Error angular bruto & {"
               + escapar_latex(str(metricas.get("err_ang_ant", "---"))) + r"} \\")
    out.append(r"    \rowcolor{GeoBlue!5}")
    out.append(r"    Precisión planimétrica & {1:"
               + str(int(metricas.get("prec_h", 0) or 0)) + r"} \\")
    out.append(r"    Precisión vertical & {1:"
               + str(int(metricas.get("prec_v", 0) or 0)) + r"} \\")
    out += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return "\n".join(out)


# ===================================================================
# BLOQUE 8 - COMPILACIÓN A PDF
# ===================================================================
# pdflatex emite bytes en la codificación del sistema (latin-1 en Windows).
# text=True sin errors="replace" revienta con UnicodeDecodeError.
_SUB = dict(capture_output=True, text=True, encoding="utf-8", errors="replace")


def _errores_del_log(ruta_log, max_errores=6):
    """Extrae las líneas de error reales del .log (mucho más útil que el stdout)."""
    if not os.path.exists(ruta_log):
        return "No se generó archivo .log."
    with open(ruta_log, "r", encoding="utf-8", errors="ignore") as f:
        lineas = f.readlines()
    errores = []
    for i, ln in enumerate(lineas):
        if ln.startswith("!") or re.match(r"^l\.\d+", ln):
            bloque = "".join(lineas[i:i + 4]).strip()
            errores.append(bloque)
        if len(errores) >= max_errores:
            break
    return "\n\n".join(errores) if errores else "Sin errores explícitos en el .log."


def limpiar_auxiliares(output_dir, nombre):
    for ext in (".aux", ".out", ".toc", ".lof", ".lot", ".fls",
                ".fdb_latexmk", ".synctex.gz"):
        p = os.path.join(output_dir, nombre + ext)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def compilar_latex_a_pdf(tex_code, output_dir="Reportes_PDF",
                         filename="Reporte_Final", limpiar=True, gestor=None):
    r"""
    Devuelve (pdf_bytes, ruta, mensaje). 'mensaje' es "OK" o "OK con advertencias: ..."

    IMPORTANTE: pdflatex se ejecuta con cwd=output_dir en lugar de usar
    -output-directory. Es lo que permite que \includegraphics{figuras/x.pdf}
    resuelva correctamente: con -output-directory las rutas de imagen se
    buscan desde el CWD del proceso (que en un servidor web no es la raíz
    del proyecto), y los gráficos no aparecían.

    Si pasas el mismo 'gestor' usado al generar el informe, las figuras que
    no se pudieron incorporar se reportan en el mensaje de salida.
    """
    os.makedirs(output_dir, exist_ok=True)

    nombre = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(filename))
    nombre = re.sub(r"_+", "_", nombre).strip("_") or "Reporte_Topografico"

    tex_path = os.path.join(output_dir, f"{nombre}.tex")
    pdf_path = os.path.join(output_dir, f"{nombre}.pdf")
    log_path = os.path.join(output_dir, f"{nombre}.log")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_code)

    if shutil.which("pdflatex") is None:
        return None, tex_path, "Error: el sistema no encuentra 'pdflatex'."

    # Rutas relativas al directorio de salida: pdflatex corre dentro de él.
    cmd_tex = ["pdflatex", "-interaction=nonstopmode", f"{nombre}.tex"]
    advertencias = []
    if gestor is not None and gestor.fallidas:
        advertencias.append("figuras no incorporadas: " + ", ".join(
            f"{n} ({m})" for n, m in gestor.fallidas))

    try:
        # Pasada 1: genera .aux
        subprocess.run(cmd_tex, cwd=output_dir, timeout=180, **_SUB)

        # Pasadas 2 y 3: tabla de contenido, referencias cruzadas
        # y \pageref{LastPage}
        subprocess.run(cmd_tex, cwd=output_dir, timeout=180, **_SUB)
        subprocess.run(cmd_tex, cwd=output_dir, timeout=180, **_SUB)

        if not os.path.exists(pdf_path):
            detalle = _errores_del_log(log_path)
            diag = diagnostico_latex()
            ayuda = ""
            if diag["apt_faltantes"]:
                ayuda = ("\n\nPaquetes de LaTeX ausentes en este servidor: "
                         + ", ".join(diag["faltantes"])
                         + ".\nAñade a packages.txt:\n\n"
                         + diag["packages_txt"])
            return None, tex_path, ("LaTeX no generó PDF. Errores detectados:\n\n"
                                    + detalle + ayuda)

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        if limpiar:
            limpiar_auxiliares(output_dir, nombre)

        msg = "OK" if not advertencias else "OK con advertencias: " + " | ".join(advertencias)
        return pdf_bytes, pdf_path, msg

    except subprocess.TimeoutExpired:
        return None, tex_path, "La compilación excedió el tiempo límite."
    except Exception as e:
        return None, tex_path, f"Error en Python al invocar LaTeX: {e}"
