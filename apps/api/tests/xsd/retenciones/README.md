# XSD del CFDI de Retenciones e información de pagos 2.0 (P3-04)

| Archivo | Bytes | SHA-256 | URL oficial |
|---|---:|---|---|
| `retencionpagov2.xsd` | 6,594 | `66b1d42242a714174f5e690317c0ffb2567af32cce2a0d22644b180a4939f01c` | `http://www.sat.gob.mx/esquemas/retencionpago/2/retencionpagov2.xsd` |
| `catRetenciones.xsd` | 12,491 | `0c69145c6b2905873158a204e3a6886fca86a86726b790c34c131072f60a80bc` | `http://www.sat.gob.mx/esquemas/retencionpago/1/catalogos/catRetenciones.xsd` |

## De dónde salen

**Fecha: 2026-10-19.** `www.sat.gob.mx` no resuelve desde el entorno donde se armó la tarea,
así que se tomaron del paquete PyPI **`satcfdi` 26.10.1** (licencia MIT), carpeta
`satcfdi/transform/schemas/www.sat.gob.mx/esquemas/retencionpago/`, que replica las rutas del
SAT.

**No son byte-idénticos a lo publicado por el SAT**: `satcfdi` los distribuye minificados (sin
espacios ni saltos de línea entre nodos). El contenido —tipos, catálogos, atributos— es el
mismo. Cuando el sitio del SAT sea alcanzable, conviene reemplazarlos por la descarga directa
y actualizar esta tabla y la copia de la app (`app/retenciones_cfdi/sat/`).

`retencionpagov2.xsd` importa `catCFDI.xsd` y `tdCFDI.xsd` por ruta relativa. Los tests los
resuelven con el snapshot OFICIAL de `tests/xsd/` (byte-idéntico al SAT, ver el README de
arriba), así que la validación de los tests usa los catálogos del SAT; la app usa la copia de
`satcfdi` en `app/retenciones_cfdi/sat/`.

`tests/plan_p/test_retenciones_cfdi.py::test_copias_de_los_xsd_son_identicas` exige que estas
copias, la de la app y los hashes de esta tabla coincidan.
