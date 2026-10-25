"""Cómo se muestran fechas, horas, duraciones y estados en pantalla."""

from __future__ import annotations

import json
from datetime import date, datetime

from ..db import ErrorDeDatos, Movimiento, Registro
from ..patentes import formatear_dominio

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
CAMPOS = {
    "tipo": "Tipo",
    "dominio": "Dominio",
    "empresa": "Empresa",
    "particular": "Particular",
    "destino": "Destino",
    "observaciones": "Observaciones",
}
ACCIONES = {
    "ingreso": "Ingreso",
    "salida": "Salida",
    "modificacion": "Modificación",
    "anulacion": "Anulación",
    "importado": "Importado",
}


def hora(texto: str | None) -> str:
    return texto[11:16] if texto and len(texto) >= 16 else (texto or "")


def fecha(texto_o_fecha: str | date | None) -> str:
    if isinstance(texto_o_fecha, date):
        return texto_o_fecha.strftime("%d/%m/%Y")
    if texto_o_fecha and len(texto_o_fecha) >= 10:
        a, m, d = texto_o_fecha[:10].split("-")
        return f"{d}/{m}/{a}"
    return texto_o_fecha or ""


def fecha_hora(texto: str | None) -> str:
    return f"{fecha(texto)} {hora(texto)}".strip()


def fecha_larga(dia: date) -> str:
    return f"{DIAS[dia.weekday()].capitalize()} {dia:%d/%m/%Y}"


def leer_fecha(texto: str) -> date:
    """Lee una fecha escrita como dd/mm/aaaa."""
    texto = texto.strip()
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ErrorDeDatos(f"«{texto}» no es una fecha válida. Escribila como dd/mm/aaaa, por ejemplo 24/10/2026.")


def duracion(desde: datetime | None, hasta: datetime) -> str:
    if not desde:
        return ""
    minutos = max(0, int((hasta - desde).total_seconds() // 60))
    dias, minutos = divmod(minutos, 24 * 60)
    horas, minutos = divmod(minutos, 60)
    if dias:
        return f"{dias} d {horas} h"
    if horas:
        return f"{horas} h {minutos:02d} min"
    return f"{minutos} min"


def tipo(registro: Registro) -> str:
    return "A pie" if registro.tipo == "peaton" else "Vehículo"


def dominio(registro: Registro) -> str:
    return formatear_dominio(registro.dominio) or "—"


def estado(registro: Registro) -> str:
    if registro.anulado:
        return "Anulado"
    if registro.origen == "v1":
        return "Importado (v1)"
    if registro.salida:
        return "Salió"
    return "Adentro"


def guardia_corta(nombre: str) -> str:
    """'Lucía Ramírez' → 'L. Ramírez'."""
    partes = nombre.split()
    if len(partes) < 2:
        return nombre
    return f"{partes[0][0]}. {' '.join(partes[1:])}"


def resumen(registro: Registro) -> str:
    quien = registro.particular
    if registro.tipo == "vehiculo":
        return f"{dominio(registro)} · {quien}"
    return f"{quien} (a pie)"


def describir(movimiento: Movimiento) -> str:
    accion = ACCIONES.get(movimiento.accion, movimiento.accion)
    cabecera = f"{fecha_hora(movimiento.momento)} · {accion}"
    if movimiento.guardia:
        cabecera += f" · {movimiento.guardia}"
    if movimiento.accion == "modificacion":
        try:
            cambios = json.loads(movimiento.detalle)
        except ValueError:
            return f"{cabecera}\n    {movimiento.detalle}"
        lineas = []
        for campo, (antes, despues) in cambios.items():
            if campo == "tipo":
                antes, despues = ("A pie" if v == "peaton" else "Vehículo" for v in (antes, despues))
            if campo == "dominio":
                antes, despues = formatear_dominio(antes), formatear_dominio(despues)
            lineas.append(f"    {CAMPOS.get(campo, campo)}: «{antes or '—'}» → «{despues or '—'}»")
        return "\n".join([cabecera, *lineas])
    if movimiento.detalle:
        return f"{cabecera}\n    {movimiento.detalle}"
    return cabecera
