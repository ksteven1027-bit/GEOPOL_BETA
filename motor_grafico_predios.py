# ===================================================================
# MOTOR GRÁFICO PARA LEVANTAMIENTOS PREDIALES Y CATASTRO
# Desarrollado para GeoPol Web (Estándar IGAC LADM-COL)
# ===================================================================
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import math
import pandas as pd

def generar_plano_predial(df_vertices, df_linderos, metricas, formato_papel="A4 (21 x 29.7 cm) - Carta", titulo="Plano Predial y Cuadro de Linderos"):
    """Genera un plano CAD 2D del predio con cuadro de áreas y linderos normativo."""
    
    # Mapeo de formatos ISO a pulgadas (Ancho x Alto) en orientación horizontal (Landscape)
    formatos_pulgadas = {
        "A4 (21 x 29.7 cm) - Carta": (11.69, 8.27),
        "A3 (29.7 x 42 cm) - Tabloide": (16.53, 11.69),
        "A2 (42 x 59.4 cm) - Medio Pliego": (23.39, 16.53),
        "A1 (59.4 x 84.1 cm) - Pliego": (33.11, 23.39),
        "A0 (84.1 x 118.9 cm) - Gran Formato": (46.81, 33.11)
    }
    
    # Asignar el tamaño de la figura dinámicamente (por defecto A4 si no se encuentra)
    dimensiones_lienzo = formatos_pulgadas.get(formato_papel, (11.69, 8.27))
    
    # Inicializar el lienzo con el nuevo tamaño dinámico
    fig, ax = plt.subplots(figsize=dimensiones_lienzo, facecolor='white')
    
    ax.grid(True, linestyle='--', color='gray', alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    
    # Extraer coordenadas para dibujo
    x = df_vertices['Este'].astype(float).tolist()
    y = df_vertices['Norte'].astype(float).tolist()
    nombres = df_vertices['Punto'].astype(str).tolist()
    
    # Cierre visual del polígono si no está cerrado
    if x[0] != x[-1] or y[0] != y[-1]:
        x.append(x[0])
        y.append(y[0])
        nombres.append(nombres[0])
        
    min_x, max_x = min(x), max(x)
    min_y, max_y = min(y), max(y)
    dx_tot = max_x - min_x
    dy_tot = max_y - min_y
    if dx_tot == 0: dx_tot = 10
    if dy_tot == 0: dy_tot = 10
    
    # Márgenes y Límites
    margen_x = dx_tot * 0.25
    margen_y_bottom = dy_tot * 0.25
    
    # Incrementamos exclusivamente el margen superior al 45% para alojar el cuadro internamente
    margen_y_top = dy_tot * 0.45 
    
    ax.set_xlim(min_x - margen_x, max_x + margen_x)
    ax.set_ylim(min_y - margen_y_bottom, max_y + margen_y_top)
    ax.set_aspect('equal', adjustable='box')
    
    # Dibujo del Polígono (Predio)
    ax.fill(x, y, color='#4CAF50', alpha=0.2, zorder=1, label='Área Predial')
    ax.plot(x, y, color='#2E7D32', linewidth=2.5, linestyle='-', zorder=2, label='Lindero')
    ax.scatter(x, y, color='red', s=45, edgecolors='black', zorder=3, label='Vértice')
    
    # Centroide aproximado para calcular la dirección hacia "afuera" del polígono
    cx, cy = np.mean(x[:-1]), np.mean(y[:-1])
    
    # Etiquetas de Vértices y Tramos (Linderos)
    for i in range(len(x) - 1):
        # Vértice
        ax.annotate(nombres[i], (x[i], y[i]), xytext=(5, 5), textcoords='offset points', 
                    fontweight='bold', fontsize=9, color='black', zorder=5,
                    bbox=dict(boxstyle="circle,pad=0.2", fc="white", ec="#2E7D32", alpha=0.8))
        
        # Tramo (Lindero)
        dx_line = x[i+1] - x[i]
        dy_line = y[i+1] - y[i]
        dist = math.hypot(dx_line, dy_line)
        
        if dist > 0:
            mid_x = x[i] + dx_line / 2
            mid_y = y[i] + dy_line / 2
            
            # Ángulo para rotar el texto
            angle = math.degrees(math.atan2(dy_line, dx_line))
            if angle > 90 or angle < -90:
                angle += 180
            
            # Buscar el azimut exacto y el colindante en la tabla de linderos
            if i < len(df_linderos):
                azimut_str = df_linderos.iloc[i]['Azimut']
                colindante_str = str(df_linderos.iloc[i].get('Colindante', '---')).strip()
            else:
                azimut_str = ""
                colindante_str = "---"
                
            # Formatear el texto incluyendo el nombre del colindante en mayúsculas
            texto_linea = f"{colindante_str.upper()}\nL= {dist:.2f} m\nAz= {azimut_str}"
            
            # Vector Normal (Perpendicular) para hacer offset hacia afuera
            nx, ny = -dy_line, dx_line
            norm = math.hypot(nx, ny)
            ux, uy = nx / norm, ny / norm
            
            # Verificar si el vector normal apunta hacia el centroide (adentro) o afuera
            vec_cx, vec_cy = mid_x - cx, mid_y - cy
            if (ux * vec_cx + uy * vec_cy) < 0:
                ux, uy = -ux, -uy # Invertir para que apunte hacia afuera
                
            # -----------------------------------------------------------------
            # ALGORITMO MULTILEADER (DIRECTRIZ CAD) PARA TRAMOS CORTOS
            # -----------------------------------------------------------------
            # Definimos el umbral: tramos menores al 6% de la dimensión total
            umbral_corto = math.hypot(dx_tot, dy_tot) * 0.06
            
            if dist < umbral_corto:
                # TRAMO CORTO: Usar Multileader (Flecha indicativa)
                # Alternamos la distancia para evitar que las cajas de los leaders choquen entre sí
                factor_dist = 2.5 if i % 2 == 0 else 4.5 
                push_dist = max(math.hypot(dx_tot, dy_tot) * 0.035, 1.5) * factor_dist
                
                tx = mid_x + ux * push_dist
                ty = mid_y + uy * push_dist
                
                # Se dibuja horizontalmente (sin rotación) apuntando con una flecha al lindero
                ax.annotate(texto_linea, 
                            xy=(mid_x, mid_y),       # Punto exacto al que apunta la flecha (lindero)
                            xytext=(tx, ty),         # Posición de la caja de texto
                            ha='center', va='center', fontsize=7.5, color='#111111',
                            bbox=dict(boxstyle="round,pad=0.2", fc="#f1f8e9", ec="gray", alpha=0.9),
                            arrowprops=dict(arrowstyle="->", color="gray", lw=1.2, connectionstyle="arc3"),
                            zorder=5)
            else:
                # TRAMO NORMAL: Etiqueta clásica paralela al lindero
                push_dist = max(math.hypot(dx_tot, dy_tot) * 0.035, 1.5)
                tx = mid_x + ux * push_dist
                ty = mid_y + uy * push_dist
                
                ax.text(tx, ty, texto_linea, rotation=angle, 
                        ha='center', va='center', fontsize=8.5, color='#111111',
                        bbox=dict(boxstyle="round,pad=0.2", fc="#f1f8e9", ec="none", alpha=0.9), zorder=4)

    # Vértice final
    ax.annotate(nombres[-1], (x[-1], y[-1]), xytext=(5, 5), textcoords='offset points', 
                fontweight='bold', fontsize=9, color='black', zorder=5,
                bbox=dict(boxstyle="circle,pad=0.2", fc="white", ec="#2E7D32", alpha=0.8))

    # -----------------------------------------------------------------
    # CUADRO DE MÉTRICAS (INTERNO CON ESPACIO RESERVADO)
    # -----------------------------------------------------------------
    info_text = (f"RESUMEN PREDIAL\n"
                 f"------------------------\n"
                 f"Área Total: {metricas['Area_m2']:,.2f} m²\n"
                 f"Hectáreas: {metricas['Area_ha']:,.4f} ha\n"
                 f"Perímetro: {metricas['Perimetro_m']:,.2f} m")
    
    # Retorna a la esquina superior izquierda (0.02, 0.97) relativa al eje
    ax.text(0.02, 0.97, info_text, transform=ax.transAxes, fontsize=10, fontweight='bold', 
            va='top', ha='left', zorder=10,
            bbox=dict(boxstyle="round,pad=0.6", facecolor='#f1f8e9', alpha=0.9, edgecolor='#2E7D32', lw=1.5))

    # Símbolo de Norte Profesional (Rosa de los Vientos)
    x_lims, y_lims = ax.get_xlim(), ax.get_ylim()
    n_x = x_lims[1] - (x_lims[1]-x_lims[0]) * 0.05
    n_y = y_lims[1] - (y_lims[1]-y_lims[0]) * 0.08
    sz = (x_lims[1]-x_lims[0]) * 0.035
    
    ax.fill([n_x, n_x, n_x - sz*0.3], [n_y, n_y + sz, n_y], color='black', zorder=10)
    ax.fill([n_x, n_x, n_x + sz*0.3], [n_y, n_y + sz, n_y], color='white', edgecolor='black', zorder=10)
    ax.fill([n_x, n_x, n_x - sz*0.3], [n_y, n_y - sz, n_y], color='white', edgecolor='black', zorder=10)
    ax.fill([n_x, n_x, n_x + sz*0.3], [n_y, n_y - sz, n_y], color='black', zorder=10)
    ax.fill([n_x, n_x + sz, n_x], [n_y, n_y, n_y + sz*0.3], color='black', zorder=10)
    ax.fill([n_x, n_x + sz, n_x], [n_y, n_y, n_y - sz*0.3], color='white', edgecolor='black', zorder=10)
    ax.fill([n_x, n_x - sz, n_x], [n_y, n_y, n_y + sz*0.3], color='white', edgecolor='black', zorder=10)
    ax.fill([n_x, n_x - sz, n_x], [n_y, n_y, n_y - sz*0.3], color='black', zorder=10)
    ax.text(n_x, n_y + sz*1.15, 'N', ha='center', va='bottom', fontsize=16, fontweight='bold')

    # Escala Gráfica Dinámica Comercial
    ancho_total = x_lims[1] - x_lims[0]
    escala_teorica = ancho_total / 0.20 
    escalas_comerciales = [100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000]
    escala_elegida = next((s for s in escalas_comerciales if s >= escala_teorica), 10000)
    scale_length = escala_elegida * 0.05 
    
    e_x = x_lims[1] - scale_length - (x_lims[1]-x_lims[0]) * 0.05
    e_y = y_lims[0] + (y_lims[1]-y_lims[0]) * 0.05
    bar_h = (y_lims[1]-y_lims[0]) * 0.008

    num_segments = 4
    seg_len = scale_length / num_segments
    for j in range(num_segments):
        color = 'black' if j % 2 == 0 else 'white'
        rect = patches.Rectangle((e_x + j*seg_len, e_y), seg_len, bar_h, linewidth=1, edgecolor='black', facecolor=color, zorder=10)
        ax.add_patch(rect)
    
    ax.text(e_x, e_y + bar_h*1.2, '0', ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.text(e_x + scale_length/2, e_y + bar_h*1.2, f'{scale_length/2:g}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.text(e_x + scale_length, e_y + bar_h*1.2, f'{scale_length:g} m', ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.text(e_x + scale_length/2, e_y - bar_h*1.5, f'Escala 1:{escala_elegida}', ha='center', va='top', fontsize=11, fontweight='bold', bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="black", alpha=0.9))

    ax.set_title(titulo, fontsize=16, fontweight='bold', pad=20, color="#333333")
    ax.set_xlabel("Coordenada Este (X) [m]", fontsize=11, fontweight='bold')
    ax.set_ylabel("Coordenada Norte (Y) [m]", fontsize=11, fontweight='bold')
    ax.legend(loc='lower left', frameon=True, fancybox=True, shadow=True)
    
    for spine in ax.spines.values(): spine.set_linewidth(1.5)

    # CAJETÍN: Cuadro de Áreas y Linderos
    if df_linderos is not None and not df_linderos.empty:
        cols = ['Vértice', 'Colindancia', 'Distancia (m)', 'Azimut', 'Este (X)', 'Norte (Y)']
        cell_text = []
        for _, r in df_linderos.iterrows():
            dist_val = f"{r['Distancia (m)']:.3f}" if r['Distancia (m)'] > 0 else "-"
            cell_text.append([str(r['Vértice']), str(r['Colindancia (Lado)']), dist_val, str(r['Azimut']), f"{r['Este (m)']:.3f}", f"{r['Norte (m)']:.3f}"])
            
        tabla = ax.table(cellText=cell_text, colLabels=cols, loc='bottom', cellLoc='center', bbox=[0.0, -0.45, 1.0, 0.3])
        tabla.auto_set_font_size(False)
        tabla.set_fontsize(8.5)
        # Ajustar ancho de las columnas
        tabla.auto_set_column_width(col=list(range(len(cols))))
        plt.subplots_adjust(bottom=0.45) 
    
    return fig