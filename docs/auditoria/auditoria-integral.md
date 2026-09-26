# Estándar de auditoría integral y plan de salida a producción

Creado por José Javier y Mateo Mazo · Versión 1.0 · Septiembre de 2026

Este estándar genera y mantiene un artefacto con el estado real de un proyecto y cuatro auditorías: código y deuda técnica, seguridad, pruebas unitarias y QA. Sirve para cualquier proyecto del área.

## Cómo usarlo en un proyecto

1. Copia este archivo en `docs/auditoria/auditoria-integral.md` del proyecto y súbelo al repositorio.
2. Abre Claude Code en la raíz del proyecto, con la sesión iniciada con tu cuenta (`/login`) en un plan Pro, Max, Team o Enterprise.
3. Escribe: `Ejecuta el estándar docs/auditoria/auditoria-integral.md`
4. Puedes darle el contexto en el mismo mensaje. Si falta algo, Claude te envía un cuestionario con lo que encontró, lo que dedujo del código y lo que necesita que le digas, y espera tu respuesta antes de auditar. Al terminar, publica el artefacto, te da el enlace y deja configurado `CLAUDE.md` para que las siguientes sesiones lo mantengan al día.
5. Comparte el enlace desde el botón Share del artefacto. Quien lo abra necesita cuenta de Claude.

Para repetir las auditorías completas (por ejemplo, antes de cada salida a producción), escribe: `Ejecuta de nuevo las auditorías del estándar y actualiza el artefacto`.

---

# Instrucciones para Claude

## 0. Modo de trabajo

- Esto es una auditoría: lee y analiza. No modifiques el código de la aplicación. Solo puedes crear o editar el artefacto y `CLAUDE.md`.
- Puedes ejecutar comandos que no cambian el proyecto: pruebas, cobertura, linters y auditoría de dependencias. Pide permiso antes de instalar paquetes, cambiar configuración o ejecutar algo que toque bases de datos o servicios externos.
- Si una herramienta no existe, no está instalada o falla, dilo y marca ese punto "Por verificar". No lo ocultes ni lo supongas.
- Todo hallazgo debe estar respaldado por el código o por la salida de un comando. No inventes.
- No copies en el artefacto secretos, contraseñas, tokens ni datos personales reales que encuentres. Indica dónde están sin mostrar su valor.
- En las vulnerabilidades, describe el riesgo y cómo corregirlo. No escribas instrucciones ni código para explotarlas.

## 1. Contexto

Antes de auditar, reúne el contexto en este orden: el mensaje con el que se ejecutó el estándar, `CLAUDE.md` del proyecto, lo conversado en esta sesión y el código.

Necesitas estos datos:

1. Nombre del proyecto.
2. Qué hace el producto y para qué cliente.
3. Roles de usuario.
4. Flujo principal del negocio.
5. Etapa actual (desarrollo, QA o producción) y fecha de salida si existe.
6. Requisitos principales del cliente.
7. Verificaciones específicas: lo propio de este proyecto que la auditoría no puede pasar por alto.
8. Normas o regulaciones aplicables (por ejemplo, protección de datos personales del país del cliente).
9. Dueño del artefacto: la persona cuya cuenta ejecuta esta sesión.

Si falta alguno, antes de empezar envíame un solo mensaje con el cuestionario completo:

- Los datos que ya encontraste, con lo que dice cada uno y de dónde salió, para que los confirme o corrija.
- Los que puedes deducir del código (como roles, flujo principal o módulos), con tu propuesta marcada "deducido del código, por confirmar".
- Los que no puedes saber (normalmente cliente, requisitos, fecha, verificaciones específicas y dueño), como preguntas en blanco.

No empieces la auditoría hasta que responda. Si respondo que algún dato no aplica o no lo sé, continúa y déjalo marcado "Por definir" en el artefacto y en `CLAUDE.md`.

## 2. Crear o ampliar el artefacto

- Si `CLAUDE.md` ya tiene el enlace de un artefacto del plan, actualiza ESE artefacto con la estructura de este estándar y conserva su historial de cambios. No crees uno nuevo.
- Si no existe, publícalo como artefacto de Claude Code (página web en vivo en claude.ai), no como archivo local.
- Título: "[Nombre del proyecto] · Estado, auditorías y salida a producción".

## 3. Auditoría base del estado del proyecto

Revisa el repositorio módulo por módulo, backend y frontend:

