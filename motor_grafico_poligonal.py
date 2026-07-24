# ===================================================================
# MOTOR DE DIBUJO PLANIMÉTRICO (CAD 2D) - VERSIÓN PREMIUM
# Desarrollado para Geoportal Web
# Incorpora: Rosa de los vientos, Escala Gráfica CAD, Escalas ISO,
# y Offset dinámico anti-superposición de etiquetas.
# ===================================================================
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import math

def decimal_a_dms_string(grados_decimales):
    """Convierte grados decimales a formato G° M' S" en string."""
    g = int(grados_decimales)
    m_float = abs(grados_decimales - g) * 60
    m = int(m_float)
    s = (m_float - m) * 60
    return f"{abs(g)}° {m}' {s:.1f}\""

def calcular_rumbo_y_distancia(dx, dy):
    """Calcula la distancia, el rumbo topográfico y el azimut."""
    distancia = math.sqrt(dx**2 + dy**2)
    azimut_rad = math.atan2(dx, dy)
    azimut_deg = math.degrees(azimut_rad)
    
    if azimut_deg < 0:
        azimut_deg += 360
        
    if 0 <= azimut_deg <= 90:
        rumbo = f"N {decimal_a_dms_string(azimut_deg)} E"
    elif 90 < azimut_deg <= 180:
        rumbo = f"S {decimal_a_dms_string(180 - azimut_deg)} E"
    elif 180 < azimut_deg <= 270:
        rumbo = f"S {decimal_a_dms_string(azimut_deg - 180)} W"
    else:
        rumbo = f"N {decimal_a_dms_string(360 - azimut_deg)} W"
        
    return distancia, rumbo, azimut_deg

