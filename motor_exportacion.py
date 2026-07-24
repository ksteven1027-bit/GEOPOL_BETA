# ===================================================================
# MOTOR DE EXPORTACIÓN MULTIFORMATO (GIS / CAD / GOOGLE EARTH)
# Desarrollado para Geoportal Web
# Convierte carteras ajustadas a formatos estándar: KML, DXF y SHP
# ===================================================================
import io
import zipfile
import math
import ezdxf
import shapefile
import pyproj
import numpy as np

# Diccionario para mapear los nombres de tu interfaz con sus códigos CRS oficiales
CRS_MAPPING = {
    "CTM12 (Origen Nacional)": "EPSG:9377",
    "MAGNA_Central": "EPSG:3116",
    "MAGNA_Oeste": "EPSG:3115",
    "MAGNA_Este": "EPSG:3117",
    "Local_Bogota_2011": "ESRI:102771",
    "Local_Medellin_2010": "ESRI:102768",
    "UTM_18N": "EPSG:32618",
    "UTM_19N": "EPSG:32619"
}

def generar_kml(df_ajuste, trans_to_wgs):
    """
    Genera un archivo KML estándar para Google Earth.
    Transforma las coordenadas planas a geográficas WGS84/MAGNA sobre la marcha.
    """
    kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Levantamiento Topográfico - GeoPol Web</name>
    <Style id="lineaTopografica">
      <LineStyle><color>ff00aaff</color><width>3</width></LineStyle>
      <PolyStyle><fill>0</fill></PolyStyle>
    </Style>
    <Placemark>
      <name>Lindero Ajustado</name>
      <styleUrl>#lineaTopografica</styleUrl>
      <LineString>
        <coordinates>
"""
    # 1. Escribir la línea del polígono
    for idx, row in df_ajuste.iterrows():
        lon, lat = trans_to_wgs.transform(float(row['X_Estacion']), float(row['Y_Estacion']))
        kml += f"          {lon:.9f},{lat:.9f},0\n"
        
    kml += """        </coordinates>
      </LineString>
    </Placemark>
"""
    # 2. Escribir los pines de los vértices individuales
    for idx, row in df_ajuste.iterrows():
        # Evitamos duplicar el marcador del punto de cierre si es una poligonal cerrada
        if idx == len(df_ajuste)-1 and df_ajuste.iloc[0]['Estacionado'] == row['Estacionado']:
            continue
        lon, lat = trans_to_wgs.transform(float(row['X_Estacion']), float(row['Y_Estacion']))
        z = float(row.get('Z_Estacion', 0.0))
        kml += f"""    <Placemark>
      <name>{row['Estacionado']}</name>
      <description>Coordenadas Planas Localizadas: X={row['X_Estacion']:.3f}, Y={row['Y_Estacion']:.3f}, Z={z:.3f}</description>
      <Point><coordinates>{lon:.9f},{lat:.9f},{z:.3f}</coordinates></Point>
    </Placemark>
"""
    kml += """  </Document>
</kml>"""
    return kml.encode('utf-8')


def generar_dxf(df_ajuste):
    """
    Genera un archivo DXF binario compatible con AutoCAD Civil 3D.
    Trazado en 3D real usando las coordenadas calculadas del Geoportal.
    """
    doc = ezdxf.new('R2000')
    msp = doc.modelspace()
    
    # Extraer lista de tuplas de coordenadas (X, Y, Z)
    puntos_3d = [(float(row['X_Estacion']), float(row['Y_Estacion']), float(row.get('Z_Estacion', 0.0))) 
                 for _, row in df_ajuste.iterrows()]
    
    # Añadir la polilínea 3D de ingeniería
    msp.add_polyline3d(puntos_3d, dxfattribs={'color': 5}) # Azul CAD estándar
    
    # Añadir los nodos POINT y textos de nomenclatura
    for idx, row in df_ajuste.iterrows():
        if idx == len(df_ajuste)-1 and df_ajuste.iloc[0]['Estacionado'] == row['Estacionado']:
            continue
        x, y, z = float(row['X_Estacion']), float(row['Y_Estacion']), float(row.get('Z_Estacion', 0.0))
        
        msp.add_point((x, y, z), dxfattribs={'color': 1}) # Punto Rojo
        msp.add_text(str(row['Estacionado']), dxfattribs={
            'insert': (x + 1.2, y + 1.2, z), # Offset de texto tipo CAD
            'height': 0.75,
            'color': 7 # Blanco/Negro según el fondo de AutoCAD
        })
        
    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode('utf-8')


def generar_shp_zip(df_ajuste, nombre_proyeccion):
    """
    Genera un archivo comprimido .ZIP que contiene las capas ESRI Shapefile
    de Puntos y Líneas, incluyendo el archivo de proyección geográfica .prj
    """
    epsg_code = CRS_MAPPING.get(nombre_proyeccion, "EPSG:9377")
    
    # Inicializar buffers en memoria para el Shapefile de Puntos
    shp_pt = io.BytesIO()
    shx_pt = io.BytesIO()
    dbf_pt = io.BytesIO()
    
    with shapefile.Writer(shp=shp_pt, shx=shx_pt, dbf=dbf_pt, shapeType=shapefile.POINT) as w:
        w.field('Estacion', 'C', 40)
        w.field('Coorde_X', 'N', 18, 4)
        w.field('Coorde_Y', 'N', 18, 4)
        w.field('Cota_Z', 'N', 18, 4)
        
        for idx, row in df_ajuste.iterrows():
            if idx == len(df_ajuste)-1 and df_ajuste.iloc[0]['Estacionado'] == row['Estacionado']:
                continue
            x, y = float(row['X_Estacion']), float(row['Y_Estacion'])
            z = float(row.get('Z_Estacion', 0.0))
            w.point(x, y)
            w.record(str(row['Estacionado']), x, y, z)
            
    # Inicializar buffers para el Shapefile de Línea (Lindero)
    shp_ln = io.BytesIO()
    shx_ln = io.BytesIO()
    dbf_ln = io.BytesIO()
    
    with shapefile.Writer(shp=shp_ln, shx=shx_ln, dbf=dbf_ln, shapeType=shapefile.POLYLINE) as w:
        w.field('Proyecto', 'C', 50)
        vertices_2d = [[float(row['X_Estacion']), float(row['Y_Estacion'])] for _, row in df_ajuste.iterrows()]
        w.line([vertices_2d])
        w.record('Poligonal_Topografica_Ajustada')
        
    # Obtener la definición WKT oficial del sistema de coordenadas usando PyProj
    try:
        prj_wkt = pyproj.CRS(epsg_code).to_wkt()
    except:
        prj_wkt = ""

    # Empaquetar todo en un único archivo ZIP para descarga directa
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Capa de Vértices (Puntos)
        zip_file.writestr("vertices_poligonal.shp", shp_pt.getvalue())
        zip_file.writestr("vertices_poligonal.shx", shx_pt.getvalue())
        zip_file.writestr("vertices_poligonal.dbf", dbf_pt.getvalue())
        if prj_wkt: zip_file.writestr("vertices_poligonal.prj", prj_wkt)
            
        # Capa de Lindero (Línea)
        zip_file.writestr("lindero_poligonal.shp", shp_ln.getvalue())
        zip_file.writestr("lindero_poligonal.shx", shx_ln.getvalue())
        zip_file.writestr("lindero_poligonal.dbf", dbf_ln.getvalue())
        if prj_wkt: zip_file.writestr("lindero_poligonal.prj", prj_wkt)
        
    return zip_buffer.getvalue()