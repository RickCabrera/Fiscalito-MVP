"""
Lo que gasta LLM (P0-02): límite por minuto por usuario y tope diario por despacho.

QUÉ SE CUENTA
-------------
Una **llamada al proveedor**: cada explicación que una ruta pide (`incluir_explicacion`) y
cada vuelta del loop del agente. Es lo único medible con lo que hay hoy —los servicios de
`app/services/llm_service.py` no devuelven tokens ni costo—, y es proporcional al gasto
porque cada llamada tiene un `max_tokens` fijo. Cuando el adaptador `app/integraciones/llm`
reemplace esos servicios (devuelve `tokens_entrada`/`tokens_salida`), el tope se puede pasar
a pesos sin cambiar la interfaz de `CobradorLLM`.

- `FISCALITO_RATE_LIMIT_LLM_POR_MINUTO` (default 20): por usuario, ventana deslizante.
- `FISCALITO_TOPE_LLM_DIARIO_LLAMADAS` (default 500): por despacho y día de la Ciudad de
  México, contado en la tabla `consumo_llm`. Al llegar al tope: 429 con `Retry-After` hasta
  la medianoche.

SE COBRA ANTES DE LLAMAR, Y SE CONFIRMA EN SU PROPIO COMMIT
----------------------------------------------------------
El contador se incrementa con un UPDATE condicional (`WHERE llamadas < tope`) y se hace
commit en el acto: si la ruta falla después, la llamada al proveedor ya ocurrió y ya costó.
Las rutas que cobran no escriben nada más en la base, así que el commit no arrastra nada.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.acceso.dependencias import aplicar_limite, usuario_autenticado
from app.acceso.limitador import entero_de_entorno, limite_llm_por_minuto
from app.db.session import obtener_db
from app.exceptions import LimiteExcedido
from app.modelos.acceso import ConsumoLLM

ZONA = ZoneInfo("America/Mexico_City")
DEFAULT_TOPE_DIARIO = 500


def tope_diario() -> int:
    """Llamadas al LLM por despacho por día (`FISCALITO_TOPE_LLM_DIARIO_LLAMADAS`)."""
    return entero_de_entorno("FISCALITO_TOPE_LLM_DIARIO_LLAMADAS", DEFAULT_TOPE_DIARIO)


def _hoy_y_espera(ahora: datetime | None = None) -> tuple[date, float]:
    """El día en la Ciudad de México y los segundos que faltan para que termine."""
    momento = (ahora or datetime.now(ZONA)).astimezone(ZONA)
    manana = datetime.combine(momento.date() + timedelta(days=1), time(0), tzinfo=ZONA)
    return momento.date(), (manana - momento).total_seconds()


def cobrar_dia(db: Session, despacho_id: str, tope: int, ahora: datetime | None = None) -> int:
    """
    Suma una llamada al día del despacho, o 429 si ya llegó al tope. Devuelve el total.

    El UPDATE condicional es el que sostiene el tope con requests simultáneos: dos que leen
    "499" no pueden escribir los dos "500".
    """
    dia, espera = _hoy_y_espera(ahora)
    filtro = (ConsumoLLM.despacho_id == despacho_id, ConsumoLLM.dia == dia)
    hecho = db.execute(
        update(ConsumoLLM)
        .where(*filtro, ConsumoLLM.llamadas < tope)
        .values(llamadas=ConsumoLLM.llamadas + 1)
    )
    if hecho.rowcount == 0:
        existe = db.scalar(select(ConsumoLLM.llamadas).where(*filtro))
        if existe is not None:
            raise LimiteExcedido(
                f"Tu despacho llegó al tope de {tope} consultas al asistente de hoy. Los "
                "cálculos siguen funcionando; las explicaciones vuelven mañana.",
                reintentar_en=espera,
            )
        try:
            with db.begin_nested():
                db.add(ConsumoLLM(despacho_id=despacho_id, dia=dia, llamadas=1))
        except IntegrityError:
            # Otro request creó el renglón entre el UPDATE y el INSERT: se reintenta una vez.
            return cobrar_dia(db, despacho_id, tope, ahora)
    db.commit()
    return int(db.scalar(select(ConsumoLLM.llamadas).where(*filtro)) or 0)


class CobradorLLM:
    """
    Lo que una ruta pide para gastar LLM. `cobrar()` antes de cada llamada al proveedor.

    El despacho se resuelve **perezosamente**: una ruta de cálculo que no pide explicación
    no toca la base ni crea al usuario.
    """

    def __init__(self, uid: str, db: Session) -> None:
        self.uid = uid
        self.db = db
        self._despacho_id: str | None = None

    @property
    def despacho_id(self) -> str:
        if self._despacho_id is None:
            from app.tenancy import asegurar_usuario

            self._despacho_id = asegurar_usuario(self.db, self.uid).despacho_id
        return self._despacho_id

    def cobrar(self) -> None:
        """Una llamada al LLM: límite por minuto del usuario y tope diario del despacho."""
        aplicar_limite(f"llm:{self.uid}", limite_llm_por_minuto(), "consultas al asistente")
        cobrar_dia(self.db, self.despacho_id, tope_diario())


def cobrador_llm(
    uid: str = Depends(usuario_autenticado), db: Session = Depends(obtener_db)
) -> CobradorLLM:
    """Dependencia de FastAPI para las rutas que pueden llamar al LLM."""
    return CobradorLLM(uid, db)
