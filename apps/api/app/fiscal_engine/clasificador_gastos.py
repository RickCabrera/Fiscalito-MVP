"""
Clasificador automatico de deducibilidad de gastos.

Usa la ClaveProdServ del catalogo SAT para determinar si un gasto
es deducible para la actividad empresarial del contribuyente.
Art. 105 LISR: solo gastos estrictamente indispensables.
"""

from __future__ import annotations

# Divisiones que son SIEMPRE consumo personal
DIVISIONES_PERSONALES = frozenset({
    "12",  # Quimicos/detergentes domesticos
    "14",  # Papel higienico, kleenex, servilletas
    "24",  # Contenedores hogar (ziploc, tupperware)
    "41",  # Suavizante, productos limpieza industrial->hogar
    "42",  # Instrumental medico personal (hisopos, etc)
    "47",  # Limpieza hogar (clorox, pinol, bolsas basura)
    "49",  # Deportes/recreacion personal
    "50",  # Alimentos y bebidas
    "51",  # Medicamentos/farmacia
    "52",  # Muebles/electrodomesticos hogar
    "53",  # Cuidado personal/ropa
    "54",  # Joyeria/relojeria
    "56",  # Colchones/accesorios hogar
    "85",  # Servicios salud personal
    "90",  # Restaurantes/catering
    "91",  # Deportes/recreacion servicios
})

# Divisiones que son SIEMPRE gastos de negocio
DIVISIONES_DEDUCIBLES = frozenset({
    "15",  # Combustibles (gasolina)
    "26",  # Energia electrica/solar/gas
    "43",  # Equipo TI/telecomunicaciones/software
    "44",  # Equipo y papeleria oficina
    "60",  # Mobiliario oficina
    "78",  # Transporte/estacionamiento/envios
    "80",  # Servicios gestion/consultoria/arrendamiento
    "81",  # Servicios ingenieria/investigacion
    "82",  # Publicidad/marketing
    "83",  # Servicios publicos (agua, luz del negocio)
    "84",  # Servicios contables/legales/financieros
})


# Divisiones relacionadas: si la actividad es X, los gastos en Y son insumos
# Mapea division de actividad -> divisiones de gasto que se vuelven deducibles
DIVISIONES_RELACIONADAS: dict[str, frozenset[str]] = {
    "90": frozenset({"50", "51"}),  # Restaurantes -> alimentos, bebidas
    "85": frozenset({"51", "42"}),  # Servicios salud -> medicamentos, instrumental
    "91": frozenset({"49"}),        # Servicios deportivos -> equipo deportivo
    "53": frozenset({"52", "54"}),  # Moda/ropa -> muebles exhibicion, joyeria
    "56": frozenset({"52"}),        # Colchones/hogar -> muebles
}


def obtener_division(clave_prod_serv: str) -> str:
    """Extrae los primeros 2 digitos (division) de la ClaveProdServ."""
    return clave_prod_serv[:2] if len(clave_prod_serv) >= 2 else ""


def inferir_actividad_contribuyente(facturas_emitidas: list) -> set[str]:
    """
    Infiere las divisiones de actividad del contribuyente
    basandose en las ClaveProdServ de sus facturas emitidas (ingresos).
    """
    divisiones: set[str] = set()
    for f in facturas_emitidas:
        div = obtener_division(f.clave_prod_serv)
        if div:
            divisiones.add(div)
    return divisiones


def es_gasto_deducible(
    clave_prod_serv: str,
    divisiones_actividad: set[str],
) -> bool:
    """
    Determina si un gasto es deducible para el contribuyente.

    Nivel 1: Si la division es SIEMPRE personal -> False
    Nivel 2: Si la division es SIEMPRE deducible -> True
    Nivel 3 (grises): Si la division coincide con la actividad -> True
    Default: True (beneficio de la duda)

    EXCEPCION: Si la actividad del contribuyente coincide con una
    division "personal", esa division se vuelve deducible para el.
    Ejemplo: restaurantero (90) -> gastos de alimentos (50) SI deducibles.
    """
    division = obtener_division(clave_prod_serv)

    if not division:
        return True  # Sin clave -> beneficio de la duda

    # EXCEPCION: si el contribuyente trabaja en esa misma categoria,
    # el gasto puede ser materia prima / insumo del negocio
    if division in divisiones_actividad:
        return True

    # EXCEPCION: divisiones relacionadas (ej: restaurantero puede deducir alimentos)
    for act in divisiones_actividad:
        relacionadas = DIVISIONES_RELACIONADAS.get(act, frozenset())
        if division in relacionadas:
            return True

    # Nivel 1: divisiones siempre personales
    if division in DIVISIONES_PERSONALES:
        return False

    # Nivel 2: divisiones siempre deducibles
    if division in DIVISIONES_DEDUCIBLES:
        return True

    # Nivel 3: grises -> beneficio de la duda
    return True


def clasificar_egresos(
    egresos: list,
    facturas_emitidas: list,
) -> tuple[list, list, float]:
    """
    Filtra los egresos separando deducibles de personales.

    Args:
        egresos: Lista de CFDIs clasificados como gastos
        facturas_emitidas: Lista de CFDIs emitidos (para inferir actividad)

    Returns:
        (deducibles, personales, total_excluido)
    """
    divisiones_actividad = inferir_actividad_contribuyente(facturas_emitidas)

    deducibles = []
    personales = []

    for f in egresos:
        if es_gasto_deducible(f.clave_prod_serv, divisiones_actividad):
            deducibles.append(f)
        else:
            personales.append(f)

    total_excluido = sum(f.base_gravable for f in personales)

    return deducibles, personales, total_excluido
