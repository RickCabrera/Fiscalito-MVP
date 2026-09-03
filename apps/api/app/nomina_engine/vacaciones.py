"""
La escala de vacaciones del patron, y su validacion contra la ley. (O-03)

VIVE APARTE DE `integracion.py` POR EL TOPE DE 300 LINEAS
---------------------------------------------------------
`apps/api/CLAUDE.md` lo pide y O-03 llevo aquel archivo de 244 a 317. El corte
no es arbitrario: aqui queda la PRESTACION —que el patron define y la ley acota—
y alla se queda la formula del Art. 27, que no es negociable.

`integracion.py` re-exporta lo de aqui, asi que quien importaba de alli sigue
funcionando.

QUE ES ESTO Y QUE NO
--------------------
El Art. 76 LFT fija el **minimo** de dias de vacaciones por antiguedad; el
patron puede otorgar mas, y muchos lo hacen (§D5 deja el minimo de ley solo como
default). Esa escala superior integra el SBC por el Art. 27 LSS, asi que tiene
que poder capturarse — y **no puede quedar por debajo de la ley**, porque
subintegrar el SBC baja todas las cuotas.
"""

from __future__ import annotations

from app.exceptions import FiscalValidationError


def dias_vacaciones_de_ley(anios_servicio_cumplidos: int) -> int:
    """
    Dias de vacaciones que marca el Art. 76 LFT segun la antiguedad.

    `anios_servicio_cumplidos` son años CUMPLIDOS: **0 es el alta nueva**, que
    para integrar el SBC usa los 12 dias que va a devengar en su primer año.
    Rechazar el 0 haria imposible calcular el SBC de un alta — que es
    justamente el caso con 5 dias habiles para presentar el aviso.

    Escala vigente desde el 1-ene-2023 (reforma DOF 27-12-2022): 12 dias el
    primer año, mas 2 por cada año subsecuente hasta llegar a 20, y a partir
    del sexto año 2 dias mas por cada 5 de servicios.

    La regla NO es una tabla cerrada: 36-40 años dan 34 dias, y asi
    sucesivamente. Un trabajador de 37 años de antiguedad existe.
    """
    if anios_servicio_cumplidos < 0:
        raise FiscalValidationError(
            f"Los años de servicio no pueden ser negativos: {anios_servicio_cumplidos}."
        )
    if anios_servicio_cumplidos <= 1:
        return 12
    if anios_servicio_cumplidos <= 5:
        return 12 + 2 * (anios_servicio_cumplidos - 1)
    quinquenios = -(-(anios_servicio_cumplidos - 5) // 5)  # techo de la division
    return 20 + 2 * quinquenios

TablaVacaciones = tuple[tuple[int, int], ...]
"""
Escala de vacaciones propia del patron: `((anios_cumplidos, dias), ...)`.

Es una PRESTACION, no una tabla fiscal: el Art. 76 fija el **minimo** y el
patron puede otorgar mas. Por eso se captura y se valida contra la ley, en vez
de vivir codificada.
"""

# Techo de cordura, no de ley.
#
# **La ley no pone maximo**, y a proposito: un patron puede dar lo que quiera.
# Este numero existe contra el TYPEO, que es el riesgo real de un formulario:
# `200` en vez de `20` produce un factor de 1.1781 contra 1.0521 —un **12 % mas
# en todas las cuotas**— y **el clamp del Art. 28 no lo caza**, porque el SBC
# resultante sigue muy por debajo del tope de 25 UMA. Pasa callado.
#
# Es el mismo guard que `factor_integracion` ya tiene para la prima ("pasar 25
# en vez de 0.25"), que hasta O-03 no existia para los dias. 60 es el triple del
# maximo de la escala de ley (20 dias) y mas del doble de lo que otorga un
# patron generoso: quien de verdad de mas que eso, lo dira y se sube la
# constante con su motivo.
MAXIMO_DIAS_VACACIONES = 60


def validar_tabla_vacaciones(tabla: TablaVacaciones) -> None:
    """
    Rechaza una escala de vacaciones por DEBAJO del minimo del Art. 76 LFT.

    Se valida renglon por renglon y no en promedio: una escala que diera de mas
    en el año 1 y de menos en el 5 subintegraria el SBC de quien lleva cinco
    años, y el promedio la taparia.

    Superiores se aceptan hasta `MAXIMO_DIAS_VACACIONES`, que es un techo contra
    el typeo y no una regla legal — ver la constante.

    Raises:
        FiscalValidationError: con el renglon infractor y lo que exige la ley.
            No dice "la tabla es invalida": dice cual y por que, porque el que
            la captura tiene que poder arreglarla sin adivinar.
    """
    for anios, dias in tabla:
        if anios < 0:
            raise FiscalValidationError(
                f"Los años de servicio no pueden ser negativos: {anios}."
            )
        minimo = dias_vacaciones_de_ley(anios)
        if dias < minimo:
            raise FiscalValidationError(
                f"La tabla de vacaciones da {dias} días al año {anios} de servicio y el "
                f"mínimo de ley son {minimo} (Art. 76 LFT, reforma DOF 27-12-2022). "
                f"Otorgar menos subintegraría el SBC y con él todas las cuotas."
            )
        if dias > MAXIMO_DIAS_VACACIONES:
            raise FiscalValidationError(
                f"La tabla de vacaciones da {dias} días al año {anios} de servicio, y el "
                f"tope que acepta esta app son {MAXIMO_DIAS_VACACIONES}. La ley no pone "
                f"máximo: este límite es contra el error de captura, porque un cero de "
                f"más infla el factor de integración y con él TODAS las cuotas, sin que "
                f"el tope de 25 UMA del Art. 28 llegue a notarlo. Si el patrón de verdad "
                f"otorga más, hay que subir el límite a propósito."
            )


def dias_vacaciones_efectivos(
    anios_servicio_cumplidos: int, tabla: TablaVacaciones | None = None
) -> int:
    """
    Dias de vacaciones que le tocan, con la escala del patron si la hay.

    SIN TABLA es la ley, igual que siempre.

    CON TABLA se toma el renglon **MAS ALTO EN DIAS** de entre los que aplican a
    su antiguedad —los de año menor o igual al suyo— y se devuelve
    **`max(ese, la ley)`**.

    Es "el mas alto en dias" y **no** "el del año mas grande", y la diferencia
    importa con una tabla no monotona: con `((1, 30), (5, 20))`, alguien de 5
    años recibe **30**, no 20. Es deliberado y es la direccion conservadora — un
    patron que capturo 30 dias al año 1 no se los quita a los cinco años— pero
    hay que leerlo asi y no como "el ultimo renglon".

    EL `max` CONTRA LA LEY NO ES PARANOIA, Y AQUI ESTA EL CASO
    ----------------------------------------------------------
    Una tabla capturada hasta el año 10 con 30 dias, y un trabajador con 11
    años. Sin `max`, "por encima del ultimo renglon se cae a la ley" le daria
    **24 dias** (Art. 76 para 11 años) y su SBC **bajaria al ganar antigüedad**.
    El Art. 27 LSS integra lo que el patron **otorga**, no el minimo: nadie
    pierde una prestacion por cumplir un año mas. Y subintegrar es la direccion
    que este repo trata siempre como la mala.

    La tabla no necesita estar ordenada: se busca el maximo, no el ultimo.
    """
    de_ley = dias_vacaciones_de_ley(anios_servicio_cumplidos)
    if not tabla:
        return de_ley
    aplicables = [dias for anios, dias in tabla if anios <= anios_servicio_cumplidos]
    if not aplicables:
        # Su antigüedad es menor que el primer renglon capturado: manda la ley.
        return de_ley
    return max(max(aplicables), de_ley)
