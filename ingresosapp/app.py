"""Arranque de IngresosApp."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from . import __version__, rutas
from .db import ErrorDeDatos, abrir

RECURSOS = Path(__file__).resolve().parent / "recursos"


def _preparar_windows() -> None:
    """Texto nítido en pantallas con escala y el ícono propio en la barra de tareas."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"IngresosApp.{__version__}")
    except Exception:
        pass


def _poner_icono(root: tk.Tk) -> None:
    try:
        root.iconphoto(True, tk.PhotoImage(file=str(RECURSOS / "icono.png")))
        if sys.platform == "win32":
            root.iconbitmap(default=str(RECURSOS / "icono.ico"))
    except tk.TclError:
        pass


def main() -> None:
    _preparar_windows()
    root = tk.Tk()
    root.withdraw()
    _poner_icono(root)

    carpeta = rutas.carpeta_datos()
    try:
        base, importados = abrir(rutas.ruta_base(carpeta), rutas.candidatas_base_v1())
    except ErrorDeDatos as e:
        messagebox.showerror("IngresosApp", str(e))
        root.destroy()
        return

    from .ui.ventana import VentanaPrincipal

    ventana = VentanaPrincipal(root, base, carpeta)
    root.deiconify()
    root.update_idletasks()

    if importados:
        messagebox.showinfo(
            "Datos de la versión 1.0",
            f"Se importaron {importados} registros de IngresosApp 1.0.\n"
            "El archivo original no se modificó.",
            parent=root,
        )
    try:
        if base.ajuste("tipo_predio") is None:
            ventana.configurar_puesto(inicial=True)
        if base.turno_actual() is None:
            ventana.cambiar_turno(obligatorio=True)
        if ventana.cerrada:
            return
        if base.ajuste("recorrido_visto") != "1":
            root.after(300, ventana.ver_recorrido)
        root.mainloop()
    finally:
        base.cerrar()


if __name__ == "__main__":
    main()
