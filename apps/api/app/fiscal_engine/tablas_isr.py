"""
Tablas de ISR Mexico 2026.
Fuente: Ley del ISR, Art. 96 (tabla mensual) y Art. 113-E (RESICO).
Anexo 8 RMF 2026, DOF 28/dic/2025.

Estas tablas se usan para calcular el ISR causado segun el regimen
del contribuyente. Se actualizan anualmente por el SAT.

Valores transcritos textualmente del PDF oficial publicado en el DOF:
https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rmf/anexos/Anexo-8-RMF-2026_DOF-28122025.pdf

- Tabla mensual: Anexo 8, Sección B, Fracción V (Art. 96 LISR).
- Tabla anual: Anexo 8, Sección C, Fracción II (Arts. 97 y 152 LISR).
"""


# ============================================================
# RESICO — Tasas fijas por rango de ingresos (Art. 113-E LISR)
# Aplica a personas fisicas con ingresos <= 3.5 MDP anuales
# ============================================================

RESICO_TASAS_MENSUALES = [
    # (limite_inferior, limite_superior, tasa)
    # RESICO PF es MENSUAL (Art. 113-E). NO existe tabla bimestral.
    # Los bimestrales eran del RIF (Art. 111, eliminado en 2022).
    (0.01, 25_000.00, 0.0100),       # 1.00%
    (25_000.01, 50_000.00, 0.0110),  # 1.10%
    (50_000.01, 83_333.33, 0.0150),  # 1.50%
    (83_333.34, 208_333.33, 0.0200), # 2.00%
    (208_333.34, 291_666.67, 0.0250),# 2.50%
]


# ============================================================
# Regimen General / Act. Empresarial / Honorarios
# Tabla mensual Art. 96 LISR (2026)
# ============================================================

TABLA_ISR_MENSUAL = [
    # (limite_inferior, limite_superior, cuota_fija, tasa_excedente)
    # Fuente: Anexo 8 RMF 2026, Seccion B Fraccion V. Art. 96 LISR.
    # Valores TEXTUALES del PDF oficial DOF 28/dic/2025.
    (0.01, 844.59, 0.00, 0.0192),
    (844.60, 7_168.51, 16.22, 0.0640),
    (7_168.52, 12_598.02, 420.95, 0.1088),
    (12_598.03, 14_644.64, 1_011.68, 0.16),
    (14_644.65, 17_533.64, 1_339.14, 0.1792),
    (17_533.65, 35_362.83, 1_856.84, 0.2136),
    (35_362.84, 55_736.68, 5_665.16, 0.2352),
    (55_736.69, 106_410.50, 10_457.09, 0.30),
    (106_410.51, 141_880.66, 25_659.23, 0.32),
    (141_880.67, 425_641.99, 37_009.69, 0.34),
    (425_642.00, float("inf"), 133_488.54, 0.35),
]


# ============================================================
# Tabla anual Art. 152 LISR (2026)
# ============================================================

TABLA_ISR_ANUAL = [
    # (limite_inferior, limite_superior, cuota_fija, tasa_excedente)
    # Fuente: Anexo 8 RMF 2026, Seccion C Fraccion II. Arts. 97 y 152 LISR.
    # Valores TEXTUALES del PDF oficial DOF 28/dic/2025.
    (0.01, 10_135.11, 0.00, 0.0192),
    (10_135.12, 86_022.11, 194.59, 0.0640),
    (86_022.12, 151_176.19, 5_051.37, 0.1088),
    (151_176.20, 175_735.66, 12_140.13, 0.16),
    (175_735.67, 210_403.69, 16_069.64, 0.1792),
    (210_403.70, 424_353.97, 22_282.14, 0.2136),
    (424_353.98, 668_840.14, 67_981.92, 0.2352),
    (668_840.15, 1_276_925.98, 125_485.07, 0.30),
    (1_276_925.99, 1_702_567.97, 307_910.81, 0.32),
    (1_702_567.98, 5_107_703.92, 444_116.23, 0.34),
    (5_107_703.93, float("inf"), 1_601_862.46, 0.35),
]


# ============================================================
# IVA
# ============================================================

TASA_IVA = 0.16  # 16% general
TASA_IVA_FRONTERA = 0.08  # 8% zona fronteriza (si aplica)
TASA_RETENCION_IVA = 2 / 3  # Retencion de 2/3 del IVA (personas morales a fisicas)


# ============================================================
# Deducciones personales (declaracion anual)
# ============================================================

LIMITE_DEDUCCIONES_PERSONALES_UMA = 5  # 5 UMAs anuales o 15% de ingresos
UMA_DIARIA_2026 = 117.22  # Valor UMA 2026
LIMITE_DEDUCCIONES_PERSONALES = LIMITE_DEDUCCIONES_PERSONALES_UMA * UMA_DIARIA_2026 * 365


def generar_tabla_acumulada(meses: int) -> list[tuple[float, float, float, float]]:
    """
    Genera la tabla ISR acumulada para pagos provisionales Art. 106.

    Para el mes N, los limites inferiores, superiores y cuotas fijas
    de la tabla base (Art. 96) se multiplican por N.
    Las tasas porcentuales NO cambian.

    Args:
        meses: Numero de meses acumulados (1=enero, 2=feb, ..., 12=dic)
    """
    return [
        (
            round(lim_inf * meses, 2) if lim_inf > 0.01 else 0.01,
            round(lim_sup * meses, 2) if lim_sup != float("inf") else float("inf"),
            round(cuota * meses, 2),
            tasa,  # La tasa NO cambia
        )
        for lim_inf, lim_sup, cuota, tasa in TABLA_ISR_MENSUAL
    ]
