"""Ventanas secundarias: turno, modificar, anular, historial, Acerca de."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

from .. import __version__
from ..db import BaseDeDatos, Contacto, ErrorDeDatos, Registro
from ..patentes import formatear_dominio
from . import formato
from .estilo import COLORES
from .perfiles import PERFILES, Perfil

RECURSOS = Path(__file__).resolve().parent.parent / "recursos"

AUTOR = "Lucas Emanuel Santoro"
SITIO_AUTOR = "https://www.lucassantoro.com.ar/"
CORREO_AUTOR = "lucassantoroemanuel@gmail.com"
SITIO_APP = "https://www.ingresosapp.com.ar/"
CODIGO_APP = "https://github.com/Lucas68747/IngresosApp"


class CampoAutocompletar(ttk.Combobox):
    """Campo de texto que sugiere los valores más usados de la base."""

    def __init__(self, master: tk.Misc, base: BaseDeDatos, campo: str, **kwargs):
        super().__init__(master, postcommand=self._actualizar, **kwargs)
        self._base = base
        self._campo = campo

    def _actualizar(self) -> None:
        self.configure(values=self._base.sugerencias(self._campo, self.get(), limite=15))


class Dialogo(tk.Toplevel):
    """Ventana modal centrada sobre la principal. Esc la cierra."""

    def __init__(self, padre: tk.Misc, titulo: str):
        super().__init__(padre)
        self.withdraw()
        self.title(titulo)
        self.transient(padre.winfo_toplevel())
        self.configure(background=COLORES["panel"])
        self.resizable(False, False)
        self.resultado = None
        self.cuerpo = ttk.Frame(self, style="Panel.TFrame", padding=(22, 18, 22, 18))
        self.cuerpo.pack(fill="both", expand=True)
        self.bind("<Escape>", lambda _e: self.cancelar())
        self.protocol("WM_DELETE_WINDOW", self.cancelar)

    def mostrar(self):
        self.update_idletasks()
        padre = self.master.winfo_toplevel()
        x = padre.winfo_rootx() + (padre.winfo_width() - self.winfo_reqwidth()) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.grab_set()
        self.focus_set()
        self.wait_window()
        return self.resultado

    def cancelar(self) -> None:
        self.resultado = None
        self.destroy()

    def botonera(self, texto_ok: str, comando, cancelar: bool = True) -> ttk.Frame:
        barra = ttk.Frame(self.cuerpo, style="Panel.TFrame")
        barra.pack(fill="x", pady=(18, 0))
        ttk.Button(barra, text=texto_ok, style="Primario.TButton", command=comando).pack(side="right")
        if cancelar:
            ttk.Button(barra, text="Cancelar", command=self.cancelar).pack(side="right", padx=(0, 8))
        return barra

    def error(self, e: Exception) -> None:
        messagebox.showwarning("Revisá los datos", str(e), parent=self)


class DialogoTurno(Dialogo):
    """Quién está de guardia. Al abrir la app por primera vez es obligatorio."""

    def __init__(self, padre: tk.Misc, base: BaseDeDatos, obligatorio: bool = False):
        super().__init__(padre, "Guardia de turno")
        self.base = base
        self.obligatorio = obligatorio
        ttk.Label(self.cuerpo, text="¿Quién está de guardia?", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(
            self.cuerpo,
            text="Elegí tu nombre de la lista o escribilo si es tu primer turno.\n"
                 "Cada ingreso y salida que registres va a quedar a tu nombre.",
            style="Suave.TLabel", justify="left",
        ).pack(anchor="w", pady=(4, 14))
        self.nombre = ttk.Combobox(self.cuerpo, values=base.guardias(), width=36)
        self.nombre.pack(fill="x")
        actual = base.turno_actual()
        if actual and not obligatorio:
            ttk.Label(
                self.cuerpo, text=f"Turno actual: {actual.guardia}, desde las {formato.hora(actual.inicio)}.",
                style="Suave.TLabel",
            ).pack(anchor="w", pady=(8, 0))
        self.botonera("Empezar turno", self.aceptar, cancelar=not obligatorio)
        self.bind("<Return>", lambda _e: self.aceptar())
        self.nombre.focus_set()

    def cancelar(self) -> None:
        if self.obligatorio:
            if messagebox.askyesno(
                "Guardia de turno", "Sin una guardia de turno no se pueden registrar ingresos.\n¿Cerrar IngresosApp?",
                parent=self,
            ):
                self.resultado = "salir"
                self.destroy()
            return
        super().cancelar()

    def aceptar(self) -> None:
        try:
            self.resultado = self.base.iniciar_turno(self.nombre.get())
        except ErrorDeDatos as e:
            self.error(e)
            return
        self.destroy()


class DialogoModificar(Dialogo):
    def __init__(self, padre: tk.Misc, base: BaseDeDatos, registro: Registro):
        super().__init__(padre, f"Modificar registro Nº {registro.id}")
        self.base = base
        self.registro = registro
        ttk.Label(self.cuerpo, text=f"Registro Nº {registro.id}", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(
            self.cuerpo,
            text=f"Ingresó el {formato.fecha(registro.ingreso)} a las {formato.hora(registro.ingreso)}. "
                 "La fecha y la hora no se modifican,\ny el cambio queda anotado en el historial.",
            style="Suave.TLabel", justify="left",
        ).pack(anchor="w", pady=(4, 12))

        formulario = ttk.Frame(self.cuerpo, style="Panel.TFrame")
        formulario.pack(fill="x")
        formulario.columnconfigure(1, weight=1)
        self.tipo = tk.StringVar(value=registro.tipo)
        tipos = ttk.Frame(formulario, style="Panel.TFrame")
        ttk.Radiobutton(tipos, text="Vehículo", value="vehiculo", variable=self.tipo).pack(side="left")
        ttk.Radiobutton(tipos, text="A pie", value="peaton", variable=self.tipo).pack(side="left", padx=(12, 0))
        self.dominio = ttk.Entry(formulario, width=40, style="Dominio.TEntry")
        self.dominio.insert(0, formatear_dominio(registro.dominio))
        self.empresa = CampoAutocompletar(formulario, base, "empresa", width=38)
        self.empresa.set(registro.empresa)
        self.particular = CampoAutocompletar(formulario, base, "particular", width=38)
        self.particular.set(registro.particular)
        self.destino = CampoAutocompletar(formulario, base, "destino", width=38)
        self.destino.set(registro.destino)
        self.autorizo = ttk.Entry(formulario, width=40)
        self.autorizo.insert(0, registro.autorizo)
        self.observaciones = ttk.Entry(formulario, width=40)
        self.observaciones.insert(0, registro.observaciones)
        filas = [
            ("Tipo", tipos), ("Dominio", self.dominio), ("Empresa", self.empresa),
            ("Particular", self.particular), ("Destino", self.destino), ("Autorizó", self.autorizo),
            ("Observaciones", self.observaciones),
        ]
        for fila, (etiqueta, campo) in enumerate(filas):
            ttk.Label(formulario, text=etiqueta, style="Campo.TLabel").grid(row=fila, column=0, sticky="w", pady=5, padx=(0, 14))
            campo.grid(row=fila, column=1, sticky="ew", pady=5)
        self.botonera("Guardar cambios", self.aceptar)
        self.bind("<Return>", lambda _e: self.aceptar())

    def aceptar(self) -> None:
        try:
            self.resultado = self.base.modificar(
                self.registro.id,
                tipo=self.tipo.get(), dominio=self.dominio.get(), empresa=self.empresa.get(),
                particular=self.particular.get(), destino=self.destino.get(),
                autorizo=self.autorizo.get(), observaciones=self.observaciones.get(),
            )
        except ErrorDeDatos as e:
            self.error(e)
            return
        self.destroy()


class DialogoAnular(Dialogo):
    def __init__(self, padre: tk.Misc, base: BaseDeDatos, registro: Registro):
        super().__init__(padre, f"Anular registro Nº {registro.id}")
        self.base = base
        self.registro = registro
        ttk.Label(self.cuerpo, text=f"Anular el registro Nº {registro.id}", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(
            self.cuerpo,
            text=f"{formato.resumen(registro)} · ingresó a las {formato.hora(registro.ingreso)}\n\n"
                 "El registro no se borra: queda tachado en las listas y en los reportes,\n"
                 "con el motivo, la hora y tu nombre.",
            style="Suave.TLabel", justify="left",
        ).pack(anchor="w", pady=(4, 12))
        ttk.Label(self.cuerpo, text="Motivo", style="Campo.TLabel").pack(anchor="w")
        self.motivo = ttk.Entry(self.cuerpo, width=52)
        self.motivo.pack(fill="x", pady=(4, 0))
        self.motivo.focus_set()
        self.botonera("Anular registro", self.aceptar)
        self.bind("<Return>", lambda _e: self.aceptar())

    def aceptar(self) -> None:
        try:
            self.resultado = self.base.anular(self.registro.id, self.motivo.get())
        except ErrorDeDatos as e:
            self.error(e)
            return
        self.destroy()


class DialogoHistorial(Dialogo):
    def __init__(self, padre: tk.Misc, base: BaseDeDatos, registro: Registro):
        super().__init__(padre, f"Historial del registro Nº {registro.id}")
        self.resizable(True, True)
        ttk.Label(self.cuerpo, text=f"Registro Nº {registro.id}: {formato.resumen(registro)}",
                  style="Titulo.TLabel").pack(anchor="w")
        detalle = f"{registro.empresa or 'Sin empresa'} · destino {registro.destino} · {formato.estado(registro)}"
        ttk.Label(self.cuerpo, text=detalle, style="Suave.TLabel").pack(anchor="w", pady=(4, 12))
        texto = tk.Text(
            self.cuerpo, width=72, height=12, wrap="word", relief="flat", padx=10, pady=8,
            background=COLORES["fondo"], foreground=COLORES["texto"], font="TkDefaultFont",
            highlightthickness=1, highlightbackground=COLORES["borde"],
        )
        texto.insert("1.0", "\n\n".join(formato.describir(m) for m in base.historial(registro.id)))
        texto.configure(state="disabled")
        texto.pack(fill="both", expand=True)
        self.botonera("Cerrar", self.cancelar, cancelar=False)


class DialogoPuesto(Dialogo):
    """Dónde se usa la app y cómo se llama el puesto. Se pide la primera vez."""

    def __init__(self, padre: tk.Misc, base: BaseDeDatos, inicial: bool = False):
        super().__init__(padre, "Configuración del puesto")
        self.base = base
        self.inicial = inicial
        ttk.Label(self.cuerpo, text="¿Dónde se usa IngresosApp?", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(
            self.cuerpo,
            text="La app funciona igual en todos los casos: esto solo adapta los ejemplos y las ayudas.",
            style="Suave.TLabel",
        ).pack(anchor="w", pady=(4, 10))
        self.tipo = tk.StringVar(value=base.ajuste("tipo_predio", "barrio") or "barrio")
        for perfil in PERFILES.values():
            ttk.Radiobutton(self.cuerpo, text=perfil.nombre, value=perfil.clave, variable=self.tipo,
                            command=self._actualizar_ejemplo).pack(anchor="w", pady=2)
        ttk.Label(self.cuerpo, text="Nombre del puesto", style="Campo.TLabel").pack(anchor="w", pady=(14, 0))
        self.ejemplo = ttk.Label(self.cuerpo, style="Suave.TLabel")
        self.ejemplo.pack(anchor="w")
        self.nombre = ttk.Entry(self.cuerpo, width=50)
        self.nombre.insert(0, base.ajuste("puesto", "") or "")
        self.nombre.pack(fill="x", pady=(4, 0))
        ttk.Label(self.cuerpo, text="Aparece arriba en la ventana y en los reportes.",
                  style="Suave.TLabel").pack(anchor="w", pady=(4, 0))
        self._actualizar_ejemplo()
        self.botonera("Guardar", self.aceptar, cancelar=not inicial)
        self.bind("<Return>", lambda _e: self.aceptar())
        self.nombre.focus_set()

    def _actualizar_ejemplo(self) -> None:
        self.ejemplo.configure(text=f"Por ejemplo: {PERFILES[self.tipo.get()].ej_puesto}")

    def cancelar(self) -> None:
        if self.inicial:
            self.aceptar()
        else:
            super().cancelar()

    def aceptar(self) -> None:
        self.base.guardar_ajuste("tipo_predio", self.tipo.get())
        self.base.guardar_ajuste("puesto", " ".join(self.nombre.get().split()))
        self.resultado = True
        self.destroy()


class DialogoContacto(Dialogo):
    """Alta o edición de un contacto de la agenda."""

    def __init__(self, padre: tk.Misc, base: BaseDeDatos, perfil: Perfil, contacto: Contacto | None = None):
        super().__init__(padre, "Editar contacto" if contacto else "Nuevo contacto")
        self.base = base
        self.contacto = contacto
        ttk.Label(self.cuerpo, text="Editar contacto" if contacto else "Nuevo contacto",
                  style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(
            self.cuerpo,
            text=f"Por ejemplo: {perfil.agenda}.\nCargá solo lo necesario para el trabajo de la guardia.",
            style="Suave.TLabel", justify="left",
        ).pack(anchor="w", pady=(4, 12))
        formulario = ttk.Frame(self.cuerpo, style="Panel.TFrame")
        formulario.pack(fill="x")
        formulario.columnconfigure(1, weight=1)
        self.campos: dict[str, ttk.Entry] = {}
        filas = [
            ("nombre", "Nombre", f"ej.: {perfil.ej_agenda_nombre}"),
            ("ubicacion", "Ubicación", "opcional"),
            ("telefonos", "Teléfonos", "opcional · se pueden poner varios"),
            ("contacto", "Contacto", "opcional · a quién llamar o quién autoriza"),
        ]
        for fila, (clave, etiqueta, ayuda) in enumerate(filas):
            ttk.Label(formulario, text=etiqueta, style="Campo.TLabel").grid(row=fila * 2, column=0, sticky="w",
                                                                              padx=(0, 14), pady=(6, 0))
            entrada = ttk.Entry(formulario, width=44)
            entrada.insert(0, getattr(contacto, clave, "") if contacto else "")
            entrada.grid(row=fila * 2, column=1, sticky="ew", pady=(6, 0))
            ttk.Label(formulario, text=ayuda, style="Suave.TLabel").grid(row=fila * 2 + 1, column=1, sticky="w")
            self.campos[clave] = entrada
        ttk.Label(formulario, text="Notas", style="Campo.TLabel").grid(row=8, column=0, sticky="nw", padx=(0, 14), pady=(8, 0))
        self.notas = tk.Text(
            formulario, height=3, width=44, wrap="word", relief="flat", padx=6, pady=5, font="TkDefaultFont",
            highlightthickness=1, highlightbackground=COLORES["linea"], highlightcolor=COLORES["azul"],
        )
        self.notas.insert("1.0", contacto.notas if contacto else "")
        self.notas.grid(row=8, column=1, sticky="ew", pady=(8, 0))
        self.botonera("Guardar", self.aceptar)
        self.campos["nombre"].focus_set()
        for entrada in self.campos.values():
            entrada.bind("<Return>", lambda _e: self.aceptar())

    def aceptar(self) -> None:
        datos = {clave: entrada.get() for clave, entrada in self.campos.items()}
        datos["notas"] = self.notas.get("1.0", "end")
        try:
            self.resultado = self.base.guardar_contacto(self.contacto.id if self.contacto else None, **datos)
        except ErrorDeDatos as e:
            self.error(e)
            return
        self.destroy()


class DialogoTexto(Dialogo):
    """Pide un texto corto, por ejemplo el nombre del puesto."""

    def __init__(self, padre: tk.Misc, titulo: str, explicacion: str, valor: str = ""):
        super().__init__(padre, titulo)
        ttk.Label(self.cuerpo, text=titulo, style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self.cuerpo, text=explicacion, style="Suave.TLabel", justify="left").pack(anchor="w", pady=(4, 12))
        self.entrada = ttk.Entry(self.cuerpo, width=48)
        self.entrada.insert(0, valor)
        self.entrada.pack(fill="x")
        self.entrada.focus_set()
        self.entrada.select_range(0, "end")
        self.botonera("Guardar", self.aceptar)
        self.bind("<Return>", lambda _e: self.aceptar())

    def aceptar(self) -> None:
        self.resultado = " ".join(self.entrada.get().split())
        self.destroy()


class AcercaDe(Dialogo):
    def __init__(self, padre: tk.Misc, carpeta_datos: Path):
        super().__init__(padre, "Acerca de IngresosApp")
        fila = ttk.Frame(self.cuerpo, style="Panel.TFrame")
        fila.pack(fill="x")
        try:
            self._icono = tk.PhotoImage(file=str(RECURSOS / "icono.png")).subsample(4, 4)
            ttk.Label(fila, image=self._icono, style="Panel.TLabel").pack(side="left", padx=(0, 16))
        except tk.TclError:
            pass
        titulos = ttk.Frame(fila, style="Panel.TFrame")
        titulos.pack(side="left", anchor="center")
        ttk.Label(titulos, text="IngresosApp", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(titulos, text=f"Versión {__version__}", style="Suave.TLabel").pack(anchor="w")

        ttk.Label(
            self.cuerpo,
            text="Registro de ingresos y salidas para la guardia de barrios cerrados,\n"
                 "parques industriales y otros predios privados.\n\n"
                 "Nació en la garita de un parque industrial, para reemplazar las\n"
                 "planillas de papel que se llenaban a mano en cada turno.",
            style="Panel.TLabel", justify="left",
        ).pack(anchor="w", pady=(16, 14))

        ttk.Label(self.cuerpo, text=f"Hecha por {AUTOR}", style="Campo.TLabel").pack(anchor="w")
        enlaces = [
            ("Página web", "www.lucassantoro.com.ar", SITIO_AUTOR),
            ("Correo", CORREO_AUTOR, f"mailto:{CORREO_AUTOR}?subject=IngresosApp%20{__version__}"),
            ("Sitio de la app", "www.ingresosapp.com.ar", SITIO_APP),
            ("Código", "github.com/Lucas68747/IngresosApp", CODIGO_APP),
        ]
        tabla = ttk.Frame(self.cuerpo, style="Panel.TFrame")
        tabla.pack(anchor="w", pady=(4, 0))
        for i, (etiqueta, texto, url) in enumerate(enlaces):
            ttk.Label(tabla, text=etiqueta, style="Suave.TLabel").grid(row=i, column=0, sticky="w", padx=(0, 12))
            ttk.Button(
                tabla, text=texto, style="Enlace.TButton", cursor="hand2",
                command=lambda u=url: webbrowser.open(u),
            ).grid(row=i, column=1, sticky="w")

        ttk.Label(
            self.cuerpo,
            text=f"Software libre bajo licencia MIT.\nTus datos se guardan solo en este equipo, en {carpeta_datos}",
            style="Suave.TLabel", justify="left", wraplength=460,
        ).pack(anchor="w", pady=(14, 0))
        self.botonera("Cerrar", self.cancelar, cancelar=False)
