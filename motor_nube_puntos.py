# ===================================================================
# MOTOR DE PROCESAMIENTO DE NUBES DE PUNTOS
# Desarrollado para Geoportal Web (GeoPol)
# Se encarga de leer, limpiar y emparejar columnas de archivos TXT/CSV
#
# CORRECCIONES APLICADAS:
#  1. Soporte de coma decimal (formato regional colombiano) y de
#     archivos sin encabezado, que antes se leían como texto y
#     terminaban convertidos a NaN sin aviso.
#  2. asignar_columnas reconoce el centinela "Ninguna" del selectbox
#     (antes se pasaba literalmente como nombre de columna).
#  3. Se informa cuántas filas se descartaron por coordenadas inválidas
#     en vez de eliminarlas en silencio.
# ===================================================================
import pandas as pd
import numpy as np

# Valor centinela que usan los selectbox de la interfaz
SIN_COLUMNA = ("Ninguna", "", None)

# Rótulos estándar para archivos que llegan sin cabecera (orden PNEZD)
NOMBRES_PNEZD = ["Punto", "Norte", "Este", "Elevación", "Descripción"]

_CABECERAS_CONOCIDAS = {
    "punto", "pto", "id", "n", "norte", "y", "este", "x", "e",
    "cota", "z", "elevacion", "elevación", "desc", "descripcion", "descripción", "code",
}


def _tiene_encabezado(primera_fila):
    """Heurística: si algún campo de la primera fila no es numérico ni un nombre conocido."""
    textos = [str(v).strip().lower() for v in primera_fila]
    if any(t in _CABECERAS_CONOCIDAS for t in textos):
        return True
    no_numericos = 0
    for t in textos:
        try:
            float(t.replace(",", "."))
        except (ValueError, AttributeError):
            no_numericos += 1
    # La descripción suele ser texto; se exige más de una columna no numérica
    return no_numericos > 1


_PATRON_COMA_DECIMAL = r"^\s*[-+]?\d+,\d+\s*$"


def _hay_coma_decimal(df):
    """True si alguna columna de texto contiene números con coma decimal."""
    for col in df.columns:
        serie = df[col]
        if serie.dtype.kind in "biufc":
            continue
        muestra = serie.dropna().astype(str).head(20)
        if muestra.empty:
            continue
        if muestra.str.match(_PATRON_COMA_DECIMAL).mean() > 0.5:
            return True
    return False


def procesar_archivo_nube(archivo):
    """
    Lee un archivo TXT o CSV y devuelve un DataFrame limpio.
    Autodetecta el separador (coma, tabulador, punto y coma o espacios),
    la presencia de encabezado y el separador decimal.
    """
    intentos = [
        {"decimal": "."},
        {"decimal": ","},
    ]

    ultimo_error = None
    for opciones in intentos:
        try:
            if hasattr(archivo, "seek"):
                archivo.seek(0)

            sonda = pd.read_csv(
                archivo, sep=None, engine="python", header=None, nrows=1,
                skip_blank_lines=True, **opciones
            )
            usar_header = 0 if _tiene_encabezado(sonda.iloc[0].tolist()) else None

            if hasattr(archivo, "seek"):
                archivo.seek(0)

            df = pd.read_csv(
                archivo, sep=None, engine="python", header=usar_header,
                skip_blank_lines=True, skipinitialspace=True, **opciones
            )

            if usar_header is None:
                # Archivo sin cabecera: se rotulan las columnas con la
                # nomenclatura topográfica estándar PNEZD para que la tabla de
                # identificación sea legible y la autodetección las reconozca.
                df.columns = [
                    NOMBRES_PNEZD[i] if i < len(NOMBRES_PNEZD) else f"Columna_{i + 1}"
                    for i in range(len(df.columns))
                ]
            else:
                df.columns = [str(c).strip() for c in df.columns]

            df = df.dropna(how="all")

            # Si alguna columna de texto contiene números escritos con coma
            # decimal (1234,567), se reintenta la lectura con decimal=","
            if opciones["decimal"] == "." and _hay_coma_decimal(df):
                ultimo_error = "Se detectaron valores con coma decimal."
                continue

            return df.reset_index(drop=True)

        except Exception as e:
            ultimo_error = e

    raise ValueError(f"No se pudo leer el archivo. Verifique el formato. Detalle: {ultimo_error}")


def asignar_columnas(df, col_punto, col_este, col_norte, col_z, col_desc, retornar_descartes=False):
    """
    Recibe el DataFrame bruto y los nombres de las columnas seleccionadas
    por el usuario, devolviendo un DataFrame estandarizado para Folium.
    """
    def _valida(col):
        return col if (col not in SIN_COLUMNA and col in df.columns) else None

    col_punto = _valida(col_punto)
    col_este = _valida(col_este)
    col_norte = _valida(col_norte)
    col_z = _valida(col_z)
    col_desc = _valida(col_desc)

    if col_este is None or col_norte is None:
        raise ValueError("Debe asignar las columnas de Este (X) y Norte (Y) antes de continuar.")

    df_clean = pd.DataFrame(index=df.index)

    # Si el usuario no selecciona columna de punto, autogeneramos un ID
    df_clean["Punto"] = df[col_punto] if col_punto else np.arange(1, len(df) + 1)

    # Coordenadas obligatorias
    df_clean["Este"] = pd.to_numeric(df[col_este], errors="coerce")
    df_clean["Norte"] = pd.to_numeric(df[col_norte], errors="coerce")

    # Cota opcional (si no hay, asumimos 0)
    df_clean["Cota"] = pd.to_numeric(df[col_z], errors="coerce") if col_z else 0.0

    # Descripción opcional
    df_clean["Descripcion"] = df[col_desc] if col_desc else "Punto Topográfico"

    # Limpieza de seguridad: Eliminar filas donde Este o Norte estén vacíos
    filas_previas = len(df_clean)
    df_clean = df_clean.dropna(subset=["Este", "Norte"]).reset_index(drop=True)
    descartadas = filas_previas - len(df_clean)

    if retornar_descartes:
        return df_clean, descartadas
    return df_clean
