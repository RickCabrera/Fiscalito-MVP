"""
P3-02/03/07/08: rutas de impuestos del cliente y calculadoras, contra la bóveda.

Las calculadoras deben dar lo mismo que el motor del módulo que las respalda.
"""

from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from app.fiscal_engine.actualizacion import calcular_actualizacion_recargos
from app.fiscal_engine.calculadora import calcular_isr_resico
from app.modelos.nucleo import Cliente
from app.nomina_engine.isr_nomina import isr_retenido
from app.tenancy import asegurar_usuario
from tests.plan_p.cfdi_sintetico import RFC_CLIENTE, RFC_PROVEEDOR, cfdi, uuid_n

NOMINA = Path(__file__).resolve().parents[1] / "fixtures" / "nomina"


@pytest.fixture
def con_clientes(sesionador, tmp_path, monkeypatch):
    monkeypatch.setenv("FISCALITO_ALMACEN_DIR", str(tmp_path / "almacen"))
    monkeypatch.delenv("FISCALITO_ALMACENAMIENTO", raising=False)
    db = sesionador()
    asegurar_usuario(db, "uid-a")
    asegurar_usuario(db, "uid-b")
    db.add_all(
        [
            Cliente(
                despacho_id="uid-a",
                clave="taller",
                nombre="Taller",
                rfc=RFC_CLIENTE,
                datos={"regimen": "612", "clave_entidad": "VER"},
            ),
            Cliente(despacho_id="uid-b", clave="otro", nombre="Otro", rfc=RFC_CLIENTE),
        ]
    )
    db.commit()
    db.close()


def _subir(a, archivos):
    r = a.post(
        "/api/v1/boveda/clientes/taller/cfdi",
        files=[("archivos", (f"{i}.xml", x, "text/xml")) for i, x in enumerate(archivos)],
    )
    assert r.status_code == 200, r.text
    assert not r.json()["rechazados"], r.json()["rechazados"]


def test_iva_de_la_boveda_arrastra_saldo(api, con_clientes):
    a = api("uid-a")
    _subir(
        a,
        [
            # enero: cobra 1,000 + 160; paga 5,000 + 800 → saldo a favor 640
            cfdi(uuid_n(1), fecha="2026-01-10T10:00:00"),
            cfdi(
                uuid_n(2),
                emisor=RFC_PROVEEDOR,
                receptor=RFC_CLIENTE,
                fecha="2026-01-11T10:00:00",
                subtotal="5000.00",
                total="5800.00",
                iva="800.00",
            ),
            # febrero: cobra 10,000 + 1,600 → 1,600 - 640 = 960
            cfdi(
                uuid_n(3),
                fecha="2026-02-10T10:00:00",
                subtotal="10000.00",
                total="11600.00",
                iva="1600.00",
            ),
        ],
    )
    r = a.post("/api/v1/impuestos/clientes/taller/iva", json={"anio": 2026, "meses": [1, 2]})
    assert r.status_code == 200, r.text
    ene, feb = r.json()["meses"]
    assert ene["saldo_favor_siguiente"] == "640.00"
    assert feb["saldo_favor_aplicado"] == "640.00" and feb["iva_a_pagar"] == "960.00"


