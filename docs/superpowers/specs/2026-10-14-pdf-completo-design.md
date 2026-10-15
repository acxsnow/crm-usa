# Rechazar PDF incompletos o falsos al subirlos

Fecha: 14 de octubre de 2026. Cadena A (José). Toca `app/shared/files/validation.py`
(común a todos los módulos) y una prueba de cobro de Mateo
(`tests/test_security_hardening.py`): se le avisa antes de integrar.

## Problema

En la revisión manual del 14 de octubre, «Factura reciente de electricidad»
(CASE-2026-0011) no abría: «Se ha producido un error al cargar el documento PDF».

- El archivo medía 27 bytes: `%PDF-1.4 QA documento\n%%EOF`. Lo subió el script
  `backend/scripts/qa_e2e.py`, que usa PDF de mentira. En la base local los 70
  PDF de expedientes son de ese script (60 `doc.pdf`, 10 `luz.pdf`); los 10 de
  proyectos son válidos.
- Un PDF real sube y baja idéntico byte a byte (verificado con uno generado con
  ReportLab): el almacenamiento no daña nada.
- El hueco: `check_type` solo mira que el archivo empiece con `%PDF-`. Acepta
  un PDF falso y también uno cortado a la mitad (señal que se cae en el parque
  durante la subida).

## Diseño

1. **Validación** (`shared/files/validation.py`): cuando la familia es `pdf`,
   además de la cabecera, los últimos 2 KB deben contener `startxref` y `%%EOF`.
   Todo PDF bien terminado los trae (también los de tablas de referencia
   comprimidas y los linealizados); uno cortado o falso no. Si falta, se rechaza
   con `code="pdf_incomplete"` y el mensaje «El PDF está incompleto o dañado.
   Vuelve a subirlo.». Cubre los ocho puntos de subida, que ya pasan por
   `check_type`. No se agrega una librería para leer PDF.
2. **Script de QA** (`scripts/qa_e2e.py`): sube PDF reales generados con ReportLab
   (ya es dependencia del backend), con una línea de texto que diga qué es.
3. **Base local de José**: los 70 PDF falsos de expedientes se reemplazan en el
   disco por un PDF real con el mismo nombre y se actualiza `size_bytes`. No se
   borran filas: los documentos siguen en sus expedientes con su estado de
   revisión. Solo en la máquina de José; no es una migración.

## Fuera de alcance

Abrir el PDF para validar su estructura completa, PDF cifrados con contraseña y
reparar PDF dañados.

## Pruebas

- `tests/test_file_validation.py`: un PDF real pasa; uno sin `startxref`/`%%EOF`
  (el del script de QA) y uno cortado a la mitad se rechazan con `pdf_incomplete`;
  la cabecera sola sigue reconociéndose como familia `pdf` en `sniff_mime`.
- Las pruebas que subían `%PDF-1.7 x` o `%PDF-1.4 fake` esperando éxito pasan a
  usar un PDF real (`tests/field_helpers.pdf_bytes()`).
- Navegador: el documento de CASE-2026-0011 se abre.
