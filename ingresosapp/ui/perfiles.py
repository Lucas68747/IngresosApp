"""Textos de ejemplo según el tipo de lugar donde se usa la app.

La app funciona igual en todos los casos; solo cambian los ejemplos y las
ayudas para que hablen el idioma de cada garita.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..db import BaseDeDatos


@dataclass(frozen=True)
class Perfil:
    clave: str
    nombre: str
    etiqueta_empresa: str
    ej_empresa: str
    ej_destino: str
    ej_autorizo: str
    ej_puesto: str
    ej_agenda_nombre: str
    agenda: str


PERFILES = {
    "barrio": Perfil(
        clave="barrio",
        nombre="Barrio cerrado o privado",
        etiqueta_empresa="Empresa o motivo",
        ej_empresa="ej.: delivery, obra",
        ej_destino="ej.: Lote 34, Casa 12",
        ej_autorizo="ej.: Pérez, por teléfono",
        ej_puesto="Barrio Los Álamos · Guardia de acceso",
        ej_agenda_nombre="Lote 34",
        agenda="cada lote o casa con el teléfono de quienes viven ahí y quién puede autorizar visitas",
    ),
    "parque": Perfil(
        clave="parque",
        nombre="Parque industrial",
        etiqueta_empresa="Empresa",
        ej_empresa="ej.: Transportes del Sur",
        ej_destino="ej.: Planta 2, Depósito",
        ej_autorizo="ej.: jefe de planta",
        ej_puesto="Parque Industrial Norte · Garita principal",
        ej_agenda_nombre="Molinos del Plata S.A.",
        agenda="cada empresa o planta con su teléfono y a quién avisar cuando llega alguien",
    ),
    "empresa": Perfil(
        clave="empresa",
        nombre="Empresa o planta",
        etiqueta_empresa="Empresa",
        ej_empresa="ej.: proveedor, cliente",
        ej_destino="ej.: Oficina, Depósito, Sector 3",
        ej_autorizo="ej.: Recepción",
        ej_puesto="Planta San Martín · Portería",
        ej_agenda_nombre="Depósito",
        agenda="cada sector u oficina con su interno o teléfono",
    ),
    "otro": Perfil(
        clave="otro",
        nombre="Otro lugar",
        etiqueta_empresa="Empresa o motivo",
        ej_empresa="",
        ej_destino="ej.: sector, oficina o lote",
        ej_autorizo="",
        ej_puesto="Club Atlético · Acceso principal",
        ej_agenda_nombre="Administración",
        agenda="cada lugar o persona de referencia con su teléfono",
    ),
}


def actual(base: BaseDeDatos) -> Perfil:
    return PERFILES.get(base.ajuste("tipo_predio", "otro") or "otro", PERFILES["otro"])
