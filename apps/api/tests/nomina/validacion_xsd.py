"""
Carga los XSD versionados y valida XML contra ellos, sin red.

No es un modulo de tests: es el helper que los tests usan. Vive aqui y no en
`app/` porque `lxml` es dependencia de **dev**, no de runtime — el generador
(`app/nomina_engine/cfdi_nomina_xml.py`) usa la stdlib a proposito, para no
arrastrar lxml al contenedor de Cloud Run.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lxml import etree

XSD = Path(__file__).resolve().parent.parent / "xsd"
PREFIJO_SAT = "http://www.sat.gob.mx/"


class ResolverLocal(etree.Resolver):
    """
    Mapea las URLs del SAT a los archivos locales de `tests/xsd/`.

    Es lo que permite guardar los XSD **byte-identicos** a lo publicado —con su
    `schemaLocation` original apuntando a sat.gob.mx— y aun asi compilarlos sin
    red. Editar los archivos habria sido la alternativa, y habria invalidado
    sus hashes contra la fuente oficial.
    """

    def resolve(self, system_url, public_id, context):  # noqa: D102
        if system_url and system_url.startswith(PREFIJO_SAT):
            local = XSD / system_url.rsplit("/", 1)[-1]
            if local.exists():
                return self.resolve_filename(str(local), context)
        return None


@lru_cache(maxsize=1)
def esquema_cfdi_nomina() -> etree.XMLSchema:
    """
    Esquema combinado CFDI 4.0 + nomina 1.2 + TimbreFiscalDigital 1.1.

    Los tres van juntos porque el `Complemento` del CFDI es un wildcard
    *strict*: si el esquema del complemento no esta en la misma coleccion, el
    validador rechaza el nodo por "no matching global element declaration"
    aunque el XML este perfecto.

    `no_network=True` no es decorativo: si el resolver fallara, el parser
    intentaria salir a internet y el test pasaria en la maquina de alguien y
    fallaria en CI. Asi truena en las dos.
    """
    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(ResolverLocal())
    documento = etree.parse(str(XSD / "envoltorio_validacion.xsd"), parser)
    return etree.XMLSchema(documento)


def errores_de_validacion(xml: str | bytes) -> list[str]:
    """
    Valida un XML y devuelve los errores. Lista vacia = valido.

    Devuelve los mensajes en vez de un bool para que un test que falle diga
    **por que** falló, no solo que falló.
    """
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    esquema = esquema_cfdi_nomina()
    documento = etree.fromstring(xml)
    if esquema.validate(documento):
        return []
    return [f"línea {e.line}: {e.message}" for e in esquema.error_log]
