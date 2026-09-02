"""
El CRUD de la cartera con el backend como dueño. (R-07)

LOS MISMOS CASOS CORREN DOS VECES, Y ESO ES EL PUNTO
-----------------------------------------------------
Contra `CarteraEnMemoria` —rápido, en CI, sin credenciales— y contra
`FirestoreCartera` **en el emulador de Firestore** (`pytest -m emulador`), que
es un Firestore de verdad.

No es redundancia. Un revisor bloqueó la primera versión del plan justamente
por proponer sólo lo primero: `FirestoreCartera` es el adaptador que ES la
tarea, y entregarlo probado únicamente contra un diccionario habría sido
entregarlo **sin haberse ejecutado nunca**. Y el test de "sobrevive reinicio"
contra un dict es tautológico: verifica que un diccionario conserva lo que le
metiste. Contra el emulador verifica lo que dice verificar.

POR QUÉ EL MARCADOR Y NO UN `skipif`
------------------------------------
El CLAUDE.md raíz pide `pytest -q` con **cero skips**, y hoy no hay un solo
skip en el repo. Marcar estos con `skipif` los convertiría en los primeros, y
además dejaría a `FirestoreCartera` sin cobertura en CI **en silencio**, que es
la mitad del problema que el emulador viene a resolver. Con el marcador
`emulador` deseleccionado por defecto, no se saltan: **no se ejecutan**, que es
distinto y honesto. Se corren aparte y su salida va al log de la sesión.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.exceptions import FiscalAgentError
from app.main import app
from app.repositorio_cartera import CarteraEnMemoria, FirestoreCartera
from app.routes import cartera as rutas_cartera

UID_A = "uid-despacho-a"
UID_B = "uid-despacho-b"

CLIENTE = {
    "id": "mio",
    "nombre": "Cliente Propio",
    "giro": "Servicios",
    "origen": "propio",
    "prima_riesgo": "0.0054355",
    "clase_riesgo": None,
    "clave_periodicidad": "04",
    "zona": "general",
    "periodo_sugerido": {"inicio": "2026-08-16", "fin": "2026-08-31", "fecha_pago": "2026-08-31"},
}

EMPLEADO = {
    "empleado_no": "E-01",
    "nombre": "PERSONA UNA",
    "puesto": "Cajera",
    "salario_diario": "520.00",
    "salario_diario_integrado": "548.50",
    "zona": "general",
    "fecha_alta": None,
    "tipo_contrato": "indeterminado",
    "prestaciones": {"dias_aguinaldo": 15, "dias_vacaciones": 0, "prima_vacacional": "0.25"},
    "nss": "",
    "employee_no": "7",
    "enrolamiento": "enrolado",
}


def _como(uid: str) -> dict[str, str]:
    """
    Cabecera de autenticacion.

    Con el emulador el token NO se verifica —no hay emulador de Auth contra el
    que validar— asi que el uid viaja como token literal. Esta declarado en
    `auth_firebase.uid_del_token` en vez de escondido en un `if`.
    """
    return {"Authorization": f"Bearer {uid}"}


@pytest.fixture
def sin_verificar():
    """
    Enciende el atajo que NO verifica el ID token.

    Hacen falta **dos** variables, y ésa es la protección: un revisor marcó que
    con sólo `FIRESTORE_EMULATOR_HOST` —que puede llegar por un `.env` copiado,
    un compose heredado o una plantilla de despliegue— la API quedaba
    completamente abierta. `PERMITIR_TOKEN_SIN_VERIFICAR` no tiene ninguna otra
    razón de existir, así que nadie la copia por accidente.
    """
    # Se GUARDA y se restaura, no se borra: un `pop` incondicional le quitaba
    # `FIRESTORE_EMULATOR_HOST` a quien la tuviera en su shell. Es el patrón de
    # `test_auth_firebase.py`.
    previos = {
        k: os.environ.get(k)
        for k in ("FIRESTORE_EMULATOR_HOST", "PERMITIR_TOKEN_SIN_VERIFICAR")
    }
    os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
    os.environ["PERMITIR_TOKEN_SIN_VERIFICAR"] = "1"
    yield
    for k, v in previos.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def repo_memoria(sin_verificar):
    almacen = CarteraEnMemoria()
    rutas_cartera._REPO_DE_PRUEBA = almacen  # noqa: SLF001
    yield almacen
    rutas_cartera._REPO_DE_PRUEBA = None  # noqa: SLF001


@pytest.fixture
def http(repo_memoria) -> TestClient:
    return TestClient(app)


# ─────────────────────────────────────────────────────────────
# Autenticacion: el uid no se puede falsificar
# ─────────────────────────────────────────────────────────────

class TestAutenticacion:
    """
    Es la mitad del valor de R-07. La cartera guarda el salario y el NSS de
    trabajadores de terceros; si el uid llegara por el cuerpo, cualquiera leeria
    la cartera de cualquiera cambiando un renglon.
    """

    def test_sin_encabezado_es_401(self, http: TestClient):
        r = http.get("/api/v1/cartera/clientes")
        assert r.status_code == 401
        assert "Authorization" in r.json()["error"]

    @pytest.mark.parametrize(
        "valor", ["", "Bearer", "Bearer   ", "Basic abc", "token-suelto"]
    )
    def test_un_encabezado_mal_formado_es_401(self, http: TestClient, valor: str):
        r = http.get("/api/v1/cartera/clientes", headers={"Authorization": valor})
        assert r.status_code == 401

    def test_el_uid_NO_se_acepta_por_query_param(self, http: TestClient, repo_memoria):
        """
        La ruta no tiene parametro de uid, y esto lo fija: pasarlo tiene que ser
        inocuo, no una puerta.
        """
        repo_memoria.guardar_cliente(UID_B, "mio", CLIENTE)

        r = http.get("/api/v1/cartera/clientes?uid=" + UID_B, headers=_como(UID_A))

        assert r.status_code == 200
        assert r.json()["clientes"] == [], "el query param movio de quien es la cartera"


# ─────────────────────────────────────────────────────────────
# Aislamiento entre despachos
# ─────────────────────────────────────────────────────────────

class TestAislamiento:
    """El test que hace verdadero el multi-tenant, medido y no declarado."""

    def test_dos_uids_ven_carteras_distintas(self, http: TestClient):
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))

        de_a = http.get("/api/v1/cartera/clientes", headers=_como(UID_A)).json()
        de_b = http.get("/api/v1/cartera/clientes", headers=_como(UID_B)).json()

        assert [c["id"] for c in de_a["clientes"]] == ["mio"]
        assert de_b["clientes"] == []

    def test_un_uid_no_puede_leer_los_empleados_de_otro(self, http: TestClient):
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))
        http.put(
            "/api/v1/cartera/clientes/mio/empleados/E-01", json=EMPLEADO, headers=_como(UID_A)
        )

        # Mismo id de cliente, otro uid: 404, no la plantilla de A.
        r = http.get("/api/v1/cartera/clientes/mio/empleados", headers=_como(UID_B))
        assert r.status_code == 404

    def test_un_uid_no_puede_borrar_el_cliente_de_otro(self, http: TestClient):
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))

        http.delete("/api/v1/cartera/clientes/mio", headers=_como(UID_B))

        sigue = http.get("/api/v1/cartera/clientes", headers=_como(UID_A)).json()
        assert [c["id"] for c in sigue["clientes"]] == ["mio"]


# ─────────────────────────────────────────────────────────────
# El CRUD
# ─────────────────────────────────────────────────────────────

class TestCRUD:
    def test_alta_edicion_y_baja_de_cliente(self, http: TestClient):
        assert http.put(
            "/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A)
        ).status_code == 200

        editado = {**CLIENTE, "nombre": "Cliente Renombrado"}
        http.put("/api/v1/cartera/clientes/mio", json=editado, headers=_como(UID_A))
        lista = http.get("/api/v1/cartera/clientes", headers=_como(UID_A)).json()
        assert lista["clientes"][0]["nombre"] == "Cliente Renombrado"
        assert lista["total"] == 1

        http.delete("/api/v1/cartera/clientes/mio", headers=_como(UID_A))
        assert http.get("/api/v1/cartera/clientes", headers=_como(UID_A)).json()["total"] == 0

    def test_el_id_de_la_url_y_el_del_cuerpo_tienen_que_coincidir(self, http: TestClient):
        """
        No se 'arregla' en silencio: adivinar cual de los dos vale escribiria el
        cliente equivocado.
        """
        r = http.put("/api/v1/cartera/clientes/otro", json=CLIENTE, headers=_como(UID_A))
        assert r.status_code == 422
        assert "no coincide" in r.json()["error"]

    def test_el_id_NO_se_guarda_dentro_del_documento(self, http: TestClient, repo_memoria):
        # Ya es el nombre del documento. Guardarlo dos veces deja dos verdades
        # que se pueden separar, y la que gana al leer es la del nombre.
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))
        assert "id" not in repo_memoria._por_uid[UID_A]["mio"]["datos"]  # noqa: SLF001

    def test_un_empleado_no_puede_colgar_de_un_cliente_que_no_existe(self, http: TestClient):
        # Seria invisible en la lista y aparecería en el calculo.
        r = http.put(
            "/api/v1/cartera/clientes/fantasma/empleados/E-01",
            json=EMPLEADO,
            headers=_como(UID_A),
        )
        assert r.status_code == 404

    def test_borrar_un_cliente_se_lleva_a_sus_empleados(self, http: TestClient):
        """
        Firestore no borra subcolecciones en cascada. Sin esto los empleados
        quedan huerfanos —con su salario y su NSS— y **reaparecen** al recrear un
        cliente con el mismo id.
        """
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))
        http.put(
            "/api/v1/cartera/clientes/mio/empleados/E-01", json=EMPLEADO, headers=_como(UID_A)
        )

        http.delete("/api/v1/cartera/clientes/mio", headers=_como(UID_A))
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))

        r = http.get("/api/v1/cartera/clientes/mio/empleados", headers=_como(UID_A))
        assert r.json()["empleados"] == [], "un empleado borrado revivio al recrear el cliente"

    def test_cuenta_los_no_vinculados_al_checador(self, http: TestClient):
        # Se cuenta en el backend y no en la UI: un aviso que depende de que
        # alguien se acuerde de filtrar es un aviso que un dia no sale.
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))
        http.put(
            "/api/v1/cartera/clientes/mio/empleados/E-01", json=EMPLEADO, headers=_como(UID_A)
        )
        http.put(
            "/api/v1/cartera/clientes/mio/empleados/E-02",
            json={**EMPLEADO, "empleado_no": "E-02", "employee_no": None},
            headers=_como(UID_A),
        )

        r = http.get("/api/v1/cartera/clientes/mio/empleados", headers=_como(UID_A)).json()
        assert r["total"] == 2
        assert r["sin_vincular"] == 1


# ─────────────────────────────────────────────────────────────
# Validacion: lo que el contrato rechaza
# ─────────────────────────────────────────────────────────────

class TestValidacion:
    def test_una_prima_de_riesgo_fuera_del_Art_72_se_rechaza(self, http: TestClient):
        """
        Capturar 5.4355 en vez de 0.0054355 multiplica Riesgos de Trabajo por
        mil, y ninguna tabla lo detecta despues.
        """
        r = http.put(
            "/api/v1/cartera/clientes/mio",
            json={**CLIENTE, "prima_riesgo": "5.4355"},
            headers=_como(UID_A),
        )
        assert r.status_code == 422

    @pytest.mark.parametrize("nss", ["1234567890", "123456789034", "abcdefghijk"])
    def test_un_NSS_mal_formado_se_rechaza(self, http: TestClient, nss: str):
        """
        MISMO VECTOR QUE `apps/store/src/services/nss.test.ts`. Son dos
        implementaciones del mismo criterio y divergir tiene que romper una
        prueba. Si agregas un caso aqui, agregalo alla.
        """
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))
        r = http.put(
            "/api/v1/cartera/clientes/mio/empleados/E-01",
            json={**EMPLEADO, "nss": nss},
            headers=_como(UID_A),
        )
        assert r.status_code == 422

    @pytest.mark.parametrize("nss", ["", "12345678903", "12345678900"])
    def test_vacio_y_11_digitos_se_aceptan_incluido_el_verificador_que_no_casa(
        self, http: TestClient, nss: str
    ):
        """
        `12345678900` tiene el verificador equivocado y **se acepta**: no hay
        norma primaria del IMSS publicada, y el XSD del SAT timbra con
        `[0-9]{1,15}` sin exigirlo. Rechazarlo empujaria al contador a teclear
        uno que pase Luhn — un NSS INVENTADO junto a datos reales (§D25).
        """
        http.put("/api/v1/cartera/clientes/mio", json=CLIENTE, headers=_como(UID_A))
        r = http.put(
            "/api/v1/cartera/clientes/mio/empleados/E-01",
            json={**EMPLEADO, "nss": nss},
            headers=_como(UID_A),
        )
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# CORS: el preflight que el navegador hace antes de un PUT
# ─────────────────────────────────────────────────────────────

def test_el_preflight_de_PUT_esta_permitido(http: TestClient):
    """
    Sin `PUT`/`DELETE` en `allow_methods` el navegador falla en el preflight, y
    eso **no se ve como un problema de permisos: se ve como red caida**, que
    manda a buscar el bug al lugar equivocado.
    """
    r = http.options(
        "/api/v1/cartera/clientes/mio",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
        },
    )
    assert r.status_code == 200
    assert "PUT" in r.headers.get("access-control-allow-methods", "")


# ─────────────────────────────────────────────────────────────
# Contra el EMULADOR: Firestore de verdad
# ─────────────────────────────────────────────────────────────

pytestmark_emulador = pytest.mark.emulador


@pytest.fixture
def repo_emulador(sin_verificar):
    """
    `FirestoreCartera` contra un Firestore real.

    Sin esto, el adaptador que ES la tarea se entregaria **sin haberse
    ejecutado nunca**: los tests de arriba prueban las rutas y la autenticacion
    contra un diccionario, no las rutas de Firestore, ni las subcolecciones, ni
    el borrado en cascada, ni que un `set(merge=True)` haga lo que se espera.
    """
    from app.auth_firebase import cliente_firestore

    db = cliente_firestore()
    repo = FirestoreCartera(db)
    # Cada corrida en su propio subarbol: los tests no pueden depender del orden
    # ni de lo que dejo la corrida anterior.
    import uuid

    sufijo = uuid.uuid4().hex[:8]
    yield repo, f"{UID_A}-{sufijo}", f"{UID_B}-{sufijo}"


@pytest.mark.emulador
class TestContraElEmulador:
    """
    Los mismos criterios, contra Firestore de verdad.

    Se corren con `pytest -m emulador`. Fuera de esa marca no se ejecutan, para
    que `pytest -q` no dependa de que alguien tenga el emulador arriba.
    """

    def test_sobrevive_a_reiniciar_el_proceso(self, repo_emulador):
        """
        EL CRITERIO LITERAL DE R-07, y el unico test que lo mide de verdad.

        Contra `CarteraEnMemoria` esto seria tautologico: verificaria que un
        diccionario conserva lo que le metiste. Aqui se escribe con un
        repositorio, se **construye otro desde cero** —como haria un proceso
        recien arrancado— y se lee con el segundo.
        """
        repo, uid, _ = repo_emulador
        repo.guardar_cliente(uid, "mio", {k: v for k, v in CLIENTE.items() if k != "id"})
        repo.guardar_empleado(uid, "mio", "E-01", EMPLEADO)

        from app.auth_firebase import cliente_firestore

        otro = FirestoreCartera(cliente_firestore())

        clientes = otro.listar_clientes(uid)
        assert [c["id"] for c in clientes] == ["mio"]
        empleados = otro.listar_empleados(uid, "mio")
        assert len(empleados) == 1
        assert empleados[0]["salario_diario"] == "520.00"

    def test_aislamiento_entre_uids_en_Firestore_real(self, repo_emulador):
        repo, uid_a, uid_b = repo_emulador
        repo.guardar_cliente(uid_a, "mio", {"nombre": "De A"})

        assert [c["id"] for c in repo.listar_clientes(uid_a)] == ["mio"]
        assert repo.listar_clientes(uid_b) == []

    def test_el_borrado_en_cascada_funciona_en_Firestore(self, repo_emulador):
        """
        La razon de este test es que Firestore **no** borra subcolecciones solo,
        y el bug es invisible hasta que alguien recrea un cliente con el mismo
        id y le reaparecen empleados ajenos con su salario y su NSS.
        """
        repo, uid, _ = repo_emulador
        repo.guardar_cliente(uid, "mio", {"nombre": "Con empleados"})
        repo.guardar_empleado(uid, "mio", "E-01", EMPLEADO)
        repo.guardar_empleado(uid, "mio", "E-02", {**EMPLEADO, "empleado_no": "E-02"})

        repo.borrar_cliente(uid, "mio")
        # Se recrea con el MISMO id: si la cascada fallo, los empleados vuelven.
        repo.guardar_cliente(uid, "mio", {"nombre": "Recreado"})

        assert repo.listar_empleados(uid, "mio") == []

    def test_un_empleado_no_cuelga_de_un_cliente_inexistente(self, repo_emulador):
        repo, uid, _ = repo_emulador
        with pytest.raises(FiscalAgentError):
            repo.guardar_empleado(uid, "fantasma", "E-01", EMPLEADO)

    def test_guardar_es_MERGE_y_no_reemplazo(self, repo_emulador):
        """
        Un PUT parcial no debe borrar campos que esta version de la app todavia
        no conoce: una cartera escrita por una version anterior perderia datos
        en silencio al editarla.
        """
        repo, uid, _ = repo_emulador
        repo.guardar_cliente(uid, "mio", {"nombre": "Original", "campo_futuro": "x"})
        repo.guardar_cliente(uid, "mio", {"nombre": "Editado"})

        guardado = repo.obtener_cliente(uid, "mio")
        assert guardado["nombre"] == "Editado"
        assert guardado["campo_futuro"] == "x", "el merge borro un campo desconocido"


class TestDocumentosLegados:
    """
    Un documento guardado por una version anterior NO puede tumbar la cartera.

    El defecto que esto cierra lo midio el revisor de motor: la lectura hacia
    `EmpleadoCarteraSchema(**e)` a secas, asi que un NSS de 9 digitos —tolerado
    hoy por el front, que castea— producia un **500**. Y como el front pide los
    empleados de todos los clientes dentro de un `Promise.all`, **un solo
    documento legado dejaba la cartera COMPLETA en cero**.

    El endpoint de clientes ya era laxo por esta razon exacta; este no lo era, y
    es el que mas duele porque es el que alimenta el calculo.
    """

    def test_un_empleado_ilegible_no_tumba_la_lista(self, http: TestClient, repo_memoria):
        repo_memoria.guardar_cliente(UID_A, "mio", CLIENTE)
        repo_memoria.guardar_empleado(UID_A, "mio", "E-01", EMPLEADO)
        # Guardado directo en el repositorio, saltando la validacion de la ruta:
        # es exactamente como llego el documento viejo a Firestore.
        repo_memoria.guardar_empleado(
            UID_A, "mio", "E-99", {**EMPLEADO, "empleado_no": "E-99", "nss": "123456789"}
        )

        r = http.get("/api/v1/cartera/clientes/mio/empleados", headers=_como(UID_A))

        assert r.status_code == 200, "un documento legado tumbo la respuesta entera"
        cuerpo = r.json()
        assert [e["empleado_no"] for e in cuerpo["empleados"]] == ["E-01"]

    def test_y_los_ilegibles_se_REPORTAN_no_se_esconden(self, http: TestClient, repo_memoria):
        """
        Quedar fuera del calculo en silencio es el modo de falla que toda la
        epica G viene evitando. Si el empleado no entra, el contador tiene que
        poder enterarse.
        """
        repo_memoria.guardar_cliente(UID_A, "mio", CLIENTE)
        repo_memoria.guardar_empleado(
            UID_A, "mio", "E-99", {**EMPLEADO, "empleado_no": "E-99", "nss": "123456789"}
        )

        cuerpo = http.get(
            "/api/v1/cartera/clientes/mio/empleados", headers=_como(UID_A)
        ).json()
        assert cuerpo["ilegibles"] == ["E-99"]

    def test_sin_ilegibles_la_lista_va_vacia(self, http: TestClient, repo_memoria):
        # La mitad simetrica: un campo que se llenara siempre volveria inutil el
        # aviso por saturacion.
        repo_memoria.guardar_cliente(UID_A, "mio", CLIENTE)
        repo_memoria.guardar_empleado(UID_A, "mio", "E-01", EMPLEADO)

        cuerpo = http.get(
            "/api/v1/cartera/clientes/mio/empleados", headers=_como(UID_A)
        ).json()
        assert cuerpo["ilegibles"] == []


class TestTopesEnFirestore:
    """
    Los topes existian SOLO en el doble en memoria, asi que el comentario que
    los justifica —"sin tope un bucle de curl con un token valido es una
    factura"— describia una proteccion que el codigo real no tenia.
    """

    def test_el_doble_y_Firestore_declaran_el_mismo_tope(self):
        from app import repositorio_cartera as rc

        # No se prueba llenando 500 clientes: se fija que la constante es UNA y
        # que las dos implementaciones la miran. La de Firestore se ejercita en
        # el emulador; aqui se evita que alguien la duplique con otro valor.
        assert rc.MAX_CLIENTES_POR_UID > 0
        assert rc.MAX_EMPLEADOS_POR_CLIENTE > 0

    def test_el_doble_rechaza_al_pasarse(self, repo_memoria, monkeypatch):
        from app import repositorio_cartera as rc

        monkeypatch.setattr(rc, "MAX_CLIENTES_POR_UID", 1)
        repo_memoria.guardar_cliente(UID_A, "uno", CLIENTE)

        with pytest.raises(FiscalAgentError) as exc:
            repo_memoria.guardar_cliente(UID_A, "dos", CLIENTE)
        assert exc.value.status_code == 409

    def test_editar_uno_existente_NO_rebota_por_el_tope(self, repo_memoria, monkeypatch):
        # Si no, llegar al tope dejaria la cartera de solo lectura.
        from app import repositorio_cartera as rc

        monkeypatch.setattr(rc, "MAX_CLIENTES_POR_UID", 1)
        repo_memoria.guardar_cliente(UID_A, "uno", CLIENTE)
        repo_memoria.guardar_cliente(UID_A, "uno", {**CLIENTE, "nombre": "Editado"})

        assert repo_memoria.obtener_cliente(UID_A, "uno")["nombre"] == "Editado"


@pytest.mark.emulador
class TestTopesContraElEmulador:
    """
    Los topes de `FirestoreCartera`, contra Firestore de verdad.

    Un revisor los encontro **sin una sola prueba** dos pasadas seguidas:
    primero porque solo existian en el doble, y despues porque los tests que
    agregue median el doble (`test_el_doble_rechaza_al_pasarse` — el nombre lo
    dice) mas una tautologia. Quitarlos de la implementacion real dejaba las dos
    suites en verde.

    Importa mas de lo que parece: el camino nuevo hace un `.get()` extra y un
    `limit(MAX+1).stream()` contra Firestore en cada alta, y ese codigo no se
    ejecutaba en ninguna corrida.
    """

    def test_rechaza_al_pasarse_del_tope_de_clientes(self, repo_emulador, monkeypatch):
        from app import repositorio_cartera as rc

        repo, uid, _ = repo_emulador
        monkeypatch.setattr(rc, "MAX_CLIENTES_POR_UID", 1)
        repo.guardar_cliente(uid, "uno", {"nombre": "Uno"})

        with pytest.raises(FiscalAgentError) as exc:
            repo.guardar_cliente(uid, "dos", {"nombre": "Dos"})
        assert exc.value.status_code == 409

    def test_editar_uno_existente_NO_rebota(self, repo_emulador, monkeypatch):
        # Si rebotara, llegar al tope dejaria la cartera de SOLO LECTURA: el
        # contador no podria ni corregir un nombre.
        from app import repositorio_cartera as rc

        repo, uid, _ = repo_emulador
        monkeypatch.setattr(rc, "MAX_CLIENTES_POR_UID", 1)
        repo.guardar_cliente(uid, "uno", {"nombre": "Uno"})
        repo.guardar_cliente(uid, "uno", {"nombre": "Editado"})

        assert repo.obtener_cliente(uid, "uno")["nombre"] == "Editado"

    def test_rechaza_al_pasarse_del_tope_de_empleados(self, repo_emulador, monkeypatch):
        from app import repositorio_cartera as rc

        repo, uid, _ = repo_emulador
        monkeypatch.setattr(rc, "MAX_EMPLEADOS_POR_CLIENTE", 1)
        repo.guardar_cliente(uid, "mio", {"nombre": "Mio"})
        repo.guardar_empleado(uid, "mio", "E-01", EMPLEADO)

        with pytest.raises(FiscalAgentError) as exc:
            repo.guardar_empleado(uid, "mio", "E-02", {**EMPLEADO, "empleado_no": "E-02"})
        assert exc.value.status_code == 409

    def test_la_LECTURA_no_trunca(self, repo_emulador, monkeypatch):
        """
        El `.limit()` estaba tambien del lado de leer, y **truncaba en
        silencio**: el cliente 501 desaparecia de la lista del contador sin un
        solo aviso, que es peor que cualquier cosa que el tope viniera a evitar.
        """
        from app import repositorio_cartera as rc

        repo, uid, _ = repo_emulador
        monkeypatch.setattr(rc, "MAX_CLIENTES_POR_UID", 1)
        # Se escriben DOS saltandose la ruta, como si vinieran de antes del tope.
        repo._clientes(uid).document("uno").set({"nombre": "Uno"})  # noqa: SLF001
        repo._clientes(uid).document("dos").set({"nombre": "Dos"})  # noqa: SLF001

        assert len(repo.listar_clientes(uid)) == 2, "la lectura truncó en silencio"
