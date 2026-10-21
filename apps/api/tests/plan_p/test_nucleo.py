"""P0: base de datos, tenencia y registro de integraciones."""

import pytest

from app.exceptions import FiscalAgentError
from app.modelos.nucleo import AsignacionCliente, Cliente, Usuario
from app.tenancy import Contexto, asegurar_usuario, cliente_o_404, clientes_visibles


def test_primer_acceso_crea_su_despacho(db_sesion):
    u = asegurar_usuario(db_sesion, "uid-a")
    assert u.despacho_id == "uid-a" and u.rol == "dueno"
    assert asegurar_usuario(db_sesion, "uid-a") is u


def test_un_despacho_no_ve_clientes_de_otro(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    asegurar_usuario(db_sesion, "uid-b")
    db_sesion.add(Cliente(despacho_id="uid-a", clave="taller", nombre="Taller"))
    db_sesion.flush()
    ctx_b = Contexto(uid="uid-b", despacho_id="uid-b", rol="dueno", db=db_sesion)
    with pytest.raises(FiscalAgentError) as e:
        cliente_o_404(ctx_b, "taller")
    assert e.value.status_code == 404
    assert clientes_visibles(ctx_b) == []


def test_auxiliar_solo_ve_lo_asignado(db_sesion):
    asegurar_usuario(db_sesion, "uid-a")
    c1 = Cliente(despacho_id="uid-a", clave="uno", nombre="Uno")
    c2 = Cliente(despacho_id="uid-a", clave="dos", nombre="Dos")
    db_sesion.add_all([c1, c2, Usuario(uid="aux", despacho_id="uid-a", rol="auxiliar")])
    db_sesion.flush()
    db_sesion.add(AsignacionCliente(usuario_uid="aux", cliente_id=c1.id))
    db_sesion.flush()
    ctx = Contexto(uid="aux", despacho_id="uid-a", rol="auxiliar", db=db_sesion)
    assert [c.clave for c in clientes_visibles(ctx)] == ["uno"]
    with pytest.raises(FiscalAgentError):
        cliente_o_404(ctx, "dos")


def test_health_de_integraciones_responde(api):
    r = api().get("/health/integraciones")
    assert r.status_code == 200
    assert "servicios" in r.json()
