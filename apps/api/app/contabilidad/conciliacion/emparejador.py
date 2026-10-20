"""
Emparejamiento automático banco ↔ libros (P2-06). Puro: sin base de datos.

QUÉ SE COMPARA
--------------
Cada lado es una lista de `Partida` con importe CON SIGNO desde el punto de vista del banco:
+ entra dinero (abono del banco = cargo a la cuenta de bancos en libros), − sale.

- Banco: los movimientos del estado de cuenta pendientes.
- Libros: los movimientos de pólizas activas sobre la cuenta contable ligada a la cuenta
  bancaria (y opcionalmente complementos de pago / CFDI PUE de la bóveda que aún no tengan
  póliza que mueva bancos).

PUNTAJE (0–100)
---------------
El importe exacto es requisito (ninguna diferencia de centavos se concilia sola). Sobre eso:
- 50 por importe exacto.
- hasta 30 por cercanía de fecha: 30 el mismo día, bajando linealmente a 10 en el borde de
  la ventana. Fuera de la ventana no hay candidato.
- 20 si la referencia del banco aparece en el concepto de libros (o al revés), si el UUID
  del CFDI o el RFC de la contraparte aparecen en el concepto del banco.
Se concilia en automático con puntaje ≥ umbral (default 60 de la cuenta bancaria: importe
exacto + fecha razonablemente cercana, o importe + referencia).

UNO A UNO PRIMERO, LUEGO UNO A VARIOS
-------------------------------------
1. Uno a uno: todos los pares candidatos se ordenan por puntaje (desc), luego por distancia
   de fechas, y se toman glotonamente sin repetir partida. Un empate exacto de puntaje y
   distancia entre dos candidatos para la misma partida se deja PENDIENTE (ambiguo): es mejor
   que el contador lo decida que conciliar el equivocado.
2. Uno a varios: para cada movimiento del banco que siguió pendiente, se busca un
   subconjunto de 2 a `MAX_GRUPO` movimientos de libros del mismo signo, dentro de la ventana,
   cuya suma sea exacta (p. ej. un depósito que liquida tres facturas). También al revés
   (un movimiento de libros contra varios del banco, p. ej. una póliza de nómina pagada en
   varias transferencias). Puntaje = 50 + fecha del más lejano + 20 si alguno trae
   referencia; se exige el mismo umbral.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from itertools import combinations

MAX_GRUPO = 4
MAX_CANDIDATOS_GRUPO = 14


@dataclass(frozen=True)
class Partida:
    clave: str  # "b:<id>", "p:<id>" o "c:<id>"
    fecha: date
    importe: Decimal  # con signo: + entra, − sale
    texto: str = ""  # concepto, en minúsculas
    referencia: str = ""
    uuid: str = ""
    rfc: str = ""


@dataclass
class Emparejamiento:
    banco: list[str]
    libros: list[str]
    puntaje: int
    motivo: str


@dataclass
class Resultado:
    emparejados: list[Emparejamiento] = field(default_factory=list)
    ambiguos: list[str] = field(default_factory=list)


def _puntaje_fecha(a: date, b: date, ventana: int) -> int | None:
    d = abs((a - b).days)
    if d > ventana:
        return None
    if ventana == 0:
        return 30
    return round(30 - 20 * d / ventana)


def _coincide_texto(b: Partida, lib: Partida) -> str:
    bt, lt = b.texto.lower(), lib.texto.lower()
    ref_b, ref_l = b.referencia.lower().strip(), lib.referencia.lower().strip()
    if ref_b and len(ref_b) >= 4 and (ref_b in lt or ref_b == ref_l):
        return "referencia"
    if ref_l and len(ref_l) >= 4 and ref_l in bt:
        return "referencia"
    if lib.uuid and (lib.uuid.lower() in bt or lib.uuid.lower()[:8] in bt):
        return "uuid"
    if lib.rfc and len(lib.rfc) >= 12 and lib.rfc.lower() in bt:
        return "rfc"
    return ""


def puntaje(b: Partida, lib: Partida, ventana: int) -> tuple[int, str] | None:
    """Puntaje de un par (None si no es candidato)."""
    if b.importe != lib.importe or b.importe == 0:
        return None
    pf = _puntaje_fecha(b.fecha, lib.fecha, ventana)
    if pf is None:
        return None
    por = _coincide_texto(b, lib)
    motivo = "importe exacto" + (f", {abs((b.fecha - lib.fecha).days)} días")
    if por:
        motivo += f", {por} en el concepto"
    return 50 + pf + (20 if por else 0), motivo


def emparejar(banco: list[Partida], libros: list[Partida], *, ventana: int = 3,
              umbral: int = 60) -> Resultado:
    resultado = Resultado()
    # 1) uno a uno
    pares = []
    for b in banco:
        for lib in libros:
            p = puntaje(b, lib, ventana)
            if p is not None:
                pares.append((p[0], abs((b.fecha - lib.fecha).days), b.clave, lib.clave, p[1]))
    pares.sort(key=lambda x: (-x[0], x[1], x[2], x[3]))
    usados: set[str] = set()
    for i, (pts, dist, cb, cl, motivo) in enumerate(pares):
        if pts < umbral or cb in usados or cl in usados:
            continue
        rivales = [x for x in pares[i + 1:] if x[0] == pts and x[1] == dist
                   and (x[2] == cb or x[3] == cl) and x[2] not in usados
                   and x[3] not in usados]
        if rivales:
            # Empate exacto: no se adivina.
            usados.update({cb, cl, *[r[2] for r in rivales], *[r[3] for r in rivales]})
            resultado.ambiguos.extend(sorted({cb, *[r[2] for r in rivales]}))
            continue
        usados.update({cb, cl})
        resultado.emparejados.append(Emparejamiento([cb], [cl], pts, motivo))
    # Los ambiguos vuelven a estar libres para el contador (no para el automático).
    bloqueados = set(usados)

    # 2) uno a varios (banco 1 → libros N, y libros 1 → banco N)
    def _grupos(unos: list[Partida], varios: list[Partida], banco_es_uno: bool) -> None:
        for u in unos:
            if u.clave in bloqueados:
                continue
            cand = [v for v in varios if v.clave not in bloqueados and v.importe != 0
                    and (v.importe > 0) == (u.importe > 0)
                    and abs((u.fecha - v.fecha).days) <= ventana]
            cand.sort(key=lambda v: abs((u.fecha - v.fecha).days))
            cand = cand[:MAX_CANDIDATOS_GRUPO]
            hallado = None
            for n in range(2, MAX_GRUPO + 1):
                for combo in combinations(cand, n):
                    if sum((c.importe for c in combo), Decimal("0")) == u.importe:
                        hallado = combo
                        break
                if hallado:
                    break
            if not hallado:
                continue
            lejos = max(abs((u.fecha - c.fecha).days) for c in hallado)
            pf = _puntaje_fecha(u.fecha, u.fecha, ventana) if lejos == 0 else \
                round(30 - 20 * lejos / max(ventana, 1))
            con_texto = any(
                _coincide_texto(u, c) if banco_es_uno else _coincide_texto(c, u)
                for c in hallado)
            pts = 50 + (pf or 0) + (20 if con_texto else 0)
            if pts < umbral:
                continue
            claves = [c.clave for c in hallado]
            bloqueados.update({u.clave, *claves})
            motivo = f"suma exacta de {len(claves)} movimientos"
            if banco_es_uno:
                resultado.emparejados.append(Emparejamiento([u.clave], claves, pts, motivo))
            else:
                resultado.emparejados.append(Emparejamiento(claves, [u.clave], pts, motivo))

    _grupos(banco, libros, True)
    _grupos(libros, banco, False)
    return resultado
