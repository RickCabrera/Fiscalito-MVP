"""
Motor de nomina: SBC, cuotas IMSS/Infonavit, ISR de sueldos y salarios.

Convencion del modulo: TODO es `Decimal` con `ROUND_HALF_UP` a 2 decimales
(PLAN_NOMINA §3.1). El motor fiscal viejo (`app/fiscal_engine/`) trabaja en
float; las fronteras entre los dos son explicitas y estan documentadas donde
ocurren.

La referencia documental con fuentes de cada valor esta en
`knowledge_base/nomina/` (docs 20-26). Esos documentos NO son fuente de
calculo: el codigo es la implementacion y ellos la justificacion.
"""
