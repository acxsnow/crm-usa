# Fuente del manual de usuario

`docs/Manual_Usuario_CRM_Delta_HVAC.docx` es el único manual de usuario. Se genera desde esta carpeta, así que cuando cambie cómo funciona una pantalla se actualiza aquí y se vuelve a generar. No se edita el Word a mano.

| Archivo | Qué es |
|---|---|
| `manual.js` | El texto del manual y dónde va cada captura (`...fig("clave")`). |
| `pantallas.py` | Cada pantalla: con qué rol se abre, qué se señala y la leyenda de cada número. |
| `capturas.py` | El dibujo de recuadros, números y flechas, y el inicio de sesión. |
| `demo.json` | Los expedientes de demostración que usan las capturas. |
| `img/` | Las capturas anotadas y `capturas.json` con sus leyendas. |

## Regenerar

Con la app arriba (`docker compose up`), desde la raíz del repositorio:

1. **Datos de demostración**, solo si la base no los tiene: seis expedientes con nombres creíbles, cada uno en la etapa que se captura. El script usa el atajo `docker` de `qa_e2e` dentro del contenedor.

   ```
   docker compose exec -T api python -m scripts.manual_demo > docs/manual/demo.json
   ```

   Si el archivo trae líneas antes del `{`, se borran: el JSON empieza en la primera llave.

2. **Capturas**: todas, o solo las claves que se pasen.

   ```
   docker run --rm --network crm-usa_default -v "<repo>/docs/manual:/m" -w /m \
     mcr.microsoft.com/playwright/python:v1.47.0-jammy \
     sh -c "pip install -q playwright==1.47.0 redis && python pantallas.py [clave ...]"
   ```

   Revise cada imagen: si un número tapa algo, cambie el lado (`left`, `right`, `top`, `bottom` o `inside`) en `pantallas.py`. Las capturas del técnico agregan y guardan equipos del expediente de demostración de Roberto Sánchez; se pueden repetir.

3. **Word**, con el manual cerrado en Word:

   ```
   docker run --rm -v "<repo>/docs:/d" -w /d/manual node:20-slim sh -c "npm install && node manual.js"
   ```
