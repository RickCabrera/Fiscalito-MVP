"""
Estados financieros desde la balanza (P2-05): estado de resultados y balance general.

DE DÓNDE SALE CADA IMPORTE
--------------------------
De `balanza.totales_por_cuenta` —la misma consulta agregada en SQL que pinta la balanza—,
así que un reporte cuadra con la balanza del mismo periodo por construcción. Los importes
se suman SIEMPRE desde las cuentas afectables (hojas); los renglones de cuentas acumulativas
son sólo presentación y nunca entran dos veces a un total.

- **Estado de resultados**: el MOVIMIENTO del periodo (cargos − abonos) de las cuentas de
  resultados; columna "acumulado" del 1 de enero del ejercicio a `hasta`.
- **Balance general**: el SALDO FINAL a `hasta` de las cuentas de balance, más el resultado
  del ejercicio (saldo de las cuentas de resultados todavía no cerradas). Cuadre:
  activo = pasivo + capital contable (capital + resultado). Las cuentas de orden van aparte
  y no entran al cuadre.

CLASIFICACIÓN (por el código agrupador del SAT de cada cuenta)
---------------------------------------------------------------
El rubro sale del primer segmento del código agrupador (Anexo 24): 101–149 activo
circulante, 150–199 no circulante, 201–249 pasivo a corto plazo, 250–299 a largo, 3xx
capital, 401–402 ingresos, 5xx costo, 6xx gastos de operación (salvo 611 ISR, que va en
impuestos a la utilidad), 403/702/704 otros ingresos y productos financieros, 701/703
gastos financieros y otros gastos, 8xx orden. Si un agrupador no es numérico se usa el
`tipo` de la cuenta. Es la estructura de la NIF B-3 (estado de resultado integral, por
función) y la NIF B-6 (estado de situación financiera, circulante / no circulante).

MONEDA
------
La contabilidad se lleva en MXN. Para ver un reporte en otra moneda se divide cada importe
entre `tipo_cambio`. No hay una tabla de tipos de cambio guardados en el sistema todavía:
el tipo de cambio lo captura el usuario (p. ej. el FIX del DOF del día de cierre) y se
rechaza la petición si falta. Nunca se inventa un tipo de cambio.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.contabilidad import agrupador, catalogo
from app.contabilidad.asientos import CERO
from app.contabilidad.balanza import totales_por_cuenta
from app.exceptions import FiscalAgentError
from app.modelos.contabilidad import CuentaContable
from app.modelos.nucleo import Cliente

COMPARATIVOS = ("ninguno", "periodo_anterior", "anio_anterior")
SOLO = ("con_movimiento", "con_saldo_o_movimiento", "todas")
AGRUPAR = ("cuenta", "agrupador")
UN_CENTAVO = Decimal("0.01")

ETIQUETAS: dict[str, dict[str, str]] = {
    "es": {
        "estado_resultados": "Estado de resultados", "balance_general": "Balance general",
        "ingresos": "Ingresos", "costo": "Costo de ventas", "utilidad_bruta": "Utilidad bruta",
        "gastos": "Gastos de operación", "utilidad_operacion": "Utilidad de operación",
        "otros_ingresos": "Otros ingresos y productos financieros",
        "otros_gastos": "Gastos financieros y otros gastos",
        "utilidad_antes_impuestos": "Utilidad antes de impuestos",
        "impuestos": "Impuestos a la utilidad", "utilidad_neta": "Utilidad neta del ejercicio",
        "activo_circulante": "Activo circulante", "activo_no_circulante": "Activo no circulante",
        "total_activo": "Total activo", "pasivo_corto": "Pasivo a corto plazo",
        "pasivo_largo": "Pasivo a largo plazo", "total_pasivo": "Total pasivo",
        "capital": "Capital contable", "resultado": "Resultado del ejercicio",
        "total_capital": "Total capital contable",
        "sin_cierre": "Resultados de ejercicios anteriores sin cierre anual",
        "pasivo_mas_capital": "Total pasivo más capital", "orden": "Cuentas de orden",
        "total": "Total", "importe": "Periodo", "acumulado": "Acumulado del ejercicio",
        "saldo": "Saldo", "comparativo": "Comparativo", "variacion": "Variación",
    },
    "en": {
        "estado_resultados": "Income statement", "balance_general": "Balance sheet",
        "ingresos": "Revenue", "costo": "Cost of sales", "utilidad_bruta": "Gross profit",
        "gastos": "Operating expenses", "utilidad_operacion": "Operating income",
        "otros_ingresos": "Other income and financial income",
        "otros_gastos": "Financial and other expenses",
        "utilidad_antes_impuestos": "Income before taxes",
        "impuestos": "Income taxes", "utilidad_neta": "Net income",
        "activo_circulante": "Current assets", "activo_no_circulante": "Non-current assets",
        "total_activo": "Total assets", "pasivo_corto": "Current liabilities",
        "pasivo_largo": "Long-term liabilities", "total_pasivo": "Total liabilities",
        "capital": "Equity", "resultado": "Net income for the year",
        "total_capital": "Total equity",
        "sin_cierre": "Prior years' results not yet closed",
        "pasivo_mas_capital": "Total liabilities and equity", "orden": "Memorandum accounts",
        "total": "Total", "importe": "Period", "acumulado": "Year to date",
        "saldo": "Balance", "comparativo": "Comparative", "variacion": "Change",
    },
}

# sección → signo con que se presenta (+1: saldo deudor positivo; −1: acreedor positivo).
SIGNO = {
    "ingresos": -1, "costo": 1, "gastos": 1, "otros_ingresos": -1, "otros_gastos": 1,
    "impuestos": 1, "activo_circulante": 1, "activo_no_circulante": 1, "pasivo_corto": -1,
    "pasivo_largo": -1, "capital": -1, "resultado": -1, "orden": 1,
}
SECCIONES_ER = ("ingresos", "costo", "gastos", "otros_ingresos", "otros_gastos", "impuestos")
SECCIONES_BG = ("activo_circulante", "activo_no_circulante", "pasivo_corto", "pasivo_largo",
                "capital")
RESULTADOS = set(SECCIONES_ER)


def _mayor(cuenta: CuentaContable) -> int | None:
    cabeza = (cuenta.codigo_agrupador or "").split(".")[0]
    return int(cabeza) if cabeza.isdigit() else None


def seccion(cuenta: CuentaContable) -> str:
    """El rubro de la cuenta en los estados financieros (ver CLASIFICACIÓN)."""
    m = _mayor(cuenta)
    if m is not None:
        if 100 <= m < 150:
            return "activo_circulante"
        if 150 <= m < 200:
            return "activo_no_circulante"
        if 200 <= m < 250:
            return "pasivo_corto"
        if 250 <= m < 300:
            return "pasivo_largo"
        if 300 <= m < 400:
            return "capital"
        if m in (401, 402):
            return "ingresos"
        if m in (403, 702, 704):
            return "otros_ingresos"
        if 500 <= m < 600:
            return "costo"
        if m == 611:
            return "impuestos"
        if 600 <= m < 700:
            return "gastos"
        if m in (701, 703):
            return "otros_gastos"
        if 800 <= m < 900:
            return "orden"
    return {"activo": "activo_circulante", "pasivo": "pasivo_corto", "capital": "capital",
            "ingreso": "ingresos", "costo": "costo", "gasto": "gastos"}.get(cuenta.tipo, "orden")


def es_de_resultados(cuenta: CuentaContable) -> bool:
    return seccion(cuenta) in RESULTADOS


# ── rangos ──


def _fin_de_mes(anio: int, mes: int) -> date:
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def _menos_meses(d: date, meses: int) -> tuple[int, int]:
    total = d.year * 12 + d.month - 1 - meses
    return total // 12, total % 12 + 1


def _menos_un_anio(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year - 1, day=28)


def rango_comparativo(desde: date, hasta: date, tipo: str) -> tuple[date, date] | None:
    """El rango contra el que se compara: el periodo anterior o el mismo del año anterior."""
    if tipo == "ninguno":
        return None
    if tipo == "anio_anterior":
        return _menos_un_anio(desde), _menos_un_anio(hasta)
    meses_completos = desde.day == 1 and hasta == _fin_de_mes(hasta.year, hasta.month)
    if meses_completos:
        meses = (hasta.year - desde.year) * 12 + hasta.month - desde.month + 1
        a, m = _menos_meses(desde, meses)
        ah, mh = _menos_meses(hasta, meses)
        return date(a, m, 1), _fin_de_mes(ah, mh)
    dias = (hasta - desde).days + 1
    return desde - timedelta(days=dias), desde - timedelta(days=1)


# ── agregación ──


@dataclass
class Opciones:
    nivel: int | None = None
    solo: str = "con_saldo_o_movimiento"
    agrupar: str = "cuenta"
    moneda: str = "MXN"
    tipo_cambio: Decimal | None = None
    idioma: str = "es"
    comparar: str = "ninguno"
    incluir_cierre: bool = False

    def validar(self) -> None:
        if self.solo not in SOLO or self.agrupar not in AGRUPAR or \
                self.comparar not in COMPARATIVOS or self.idioma not in ETIQUETAS:
            raise FiscalAgentError("Filtro de reporte inválido.", 422)
        self.moneda = (self.moneda or "MXN").strip().upper()
        if self.moneda != "MXN":
            if self.tipo_cambio is None or self.tipo_cambio <= 0:
                raise FiscalAgentError(
                    f"Para presentar en {self.moneda} captura el tipo de cambio (pesos por "
                    f"1 {self.moneda}): el sistema no tiene tipos de cambio guardados.", 422)
        else:
            self.tipo_cambio = None


@dataclass
class Fila:
    clave: str
    numero: str
    nombre: str
    nivel: int
    cuenta_id: int | None
    valores: dict[str, Decimal] = field(default_factory=dict)
    tiene_movimiento: bool = False


class Agregador:
    """Suma importes de hojas por sección, a la cuenta y sus ancestros (o por agrupador)."""

    def __init__(self, cuentas: list[CuentaContable], opciones: Opciones) -> None:
        self.cuentas = cuentas
        self.por_id = {c.id: c for c in cuentas}
        self.op = opciones
        self.filas: dict[str, dict[str, Fila]] = {}
        self.totales: dict[str, dict[str, Decimal]] = {}

    def _llaves(self, hoja: CuentaContable) -> list[tuple[str, str, str, int, int | None]]:
        if self.op.agrupar == "agrupador":
            codigo = hoja.codigo_agrupador or "—"
            mayor = codigo.split(".")[0]
            salida = []
            for cod, niv in ((mayor, 1), (codigo, 2)):
                if niv == 2 and cod == mayor:
                    continue
                info = agrupador.obtener(cod)
                salida.append((f"a:{cod}", cod, info.nombre if info else cod, niv, None))
            return salida
        salida = []
        actual: int | None = hoja.id
        while actual is not None:
            c = self.por_id[actual]
            salida.append((f"c:{c.id}", c.numero, c.nombre, c.nivel, c.id))
            actual = c.padre_id
        return salida

    def sumar(self, hoja: CuentaContable, columna: str, valor: Decimal, movimiento: bool) -> str:
        sec = seccion(hoja)
        valor = valor * SIGNO[sec]
        tot = self.totales.setdefault(sec, {})
        tot[columna] = tot.get(columna, CERO) + valor
        filas = self.filas.setdefault(sec, {})
        for clave, numero, nombre, nivel, cid in self._llaves(hoja):
            f = filas.get(clave)
            if f is None:
                f = filas[clave] = Fila(clave, numero, nombre, nivel, cid)
            f.valores[columna] = f.valores.get(columna, CERO) + valor
            f.tiene_movimiento = f.tiene_movimiento or movimiento
        return sec

    def asegurar_todas(self, secciones: tuple[str, ...]) -> None:
        """Con `solo=todas`, también las cuentas sin importes."""
        for c in self.cuentas:
            sec = seccion(c)
            if sec not in secciones:
                continue
            if self.op.agrupar == "agrupador":
                if c.afectable:
                    for clave, numero, nombre, nivel, cid in self._llaves(c):
                        self.filas.setdefault(sec, {}).setdefault(
                            clave, Fila(clave, numero, nombre, nivel, cid))
                continue
            clave = f"c:{c.id}"
            self.filas.setdefault(sec, {}).setdefault(
                clave, Fila(clave, c.numero, c.nombre, c.nivel, c.id))

    def renglones(self, sec: str) -> list[Fila]:
        salida = []
        for f in sorted(self.filas.get(sec, {}).values(), key=lambda f: f.numero):
            if self.op.nivel is not None and f.nivel > self.op.nivel:
                continue
            con_saldo = any(v != 0 for v in f.valores.values())
            if self.op.solo == "con_movimiento" and not f.tiene_movimiento:
                continue
            if self.op.solo == "con_saldo_o_movimiento" and not (con_saldo or f.tiene_movimiento):
                continue
            salida.append(f)
        return salida

    def total(self, sec: str, columna: str) -> Decimal:
        return self.totales.get(sec, {}).get(columna, CERO)


class Presentador:
    """Convierte importes a la moneda pedida y arma las líneas del reporte."""

    def __init__(self, op: Opciones, columnas: list[str]) -> None:
        self.op = op
        self.columnas = columnas
        self.t = ETIQUETAS[op.idioma]
        self.lineas: list[dict[str, Any]] = []

    def importe(self, v: Decimal) -> str:
        if self.op.tipo_cambio:
            v = v / self.op.tipo_cambio
        return f"{v.quantize(UN_CENTAVO):.2f}"

    def _valores(self, valores: dict[str, Decimal]) -> dict[str, str]:
        salida = {}
        for col in self.columnas:
            if col == "variacion":
                v = valores.get("importe", CERO) - valores.get("comparativo", CERO)
            else:
                v = valores.get(col, CERO)
            salida[col] = self.importe(v)
        return salida

    def encabezado(self, clave: str) -> None:
        self.lineas.append({"tipo": "encabezado", "clave": clave, "etiqueta": self.t[clave],
                            "nivel": 0})

    def cuenta(self, f: Fila) -> None:
        self.lineas.append({"tipo": "cuenta", "clave": f.clave, "cuenta_id": f.cuenta_id,
                            "numero": f.numero, "etiqueta": f.nombre, "nivel": f.nivel,
                            "valores": self._valores(f.valores)})

    def total(self, clave: str, valores: dict[str, Decimal], tipo: str = "subtotal",
              etiqueta: str | None = None) -> None:
        self.lineas.append({"tipo": tipo, "clave": clave, "etiqueta": etiqueta or self.t[clave],
                            "nivel": 0, "valores": self._valores(valores)})

    def columnas_dict(self) -> list[dict[str, str]]:
        return [{"clave": c, "etiqueta": self.t[c]} for c in self.columnas]


def _cargar(ag: Agregador, db: Session, cliente: Cliente, desde: date, hasta: date,
            columna: str, secciones: tuple[str, ...], *, saldo_final: bool) -> None:
    hojas = totales_por_cuenta(db, cliente, desde, hasta, incluir_cierre=ag.op.incluir_cierre)
    for cid, t in hojas.items():
        cuenta = ag.por_id.get(cid)
        if cuenta is None or seccion(cuenta) not in secciones:
            continue
        valor = t.final if saldo_final else t.cargos - t.abonos
        ag.sumar(cuenta, columna, valor, t.cargos != 0 or t.abonos != 0)


def _sumas(ag: Agregador, secciones: tuple[str, ...], columnas: list[str],
           signos: tuple[int, ...] | None = None) -> dict[str, Decimal]:
    signos = signos or tuple(1 for _ in secciones)
    return {col: sum((ag.total(s, col) * sg for s, sg in zip(secciones, signos, strict=True)),
                     CERO) for col in columnas}


def _encabezado(op: Opciones, cliente: Cliente, reporte: str, desde: date, hasta: date,
                comparativo: tuple[date, date] | None) -> dict[str, Any]:
    return {
        "reporte": reporte, "titulo": ETIQUETAS[op.idioma][reporte],
        "cliente": {"clave": cliente.clave, "nombre": cliente.nombre, "rfc": cliente.rfc},
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "moneda": op.moneda,
        "tipo_cambio": f"{op.tipo_cambio}" if op.tipo_cambio else None, "idioma": op.idioma,
        "nivel": op.nivel, "agrupar": op.agrupar, "solo": op.solo,
        "incluir_cierre": op.incluir_cierre,
        "comparativo": None if comparativo is None else {
            "tipo": op.comparar, "desde": comparativo[0].isoformat(),
            "hasta": comparativo[1].isoformat()},
    }


def estado_resultados(db: Session, cliente: Cliente, desde: date, hasta: date,
                      op: Opciones) -> dict[str, Any]:
    """Estado de resultados del periodo, con acumulado del ejercicio y comparativo."""
    if desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    op.validar()
    comp = rango_comparativo(desde, hasta, op.comparar)
    columnas = ["importe", "acumulado"] + (["comparativo", "variacion"] if comp else [])
    datos = ["importe", "acumulado"] + (["comparativo"] if comp else [])
    ag = Agregador(catalogo.cuentas(db, cliente), op)
    _cargar(ag, db, cliente, desde, hasta, "importe", SECCIONES_ER, saldo_final=False)
    _cargar(ag, db, cliente, date(hasta.year, 1, 1), hasta, "acumulado", SECCIONES_ER,
            saldo_final=False)
    if comp:
        _cargar(ag, db, cliente, *comp, "comparativo", SECCIONES_ER, saldo_final=False)
    if op.solo == "todas":
        ag.asegurar_todas(SECCIONES_ER)
    p = Presentador(op, columnas)

    def bloque(sec: str) -> None:
        p.encabezado(sec)
        for f in ag.renglones(sec):
            p.cuenta(f)
        p.total(f"total_{sec}", {c: ag.total(sec, c) for c in datos},
                etiqueta=f"{p.t['total']} {p.t[sec].lower()}")

    bloque("ingresos")
    bloque("costo")
    bruta = _sumas(ag, ("ingresos", "costo"), datos, (1, -1))
    p.total("utilidad_bruta", bruta)
    bloque("gastos")
    operacion = {c: bruta[c] - ag.total("gastos", c) for c in datos}
    p.total("utilidad_operacion", operacion)
    bloque("otros_ingresos")
    bloque("otros_gastos")
    antes = {c: operacion[c] + ag.total("otros_ingresos", c) - ag.total("otros_gastos", c)
             for c in datos}
    p.total("utilidad_antes_impuestos", antes)
    bloque("impuestos")
    neta = {c: antes[c] - ag.total("impuestos", c) for c in datos}
    p.total("utilidad_neta", neta, tipo="total")
    return {
        **_encabezado(op, cliente, "estado_resultados", desde, hasta, comp),
        "columnas": p.columnas_dict(), "lineas": p.lineas,
        "resumen": {
            "ingresos": p.importe(ag.total("ingresos", "importe")),
            "costo": p.importe(ag.total("costo", "importe")),
            "utilidad_bruta": p.importe(bruta["importe"]),
            "gastos": p.importe(ag.total("gastos", "importe")),
            "utilidad_operacion": p.importe(operacion["importe"]),
            "utilidad_antes_impuestos": p.importe(antes["importe"]),
            "utilidad_neta": p.importe(neta["importe"]),
            "utilidad_neta_acumulada": p.importe(neta["acumulado"]),
        },
    }


def _resultados_previos(db: Session, cliente: Cliente, ag: Agregador, hasta: date) -> Decimal:
    """Saldo acreedor de las cuentas de resultados al 1 de enero del año de `hasta`."""
    hojas = totales_por_cuenta(db, cliente, date(hasta.year, 1, 1), hasta,
                               incluir_cierre=ag.op.incluir_cierre)
    return sum((-t.inicial for cid, t in hojas.items()
                if cid in ag.por_id and es_de_resultados(ag.por_id[cid])), CERO)


def balance_general(db: Session, cliente: Cliente, hasta: date, op: Opciones,
                    desde: date | None = None) -> dict[str, Any]:
    """Balance general al `hasta`, con comparativo. `desde` sólo define el comparativo."""
    op.validar()
    desde = desde or date(hasta.year, hasta.month, 1)
    if desde > hasta:
        raise FiscalAgentError("'desde' no puede ser posterior a 'hasta'.", 422)
    comp = rango_comparativo(desde, hasta, op.comparar)
    columnas = ["importe"] + (["comparativo", "variacion"] if comp else [])
    datos = ["importe"] + (["comparativo"] if comp else [])
    ag = Agregador(catalogo.cuentas(db, cliente), op)
    todas = (*SECCIONES_BG, *SECCIONES_ER, "orden")
    # Saldo final con el mismo rango que la balanza del periodo: así coinciden al centavo
    # (incluida la regla de `fecha_saldos_iniciales` y la de pólizas de cierre).
    _cargar(ag, db, cliente, desde, hasta, "importe", todas, saldo_final=True)
    if comp:
        _cargar(ag, db, cliente, *comp, "comparativo", todas, saldo_final=True)
    if op.solo == "todas":
        ag.asegurar_todas((*SECCIONES_BG, "orden"))
    p = Presentador(op, columnas)
    t = p.t

    def bloque(sec: str, con_total: bool = True) -> None:
        p.encabezado(sec)
        for f in ag.renglones(sec):
            p.cuenta(f)
        if con_total:
            p.total(f"total_{sec}", {c: ag.total(sec, c) for c in datos},
                    etiqueta=f"{t['total']} {t[sec].lower()}")

    # Saldo (acreedor positivo) de las cuentas de resultados. Lo que traían al 1 de enero
    # es de ejercicios que no se cerraron: se separa para no presentarlo como del ejercicio.
    total_resultados = {c: sum((-ag.total(s, c) * SIGNO[s] for s in SECCIONES_ER), CERO)
                        for c in datos}
    previos = {"importe": _resultados_previos(db, cliente, ag, hasta)}
    if comp:
        previos["comparativo"] = _resultados_previos(db, cliente, ag, comp[1])
    resultado = {c: total_resultados[c] - previos[c] for c in datos}
    bloque("activo_circulante")
    bloque("activo_no_circulante")
    activo = _sumas(ag, ("activo_circulante", "activo_no_circulante"), datos)
    p.total("total_activo", activo, tipo="total")
    bloque("pasivo_corto")
    bloque("pasivo_largo")
    pasivo = _sumas(ag, ("pasivo_corto", "pasivo_largo"), datos)
    p.total("total_pasivo", pasivo, tipo="total")
    bloque("capital", con_total=False)
    if any(previos.values()):
        p.total("sin_cierre", previos)
    p.total("resultado", resultado)
    capital = {c: ag.total("capital", c) + total_resultados[c] for c in datos}
    p.total("total_capital", capital)
    pmc = {c: pasivo[c] + capital[c] for c in datos}
    p.total("pasivo_mas_capital", pmc, tipo="total")
    orden = {c: ag.total("orden", c) for c in datos}
    if ag.renglones("orden"):
        bloque("orden")
    # Las cuentas de orden van en pares (cuenta y contra cuenta) y netean cero; si no, su
    # neto se suma al cuadre para que el balance cuadre exactamente cuando cuadra la balanza.
    diferencia = activo["importe"] - pmc["importe"] + orden["importe"]
    return {
        **_encabezado(op, cliente, "balance_general", desde, hasta, comp),
        "columnas": p.columnas_dict(), "lineas": p.lineas,
        "resumen": {
            "activo": p.importe(activo["importe"]), "pasivo": p.importe(pasivo["importe"]),
            "capital": p.importe(ag.total("capital", "importe")),
            "resultado": p.importe(resultado["importe"]),
            "resultados_sin_cierre": p.importe(previos["importe"]),
            "pasivo_mas_capital": p.importe(pmc["importe"]),
            "cuentas_de_orden": p.importe(orden["importe"]),
        },
        "cuadra": diferencia == 0, "diferencia": p.importe(diferencia),
    }
