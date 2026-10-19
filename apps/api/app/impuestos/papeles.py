"""
Papeles de trabajo de la anual en Excel (P3-06), como "Cálculo anual ISR → Generar archivo" de
Contadigital. Se arman con openpyxl a partir del MISMO diccionario que devuelve
`POST /impuestos/clientes/{clave}/anual` (`app/impuestos/anual.py`): ningún importe se
recalcula aquí, sólo se copia. Los importes van como números (`Decimal`) con formato de
moneda, sin fórmulas, para que el archivo abra igual en cualquier hoja de cálculo.
"""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from app.constants import NOMBRES_MESES

MONEDA = "#,##0.00"
NEGRITA = Font(bold=True)


def _n(v: str | None) -> Decimal | str:
    try:
        return Decimal(v) if v not in (None, "") else ""
    except Exception:  # noqa: BLE001 - texto que no es importe: se escribe tal cual
        return str(v)


def _hoja(libro: Workbook, titulo: str, encabezado: list[str], cabecera: str) -> Worksheet:
    h = libro.create_sheet(titulo)
    h.append([cabecera])
    h["A1"].font = NEGRITA
    h.append([])
    h.append(encabezado)
    for c in h[3]:
        c.font = NEGRITA
    h.column_dimensions["A"].width = 46
    for col in "BCDEFGHIJKLMNOPQ":
        h.column_dimensions[col].width = 16
    return h


def _formato(h: Worksheet, desde_fila: int = 4) -> None:
    for fila in h.iter_rows(min_row=desde_fila):
        for c in fila:
            if isinstance(c.value, Decimal):
                c.number_format = MONEDA


def _mes(m: int) -> str:
    return NOMBRES_MESES.get(m, str(m))


def _calculo(libro: Workbook, r: dict[str, Any], cab: str) -> None:
    h = _hoja(libro, "Cálculo ISR", ["Concepto", "Importe", "Fundamento"], cab)
    for x in r["renglones"]:
        h.append([x["concepto"], _n(x["importe"]), x["fundamento"]])
    _formato(h)


def _notas(libro: Workbook, r: dict[str, Any], cab: str) -> None:
    h = _hoja(libro, "Notas", ["Nota"], cab)
    h.column_dimensions["A"].width = 120
    for n in r.get("notas", []):
        h.append([n])


def _filas_meses(h: Worksheet, meses: list[dict[str, Any]], campos: list[str]) -> None:
    totales = {k: Decimal("0") for k in campos}
    for m in meses:
        h.append([_mes(m["mes"])] + [_n(m[k]) for k in campos])
        for k in campos:
            totales[k] += Decimal(m[k])
    h.append(["Total"] + [totales[k] for k in campos])
    for c in h[h.max_row]:
        c.font = NEGRITA
    _formato(h)


def _pf(libro: Workbook, r: dict[str, Any], cab: str) -> None:
    h = _hoja(libro, "Mes a mes", ["Mes", "Ingresos", "Deducciones", "Base", "ISR causado",
                                   "Retenciones", "Pago determinado", "Pago efectuado"], cab)
    _filas_meses(h, r["meses"], ["ingresos", "deducciones", "base", "isr_causado",
                                 "retenciones", "pago_determinado", "pago_efectuado"])


def _por_cuenta(h: Worksheet, cuentas: list[dict[str, Any]], clases: tuple[str, ...]) -> None:
    filas = [c for c in cuentas if c["clase"] in clases]
    if not filas:
        return
    h.append([])
    h.append(["Detalle por cuenta", "Código", "Clase", "Total"]
             + [_mes(m) for m in range(1, 13)])
    for c in h[h.max_row]:
        c.font = NEGRITA
    for c in filas:
        h.append([f"{c['numero']} {c['nombre']}", c["codigo"], c["clase"], _n(c["total"])]
                 + [_n(v) for v in c["meses"]])
    _formato(h)


