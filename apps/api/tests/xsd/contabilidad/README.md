# XSD de contabilidad electrónica (Anexo 24 RMF, versión 1.3)

Esquemas y hojas de transformación (cadena original) del SAT para los XML de contabilidad
electrónica, guardados aquí para que `tests/plan_p/test_anexo24.py` valide **sin red**.
Es el "Listo cuando" de P2-07: los XML de catálogo, balanza y pólizas de un mes validan
contra estos XSD.

## Fuente

Copia byte por byte de lo que publica el SAT en
`http://www.sat.gob.mx/esquemas/ContabilidadE/1_3/...` y
`http://www.sat.gob.mx/esquemas/utilerias.xslt`, **tomada del paquete PyPI `satcfdi` 26.10.0**
(licencia MIT, `satcfdi/transform/schemas/www.sat.gob.mx/esquemas/`), el **2026-10-19**.
El sitio del SAT no fue alcanzable desde el entorno de desarrollo (DNS/proxy), así que no se
pudo comparar el hash contra la descarga directa: **POR CONFIRMAR** bajando los archivos de
`sat.gob.mx` y comparando con la tabla de abajo.

Se conserva la estructura de carpetas del SAT: cada XSD importa
`../CatalogosParaEsqContE/CatalogosParaEsqContE.xsd` y cada XSLT incluye
`../../../utilerias.xslt` por ruta relativa. La app usa una copia idéntica en
`apps/api/app/contabilidad/anexo24/sat/` (los `tests/` no entran a la imagen de Docker);
el test exige que las dos copias sean iguales.

Los XSLT se llaman `*_1_2.xslt` y apuntan al namespace 1_3: así los publica el SAT.

## Snapshot

| Archivo (bajo `esquemas/`) | SHA-256 |
|---|---|
| `ContabilidadE/1_3/CatalogoCuentas/CatalogoCuentas_1_3.xsd` | `40334af7689237a2faff22eefb595d19fa56dc66712014aa41fa8ef4da061f01` |
| `ContabilidadE/1_3/BalanzaComprobacion/BalanzaComprobacion_1_3.xsd` | `02df1d97862eaf57ad92ab4eaddd86ea3b4625c2c04ebce2e89342f61a6977cc` |
| `ContabilidadE/1_3/PolizasPeriodo/PolizasPeriodo_1_3.xsd` | `4d83675a54fd04d9db5ec3c750b1bc6c2a1cda3ce9c0f774e2bf5754a32673ec` |
| `ContabilidadE/1_3/AuxiliarCtas/AuxiliarCtas_1_3.xsd` | `ec85d5381730dd7f00df14793ef10c370600717ee38f3508964ca9972592382c` |
| `ContabilidadE/1_3/AuxiliarFolios/AuxiliarFolios_1_3.xsd` | `ae865b852e93bd669dacd8156070baa57562d42f64997e25bb005d3ac9ef1f1b` |
| `ContabilidadE/1_3/CatalogosParaEsqContE/CatalogosParaEsqContE.xsd` | `4641439c4e710e3b7761755214d827bc98d4b50fdf587b6f3672034cf215fa51` |
| `ContabilidadE/1_3/SelloDigitalContElec/SelloDigitalContElec.xsd` | `a4a887db2e02ad107168f36ac4168498edd1d988ca878d83ced62125a4be733f` |
| `ContabilidadE/1_3/CatalogoCuentas/CatalogoCuentas_1_2.xslt` | `1a3b768e5e8f0c99083ce53849b2a87af676e798843d9719c45ab9d027e70389` |
| `ContabilidadE/1_3/BalanzaComprobacion/BalanzaComprobacion_1_2.xslt` | `a715833a58da54ed91cd4b2b95a8a44be559f2ab3815a1184b48b3139ad3d0c5` |
| `ContabilidadE/1_3/PolizasPeriodo/PolizasPeriodo_1_2.xslt` | `112fafaab878eb0c3a4e8529178d865877d18caa75b76133cfdea96cd1a4e4fa` |
| `ContabilidadE/1_3/AuxiliarCtas/AuxiliarCtas_1_2.xslt` | `1f2350c044d11dbf23aa741472261b7969733784810d353d73dfd0f8611b9665` |
| `ContabilidadE/1_3/AuxiliarFolios/AuxiliarFolios_1_2.xslt` | `4f043e1a321758ceaf2afa41c952d30ecb5d4386a97a4140ceeb658c28d7088a` |
| `ContabilidadE/1_3/SelloDigitalContElec/SelloDigitalContElec.xslt` | `963251e7da43108f6137b542b38e96622ff953cd0ebec173810794a80629dd7e` |
| `utilerias.xslt` | `4df421ef981d48d4a7861777f2bd30299eb0c5c3035ad27880fdb1f91cda0f6b` |

## Alcance

El XSD valida estructura y catálogos (código agrupador, bancos, monedas, métodos de pago).
No valida reglas de negocio del Anexo 24 (p. ej. que la balanza cuadre o que el catálogo
tenga todas las cuentas de la balanza); eso lo revisa el generador y lo reporta como
advertencia. El catálogo `c_CodAgrup` es el mismo que siembra `app/contabilidad/datos/`.
