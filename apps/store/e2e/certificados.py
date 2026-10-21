"""
Certificados de PRUEBA para el recorrido e2e (P6-04): `python e2e/certificados.py <dir> <rfc>`.

Escribe en `<dir>` una e.firma y un CSD sintéticos del RFC dado (`efirma.cer/.key`,
`csd.cer/.key`) con la fábrica de la suite de la API (`tests/plan_p/certs_sat.py`): CA
propia, nada del SAT. Imprime la contraseña. Se corre desde `apps/store`.
"""

import sys
from pathlib import Path

API = Path(__file__).resolve().parents[2] / "api"
sys.path.insert(0, str(API))

from tests.plan_p.certs_sat import generar  # noqa: E402


def main() -> None:
    destino, rfc = Path(sys.argv[1]), sys.argv[2]
    destino.mkdir(parents=True, exist_ok=True)
    password = "clave-e2e-123"
    for tipo, numero, semilla in (
        ("efirma", "30001000000500003416", 1),
        ("csd", "30001000000500003417", 2),
    ):
        par = generar(rfc=rfc, tipo=tipo, password=password, numero=numero, semilla=semilla)
        (destino / f"{tipo}.cer").write_bytes(par.cer)
        (destino / f"{tipo}.key").write_bytes(par.key)
    print(password)


if __name__ == "__main__":
    main()