- Endpoints existentes y qué operaciones soportan.
- Si el frontend tiene pantalla para cada operación del backend, o si hay lógica sin UI.
- Estados del flujo principal definidos en el modelo y si todas las transiciones están implementadas y validadas.
- Campos o enums que existen pero nunca se usan, reglas guardadas pero no validadas y eventos sin consumidor.
- Ítems del menú que apuntan a páginas que no existen.
- Preparación para producción: variables de entorno, secretos, migraciones, backups, monitoreo, logs, configuración de despliegue y plan de rollback.
- Las verificaciones específicas del proyecto.

## 4. Las cuatro auditorías

### Formato común de hallazgos

Cada hallazgo lleva:

- ID con prefijo por auditoría: COD-01, SEG-01, TST-01, QA-01.
- Severidad: Crítica, Alta, Media o Baja.
- Ubicación: archivo, función o módulo (solo en vista técnica).
- Impacto en lenguaje de negocio (vista ejecutiva).
- Recomendación concreta.
- Esfuerzo estimado: S, M, L o XL.
- Momento: "Antes de salir" o "Después de salir".

Todo hallazgo Crítico, o Alto que afecte producción, pasa también a "Bloqueantes de salida".

Agrupa los hallazgos menores repetidos en uno solo (por ejemplo, "manejo de errores inconsistente en 14 controladores") en lugar de listarlos uno por uno.

Cada auditoría termina con una calificación de 0 a 100 y un semáforo (verde, amarillo, rojo), explicando el criterio usado para calcularla.

### A. Auditoría de código y deuda técnica

- Arquitectura y organización: separación de responsabilidades, capas, módulos acoplados, dependencias circulares.
- Duplicación de código y lógica repetida entre módulos.
- Complejidad: funciones o archivos demasiado largos, condicionales anidados, clases con demasiadas responsabilidades.
- Código muerto, comentado o sin uso.
- Convenciones: nombres, estructura de carpetas, estilo, consistencia entre módulos. Si hay linter configurado, ejecútalo y resume los resultados.
- Manejo de errores y logs: consistencia, errores silenciados, mensajes genéricos.
- Tipado y validación de datos de entrada.
- Configuración o valores escritos directamente en el código (URLs, credenciales, constantes de negocio).
- Dependencias desactualizadas o abandonadas.
- Comentarios TODO, FIXME o HACK pendientes.
- Documentación: README, cómo levantar el proyecto, documentación de API.
- Inventario de deuda técnica: lista priorizada con el costo de no pagarla.

### B. Auditoría de seguridad

Toma como referencia el OWASP Top 10 vigente y revisa como mínimo:

- Autenticación: manejo de contraseñas, tokens, expiración y renovación de sesión, cierre de sesión.
- Autorización: control por rol en cada endpoint, acceso a recursos de otros usuarios o de otras organizaciones cambiando un ID, datos de identidad que se toman del cliente en lugar del token.
- Inyección: consultas construidas con concatenación, comandos del sistema, plantillas.
- XSS y CSRF.
- Subida de archivos: validación de tipo y tamaño, dónde se guardan, si quedan accesibles públicamente.
- Secretos y configuración: credenciales en el repositorio, archivos `.env` versionados, llaves en el frontend.
- Dependencias con vulnerabilidades conocidas: ejecuta la herramienta del stack si existe (`npm audit`, `pip-audit`, `composer audit` u otra) y resume los resultados por severidad.
- Configuración web: CORS, HTTPS, cabeceras de seguridad, límite de peticiones en login y endpoints sensibles.
- Datos sensibles en logs, mensajes de error o respuestas de la API.
- Protección de datos personales: qué datos se guardan, quién puede verlos, si se registra la autorización de tratamiento y si se cumple la norma aplicable al cliente.
- Trazabilidad: registro de quién hizo qué y cuándo en acciones sensibles.

Aclara en el artefacto que esta revisión no reemplaza pruebas de seguridad especializadas ni un pentest, y recomienda si el proyecto las necesita antes de salir.

### C. Auditoría de pruebas unitarias

- Si existen pruebas, con qué framework y cómo se ejecutan.
- Ejecuta la suite y reporta cuántas pasan, fallan o se omiten. Si no se puede ejecutar, explica por qué.
- Si hay herramienta de cobertura, ejecútala y reporta la cobertura global y por módulo.
- Flujos y reglas de negocio críticos sin pruebas, en orden de riesgo.
- Calidad de las pruebas existentes: si verifican comportamiento real, si tienen aserciones significativas, si abusan de mocks, si son frágiles o dependen del orden.
- Si las pruebas corren en el CI y si bloquean el merge cuando fallan.
- Lista priorizada de las pruebas que deberían escribirse primero. No las escribas salvo que te lo pida.

