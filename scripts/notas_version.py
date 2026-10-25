"""Imprime la sección del CHANGELOG de una versión, para las notas de la release.

Uso: python scripts/notas_version.py 2.0.0
"""

import re
import sys
from pathlib import Path

version = sys.argv[1]
texto = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
seccion = re.search(rf"^## \[{re.escape(version)}\].*?$(.*?)(?=^## \[|\Z)", texto, re.S | re.M)
if not seccion:
    sys.exit(f"No hay una sección para la versión {version} en el CHANGELOG.")
print(seccion.group(1).strip())
print(
    "\n---\n**Descargas:** `IngresosApp.exe` para Windows e `IngresosApp` para Linux "
    "(en Linux, antes de abrirlo: `chmod +x IngresosApp`). Las huellas SHA-256 están en `SHA256SUMS.txt`.\n\n"
    "El ejecutable de Windows todavía no está firmado digitalmente, así que Windows puede mostrar un aviso "
    "de SmartScreen: tocá «Más información» y después «Ejecutar de todas formas»."
)