def generar_plano_profesional(df_ajuste, titulo="Plano Topográfico de Poligonal"):
    """Genera una figura de matplotlib con estética CAD Profesional."""
    
    fig, ax = plt.subplots(figsize=(12, 10), facecolor='white')
    
    x = df_ajuste['X_Estacion'].astype(float).values
    y = df_ajuste['Y_Estacion'].astype(float).values
    nombres = df_ajuste['Estacionado'].astype(str).values

    x_min, x_max = min(x), max(x)
    y_min, y_max = min(y), max(y)
    dx_tot = x_max - x_min
    dy_tot = y_max - y_min
    if dx_tot == 0: dx_tot = 10
    if dy_tot == 0: dy_tot = 10
    
    diag_plano = math.hypot(dx_tot, dy_tot)
    
    # 1. CÁLCULO DE ESCALAS CONVENCIONALES (ISO)
    # Suponiendo que el ancho del gráfico en papel es de ~0.23 metros (9 pulgadas)
    req_scale = (max(dx_tot, dy_tot) * 1.5) / 0.23
    escalas_convencionales = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 50000]
    escala_elegida = next((s for s in escalas_convencionales if s >= req_scale), escalas_convencionales[-1])
    
    # Aplicar márgenes calculados según la escala para que sea un plano riguroso
    ancho_real_lienzo = 0.23 * escala_elegida
    margen_x = (ancho_real_lienzo - dx_tot) / 2
    margen_y = (ancho_real_lienzo - dy_tot) / 2
    
    ax.set_xlim(x_min - margen_x, x_max + margen_x)
    ax.set_ylim(y_min - margen_y, y_max + margen_y)

    if len(x) > 1 and x[0] == x[-1] and y[0] == y[-1]:
        cx, cy = np.mean(x[:-1]), np.mean(y[:-1])
    else:
        cx, cy = np.mean(x), np.mean(y)

    # 2. DIBUJO DE POLÍGONO Y PUNTOS
    ax.plot(x, y, color='#1c39bb', linewidth=2.5, linestyle='-', zorder=2)
    ax.scatter(x, y, color='red', s=50, edgecolors='black', zorder=3)

    # 3. NOMENCLATURA Y TEXTOS ANTI-COLISIÓN
    for i in range(len(x)):
        vx = x[i] - cx
        vy = y[i] - cy
        norm_v = math.hypot(vx, vy)
        if norm_v == 0: norm_v = 1
        
        offset_x = (vx / norm_v) * 20
        offset_y = (vy / norm_v) * 20
        
        if not (i == len(x)-1 and x[i] == x[0] and y[i] == y[0]):
            ax.annotate(nombres[i], (x[i], y[i]), xytext=(offset_x, offset_y), 
                        textcoords='offset points', fontweight='bold', fontsize=10, 
                        color='black', ha='center', va='center', zorder=6,
                        bbox=dict(boxstyle="round,pad=0.3", fc="#ffffcc", ec="gray", alpha=0.9))
        
        if i < len(x) - 1:
            dx_line = x[i+1] - x[i]
            dy_line = y[i+1] - y[i]
            dist, rumbo, azimut = calcular_rumbo_y_distancia(dx_line, dy_line)
            
            mid_x = x[i] + dx_line / 2
            mid_y = y[i] + dy_line / 2
            
            angle = math.degrees(math.atan2(dy_line, dx_line))
            if angle > 90: angle -= 180
            elif angle < -90: angle += 180
                
            texto_linea = f"{rumbo}\nD = {dist:.3f} m"
            
            # Calcular normales para empujar el texto hacia afuera
            nx1, ny1 = -dy_line, dx_line
            nx2, ny2 = dy_line, -dx_line
            
            vec_cx = mid_x - cx
            vec_cy = mid_y - cy
            
            if (nx1 * vec_cx + ny1 * vec_cy) > (nx2 * vec_cx + ny2 * vec_cy):
                nx, ny = nx1, ny1
            else:
                nx, ny = nx2, ny2
                
            norm_n = math.hypot(nx, ny)
            if norm_n == 0: norm_n = 1
            ux, uy = nx / norm_n, ny / norm_n
            
            if dist < (diag_plano * 0.18) and dist > 0:
                push_dist = diag_plano * 0.12
                tx = mid_x + ux * push_dist
                ty = mid_y + uy * push_dist
                
                ax.annotate(texto_linea, xy=(mid_x, mid_y), xytext=(tx, ty),
                            arrowprops=dict(arrowstyle="-|>", color="#666666", lw=1.5),
                            ha='center', va='center', fontsize=8, color='#111111',
                            bbox=dict(boxstyle="round,pad=0.3", fc="#f8f9fa", ec="#aaaaaa", alpha=0.95),
                            zorder=5)
            else:
                # SOLUCIÓN: Incremento del offset (push_dist) para que no pise la línea azul
                push_dist = max(diag_plano * 0.045, 2.5) 
                tx = mid_x + ux * push_dist
                ty = mid_y + uy * push_dist
                
                ax.text(tx, ty, texto_linea, rotation=angle, 
                        ha='center', va='center', fontsize=9, color='#333333',
                        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8),
                        zorder=4)

    lon_flecha = dy_tot * 0.08
    ax.plot([x[0], x[0]], [y[0], y[0] + lon_flecha], color='red', linestyle='--', linewidth=1.5)
    ax.text(x[0], y[0] + lon_flecha * 1.1, 'N (Azimut)', ha='center', va='bottom', fontweight='bold', color='red', fontsize=9)
    
    # 4. CONFIGURAR ASPECTO DE GRILLA
    ax.set_aspect('equal', adjustable='box') 
    ax.grid(True, which='both', color='gray', linestyle='--', linewidth=0.5, alpha=0.6)
    ax.set_xlabel('Coordenada Este (X) - [m]', fontweight='bold')
    ax.set_ylabel('Coordenada Norte (Y) - [m]', fontweight='bold')
    ax.set_title(titulo, fontsize=15, fontweight='bold', pad=20)
    
    # 5. SÍMBOLO DE NORTE PROFESIONAL (Rosa de los Vientos en 3D)
    x_lims, y_lims = ax.get_xlim(), ax.get_ylim()
    n_x = x_lims[1] - (x_lims[1]-x_lims[0]) * 0.05
    n_y = y_lims[1] - (y_lims[1]-y_lims[0]) * 0.08
    sz = (x_lims[1]-x_lims[0]) * 0.035
    
    # Dibujo de la Rosa
    # Punta Superior
    ax.fill([n_x, n_x, n_x - sz*0.3], [n_y, n_y + sz, n_y], color='black', zorder=10)
    ax.fill([n_x, n_x, n_x + sz*0.3], [n_y, n_y + sz, n_y], color='white', edgecolor='black', zorder=10)
    # Punta Inferior
    ax.fill([n_x, n_x, n_x - sz*0.3], [n_y, n_y - sz, n_y], color='white', edgecolor='black', zorder=10)
    ax.fill([n_x, n_x, n_x + sz*0.3], [n_y, n_y - sz, n_y], color='black', zorder=10)
    # Punta Derecha
    ax.fill([n_x, n_x + sz, n_x], [n_y, n_y, n_y + sz*0.3], color='black', zorder=10)
    ax.fill([n_x, n_x + sz, n_x], [n_y, n_y, n_y - sz*0.3], color='white', edgecolor='black', zorder=10)
    # Punta Izquierda
    ax.fill([n_x, n_x - sz, n_x], [n_y, n_y, n_y + sz*0.3], color='white', edgecolor='black', zorder=10)
    ax.fill([n_x, n_x - sz, n_x], [n_y, n_y, n_y - sz*0.3], color='black', zorder=10)
    
    ax.text(n_x, n_y + sz*1.15, 'N', ha='center', va='bottom', fontsize=16, fontweight='bold')

    # 6. ESCALA GRÁFICA TIPO CAD Y ESCALA TEXTUAL
    target_real_length = 0.05 * escala_elegida # Aprox 5cm en papel
    magnitud = 10 ** math.floor(math.log10(target_real_length))
    if target_real_length < 2.5 * magnitud: bar_len = 2 * magnitud
    elif target_real_length < 7.5 * magnitud: bar_len = 5 * magnitud
    else: bar_len = 10 * magnitud

    e_x = x_lims[1] - bar_len - (x_lims[1]-x_lims[0]) * 0.05
    e_y = y_lims[0] + (y_lims[1]-y_lims[0]) * 0.05
    bar_h = (y_lims[1]-y_lims[0]) * 0.008

    # Dibujar escala de ajedrez (Alternando negro y blanco)
    num_segments = 4
    seg_len = bar_len / num_segments
    for j in range(num_segments):
        color = 'black' if j % 2 == 0 else 'white'
        rect = patches.Rectangle((e_x + j*seg_len, e_y), seg_len, bar_h, linewidth=1, edgecolor='black', facecolor=color, zorder=10)
        ax.add_patch(rect)
    
    # Textos de la regla
    ax.text(e_x, e_y + bar_h*1.2, '0', ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.text(e_x + bar_len/2, e_y + bar_h*1.2, f'{bar_len/2:g}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    ax.text(e_x + bar_len, e_y + bar_h*1.2, f'{bar_len:g} m', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Etiqueta ISO Comercial
    ax.text(e_x + bar_len/2, e_y - bar_h*1.5, f'Escala 1:{escala_elegida}', 
            ha='center', va='top', fontsize=12, fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.3", fc="#f8f9fa", ec="black", alpha=0.9))

    for spine in ax.spines.values():
        spine.set_linewidth(2.0)
        
    plt.tight_layout()
    return fig