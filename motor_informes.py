# ===================================================================
# MOTOR DE GENERACIÓN DE INFORMES TÉCNICOS EN LATEX
# Desarrollado para Geoportal Web (GeoPol)
# ===================================================================
import pandas as pd
import numpy as np
import re
from datetime import datetime
import os
import subprocess
import shutil

def escapar_latex(texto):
    if not isinstance(texto, str):
        texto = str(texto)
    reemplazos = {
        '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
    }
    tx = texto
    for key, val in reemplazos.items():
        tx = tx.replace(key, val)
    return tx

def dividir_y_generar_tablas(df, caption, label_prefix, id_cols=2):
    """
    Divide un DataFrame ancho en varias tablas verticales de máximo 6 columnas
    para mantener el formato vertical (portrait) perfectamente legible.
    Mantiene las primeras 'id_cols' columnas como referencia.
    """
    cols = list(df.columns)
    if len(cols) <= (id_cols + 4):
        return dataframe_a_latex_table(df, caption, label_prefix)
    
    base_cols = cols[:id_cols]
    rest_cols = cols[id_cols:]
    
    chunks = [rest_cols[i:i+4] for i in range(0, len(rest_cols), 4)]
    
    latex_str = ""
    for i, chunk in enumerate(chunks):
        sub_df = df[base_cols + chunk]
        latex_str += dataframe_a_latex_table(sub_df, f"{caption} (Parte {i+1})", f"{label_prefix}_{i}")
        latex_str += "\n\\vspace{0.8cm}\n"
    return latex_str

def dataframe_a_latex_table(df, caption, label):
    num_columnas = len(df.columns)
    latex_tab = []
    latex_tab.append(r"\begin{table}[H]")
    latex_tab.append(r"  \centering")
    latex_tab.append(r"  \small")
    latex_tab.append(f"  \\caption{{{escapar_latex(caption)}}}")
    latex_tab.append(f"  \\label{{tab:{label}}}")
    alineacion = "|" + "|".join(["c"] * num_columnas) + "|"
    latex_tab.append(f"  \\begin{{tabular}}{{{alineacion}}}")
    latex_tab.append(r"    \hline")
    latex_tab.append(r"    \rowcolor{GeoBlue}")
    
    headers = [f"\\textcolor{{white}}{{\\textbf{{{escapar_latex(col)}}}}}" for col in df.columns]
    latex_tab.append("    " + " & ".join(headers) + r" \\")
    latex_tab.append(r"    \hline")
    
    for idx, row in df.iterrows():
        fila_items = []
        for col in df.columns:
            val = row[col]
            if pd.isna(val) or val is None:
                fila_items.append("---")
            elif isinstance(val, (int, float, np.number)):
                if abs(val) > 10000:
                    fila_items.append(f"{val:.3f}")
                else:
                    fila_items.append(f"{val:.3f}")
            else:
                fila_items.append(escapar_latex(str(val)))
        
        if idx % 2 == 0:
            latex_tab.append(r"    \rowcolor{GeoBlue!5}")
        else:
            latex_tab.append(r"    \rowcolor{white}")
            
        latex_tab.append("    " + " & ".join(fila_items) + r" \\")
        latex_tab.append(r"    \hline")
        
    latex_tab.append(r"  \end{tabular}")
    latex_tab.append(r"\end{table}")
    
    return "\n".join(latex_tab)

def evaluar_precision(prec_h):
    if prec_h <= 0:
        return "La poligonal presenta un error matemático crítico o no logró cerrar. Es obligatorio revisar la cartera de campo y garantizar el amarre correcto de los datos."
    elif prec_h < 1000:
        return f"Se obtuvo una precisión de 1:{int(prec_h)}. Esta precisión es \\textbf{{DEFICIENTE}}. No cumple con los estándares mínimos para levantamientos topográficos convencionales. Se recomienda enfáticamente revisar los ángulos observados o repetir la medición en campo."
    elif prec_h < 5000:
        return f"Se obtuvo una precisión de 1:{int(prec_h)}. Esta precisión es \\textbf{{BAJA}}. Es aceptable únicamente para levantamientos rurales expeditos o estimaciones preliminares, pero carece de la fiabilidad necesaria para la ejecución de obra civil de detalle."
    elif prec_h < 15000:
        return f"Se obtuvo una precisión de 1:{int(prec_h)}. Esta precisión es \\textbf{{BUENA}}. Cumple plenamente con los estándares vigentes para levantamientos urbanos, topografía convencional y diseño de obras civiles de rigor intermedio."
    else:
        return f"Se obtuvo una precisión de 1:{int(prec_h)}. Esta precisión es \\textbf{{ALTA}}. Demuestra un excelente trabajo de campo y de instrumentación. Este nivel de error es aplicable para redes de control de alta exigencia, proyectos de infraestructura pesada o trazados geodésicos."

