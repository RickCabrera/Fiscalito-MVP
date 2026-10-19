"""
Un SAT simulado para los tests de la descarga masiva (P1-01): `httpx.MockTransport` que
contesta con las plantillas grabadas de `tests/fixtures/sat_descarga/`. Sin red.

Programable: cuántas verificaciones responden "en proceso", qué código da la solicitud, si
el token vence, qué paquetes (ZIP) genera cada solicitud. Registra cada petición para que el
test cuente autenticaciones, solicitudes y descargas.
"""

from __future__ import annotations

import base64
import io
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from lxml import etree

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sat_descarga"


def plantilla(nombre: str, **campos: str) -> str:
    texto = (FIXTURES / nombre).read_text(encoding="utf-8")
    for k, v in campos.items():
        texto = texto.replace("{" + k + "}", v)
    return texto


def zip_de(miembros: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, datos in miembros.items():
            zf.writestr(nombre, datos)
    return buf.getvalue()


@dataclass
class Reloj:
    momento: datetime = field(default_factory=lambda: datetime(2026, 10, 1, 12, 0, tzinfo=UTC))

    def __call__(self) -> datetime:
        return self.momento

    def avanzar(self, **kw: float) -> None:
        self.momento += timedelta(**kw)


@dataclass
class SatSimulado:
    reloj: Reloj = field(default_factory=Reloj)
    # Paquetes (ZIP) por cada solicitud aceptada, en orden. [] = sin información.
    paquetes_por_solicitud: list[list[bytes]] = field(default_factory=list)
    en_proceso: int = 0
    codigo_solicitud: str = "5000"
    # La siguiente llamada con token responde Fault de seguridad (token rechazado).
    rechazar_token_una_vez: bool = False
    # Respuestas de verificación forzadas (CodEstatus) para la siguiente llamada.
    codigo_verificacion: str = "5000"
    codigo_descarga: str = "5000"
    vida_token: timedelta = timedelta(minutes=5)

    peticiones: list[tuple[str, dict[str, str], bytes]] = field(default_factory=list)
    tokens_emitidos: list[str] = field(default_factory=list)
    _solicitudes: dict[str, list[str]] = field(default_factory=dict)
    _paquetes: dict[str, bytes] = field(default_factory=dict)
    _verificadas: dict[str, int] = field(default_factory=dict)

    # ── conteos ──

    def contar(self, operacion: str) -> int:
        return sum(1 for op, _h, _b in self.peticiones if op == operacion)

    # ── transporte ──

    def transporte(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._responder)

    def cliente(self) -> httpx.Client:
        return httpx.Client(transport=self.transporte())

    def _token_valido(self, encabezado: str) -> bool:
        if not encabezado.startswith('WRAP access_token="'):
            return False
        token = encabezado[len('WRAP access_token="'):-1]
        if token not in self.tokens_emitidos:
            return False
        emitido = datetime.fromisoformat(token.split("|")[1])
        return self.reloj() < emitido + self.vida_token

    def _responder(self, request: httpx.Request) -> httpx.Response:
        accion = request.headers.get("SOAPAction", "")
        operacion = accion.rsplit("/", 1)[-1]
        cuerpo = request.read()
        self.peticiones.append((operacion, dict(request.headers), cuerpo))
        if operacion == "Autentica":
            return self._autenticar()
        if self.rechazar_token_una_vez or not self._token_valido(
            request.headers.get("Authorization", "")
        ):
            self.rechazar_token_una_vez = False
            return httpx.Response(500, text=plantilla("fault_seguridad.xml"))
        raiz = etree.fromstring(cuerpo)
        nodo = raiz.find(".//{http://DescargaMasivaTerceros.sat.gob.mx}solicitud")
        if operacion.startswith("SolicitaDescarga"):
            return self._solicitar(operacion)
        if operacion == "VerificaSolicitudDescarga":
            return self._verificar(nodo.get("IdSolicitud"))
        if operacion == "Descargar":
            p = raiz.find(".//{http://DescargaMasivaTerceros.sat.gob.mx}peticionDescarga")
            return self._descargar(p.get("IdPaquete"))
        return httpx.Response(404, text="operación desconocida")

    def _autenticar(self) -> httpx.Response:
        creado = self.reloj()
        token = f"tok{len(self.tokens_emitidos) + 1}|{creado.isoformat()}"
        self.tokens_emitidos.append(token)
        fmt = "%Y-%m-%dT%H:%M:%S.000Z"
        return httpx.Response(200, text=plantilla(
            "autenticacion_token.xml", CREADO=creado.strftime(fmt),
            EXPIRA=(creado + self.vida_token).strftime(fmt), TOKEN=token,
        ))

    def _solicitar(self, operacion: str) -> httpx.Response:
        if self.codigo_solicitud != "5000":
            return httpx.Response(200, text=plantilla(
                "solicitud.xml", OPERACION=operacion, ID="", CODIGO=self.codigo_solicitud,
                MENSAJE="Respuesta del SAT",
            ))
        ident = f"4e80345d-917f-40bb-a98f-{len(self._solicitudes) + 1:012d}"
        zips = self.paquetes_por_solicitud.pop(0) if self.paquetes_por_solicitud else []
        ids = []
        for n, contenido in enumerate(zips, start=1):
            pid = f"{ident}_{n:02d}"
            self._paquetes[pid] = contenido
            ids.append(pid)
        self._solicitudes[ident] = ids
        return httpx.Response(200, text=plantilla(
            "solicitud.xml", OPERACION=operacion, ID=ident, CODIGO="5000",
            MENSAJE="Solicitud Aceptada",
        ))

    def _verificar(self, ident: str) -> httpx.Response:
        if self.codigo_verificacion != "5000" or ident not in self._solicitudes:
            codigo = self.codigo_verificacion if self.codigo_verificacion != "5000" else "5004"
            return httpx.Response(200, text=plantilla(
                "verificacion.xml", CODIGO=codigo, ESTADO="0", CODIGO_ESTADO="", NUMERO="0",
                MENSAJE="No se encontró la solicitud", PAQUETES="",
            ))
        vista = self._verificadas.get(ident, 0) + 1
        self._verificadas[ident] = vista
        if vista <= self.en_proceso:
            return httpx.Response(200, text=plantilla(
                "verificacion.xml", CODIGO="5000", ESTADO="2", CODIGO_ESTADO="5000",
                NUMERO="0", MENSAJE="Solicitud Aceptada", PAQUETES="",
            ))
        ids = self._solicitudes[ident]
        if not ids:
            return httpx.Response(200, text=plantilla(
                "verificacion.xml", CODIGO="5000", ESTADO="5", CODIGO_ESTADO="5004",
                NUMERO="0", MENSAJE="Solicitud Aceptada", PAQUETES="",
            ))
        paquetes = "".join(f"<IdsPaquetes>{i}</IdsPaquetes>" for i in ids)
        return httpx.Response(200, text=plantilla(
            "verificacion.xml", CODIGO="5000", ESTADO="3", CODIGO_ESTADO="5000",
            NUMERO=str(len(ids)), MENSAJE="Solicitud Aceptada", PAQUETES=paquetes,
        ))

    def _descargar(self, pid: str) -> httpx.Response:
        if self.codigo_descarga != "5000" or pid not in self._paquetes:
            codigo = self.codigo_descarga if self.codigo_descarga != "5000" else "5007"
            return httpx.Response(200, text=plantilla(
                "descarga.xml", CODIGO=codigo, MENSAJE="No existe el paquete solicitado",
                PAQUETE="<Paquete />",
            ))
        b64 = base64.b64encode(self._paquetes[pid]).decode()
        # Partido en renglones de 76 como lo manda un servicio .NET: el lector debe tolerarlo.
        partido = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
        return httpx.Response(200, text=plantilla(
            "descarga.xml", CODIGO="5000", MENSAJE="Solicitud Aceptada",
            PAQUETE=f"<Paquete>{partido}</Paquete>",
        ))
