"""
Generador de calendario fiscal personalizado.

Genera obligaciones fiscales segun el tipo de contribuyente, regimen y RFC.
"""

from __future__ import annotations
from datetime import date, timedelta
from dataclasses import dataclass


@dataclass
class ObligacionFiscal:
    """Una obligacion fiscal con fecha limite."""
    nombre: str
    descripcion: str
    fecha_limite: str
    periodicidad: str
    completada: bool = False


def _obtener_sexto_digito_rfc(rfc: str) -> int | None:
    """Obtiene el 6to digito numerico del RFC para ajuste de fecha."""
    # RFC persona fisica: 4 letras + 6 digitos + 3 homoclave = 13
    # RFC persona moral: 3 letras + 6 digitos + 3 homoclave = 12
    # El 6to digito numerico esta en posicion variable
    digitos = [c for c in rfc if c.isdigit()]
    if len(digitos) >= 6:
        return int(digitos[5])
    return None


def _dias_habiles_extra(sexto_digito: int | None) -> int:
    """Dias habiles extra despues del dia 17 segun 6to digito del RFC."""
    if sexto_digito is None:
        return 0
    mapping = {
        1: 1, 2: 1,
        3: 2, 4: 2,
        5: 3, 6: 3,
        7: 4, 8: 4,
        9: 5, 0: 5,
    }
    return mapping.get(sexto_digito, 0)


def _fecha_limite_dia_17(year: int, month: int, dias_extra: int) -> str:
    """Calcula fecha limite partiendo del dia 17 mas dias habiles extra."""
    base = date(year, month, 17)
    dias_agregados = 0
    current = base
    while dias_agregados < dias_extra:
        current += timedelta(days=1)
        # Saltar fines de semana (lunes=0 ... domingo=6)
        if current.weekday() < 5:
            dias_agregados += 1
    return current.isoformat()