def evaluar_volumen(neto, corte, relleno):
    if neto > 0:
        return f"Dado el balance volumétrico resultante, el proyecto requiere de un transporte de material excedentario hacia un sitio de disposición final (botadero), ya que los volúmenes de excavación superan a los terraplenes requeridos."
    elif neto < 0:
        return f"El diseño geométrico evaluado requiere la importación de material de préstamo, dado que el volumen de relleno (terraplén) supera la cantidad de material obtenido por excavación."
    else:
        return f"El diseño presenta una compensación volumétrica prácticamente perfecta, optimizando al máximo los costos de movimiento de tierras y transporte."

def generar_preambulo_y_caratula(titulo_informe, autores, tutor, tipo_poligonal=None):
    tex = []
    tex.append(r"\documentclass[11pt,letterpaper]{article}")
    tex.append(r"\usepackage[utf8]{inputenc}")
    tex.append(r"\usepackage[spanish,es-tabla]{babel}")
    tex.append(r"\usepackage[margin=2.5cm]{geometry}")
    tex.append(r"\usepackage{amsmath,amssymb}")
    tex.append(r"\usepackage{booktabs}")
    tex.append(r"\usepackage{graphicx}")
    tex.append(r"\usepackage{float}")
    tex.append(r"\usepackage{fancyhdr}")
    tex.append(r"\usepackage{hyperref}")
    tex.append(r"\usepackage[table]{xcolor}")
    tex.append(r"\usepackage{tikz}")
    tex.append(r"\usepackage{transparent}")
    tex.append(r"\usepackage{eso-pic}")
    tex.append(r"\usepackage{caption}")
    
    tex.append(r"\definecolor{GeoOrange}{HTML}{FF8C00}")
    tex.append(r"\definecolor{GeoBlue}{HTML}{0D47A1}")
    
    # MARCA DE AGUA (WATERMARK)
    ruta_logo = "Iconos/logo_geopol.png"
    if os.path.exists(ruta_logo):
        ruta_logo_latex = ruta_logo.replace('\\', '/')
        tex.append(r"\AddToShipoutPictureBG{")
        tex.append(r"  \AtPageCenter{")
        tex.append(f"    \\makebox[0pt]{{\\transparent{{0.06}}\\includegraphics[width=12cm]{{{ruta_logo_latex}}}}}")
        tex.append(r"  }")
        tex.append(r"}")
    
    tex.append(r"\hypersetup{colorlinks=true, linkcolor=GeoBlue, urlcolor=GeoOrange}")
    tex.append(r"\pagestyle{fancy}")
    tex.append(r"\fancyhf{}")
    tex.append(r"\fancyhead[L]{\footnotesize \textcolor{GeoBlue}{\textbf{GeoPol Web}} - Reporte Técnico}")
    tex.append(r"\fancyhead[R]{\footnotesize Universidad Distrital F.J.C.}")
    tex.append(r"\fancyfoot[C]{\thepage}")
    tex.append(r"\renewcommand{\headrulewidth}{0.4pt}")
    tex.append(r"\renewcommand{\footrulewidth}{0.4pt}")
    
    tex.append(r"\begin{document}")
    
    # PORTADA
    tex.append(r"\begin{titlepage}")
    tex.append(r"\begin{tikzpicture}[remember picture,overlay]")
    tex.append(r"  \fill[GeoBlue] (current page.north west) rectangle ([yshift=-4cm]current page.north east);")
    tex.append(r"  \fill[GeoOrange] ([yshift=-4cm]current page.north west) rectangle ([yshift=-4.5cm]current page.north east);")
    tex.append(r"  \fill[GeoBlue!5] (current page.south west) rectangle ([yshift=4cm]current page.south east);")
    tex.append(r"\end{tikzpicture}")
    
    tex.append(r"\vspace*{-2cm}")
    tex.append(r"\begin{center}")
    tex.append(r"  \textcolor{white}{\Huge \textbf{GEOPORTAL WEB (GeoPol)}} \\[0.5cm]")
    tex.append(r"  \textcolor{white}{\large \textit{''Máxima precisión al alcance de tus manos''}} \\[2cm]")
    tex.append(r"  \vspace{3cm}")
    tex.append(r"  {\LARGE \textbf{INFORME TÉCNICO DE INGENIERÍA}} \\[0.5cm]")
    if tipo_poligonal:
        tex.append(f"  {{\\Large \\textbf{{{tipo_poligonal}}}}} \\\\[2cm]")
    else:
        tex.append(f"  {{\\Large \\textbf{{{titulo_informe}}}}} \\\\[2cm]")
    
    tex.append(r"  \begin{flushleft}")
    tex.append(r"    \Large \textbf{Autores del Procesamiento:}\\[0.2cm]")
    for aut in autores:
        tex.append(f"    \\large $\\bullet$ {escapar_latex(aut)} \\\\[0.1cm]")
    tex.append(r"    \vspace{1cm}")
    tex.append(r"    \Large \textbf{Tutor - Director de Proyecto:}\\[0.2cm]")
    tex.append(f"    \\large $\\bullet$ {escapar_latex(tutor)}")
    tex.append(r"  \end{flushleft}")
    tex.append(r"  \vfill")
    tex.append(r"  \textbf{UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS}\\[0.2cm]")
    tex.append(r"  Facultad de Medio Ambiente y Recursos Naturales \\ Ingeniería Topográfica / Civil \\[0.2cm]")
    tex.append(f"  Bogotá D.C. -- {datetime.now().strftime('%d de %B de %Y')}")
    tex.append(r"\end{center}")
    tex.append(r"\end{titlepage}")
    
    tex.append(r"\tableofcontents")
    tex.append(r"\newpage")
    return "\n".join(tex)


