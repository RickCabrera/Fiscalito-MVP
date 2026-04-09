"""
Constantes compartidas del sistema fiscal.

Centraliza diccionarios y valores que se usan en multiples modulos
para evitar duplicacion (principio DRY).
"""

# Nombres de meses del calendario fiscal
NOMBRES_MESES: dict[int, str] = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Nombres de bimestres (formato completo)
NOMBRES_BIMESTRES: dict[int, str] = {
    1: "Enero-Febrero", 2: "Marzo-Abril", 3: "Mayo-Junio",
    4: "Julio-Agosto", 5: "Septiembre-Octubre", 6: "Noviembre-Diciembre",
}

# Nombres descriptivos de regimenes fiscales SAT
NOMBRES_REGIMEN: dict[str, str] = {
    "626": "RESICO (Regimen Simplificado de Confianza)",
    "612": "Actividad Empresarial y Profesional",
    "605": "Sueldos y Salarios",
    "606": "Arrendamiento",
    "625": "Plataformas Tecnologicas",
    "621": "Incorporacion Fiscal (RIF)",
}

# Tope de ingresos anuales para permanecer en RESICO ($3.5M)
TOPE_RESICO_ANUAL: float = 3_500_000.00

# Regimenes con pagos provisionales acumulativos (Art. 106/116 LISR).
# En estos regimenes cada mes se calcula sobre la base acumulada desde
# enero y se restan los ISR ya causados en meses anteriores.
REGIMENES_ACUMULATIVOS: set[str] = {"612", "606"}
