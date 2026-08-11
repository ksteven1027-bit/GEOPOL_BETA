# ===================================================================
# MOTOR GRÁFICO PARA DISEÑO VIAL (PLANTA CAD AVANZADA)
# Desarrollado para GeoPol Web
#
# CORRECCIONES APLICADAS:
#  1. Se elimina el uso del índice de iterrows() como posición entera.
#     Si el usuario borraba una fila en el editor, el DataFrame dejaba
#     de tener RangeIndex y el plano se dibujaba mal o reventaba con
#     IndexError al hacer df_vertical.iloc[i] / df_pis.iloc[i+1].
#  2. Acceso tolerante a las columnas del cuadro de curvas: si el
#     reporte cambia de esquema no se cae el renderizado completo.
#  3. La barra de escala ya no depende de la escala elegida para su
#     altura (antes crecía de forma desproporcionada) y se ancla en
#     coordenadas de ejes, no de datos.
#  4. Comparaciones de flotantes contra cero reemplazadas por tolerancia.
# ===================================================================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd

_EPS = 1e-9


def _num(valor, defecto=0.0):
    """Conversión numérica tolerante a None / NaN / texto."""
    try:
        v = float(valor)
        return defecto if np.isnan(v) else v
    except (TypeError, ValueError):
        return defecto


