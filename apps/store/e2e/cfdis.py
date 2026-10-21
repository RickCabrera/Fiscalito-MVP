"""
CFDI sintéticos que "baja" el SAT falso en el recorrido e2e (P6-04).

`python e2e/cfdis.py <dir> <rfc> <AAAA-MM>` escribe en `<dir>/emitidos/` y
`<dir>/recibidos/` los XML que `DescargaSatFalso` entrega cuando la API corre con
`FISCALITO_SAT_FALSO_DIR=<dir>`. Usa la fábrica de la suite de la API
(`tests/plan_p/cfdi_sintetico.py`): RFC y UUID inventados, sellos de relleno.

Importes del mes (los que el recorrido espera ver en la balanza):
- Emitidos: 10,000 + 5,000 de subtotal, IVA 16 % → ingresos 15,000, IVA trasladado 2,400.
- Recibido: 2,000 de subtotal, IVA 320 (un gasto del cliente).
"""

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[2] / "api"
sys.path.insert(0, str(API))

from tests.plan_p.cfdi_sintetico import cfdi, uuid_n  # noqa: E402

COMPRADOR = "COM010101BB2"
PROVEEDOR = "PRO010101AA1"


def main() -> None:
    destino, rfc, mes = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    emitidos, recibidos = destino / "emitidos", destino / "recibidos"
    emitidos.mkdir(parents=True, exist_ok=True)
    recibidos.mkdir(parents=True, exist_ok=True)
    for n, (dia, sub, iva) in enumerate([("05", "10000.00", "1600.00"),
                                         ("12", "5000.00", "800.00")], start=1):
        total = f"{float(sub) + float(iva):.2f}"
        uuid = uuid_n(n, "E2E00000")
        (emitidos / f"{uuid}.xml").write_bytes(cfdi(
            uuid, emisor=rfc, receptor=COMPRADOR, fecha=f"{mes}-{dia}T10:00:00",
            subtotal=sub, total=total, iva=iva,
        ))
    uuid = uuid_n(3, "E2E00000")
    (recibidos / f"{uuid}.xml").write_bytes(cfdi(
        uuid, emisor=PROVEEDOR, receptor=rfc, fecha=f"{mes}-08T09:00:00",
        subtotal="2000.00", total="2320.00", iva="320.00",
    ))


if __name__ == "__main__":
    main()
