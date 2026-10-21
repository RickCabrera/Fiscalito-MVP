"""
Piezas compartidas por las rutas de nómina (F1-07): el router y el aviso de demo.

Un solo `APIRouter` para todo el paquete: así las rutas se registran en el mismo orden y con
el mismo tag que cuando vivían en `routes/nomina.py`, y el OpenAPI no cambia ni un byte.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Nómina (demo)"])

# La sesión la exige app/main.py para todo /api/v1 (P0-02).
_AVISO = "DEMO — no desplegar. "
