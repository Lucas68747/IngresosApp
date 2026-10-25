"""Colores, tipografías y estilos ttk de IngresosApp.

Es la misma paleta que www.ingresosapp.com.ar: azul noche, azul y celeste.
Se usa el tema "clam" de Tkinter como base porque se ve igual en Windows
y en Linux y permite cambiar colores; no hace falta ninguna librería extra.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

COLORES = {
    "noche": "#0b1220",
    "noche_borde": "#26334d",
    "noche_texto": "#b8c4d6",
    "azul": "#1d3e7b",
    "azul_oscuro": "#163161",
    "azul_apagado": "#9fb0cc",
    "celeste": "#6f9ae0",
    "fondo": "#f4f6f9",
    "panel": "#ffffff",
    "gris": "#eef1f5",
    "borde": "#d6dce5",
    "linea": "#9aa4b2",
    "texto": "#1c222c",
    "suave": "#5b6575",
    "anulado": "#8a919c",
    "fila_par": "#f8f9fb",
    "error": "#b42318",
}

FAMILIAS_PREFERIDAS = ("Segoe UI", "Noto Sans", "Open Sans", "DejaVu Sans")


def _familia(root: tk.Misc) -> str:
    disponibles = set(tkfont.families(root))
    for familia in FAMILIAS_PREFERIDAS:
        if familia in disponibles:
            return familia
    return tkfont.nametofont("TkDefaultFont").actual("family")


def aplicar(root: tk.Tk) -> dict[str, tkfont.Font]:
    """Configura fuentes y estilos. Devuelve las fuentes con nombre."""
    c = COLORES
    familia = _familia(root)
    for nombre in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        tkfont.nametofont(nombre).configure(family=familia, size=10)

    fuentes = {
        "normal": tkfont.Font(root, family=familia, size=10),
        "negrita": tkfont.Font(root, family=familia, size=10, weight="bold"),
        "chica": tkfont.Font(root, family=familia, size=9),
        "titulo": tkfont.Font(root, family=familia, size=12, weight="bold"),
        "grande": tkfont.Font(root, family=familia, size=13, weight="bold"),
        "reloj": tkfont.Font(root, family=familia, size=18, weight="bold"),
        "dominio": tkfont.Font(root, family=familia, size=11, weight="bold"),
        "tachada": tkfont.Font(root, family=familia, size=10, overstrike=True),
    }

    root.configure(background=c["fondo"])
    root.option_add("*Menu.font", fuentes["normal"])
    root.option_add("*TCombobox*Listbox.font", fuentes["normal"])

    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(
        ".",
        background=c["fondo"], foreground=c["texto"], font=fuentes["normal"],
        bordercolor=c["borde"], lightcolor=c["panel"], darkcolor=c["borde"],
        troughcolor=c["gris"], focuscolor=c["celeste"], selectbackground=c["azul"],
        selectforeground="#ffffff", insertcolor=c["texto"],
    )

    # Contenedores y textos
    st.configure("Panel.TFrame", background=c["panel"])
    st.configure("Noche.TFrame", background=c["noche"])
    st.configure("Barra.TFrame", background=c["panel"])
    st.configure("Estado.TFrame", background=c["gris"])
    st.configure("Panel.TLabel", background=c["panel"])
    st.configure("Campo.TLabel", background=c["panel"], font=fuentes["negrita"])
    st.configure("Suave.TLabel", background=c["panel"], foreground=c["suave"], font=fuentes["chica"])
    st.configure("Aviso.TLabel", background=c["panel"], foreground=c["azul"], font=fuentes["negrita"])
    st.configure("Error.TLabel", background=c["panel"], foreground=c["error"], font=fuentes["negrita"])
    st.configure("Titulo.TLabel", background=c["panel"], foreground=c["noche"], font=fuentes["titulo"])
    st.configure("Noche.TLabel", background=c["noche"], foreground="#ffffff", font=fuentes["grande"])
    st.configure("NocheSuave.TLabel", background=c["noche"], foreground=c["noche_texto"], font=fuentes["chica"])
    st.configure("Reloj.TLabel", background=c["noche"], foreground="#ffffff", font=fuentes["reloj"])
    st.configure("Estado.TLabel", background=c["gris"], foreground=c["suave"], font=fuentes["chica"])

    # Botones
    st.configure(
        "TButton", padding=(12, 6), background=c["panel"], foreground=c["texto"],
        bordercolor=c["linea"], lightcolor=c["panel"], darkcolor=c["panel"], relief="solid", borderwidth=1,
    )
    st.map(
        "TButton",
        background=[("disabled", c["gris"]), ("pressed", c["borde"]), ("active", c["gris"])],
        foreground=[("disabled", c["anulado"])],
        bordercolor=[("focus", c["azul"])],
    )
    st.configure(
        "Primario.TButton", background=c["azul"], foreground="#ffffff", bordercolor=c["azul"],
        lightcolor=c["azul"], darkcolor=c["azul"], font=fuentes["negrita"],
    )
    st.map(
        "Primario.TButton",
        background=[("disabled", c["azul_apagado"]), ("pressed", c["noche"]), ("active", c["azul_oscuro"])],
        foreground=[("disabled", "#ffffff")],
        bordercolor=[("focus", c["celeste"])],
        lightcolor=[("active", c["azul_oscuro"])], darkcolor=[("active", c["azul_oscuro"])],
    )
    st.configure("Contorno.TButton", foreground=c["azul"], bordercolor=c["azul"], font=fuentes["negrita"])
    st.configure(
        "Noche.TButton", background=c["noche"], foreground="#ffffff", bordercolor=c["celeste"],
        lightcolor=c["noche"], darkcolor=c["noche"], padding=(10, 4),
    )
    st.map("Noche.TButton", background=[("pressed", c["azul_oscuro"]), ("active", "#16233d")])
    st.configure("Enlace.TButton", background=c["panel"], foreground=c["azul"], bordercolor=c["panel"],
                 lightcolor=c["panel"], darkcolor=c["panel"], padding=(2, 2), relief="flat")
    st.map("Enlace.TButton", foreground=[("active", c["azul_oscuro"])], background=[("active", c["panel"])])

    # Selector Vehículo / A pie
    st.configure(
        "Segmento.Toolbutton", background=c["panel"], foreground=c["azul"], bordercolor=c["azul"],
        lightcolor=c["panel"], darkcolor=c["panel"], padding=(10, 6), anchor="center", font=fuentes["negrita"],
        relief="solid", borderwidth=1,
    )
    st.map(
        "Segmento.Toolbutton",
        background=[("selected", c["azul"]), ("active", c["gris"])],
        foreground=[("selected", "#ffffff")],
        lightcolor=[("selected", c["azul"])], darkcolor=[("selected", c["azul"])],
    )

    # Campos
    for estilo in ("TEntry", "TCombobox"):
        st.configure(
            estilo, fieldbackground=c["panel"], bordercolor=c["linea"], lightcolor=c["panel"],
            darkcolor=c["panel"], padding=5,
        )
        st.map(
            estilo,
            bordercolor=[("focus", c["azul"])], lightcolor=[("focus", c["azul"])],
            fieldbackground=[("disabled", c["gris"]), ("readonly", c["panel"])],
            foreground=[("disabled", c["anulado"])],
        )
    st.configure("Dominio.TEntry", font=fuentes["dominio"])

    # Pestañas y tablas
    st.configure("TNotebook", background=c["gris"], bordercolor=c["borde"], tabmargins=(10, 8, 10, 0))
    st.configure(
        "TNotebook.Tab", padding=(16, 7), background=c["gris"], foreground=c["suave"],
        bordercolor=c["borde"], lightcolor=c["gris"],
    )
    st.map(
        "TNotebook.Tab",
        background=[("selected", c["panel"])], foreground=[("selected", c["noche"])],
        font=[("selected", fuentes["negrita"])], lightcolor=[("selected", c["panel"])],
    )
    st.configure(
        "Treeview", background=c["panel"], fieldbackground=c["panel"], foreground=c["texto"],
        rowheight=28, bordercolor=c["borde"], lightcolor=c["panel"], darkcolor=c["panel"],
    )
    st.map("Treeview", background=[("selected", c["azul"])], foreground=[("selected", "#ffffff")])
    st.configure(
        "Treeview.Heading", background=c["gris"], foreground=c["texto"], font=fuentes["negrita"],
        bordercolor=c["borde"], lightcolor=c["gris"], darkcolor=c["borde"], padding=(8, 5), relief="flat",
    )
    st.map("Treeview.Heading", background=[("active", c["borde"])])
    st.configure("TScrollbar", background=c["gris"], bordercolor=c["gris"], arrowcolor=c["suave"],
                 lightcolor=c["gris"], darkcolor=c["gris"])
    st.configure("TRadiobutton", background=c["panel"])
    st.configure("TCheckbutton", background=c["panel"])
    return fuentes


def tarjeta(master: tk.Misc, **kwargs) -> tk.Frame:
    """Panel blanco con borde fino, como las tarjetas de la web."""
    return tk.Frame(
        master, background=COLORES["panel"], highlightthickness=1,
        highlightbackground=COLORES["borde"], highlightcolor=COLORES["borde"], **kwargs,
    )
