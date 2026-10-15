# Rechazar PDF incompletos o falsos — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Que ningún punto de subida acepte un PDF cortado o falso, que el QA deje PDF que se abren y que la base local de José no tenga PDF dañados.

**Spec:** `docs/superpowers/specs/2026-10-14-pdf-completo-design.md`

## Global Constraints

- Un solo cambio de regla, en `shared/files/validation.py::check_type`; ningún módulo duplica la validación.
- Sin dependencias nuevas.
- La prueba de cobro de Mateo solo cambia el contenido del PDF de ejemplo; se le avisa.
- Sin commits hasta que José lo pida.

## Review Focus

- Un PDF real con espacios o saltos después de `%%EOF` pasa.
- Un PDF cortado a la mitad se rechaza aunque empiece bien.
- Las demás familias (fotos, videos) no cambian.

---

### Task 1: Validación

- [x] `tests/field_helpers.py`: `pdf_bytes()` genera un PDF real con ReportLab.
- [x] Pruebas que fallan en `tests/test_file_validation.py`: real pasa; falso del QA y cortado → `pdf_incomplete`; real con espacios al final pasa.
- [x] Implementar en `check_type`; ver pasar.
- [x] Cambiar a `pdf_bytes()` las pruebas que esperaban éxito con PDF falso (`test_case_documents.py`, `test_security_hardening.py`); correr esas y las de subida.

### Task 2: Script de QA

- [x] `scripts/qa_e2e.py`: los tres PDF de ejemplo generados con ReportLab.
- [x] Comprobar que el script compila e importa.

### Task 3: Base local

- [x] Reemplazar en el disco los 70 PDF falsos de expedientes por uno real y actualizar `size_bytes`.
- [x] El documento de CASE-2026-0011 se descarga por la API como PDF completo (1.509 bytes).
- [ ] Abrirlo en Chrome (lo hace José: el navegador sin pantalla de las pruebas no muestra el visor de PDF).

### Task 4: Verificación

- [x] Batería completa de pytest (533 en verde).
- [x] Informar a José; comiteado el 15 oct a pedido suyo.
