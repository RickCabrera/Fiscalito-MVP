# Servicios externos

Cada servicio externo vive detrás de un adaptador en `apps/api/app/integraciones/<servicio>.py`
(un `Protocol`, una implementación `falso` sin red y las reales) y se elige con la variable
`FISCALITO_<SERVICIO>`. Sin la variable se usa `falso` fuera de producción
(`FISCALITO_ENTORNO=produccion` exige configurarla). `GET /health/integraciones` dice qué
implementación usa cada uno. Convenciones en `docs/arquitectura-p.md`.

Una sección por servicio: qué es, variables, cómo se prueba y a quién contratar.

---

## Almacenamiento de archivos (`almacenamiento`) — P0-03

**Qué es.** Donde viven los XML originales de la bóveda de CFDI (y, más adelante, PDF y papeles
de trabajo). La app guarda, lee, borra y pregunta si existe por **ruta relativa**
(`cfdi/<despacho>/<cliente_id>/<UUID>.xml`); la base de datos sólo guarda la ruta y el SHA-256.
Ninguna implementación acepta rutas absolutas ni con `..`.

| Variable | Valores | Default | Para qué |
|---|---|---|---|
| `FISCALITO_ALMACENAMIENTO` | `falso`, `local`, `s3` | `falso` (dev) | Elige la implementación |
| `FISCALITO_ALMACEN_DIR` | ruta | `./almacen` | Carpeta raíz de `falso`/`local` |
| `FISCALITO_S3_BUCKET` | nombre | — (**obligatoria** con `s3`) | Bucket |
| `FISCALITO_S3_ENDPOINT` | URL | — (AWS) | Endpoint S3 compatible. R2: `https://<cuenta>.r2.cloudflarestorage.com` |
| `FISCALITO_S3_REGION` | texto | `auto` | Región (`auto` en R2) |
| `FISCALITO_S3_ACCESS_KEY` | llave | — | Access key ID |
| `FISCALITO_S3_SECRET_KEY` | secreto | — | Secret access key |
| `FISCALITO_S3_PREFIJO` | texto | vacío | Prefijo dentro del bucket (p. ej. `prod`) |

- **`falso` y `local` son la misma clase (disco).** `falso` no es memoria a propósito: el
  SQLite de desarrollo sobrevive reinicios y el almacén también tiene que hacerlo, o la base
  diría que un XML existe que ya se perdió. `almacen/` está en `.gitignore`.
- **`s3`** usa boto3 y sirve para AWS S3, Cloudflare R2 o MinIO. Sin `FISCALITO_S3_BUCKET`
  responde 503 con el nombre de la variable que falta.

**Cómo se prueba.** `apps/api/tests/plan_p/test_almacenamiento.py`: disco en `tmp_path`, una
implementación en memoria para pruebas de dominio, y S3 con un cliente boto3 real envuelto en
`botocore.stub.Stubber` que verifica cada llamada (`put_object`, `get_object`, `head_object`,
`delete_object`, errores 404/403) **sin red**.

**A quién contratar.** Recomendado: **Cloudflare R2** (sin costo de egreso, 10 GB gratis al
mes). Crear un bucket privado, un token de API con permiso de lectura y escritura sólo sobre
ese bucket, y pegar las cinco variables `FISCALITO_S3_*` en Railway. Alternativa: AWS S3 con un
usuario IAM limitado al bucket.
