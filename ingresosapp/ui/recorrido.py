"""Recorrido de la primera vez: explica la ventana paso a paso.

Se dibuja dentro de la misma ventana (un marco celeste alrededor de cada
parte y un globo con la explicación), así acompaña a la ventana si se
mueve o cambia de tamaño. Se puede repetir desde Ayuda → Ver recorrido.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Callable

from .estilo import COLORES


@dataclass
class Paso:
    objetivo: Callable[[], tk.Misc]
    titulo: str
    texto: str
    antes: Callable[[], None] | None = None  # por ejemplo, cambiar de pestaña


class Recorrido:
    GROSOR = 3
    ANCHO_GLOBO = 410

    def __init__(self, root: tk.Tk, pasos: list[Paso], al_terminar: Callable[[], None]):
        self.root = root
        self.pasos = pasos
        self.al_terminar = al_terminar
        self.indice = 0
        self.bordes = [tk.Frame(root, background=COLORES["celeste"]) for _ in range(4)]
        self.globo = tk.Frame(
            root, background=COLORES["panel"], highlightthickness=2,
            highlightbackground=COLORES["celeste"], highlightcolor=COLORES["celeste"], padx=18, pady=14,
        )
        self.contador = ttk.Label(self.globo, style="Suave.TLabel")
        self.contador.pack(anchor="w")
        self.titulo = ttk.Label(self.globo, style="Titulo.TLabel")
        self.titulo.pack(anchor="w", pady=(2, 6))
        self.texto = ttk.Label(self.globo, style="Panel.TLabel", wraplength=self.ANCHO_GLOBO - 40, justify="left")
        self.texto.pack(anchor="w")
        barra = ttk.Frame(self.globo, style="Panel.TFrame")
        barra.pack(fill="x", pady=(14, 0))
        ttk.Button(barra, text="Saltar recorrido", style="Enlace.TButton", command=self.terminar).pack(side="left")
        self.siguiente = ttk.Button(barra, text="Siguiente", style="Primario.TButton", command=self.avanzar)
        self.siguiente.pack(side="right")
        self.anterior = ttk.Button(barra, text="Anterior", command=self.retroceder)
        self.anterior.pack(side="right", padx=(0, 8))
        self.activo = True
        # No se usa unbind al terminar: en Tkinter borra también otros enlaces del mismo evento.
        self._ubicando = False
        root.bind("<Configure>", self._ventana_cambio, add="+")
        root.bind("<Escape>", lambda _e: self.terminar(), add="+")

    def empezar(self) -> None:
        self.indice = 0
        self._mostrar()

    def avanzar(self) -> None:
        if self.indice >= len(self.pasos) - 1:
            self.terminar()
            return
        self.indice += 1
        self._mostrar()

    def retroceder(self) -> None:
        if self.indice > 0:
            self.indice -= 1
            self._mostrar()

    def terminar(self) -> None:
        if not self.activo:
            return
        self.activo = False
        for widget in (*self.bordes, self.globo):
            widget.destroy()
        self.al_terminar()

    def _mostrar(self) -> None:
        paso = self.pasos[self.indice]
        if paso.antes:
            paso.antes()
        self.contador.configure(text=f"Paso {self.indice + 1} de {len(self.pasos)}")
        self.titulo.configure(text=paso.titulo)
        self.texto.configure(text=paso.texto)
        ultimo = self.indice == len(self.pasos) - 1
        self.siguiente.configure(text="Terminar" if ultimo else "Siguiente")
        self.anterior.state(["disabled"] if self.indice == 0 else ["!disabled"])
        self.root.update_idletasks()
        self._ubicar()
        self.siguiente.focus_set()

    def _ventana_cambio(self, evento) -> None:
        # <Configure> llega por cada parte de la ventana; solo interesa la ventana principal.
        if evento.widget is self.root:
            self._ubicar()

    def _ubicar(self) -> None:
        if not self.activo or self._ubicando:
            return
        self._ubicando = True
        try:
            self._calcular_posicion()
        finally:
            self._ubicando = False

    def _calcular_posicion(self) -> None:
        objetivo = self.pasos[self.indice].objetivo()
        x = objetivo.winfo_rootx() - self.root.winfo_rootx()
        y = objetivo.winfo_rooty() - self.root.winfo_rooty()
        ancho, alto = objetivo.winfo_width(), objetivo.winfo_height()
        g, m = self.GROSOR, 4
        rectangulos = [
            (x - m - g, y - m - g, ancho + 2 * (m + g), g),
            (x - m - g, y + alto + m, ancho + 2 * (m + g), g),
            (x - m - g, y - m, g, alto + 2 * m),
            (x + ancho + m, y - m, g, alto + 2 * m),
        ]
        for borde, (bx, by, bw, bh) in zip(self.bordes, rectangulos):
            borde.place(x=bx, y=by, width=bw, height=bh)
            borde.lift()

        self.globo.place(x=0, y=0, width=self.ANCHO_GLOBO)
        self.globo.update_idletasks()
        alto_globo = self.globo.winfo_reqheight()
        ancho_ventana, alto_ventana = self.root.winfo_width(), self.root.winfo_height()
        separacion = 18
        if ancho > ancho_ventana * 0.45 and alto > alto_ventana * 0.35:
            # zona grande (una lista): el globo va adentro, en la esquina de abajo
            gx, gy = x + ancho - self.ANCHO_GLOBO - 24, y + alto - alto_globo - 24
        elif x + ancho + separacion + self.ANCHO_GLOBO < ancho_ventana:
            gx, gy = x + ancho + separacion, y
        elif x - separacion - self.ANCHO_GLOBO > 0:
            gx, gy = x - separacion - self.ANCHO_GLOBO, y
        elif y + alto + separacion + alto_globo < alto_ventana:
            gx, gy = x, y + alto + separacion
        else:
            gx, gy = x, y - separacion - alto_globo
        gx = min(max(gx, 8), ancho_ventana - self.ANCHO_GLOBO - 8)
        gy = min(max(gy, 8), alto_ventana - alto_globo - 8)
        self.globo.place(x=gx, y=gy, width=self.ANCHO_GLOBO)
        self.globo.lift()
