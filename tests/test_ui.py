"""Prueba de humo de la interfaz: abre la ventana y usa los flujos principales.

Necesita una pantalla (en Linux sin escritorio: xvfb-run python -m pytest).
Si no hay, se omite.
"""

from datetime import date

import pytest

tk = pytest.importorskip("tkinter")

from ingresosapp.db import BaseDeDatos  # noqa: E402


@pytest.fixture
def ventana(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No hay pantalla disponible")
    from tkinter import messagebox

    from ingresosapp.ui.ventana import VentanaPrincipal

    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    avisos = []
    monkeypatch.setattr(messagebox, "showwarning", lambda titulo, texto, **k: avisos.append(texto))
    base = BaseDeDatos(tmp_path / "ingresos.db")
    base.iniciar_turno("Lucía Ramírez")
    base.guardar_ajuste("recorrido_visto", "1")
    v = VentanaPrincipal(root, base, tmp_path)
    v.avisos = avisos
    root.update()
    yield v
    root.destroy()
    base.cerrar()


def cargar(v, dominio="ab123cd", particular="Ramiro Sánchez", destino="Planta 2"):
    v.entrada_dominio.insert(0, dominio)
    v.entrada_particular.insert(0, particular)
    v.entrada_destino.insert(0, destino)
    v.registrar_ingreso()


def test_registrar_ingreso_y_salida(ventana):
    cargar(ventana)
    assert ventana.tabla_adentro.get_children() == ("1",)
    assert ventana.tabla_adentro.set("1", "dominio") == "AB 123 CD"
    assert ventana.pestanas.tab(0, "text") == "Adentro ahora (1)"
    assert ventana.entrada_dominio.get() == ""  # el formulario quedó limpio
    ventana.tabla_adentro.selection_set("1")
    ventana.registrar_salida()
    assert ventana.tabla_adentro.get_children() == ()
    assert ventana.tabla_dia.set("1", "estado") == "Salió"


def test_datos_incompletos_avisan_sin_guardar(ventana):
    cargar(ventana, particular="")
    assert "Falta el nombre" in ventana.avisos[0]
    assert ventana.base.del_dia(date.today()) == []


def test_a_pie(ventana):
    ventana.var_tipo.set("peaton")
    ventana._cambio_tipo()
    ventana.entrada_particular.insert(0, "Juan Márquez")
    ventana.entrada_destino.insert(0, "Vestuarios")
    ventana.registrar_ingreso()
    assert ventana.tabla_adentro.set("1", "tipo") == "A pie"


def test_buscar_y_recorrido(ventana):
    cargar(ventana)
    ventana.pestanas.select(2)
    ventana.entrada_buscar._sacar_ayuda()
    ventana.entrada_buscar.insert(0, "ab 123")
    ventana.buscar()
    assert ventana.tabla_buscar.get_children() == ("1",)
    ventana.ver_recorrido()
    for _ in range(20):
        if not ventana._recorrido.activo:
            break
        ventana._recorrido.avanzar()
        ventana.root.update()
    assert not ventana._recorrido.activo
    assert ventana.base.ajuste("recorrido_visto") == "1"