def _pm(libro: Workbook, r: dict[str, Any], cab: str) -> None:
    h = _hoja(libro, "Ingresos", ["Mes", "Ingresos"], cab)
    _filas_meses(h, r["meses"], ["ingresos"])
    h.append(["Ingresos adicionales capturados", _n(r["ajustes"]["ingresos_adicionales"])])
    _por_cuenta(h, r["cuentas"], ("ingreso",))
    _formato(h)

    h = _hoja(libro, "Deducciones", ["Mes", "Deducciones autorizadas", "No deducibles"], cab)
    _filas_meses(h, r["meses"], ["deducciones", "no_deducibles"])
    for k, t in (("deduccion_inversiones", "Deducción fiscal de inversiones"),
                 ("deducciones_adicionales", "Deducciones adicionales capturadas"),
                 ("no_deducibles_adicionales", "No deducibles adicionales (se restan)")):
        h.append([t, _n(r["ajustes"][k])])
    _por_cuenta(h, r["cuentas"], ("deduccion", "no_deducible"))
    _formato(h)

    if r["aai"]:
        a = r["aai"]
        h = _hoja(libro, "Ajuste por inflación", ["Mes", "Créditos", "Deudas"], cab)
        for i, (c, d) in enumerate(zip(a["saldos_creditos"], a["saldos_deudas"]), start=1):
            h.append([_mes(i), _n(c), _n(d)])
        h.append(["Saldo promedio anual", _n(a["promedio_creditos"]), _n(a["promedio_deudas"])])
        f = a["factor"] or {}
        h.append([])
        h.append([f"INPC {f.get('mes_reciente', '')}", _n(f.get("inpc_reciente"))])
        h.append([f"INPC {f.get('mes_antiguo', '')}", _n(f.get("inpc_antiguo"))])
        h.append(["Factor de ajuste anual (Art. 44 fr. III)", a["factor_ajuste"]])
        h.append(["Ajuste anual por inflación acumulable", _n(a["acumulable"])])
        h.append(["Ajuste anual por inflación deducible", _n(a["deducible"])])
        h.append([f"Saldos: {r['origen_saldos']}"])
        _formato(h)

    if r["tipo"] == "pm":
        c = r["coeficiente"]
        h = _hoja(libro, "Coeficiente", ["Concepto", "Importe"], cab)
        h.append(["Coeficiente aplicado en los pagos del ejercicio", c["aplicado"]])
        h.append(["Origen", c["origen"]])
        h.append(["Utilidad fiscal del ejercicio", _n(c["utilidad_fiscal"])])
        h.append(["Anticipos a miembros (Art. 94 fr. II)", _n(c["anticipos_miembros"])])
        h.append(["Ingresos nominales del ejercicio", _n(c["ingresos_nominales"])])
        h.append(["Coeficiente para el ejercicio siguiente (Art. 14 fr. I)", c["siguiente"]])
        _formato(h)

    p = r["ptu"]
    h = _hoja(libro, "PTU", ["Concepto", "Importe"], cab)
    h.append(["Utilidad antes de PTU (ingresos − deducciones)", _n(p["utilidad_antes_ptu"])])
    h.append(["(−) No deducibles Art. 28 fr. XXX (Art. 9 cuarto párrafo)",
              _n(p["no_deducibles_art28_xxx"]), p["origen_art28_xxx"]])
    h.append(["Renta gravable (Art. 9, sin PTU ni pérdidas)", _n(p["renta_gravable"])])
    h.append(["Porcentaje", p["porcentaje"], p["fundamento"]])
    h.append(["PTU a repartir", _n(p["a_repartir"])])
    h.append(["PTU pagada en el ejercicio", _n(p["pagada_en_el_ejercicio"])])
    _formato(h)

    h = _hoja(libro, "Pérdidas", ["Ejercicio", "Remanente inicial", "Actualizada",
                                  "Actualizada a", "Aplicada", "Remanente final", "Nota"], cab)
    for x in r["perdidas"]:
        h.append([x["ejercicio"], _n(x["remanente_inicial"]), _n(x["actualizada"]),
                  x["actualizada_a"], _n(x["aplicada"]), _n(x["remanente_final"]), x["nota"]])
    _formato(h)

    campos = ["ingresos_acumulados", "deducciones_acumuladas", "utilidad_estimada",
              "ptu_disminuida", "estimulos", "perdidas", "base", "isr_causado",
              "pagos_anteriores", "retenciones", "pago_determinado", "pago_efectuado"]
    h = _hoja(libro, "Pagos provisionales",
              ["Mes", "Ingresos acumulados", "Deducciones acumuladas", "Utilidad estimada",
               "PTU disminuida", "Estímulos", "Pérdidas", "Base", "ISR causado",
               "Pagos anteriores", "Retenciones", "Pago determinado", "Pago efectuado"], cab)
    for x in r["pagos_provisionales"]:
        h.append([_mes(x["mes"])] + [_n(x[k]) for k in campos])
    _formato(h)


def papeles_xlsx(r: dict[str, Any], nombre: str) -> bytes:
    """El libro de papeles de trabajo de la anual."""
    libro = Workbook()
    libro.remove(libro.active)
    cab = f"Papeles de trabajo de la anual {r['anio']} · {nombre} · régimen {r['regimen']}"
    _calculo(libro, r, cab)
    if r["tipo"] == "pf":
        _pf(libro, r, cab)
    else:
        _pm(libro, r, cab)
    _notas(libro, r, cab)
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()