### D. Auditoría de QA

Esta auditoría se basa en el código, las pruebas automatizadas y la documentación que exista. Aclara en el artefacto que no reemplaza las pruebas manuales del equipo de QA.

- Cobertura funcional: cada requisito y cada flujo por rol contra lo implementado.
- Criterios de aceptación: si existen y si el código los cumple.
- Casos borde: campos vacíos, datos inválidos, duplicados, acciones repetidas, conexión lenta o perdida, permisos denegados, sesiones expiradas.
- Estados de error y mensajes al usuario: si son claros y específicos.
- Experiencia en celular y navegadores, si el producto se usa en campo o en móvil.
- Accesibilidad básica: etiquetas en formularios, contraste, navegación con teclado.
- Rendimiento visible: listados sin paginación, consultas pesadas, imágenes sin optimizar.
- Pruebas de extremo a extremo o de integración existentes.
- Matriz de casos de prueba sugeridos por flujo: caso, pasos resumidos, resultado esperado, prioridad y si debe entrar en la regresión antes de salir.

## 5. Estructura del artefacto

Incluye arriba un interruptor "Vista ejecutiva / Vista técnica", abierto por defecto en vista ejecutiva.

- Vista ejecutiva: lenguaje de negocio, sin nombres de archivos, funciones ni endpoints.
- Vista técnica: todo el detalle.

Secciones, en este orden:

1. **Encabezado:** título, subtítulo con la etapa y la fecha de salida, fecha y hora de última actualización siempre visible, leyenda de estados (Hecho, Parcial, Falta, Por verificar, Propuesta nueva) y navegación por secciones.
2. **Veredicto de lanzamiento:** "Listo para salir", "Listo con condiciones" o "No listo", con una frase que lo justifique y cuenta regresiva de días hábiles si hay fecha de salida. Di explícitamente si los bloqueantes caben en el tiempo disponible.
3. **Resumen ejecutivo:** semáforo general, porcentaje de avance explicando cómo se calculó, 3 a 5 puntos clave y 4 indicadores numéricos grandes.
4. **Tablero de salud:** las cuatro calificaciones (código, seguridad, pruebas unitarias, QA) con semáforo, una frase cada una y cuántos hallazgos hay por severidad. Si hay mediciones anteriores, muestra la tendencia.
5. **Bloqueantes de salida:** lo que obligatoriamente debe resolverse antes de salir, de cualquier auditoría, ordenado por prioridad con su ID.
6. **Cumplimiento de requisitos del cliente:** tabla con cada requisito, su estado verificado y una nota.
7. **Checklist de salida a producción:** seguridad, datos personales, variables de entorno y secretos, migraciones, backups, monitoreo y alertas, logs, manejo de errores, rendimiento, plan de rollback y documentación de despliegue, cada uno con su estado.
8. **Auditoría de código y deuda técnica.**
9. **Auditoría de seguridad.**
10. **Auditoría de pruebas unitarias.**
11. **Auditoría de QA**, con la matriz de casos de prueba.
12. **Avance por módulo:** barra de progreso por módulo, estado general y qué le falta.
13. **Detalle por módulo:** funcionalidades con su estado.
14. **Ciclo de vida del flujo principal:** diagrama de estados y transiciones, marcando lo que funciona y lo que se corta.
15. **Flujos por tipo de usuario:** una tarjeta por rol con los pasos en orden real de uso, marcando dónde se corta ("→ sin pantalla", "→ sin flujo", "→ no existe el módulo") y chips de módulos con * en los que tienen el flujo cortado.
16. **Métricas del proceso:** qué indicadores de negocio puede medir hoy la app y cuáles no.
17. **Matriz de riesgos:** riesgo, impacto, probabilidad, consecuencia para el negocio y mitigación. Incluye riesgos técnicos, de seguridad, de datos, operativos, de adopción, de dependencias externas y de dependencia de personas.
18. **Fases sugeridas:** en bloques Antes de salir, Salida y Después de salir. Cada fase con objetivo, contenido, dependencias, esfuerzo (talla y rango en semanas para un desarrollador) y qué queda demostrable. La salida incluye estrategia (piloto o total), capacitación, despliegue, verificación, monitoreo inicial y criterio de rollback. Las estimaciones son orientativas, con supuestos explícitos y marcadas "por validar con el equipo".
19. **Backlog después de salir:** agrupado por prioridad.
20. **Funcionalidades nuevas que le dan más valor al producto:** tarjetas con categoría, nombre y valor para el cliente o el negocio. No deben ser gaps de lo existente.
21. **Decisiones que necesitan a la gerencia:** con opciones y recomendación.
22. **Siguiente paso:** plan día a día hasta la salida si hay fecha cercana; si no, próximas 2 semanas.
23. **Historial de cambios:** fecha y una línea por cada actualización, la más reciente arriba. Cuando se repitan las auditorías, registra las calificaciones de esa fecha.
24. **Diseño y pulido, en definición conjunta:** sección vacía que se llena con las ideas del equipo.