def generar_reporte_poligonal_latex(df_campo, df_ajuste, metricas, tipo_poligonal, autores, tutor, path_grafico=None, fotos_paths=None):
    tex = [generar_preambulo_y_caratula(tipo_poligonal, autores, tutor, tipo_poligonal)]
    
    tex.append(r"\section{Marco Teórico y Referencia Geodésica}")
    tex.append(r"El presente informe detalla el cálculo, ajuste y representación de una red de apoyo planimétrico. Este procesamiento se apoya en los lineamientos técnicos de la Topografía Clásica y la normatividad geodésica dictada por el \textbf{Instituto Geográfico Agustín Codazzi (IGAC)}.")
    tex.append(r"\subsection{Sistema de Georreferenciación (MAGNA-SIRGAS)}")
    tex.append(r"De acuerdo con la \textbf{Resolución 471 de 2020} (y su modificación en la Resolución 529 de 2020) emitida por el IGAC, el único sistema oficial de coordenadas para la República de Colombia es el Origen Nacional \textbf{MAGNA-SIRGAS (EPSG: 9377)}.")
    
    tex.append(r"\subsection{Fundamento Matemático: " + tipo_poligonal + "}")
    if "Cerrada" in tipo_poligonal:
        tex.append(r"Una Poligonal Cerrada de Circuito es aquella que inicia en una estación conocida y, tras medir una serie de vértices (deltas), retorna matemáticamente al mismo punto de origen. Esto permite una doble comprobación de errores:")
        tex.append(r"\begin{itemize}")
        tex.append(r"  \item \textbf{Cierre Angular:} La suma teórica de los ángulos internos debe cumplir $\Sigma \alpha = (n - 2) \cdot 180^\circ$. El error angular se compensa en partes iguales o ponderadas.")
        tex.append(r"  \item \textbf{Cierre Lineal:} Las sumatorias de las proyecciones corregidas en el eje Norte ($Y$) y Este ($X$) deben ser estrictamente cero ($\Sigma \Delta N = 0, \Sigma \Delta E = 0$). El error de cierre se ajusta mediante el método de la Brújula (Regla de Bowditch).")
        tex.append(r"\end{itemize}")
    else:
        tex.append(r"Una Poligonal Abierta con Control es aquella que parte de una línea base con azimut y coordenadas conocidas, y finaliza su recorrido en otra estación (o par de estaciones) de coordenadas igualmente conocidas.")
        tex.append(r"\begin{itemize}")
        tex.append(r"  \item \textbf{Cierre Angular:} El azimut calculado del último alineamiento se compara contra el azimut teórico conocido de llegada.")
        tex.append(r"  \item \textbf{Cierre Lineal:} La sumatoria de las proyecciones debe ser igual a la diferencia real de coordenadas entre el punto de llegada y el de partida ($\Sigma \Delta N = N_{llegada} - N_{partida}$). Los desvíos se compensan proporcionalmente a las distancias.")
        tex.append(r"\end{itemize}")

    tex.append(r"\section{Trabajo de Campo: Registro de Observaciones}")
    tex.append(r"En la siguiente sección se relacionan los datos brutos levantados en campo (ángulos horizontales, verticales, distancias inclinadas y alturas instrumentales).")
    
    df_c_clean = df_campo.drop(columns=['📸 Tomar_Fotos'], errors='ignore')
    tex.append(dividir_y_generar_tablas(df_c_clean, "Cartera de Observaciones Brutas", "campo"))
    
    if fotos_paths and len(fotos_paths) > 0:
        tex.append(r"\subsection{Registro Fotográfico Panorámico}")
        tex.append(r"\begin{figure}[H]")
        tex.append(r"  \centering")
        for idx, path in enumerate(fotos_paths[:4]):
            path_latex = path.replace('\\', '/')
            tex.append(f"  \\includegraphics[height=5cm, keepaspectratio]{{{path_latex}}}")
            if idx % 2 == 1:
                tex.append(r"  \\[0.5cm]")
        tex.append(r"  \caption{Mosaico de registro fotográfico de estaciones}")
        tex.append(r"\end{figure}")
        
    tex.append(r"\section{Cálculo, Análisis de Errores y Compensación}")
    tex.append(r"El motor de cálculo topográfico procesó las observaciones, obteniendo las siguientes métricas de cierre (incluyendo planimetría y altimetría) antes de ejecutar el ajuste perimetral:")
    
    tex.append(r"\begin{table}[H]")
    tex.append(r"  \centering")
    tex.append(r"  \caption{Métricas de Cierre Geométrico}")
    tex.append(r"  \begin{tabular}{|l|l|}")
    tex.append(r"    \hline")
    tex.append(r"    \rowcolor{GeoBlue}")
    tex.append(r"    \textcolor{white}{\textbf{Parámetro Analizado}} & \textcolor{white}{\textbf{Magnitud del Error}} \\")
    tex.append(r"    \hline")
    tex.append(f"    Error Angular Bruto & {escapar_latex(str(metricas.get('err_ang_ant', 0)))} \\\\")
    tex.append(r"    \rowcolor{GeoBlue!5}")
    tex.append(f"    Error Horizontal Este ($e_x$) & {metricas.get('err_e_ant', 0):.5f} m \\\\")
    tex.append(f"    Error Horizontal Norte ($e_y$) & {metricas.get('err_n_ant', 0):.5f} m \\\\")
    tex.append(r"    \rowcolor{white}")
    tex.append(f"    Error Vertical ($\\Delta Z$) & {metricas.get('err_v_ant', 0):.5f} m \\\\")
    tex.append(f"    Precisión Vertical Relativa & 1 en {int(metricas.get('prec_v', 0))} \\\\")
    tex.append(r"    \rowcolor{GeoBlue!5}")
    tex.append(f"    Error Lineal Cierre ($e_L$) & {metricas.get('err_h_ant', 0):.5f} m \\\\")
    tex.append(f"    Precisión Planimétrica ($1:P$) & 1 en {int(metricas.get('prec_h', 0))} \\\\")
    tex.append(r"    \hline")
    tex.append(r"  \end{tabular}")
    tex.append(r"\end{table}")
    
    tex.append(r"\subsection{Cartera Final de Coordenadas Ajustadas}")
    tex.append(dividir_y_generar_tablas(df_ajuste, "Coordenadas Compensadas de la Red", "ajuste"))
    
    if path_grafico:
        path_grafico_latex = path_grafico.replace('\\', '/')
        tex.append(r"\section{Esquema Geométrico de la Red Planimétrica}")
        tex.append(r"\begin{figure}[H]")
        tex.append(r"  \centering")
        tex.append(f"  \\includegraphics[width=0.95\\textwidth]{{{path_grafico_latex}}}")
        tex.append(f"  \\caption{{Plano As-Built de la {tipo_poligonal}}}")
        tex.append(r"\end{figure}")
        
    tex.append(r"\section{Conclusiones y Dictamen Técnico}")
    prec_h = metricas.get('prec_h', 0)
    comentario_precision = evaluar_precision(prec_h)
    
    tex.append(r"\begin{itemize}")
    tex.append(f"  \\item {comentario_precision}")
    tex.append(r"  \item El procesamiento fue realizado exitosamente de forma automatizada mediante \textbf{GeoPol Web}, suprimiendo el error de cálculo humano y garantizando la trazabilidad matemática requerida por la ingeniería civil moderna.")
    tex.append(r"\end{itemize}")
    
    tex.append(r"\end{document}")
    return "\n".join(tex)