def test_resumen_con_pago_tarde_y_capturas(api, con_clientes):
    a = api("uid-a")
    _subir(
        a,
        [
            cfdi(
                uuid_n(1),
                fecha="2026-01-10T10:00:00",
                subtotal="10000.00",
                total="11600.00",
                iva="1600.00",
            )
        ],
    )
    r = a.post(
        "/api/v1/impuestos/clientes/taller/resumen",
        json={
            "anio": 2026,
            "mes": 1,
            "fecha_pago": "2026-08-10",
            "capturas": {"iva_a_cargo": {"compensaciones": "100"}},
        },
    )
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["fecha_limite"] == "2026-02-17"
    filas = {f["clave"]: f for f in datos["renglones"]}
    assert len(filas) == 13 and filas["isr_pm"]["aplica"] is False
    iva = filas["iva_a_cargo"]
    assert iva["importe_sistema"] == "1600.00" and iva["compensaciones"] == "100.00"
    esperado = calcular_actualizacion_recargos(D("1500"), date(2026, 2, 17), date(2026, 8, 10))
    assert iva["actualizacion"] == f"{esperado.actualizacion:.2f}"
    assert iva["recargos"] == f"{esperado.recargos:.2f}"
    isr = filas["isr_pf_empresarial"]
    assert D(isr["importe_sistema"]) > 0  # 612: el motor de calculadora.py

    xlsx = a.post(
        "/api/v1/impuestos/clientes/taller/resumen",
        json={"anio": 2026, "mes": 1, "fecha_pago": "2026-02-17", "formato": "xlsx"},
    )
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    csv = a.post(
        "/api/v1/impuestos/clientes/taller/resumen",
        json={"anio": 2026, "mes": 1, "fecha_pago": "2026-02-17", "formato": "csv"},
    )
    assert "IVA a cargo" in csv.content.decode("utf-8-sig")


def test_subsidio_solo_en_salarios(api, con_clientes):
    a = api("uid-a")
    r = a.post(
        "/api/v1/impuestos/clientes/taller/resumen",
        json={
            "anio": 2026,
            "mes": 1,
            "fecha_pago": "2026-02-17",
            "capturas": {"iva_a_cargo": {"subsidio": "10"}},
        },
    )
    assert r.status_code == 422


def test_isn_del_cliente_en_veracruz_con_nomina_de_la_boveda(api, con_clientes, sesionador):
    a = api("uid-a")
    db = sesionador()
    cliente = db.query(Cliente).filter_by(clave="taller").one()
    xmls = sorted(NOMINA.glob("semana-*/*.xml"))
    rfc_emisor = xmls[0].read_text(encoding="utf-8").split('Rfc="')[1].split('"')[0]
    cliente.rfc = rfc_emisor
    db.commit()
    db.close()
    marzo = [x for x in xmls if 'FechaPago="2026-03' in x.read_text(encoding="utf-8")]
    _subir(a, [x.read_bytes() for x in marzo])
    r = a.post("/api/v1/calculadoras/isn", json={"cliente": "taller", "anio": 2026, "mes": 3})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["entidad"] == "VER" and d["tasa"] == "0.03" and d["nominas"] == len(marzo)
    base = D(d["base"])
    assert base > 0 and D(d["impuesto"]) == (base * D("0.03")).quantize(D("0.01"))
    assert D(d["adicional"]) == (D(d["impuesto"]) * D("0.15")).quantize(D("0.01"))


def test_multitenant_404(api, con_clientes):
    b = api("uid-b")
    assert (
        b.post(
            "/api/v1/impuestos/clientes/taller/iva", json={"anio": 2026, "meses": [1]}
        ).status_code
        == 404
    )
    assert (
        b.post(
            "/api/v1/impuestos/clientes/taller/resumen",
            json={"anio": 2026, "mes": 1, "fecha_pago": "2026-02-17"},
        ).status_code
        == 404
    )
    assert (
        b.post(
            "/api/v1/calculadoras/isn", json={"cliente": "taller", "anio": 2026, "mes": 3}
        ).status_code
        == 404
    )
    assert b.get("/api/v1/impuestos/clientes/taller/config").status_code == 404


def test_config_por_cliente(api, con_clientes):
    a = api("uid-a")
    assert (
        a.get("/api/v1/impuestos/clientes/taller/config").json()["config"]["modo_factor"]
        == "truncar"
    )
    r = a.put(
        "/api/v1/impuestos/clientes/taller/config",
        json={"modo_factor": "redondear", "region_fronteriza": True},
    )
    assert r.status_code == 200
    assert (
        a.get("/api/v1/impuestos/clientes/taller/config").json()["config"]["region_fronteriza"]
        is True
    )


def test_sin_token_401(api, con_clientes):
    from fastapi.testclient import TestClient

    from app.main import app

    api("uid-a")
    assert (
        TestClient(app)
        .post("/api/v1/calculadoras/isr-resico", json={"ingresos_cobrados": "1"})
        .status_code
        == 401
    )


# ── calculadoras = mismo motor ──


