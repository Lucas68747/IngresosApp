"""Normalización de dominios (patentes).

Se guardan siempre en mayúsculas y sin espacios ni guiones, así
"ab 123 cd", "AB-123-CD" y "AB123CD" son el mismo vehículo al buscar.
Para mostrarlos se separan los grupos de letras y de números.
No se rechaza ningún formato: también entran motos, patentes viejas o
extranjeras.
"""

from __future__ import annotations

import re

_SEPARADORES = re.compile(r"[\s\-\.·_]+")
_GRUPOS = re.compile(r"[A-Z]+|\d+|[^A-Z\d]+")


def normalizar_dominio(texto: str | None) -> str:
    if not texto:
        return ""
    return _SEPARADORES.sub("", texto).upper()


def formatear_dominio(dominio: str | None) -> str:
    """Separa letras y números: AB123CD → AB 123 CD, ABC123 → ABC 123."""
    return " ".join(_GRUPOS.findall(normalizar_dominio(dominio)))
