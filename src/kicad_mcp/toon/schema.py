"""Modelos pydantic del estado normalizado que consume el encoder TOON v1.

Este schema es la contraparte ejecutable de `docs/specs/toon-v1.md §1`. El
bridge produce estas estructuras; el encoder solo las lee. Toda entrada que
cruza esta frontera (proceso ↔ IPC) se valida en el borde (regla #5).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Pin(BaseModel):
    """Un pin de un componente. ``net=None`` ⇒ pin sin conectar (emite ``>-``)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    p: str = Field(description="Identificador del pin (número si existe; nombre si no)")
    name: str | None = Field(default=None, description="Nombre lógico del pin (no se emite)")
    net: str | None = Field(default=None, description="Net conectada, o None si sin conectar")


class Component(BaseModel):
    """Un componente (símbolo o footprint) del proyecto."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    ref: str = Field(description="Referencia (p. ej. ``U1``, ``R42``)")
    value: str = Field(description="Valor visible (p. ej. ``100nF``, ``10k``)")
    lib: str | None = Field(
        default=None,
        description=(
            "Identificador de librería (`Device:R`). No se emite en TOON: "
            "recuperable vía ``get_component_detail`` (spec §2)."
        ),
    )
    x: float = Field(description="Posición X en mm")
    y: float = Field(description="Posición Y en mm")
    pins: tuple[Pin, ...] = Field(default=(), description="Pines del componente")


class NormalizedState(BaseModel):
    """Estado completo de un esquemático o PCB, tal como sale del bridge."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    kind: Literal["sch", "pcb"] = Field(description="Tipo de documento")
    snap: int = Field(ge=0, description="Identificador de snapshot (arquitectura §4.3)")
    components: tuple[Component, ...] = Field(description="Componentes del proyecto")