def generar_plano_vias(df_eje, df_curvas, df_pis, df_vertical=None, ancho_calzada=7.2,
                       titulo="Diseño Geométrico de Vías (Planta)", incluir_cuadro_curvas=False):
    # Normalización de índices: imprescindible para poder usar posiciones
    df_eje = df_eje.reset_index(drop=True)
    df_pis = df_pis.reset_index(drop=True) if df_pis is not None else None
    df_curvas = df_curvas.reset_index(drop=True) if df_curvas is not None else None
    df_vertical = df_vertical.reset_index(drop=True) if df_vertical is not None else None

    fig, ax = plt.subplots(figsize=(16, 12))

    ax.grid(True, linestyle="--", color="gray", alpha=0.5)
    ax.set_axisbelow(True)

    min_x, max_x = float(df_eje["Este"].min()), float(df_eje["Este"].max())
    min_y, max_y = float(df_eje["Norte"].min()), float(df_eje["Norte"].max())

    margen_x = (max_x - min_x) * 0.35
    margen_y = (max_y - min_y) * 0.35
    if margen_x < _EPS:
        margen_x = 20.0
    if margen_y < _EPS:
        margen_y = 20.0

    ax.set_xlim(min_x - margen_x, max_x + margen_x)
    ax.set_ylim(min_y - margen_y, max_y + margen_y)
    ax.set_aspect("equal")

    # ---------------- Escala gráfica comercial dinámica ----------------
    ancho_total = (max_x + margen_x) - (min_x - margen_x)
    escala_teorica = ancho_total / 0.20  # 20 cm de ancho útil de papel
    escalas_comerciales = [100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 50000]
    escala_elegida = next((s for s in escalas_comerciales if s >= escala_teorica), 50000)
    scale_length = escala_elegida * 0.05  # 5 cm de barra sobre el papel

    # Anclaje en coordenadas de ejes (0-1): la barra no se deforma con la escala
    x0_ax, y0_ax = 0.62, 0.04
    ancho_ax = scale_length / (ax.get_xlim()[1] - ax.get_xlim()[0])
    alto_ax = 0.008
    segment_ax = ancho_ax / 4

    for i in range(4):
        color1 = "black" if i % 2 == 0 else "white"
        color2 = "white" if i % 2 == 0 else "black"
        ax.add_patch(patches.Rectangle(
            (x0_ax + i * segment_ax, y0_ax), segment_ax, alto_ax,
            facecolor=color1, edgecolor="black", lw=0.6,
            transform=ax.transAxes, zorder=10, clip_on=False))
        ax.add_patch(patches.Rectangle(
            (x0_ax + i * segment_ax, y0_ax + alto_ax), segment_ax, alto_ax,
            facecolor=color2, edgecolor="black", lw=0.6,
            transform=ax.transAxes, zorder=10, clip_on=False))

    ax.text(x0_ax + ancho_ax / 2, y0_ax + 2 * alto_ax + 0.008,
            f"Escala 1:{escala_elegida}  ({scale_length:g} m)",
            ha="center", va="bottom", fontsize=8, fontweight="bold",
            transform=ax.transAxes, zorder=11)

    # ---------------- Eje vial ----------------
    x_eje = df_eje["Este"].to_numpy(dtype=float)
    y_eje = df_eje["Norte"].to_numpy(dtype=float)
    ax.plot(x_eje, y_eje, color="#0D47A1", linewidth=2.5, label="Eje Vial Definitivo")

    # Bordes de calzada (offsets normales)
    if len(x_eje) > 1:
        dx = np.gradient(x_eje)
        dy = np.gradient(y_eje)
        lengths = np.hypot(dx, dy)
        lengths[lengths < _EPS] = _EPS
        nx = -dy / lengths
        ny = dx / lengths
        ax.plot(x_eje + nx * (ancho_calzada / 2), y_eje + ny * (ancho_calzada / 2),
                color="gray", linewidth=1, linestyle="--")
        ax.plot(x_eje - nx * (ancho_calzada / 2), y_eje - ny * (ancho_calzada / 2),
                color="gray", linewidth=1, linestyle="--")

    # ---------------- PIs y tangentes ----------------
    if df_pis is not None and not df_pis.empty:
        ax.scatter(df_pis["Este"], df_pis["Norte"], color="#FF8C00", s=80, marker="^",
                   zorder=5, label="PI (Intersección)", edgecolor="black")

        n_pis = len(df_pis)
        for pos in range(n_pis):
            row = df_pis.iloc[pos]
            lbl = f"{row['PI']}"
            if "Elevacion" in df_pis.columns and pd.notna(row.get("Elevacion")):
                lbl += f"\nZ: {_num(row['Elevacion']):.3f}"
            ax.annotate(lbl, (_num(row["Este"]), _num(row["Norte"])),
                        xytext=(12, 12), textcoords="offset points", fontsize=8, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="orange", lw=1))

            if pos >= n_pis - 1:
                continue

            e1, n1 = _num(row["Este"]), _num(row["Norte"])
            e2, n2 = _num(df_pis.iloc[pos + 1]["Este"]), _num(df_pis.iloc[pos + 1]["Norte"])
            e_mid, n_mid = (e1 + e2) / 2, (n1 + n2) / 2

            dx_line = e2 - e1
            dy_line = n2 - n1
            len_line = np.hypot(dx_line, dy_line)
            if len_line > _EPS:
                nx_text, ny_text = -dy_line / len_line, dx_line / len_line
            else:
                nx_text, ny_text = 0.0, 0.0

            offset_val = max((max_x - min_x) * 0.055, 1.0)
            e_text = e_mid + nx_text * offset_val
            n_text = n_mid + ny_text * offset_val

            # Lectura posicional segura del cuadro vertical
            if df_vertical is not None and pos < len(df_vertical):
                slope = _num(df_vertical.iloc[pos].get("Pendiente Salida (%)"))
                l_geom = _num(df_vertical.iloc[pos].get("Longitud Tramo (m)"), len_line)
            else:
                slope, l_geom = 0.0, len_line

            ang_plot = np.degrees(np.arctan2(n2 - n1, e2 - e1))
            if ang_plot > 90 or ang_plot < -90:
                ang_plot += 180

            ax.plot([e1, e2], [n1, n2], color="gray", linestyle=":", linewidth=1)
            ax.text(e_text, n_text, f"L={l_geom:.3f}m | m={slope:.2f}%", color="#4A4A4A",
                    fontsize=8, ha="center", va="center", rotation=ang_plot,
                    bbox=dict(facecolor="white", alpha=0.8, edgecolor="none", pad=1))

    # ---------------- PC y PT ----------------
    if df_curvas is not None and not df_curvas.empty and "E_PC (m)" in df_curvas.columns:
        for _, row in df_curvas.iterrows():
            if pd.isna(row.get("E_PC (m)")):
                continue
            ax.scatter(_num(row["E_PC (m)"]), _num(row["N_PC (m)"]),
                       color="#43A047", s=40, zorder=6, edgecolor="black")
            ax.annotate("PC", (_num(row["E_PC (m)"]), _num(row["N_PC (m)"])),
                        xytext=(-20, -20), textcoords="offset points",
                        color="green", fontsize=8, fontweight="bold")

            ax.scatter(_num(row["E_PT (m)"]), _num(row["N_PT (m)"]),
                       color="#E53935", s=40, zorder=6, edgecolor="black")
            ax.annotate("PT", (_num(row["E_PT (m)"]), _num(row["N_PT (m)"])),
                        xytext=(5, -20), textcoords="offset points",
                        color="red", fontsize=8, fontweight="bold")

    # ---------------- Cuadro de información de sección ----------------
    if df_curvas is not None and not df_curvas.empty and "Peralte (%)" in df_curvas.columns:
        peralte_max = _num(df_curvas["Peralte (%)"].max(), 2.0)
    else:
        peralte_max = 2.0
    info_text = (f"Ancho de Calzada: {_num(ancho_calzada, 7.2):.2f} m\n"
                 f"Peralte Máx (INVIAS): {peralte_max:.2f} %")
    ax.text(0.02, 0.95, info_text, transform=ax.transAxes, fontsize=10, fontweight="bold",
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="#0D47A1", lw=1.5))

    # ---------------- Flecha Norte ----------------
    norte_x = max_x + (margen_x * 0.6)
    norte_y = max_y + (margen_y * 0.6)
    arrow = patches.FancyArrowPatch((norte_x, norte_y - (margen_y * 0.3)), (norte_x, norte_y),
                                    mutation_scale=20, color="black", zorder=10)
    ax.add_patch(arrow)
    ax.text(norte_x, norte_y + (margen_y * 0.05), "N", ha="center", va="bottom",
            fontsize=14, fontweight="bold")

    ax.set_title(titulo, fontsize=16, fontweight="bold", pad=20, color="#333333")
    ax.set_xlabel("Coordenada Este (X) [m]", fontsize=11, fontweight="bold")
    ax.set_ylabel("Coordenada Norte (Y) [m]", fontsize=11, fontweight="bold")

    for spine in ax.spines.values():
        spine.set_linewidth(1.5)
    ax.legend(loc="upper right", frameon=True, fancybox=True, shadow=True)

    # ---------------- Cuadro de curvas (opcional) ----------------
    # Desactivado por defecto: el plano se entrega limpio y la memoria de
    # cálculo se consulta en la tabla del paso 4 de la aplicación.
    if (incluir_cuadro_curvas and df_curvas is not None and not df_curvas.empty
            and "Vértice (PI)" in df_curvas.columns):
        # (etiqueta visible, columna origen, formato)
        esquema = [
            ("Vértice (PI)", "Vértice (PI)", None),
            ("Deflexión (Δ)", "Deflexión (Δ)", None),
            ("Radio (m)", "Radio (m)", "{:.2f}"),
            ("Tang. (m)", "Tangente (m)", "{:.2f}"),
            ("L. Curva (m)", "Long. Curva (m)", "{:.2f}"),
            ("Peralte (%)", "Peralte (%)", "{:.2f}"),
            ("Pend. (%)", "Pendiente (%)", "{:.2f}"),
            ("Abscisa PC", "Abscisa PC", None),
            ("Abscisa PT", "Abscisa PT", None),
        ]
        esquema = [e for e in esquema if e[1] in df_curvas.columns]

        cell_text = []
        for _, r in df_curvas.iterrows():
            fila = []
            for _, origen, fmt in esquema:
                fila.append(fmt.format(_num(r[origen])) if fmt else str(r[origen]))
            cell_text.append(fila)

        cols = [e[0] for e in esquema]
        anchos_base = {
            "Vértice (PI)": 0.08, "Deflexión (Δ)": 0.18, "Radio (m)": 0.07,
            "Tang. (m)": 0.08, "L. Curva (m)": 0.09, "Peralte (%)": 0.08,
            "Pend. (%)": 0.09, "Abscisa PC": 0.165, "Abscisa PT": 0.165,
        }
        col_widths = [anchos_base.get(c, 0.10) for c in cols]
        total = sum(col_widths)
        col_widths = [w / total for w in col_widths]

        tabla = ax.table(cellText=cell_text, colLabels=cols, loc="bottom", cellLoc="center",
                         bbox=[0.0, -0.45, 1.0, 0.3], colWidths=col_widths)
        tabla.auto_set_font_size(False)
        tabla.set_fontsize(7.5)
        plt.subplots_adjust(bottom=0.45)

    return fig
