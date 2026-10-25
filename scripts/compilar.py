"""Compila IngresosApp en un único ejecutable con PyInstaller.

Uso (desde la carpeta del proyecto):
    python -m pip install -r requirements.txt pyinstaller
    python scripts/compilar.py

El resultado queda en dist/: IngresosApp.exe en Windows o IngresosApp en Linux.
Lo usan también las GitHub Actions para publicar cada versión.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ingresosapp import __version__  # noqa: E402

PLANTILLA_VERSION = """\
VSVersionInfo(
  ffi=FixedFileInfo(filevers={tupla}, prodvers={tupla}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040A04B0', [
      StringStruct('CompanyName', 'Lucas Emanuel Santoro'),
      StringStruct('FileDescription', 'IngresosApp - Registro de ingresos y salidas'),
      StringStruct('FileVersion', '{texto}'),
      StringStruct('InternalName', 'IngresosApp'),
      StringStruct('LegalCopyright', 'Copyright (c) 2024-2026 Lucas Emanuel Santoro. Licencia MIT.'),
      StringStruct('OriginalFilename', 'IngresosApp.exe'),
      StringStruct('ProductName', 'IngresosApp'),
      StringStruct('ProductVersion', '{texto}')])]),
    VarFileInfo([VarStruct('Translation', [0x040A, 1200])])
  ]
)
"""


def archivo_version() -> Path:
    """Metadatos que Windows muestra en Propiedades → Detalles del .exe."""
    numeros = [int(n) for n in re.findall(r"\d+", __version__)[:3]]
    tupla = tuple(numeros + [0] * (4 - len(numeros)))
    destino = RAIZ / "build" / "version_windows.txt"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(PLANTILLA_VERSION.format(tupla=tupla, texto=__version__), encoding="utf-8")
    return destino


def main() -> None:
    import PyInstaller.__main__

    recursos = RAIZ / "ingresosapp" / "recursos"
    argumentos = [
        str(RAIZ / "IngresosApp.py"),
        "--name", "IngresosApp",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(recursos / "icono.ico"),
        "--add-data", f"{recursos}{os.pathsep}ingresosapp/recursos",
        "--distpath", str(RAIZ / "dist"),
        "--workpath", str(RAIZ / "build"),
        "--specpath", str(RAIZ / "build"),
    ]
    if sys.platform == "win32":
        argumentos += ["--version-file", str(archivo_version())]
    PyInstaller.__main__.run(argumentos)
    print(f"\nListo: IngresosApp {__version__} en {RAIZ / 'dist'}")


if __name__ == "__main__":
    main()
