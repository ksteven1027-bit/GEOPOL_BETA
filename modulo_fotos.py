def estampar_datos_en_foto(imagen_camara, nombre_delta, paso_actual, latitud, longitud):
    # 1. Abrir la imagen y convertirla a RGBA para soportar transparencias (Canal Alpha)
    img = Image.open(imagen_camara).convert("RGBA")
    
    # 2. Crear una capa vacía para dibujar el banner oscuro
    capa_overlay = Image.new('RGBA', img.size, (0,0,0,0))
    draw_overlay = ImageDraw.Draw(capa_overlay)
    
    # Extraer el tamaño de la foto
    ancho, alto = img.size
    alto_banner = 70 # Tamaño del cuadro oscuro en la parte inferior
    
    # Dibujar un rectángulo negro semitransparente (Opacidad de 150/255) al fondo
    draw_overlay.rectangle(
        [(0, alto - alto_banner), (ancho, alto)],
        fill=(0, 0, 0, 150) 
    )
    
    # Fusionar la foto original con el banner semitransparente
    img = Image.alpha_composite(img, capa_overlay)
    draw = ImageDraw.Draw(img)

    # 3. Definir el Azimut
    azimut_str = "N/A"
    if paso_actual == 2: azimut_str = "0° (Norte)"
    elif paso_actual == 3: azimut_str = "90° (Este)"
    elif paso_actual == 4: azimut_str = "180° (Sur)"
    elif paso_actual == 5: azimut_str = "270° (Oeste)"
    elif paso_actual == 1: azimut_str = "Punto / Placa"

    # 4. Obtener Fecha y Hora en tiempo real
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 5. Preparar los textos modernos con íconos
    texto_linea1 = f"📍 Delta: {nombre_delta}   |   🧭 Azimut: {azimut_str}"
    texto_linea2 = f"🌐 Lat: {latitud}   |   Lon: {longitud}   |   📅 {fecha_actual}"
    
    # 6. Posicionar los textos dentro del banner
    pos_y1 = alto - alto_banner + 15
    pos_y2 = alto - alto_banner + 35
    
    # Estampar con color blanco brillante y el detalle inferior en amarillo topográfico
    draw.text((20, pos_y1), texto_linea1, fill="white")
    draw.text((20, pos_y2), texto_linea2, fill="#FFCC00") # Amarillo institucional

    # 7. Convertir de nuevo a RGB para que se pueda guardar como .JPG sin problemas
    return img.convert("RGB")