def generar_reporte_volumenes_latex(df_cubicaje, metricas, autores, tutor, path_grafico=None, path_masas=None, paths_secciones=None):
    titulo = "Memorias de Cálculo Matemático y Diseño Vial\\\\ (Cubicaje de Volúmenes)"
    tex = [generar_preambulo_y_caratula(titulo, autores, tutor)]
    
    tex.append(r"\section{Introducción y Metodología de Cubicaje}")
    tex.append(r"Este reporte detalla el cálculo de movimiento de tierras para el proyecto vial. El cálculo de volúmenes se ejecutó mediante el \textbf{Método de las Áreas Medias (Average End Area Method)}, evaluando sección transversal por sección transversal de forma secuencial.")
    
    tex.append(r"\subsection{Criterios del Diagrama de Masas (Curva Masa)}")
    tex.append(r"Para el análisis del movimiento de tierras, se ha calculado el volumen neto acumulado. La Curva Masa permite visualizar analíticamente el déficit o superávit de material a lo largo del eje del proyecto, facilitando el diseño de las zonas de préstamo y botadero.")
    
    tex.append(r"\section{Resumen Ejecutivo de Volúmenes}")
    tex.append(r"\begin{itemize}")
    tex.append(f"  \\item \\textbf{{Volumen Total de Corte (Excavación):}} {metricas.get('Corte_Total', 0):.3f} $m^3$")
    tex.append(f"  \\item \\textbf{{Volumen Total de Relleno (Terraplén):}} {metricas.get('Relleno_Total', 0):.3f} $m^3$")
    tex.append(f"  \\item \\textbf{{Balance Neto del Proyecto:}} {metricas.get('Volumen_Neto', 0):.3f} $m^3$")
    tex.append(r"\end{itemize}")
    
    tex.append(r"\section{Cuadro de Movimiento de Tierras}")
    tex.append(r"A continuación, se presenta la tabla de cálculo tabulada. Los valores negativos indican predominancia de relleno, mientras que los positivos corresponden a áreas de corte.")
    tex.append(dividir_y_generar_tablas(df_cubicaje, "Cuadro generalizado de cubicaje", "cubicaje", id_cols=1))
    
    if path_masas:
        path_masas_latex = path_masas.replace('\\', '/')
        tex.append(r"\section{Diagrama de Masas (Curva Masa)}")
        tex.append(r"Evolución gráfica del volumen acumulado en función de la abscisa (Distancia en K).")
        tex.append(r"\begin{figure}[H]")
        tex.append(r"  \centering")
        tex.append(f"  \\includegraphics[width=0.95\\textwidth]{{{path_masas_latex}}}")
        tex.append(r"  \\caption{Diagrama de Masas para compensación longitudinal de material}")
        tex.append(r"\end{figure}")
        
    tex.append(r"\section{Conclusiones y Dictamen Técnico}")
    neto = metricas.get('Volumen_Neto', 0)
    corte = metricas.get('Corte_Total', 0)
    relleno = metricas.get('Relleno_Total', 0)
    tex.append(r"\begin{itemize}")
    tex.append(f"  \\item {evaluar_volumen(neto, corte, relleno)}")
    tex.append(r"  \item El \textbf{Diagrama de Masas} demuestra los puntos críticos de corte y la distribución longitudinal del material, permitiendo a los ingenieros y planificadores viales organizar el acarreo en volquetas de manera eficiente.")
    tex.append(r"\end{itemize}")
    
    # SECCIONES TRANSVERSALES MULTIPLES EN GRID (BOTTOM-UP)
    if paths_secciones and len(paths_secciones) > 0:
        tex.append(r"\newpage")
        tex.append(r"\section{Anexo Gráfico: Perfiles de Secciones Transversales}")
        tex.append(r"A continuación, se adjuntan los perfiles de todas las abscisas calculadas. Conforme a las normativas de presentación de planos de diseño vial, las secciones se han ploteado ordenadas de forma ascendente: \textbf{de abajo hacia arriba y de izquierda a derecha}.")
        
        paths_secciones = sorted(paths_secciones, key=lambda x: x[0])
        chunks = [paths_secciones[i:i+8] for i in range(0, len(paths_secciones), 8)]
        
        for idx_chunk, chunk in enumerate(chunks):
            tex.append(r"\begin{figure}[H]")
            tex.append(r"  \centering")
            
            # Formato estándar Bottom-Up, Left-to-Right en grilla 4x2
            grid_indices = [6, 7, 4, 5, 2, 3, 0, 1]
            
            for col_i, data_idx in enumerate(grid_indices):
                if data_idx < len(chunk):
                    abs_val, p_sec = chunk[data_idx]
                    p_sec_latex = p_sec.replace('\\', '/')
                    tex.append(r"  \begin{minipage}{0.48\textwidth}")
                    tex.append(f"    \\includegraphics[width=\\linewidth]{{{p_sec_latex}}}")
                    tex.append(r"  \end{minipage}")
                else:
                    # Espacio en blanco si la hoja no está llena
                    tex.append(r"  \begin{minipage}{0.48\textwidth}")
                    tex.append(r"    \vspace{4.5cm}") 
                    tex.append(r"  \end{minipage}")
                
                if col_i % 2 == 1:
                    tex.append(r"  \\[0.3cm]")
                else:
                    tex.append(r"  \hfill")
            
            tex.append(f"  \\caption{{Anexo Secciones Transversales - Plancha {idx_chunk+1}}}")
            tex.append(r"\end{figure}")
            if idx_chunk < len(chunks) - 1:
                tex.append(r"\newpage")
            
    tex.append(r"\end{document}")
    return "\n".join(tex)


