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
    base.guardar_ajuste("tipo_predio", "barrio")
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


def test_perfil_barrio_y_autorizo(ventana):
    assert ventana.campo_empresa.titulo.cget("text") == "Empresa o motivo"
    ventana.entrada_autorizo.insert(0, "Pérez, Lote 34")
    cargar(ventana, destino="Lote 34")
    assert ventana.base.obtener(1).autorizo == "Pérez, Lote 34"
    ventana.pestanas.select(1)
    assert ventana.tabla_dia.set("1", "autorizo") == "Pérez, Lote 34"


def test_agenda_y_ficha_en_el_formulario(ventana, monkeypatch):
    from tkinter import messagebox

    c = ventana.base.guardar_contacto(nombre="Lote 34", contacto="Familia Pérez", telefonos="11 5555-1234")
    ventana.actualizar_todo()
    assert ventana.tabla_agenda.get_children() == (str(c.id),)
    assert ventana.pestanas.tab(3, "text") == "Agenda (1)"

    ventana.entrada_destino.insert(0, "Lote 34")
    ventana._actualizar_ficha()
    ventana.root.update()
    assert ventana.ficha.winfo_manager() == "pack"
    assert "11 5555-1234" in ventana.ficha_texto.cget("text")

    ventana.pestanas.select(3)
    ventana.root.update()
    assert not ventana.barra_acciones.winfo_manager()  # las acciones de registros no aplican a la agenda
    ventana.tabla_agenda.selection_set(str(c.id))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    ventana.eliminar_contacto()
    assert ventana.tabla_agenda.get_children() == ()
    assert ventana.ficha.winfo_manager() == ""  # la ficha desaparece
    ventana.pestanas.select(0)
    ventana.root.update()
    assert ventana.barra_acciones.winfo_manager() == "pack"
