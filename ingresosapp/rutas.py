"""Dónde guarda IngresosApp sus datos.

La base de datos y las copias de seguridad viven en una carpeta fija y
visible para el encargado (Documentos/IngresosApp), sin importar desde
dónde se abra el programa. En la versión 1.0 la base se creaba en la
carpeta de trabajo, y abrir la app desde un acceso directo podía crear
una base nueva y vacía.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOMBRE_CARPETA = "IngresosApp"
NOMBRE_BASE = "ingresos.db"
NOMBRE_BASE_V1 = "base"  # nombre del archivo que usaba la versión 1.0


def _documentos_windows() -> Path | None:
    """Carpeta Documentos real en Windows (puede estar movida a OneDrive)."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        guid = GUID(
            0xFDD39AD0, 0x238F, 0x46AF,
            (wintypes.BYTE * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
        )
        ruta = ctypes.c_wchar_p()
        resultado = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(ruta)
        )
        if resultado != 0:
            return None
        carpeta = Path(ruta.value)
        ctypes.windll.ole32.CoTaskMemFree(ruta)
        return carpeta
    except Exception:
        return None


def carpeta_documentos() -> Path:
    if sys.platform == "win32":
        documentos = _documentos_windows()
        if documentos:
            return documentos
    inicio = Path.home()
    for nombre in ("Documentos", "Documents"):
        if (inicio / nombre).is_dir():
            return inicio / nombre
    return inicio


def carpeta_datos() -> Path:
    """Carpeta de datos de la app. Se puede cambiar con INGRESOSAPP_DATOS."""
    personalizada = os.environ.get("INGRESOSAPP_DATOS")
    carpeta = Path(personalizada) if personalizada else carpeta_documentos() / NOMBRE_CARPETA
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ruta_base(carpeta: Path | None = None) -> Path:
    return (carpeta or carpeta_datos()) / NOMBRE_BASE


def carpeta_respaldos(carpeta: Path | None = None) -> Path:
    respaldos = (carpeta or carpeta_datos()) / "respaldos"
    respaldos.mkdir(parents=True, exist_ok=True)
    return respaldos


def candidatas_base_v1() -> list[Path]:
    """Lugares donde puede haber quedado la base de la versión 1.0.

    La v1 creaba el archivo 'base' en la carpeta de trabajo, que en la
    práctica es la carpeta donde está el ejecutable.
    """
    carpetas: list[Path] = [Path.cwd()]
    if getattr(sys, "frozen", False):
        carpetas.append(Path(sys.executable).resolve().parent)
    if sys.argv and sys.argv[0]:
        carpetas.append(Path(sys.argv[0]).resolve().parent)

    vistas: set[Path] = set()
    candidatas: list[Path] = []
    for carpeta in carpetas:
        archivo = (carpeta / NOMBRE_BASE_V1).resolve()
        if archivo not in vistas and archivo.is_file():
            vistas.add(archivo)
            candidatas.append(archivo)
    return candidatas