def test_calculadora_actualizacion_es_el_motor(api, con_clientes):
    a = api("uid-a")
    r = a.post(
        "/api/v1/calculadoras/actualizacion-recargos",
        json={"monto": "25000", "fecha_limite": "2026-02-17", "fecha_pago": "2026-08-10"},
    ).json()
    m = calcular_actualizacion_recargos(D("25000"), date(2026, 2, 17), date(2026, 8, 10))
    assert r["monto_actualizado"] == f"{m.monto_actualizado:.2f}" == "25275.00"
    assert r["recargos"] == f"{m.recargos:.2f}"


def test_calculadora_isr_sueldos_es_el_motor(api, con_clientes):
    a = api("uid-a")
    r = a.post(
        "/api/v1/calculadoras/isr-sueldos",
        json={"base_gravable": "9500", "clave_periodicidad": "05", "fecha_pago": "2026-03-31"},
    ).json()
    m = isr_retenido(D("9500"), "05", date(2026, 3, 31), D("9500"), 30)
    assert r["isr_retenido"] == f"{m.retenido:.2f}" and r["subsidio"] == f"{m.subsidio:.2f}"


def test_calculadora_resico_es_el_motor(api, con_clientes):
    a = api("uid-a")
    r = a.post(
        "/api/v1/calculadoras/isr-resico",
        json={"ingresos_cobrados": "40000", "isr_retenido": "100"},
    ).json()
    isr, tasa = calcular_isr_resico(40000.0)
    assert r["isr_causado"] == f"{isr:.2f}" == "440.00" and r["isr_a_pagar"] == "340.00"


def test_calculadoras_laborales(api, con_clientes):
    a = api("uid-a")
    ag = a.post(
        "/api/v1/calculadoras/aguinaldo", json={"salario_diario": "500", "fecha_pago": "2026-12-15"}
    ).json()
    assert ag["importe"] == "7500.00"
    exento = D(ag["partidas"][0]["exento"])
    assert exento == (D("117.31") * 30).quantize(D("0.01"))  # Art. 93 fr. XIV: 30 UMA
    ptu = a.post(
        "/api/v1/calculadoras/ptu",
        json={
            "utilidad_repartible": "100000",
            "dias_trabajador": 365,
            "salario_trabajador": "100000",
            "total_dias_todos": 3650,
            "total_salarios_todos": "1000000",
            "salario_diario": "300",
            "fecha_pago": "2026-05-30",
        },
    ).json()
    assert ptu["calculada"] == "10000.00" and ptu["importe"] == "10000.00"
    fin = a.post(
        "/api/v1/calculadoras/finiquito",
        json={
            "salario_diario": "400",
            "fecha_ingreso": "2024-01-01",
            "fecha_baja": "2026-06-30",
            "tipo": "despido_injustificado",
        },
    ).json()
    assert fin["exito"] and D(fin["total_bruto"]) > D("36000")  # incluye 90 días de indemnización
    # O1: el motor de P4 indemniza con SDI (Art. 84 LFT), no con el salario diario. Sin SDI
    # capturado se integra con el factor de ley a 2 años: 1.0507 → 420.28 × 90.
    indem = next(s for s in fin["separacion"] if "50 fr. III" in s["fundamento"])
    assert fin["salario_diario_integrado"] == "420.28" and indem["importe"] == "37825.20"
    # O4: sin pedirlos, los 20 días por año no entran, y la respuesta lo dice.
    assert not any("20 DÍAS" in s["concepto"] for s in fin["separacion"])
    assert any("Art. 49" in n for n in fin["notas"])


def test_isn_sin_cliente_y_catalogo(api, con_clientes):
    a = api("uid-a")
    r = a.post(
        "/api/v1/calculadoras/isn",
        json={"entidad": "VER", "fecha": "2026-03-01", "total_erogaciones": "10000"},
    ).json()
    assert r["impuesto"] == "300.00" and r["adicional"] == "45.00" and r["total"] == "345.00"
    cat = a.get("/api/v1/calculadoras/isn/tasas", params={"fecha": "2026-03-01"}).json()
    assert len(cat["entidades"]) == 32