def generar_reporte_nivelacion_latex(df_calc, metricas, tipo_nivelacion, autores, tutor, path_grafico=None, fotos_paths=None):
    titulo = f"Informe Técnico de Altimetría\\\\ ({tipo_nivelacion})"
    tex = [generar_preambulo_y_caratula(titulo, autores, tutor)]
    
    tex.append(r"\section{Marco Teórico y Referencia Altimétrica}")
    tex.append(r"El presente informe detalla el cálculo, ajuste y compensación de una red de apoyo altimétrico. El proceso se fundamenta en la Nivelación Geométrica o Directa, garantizando la transferencia de cotas desde un Banco de Nivel (BM) de origen hacia los puntos de interés.")
    
    if "Cerrada" in tipo_nivelacion:
        tex.append(r"Al tratarse de una Nivelación Cerrada, el circuito inicia y termina en el mismo punto de control, lo que permite cuantificar el error de cierre evaluando la diferencia entre la cota final calculada y la cota de partida.")
    else:
        tex.append(r"Al tratarse de una Nivelación Abierta con Control, la línea inicia en un Banco de Nivel conocido y cierra sobre un Banco de Nivel distinto, permitiendo contrastar la cota calculada de llegada con la elevación teórica esperada.")
    
    tex.append(r"\section{Cartera Altimétrica Compensada}")
    tex.append(r"A continuación se relacionan las lecturas de campo (vistas atrás, intermedias y adelante) junto con las cotas instrumentales y las elevaciones ajustadas tras el prorrateo del error de cierre:")
    
    df_clean = df_calc.drop(columns=['📸 Tomar_Fotos'], errors='ignore')
    tex.append(dividir_y_generar_tablas(df_clean, "Cartera de Nivelación Procesada", "nivelacion"))
    
    if fotos_paths and len(fotos_paths) > 0:
        tex.append(r"\subsection{Registro Fotográfico de Puntos Verticales}")
        tex.append(r"\begin{figure}[H]")
        tex.append(r"  \centering")
        for idx, path in enumerate(fotos_paths[:4]):
            path_latex = path.replace('\\', '/')
            tex.append(f"  \\includegraphics[height=5cm, keepaspectratio]{{{path_latex}}}")
            if idx % 2 == 1:
                tex.append(r"  \\[0.5cm]")
        tex.append(r"  \caption{Mosaico de registro fotográfico de placas/BMs}")
        tex.append(r"\end{figure}")
        
    tex.append(r"\section{Análisis de Errores y Compensación Altimétrica}")
    tex.append(r"Las métricas de validación geométrica del circuito arrojaron los siguientes resultados:")
    tex.append(r"\begin{itemize}")
    tex.append(f"  \\item \\textbf{{Sumatoria Vista Atrás ($\\Sigma V^+$):}} {metricas.get('sum_vista_atras', 0):.3f} m")
    tex.append(f"  \\item \\textbf{{Sumatoria Vista Adelante ($\\Sigma V^-$):}} {metricas.get('sum_vista_adelante', 0):.3f} m")
    tex.append(f"  \\item \\textbf{{Cota Final Calculada (Cruda):}} {metricas.get('cota_final_cruda', 0):.3f} m")
    tex.append(f"  \\item \\textbf{{Cota Teórica Esperada:}} {metricas.get('cota_teorica_final', 0):.3f} m")
    tex.append(f"  \\item \\textbf{{Error de Cierre Altimétrico:}} {metricas.get('error_cierre_m', 0):.4f} m ({metricas.get('error_cierre_mm', 0):.1f} mm)")
    tex.append(r"\end{itemize}")
    
    if path_grafico:
        path_grafico_latex = path_grafico.replace('\\', '/')
        tex.append(r"\section{Perfil Topográfico de Nivelación}")
        tex.append(r"\begin{figure}[H]")
        tex.append(r"  \centering")
        tex.append(f"  \\includegraphics[width=0.95\\textwidth]{{{path_grafico_latex}}}")
        tex.append(r"  \caption{Perfil altimétrico de la línea de nivelación compensada}")
        tex.append(r"\end{figure}")
        
    tex.append(r"\section{Conclusiones}")
    tex.append(r"El ajuste altimétrico se ha distribuido de manera proporcional en los puntos de cambio, obteniendo un conjunto de elevaciones definitivas aptas para la densificación de cotas, control vertical y ejecución de obras civiles.")
    
    tex.append(r"\end{document}")
    return "\n".join(tex)


