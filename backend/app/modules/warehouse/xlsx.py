"""Lee un .xlsx sin dependencias: es un zip con XML adentro.

El cliente manda el catálogo en Excel (hoja «Catálogo»), así que hay que abrir
.xlsx en el servidor. `openpyxl` haría el trabajo, pero son ~40 líneas de
lectura de las partes que se usan —hoja, fila, celda y la tabla de cadenas
compartidas— contra una dependencia más que arrastrar al contenedor. De paso
funciona sin red en las pruebas.

Solo entiende lo que un Excel de encuesta tiene: texto (compartido o en línea),
números, booleanos y fechas como número de serie. No escribe, no evalúa
fórmulas (devuelve el último resultado guardado) y no lee ni macros ni
formatos.
"""
import re
import zipfile
from datetime import date, timedelta
from io import BytesIO
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# El inicio del calendario de Excel. Las fechas de la encuesta son del 2026.
_EPOCH = date(1899, 12, 30)


class NotAnXlsxError(ValueError):
    """El archivo no es un .xlsx legible (o está corrupto)."""


def _column_index(ref: str) -> int:
    letras = re.match(r"([A-Za-z]+)", ref or "")
    if not letras:
        return 0
    indice = 0
    for letra in letras.group(1).upper():
        indice = indice * 26 + (ord(letra) - 64)
    return indice - 1


def _text(node) -> str:
    return "".join(part.text or "" for part in node.iter(f"{NS}t"))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        raiz = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [_text(si) for si in raiz.findall(f"{NS}si")]


def _sheet_paths(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Nombre de la hoja y ruta dentro del zip, en el orden del libro."""
    libro = ET.fromstring(z.read("xl/workbook.xml"))
    destinos = {}
    try:
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for rel in rels:
            destino = rel.get("Target", "")
            destinos[rel.get("Id")] = destino.lstrip("/").removeprefix("xl/")
    except KeyError:
        pass
    hojas = []
    for hoja in libro.iter(f"{NS}sheet"):
        destino = destinos.get(hoja.get(f"{NS_REL}id"))
        if destino:
            hojas.append((hoja.get("name") or "", f"xl/{destino}"))
    return hojas


def _cell_value(celda, compartidas: list[str]):
    tipo = celda.get("t")
    if tipo == "inlineStr":
        return _text(celda)
    valor = celda.find(f"{NS}v")
    if valor is None or valor.text is None:
        return None
    if tipo == "s":
        indice = int(valor.text)
        return compartidas[indice] if 0 <= indice < len(compartidas) else None
    if tipo == "b":
        return valor.text not in ("0", "false", "False")
    if tipo == "str":
        return valor.text
    texto = valor.text.strip()
    if not texto:
        return None
    try:
        numero = float(texto)
    except ValueError:
        return valor.text
    return int(numero) if numero.is_integer() else numero


def _read_sheet(z: zipfile.ZipFile, path: str, compartidas: list[str]) -> list[list]:
    raiz = ET.fromstring(z.read(path))
    filas: list[list] = []
    for fila in raiz.iter(f"{NS}row"):
        celdas: list = []
        for celda in fila.findall(f"{NS}c"):
            indice = _column_index(celda.get("r", ""))
            while len(celdas) <= indice:
                celdas.append(None)
            celdas[indice] = _cell_value(celda, compartidas)
        filas.append(celdas)
    return filas


# Un .xlsx es un zip: sin estos topes, un archivo de 5 MB podría descomprimir
# gigas en memoria (bomba zip). Un catálogo real queda muy por debajo.
MAX_UNCOMPRESSED_MEMBER = 50 * 1024 * 1024
MAX_UNCOMPRESSED_TOTAL = 150 * 1024 * 1024


def read_sheets(data: bytes) -> dict[str, list[list]]:
    """Todas las hojas del libro: `{nombre: [[celda, …], …]}`."""
    try:
        z = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise NotAnXlsxError("El archivo no es un Excel (.xlsx) válido.") from exc
    tamanos = [info.file_size for info in z.infolist()]
    if any(t > MAX_UNCOMPRESSED_MEMBER for t in tamanos) or sum(tamanos) > MAX_UNCOMPRESSED_TOTAL:
        raise NotAnXlsxError("El Excel es demasiado grande para importarlo.")
    try:
        compartidas = _shared_strings(z)
        return {nombre: _read_sheet(z, path, compartidas) for nombre, path in _sheet_paths(z)}
    except (KeyError, ET.ParseError) as exc:
        raise NotAnXlsxError("No se pudo leer el contenido del Excel.") from exc


def to_date(valor) -> date | None:
    """Una fecha de Excel viene como número de días desde 1900."""
    if valor is None or isinstance(valor, date):
        return valor if isinstance(valor, date) else None
    try:
        return _EPOCH + timedelta(days=int(float(valor)))
    except (TypeError, ValueError):
        return None
