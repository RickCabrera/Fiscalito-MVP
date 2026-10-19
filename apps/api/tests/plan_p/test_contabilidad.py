"""
P2-01 a P2-04: catálogo, reglas, pólizas automáticas y manuales, balanza y auxiliares.

"Listo cuando" medidos aquí:
- P2-01: cada cuenta del agrupador cita su fuente; un cliente agrega subcuentas.
- P2-02: cambiar una regla cambia la cuenta de las pólizas nuevas.
- P2-03: un mes de la bóveda genera sus pólizas una sola vez, Σ cargos = Σ abonos, y una
  póliza manual se guarda y aparece en la balanza.
- P2-04: el saldo final de un mes es el inicial del siguiente y el detalle cuadra con la
  balanza.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.boveda_cfdi import servicio
from app.contabilidad import agrupador, balanza, catalogo, config, generador, polizas
from app.exceptions import FiscalAgentError
from app.integraciones.almacenamiento import AlmacenamientoMemoria
from app.modelos.cfdi import Comprobante
from app.modelos.contabilidad import CuentaContable, MovimientoPoliza, Poliza
from app.modelos.nucleo import Cliente
from app.tenancy import asegurar_usuario
from tests.plan_p.conta_sintetico import (
    RFC_CLIENTE,
    RFC_PROVEEDOR,
    Concepto,
    factura,
    nomina,
    pago20,
    uuid_n,
)

MARZO = (date(2026, 3, 1), date(2026, 3, 31))
ABRIL = (date(2026, 4, 1), date(2026, 4, 30))


@pytest.fixture
def cliente(db_sesion):
    asegurar_usuario(db_sesion, "uid-conta")
    c = Cliente(despacho_id="uid-conta", clave="taller", nombre="Taller", rfc=RFC_CLIENTE)
    db_sesion.add(c)
    db_sesion.flush()
    catalogo.sembrar_base(db_sesion, c)
    return c


@pytest.fixture
def almacen():
    return AlmacenamientoMemoria()


def subir(db, cliente, almacen, *xmls: bytes) -> None:
    rep = servicio.importar(db, cliente, [(f"{i}.xml", io.BytesIO(x)) for i, x in
                                          enumerate(xmls)], almacen=almacen)
    assert not rep.rechazados, rep.rechazados


def poliza_de(db, cliente, uuid: str) -> Poliza:
    return db.scalar(select(Poliza).where(Poliza.cliente_id == cliente.id,
                                          Poliza.clave_origen == f"cfdi:{uuid}"))


def movs(db, poliza: Poliza) -> dict[str, tuple[Decimal, Decimal]]:
    """cuenta → (Σ cargo, Σ abono) de la póliza."""
    salida: dict[str, tuple[Decimal, Decimal]] = {}
    for m, c in polizas.movimientos(db, poliza.id):
        car, abo = salida.get(c.numero, (Decimal(0), Decimal(0)))
        salida[c.numero] = (car + m.cargo, abo + m.abono)
    return salida


def cuadra(db, poliza: Poliza) -> bool:
    m = movs(db, poliza)
    return sum(v[0] for v in m.values()) == sum(v[1] for v in m.values())


def renglon(bal: dict, numero: str) -> dict:
    return next(r for r in bal["renglones"] if r["numero"] == numero)


# ── P2-01: agrupador y catálogo ──


def test_agrupador_completo_y_con_fuente():
    cat = agrupador.catalogo()
    assert len(cat) == 1080
    encabezado = agrupador.RUTA_CSV.read_text(encoding="utf-8").splitlines()[:6]
    assert any("sat.gob.mx/esquemas/ContabilidadE" in linea for linea in encabezado)
    assert "Anexo 24" in agrupador.FUENTE
    assert cat["118.01"].nombre == "IVA acreditable pagado"
    assert cat["209.01"].nombre == "IVA trasladado no cobrado"
    assert (cat["171"].naturaleza, cat["402"].naturaleza) == ("acreedora", "deudora")
    assert (cat["704"].naturaleza, cat["899.02"].naturaleza) == ("acreedora", "acreedora")
    assert cat["100"].nivel == 0 and not cat["100"].asignable
    # Lo que no se pudo verificar se dice, no se inventa.
    assert cat["402.05"].nombre == agrupador.POR_CONFIRMAR
    assert all(c.nombre for c in cat.values())


def test_catalogo_base_cuadra_con_el_agrupador(db_sesion, cliente):
    cuentas = catalogo.cuentas(db_sesion, cliente)
    assert len(cuentas) == len(catalogo.CATALOGO_BASE)
    por_id = {c.id: c for c in cuentas}
    for c in cuentas:
        codigo = agrupador.obtener(c.codigo_agrupador)
        assert codigo is not None and codigo.asignable, c.numero
        assert c.naturaleza == codigo.naturaleza and c.tipo == codigo.tipo, c.numero
        if c.nivel <= 2:  # nivel 1-2: el número ES el código agrupador
            assert c.numero == c.codigo_agrupador and codigo.nivel == c.nivel
        padre = por_id.get(c.padre_id) if c.padre_id else None
        assert c.nivel == (padre.nivel + 1 if padre else 1)
        if padre:
            assert not padre.afectable and c.numero.startswith(padre.numero + ".")
    # Toda cuenta por default de la configuración existe y es afectable.
    numeros = {c.numero: c for c in cuentas}
    for rol, (default, _d) in config.ROLES.items():
        assert numeros[default].afectable, rol
    assert catalogo.sembrar_base(db_sesion, cliente) == 0  # idempotente


def test_subcuentas_y_validaciones(db_sesion, cliente):
    bancos = catalogo.por_numero(db_sesion, cliente)["102.01"]
    sub = catalogo.crear(db_sesion, cliente, numero="102.01.02", nombre="BBVA 1234",
                         codigo_agrupador="102.01", padre_id=bancos.id)
    assert (sub.nivel, sub.naturaleza, sub.tipo, sub.afectable) == (3, "deudora", "activo", True)
    with pytest.raises(FiscalAgentError, match="Nivel incoherente"):
        catalogo.crear(db_sesion, cliente, numero="102.01.03", nombre="X",
                       codigo_agrupador="102.01", padre_id=bancos.id, nivel=2)
    with pytest.raises(FiscalAgentError, match="no existe en el Anexo"):
        catalogo.crear(db_sesion, cliente, numero="999", nombre="X", codigo_agrupador="999.99")
    with pytest.raises(FiscalAgentError, match="encabezado"):
        catalogo.crear(db_sesion, cliente, numero="999", nombre="X", codigo_agrupador="100")
    with pytest.raises(FiscalAgentError) as e:
        catalogo.crear(db_sesion, cliente, numero="X", nombre="X", codigo_agrupador="101",
                       padre_id=999999)
    assert e.value.status_code == 404
    # Subcuenta a una afectable la vuelve acumulativa.
    caja = catalogo.por_numero(db_sesion, cliente)["101.01"]
    catalogo.crear(db_sesion, cliente, numero="101.01.01", nombre="Caja chica",
                   codigo_agrupador="101.01", padre_id=caja.id)
    assert not caja.afectable
    with pytest.raises(FiscalAgentError, match="subcuentas"):
        catalogo.borrar(db_sesion, cliente, bancos.id)
    with pytest.raises(FiscalAgentError, match="configuración"):
        catalogo.borrar(db_sesion, cliente, catalogo.por_numero(db_sesion, cliente)["105.01"].id)
    catalogo.borrar(db_sesion, cliente, sub.id)


def test_no_borrar_cuenta_con_movimientos_ni_subcuenta_a_cuenta_con_movimientos(
        db_sesion, cliente):
    c = catalogo.por_numero(db_sesion, cliente)
    nueva = catalogo.crear(db_sesion, cliente, numero="601.84.01", nombre="Varios",
                           codigo_agrupador="601.84", padre_id=c["601.84"].id)
    polizas.crear_manual(db_sesion, cliente, tipo="diario", fecha=date(2026, 3, 5),
                         concepto="x", uid="u", movimientos=[
                             polizas.MovimientoEntrada(nueva.id, cargo=Decimal("10")),
                             polizas.MovimientoEntrada(c["101.01"].id, abono=Decimal("10"))])
    with pytest.raises(FiscalAgentError, match="movimientos"):
        catalogo.borrar(db_sesion, cliente, nueva.id)
    with pytest.raises(FiscalAgentError, match="movimientos o saldo"):
        catalogo.crear(db_sesion, cliente, numero="601.84.01.01", nombre="Y",
                       codigo_agrupador="601.84", padre_id=nueva.id)


# ── P2-03: esquemas de asiento ──


def test_ingreso_ppd_y_pago_mueve_iva_pendiente_a_cobrado(db_sesion, cliente, almacen):
    fac, pag = uuid_n(1, "F1000000"), uuid_n(2, "P1000000")
    subir(db_sesion, cliente, almacen, factura(fac, metodo="PPD", forma="99"),
          pago20(pag, [(fac, "1160.00", "580.00")], fecha="2026-04-05T12:00:00"))
    generador.generar(db_sesion, cliente, *MARZO)
    p = poliza_de(db_sesion, cliente, fac)
    assert p.tipo == "diario" and cuadra(db_sesion, p)
    assert movs(db_sesion, p) == {
        "105.01": (Decimal("1160.00"), 0), "401.01": (0, Decimal("1000.00")),
        "209.01": (0, Decimal("160.00"))}
    generador.generar(db_sesion, cliente, *ABRIL)
    pp = poliza_de(db_sesion, cliente, pag)
    assert pp.tipo == "ingreso" and cuadra(db_sesion, pp)
    # Pago del 50 %: 580 a bancos contra clientes y la mitad del IVA pasa a cobrado.
    assert movs(db_sesion, pp) == {
        "102.01.01": (Decimal("580.00"), 0), "105.01": (0, Decimal("580.00")),
        "209.01": (Decimal("80.00"), 0), "208.01": (0, Decimal("80.00"))}


def test_egreso_ppd_pago_mueve_iva_acreditable_pendiente_a_pagado(db_sesion, cliente, almacen):
    fac, pag = uuid_n(1, "F2000000"), uuid_n(2, "P2000000")
    subir(db_sesion, cliente, almacen,
          factura(fac, emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE, metodo="PPD", forma="99"),
          pago20(pag, [(fac, "1160.00", "1160.00")], emisor=RFC_PROVEEDOR,
                 receptor=RFC_CLIENTE, fecha="2026-03-20T12:00:00"))
    generador.generar(db_sesion, cliente, *MARZO)
    assert movs(db_sesion, poliza_de(db_sesion, cliente, fac)) == {
        "601.84": (Decimal("1000.00"), 0), "119.01": (Decimal("160.00"), 0),
        "201.01": (0, Decimal("1160.00"))}
    pp = poliza_de(db_sesion, cliente, pag)
    assert pp.tipo == "egreso"
    assert movs(db_sesion, pp) == {
        "201.01": (Decimal("1160.00"), 0), "102.01.01": (0, Decimal("1160.00")),
        "118.01": (Decimal("160.00"), 0), "119.01": (0, Decimal("160.00"))}
    bal = balanza.balanza(db_sesion, cliente, *MARZO)
    assert renglon(bal, "119.01")["saldo_final"] == "0.00"
    assert renglon(bal, "118.01")["saldo_final"] == "160.00"


def test_pue_con_retenciones_y_cobro_en_la_misma_poliza(db_sesion, cliente, almacen):
    # Honorarios cobrados a una persona moral: nos retiene 10 % ISR y 2/3 del IVA.
    fac = uuid_n(3, "F3000000")
    subir(db_sesion, cliente, almacen, factura(fac, conceptos=[
        Concepto("10000.00", ret_isr="1000.00", ret_iva="1066.67")]))
    generador.generar(db_sesion, cliente, *MARZO)
    p = poliza_de(db_sesion, cliente, fac)
    assert p.tipo == "ingreso" and p.diferencia == 0
    neto = Decimal("10000.00") + Decimal("1600.00") - Decimal("1000.00") - Decimal("1066.67")
    assert movs(db_sesion, p) == {
        "105.01": (neto, neto), "401.01": (0, Decimal("10000.00")),
        "208.01": (0, Decimal("1600.00")), "113.01": (Decimal("1066.67"), 0),
        "113.02": (Decimal("1000.00"), 0), "102.01.01": (neto, 0)}


def test_egreso_con_retenciones_y_arrendamiento(db_sesion, cliente, almacen):
    fac = uuid_n(4, "F4000000")
    subir(db_sesion, cliente, almacen, factura(
        fac, emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE, metodo="PPD", forma="99",
        conceptos=[Concepto("5000.00", clave="80131500", descripcion="Renta local",
                            ret_isr="500.00", ret_iva="533.33")]))
    generador.generar(db_sesion, cliente, *MARZO)
    m = movs(db_sesion, poliza_de(db_sesion, cliente, fac))
    assert m["216.03"] == (0, Decimal("500.00"))  # ISR retenido por arrendamiento
    assert m["216.10"] == (0, Decimal("533.33"))
    assert m["119.01"] == (Decimal("800.00"), 0)
    assert m["201.01"] == (0, Decimal("5000.00") + Decimal("800.00") - Decimal("1033.33"))


def test_nota_de_credito_invierte_y_va_a_devoluciones(db_sesion, cliente, almacen):
    nc = uuid_n(5, "E5000000")
    subir(db_sesion, cliente, almacen, factura(nc, tipo="E", metodo="PUE", forma="03"))
    generador.generar(db_sesion, cliente, *MARZO)
    p = poliza_de(db_sesion, cliente, nc)
    assert p.tipo == "egreso"
    assert movs(db_sesion, p) == {
        "105.01": (Decimal("1160.00"), Decimal("1160.00")), "402.01": (Decimal("1000.00"), 0),
        "208.01": (Decimal("160.00"), 0), "102.01.01": (0, Decimal("1160.00"))}


def test_nomina_emitida(db_sesion, cliente, almacen):
    n = uuid_n(6, "N6000000")
    subir(db_sesion, cliente, almacen, nomina(n, otros_pagos="50.00"))
    generador.generar(db_sesion, cliente, *MARZO)
    p = poliza_de(db_sesion, cliente, n)
    assert p.tipo == "egreso" and p.diferencia == 0 and cuadra(db_sesion, p)
    assert movs(db_sesion, p) == {
        "601.01": (Decimal("10000.00"), 0), "110.01": (Decimal("50.00"), 0),
        "216.01": (0, Decimal("1000.00")), "216.11": (0, Decimal("250.00")),
        "102.01.01": (0, Decimal("8800.00"))}


def test_ingresos_exentos_y_tasa_cero_se_separan(db_sesion, cliente, almacen):
    fac = uuid_n(7, "F7000000")
    subir(db_sesion, cliente, almacen, factura(fac, metodo="PPD", forma="99", conceptos=[
        Concepto("100.00"), Concepto("200.00", tasa="0.000000"), Concepto("300.00", tasa="")]))
    generador.generar(db_sesion, cliente, *MARZO)
    m = movs(db_sesion, poliza_de(db_sesion, cliente, fac))
    assert (m["401.01"], m["401.04"], m["401.07"]) == (
        (0, Decimal("100.00")), (0, Decimal("200.00")), (0, Decimal("300.00")))


def test_moneda_extranjera_se_convierte(db_sesion, cliente, almacen):
    fac = uuid_n(8, "F8000000")
    subir(db_sesion, cliente, almacen, factura(fac, metodo="PPD", forma="99", moneda="USD",
                                               tipo_cambio="18.50"))
    generador.generar(db_sesion, cliente, *MARZO)
    m = movs(db_sesion, poliza_de(db_sesion, cliente, fac))
    assert m["105.01"] == (Decimal("21460.00"), 0) and m["401.01"] == (0, Decimal("18500.00"))


# ── P2-02: reglas y configuración ──


def test_reglas_cambian_la_cuenta_de_polizas_nuevas(db_sesion, cliente, almacen):
    def recibida(n: int, **kw) -> bytes:
        return factura(uuid_n(n, "R0000000"), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                       metodo="PPD", forma="99", **kw)

    c = catalogo.por_numero(db_sesion, cliente)
    subir(db_sesion, cliente, almacen, recibida(1, conceptos=[Concepto(clave="15101514",
                                                                       descripcion="Gasolina")]))
    generador.generar(db_sesion, cliente, *MARZO)
    assert "601.84" in movs(db_sesion, poliza_de(db_sesion, cliente, uuid_n(1, "R0000000")))

    config.crear_regla(db_sesion, cliente, criterio="prefijo", valor="1510", prioridad=10,
                       cuenta_numero="601.48")
    config.crear_regla(db_sesion, cliente, criterio="rfc", valor=RFC_PROVEEDOR, prioridad=50,
                       cuenta_numero="601.56")
    config.crear_regla(db_sesion, cliente, criterio="descripcion", valor="papel",
                       prioridad=5, cuenta_numero="601.55")
    subir(db_sesion, cliente, almacen,
          recibida(2, conceptos=[Concepto(clave="15101514", descripcion="Gasolina")]),
          recibida(3, conceptos=[Concepto(clave="72101500", descripcion="Reparación")]),
          recibida(4, conceptos=[Concepto(clave="14111500", descripcion="PAPEL bond")]),
          recibida(5, uso="S01"), recibida(6, uso="I04"))
    r = generador.generar(db_sesion, cliente, *MARZO)
    assert (r.generadas, r.ya_existian) == (5, 1)
    cuenta = lambda n: set(movs(db_sesion, poliza_de(db_sesion, cliente, uuid_n(n, "R0000000"))))  # noqa: E731
    # La póliza vieja no cambia; las nuevas siguen las reglas por prioridad.
    assert "601.84" in cuenta(1)
    assert "601.48" in cuenta(2) and "601.56" in cuenta(3) and "601.55" in cuenta(4)
    # S01 → no deducible con todo y su IVA; UsoCFDI I04 → equipo de cómputo (activo).
    # La regla por RFC gana a S01 y a UsoCFDI de inversión (va por prioridad, antes que los
    # defaults): el gasto va a 601.56 y su IVA sigue siendo acreditable.
    m5 = movs(db_sesion, poliza_de(db_sesion, cliente, uuid_n(5, "R0000000")))
    assert m5["601.56"] == (Decimal("1000.00"), 0) and m5["119.01"] == (Decimal("160.00"), 0)
    assert "601.56" in cuenta(6)
    assert c["601.48"].afectable


def test_uso_de_inversion_sin_regla_va_a_activo(db_sesion, cliente, almacen):
    subir(db_sesion, cliente, almacen, factura(
        uuid_n(1, "V0000000"), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE, metodo="PPD",
        forma="99", uso="I04"))
    generador.generar(db_sesion, cliente, *MARZO)
    assert movs(db_sesion, poliza_de(db_sesion, cliente, uuid_n(1, "V0000000")))["156.01"] == (
        Decimal("1000.00"), 0)


def test_config_tope_activo_s01_y_cuentas(db_sesion, cliente, almacen):
    config.guardar(db_sesion, cliente, {"tope_activo": "5000", "cuentas": {"gastos": "601.56"}})
    subir(db_sesion, cliente, almacen,
          factura(uuid_n(1, "T0000000"), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                  metodo="PPD", forma="99", conceptos=[Concepto("8000.00")]),
          factura(uuid_n(2, "T0000000"), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                  metodo="PPD", forma="99", conceptos=[Concepto("100.00")]),
          factura(uuid_n(3, "T0000000"), emisor=RFC_PROVEEDOR, receptor=RFC_CLIENTE,
                  metodo="PPD", forma="99", uso="S01"))
    generador.generar(db_sesion, cliente, *MARZO)
    assert "160.01" in movs(db_sesion, poliza_de(db_sesion, cliente, uuid_n(1, "T0000000")))
    assert "601.56" in movs(db_sesion, poliza_de(db_sesion, cliente, uuid_n(2, "T0000000")))
    m3 = movs(db_sesion, poliza_de(db_sesion, cliente, uuid_n(3, "T0000000")))
    assert m3 == {"601.83": (Decimal("1160.00"), 0), "201.01": (0, Decimal("1160.00"))}
    with pytest.raises(FiscalAgentError, match="no existe"):
        config.guardar(db_sesion, cliente, {"cuentas": {"gastos": "999"}})
    with pytest.raises(FiscalAgentError, match="subcuentas"):
        config.guardar(db_sesion, cliente, {"cuentas": {"gastos": "601"}})


def test_automatica_apagada_omite(db_sesion, cliente, almacen):
    config.guardar(db_sesion, cliente, {"automatica_ingresos": False})
    subir(db_sesion, cliente, almacen, factura(uuid_n(1, "O0000000")))
    r = generador.generar(db_sesion, cliente, *MARZO)
    assert (r.generadas, r.omitidas) == (0, 1)


# ── P2-03: generación masiva ──


def _mes_completo(db, cliente, almacen) -> None:
    xmls = []
    for n in range(30):
        emitido = n % 3 != 0
        xmls.append(factura(
            uuid_n(n, "M0000000"), emisor=RFC_CLIENTE if emitido else RFC_PROVEEDOR,
            receptor="COM010101BB2" if emitido else RFC_CLIENTE,
            fecha=f"2026-03-{(n % 28) + 1:02d}T10:00:00",
            metodo="PUE" if n % 2 else "PPD", forma="03" if n % 2 else "99",
            conceptos=[Concepto(f"{100 + n * 37}.{n:02d}"), Concepto("12.34", tasa="")]))
    xmls.append(nomina(uuid_n(99, "M0000000")))
    subir(db, cliente, almacen, *xmls)


def test_generar_dos_veces_no_duplica_y_todo_cuadra(db_sesion, cliente, almacen):
    _mes_completo(db_sesion, cliente, almacen)
    r1 = generador.generar(db_sesion, cliente, *MARZO)
    assert (r1.generadas, r1.errores) == (31, [])
    r2 = generador.generar(db_sesion, cliente, *MARZO)
    assert (r2.generadas, r2.ya_existian) == (0, 31)
    assert db_sesion.scalar(select(func.count(Poliza.id))) == 31
    for p in db_sesion.scalars(select(Poliza)):
        assert cuadra(db_sesion, p), polizas.folio(p)
        assert p.diferencia == 0
    car, abo = db_sesion.execute(select(func.sum(MovimientoPoliza.cargo),
                                        func.sum(MovimientoPoliza.abono))).one()
    assert car == abo
    # Folios consecutivos por tipo y mes.
    for tipo in ("ingreso", "egreso", "diario"):
        nums = sorted(db_sesion.scalars(select(Poliza.numero).where(Poliza.tipo == tipo)))
        assert nums == list(range(1, len(nums) + 1))
    bal = balanza.balanza(db_sesion, cliente, *MARZO)
    assert bal["cuadra"] and bal["totales"]["cargos"] == bal["totales"]["abonos"]


def test_trabajo_en_segundo_plano_es_idempotente(db_sesion, cliente, almacen):
    from app.contabilidad import trabajos as tr

    _mes_completo(db_sesion, cliente, almacen)
    t = tr.encolar_generacion(db_sesion, cliente, *MARZO, uid="u")
    assert tr.generar_polizas(db_sesion, t)["generadas"] == 31
    assert tr.generar_polizas(db_sesion, t)["generadas"] == 0


def test_cancelado_cancela_o_revierte(db_sesion, cliente, almacen):
    a, b = uuid_n(1, "C0000000"), uuid_n(2, "C0000000")
    subir(db_sesion, cliente, almacen, factura(a, metodo="PPD", forma="99"),
          factura(b, metodo="PPD", forma="99"))
    generador.generar(db_sesion, cliente, *MARZO)
    comp_a = db_sesion.scalar(select(Comprobante).where(Comprobante.uuid == a))
    comp_a.estatus_sat = "cancelado"
    assert polizas.cancelar_por_cfdi(db_sesion, comp_a) == "cancelada"
    assert poliza_de(db_sesion, cliente, a).estado == "cancelada"
    # Mes cerrado: no se toca, se revierte con fecha de hoy (abril).
    polizas.cerrar_periodo(db_sesion, cliente, 2026, 3, "u")
    comp_b = db_sesion.scalar(select(Comprobante).where(Comprobante.uuid == b))
    comp_b.estatus_sat = "cancelado"
    assert polizas.cancelar_por_cfdi(db_sesion, comp_b, date(2026, 4, 2)) == "reversa"
    assert polizas.cancelar_por_cfdi(db_sesion, comp_b, date(2026, 4, 2)) == "reversa"
    assert poliza_de(db_sesion, cliente, b).estado == "activa"
    marzo = balanza.balanza(db_sesion, cliente, *MARZO)
    assert renglon(marzo, "105.01")["saldo_final"] == "1160.00"  # sólo B; A cancelada
    abril = balanza.balanza(db_sesion, cliente, *ABRIL)
    assert renglon(abril, "105.01")["saldo_final"] == "0.00"
    assert abril["cuadra"]
    # Un cancelado no se vuelve a generar.
    assert generador.generar(db_sesion, cliente, *ABRIL).generadas == 0


def test_generar_cancela_las_polizas_de_cfdi_cancelados(db_sesion, cliente, almacen):
    a = uuid_n(1, "G0000000")
    subir(db_sesion, cliente, almacen, factura(a))
    generador.generar(db_sesion, cliente, *MARZO)
    comp = db_sesion.scalar(select(Comprobante).where(Comprobante.uuid == a))
    comp.estatus_sat = "cancelado"  # marcado por fuera (p. ej. antes de P2-03)
    r = generador.generar(db_sesion, cliente, *MARZO)
    assert (r.canceladas, r.generadas) == (1, 0)
    assert poliza_de(db_sesion, cliente, a).estado == "cancelada"
    assert balanza.balanza(db_sesion, cliente, *MARZO)["renglones"] == []


def test_estatus_sat_cancela_la_poliza(db_sesion, cliente, almacen):
    from app.sat_verificacion import estatus

    a = uuid_n(1, "S0000000")
    subir(db_sesion, cliente, almacen, factura(a))
    generador.generar(db_sesion, cliente, *MARZO)
    comp = db_sesion.scalar(select(Comprobante).where(Comprobante.uuid == a))

    class Est:
        encontrado, resumen, en_proceso_de_cancelacion = True, "cancelado", False
        codigo_estatus = estado = es_cancelable = estatus_cancelacion = "x"
        validacion_efos = ""

    estatus._aplicar(db_sesion, comp, Est(), comp.fecha, estatus.ResultadoVerificacion())  # type: ignore[arg-type]
    assert poliza_de(db_sesion, cliente, a).estado == "cancelada"


# ── pólizas manuales ──


def test_poliza_manual_valida_y_aparece_en_balanza(db_sesion, cliente):
    c = catalogo.por_numero(db_sesion, cliente)
    M = polizas.MovimientoEntrada
    with pytest.raises(FiscalAgentError, match="no cuadra"):
        polizas.crear_manual(db_sesion, cliente, tipo="diario", fecha=date(2026, 3, 1),
                             concepto="x", uid="u", movimientos=[
                                 M(c["301.01"].id, abono=Decimal("100")),
                                 M(c["102.01.01"].id, cargo=Decimal("90"))])
    with pytest.raises(FiscalAgentError, match="subcuentas"):
        polizas.crear_manual(db_sesion, cliente, tipo="diario", fecha=date(2026, 3, 1),
                             concepto="x", uid="u", movimientos=[
                                 M(c["301"].id, abono=Decimal("100")),
                                 M(c["102.01.01"].id, cargo=Decimal("100"))])
    with pytest.raises(FiscalAgentError, match="uno de los dos"):
        polizas.crear_manual(db_sesion, cliente, tipo="diario", fecha=date(2026, 3, 1),
                             concepto="x", uid="u", movimientos=[
                                 M(c["301.01"].id, cargo=Decimal("1"), abono=Decimal("1")),
                                 M(c["102.01.01"].id, cargo=Decimal("0"))])
    p = polizas.crear_manual(db_sesion, cliente, tipo="diario", fecha=date(2026, 3, 1),
                             concepto="Aportación", uid="u", movimientos=[
                                 M(c["102.01.01"].id, cargo=Decimal("50000")),
                                 M(c["301.01"].id, abono=Decimal("50000"))])
    assert polizas.folio(p) == "D-2026-03-0001" and p.origen == "manual"
    bal = balanza.balanza(db_sesion, cliente, *MARZO)
    assert renglon(bal, "301.01")["final_acreedor"] == "50000.00"
    assert renglon(bal, "102")["final_deudor"] == "50000.00"  # sube a los ancestros
    # Edición y cancelación; periodo cerrado bloquea.
    polizas.editar(db_sesion, cliente, p.id, fecha=None, concepto="Aportación inicial",
                   movimientos=[M(c["102.01.01"].id, cargo=Decimal("60000")),
                                M(c["301.01"].id, abono=Decimal("60000"))])
    assert renglon(balanza.balanza(db_sesion, cliente, *MARZO), "301.01")["abonos"] == "60000.00"
    polizas.cerrar_periodo(db_sesion, cliente, 2026, 3, "u")
    with pytest.raises(FiscalAgentError, match="cerrado"):
        polizas.cancelar(db_sesion, cliente, p.id, "")
    with pytest.raises(FiscalAgentError, match="cerrado"):
        polizas.crear_manual(db_sesion, cliente, tipo="diario", fecha=date(2026, 3, 2),
                             concepto="x", uid="u", movimientos=[
                                 M(c["102.01.01"].id, cargo=Decimal("1")),
                                 M(c["301.01"].id, abono=Decimal("1"))])
    polizas.abrir_periodo(db_sesion, cliente, 2026, 3)
    polizas.cancelar(db_sesion, cliente, p.id, "error de captura")
    assert balanza.balanza(db_sesion, cliente, *MARZO)["renglones"] == []


# ── P2-04: balanza y auxiliar ──


def test_saldo_final_de_un_mes_es_el_inicial_del_siguiente(db_sesion, cliente, almacen):
    c = catalogo.por_numero(db_sesion, cliente)
    balanza.guardar_saldos_iniciales(db_sesion, cliente, [
        (c["102.01.01"].id, Decimal("1000"), Decimal("0")),
        (c["301.01"].id, Decimal("0"), Decimal("1000"))])
    _mes_completo(db_sesion, cliente, almacen)
    fac, pag = uuid_n(1, "Z0000000"), uuid_n(2, "Z0000000")
    subir(db_sesion, cliente, almacen, factura(fac, metodo="PPD", forma="99"),
          pago20(pag, [(fac, "1160.00", "1160.00")], fecha="2026-04-10T10:00:00"))
    generador.generar(db_sesion, cliente, date(2026, 3, 1), date(2026, 4, 30))
    marzo = balanza.balanza(db_sesion, cliente, *MARZO, solo="todas")
    abril = balanza.balanza(db_sesion, cliente, *ABRIL, solo="todas")
    assert marzo["cuadra"] and abril["cuadra"]
    for r_mar in marzo["renglones"]:
        r_abr = renglon(abril, r_mar["numero"])
        assert r_mar["saldo_final"] == r_abr["saldo_inicial"], r_mar["numero"]
    assert renglon(marzo, "102.01.01")["saldo_inicial"] == "1000.00"
    # Rango de dos meses = inicial de marzo + movimientos de ambos.
    rango = balanza.balanza(db_sesion, cliente, date(2026, 3, 1), date(2026, 4, 30),
                            solo="todas")
    for r in rango["renglones"]:
        assert r["saldo_final"] == renglon(abril, r["numero"])["saldo_final"]
    # Nivel 1: los totales no cambian.
    n1 = balanza.balanza(db_sesion, cliente, *MARZO, nivel=1)
    assert all(r["nivel"] == 1 for r in n1["renglones"]) and n1["totales"] == marzo["totales"]


def test_auxiliar_cuadra_con_la_balanza(db_sesion, cliente, almacen):
    _mes_completo(db_sesion, cliente, almacen)
    generador.generar(db_sesion, cliente, *MARZO)
    bal = balanza.balanza(db_sesion, cliente, *MARZO)
    for numero in ("105.01", "105", "401.01", "102.01.01", "209.01", "119.01"):
        r = renglon(bal, numero)
        aux = balanza.auxiliar(db_sesion, cliente, r["cuenta_id"], *MARZO)
        assert (aux["saldo_inicial"], aux["cargos"], aux["abonos"], aux["saldo_final"]) == (
            r["saldo_inicial"], r["cargos"], r["abonos"], r["saldo_final"]), numero
        assert sum(Decimal(m["cargo"]) for m in aux["movimientos"]) == Decimal(r["cargos"])
        if aux["movimientos"]:
            assert aux["movimientos"][-1]["saldo"] == r["saldo_final"]
            assert aux["movimientos"][0]["xml_disponible"]


# ── API y multi-tenant ──


@pytest.fixture
def con_clientes(sesionador, tmp_path, monkeypatch):
    """Despacho A con `taller` y despacho B con `otro`; almacén en disco temporal."""
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    db.add_all([Cliente(despacho_id="uid-a", clave="taller", nombre="Taller", rfc=RFC_CLIENTE),
                Cliente(despacho_id="uid-b", clave="otro", nombre="Otro", rfc=RFC_CLIENTE)])
    db.commit()
    db.close()


def test_api_flujo_y_multitenant(api, sesionador, con_clientes):
    a, b = api("uid-a"), api("uid-b")
    base = "/api/v1/contabilidad/clientes/taller"
    assert a.post(f"{base}/cuentas/sembrar").json()["creadas"] > 50
    cuentas = {c["numero"]: c for c in a.get(f"{base}/cuentas").json()["cuentas"]}
    r = a.post(f"{base}/cuentas", json={"numero": "102.01.02", "nombre": "Banorte",
                                        "codigo_agrupador": "102.01",
                                        "padre_id": cuentas["102.01"]["id"]})
    assert r.status_code == 201 and r.json()["cuenta"]["nivel"] == 3
    xml = factura(uuid_n(1, "A0000000"))
    r = a.post("/api/v1/boveda/clientes/taller/cfdi",
               files=[("archivos", ("f.xml", xml, "application/xml"))])
    assert r.json()["importados"] == 1
    r = a.post(f"{base}/polizas/generar", json={"desde": "2026-03-01", "hasta": "2026-03-31"})
    assert r.json()["resultado"]["generadas"] == 1
    lista = a.get(f"{base}/polizas?desde=2026-03-01&hasta=2026-03-31").json()
    pid = lista["polizas"][0]["id"]
    det = a.get(f"{base}/polizas/{pid}").json()["poliza"]
    assert det["total_cargos"] == det["total_abonos"] and len(det["movimientos"]) == 5
    r = a.post(f"{base}/polizas", json={"tipo": "diario", "fecha": "2026-03-31", "movimientos": [
        {"cuenta_id": cuentas["601.84"]["id"], "cargo": "10.00"},
        {"cuenta_id": cuentas["101.01"]["id"], "abono": "10.00"}]})
    assert r.status_code == 201, r.text
    bal = a.get(f"{base}/balanza?desde=2026-03-01&hasta=2026-03-31").json()
    assert bal["cuadra"]
    aux = a.get(f"{base}/cuentas/{cuentas['601.84']['id']}/auxiliar?desde=2026-03-01"
                "&hasta=2026-03-31").json()
    assert aux["saldo_final"] == "10.00"
    assert a.post(f"{base}/polizas/generar", json={
        "desde": "2026-01-01", "hasta": "2026-12-31"}).json()["en_segundo_plano"] is True
    assert a.get(f"{base}/config").json()["config"]["cuentas"]["clientes"] == "105.01"
    assert a.post(f"{base}/reglas", json={"criterio": "rfc", "valor": "X",
                                          "cuenta_numero": "601.48"}).status_code == 201
    assert len(a.get("/api/v1/contabilidad/codigo-agrupador").json()["codigos"]) == 1080
    # El despacho B no ve nada de A: 404 en todo.
    for metodo, ruta in [("get", f"{base}/cuentas"), ("get", f"{base}/polizas/{pid}"),
                         ("get", f"{base}/balanza?desde=2026-03-01&hasta=2026-03-31"),
                         ("post", f"{base}/cuentas/sembrar"), ("get", f"{base}/config")]:
        assert getattr(b, metodo)(ruta).status_code == 404, ruta
    otro = "/api/v1/contabilidad/clientes/otro"
    b.post(f"{otro}/cuentas/sembrar")
    # Ids de A por la ruta de un cliente de B: 404.
    assert b.get(f"{otro}/polizas/{pid}").status_code == 404
    assert b.get(f"{otro}/cuentas/{cuentas['601.84']['id']}/auxiliar?desde=2026-03-01"
                 "&hasta=2026-03-31").status_code == 404
    assert b.delete(f"{otro}/cuentas/{cuentas['102.01']['id']}").status_code == 404
    with sesionador() as db:
        assert db.scalar(select(func.count(CuentaContable.id))) > 100
