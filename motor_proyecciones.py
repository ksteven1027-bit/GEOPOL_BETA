# ===================================================================
# MOTOR DE PROYECCIONES Y TRANSFORMACIÓN DE COORDENADAS
# Desarrollado para Geoportal Web (Arquitectura Orientada a Objetos)
# Autor Original: Kevin Cubillos / Sergio Barbosa
# ===================================================================
import pyproj

class MotorCoordenadasIGAC_V2:
    def __init__(self):
        """
        Inicializa transformadores para sistemas nacionales, orígenes Gauss-Krüger, 
        sistemas locales de ciudad y grillas UTM.
        """
        # Sistema Geodésico base: MAGNA-SIRGAS (Longitud, Latitud)
        # Esto anula la deriva tectónica imitando al software del IGAC
        self.crs_geodesico = pyproj.CRS("EPSG:4686")
        
        # 1. Sistemas Nacionales y Tradicionales Gauss-Krüger
        self.crs_ctm12 = pyproj.CRS("EPSG:9377")          # Origen Nacional (Res 471 de 2020)
        self.crs_central = pyproj.CRS("EPSG:3116")        # Origen Central
        self.crs_oeste = pyproj.CRS("EPSG:3115")          # Origen Oeste
        self.crs_este = pyproj.CRS("EPSG:3117")           # Origen Este
        
        # 2. Sistemas Locales (Ciudades)
        self.crs_bogota_2011 = pyproj.CRS("ESRI:102771")  # Local Bogotá 2011
        self.crs_medellin_2010 = pyproj.CRS("ESRI:102768")# Local Medellín 2010
        
        # 3. Sistemas UTM (Universal Transversal de Mercator)
        self.crs_utm_18n = pyproj.CRS("EPSG:32618")
        self.crs_utm_19n = pyproj.CRS("EPSG:32619")

        # --- TRANSFORMADORES DIRECTOS (GPS -> Plano) ---
        self.transformadores = {
            "Local_Bogota_2011": pyproj.Transformer.from_crs(self.crs_geodesico, self.crs_bogota_2011, always_xy=True),
            "CTM12 (Origen Nacional)": pyproj.Transformer.from_crs(self.crs_geodesico, self.crs_ctm12, always_xy=True),
            "MAGNA_Central": pyproj.Transformer.from_crs(self.crs_geodesico, self.crs_central, always_xy=True),
            "MAGNA_Oeste": pyproj.Transformer.from_crs(self.crs_geodesico, self.crs_oeste, always_xy=True),
            "MAGNA_Este": pyproj.Transformer.from_crs(self.crs_geodesico, self.crs_este, always_xy=True),
            "Local_Medellin_2010": pyproj.Transformer.from_crs(self.crs_geodesico, self.crs_medellin_2010, always_xy=True),
            "UTM_18N": pyproj.Transformer.from_crs(self.crs_geodesico, self.crs_utm_18n, always_xy=True),
            "UTM_19N": pyproj.Transformer.from_crs(self.crs_geodesico, self.crs_utm_19n, always_xy=True)
        }
        
        # --- TRANSFORMADORES INVERSOS (Plano -> GPS) ---
        # (Añadido exclusivamente para que el mapa de Folium pueda retroceder el cálculo y dibujar los pines)
        self.transformadores_inversos = {
            "Local_Bogota_2011": pyproj.Transformer.from_crs(self.crs_bogota_2011, self.crs_geodesico, always_xy=True),
            "CTM12 (Origen Nacional)": pyproj.Transformer.from_crs(self.crs_ctm12, self.crs_geodesico, always_xy=True),
            "MAGNA_Central": pyproj.Transformer.from_crs(self.crs_central, self.crs_geodesico, always_xy=True),
            "MAGNA_Oeste": pyproj.Transformer.from_crs(self.crs_oeste, self.crs_geodesico, always_xy=True),
            "MAGNA_Este": pyproj.Transformer.from_crs(self.crs_este, self.crs_geodesico, always_xy=True),
            "Local_Medellin_2010": pyproj.Transformer.from_crs(self.crs_medellin_2010, self.crs_geodesico, always_xy=True),
            "UTM_18N": pyproj.Transformer.from_crs(self.crs_utm_18n, self.crs_geodesico, always_xy=True),
            "UTM_19N": pyproj.Transformer.from_crs(self.crs_utm_19n, self.crs_geodesico, always_xy=True)
        }

    def convertir_coordenada(self, latitud, longitud):
        """
        Calcula las proyecciones para todos los sistemas configurados a partir
        de una coordenada geodésica MAGNA-SIRGAS. (Tu método original mantenido)
        """
        resultados = {
            "Geodesica_Base": {
                "Latitud": latitud,
                "Longitud": longitud
            }
        }
        
        for nombre, transformador in self.transformadores.items():
            este, norte = transformador.transform(longitud, latitud)
            resultados[nombre] = {
                "Este": round(este, 3),
                "Norte": round(norte, 3)
            }
            
        return resultados