def compilar_latex_a_pdf(tex_code, output_dir="Reportes_PDF", filename="Reporte_Final"):
    os.makedirs(output_dir, exist_ok=True)
    
    safe_filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(filename))
    safe_filename = re.sub(r'_+', '_', safe_filename).strip('_')
    if not safe_filename:
        safe_filename = "Reporte_Topografico"
        
    tex_path = os.path.join(output_dir, f"{safe_filename}.tex")
    pdf_path = os.path.join(output_dir, f"{safe_filename}.pdf")
    
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_code)
        
    try:
        if shutil.which("pdflatex") is None:
            return None, tex_path, "Error: Windows no encuentra 'pdflatex'."
            
        tex_path_seguro = tex_path.replace('\\', '/')
        output_dir_seguro = output_dir.replace('\\', '/')
        
        comando = [
            "pdflatex", 
            "-interaction=nonstopmode", 
            "-halt-on-error", 
            f"-output-directory={output_dir_seguro}", 
            tex_path_seguro
        ]
        
        proceso = subprocess.run(comando, capture_output=True, text=True)
        
        if proceso.returncode != 0:
            log_error = proceso.stdout[-1500:] if proceso.stdout else proceso.stderr
            return None, tex_path, f"LaTeX falló al compilar el documento. Revisa el siguiente log de error:\n\n{log_error}"
            
        subprocess.run(comando, capture_output=True)
        
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            return pdf_bytes, pdf_path, "OK"
            
        return None, tex_path, "LaTeX se ejecutó, pero no devolvió ningún archivo PDF."
        
    except Exception as e:
        return None, tex_path, f"Error en Python al llamar a LaTeX: {str(e)}"