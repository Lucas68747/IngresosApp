"""Ventana principal de IngresosApp."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import traceback
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from .. import __version__, correo, reportes, rutas
from ..db import BaseDeDatos, Contacto, ErrorDeDatos, Registro
from ..patentes import formatear_dominio
from . import estilo, formato, perfiles
from .dialogos import (
    AcercaDe,
    CampoAutocompletar,
    DialogoAnular,
    DialogoContacto,
    DialogoCorreo,
    DialogoFechas,
    DialogoHistorial,
    DialogoModificar,
    DialogoPuesto,
    DialogoTurno,
)
from .estilo import COLORES
from .recorrido import Paso, Recorrido

# id: (título, ancho, se estira, alineación)
COLUMNAS = {
    "n": ("Nº", 46, False, "e"),
    "fecha": ("Fecha", 90, False, "w"),
    "ingreso": ("Ingreso", 66, False, "center"),
    "salida": ("Salida", 62, False, "center"),
    "tipo": ("Tipo", 74, False, "w"),
    "dominio": ("Dominio", 100, False, "w"),
    "empresa": ("Empresa", 150, True, "w"),
    "particular": ("Particular", 150, True, "w"),
    "destino": ("Destino", 110, True, "w"),
    "guardia": ("Guardia", 100, False, "w"),
    "tiempo": ("Adentro hace", 100, False, "w"),
    "estado": ("Estado", 104, False, "w"),
    "autorizo": ("Autorizó", 150, True, "w"),
    "nombre": ("Nombre", 170, True, "w"),
    "ubicacion": ("Ubicación", 130, False, "w"),
    "telefonos": ("Teléfonos", 160, False, "w"),
    "contacto": ("Contacto", 160, True, "w"),
    "notas": ("Notas", 220, True, "w"),
}
COLUMNAS_ADENTRO = ("n", "ingreso", "tipo", "dominio", "empresa", "particular", "destino", "guardia", "tiempo")
COLUMNAS_DIA = (
    "n", "ingreso", "salida", "tipo", "dominio", "empresa", "particular", "destino", "guardia", "estado", "autorizo",
)
COLUMNAS_AGENDA = ("nombre", "ubicacion", "telefonos", "contacto", "notas")
PESTANA_AGENDA = 3
COLUMNAS_BUSCAR = ("n", "fecha", "ingreso", "salida", "dominio", "empresa", "particular", "destino", "estado")

PERIODOS = ("Hoy", "Ayer", "Últimos 7 días", "Este mes", "Mes anterior", "Elegir fechas…")


class VentanaPrincipal:
    def __init__(self, root: tk.Tk, base: BaseDeDatos, carpeta_datos: Path):
        self.root = root
        self.base = base
        self.carpeta = carpeta_datos
        self.fuentes = estilo.aplicar(root)
        self.dia_mostrado = date.today()
        self.ultima_busqueda: tuple[str, date | None, date | None] | None = None
        self._mensaje_pendiente: str | None = None
        self._dia_respaldo: date | None = None
        self.cerrada = False

        root.title("IngresosApp")
        root.minsize(1000, 620)
        ancho, alto = min(1280, root.winfo_screenwidth() - 60), min(820, root.winfo_screenheight() - 80)
        root.geometry(f"{ancho}x{alto}+{(root.winfo_screenwidth() - ancho) // 2}+{max((root.winfo_screenheight() - alto) // 3, 0)}")
        root.report_callback_exception = self._error_inesperado
        root.protocol("WM_DELETE_WINDOW", self.salir)

        self._menu()
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        self._cabecera().grid(row=0, column=0, sticky="ew")
        cuerpo = ttk.Frame(root, padding=14)
        cuerpo.grid(row=1, column=0, sticky="nsew")
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)
        self._formulario(cuerpo).grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        self._listas(cuerpo).grid(row=0, column=1, sticky="nsew")
        self._reportes().grid(row=2, column=0, sticky="ew")
        self._barra_estado().grid(row=3, column=0, sticky="ew")

        root.bind("<F1>", lambda _e: self.ver_recorrido())
        root.bind("<F5>", lambda _e: self.actualizar_todo())
        root.bind("<Control-n>", lambda _e: self.nuevo_ingreso())

        self.aplicar_perfil()
        self.actualizar_turno()
        self.actualizar_todo()
        self.respaldar(silencioso=True)
        self._tic_reloj()
        self.root.after(30_000, self._tic_periodico)

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def _menu(self) -> None:
        barra = tk.Menu(self.root)
        archivo = tk.Menu(barra, tearoff=False)
        archivo.add_command(label="Abrir carpeta de datos", command=self.abrir_carpeta_datos)
        archivo.add_command(label="Hacer copia de seguridad ahora", command=self.respaldar)
        archivo.add_command(label="Importar datos de la versión 1.0…", command=self.importar_v1)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.salir)
        barra.add_cascade(label="Archivo", menu=archivo)

        registros = tk.Menu(barra, tearoff=False)
        registros.add_command(label="Nuevo ingreso", accelerator="Ctrl+N", command=self.nuevo_ingreso)
        registros.add_command(label="Registrar salida", command=self.registrar_salida)
        registros.add_command(label="Modificar…", command=self.modificar)
        registros.add_command(label="Anular…", command=self.anular)
        registros.add_command(label="Ver historial", command=self.ver_historial)
        registros.add_separator()
        registros.add_command(label="Agenda", command=lambda: self.pestanas.select(PESTANA_AGENDA))
        registros.add_command(label="Cambiar turno…", command=self.cambiar_turno)
        registros.add_command(label="Actualizar listas", accelerator="F5", command=self.actualizar_todo)
        barra.add_cascade(label="Registros", menu=registros)

        reportes = tk.Menu(barra, tearoff=False)
        reportes.add_command(label="Exportar PDF…", command=self.exportar_pdf)
        reportes.add_command(label="Enviar por correo…", command=self.enviar_correo)
        barra.add_cascade(label="Reportes", menu=reportes)

        ajustes = tk.Menu(barra, tearoff=False)
        ajustes.add_command(label="Puesto y tipo de lugar…", command=self.configurar_puesto)
        ajustes.add_command(label="Envío por correo…", command=self.configurar_correo)
        barra.add_cascade(label="Configuración", menu=ajustes)

        ayuda = tk.Menu(barra, tearoff=False)
        ayuda.add_command(label="Ver recorrido", accelerator="F1", command=self.ver_recorrido)
        ayuda.add_separator()
        ayuda.add_command(label="Acerca de IngresosApp", command=self.acerca_de)
        barra.add_cascade(label="Ayuda", menu=ayuda)
        self.root.configure(menu=barra)

    def _cabecera(self) -> ttk.Frame:
        cabecera = ttk.Frame(self.root, style="Noche.TFrame", padding=(20, 10))
        cabecera.columnconfigure(0, weight=1)

        puesto = ttk.Frame(cabecera, style="Noche.TFrame")
        puesto.grid(row=0, column=0, sticky="w")
        ttk.Label(puesto, text="Puesto de control", style="NocheSuave.TLabel").pack(anchor="w")
        self.etiqueta_puesto = ttk.Label(puesto, style="Noche.TLabel")
        self.etiqueta_puesto.pack(anchor="w")

        self.caja_turno = ttk.Frame(cabecera, style="Noche.TFrame", padding=(18, 0))
        self.caja_turno.grid(row=0, column=1, sticky="e", padx=18)
        textos = ttk.Frame(self.caja_turno, style="Noche.TFrame")
        textos.pack(side="left")
        self.etiqueta_desde = ttk.Label(textos, style="NocheSuave.TLabel")
        self.etiqueta_desde.pack(anchor="w")
        self.etiqueta_guardia = ttk.Label(textos, style="Noche.TLabel")
        self.etiqueta_guardia.pack(anchor="w")
        ttk.Button(self.caja_turno, text="Cambiar turno", style="Noche.TButton",
                   command=self.cambiar_turno).pack(side="left", padx=(16, 0))

        reloj = ttk.Frame(cabecera, style="Noche.TFrame")
        reloj.grid(row=0, column=2, sticky="e")
        self.etiqueta_hora = ttk.Label(reloj, style="Reloj.TLabel")
        self.etiqueta_hora.pack(anchor="e")
        self.etiqueta_fecha = ttk.Label(reloj, style="NocheSuave.TLabel")
        self.etiqueta_fecha.pack(anchor="e")
        return cabecera

    def _campo(self, master: tk.Misc, etiqueta: str, opcional: bool = False) -> ttk.Frame:
        """Un campo del formulario: título, aclaración y lugar para un ejemplo."""
        marco = ttk.Frame(master, style="Panel.TFrame")
        marco.pack(fill="x", pady=(0, 9))
        titulo = ttk.Frame(marco, style="Panel.TFrame")
        titulo.pack(fill="x")
        marco.titulo = ttk.Label(titulo, text=etiqueta, style="Campo.TLabel")
        marco.titulo.pack(side="left")
        if opcional:
            ttk.Label(titulo, text=" (opcional)", style="Suave.TLabel").pack(side="left")
        marco.ejemplo = ttk.Label(titulo, style="Suave.TLabel")
        marco.ejemplo.pack(side="right")
        return marco

    def _formulario(self, master: tk.Misc) -> tk.Frame:
        tarjeta = estilo.tarjeta(master)
        # Los botones van fijos abajo: siempre visibles aunque el formulario tenga que desplazarse.
        pie = ttk.Frame(tarjeta, style="Panel.TFrame", padding=(18, 10, 18, 14))
        pie.pack(side="bottom", fill="x")
        desplazable = MarcoDesplazable(tarjeta)
        desplazable.pack(side="top", fill="both", expand=True)
        f = ttk.Frame(desplazable.interior, style="Panel.TFrame", padding=(18, 18, 18, 4))
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Nuevo ingreso", style="Titulo.TLabel").pack(anchor="w", pady=(0, 12))

        self.var_tipo = tk.StringVar(value="vehiculo")
        self.campo_tipo = ttk.Frame(f, style="Panel.TFrame")
        self.campo_tipo.pack(fill="x", pady=(0, 12))
        for texto, valor in (("Vehículo", "vehiculo"), ("A pie", "peaton")):
            ttk.Radiobutton(
                self.campo_tipo, text=texto, value=valor, variable=self.var_tipo,
                style="Segmento.Toolbutton", command=self._cambio_tipo,
            ).pack(side="left", fill="x", expand=True)

        self.campo_dominio = self._campo(f, "Dominio")
        self.entrada_dominio = ttk.Entry(self.campo_dominio, style="Dominio.TEntry", width=32)
        self.entrada_dominio.pack(fill="x", pady=(4, 0))
        self.entrada_dominio.bind("<FocusOut>", self._formatear_dominio)

        self.campo_empresa = self._campo(f, "Empresa", opcional=True)
        self.entrada_empresa = CampoAutocompletar(self.campo_empresa, self.base, "empresa", width=30)
        self.entrada_empresa.pack(fill="x", pady=(4, 0))

        self.campo_particular = self._campo(f, "Particular")
        self.entrada_particular = CampoAutocompletar(self.campo_particular, self.base, "particular", width=30)
        self.entrada_particular.pack(fill="x", pady=(4, 0))

        self.campo_destino = self._campo(f, "Destino")
        self.entrada_destino = CampoAutocompletar(self.campo_destino, self.base, "destino", width=30)
        self.entrada_destino.pack(fill="x", pady=(4, 0))

        # Ficha de la agenda: aparece sola cuando el destino o la empresa coinciden con un contacto.
        self.ficha = tk.Frame(f, background=COLORES["gris"], highlightthickness=1,
                              highlightbackground=COLORES["borde"], padx=10, pady=8)
        self.ficha_texto = tk.Label(self.ficha, background=COLORES["gris"], foreground=COLORES["texto"],
                                    font=self.fuentes["normal"], justify="left", anchor="w", wraplength=270)
        self.ficha_texto.pack(fill="x")
        self._ficha_pendiente: str | None = None
        for entrada in (self.entrada_destino, self.entrada_empresa):
            entrada.bind("<KeyRelease>", lambda _e: self._programar_ficha(), add="+")
            entrada.bind("<<ComboboxSelected>>", lambda _e: self._programar_ficha(), add="+")

        self.campo_autorizo = self._campo(f, "Autorizó", opcional=True)
        self.entrada_autorizo = ttk.Entry(self.campo_autorizo, width=32)
        self.entrada_autorizo.pack(fill="x", pady=(4, 0))

        campo_obs = self._campo(f, "Observaciones", opcional=True)
        self.entrada_observaciones = tk.Text(
            campo_obs, height=2, width=30, wrap="word", relief="flat", padx=6, pady=5,
            font=self.fuentes["normal"], background=COLORES["panel"], foreground=COLORES["texto"],
            highlightthickness=1, highlightbackground=COLORES["linea"], highlightcolor=COLORES["azul"],
        )
        self.entrada_observaciones.pack(fill="x", pady=(4, 0))
        self.entrada_observaciones.bind("<Return>", self._enter_observaciones)
        self.entrada_observaciones.bind("<Tab>", self._tab_observaciones)

        ttk.Label(
            f, text="La fecha, la hora y la guardia de turno se\nregistran solas. Enter registra, Esc limpia.",
            style="Suave.TLabel", justify="left",
        ).pack(anchor="w", pady=(0, 4))

        botones = ttk.Frame(pie, style="Panel.TFrame")
        botones.pack(fill="x")
        self.boton_registrar = ttk.Button(
            botones, text="Registrar ingreso", style="Primario.TButton", command=self.registrar_ingreso
        )
        self.boton_registrar.pack(side="left", fill="x", expand=True)
        ttk.Button(botones, text="Limpiar", command=self.limpiar).pack(side="left", padx=(8, 0))

        self.etiqueta_mensaje = ttk.Label(pie, style="Aviso.TLabel", wraplength=300, justify="left")
        self.etiqueta_mensaje.pack(anchor="w", pady=(8, 0))

        for entrada in (self.entrada_dominio, self.entrada_empresa, self.entrada_particular, self.entrada_destino,
                        self.entrada_autorizo):
            entrada.bind("<Return>", lambda _e: self.registrar_ingreso())
            entrada.bind("<KP_Enter>", lambda _e: self.registrar_ingreso())
            entrada.bind("<Escape>", lambda _e: self.limpiar())
        self.entrada_observaciones.bind("<Escape>", lambda _e: self.limpiar())
        return tarjeta

    def _tabla(self, master: tk.Misc, columnas: tuple[str, ...]) -> ttk.Treeview:
        marco = ttk.Frame(master, style="Panel.TFrame")
        marco.pack(fill="both", expand=True)
        tabla = ttk.Treeview(marco, columns=columnas, show="headings", selectmode="browse")
        for columna in columnas:
            titulo, ancho, estira, alineacion = COLUMNAS[columna]
            tabla.heading(columna, text=titulo, anchor="w" if alineacion == "w" else alineacion)
            tabla.column(columna, width=ancho, minwidth=40, stretch=estira, anchor=alineacion)
        vertical = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        horizontal = ttk.Scrollbar(marco, orient="horizontal", command=tabla.xview)
        tabla.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        tabla.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        tabla.tag_configure("par", background=COLORES["fila_par"])
        tabla.tag_configure("anulado", foreground=COLORES["anulado"], font=self.fuentes["tachada"])
        tabla.tag_configure("v1", foreground=COLORES["suave"])
        tabla.bind("<<TreeviewSelect>>", lambda _e: self._actualizar_acciones())
        tabla.bind("<Double-1>", self._doble_clic)
        tabla.bind("<Return>", self._doble_clic)
        return tabla

    def _listas(self, master: tk.Misc) -> tk.Frame:
        tarjeta = estilo.tarjeta(master)
        self.barra_acciones = ttk.Frame(tarjeta, style="Panel.TFrame", padding=(12, 10))
        self.barra_acciones.pack(side="bottom", fill="x")
        self.pestanas = ttk.Notebook(tarjeta)
        self.pestanas.pack(side="top", fill="both", expand=True)
        self.pestanas.bind("<<NotebookTabChanged>>", lambda _e: self._actualizar_acciones())

        # Adentro ahora
        adentro = ttk.Frame(self.pestanas, style="Panel.TFrame", padding=12)
        barra = ttk.Frame(adentro, style="Panel.TFrame")
        barra.pack(fill="x", pady=(0, 10))
        self.var_filtro = tk.StringVar()
        self.entrada_filtro = EntradaConAyuda(barra, "Filtrar por dominio, empresa o persona",
                                              textvariable=self.var_filtro, width=34)
        self.entrada_filtro.pack(side="left")
        self.var_filtro.trace_add("write", lambda *_: self._cargar_adentro())
        ttk.Label(barra, text="Entraron y todavía no registraron la salida.", style="Suave.TLabel").pack(side="left", padx=12)
        self.tabla_adentro = self._tabla(adentro, COLUMNAS_ADENTRO)
        self.pestanas.add(adentro, text="Adentro ahora")

        # Registro del día
        dia = ttk.Frame(self.pestanas, style="Panel.TFrame", padding=12)
        barra = ttk.Frame(dia, style="Panel.TFrame")
        barra.pack(fill="x", pady=(0, 10))
        ttk.Button(barra, text="◀", width=3, command=lambda: self.mover_dia(-1)).pack(side="left")
        self.etiqueta_dia = ttk.Label(barra, style="Campo.TLabel", width=24, anchor="center")
        self.etiqueta_dia.pack(side="left", padx=6)
        ttk.Button(barra, text="▶", width=3, command=lambda: self.mover_dia(1)).pack(side="left")
        ttk.Button(barra, text="Hoy", command=self.ir_a_hoy).pack(side="left", padx=(8, 0))
        self.etiqueta_total_dia = ttk.Label(barra, style="Suave.TLabel")
        self.etiqueta_total_dia.pack(side="right")
        self.tabla_dia = self._tabla(dia, COLUMNAS_DIA)
        self.pestanas.add(dia, text="Registro del día")

        # Buscar
        buscar = ttk.Frame(self.pestanas, style="Panel.TFrame", padding=12)
        barra = ttk.Frame(buscar, style="Panel.TFrame")
        barra.pack(fill="x", pady=(0, 10))
        self.entrada_buscar = EntradaConAyuda(barra, "Dominio, empresa, persona…", width=30)
        self.entrada_buscar.pack(side="left")
        ttk.Label(barra, text="Desde", style="Panel.TLabel").pack(side="left", padx=(12, 4))
        self.entrada_desde = ttk.Entry(barra, width=11)
        self.entrada_desde.pack(side="left")
        ttk.Label(barra, text="Hasta", style="Panel.TLabel").pack(side="left", padx=(10, 4))
        self.entrada_hasta = ttk.Entry(barra, width=11)
        self.entrada_hasta.pack(side="left")
        ttk.Button(barra, text="Buscar", style="Primario.TButton", command=self.buscar).pack(side="left", padx=(12, 0))
        self.etiqueta_resultados = ttk.Label(barra, style="Suave.TLabel")
        self.etiqueta_resultados.pack(side="right")
        for entrada in (self.entrada_buscar, self.entrada_desde, self.entrada_hasta):
            entrada.bind("<Return>", lambda _e: self.buscar())
        self.tabla_buscar = self._tabla(buscar, COLUMNAS_BUSCAR)
        self.pestanas.add(buscar, text="Buscar")

        # Agenda
        agenda = ttk.Frame(self.pestanas, style="Panel.TFrame", padding=12)
        barra = ttk.Frame(agenda, style="Panel.TFrame")
        barra.pack(fill="x", pady=(0, 10))
        self.var_filtro_agenda = tk.StringVar()
        self.entrada_filtro_agenda = EntradaConAyuda(barra, "Buscar en la agenda", textvariable=self.var_filtro_agenda,
                                                     width=28)
        self.entrada_filtro_agenda.pack(side="left")
        self.var_filtro_agenda.trace_add("write", lambda *_: self._cargar_agenda())
        ttk.Button(barra, text="Nuevo contacto", style="Primario.TButton",
                   command=self.nuevo_contacto).pack(side="left", padx=(12, 0))
        self.boton_editar_contacto = ttk.Button(barra, text="Editar", command=self.editar_contacto)
        self.boton_editar_contacto.pack(side="left", padx=(8, 0))
        self.boton_eliminar_contacto = ttk.Button(barra, text="Eliminar", command=self.eliminar_contacto)
        self.boton_eliminar_contacto.pack(side="left", padx=(8, 0))
        ttk.Label(barra, text="No sale en los reportes", style="Suave.TLabel").pack(side="right")
        self.tabla_agenda = self._tabla(agenda, COLUMNAS_AGENDA)
        self.tabla_agenda.bind("<Double-1>", lambda _e: self.editar_contacto())
        self.tabla_agenda.bind("<Return>", lambda _e: self.editar_contacto())
        self.tabla_agenda.bind("<Delete>", lambda _e: self.eliminar_contacto())
        self.pestanas.add(agenda, text="Agenda")

        # Acciones sobre el registro elegido
        self.boton_salida = ttk.Button(self.barra_acciones, text="Registrar salida", style="Primario.TButton",
                                       command=self.registrar_salida)
        self.boton_salida.pack(side="left")
        self.boton_modificar = ttk.Button(self.barra_acciones, text="Modificar", command=self.modificar)
        self.boton_modificar.pack(side="left", padx=(8, 0))
        self.boton_anular = ttk.Button(self.barra_acciones, text="Anular…", command=self.anular)
        self.boton_anular.pack(side="left", padx=(8, 0))
        self.boton_historial = ttk.Button(self.barra_acciones, text="Ver historial", command=self.ver_historial)
        self.boton_historial.pack(side="left", padx=(8, 0))
        self.etiqueta_seleccion = ttk.Label(self.barra_acciones, style="Suave.TLabel")
        self.etiqueta_seleccion.pack(side="right")
        return tarjeta

    def _reportes(self) -> ttk.Frame:
        self.barra_reportes = ttk.Frame(self.root, style="Barra.TFrame", padding=(16, 10))
        ttk.Label(self.barra_reportes, text="Reporte", style="Campo.TLabel").pack(side="left")
        self.var_periodo = tk.StringVar(value=PERIODOS[0])
        ttk.Combobox(self.barra_reportes, textvariable=self.var_periodo, values=PERIODOS, state="readonly",
                     width=16).pack(side="left", padx=(10, 10))
        ttk.Button(self.barra_reportes, text="Exportar PDF", style="Contorno.TButton",
                   command=self.exportar_pdf).pack(side="left")
        ttk.Button(self.barra_reportes, text="Enviar por correo", style="Contorno.TButton",
                   command=self.enviar_correo).pack(side="left", padx=(8, 0))
        self.etiqueta_respaldo = ttk.Label(self.barra_reportes, style="Suave.TLabel")
        self.etiqueta_respaldo.pack(side="right")
        return self.barra_reportes

    def _barra_estado(self) -> ttk.Frame:
        barra = ttk.Frame(self.root, style="Estado.TFrame", padding=(12, 3))
        ttk.Label(barra, text=f"IngresosApp {__version__}", style="Estado.TLabel").pack(side="left")
        ttk.Label(barra, text=f"Datos: {self.carpeta}", style="Estado.TLabel").pack(side="left", padx=16)
        ttk.Label(barra, text="F1: ver el recorrido de la app", style="Estado.TLabel").pack(side="right")
        return barra

    # ------------------------------------------------------------------
    # Formulario
    # ------------------------------------------------------------------

    def _cambio_tipo(self) -> None:
        if self.var_tipo.get() == "peaton":
            self.entrada_dominio.delete(0, "end")
            self.entrada_dominio.state(["disabled"])
            self.entrada_particular.focus_set()
        else:
            self.entrada_dominio.state(["!disabled"])
            self.entrada_dominio.focus_set()

    def _formatear_dominio(self, _evento=None) -> None:
        texto = self.entrada_dominio.get()
        if texto:
            self.entrada_dominio.delete(0, "end")
            self.entrada_dominio.insert(0, formatear_dominio(texto))

    def _enter_observaciones(self, evento):
        if evento.state & 0x0001:  # Shift+Enter agrega un renglón
            return None
        self.registrar_ingreso()
        return "break"

    def _tab_observaciones(self, evento):
        evento.widget.tk_focusNext().focus_set()
        return "break"

    def nuevo_ingreso(self) -> None:
        (self.entrada_particular if self.var_tipo.get() == "peaton" else self.entrada_dominio).focus_set()

    def limpiar(self) -> None:
        for entrada in (self.entrada_dominio, self.entrada_empresa, self.entrada_particular, self.entrada_destino,
                        self.entrada_autorizo):
            entrada.delete(0, "end")
        self.entrada_observaciones.delete("1.0", "end")
        self._actualizar_ficha()
        self.nuevo_ingreso()

    def _programar_ficha(self) -> None:
        if self._ficha_pendiente:
            self.root.after_cancel(self._ficha_pendiente)
        self._ficha_pendiente = self.root.after(250, self._actualizar_ficha)

    def _actualizar_ficha(self) -> None:
        self._ficha_pendiente = None
        contactos = self.base.contactos_para(self.entrada_destino.get(), self.entrada_empresa.get())
        if not contactos:
            self.ficha.pack_forget()
            return
        lineas = []
        for c in contactos:
            cabecera = " · ".join(x for x in (c.nombre, c.contacto) if x)
            lineas.append(cabecera)
            if c.telefonos:
                lineas.append(f"Tel.: {c.telefonos}")
            if c.notas:
                lineas.append(c.notas)
            lineas.append("")
        self.ficha_texto.configure(text="\n".join(lineas).strip())
        self.ficha.pack(fill="x", pady=(0, 10), after=self.campo_destino)

    def mensaje(self, texto: str) -> None:
        self.etiqueta_mensaje.configure(text=texto)
        self._mensaje_pendiente = texto
        self.root.after(8000, lambda: self._borrar_mensaje(texto))

    def _borrar_mensaje(self, texto: str) -> None:
        if self._mensaje_pendiente == texto:
            self.etiqueta_mensaje.configure(text="")

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _guardia_requerida(self) -> bool:
        if self.base.turno_actual():
            return True
        messagebox.showinfo("Guardia de turno", "Antes de registrar, indicá quién está de guardia.", parent=self.root)
        return self.cambiar_turno()

    def registrar_ingreso(self) -> None:
        if not self._guardia_requerida():
            return
        tipo = self.var_tipo.get()
        dominio = self.entrada_dominio.get()
        if tipo == "vehiculo":
            repetidos = self.base.adentro_con_dominio(dominio)
            if repetidos and not messagebox.askyesno(
                "Vehículo adentro",
                f"{formatear_dominio(dominio)} figura adentro desde las {formato.hora(repetidos[0].ingreso)} "
                f"({repetidos[0].particular}).\n\n¿Registrar otro ingreso igual?",
                parent=self.root,
            ):
                return
        try:
            registro = self.base.registrar_ingreso(
                tipo=tipo, dominio=dominio, empresa=self.entrada_empresa.get(),
                particular=self.entrada_particular.get(), destino=self.entrada_destino.get(),
                autorizo=self.entrada_autorizo.get(), observaciones=self.entrada_observaciones.get("1.0", "end"),
            )
        except ErrorDeDatos as e:
            messagebox.showwarning("Revisá los datos", str(e), parent=self.root)
            return
        self.limpiar()
        self.mensaje(f"Ingreso Nº {registro.id} registrado a las {formato.hora(registro.ingreso)}: "
                     f"{formato.resumen(registro)}.")
        self.pestanas.select(0)
        self.actualizar_todo(seleccionar=registro.id)

    def _seleccionado(self) -> Registro | None:
        tabla = self._tabla_actual()
        if tabla is None:
            return None
        seleccion = tabla.selection()
        if not seleccion:
            return None
        try:
            return self.base.obtener(int(seleccion[0]))
        except ErrorDeDatos:
            return None

    def _tabla_actual(self) -> ttk.Treeview | None:
        indice = self.pestanas.index("current")
        if indice == PESTANA_AGENDA:
            return None
        return (self.tabla_adentro, self.tabla_dia, self.tabla_buscar)[indice]

    def _pedir_seleccion(self) -> Registro | None:
        registro = self._seleccionado()
        if registro is None:
            messagebox.showinfo("Elegí un registro", "Primero seleccioná un registro de la lista.", parent=self.root)
        return registro

    def _doble_clic(self, _evento=None) -> None:
        registro = self._seleccionado()
        if registro is None:
            return
        if registro.adentro:
            self.registrar_salida()
        else:
            self.ver_historial()

    def registrar_salida(self) -> None:
        registro = self._pedir_seleccion()
        if registro is None or not self._guardia_requerida():
            return
        if not registro.adentro:
            messagebox.showinfo("Registrar salida", f"El registro Nº {registro.id} no figura adentro "
                                f"({formato.estado(registro).lower()}).", parent=self.root)
            return
        if not messagebox.askyesno(
            "Registrar salida",
            f"¿Registrar la salida de {formato.resumen(registro)}?\nIngresó a las {formato.hora(registro.ingreso)}.",
            parent=self.root,
        ):
            return
        try:
            registro = self.base.registrar_salida(registro.id)
        except ErrorDeDatos as e:
            messagebox.showwarning("Registrar salida", str(e), parent=self.root)
            return
        self.mensaje(f"Salida registrada a las {formato.hora(registro.salida)}: {formato.resumen(registro)}.")
        self.actualizar_todo()

    def modificar(self) -> None:
        registro = self._pedir_seleccion()
        if registro is None or not self._guardia_requerida():
            return
        if registro.anulado:
            messagebox.showinfo("Modificar", "Un registro anulado no se puede modificar.", parent=self.root)
            return
        if DialogoModificar(self.root, self.base, registro).mostrar():
            self.mensaje(f"Registro Nº {registro.id} modificado. El cambio quedó en el historial.")
            self.actualizar_todo(seleccionar=registro.id)

    def anular(self) -> None:
        registro = self._pedir_seleccion()
        if registro is None or not self._guardia_requerida():
            return
        if registro.anulado:
            messagebox.showinfo("Anular", f"El registro Nº {registro.id} ya está anulado.", parent=self.root)
            return
        if DialogoAnular(self.root, self.base, registro).mostrar():
            self.mensaje(f"Registro Nº {registro.id} anulado.")
            self.actualizar_todo(seleccionar=registro.id)

    def ver_historial(self) -> None:
        registro = self._pedir_seleccion()
        if registro is not None:
            DialogoHistorial(self.root, self.base, registro).mostrar()

    def cambiar_turno(self, obligatorio: bool = False) -> bool:
        resultado = DialogoTurno(self.root, self.base, obligatorio=obligatorio).mostrar()
        if resultado == "salir":
            self.salir()
            return False
        if resultado:
            self.actualizar_turno()
            self.mensaje(f"Turno de {resultado.guardia} desde las {formato.hora(resultado.inicio)}.")
            return True
        return False

    def configurar_puesto(self, inicial: bool = False) -> None:
        if DialogoPuesto(self.root, self.base, inicial=inicial).mostrar():
            self.aplicar_perfil()
            self.actualizar_turno()

    def aplicar_perfil(self) -> None:
        """Ajusta etiquetas y ejemplos al tipo de lugar (barrio, parque, empresa…)."""
        perfil = perfiles.actual(self.base)
        self.campo_empresa.titulo.configure(text=perfil.etiqueta_empresa)
        self.campo_empresa.ejemplo.configure(text=perfil.ej_empresa)
        self.campo_destino.ejemplo.configure(text=perfil.ej_destino)
        self.campo_autorizo.ejemplo.configure(text=perfil.ej_autorizo)

    # Agenda
    def _contacto_seleccionado(self) -> Contacto | None:
        seleccion = self.tabla_agenda.selection()
        if not seleccion:
            return None
        try:
            return self.base.contacto(int(seleccion[0]))
        except ErrorDeDatos:
            return None

    def nuevo_contacto(self) -> None:
        contacto = DialogoContacto(self.root, self.base, perfiles.actual(self.base)).mostrar()
        if contacto:
            self._cargar_agenda(seleccionar=contacto.id)
            self._actualizar_ficha()

    def editar_contacto(self) -> None:
        contacto = self._contacto_seleccionado()
        if contacto is None:
            messagebox.showinfo("Agenda", "Primero seleccioná un contacto de la lista.", parent=self.root)
            return
        if DialogoContacto(self.root, self.base, perfiles.actual(self.base), contacto).mostrar():
            self._cargar_agenda(seleccionar=contacto.id)
            self._actualizar_ficha()

    def eliminar_contacto(self) -> None:
        contacto = self._contacto_seleccionado()
        if contacto is None:
            messagebox.showinfo("Agenda", "Primero seleccioná un contacto de la lista.", parent=self.root)
            return
        if messagebox.askyesno(
            "Eliminar contacto",
            f"¿Eliminar «{contacto.nombre}» de la agenda?\n\n"
            "Se borra definitivamente. Los ingresos ya registrados no cambian.",
            parent=self.root,
        ):
            self.base.eliminar_contacto(contacto.id)
            self._cargar_agenda()
            self._actualizar_ficha()

    # Reportes y correo
    def _periodo_elegido(self) -> reportes.Periodo | None:
        nombre = self.var_periodo.get()
        if nombre == "Elegir fechas…":
            return DialogoFechas(self.root).mostrar()
        return reportes.periodo_por_nombre(nombre)

    def _generar_pdf(self, periodo: reportes.Periodo, destino: Path) -> Path:
        turno = self.base.turno_actual()
        return reportes.generar_pdf(
            self.base.entre_fechas(periodo.desde, periodo.hasta), periodo, destino,
            puesto=self.base.ajuste("puesto", "") or "",
            generado_por=turno.guardia if turno else "",
        )

    def _carpeta_reportes(self) -> Path:
        carpeta = self.carpeta / "reportes"
        carpeta.mkdir(parents=True, exist_ok=True)
        return carpeta

    def exportar_pdf(self) -> None:
        periodo = self._periodo_elegido()
        if periodo is None:
            return
        archivo = filedialog.asksaveasfilename(
            parent=self.root, title="Guardar reporte en PDF", defaultextension=".pdf",
            initialdir=str(self._carpeta_reportes()), initialfile=periodo.nombre_archivo(),
            filetypes=[("PDF", "*.pdf")],
        )
        if not archivo:
            return
        try:
            ruta = self._generar_pdf(periodo, Path(archivo))
        except OSError as e:
            messagebox.showwarning("Exportar PDF", f"No se pudo guardar el PDF:\n{e}\n\n"
                                   "Si el archivo está abierto en otro programa, cerralo y probá de nuevo.",
                                   parent=self.root)
            return
        self.mensaje(f"Reporte guardado: {ruta.name}")
        abrir_en_sistema(ruta)

    def enviar_correo(self) -> None:
        config = correo.leer_config(self.base)
        clave = correo.contrasena_guardada(config.remitente) if config.completa else None
        if not (config.completa and clave):
            if messagebox.askyesno(
                "Enviar por correo",
                "El envío por correo todavía no está configurado.\n\n¿Configurarlo ahora?\n"
                "(Si elegís «No», se genera el PDF y se abre tu programa de correo para adjuntarlo a mano.)",
                parent=self.root,
            ):
                self.configurar_correo()
                return
            self._enviar_a_mano()
            return
        periodo = self._periodo_elegido()
        if periodo is None:
            return
        if not messagebox.askyesno(
            "Enviar por correo",
            f"¿Enviar el reporte {periodo.texto()} a {config.destinatarios}?", parent=self.root,
        ):
            return
        ruta = self._generar_pdf(periodo, self._carpeta_reportes() / periodo.nombre_archivo())
        asunto, cuerpo = self._textos_correo(periodo)
        self.mensaje("Enviando el reporte por correo…")
        resultado: list[str] = []

        def tarea():
            try:
                correo.enviar(config, clave, asunto, cuerpo, ruta)
                resultado.append("ok")
            except correo.ErrorDeCorreo as e:
                resultado.append(str(e))

        hilo = threading.Thread(target=tarea, daemon=True)
        hilo.start()

        def esperar():
            if hilo.is_alive():
                self.root.after(200, esperar)
            elif resultado and resultado[0] == "ok":
                self.mensaje(f"Reporte {periodo.texto()} enviado a {config.destinatarios}.")
            else:
                self.mensaje("No se pudo enviar el reporte.")
                messagebox.showwarning("Enviar por correo", resultado[0] if resultado else "No se pudo enviar.",
                                       parent=self.root)

        esperar()

    def _textos_correo(self, periodo: reportes.Periodo) -> tuple[str, str]:
        puesto = self.base.ajuste("puesto", "") or "Puesto de control"
        registros = [r for r in self.base.entre_fechas(periodo.desde, periodo.hasta) if not r.anulado]
        asunto = f"IngresosApp · {puesto} · Reporte {periodo.texto()}"
        cuerpo = (f"Reporte de ingresos y salidas {periodo.texto()}.\n"
                  f"{puesto}\n\n{len(registros)} registros. El detalle está en el PDF adjunto.\n\n"
                  f"Enviado con IngresosApp {__version__}.")
        return asunto, cuerpo

    def _enviar_a_mano(self) -> None:
        periodo = self._periodo_elegido()
        if periodo is None:
            return
        ruta = self._generar_pdf(periodo, self._carpeta_reportes() / periodo.nombre_archivo())
        asunto, cuerpo = self._textos_correo(periodo)
        destinatarios = self.base.ajuste("correo_destinatarios", "") or ""
        webbrowser.open(correo.enlace_mailto(destinatarios, asunto, cuerpo))
        abrir_en_sistema(ruta.parent)
        messagebox.showinfo(
            "Enviar por correo",
            f"Se generó el reporte {ruta.name} y se abrió la carpeta donde está.\n"
            "Adjuntalo al correo que se abrió en tu programa de correo.",
            parent=self.root,
        )

    def configurar_correo(self) -> None:
        if DialogoCorreo(self.root, self.base).mostrar():
            self.mensaje("Configuración de correo guardada.")

    def abrir_carpeta_datos(self) -> None:
        abrir_en_sistema(self.carpeta)

    def importar_v1(self) -> None:
        archivo = filedialog.askopenfilename(
            parent=self.root, title="Elegí el archivo «base» de IngresosApp 1.0",
            filetypes=[("Base de IngresosApp 1.0", "base"), ("Todos los archivos", "*")],
        )
        if not archivo:
            return
        try:
            cantidad = self.base.importar_base_v1(Path(archivo))
        except Exception as e:  # archivo dañado o que no es una base de datos
            messagebox.showwarning("Importar", f"No se pudo leer el archivo:\n{e}", parent=self.root)
            return
        if cantidad:
            messagebox.showinfo("Importar", f"Se importaron {cantidad} registros de la versión 1.0.\n"
                                "El archivo original no se modificó.", parent=self.root)
        else:
            messagebox.showinfo("Importar", "No había registros nuevos para importar "
                                "(el archivo está vacío o ya se había importado).", parent=self.root)
        self.actualizar_todo()

    def respaldar(self, silencioso: bool = False) -> None:
        try:
            archivo = self.base.respaldar(rutas.carpeta_respaldos(self.carpeta))
        except Exception as e:
            self.etiqueta_respaldo.configure(text="No se pudo hacer la copia de seguridad")
            if not silencioso:
                messagebox.showwarning("Copia de seguridad", f"No se pudo hacer la copia:\n{e}", parent=self.root)
            return
        self._dia_respaldo = date.today()
        momento = datetime.fromtimestamp(archivo.stat().st_mtime)
        self.etiqueta_respaldo.configure(text=f"Copia de seguridad del día: {momento:%H:%M}")
        if not silencioso:
            messagebox.showinfo("Copia de seguridad", f"La copia del día está en:\n{archivo}", parent=self.root)

    def ver_recorrido(self) -> None:
        if getattr(self, "_recorrido", None) and self._recorrido.activo:
            return
        self._recorrido = Recorrido(self.root, self._pasos_recorrido(), self._fin_recorrido)
        self._recorrido.empezar()

    def _fin_recorrido(self) -> None:
        self.base.guardar_ajuste("recorrido_visto", "1")
        self.nuevo_ingreso()

    def acerca_de(self) -> None:
        AcercaDe(self.root, self.carpeta).mostrar()

    def salir(self) -> None:
        self.cerrada = True
        self.root.destroy()

    # ------------------------------------------------------------------
    # Listas
    # ------------------------------------------------------------------

    def actualizar_turno(self) -> None:
        puesto = self.base.ajuste("puesto", "") or "Configurá el nombre en Configuración → Puesto y tipo de lugar"
        self.etiqueta_puesto.configure(text=puesto)
        turno = self.base.turno_actual()
        if turno:
            self.etiqueta_desde.configure(text=f"Guardia de turno · desde las {formato.hora(turno.inicio)}")
            self.etiqueta_guardia.configure(text=turno.guardia)
        else:
            self.etiqueta_desde.configure(text="Guardia de turno")
            self.etiqueta_guardia.configure(text="Sin asignar")

    def actualizar_todo(self, seleccionar: int | None = None) -> None:
        self._cargar_adentro(seleccionar)
        self._cargar_dia(seleccionar)
        self._cargar_agenda()
        if self.ultima_busqueda:
            self._ejecutar_busqueda(*self.ultima_busqueda)
        self._actualizar_acciones()

    def _valores(self, registro: Registro, columnas: tuple[str, ...], ahora: datetime) -> tuple[str, ...]:
        valores = {
            "n": str(registro.id),
            "fecha": formato.fecha(registro.ingreso),
            "ingreso": formato.hora(registro.ingreso),
            "salida": formato.hora(registro.salida) or "—",
            "tipo": formato.tipo(registro),
            "dominio": formato.dominio(registro),
            "empresa": registro.empresa or "—",
            "particular": registro.particular,
            "destino": registro.destino,
            "guardia": formato.guardia_corta(registro.guardia_ingreso) or "—",
            "tiempo": formato.duracion(registro.momento_ingreso, ahora),
            "estado": formato.estado(registro),
            "autorizo": registro.autorizo or "—",
        }
        return tuple(valores[c] for c in columnas)

    def _llenar(self, tabla: ttk.Treeview, registros: list[Registro], columnas: tuple[str, ...],
                seleccionar: int | None = None) -> None:
        anterior = tabla.selection()
        elegido = str(seleccionar) if seleccionar is not None else (anterior[0] if anterior else None)
        tabla.delete(*tabla.get_children())
        ahora = datetime.now()
        for i, registro in enumerate(registros):
            etiquetas = ["par"] if i % 2 else []
            if registro.anulado:
                etiquetas.append("anulado")
            elif registro.origen == "v1":
                etiquetas.append("v1")
            tabla.insert("", "end", iid=str(registro.id), values=self._valores(registro, columnas, ahora),
                         tags=etiquetas)
        if elegido and tabla.exists(elegido):
            tabla.selection_set(elegido)
            tabla.see(elegido)

    def _cargar_adentro(self, seleccionar: int | None = None) -> None:
        registros = self.base.adentro()
        filtro = self.entrada_filtro.valor().lower() if hasattr(self, "entrada_filtro") else ""
        if filtro:
            compacto = filtro.replace(" ", "").upper()
            registros = [
                r for r in registros
                if compacto in r.dominio or filtro in r.empresa.lower() or filtro in r.particular.lower()
                or filtro in r.destino.lower()
            ]
        self._llenar(self.tabla_adentro, registros, COLUMNAS_ADENTRO, seleccionar)
        self.pestanas.tab(0, text=f"Adentro ahora ({len(self.base.adentro())})")

    def _cargar_dia(self, seleccionar: int | None = None) -> None:
        registros = self.base.del_dia(self.dia_mostrado)
        self._llenar(self.tabla_dia, registros, COLUMNAS_DIA, seleccionar)
        validos = [r for r in registros if not r.anulado]
        anulados = len(registros) - len(validos)
        es_hoy = self.dia_mostrado == date.today()
        self.etiqueta_dia.configure(text=("Hoy, " if es_hoy else "") + formato.fecha_larga(self.dia_mostrado))
        resumen = f"{len(validos)} ingresos"
        if anulados:
            resumen += f" · {anulados} anulado{'s' if anulados > 1 else ''}"
        self.etiqueta_total_dia.configure(text=resumen)
        self.pestanas.tab(1, text=f"Registro del día ({len(validos)})" if es_hoy else "Registro del día")

    def _cargar_agenda(self, seleccionar: int | None = None) -> None:
        if not hasattr(self, "tabla_agenda"):
            return
        tabla = self.tabla_agenda
        anterior = tabla.selection()
        elegido = str(seleccionar) if seleccionar is not None else (anterior[0] if anterior else None)
        tabla.delete(*tabla.get_children())
        for i, c in enumerate(self.base.agenda(self.entrada_filtro_agenda.valor())):
            tabla.insert("", "end", iid=str(c.id), tags=["par"] if i % 2 else [],
                         values=(c.nombre, c.ubicacion, c.telefonos, c.contacto, " ".join(c.notas.split())))
        if elegido and tabla.exists(elegido):
            tabla.selection_set(elegido)
            tabla.see(elegido)
        cantidad = len(self.base.agenda())
        self.pestanas.tab(PESTANA_AGENDA, text=f"Agenda ({cantidad})" if cantidad else "Agenda")

    def mover_dia(self, dias: int) -> None:
        self.dia_mostrado += timedelta(days=dias)
        self._cargar_dia()
        self._actualizar_acciones()

    def ir_a_hoy(self) -> None:
        self.dia_mostrado = date.today()
        self._cargar_dia()
        self._actualizar_acciones()

    def buscar(self) -> None:
        texto = self.entrada_buscar.valor()
        try:
            desde = formato.leer_fecha(self.entrada_desde.get()) if self.entrada_desde.get().strip() else None
            hasta = formato.leer_fecha(self.entrada_hasta.get()) if self.entrada_hasta.get().strip() else None
        except ErrorDeDatos as e:
            messagebox.showwarning("Buscar", str(e), parent=self.root)
            return
        self.ultima_busqueda = (texto, desde, hasta)
        self._ejecutar_busqueda(texto, desde, hasta)
        self._actualizar_acciones()

    def _ejecutar_busqueda(self, texto: str, desde: date | None, hasta: date | None) -> None:
        resultados = self.base.buscar(texto, desde, hasta, limite=500)
        self._llenar(self.tabla_buscar, resultados, COLUMNAS_BUSCAR)
        if len(resultados) == 500:
            self.etiqueta_resultados.configure(text="Se muestran los 500 más recientes. Acotá la búsqueda.")
        else:
            self.etiqueta_resultados.configure(text=f"{len(resultados)} resultado{'s' if len(resultados) != 1 else ''}")

    def _actualizar_acciones(self) -> None:
        if not hasattr(self, "boton_salida"):
            return
        en_agenda = self.pestanas.index("current") == PESTANA_AGENDA
        if en_agenda:
            self.barra_acciones.pack_forget()
            hay_contacto = bool(self.tabla_agenda.selection())
            for boton in (self.boton_editar_contacto, self.boton_eliminar_contacto):
                boton.state(["!disabled"] if hay_contacto else ["disabled"])
            return
        if not self.barra_acciones.winfo_manager():
            self.barra_acciones.pack(side="bottom", fill="x", before=self.pestanas)
        registro = self._seleccionado()
        hay = registro is not None
        self.boton_salida.state(["!disabled"] if hay and registro.adentro else ["disabled"])
        editable = hay and not registro.anulado
        self.boton_modificar.state(["!disabled"] if editable else ["disabled"])
        self.boton_anular.state(["!disabled"] if editable else ["disabled"])
        self.boton_historial.state(["!disabled"] if hay else ["disabled"])
        self.etiqueta_seleccion.configure(
            text=f"Seleccionado: Nº {registro.id} · {formato.resumen(registro)}" if hay else "Seleccioná un registro de la lista"
        )

    # ------------------------------------------------------------------
    # Reloj, tareas periódicas y errores
    # ------------------------------------------------------------------

    def _tic_reloj(self) -> None:
        ahora = datetime.now()
        self.etiqueta_hora.configure(text=f"{ahora:%H:%M}")
        self.etiqueta_fecha.configure(text=formato.fecha_larga(ahora.date()))
        self.root.after(1000 - ahora.microsecond // 1000, self._tic_reloj)

    def _tic_periodico(self) -> None:
        hoy = date.today()
        if self._dia_respaldo != hoy:
            if self.dia_mostrado == hoy - timedelta(days=1):
                self.dia_mostrado = hoy
            self.respaldar(silencioso=True)
        self.actualizar_todo()
        self.root.after(30_000, self._tic_periodico)

    def _error_inesperado(self, tipo, valor, rastro) -> None:
        detalle = "".join(traceback.format_exception(tipo, valor, rastro))
        archivo = self.carpeta / "errores.log"
        try:
            with archivo.open("a", encoding="utf-8") as log:
                log.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} · IngresosApp {__version__}\n{detalle}\n")
        except OSError:
            pass
        messagebox.showerror(
            "Ocurrió un error inesperado",
            f"{valor}\n\nLos datos ya guardados no se perdieron. El detalle quedó en:\n{archivo}",
            parent=self.root,
        )

    # ------------------------------------------------------------------
    # Recorrido
    # ------------------------------------------------------------------

    def _pasos_recorrido(self) -> list[Paso]:
        perfil = perfiles.actual(self.base)
        ir_a = lambda indice: (lambda: self.pestanas.select(indice))  # noqa: E731
        destino = perfil.ej_destino.removeprefix("ej.: ")
        return [
            Paso(lambda: self.caja_turno, "Guardia de turno",
                 "Al empezar cada turno, la guardia que entra pone su nombre con «Cambiar turno». "
                 "Todo lo que se registre queda firmado con ese nombre."),
            Paso(lambda: self.campo_tipo, "Vehículo o a pie",
                 "Elegí «Vehículo» si entra con auto, camión o moto, y «A pie» si entra caminando. "
                 "A pie no hace falta el dominio."),
            Paso(lambda: self.campo_dominio, "Dominio",
                 "La patente del vehículo. Se puede escribir con o sin espacios: «ab123cd» queda AB 123 CD."),
            Paso(lambda: self.campo_empresa, perfil.etiqueta_empresa,
                 "De dónde viene o a qué viene la persona: una empresa, un delivery, una obra, una visita. "
                 "Es opcional, y con el uso la app sugiere lo que ya se cargó."),
            Paso(lambda: self.campo_particular, "Particular",
                 "El nombre y apellido completo de la persona que entra o sale del predio."),
            Paso(lambda: self.campo_destino, "Destino",
                 f"A dónde va dentro del predio ({destino}). Si ese lugar está en la Agenda, "
                 "debajo aparece su ficha con el teléfono, lista para llamar."),
            Paso(lambda: self.campo_autorizo, "Autorizó",
                 "Quién dio el permiso para entrar, si hizo falta pedirlo: por ejemplo, el vecino que "
                 "atendió el llamado o el responsable del sector. Queda en el historial y en los reportes."),
            Paso(lambda: self.boton_registrar, "Registrar ingreso",
                 "Guarda el ingreso. La fecha y la hora las pone la app, nadie las escribe a mano. "
                 "En Observaciones se puede anotar algo útil, como «trae carga» o «remís». "
                 "Atajos: Enter para registrar y Esc para limpiar."),
            Paso(lambda: self.tabla_adentro, "Adentro ahora",
                 "Quienes entraron y todavía no salieron, con cuánto tiempo llevan adentro. "
                 "Cuando alguien se va, seleccionalo y tocá «Registrar salida» (o hacé doble clic).",
                 antes=ir_a(0)),
            Paso(lambda: self.barra_acciones, "Corregir sin borrar",
                 "«Modificar» corrige los datos y «Anular…» deja el registro tachado con un motivo. "
                 "Nada se borra: «Ver historial» muestra todo lo que le pasó a cada registro."),
            Paso(lambda: self.pestanas, "Registro del día y Buscar",
                 "En «Registro del día» está todo lo que pasó en una fecha, y en «Buscar» se encuentra "
                 "cualquier dominio, empresa o persona.", antes=ir_a(1)),
            Paso(lambda: self.pestanas, "Agenda",
                 f"Los teléfonos que la guardia necesita a mano: {perfil.agenda}. "
                 "Los contactos se pueden editar y eliminar en cualquier momento.\n\n"
                 "Son datos personales: cargá solo lo necesario para el trabajo de la guardia y borrá lo que "
                 "ya no sirva. En Argentina, su tratamiento está alcanzado por la Ley 25.326 de Protección de "
                 "Datos Personales. La agenda queda solo en este equipo y nunca sale en los reportes ni en los correos. "
                 "Tené en cuenta que las copias de seguridad diarias guardan la base completa: un contacto eliminado "
                 "sigue en esas copias hasta que se borran solas, a los 30 días.",
                 antes=ir_a(PESTANA_AGENDA)),
            Paso(lambda: self.barra_reportes, "Reportes",
                 "Elegí el período y exportalo a PDF para imprimir, o envialo por correo al encargado "
                 "(la cuenta se configura una vez en Configuración → Envío por correo). "
                 "Este recorrido se puede repetir con F1 o desde Ayuda.", antes=ir_a(0)),
        ]


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------

class MarcoDesplazable(tk.Frame):
    """Contenedor con barra de desplazamiento vertical que aparece solo si hace falta.

    Permite usar la app en pantallas bajas (por ejemplo notebooks de 1366×768)
    sin que el formulario quede cortado.
    """

    def __init__(self, master: tk.Misc):
        super().__init__(master, background=COLORES["panel"])
        self.lienzo = tk.Canvas(self, background=COLORES["panel"], highlightthickness=0, borderwidth=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        self.lienzo.configure(yscrollcommand=self.barra.set)
        self.interior = ttk.Frame(self.lienzo, style="Panel.TFrame")
        self._ventana = self.lienzo.create_window(0, 0, window=self.interior, anchor="nw")
        self.lienzo.pack(side="left", fill="both", expand=True)
        self.interior.bind("<Configure>", self._ajustar)
        self.lienzo.bind("<Configure>", self._ajustar)
        self.bind_all("<MouseWheel>", self._rueda, add="+")
        self.bind_all("<Button-4>", self._rueda, add="+")
        self.bind_all("<Button-5>", self._rueda, add="+")

    def _ajustar(self, _evento=None) -> None:
        ancho = self.interior.winfo_reqwidth()
        alto = self.interior.winfo_reqheight()
        self.lienzo.configure(width=ancho, scrollregion=(0, 0, ancho, alto))
        self.lienzo.itemconfigure(self._ventana, width=max(ancho, self.lienzo.winfo_width()))
        if alto > self.lienzo.winfo_height() > 1:
            if not self.barra.winfo_ismapped():
                self.barra.pack(side="right", fill="y")
        elif self.barra.winfo_ismapped():
            self.barra.pack_forget()
            self.lienzo.yview_moveto(0)

    def _rueda(self, evento) -> None:
        if not self.barra.winfo_ismapped():
            return
        widget = self.winfo_containing(evento.x_root, evento.y_root)
        while widget is not None and widget is not self:
            widget = widget.master
        if widget is None:
            return
        paso = -1 if getattr(evento, "num", 0) == 4 or getattr(evento, "delta", 0) > 0 else 1
        self.lienzo.yview_scroll(paso * 2, "units")


class EntradaConAyuda(ttk.Entry):
    """Campo con un texto gris de ayuda mientras está vacío."""

    def __init__(self, master: tk.Misc, ayuda: str, **kwargs):
        super().__init__(master, **kwargs)
        self.ayuda = ayuda
        self.mostrando_ayuda = False
        self.bind("<FocusIn>", self._sacar_ayuda, add="+")
        self.bind("<FocusOut>", self._poner_ayuda, add="+")
        self._poner_ayuda()

    def _poner_ayuda(self, _evento=None) -> None:
        if not self.get():
            self.mostrando_ayuda = True
            self.insert(0, self.ayuda)
            self.configure(foreground=COLORES["anulado"])

    def _sacar_ayuda(self, _evento=None) -> None:
        if self.mostrando_ayuda:
            self.mostrando_ayuda = False
            self.delete(0, "end")
            self.configure(foreground=COLORES["texto"])

    def valor(self) -> str:
        return "" if self.mostrando_ayuda else self.get().strip()


def abrir_en_sistema(ruta: Path) -> None:
    if sys.platform == "win32":
        os.startfile(ruta)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
    else:
        subprocess.Popen(["xdg-open", str(ruta)])