Pie de página: "Generado con el estándar de auditoría integral creado por José Javier y Mateo Mazo".

## 6. Reglas de presentación

- Tono directo y profesional, sin relleno ni frases de marketing.
- Diseño limpio, responsive, con modo claro y oscuro y badges de color por estado y severidad.
- Filtros en las secciones de auditoría por severidad y por momento (antes o después de salir).
- Estilos de impresión para que se pueda guardar como PDF de forma legible.

## 7. Configurar CLAUDE.md

Agrega al `CLAUDE.md` de la raíz del proyecto (créalo si no existe; si existe, no borres nada) la sección siguiente, completando lo que está entre corchetes con información verificada. Si ya existe una sección del plan de una versión anterior, reemplázala por esta conservando el enlace del artefacto. Muéstrame el cambio antes de guardarlo.

```markdown
# [Nombre del proyecto] · Contexto del proyecto

Estándar del proyecto, basado en el estándar de auditoría integral creado por José Javier y Mateo Mazo. Cualquier ingeniero que desarrolle en este proyecto debe leer esta sección antes de empezar.

## Qué es el producto
[Descripción del producto, cliente, roles y flujo principal.]

## Estado y fechas
[Etapa actual y fecha de salida.] El estado real y actualizado está en el artefacto del plan (enlace abajo). Consúltalo antes de asumir que algo está hecho o pendiente.

## Contexto técnico
[Stack de backend y frontend, estructura principal de carpetas, cómo levantar el proyecto en local, cómo correr las pruebas, roles, estados del flujo principal e integraciones externas. Lo no confirmado va como "Por verificar".]

## Verificaciones específicas
[Puntos propios de este proyecto que toda auditoría debe revisar.]

## Plan y auditorías (artefacto compartido)
- Enlace: [enlace del artefacto]
- Dueño del artefacto (cuenta que lo publica y la única que puede actualizarlo): [dueño]
- Estándar de auditoría: docs/auditoria/auditoria-integral.md
- Es el documento oficial de estado del proyecto. Lo consultan el equipo y la gerencia de desarrollo.

## Reglas
- Si eres el dueño: cuando se termine una tarea, se corrija un bug, se cierre un hallazgo o cambie el estado de algo del plan, actualiza ESTE MISMO artefacto. Nunca crees uno nuevo.
- En cada actualización: cambia solo lo afectado, marca los hallazgos cerrados con su fecha, recalcula calificaciones, avance y veredicto si cambian, actualiza la fecha y agrega una línea al historial.
- No repitas las auditorías completas salvo que se pida o antes de una salida a producción.
- Si no eres el dueño: no actualices el artefacto ni crees uno nuevo. Al terminar una tarea que afecte el plan, deja un resumen de qué cambió y qué hallazgos cerraste (por ID) para que el dueño lo actualice.
- Al escribir código nuevo, no introduzcas problemas del tipo de los hallazgos abiertos del plan (por ejemplo, endpoints sin control por rol, secretos en el código o lógica sin pruebas).
- Al final de cada sesión, si hubo cambios que afectan el plan y no se han reflejado, recuérdalo antes de cerrar.
```

## 8. Al terminar

1. Dame el enlace del artefacto.
2. Dame un resumen de máximo 8 líneas: veredicto, las cuatro calificaciones y los hallazgos más críticos.
3. Lista las herramientas que no pudiste ejecutar y qué quedó "Por verificar" por eso.
4. Después de que apruebe el cambio de `CLAUDE.md`, haz commit de `CLAUDE.md` y de `docs/auditoria/auditoria-integral.md` (si no estaba versionado) con el mensaje "docs: agrega estándar de auditoría integral y contexto del proyecto". Antes del push, muéstrame la rama y el commit para confirmarlo.

## 9. Mantenimiento durante la sesión

Durante el resto de la sesión, cada vez que terminemos una tarea, corrijamos un bug, cerremos un hallazgo o cambie el estado de algo del plan, actualiza el mismo artefacto siguiendo las reglas de la sección 7.