def generar_calendario(
    contributor_type: str,
    regimen: str,
    rfc: str,
    year: int | None = None,
) -> list[ObligacionFiscal]:
    """
    Genera calendario de obligaciones fiscales segun el tipo de contribuyente.

    Args:
        contributor_type: asalariado, independiente, arrendamiento, plataformas, pyme
        regimen: codigo de regimen fiscal (626, 612, 606, 625, 605)
        rfc: RFC del contribuyente (para calcular ajuste de fecha)
        year: anio fiscal (por defecto el anio actual)
    """
    year = year or date.today().year
    sexto_digito = _obtener_sexto_digito_rfc(rfc)
    dias_extra = _dias_habiles_extra(sexto_digito)
    obligaciones: list[ObligacionFiscal] = []

    if contributor_type == "asalariado":
        # Solo declaracion anual en abril
        obligaciones.append(ObligacionFiscal(
            nombre="Declaracion anual",
            descripcion="Declaracion anual de personas fisicas con deducciones personales",
            fecha_limite=f"{year}-04-30",
            periodicidad="anual",
        ))

    elif contributor_type == "independiente":
        if regimen == "626":
            # RESICO PF: MENSUAL (Art. 113-E). Los bimestrales eran del RIF.
            for mes in range(1, 12):
                mes_vencimiento = mes + 1
                obligaciones.append(ObligacionFiscal(
                    nombre=f"Declaracion mensual RESICO mes {mes}",
                    descripcion=f"ISR RESICO + IVA del mes {mes}",
                    fecha_limite=_fecha_limite_dia_17(year, mes_vencimiento, dias_extra),
                    periodicidad="mensual",
                ))
            # Diciembre se presenta en enero del siguiente anio
            obligaciones.append(ObligacionFiscal(
                nombre="Declaracion mensual RESICO mes 12",
                descripcion="ISR RESICO + IVA del mes 12",
                fecha_limite=_fecha_limite_dia_17(year + 1, 1, dias_extra),
                periodicidad="mensual",
            ))
        else:
            # Regimen 612: mensual
            for mes in range(1, 12):
                mes_vencimiento = mes + 1
                obligaciones.append(ObligacionFiscal(
                    nombre=f"Declaracion mensual mes {mes}",
                    descripcion=f"ISR + IVA del mes {mes}",
                    fecha_limite=_fecha_limite_dia_17(year, mes_vencimiento, dias_extra),
                    periodicidad="mensual",
                ))
            # Diciembre se presenta en enero del siguiente anio
            obligaciones.append(ObligacionFiscal(
                nombre="Declaracion mensual mes 12",
                descripcion="ISR + IVA del mes 12",
                fecha_limite=_fecha_limite_dia_17(year + 1, 1, dias_extra),
                periodicidad="mensual",
            ))

        # Declaracion anual
        obligaciones.append(ObligacionFiscal(
            nombre="Declaracion anual",
            descripcion="Declaracion anual del ejercicio fiscal",
            fecha_limite=f"{year + 1}-04-30",
            periodicidad="anual",
        ))

    elif contributor_type == "arrendamiento":
        # Mensual + anual
        for mes in range(1, 12):
            mes_vencimiento = mes + 1
            obligaciones.append(ObligacionFiscal(
                nombre=f"Declaracion mensual mes {mes}",
                descripcion=f"ISR + IVA arrendamiento del mes {mes}",
                fecha_limite=_fecha_limite_dia_17(year, mes_vencimiento, dias_extra),
                periodicidad="mensual",
            ))
        obligaciones.append(ObligacionFiscal(
            nombre="Declaracion mensual mes 12",
            descripcion="ISR + IVA arrendamiento del mes 12",
            fecha_limite=_fecha_limite_dia_17(year + 1, 1, dias_extra),
            periodicidad="mensual",
        ))
        obligaciones.append(ObligacionFiscal(
            nombre="Declaracion anual",
            descripcion="Declaracion anual del ejercicio fiscal",
            fecha_limite=f"{year + 1}-04-30",
            periodicidad="anual",
        ))

    elif contributor_type == "plataformas":
        # Mensual + anual (puede ser solo anual si retenciones definitivas)
        for mes in range(1, 12):
            mes_vencimiento = mes + 1
            obligaciones.append(ObligacionFiscal(
                nombre=f"Declaracion mensual mes {mes}",
                descripcion=f"ISR + IVA plataformas del mes {mes}",
                fecha_limite=_fecha_limite_dia_17(year, mes_vencimiento, dias_extra),
                periodicidad="mensual",
            ))
        obligaciones.append(ObligacionFiscal(
            nombre="Declaracion mensual mes 12",
            descripcion="ISR + IVA plataformas del mes 12",
            fecha_limite=_fecha_limite_dia_17(year + 1, 1, dias_extra),
            periodicidad="mensual",
        ))
        obligaciones.append(ObligacionFiscal(
            nombre="Declaracion anual",
            descripcion="Declaracion anual del ejercicio fiscal",
            fecha_limite=f"{year + 1}-04-30",
            periodicidad="anual",
        ))

    elif contributor_type == "pyme":
        # Mensual + anual + DIOT mensual
        for mes in range(1, 12):
            mes_vencimiento = mes + 1
            obligaciones.append(ObligacionFiscal(
                nombre=f"Declaracion mensual mes {mes}",
                descripcion=f"ISR + IVA del mes {mes}",
                fecha_limite=_fecha_limite_dia_17(year, mes_vencimiento, dias_extra),
                periodicidad="mensual",
            ))
            obligaciones.append(ObligacionFiscal(
                nombre=f"DIOT mes {mes}",
                descripcion=f"Declaracion Informativa de Operaciones con Terceros del mes {mes}",
                fecha_limite=_fecha_limite_dia_17(year, mes_vencimiento, dias_extra),
                periodicidad="mensual",
            ))
        # Diciembre
        obligaciones.append(ObligacionFiscal(
            nombre="Declaracion mensual mes 12",
            descripcion="ISR + IVA del mes 12",
            fecha_limite=_fecha_limite_dia_17(year + 1, 1, dias_extra),
            periodicidad="mensual",
        ))
        obligaciones.append(ObligacionFiscal(
            nombre="DIOT mes 12",
            descripcion="Declaracion Informativa de Operaciones con Terceros del mes 12",
            fecha_limite=_fecha_limite_dia_17(year + 1, 1, dias_extra),
            periodicidad="mensual",
        ))
        obligaciones.append(ObligacionFiscal(
            nombre="Declaracion anual",
            descripcion="Declaracion anual del ejercicio fiscal",
            fecha_limite=f"{year + 1}-04-30",
            periodicidad="anual",
        ))

    return obligaciones
