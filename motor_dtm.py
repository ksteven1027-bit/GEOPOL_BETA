# ===================================================================
# MOTOR DTM (MODELO DIGITAL DE TERRENO) - GEO_POL WEB
# Actualizado: Restricción máxima de interpolación a 100m
#
# CORRECCIONES APLICADAS:
#  1. extraer_elevaciones_dtm ya NO rellena los huecos con el promedio
#     global de cotas (inventaba terreno y contaminaba el cubicaje).
#     Ahora usa el vecino más cercano y puede informar qué puntos
#     quedaron fuera de la cobertura del TIN.
#  2. Enmascarado de triángulos vectorizado (antes era un bucle Python
#     sobre cada símplex: inviable con nubes grandes).
#  3. DPI y tamaño de figura parametrizables. El valor anterior
#     (20x20 in @ 400 dpi = 8000x8000 px) generaba un PNG de varios MB
#     que ralentizaba el visor de Folium.
#  4. Validación explícita cuando no hay puntos suficientes para
#     triangular, en vez de dejar reventar a scipy.
# ===================================================================
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.spatial import Delaunay
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from matplotlib.tri import Triangulation


def _preparar_nube(df):
    """Limpia y valida la nube de puntos antes de triangular."""
    faltantes = [c for c in ("Este", "Norte", "Cota") if c not in df.columns]
    if faltantes:
        raise ValueError(f"La nube de puntos no contiene las columnas: {', '.join(faltantes)}.")

    df_clean = df.copy()
    for c in ("Este", "Norte", "Cota"):
        df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce")

    df_clean = df_clean.dropna(subset=["Este", "Norte", "Cota"]).drop_duplicates(subset=["Este", "Norte"])

    if len(df_clean) < 3:
        raise ValueError(
            f"Se requieren al menos 3 puntos válidos con cota para generar el modelo. "
            f"Se encontraron {len(df_clean)}. Verifique la asignación de columnas."
        )

    return (
        df_clean["Este"].to_numpy(dtype=float),
        df_clean["Norte"].to_numpy(dtype=float),
        df_clean["Cota"].to_numpy(dtype=float),
    )


def generar_dtm_curvas(df, ruta_salida, transformador_wgs, max_dist=100.0,
                       niveles=25, dpi=150, tam_pulgadas=10):
    """
    Genera un modelo TIN y curvas de nivel, filtrando los triángulos
    que tengan una longitud de arista mayor a max_dist (por defecto 100m).
    Devuelve los bounds [[lat_min, lon_min], [lat_max, lon_max]] para Folium.
    """
    x, y, z = _preparar_nube(df)

    tri = Delaunay(np.c_[x, y])
    simplices = tri.simplices

    # Enmascarado vectorizado: longitud máxima de arista por triángulo
    pts = np.stack([np.c_[x[simplices[:, k]], y[simplices[:, k]]] for k in range(3)], axis=1)
    d1 = np.linalg.norm(pts[:, 0] - pts[:, 1], axis=1)
    d2 = np.linalg.norm(pts[:, 1] - pts[:, 2], axis=1)
    d3 = np.linalg.norm(pts[:, 2] - pts[:, 0], axis=1)
    mask = np.maximum(np.maximum(d1, d2), d3) > float(max_dist)

    if mask.all():
        raise ValueError(
            f"Todos los triángulos superan la distancia máxima de interpolación ({max_dist} m). "
            f"Aumente el parámetro o revise las unidades de las coordenadas."
        )

    triang = Triangulation(x, y, simplices)
    triang.set_mask(mask)

    fig, ax = plt.subplots(figsize=(tam_pulgadas, tam_pulgadas))
    ax.tricontourf(triang, z, levels=niveles, cmap="terrain", alpha=0.55)

    contour_lines = ax.tricontour(triang, z, levels=niveles, colors="#5D4037", linewidths=0.3, alpha=0.6)
    ax.clabel(contour_lines, inline=True, fontsize=7, colors="black", fmt="%.1f")

    # El overlay debe cubrir exactamente el rectángulo de los bounds:
    # se fijan los límites al extent real de los datos y se elimina el margen.
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(y.min(), y.max())
    ax.set_position([0, 0, 1, 1])
    ax.set_axis_off()

    fig.savefig(ruta_salida, transparent=True, pad_inches=0, dpi=dpi)
    plt.close(fig)

    min_lon, min_lat = transformador_wgs.transform(float(x.min()), float(y.min()))
    max_lon, max_lat = transformador_wgs.transform(float(x.max()), float(y.max()))

    bounds = [[min_lat, min_lon], [max_lat, max_lon]]
    return bounds


def extraer_elevaciones_dtm(x_eval, y_eval, df, retornar_mascara=False):
    """
    Toma coordenadas en un eje plano y obtiene la elevación interpolada del TIN.

    Los puntos que caen FUERA del casco convexo del modelo se completan con el
    vecino más cercano (no con el promedio global, que introducía terreno
    ficticio en el cubicaje). Si retornar_mascara=True devuelve además un array
    booleano indicando qué puntos fueron extrapolados.
    """
    x, y, z = _preparar_nube(df)

    x_eval = np.asarray(x_eval, dtype=float)
    y_eval = np.asarray(y_eval, dtype=float)

    interp = LinearNDInterpolator(np.c_[x, y], z)
    z_eval = interp(x_eval, y_eval)

    fuera = np.isnan(z_eval)
    if fuera.any():
        # Relleno por vecino más cercano: conserva el orden de magnitud real
        interp_nn = NearestNDInterpolator(np.c_[x, y], z)
        z_eval[fuera] = interp_nn(x_eval[fuera], y_eval[fuera])

    if retornar_mascara:
        return z_eval, fuera
    return z_eval
