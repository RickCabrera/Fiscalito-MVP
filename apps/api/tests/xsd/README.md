# XSD del SAT versionados

Esquemas del CFDI 4.0 y del complemento de nómina 1.2, guardados aquí para que
`tests/nomina/test_cfdi_nomina_xml.py` valide **sin red**, que es lo que pide el
criterio de cierre de F1-05.

## Los archivos son byte-idénticos a lo que publica el SAT

**No se les reescribió el `schemaLocation`.** La resolución offline la hace el
test con un `etree.Resolver` de lxml que mapea las URLs `http://www.sat.gob.mx/…`
a estos archivos locales.

Es a propósito: un archivo editado hashea a la salida del editor, no a lo que
publicó la autoridad, y entonces el SHA-256 de abajo no verificaría nada contra
la fuente oficial. `tests/nomina/test_xsd_versionados.py` recalcula los seis
hashes y los compara — un README con hashes que nadie ejecuta es prosa.

## Snapshot

**Fecha de descarga: 2026-09-01.** Descargados con `scripts/descargar_xsd.py`.

| Archivo | Bytes | SHA-256 | Origen |
|---|---:|---|---|
| `cfdv40.xsd` | 50,607 | `2489b5b535f5cbc6a6c2db6132620de1833f85372512d01deea62880e700e276` | `http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd` |
| `nomina12.xsd` | 40,348 | `ac5db22ceee35c2224aad8745a3ab968c9c3d04d36adb50d056c83c4c1a29083` | `http://www.sat.gob.mx/sitio_internet/cfd/nomina/nomina12.xsd` |
| `TimbreFiscalDigitalv11.xsd` | 4,732 | `fb3d061fe9914500bef8beb3ea2e8722ee8a8224fa3af63643877a64c0ea05f7` | `http://www.sat.gob.mx/sitio_internet/cfd/TimbreFiscalDigital/TimbreFiscalDigitalv11.xsd` |
| `catCFDI.xsd` | 5,984,046 | `6c58936cb77576f839a4d7915953ceaf252b9eb9319f9458fe5bb67ae2bb0bb1` | `http://www.sat.gob.mx/sitio_internet/cfd/catalogos/catCFDI.xsd` |
| `catNomina.xsd` | 13,868 | `aeabf62f9901d75d5dccf0fbed13dd9dca6295e5b0ef40c9d89edcae3c641bc9` | `http://www.sat.gob.mx/sitio_internet/cfd/catalogos/Nomina/catNomina.xsd` |
| `tdCFDI.xsd` | 7,315 | `b3b81fe4017b95d5477f23a32f47e8b0571683cfddfff1330508c75e02b504cd` | `http://www.sat.gob.mx/sitio_internet/cfd/tipoDatos/tdCFDI/tdCFDI.xsd` |

### Por qué `catCFDI.xsd` pesa 6 MB

Son las enumeraciones de `c_ClaveProdServ` (~52 mil claves) y `c_CodigoPostal`
(~95 mil). Un CFDI de nómina **las usa**: `ClaveProdServ="84111505"` en el
concepto y el CP del emisor en `LugarExpedicion`. `cfdv40.xsd` referencia
`catCFDI` en 25 atributos, así que no se puede omitir sin romper la validación.

## ⚠️ Este snapshot caduca, y el test no se va a enterar

`knowledge_base/nomina/24_cfdi_nomina_12.md` §3 lo advierte: **los catálogos del
SAT son vivos**. El SAT agrega claves sin cambiar la versión 1.2 del
complemento — en 2026 incorporó claves de percepción y deducción para días de
descanso laborados.

Consecuencia directa: **que un XML valide contra estos archivos no prueba que
valide contra el catálogo vigente.** Un CFDI que use una clave publicada después
del 2026-09-01 fallaría aquí y sería correcto en el mundo real.

Cuando haya que refrescar: `python scripts/descargar_xsd.py`, actualizar esta
tabla y las constantes de `test_xsd_versionados.py`.

## Alcance de la validación

El XSD valida **estructura y catálogos**. No valida las reglas de la Guía de
llenado ni las validaciones adicionales del Anexo 20, así que un XML que pasa
aquí **no es evidencia de que un PAC lo aceptaría**. El timbrado real es F3
(§D7).

## `envoltorio_validacion.xsd` no es del SAT

Ese archivo lo escribimos nosotros. El `Complemento` del CFDI es un wildcard
*strict*, así que los esquemas del complemento tienen que estar en la misma
colección para que el validador los reconozca; el envoltorio solo los importa a
los tres. No lleva hash porque no viene de ninguna autoridad.
