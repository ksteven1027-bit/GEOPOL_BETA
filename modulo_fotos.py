# ===================================================================
# MÓDULO DE ESTAMPADO DE FOTOGRAFÍAS - GeoPol Web
# Superpone un banner con los datos del registro fotográfico sobre la
# imagen capturada, para que la fotografía sirva como evidencia
# trazable dentro del informe técnico.
# -------------------------------------------------------------------
# Correcciones frente a la versión anterior:
#   * No declaraba NINGÚN import pese a usar Image, ImageDraw y
#     datetime: cualquier llamada moría con NameError.
#   * Usaba emojis en draw.text(). Las fuentes de PIL no tienen esos
#     glifos y se dibujaban como rectángulos vacíos.
#   * Banner de 70 px fijos y letra por defecto de PIL (~11 px). En una
#     foto de teléfono de 4000 px de ancho el texto era ilegible.
#     Ahora todo escala con la imagen.
#   * No rotaba según la orientación EXIF: las fotos tomadas en
#     vertical con el móvil salían acostadas y el banner quedaba en un
#     lateral.
# ===================================================================
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageOps

# Fuentes escalables habituales en Linux (Streamlit Cloud las trae).
# Si no hay ninguna se recurre a la bitmap de PIL.
_RUTAS_FUENTE = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

_ORIENTACIONES = {
    1: "Placa / Punto", 2: "Vista al Norte", 3: "Vista al Este",
    4: "Vista al Sur", 5: "Vista al Oeste",
}


def _cargar_fuente(tamano):
    """Fuente escalable si existe; si no, la bitmap de PIL."""
    for ruta in _RUTAS_FUENTE:
        try:
            return ImageFont.truetype(ruta, tamano)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size=tamano)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def _etiqueta_orientacion(paso):
    """
    Acepta el número de paso (1-5) o el sufijo de la secuencia de la
    app ('Norte', 'Este', 'Placa-Punto'...).
    """
    if isinstance(paso, str):
        limpio = paso.replace("-", " ").replace("_", " ").strip()
        for etiqueta in _ORIENTACIONES.values():
            if limpio.lower() in etiqueta.lower():
                return etiqueta
        return limpio or "Sin especificar"
    try:
        return _ORIENTACIONES.get(int(paso), "Sin especificar")
    except (TypeError, ValueError):
        return "Sin especificar"


def estampar_datos_en_foto(imagen_camara, nombre_delta, paso_actual,
                           latitud=None, longitud=None, proyecto=None,
                           ancho_maximo=1600):
    """
    Devuelve un PIL.Image en RGB con el banner ya estampado.

    imagen_camara    : ruta, archivo o buffer (lo de st.camera_input)
    nombre_delta     : estación o delta al que pertenece la fotografía
    paso_actual      : número de paso (1-5) o sufijo ('Norte', 'Este'...)
    latitud/longitud : opcionales. Si no se pasan, la línea de
                       coordenadas no se dibuja. Es preferible omitirla
                       a estampar una posición que no corresponde a
                       donde se tomó la foto.
    ancho_maximo     : las fotos de móvil pesan varios MB; reducirlas
                       evita que el PDF final sea inmanejable.
    """
    img = Image.open(imagen_camara)
    img = ImageOps.exif_transpose(img)          # respeta la orientación real
    img = img.convert("RGBA")

    if ancho_maximo and img.width > ancho_maximo:
        alto_nuevo = int(img.height * ancho_maximo / img.width)
        img = img.resize((ancho_maximo, alto_nuevo), Image.LANCZOS)

    ancho, alto = img.size

    # Todo proporcional a la imagen, no en píxeles fijos
    tam_texto = max(12, int(ancho * 0.022))
    margen = max(8, int(ancho * 0.015))
    interlinea = int(tam_texto * 0.45)
    fuente = _cargar_fuente(tam_texto)
    fuente_peq = _cargar_fuente(max(10, int(tam_texto * 0.85)))

    lineas = [(f"Estación: {nombre_delta}    |    "
               f"Orientación: {_etiqueta_orientacion(paso_actual)}", fuente, "white")]

    segunda = datetime.now().strftime("Fecha: %Y-%m-%d %H:%M:%S")
    if latitud is not None and longitud is not None:
        segunda += (f"    |    Lat: {float(latitud):.6f}"
                    f"   Lon: {float(longitud):.6f}")
    lineas.append((segunda, fuente_peq, "#FFCC00"))

    if proyecto:
        lineas.append((f"Proyecto: {proyecto}", fuente_peq, "#E0E0E0"))

    alto_banner = (margen * 2 + len(lineas) * tam_texto
                   + (len(lineas) - 1) * interlinea)

    # Banner semitransparente sobre una capa aparte
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(capa).rectangle(
        [(0, alto - alto_banner), (ancho, alto)], fill=(0, 0, 0, 165))
    img = Image.alpha_composite(img, capa)

    # Texto
    dibujo = ImageDraw.Draw(img)
    y = alto - alto_banner + margen
    for texto, fnt, color in lineas:
        dibujo.text((margen, y), texto, font=fnt, fill=color)
        y += tam_texto + interlinea

    return img.convert("RGB")


def guardar_foto_estampada(imagen_camara, ruta_destino, nombre_delta, paso_actual,
                           latitud=None, longitud=None, proyecto=None, calidad=85):
    """
    Estampa y guarda en disco. Si algo falla (fuente ausente, formato
    raro, EXIF corrupto), guarda la foto original sin estampar: perder
    el estampado es un inconveniente, perder la foto de campo no.

    Devuelve True si se estampó, False si se guardó sin estampar.
    """
    try:
        img = estampar_datos_en_foto(imagen_camara, nombre_delta, paso_actual,
                                     latitud, longitud, proyecto)
        img.save(ruta_destino, "JPEG", quality=calidad, optimize=True)
        return True
    except Exception:
        try:
            imagen_camara.seek(0)
        except Exception:
            pass
        datos = (imagen_camara.getbuffer() if hasattr(imagen_camara, "getbuffer")
                 else imagen_camara.read())
        with open(ruta_destino, "wb") as f:
            f.write(datos)
        return False
