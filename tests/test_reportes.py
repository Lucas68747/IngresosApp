from datetime import date, datetime

import pytest

pypdf = pytest.importorskip("pypdf")

from ingresosapp.db import BaseDeDatos  # noqa: E402
from ingresosapp.reportes import Periodo, generar_pdf, periodo_por_nombre  # noqa: E402


def texto_pdf(ruta):
    return "\n".join(pagina.extract_text() for pagina in pypdf.PdfReader(ruta).pages)


@pytest.fixture
def base(tmp_path):
    reloj = lambda: datetime(2026, 10, 24, 9, 30)  # noqa: E731
    with BaseDeDatos(tmp_path / "ingresos.db", reloj=reloj) as b:
        b.iniciar_turno("Lucía Ramírez")
        yield b


def test_pdf_con_anulado_autorizo_y_sin_agenda(base, tmp_path):
    base.guardar_contacto(nombre="Lote 34", telefonos="11 5555-1234", contacto="Familia Pérez")
    base.registrar_ingreso(dominio="ab123cd", empresa="Delivery", particular="Matías López",
                           destino="Lote 34", autorizo="Pérez por teléfono")
    r = base.registrar_ingreso(dominio="AE112PQ", particular="Ana Sáenz", destino="Planta 1")
    base.anular(r.id, "Cargado dos veces")
    dia = date(2026, 10, 24)
    ruta = generar_pdf(base.del_dia(dia), Periodo(dia, dia), tmp_path / "r.pdf", puesto="Barrio Los Álamos",
                       generado_por="Lucía Ramírez")
    texto = texto_pdf(ruta)
    for esperado in ("Registro de ingresos y salidas", "Barrio Los Álamos", "AB 123 CD", "Matías López",
                     "Pérez por teléfono", "ANULADO", "Cargado dos veces", "Firma y aclaración del encargado",
                     "1 registro (1 anulado)"):
        assert esperado in texto, esperado
    assert "5555-1234" not in texto  # la agenda nunca sale en los reportes


def test_pdf_vacio_y_varias_paginas(base, tmp_path):
    vacio = generar_pdf([], Periodo(date(2026, 10, 25), date(2026, 10, 25)), tmp_path / "v.pdf")
    assert "No hay registros en este período" in texto_pdf(vacio)
    for i in range(60):
        base.registrar_ingreso(dominio=f"AA{100 + i}BB", particular=f"Persona {i}", destino="Oficina",
                               observaciones="Texto largo " * 8)
    ruta = generar_pdf(base.del_dia(date(2026, 10, 24)), Periodo(date(2026, 10, 1), date(2026, 10, 24)),
                       tmp_path / "m.pdf")
    paginas = pypdf.PdfReader(ruta).pages
    assert len(paginas) > 1
    assert "Nº" in paginas[1].extract_text()  # el encabezado de la tabla se repite


@pytest.mark.parametrize(
    "nombre, desde, hasta",
    [
        ("Hoy", date(2026, 1, 15), date(2026, 1, 15)),
        ("Ayer", date(2026, 1, 14), date(2026, 1, 14)),
        ("Últimos 7 días", date(2026, 1, 9), date(2026, 1, 15)),
        ("Este mes", date(2026, 1, 1), date(2026, 1, 15)),
        ("Mes anterior", date(2025, 12, 1), date(2025, 12, 31)),
    ],
)
def test_periodos(nombre, desde, hasta):
    assert periodo_por_nombre(nombre, hoy=date(2026, 1, 15)) == Periodo(desde, hasta)


def test_nombres_de_archivo():
    assert Periodo(date(2026, 10, 24), date(2026, 10, 24)).nombre_archivo() == "ingresos_2026-10-24.pdf"
    assert Periodo(date(2026, 10, 1), date(2026, 10, 24)).nombre_archivo() == "ingresos_2026-10-01_al_2026-10-24.pdf"
