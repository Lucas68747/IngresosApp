"""Normalización de dominios (patentes).

Se guardan siempre en mayúsculas y sin espacios ni guiones, así
"ab 123 cd", "AB-123-CD" y "AB123CD" son el mismo vehículo al buscar.
Para mostrarlos se agregan los espacios de los formatos argentinos.
No se rechaza ningún formato: también entran motos, patentes viejas o
extranjeras.
"""

from __future__ import annotations

import re

_SEPARADORES = re.compile(r"[\s\-\.·_]+")
_MERCOSUR = re.compile(r"^([A-Z]{2})(\d{3})([A-Z]{2})$")  # AB123CD
_ANTERIOR = re.compile(r"^([A-Z]{3})(\d{3})$")  # ABC123


def normalizar_dominio(texto: str | None) -> str:
    if not texto:
        return ""
    return _SEPARADORES.sub("", texto).upper()


def formatear_dominio(dominio: str | None) -> str:
    dominio = normalizar_dominio(dominio)
    if m := _MERCOSUR.match(dominio):
        return " ".join(m.groups())
    if m := _ANTERIOR.match(dominio):
        return " ".join(m.groups())
    return dominio
