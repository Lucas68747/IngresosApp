# Historial de cambios

Todas las versiones de IngresosApp. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y la numeración, [Versionado Semántico](https://semver.org/lang/es/): `MAYOR.MENOR.PARCHE`.

## [Sin publicar] · 2.0.0

### Agregado
- Registro de salidas y lista de quienes siguen dentro del predio.
- Guardia de turno: cada ingreso, salida y cambio queda firmado con la guardia que lo hizo.
- Ingresos a pie (sin dominio) y campo de observaciones.
- Historial de cada registro: qué cambió, cuándo y quién lo cambió.
- Búsqueda por dominio, empresa, persona, destino u observaciones.
- Copia de seguridad automática diaria, con las últimas 30 copias.
- Importación automática de los datos de la versión 1.0, sin modificar el archivo original.

### Cambiado
- Los registros ya no se borran: se anulan con un motivo y siguen apareciendo en los reportes.
- Los dominios se guardan normalizados (`ab 123 cd` → `AB123CD`) y se muestran con espacios.
- La base de datos se guarda en una carpeta fija (Documentos\IngresosApp), sin importar desde dónde se abra la app.
- Licencia MIT.

### Corregido
- Modificar un registro ya no reemplaza la fecha y la hora de ingreso por la de la edición.
- La base de datos se crea sola al abrir la app; ya no hace falta usar el menú.
- Se validan los datos: no se pueden guardar ingresos vacíos.
- Las consultas usan parámetros en lugar de concatenar texto.

## [1.0] · 2024-01-22

Primera versión: carga, modificación y eliminación de ingresos con fecha y hora automáticas,
listado y exportación a PDF. Ejecutables para Windows y Linux.

[1.0]: https://github.com/Lucas68747/IngresosApp/releases/tag/v1.0
