"""Reportes en PDF.

Una tabla de verdad, con bordes y columnas de ancho fijo, en hoja A4
horizontal. Los textos largos pasan a un segundo renglón en lugar de pisarse,
los anulados se ven tachados con su motivo y la última hoja tiene lugar para
la firma del encargado. La agenda nunca se incluye.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from . import __version__
from .db import Registro
from .patentes import formatear_dominio

RECURSOS = Path(__file__).resolve().parent / "recursos"
AZUL = (29, 62, 123)
NOCHE = (11, 18, 32)
GRIS_TEXTO = (75, 85, 99)
GRIS_ANULADO = (138, 145, 156)
GRIS_FILA = (241, 244, 248)


@dataclass(frozen=True)
class Periodo:
    desde: date
    hasta: date

    @property
    def un_dia(self) -> bool:
        return self.desde == self.hasta

    def texto(self) -> str:
        if self.un_dia:
            return f"{self.desde:%d/%m/%Y}"
        return f"del {self.desde:%d/%m/%Y} al {self.hasta:%d/%m/%Y}"

    def nombre_archivo(self) -> str:
        if self.un_dia:
            return f"ingresos_{self.desde:%Y-%m-%d}.pdf"
        return f"ingresos_{self.desde:%Y-%m-%d}_al_{self.hasta:%Y-%m-%d}.pdf"


def periodo_por_nombre(nombre: str, hoy: date | None = None) -> Periodo:
    """Traduce las opciones del selector de la ventana a fechas."""
    hoy = hoy or date.today()
    if nombre == "Hoy":
        return Periodo(hoy, hoy)
    if nombre == "Ayer":
        ayer = hoy - timedelta(days=1)
        return Periodo(ayer, ayer)
    if nombre == "Últimos 7 días":
        return Periodo(hoy - timedelta(days=6), hoy)
    if nombre == "Este mes":
        return Periodo(hoy.replace(day=1), hoy)
    if nombre == "Mes anterior":
        fin = hoy.replace(day=1) - timedelta(days=1)
        return Periodo(fin.replace(day=1), fin)
    raise ValueError(f"Período desconocido: {nombre}")


class _Documento(FPDF):
    def __init__(self, titulo_pie: str):
        super().__init__(orientation="landscape", unit="mm", format="A4")
        self.titulo_pie = titulo_pie
        self.add_font("OpenSans", "", str(RECURSOS / "fuentes" / "OpenSans-Regular.ttf"))
        self.add_font("OpenSans", "B", str(RECURSOS / "fuentes" / "OpenSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(12, 12, 12)
        self.alias_nb_pages()

    def footer(self) -> None:
        self.set_y(-11)
        self.set_font("OpenSans", "", 7.5)
        self.set_text_color(*GRIS_TEXTO)
        self.cell(0, 5, self.titulo_pie, align="L")
        self.set_x(self.l_margin)
        self.cell(0, 5, f"Página {self.page_no()} de {{nb}}", align="R")


def generar_pdf(
    registros: list[Registro],
    periodo: Periodo,
    destino: Path,
    puesto: str = "",
    generado_por: str = "",
    ahora: datetime | None = None,
) -> Path:
    """Genera el PDF y devuelve su ruta."""
    ahora = ahora or datetime.now()
    pdf = _Documento(f"Generado con IngresosApp {__version__} · www.ingresosapp.com.ar · "
                     f"{ahora:%d/%m/%Y %H:%M}")
    pdf.add_page()

    # Encabezado
    try:
        pdf.image(str(RECURSOS / "icono.png"), x=12, y=11, w=13)
    except (OSError, RuntimeError):
        pass
    pdf.set_xy(28, 11)
    pdf.set_font("OpenSans", "B", 15)
    pdf.set_text_color(*NOCHE)
    pdf.cell(150, 7, "Registro de ingresos y salidas")
    pdf.set_xy(28, 18)
    pdf.set_font("OpenSans", "", 9.5)
    pdf.set_text_color(*GRIS_TEXTO)
    pdf.cell(150, 5, puesto or "Puesto de control")

    validos = [r for r in registros if not r.anulado]
    anulados = len(registros) - len(validos)
    resumen = f"{len(validos)} registro{'s' if len(validos) != 1 else ''}"
    if anulados:
        resumen += f" ({anulados} anulado{'s' if anulados != 1 else ''})"
    datos = [("Período", periodo.texto()), ("Registros", resumen),
             ("Generado", f"{ahora:%d/%m/%Y %H:%M}" + (f" por {generado_por}" if generado_por else ""))]
    y = 11
    for etiqueta, valor in datos:
        pdf.set_xy(195, y)
        pdf.set_font("OpenSans", "", 8)
        pdf.set_text_color(*GRIS_TEXTO)
        pdf.cell(20, 5, etiqueta)
        pdf.set_font("OpenSans", "B", 8)
        pdf.set_text_color(*NOCHE)
        pdf.cell(70, 5, valor, align="L")
        y += 5
    pdf.set_draw_color(*NOCHE)
    pdf.set_line_width(0.6)
    pdf.line(12, 28, 285, 28)
    pdf.set_y(32)

    # Tabla
    con_fecha = not periodo.un_dia
    columnas = ["Nº"] + (["Fecha"] if con_fecha else []) + [
        "Ingreso", "Salida", "Dominio", "Empresa", "Particular", "Destino", "Autorizó", "Guardia", "Observaciones",
    ]
    anchos = [9] + ([14] if con_fecha else []) + [14, 13, 20, 32, 32, 25, 30, 24]
    anchos.append(273 - sum(anchos))  # observaciones ocupa el resto

    pdf.set_font("OpenSans", "", 7.5)
    pdf.set_text_color(*NOCHE)
    pdf.set_draw_color(154, 164, 178)
    pdf.set_line_width(0.2)
    encabezado = FontFace(emphasis="B", color=(255, 255, 255), fill_color=AZUL)
    anulado = FontFace(color=GRIS_ANULADO, emphasis="S")
    nota_anulado = FontFace(color=GRIS_ANULADO)

    with pdf.table(
        col_widths=anchos, width=273, line_height=4.6, headings_style=encabezado,
        cell_fill_color=GRIS_FILA, cell_fill_mode="ROWS", text_align="LEFT", padding=1.4,
        repeat_headings=1,
    ) as tabla:
        fila = tabla.row()
        for titulo in columnas:
            fila.cell(titulo)
        if not registros:
            fila = tabla.row()
            fila.cell("No hay registros en este período.", colspan=len(columnas))
        for r in registros:
            valores = [str(r.id)] + ([f"{r.ingreso[8:10]}/{r.ingreso[5:7]}"] if con_fecha else []) + [
                r.ingreso[11:16],
                (r.salida or "")[11:16] or "—",
                formatear_dominio(r.dominio) or "A pie",
                r.empresa or "—",
                r.particular,
                r.destino,
                r.autorizo or "",
                r.guardia_ingreso or ("Versión 1.0" if r.origen == "v1" else ""),
            ]
            fila = tabla.row()
            for valor in valores:
                fila.cell(valor, style=anulado if r.anulado else None)
            if r.anulado:
                quien = f" por {r.anulado_por}" if r.anulado_por else ""
                fila.cell(f"ANULADO{quien}: {r.anulado_motivo}", style=nota_anulado)
            else:
                fila.cell(r.observaciones)

    # Firma, debajo de la tabla (o arriba de una hoja nueva si no entra)
    if pdf.get_y() + 26 > pdf.h - 16:
        pdf.add_page()
        pdf.set_y(40)
    else:
        pdf.set_y(pdf.get_y() + 20)
    pdf.set_draw_color(*NOCHE)
    pdf.set_line_width(0.3)
    x = 148.5 - 40
    pdf.line(x, pdf.get_y(), x + 80, pdf.get_y())
    pdf.set_xy(x, pdf.get_y() + 1)
    pdf.set_font("OpenSans", "", 8)
    pdf.set_text_color(*NOCHE)
    pdf.cell(80, 5, "Firma y aclaración del encargado", align="C")

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(destino))
    return destino
