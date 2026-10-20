"""Esquemas de la DIOT con layout 2025 (P3-05)."""

from typing import Literal

from pydantic import BaseModel, Field


class ConfigProveedorDiotSchema(BaseModel):
    """
    Clasificación de un proveedor en la DIOT. `None` = se deduce de los CFDI.

    Defaults (DP-3, documentados): IVA acreditable "exclusivamente de actividades gravadas";
    el 8 % se reporta en la región fronteriza NORTE; la importación, como bienes tangibles;
    efectos fiscales 01 (Sí).
    """

    tipo_tercero: Literal["04", "05", "15"] | None = None
    tipo_operacion: Literal["02", "03", "06", "07", "08", "85", "87"] | None = None
    region_8: Literal["norte", "sur"] = "norte"
    importacion: Literal["tangibles", "intangibles"] = "tangibles"
    asignacion_iva: Literal["gravadas", "proporcion"] = "gravadas"
    iva_no_acreditable: Literal["", "proporcion", "requisitos", "exentas", "no_objeto"] = ""
    id_fiscal: str = Field("", max_length=40)
    nombre_extranjero: str = Field("", max_length=300)
    pais: str = Field("", max_length=3)
    jurisdiccion: str = Field("", max_length=300)
    efectos_fiscales: Literal["01", "02"] = "01"
