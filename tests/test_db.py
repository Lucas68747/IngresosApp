import json
import sqlite3
from datetime import date, datetime, timedelta

import pytest

from ingresosapp.db import BaseDeDatos, ErrorDeDatos, abrir
from ingresosapp.patentes import formatear_dominio, normalizar_dominio


class Reloj:
    """Reloj controlable para que los tests no dependan de la hora real."""

    def __init__(self, inicio=datetime(2026, 10, 24, 8, 0, 0)):
        self.ahora = inicio

    def __call__(self):
        return self.ahora

    def avanzar(self, **kwargs):
        self.ahora += timedelta(**kwargs)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def base(tmp_path, reloj):
    with BaseDeDatos(tmp_path / "ingresos.db", reloj=reloj) as b:
        b.iniciar_turno("Lucía Ramírez")
        yield b


def ingreso(base, **cambios):
    datos = dict(
        tipo="vehiculo",
        dominio="ab 123 cd",
        empresa="Transportes del Sur S.R.L.",
        particular="Ramiro Sánchez",
        destino="Planta 2",
    )
    datos.update(cambios)
    return base.registrar_ingreso(**datos)


# --- Patentes -----------------------------------------------------------------

@pytest.mark.parametrize(
    "entrada, normal, linda",
    [
        ("ab 123 cd", "AB123CD", "AB 123 CD"),
        ("AB-123-CD", "AB123CD", "AB 123 CD"),
        ("abc123", "ABC123", "ABC 123"),
        ("A123BCD", "A123BCD", "A 123 BCD"),  # moto
        ("ABL 3212 GH", "ABL3212GH", "ABL 3212 GH"),  # formato no estándar: igual se lee bien
        ("", "", ""),
        (None, "", ""),
    ],
)
def test_dominios(entrada, normal, linda):
    assert normalizar_dominio(entrada) == normal
    assert formatear_dominio(entrada) == linda


# --- Ingresos -------------------------------------------------------------------

def test_ingreso_pone_fecha_hora_y_guardia(base):
    r = ingreso(base)
    assert r.ingreso == "2026-10-24 08:00:00"
    assert r.guardia_ingreso == "Lucía Ramírez"
    assert r.dominio == "AB123CD"
    assert r.adentro
    assert [m.accion for m in base.historial(r.id)] == ["ingreso"]


def test_ingreso_limpia_espacios(base):
    r = ingreso(base, particular="  Ramiro   Sánchez ", empresa=" ")
    assert r.particular == "Ramiro Sánchez"
    assert r.empresa == ""


@pytest.mark.parametrize(
    "cambios, mensaje",
    [
        ({"dominio": ""}, "Falta el dominio"),
        ({"particular": "   "}, "Falta el nombre"),
        ({"destino": ""}, "Falta el destino"),
        ({"tipo": "camion"}, "tipo de ingreso"),
        ({"observaciones": "x" * 501}, "hasta 500"),
    ],
)
def test_ingreso_valida(base, cambios, mensaje):
    with pytest.raises(ErrorDeDatos, match=mensaje):
        ingreso(base, **cambios)


def test_a_pie_no_necesita_dominio_y_lo_descarta(base):
    r = ingreso(base, tipo="peaton", dominio="AB123CD")
    assert r.tipo == "peaton"
    assert r.dominio == ""


# --- Salidas --------------------------------------------------------------------

def test_salida(base, reloj):
    r = ingreso(base)
    reloj.avanzar(hours=2, minutes=5)
    base.iniciar_turno("Pablo Acosta")
    r = base.registrar_salida(r.id)
    assert r.salida == "2026-10-24 10:05:00"
    assert r.guardia_salida == "Pablo Acosta"
    assert not r.adentro
    assert base.adentro() == []


def test_no_se_registra_dos_veces_la_salida(base):
    r = ingreso(base)
    base.registrar_salida(r.id)
    with pytest.raises(ErrorDeDatos, match="ya tiene la salida registrada a las 08:00"):
        base.registrar_salida(r.id)


def test_adentro_y_mismo_dominio(base):
    a = ingreso(base)
    ingreso(base, tipo="peaton", particular="Juan Márquez")
    assert [r.id for r in base.adentro_con_dominio("AB-123-CD")] == [a.id]
    assert len(base.adentro()) == 2


# --- Modificar: el error principal de la v1 --------------------------------------

def test_modificar_no_cambia_la_hora_de_ingreso(base, reloj):
    r = ingreso(base)
    reloj.avanzar(hours=3)
    r2 = base.modificar(r.id, particular="Ramiro Sanchez Díaz")
    assert r2.ingreso == r.ingreso == "2026-10-24 08:00:00"
    assert r2.particular == "Ramiro Sanchez Díaz"
    movimiento = base.historial(r.id)[-1]
    assert movimiento.accion == "modificacion"
    assert movimiento.momento == "2026-10-24 11:00:00"
    assert json.loads(movimiento.detalle) == {"particular": ["Ramiro Sánchez", "Ramiro Sanchez Díaz"]}


def test_modificar_sin_cambios_no_anota(base):
    r = ingreso(base)
    base.modificar(r.id, dominio="AB 123 CD")  # mismo dominio, otro formato
    assert [m.accion for m in base.historial(r.id)] == ["ingreso"]


def test_modificar_rechaza_campos_de_fecha(base):
    r = ingreso(base)
    with pytest.raises(ErrorDeDatos, match="No se puede modificar: ingreso"):
        base.modificar(r.id, ingreso="2026-01-01 00:00:00")


def test_modificar_valida(base):
    r = ingreso(base)
    with pytest.raises(ErrorDeDatos, match="Falta el destino"):
        base.modificar(r.id, destino="")


# --- Anular en lugar de borrar ---------------------------------------------------

def test_anular(base):
    r = ingreso(base)
    r = base.anular(r.id, "Cargado dos veces")
    assert r.anulado and r.anulado_motivo == "Cargado dos veces" and r.anulado_por == "Lucía Ramírez"
    assert base.adentro() == []
    assert len(base.del_dia(date(2026, 10, 24))) == 1  # sigue en el reporte
    with pytest.raises(ErrorDeDatos, match="anulado"):
        base.modificar(r.id, destino="Oficina")
    with pytest.raises(ErrorDeDatos, match="anulado"):
        base.registrar_salida(r.id)


def test_anular_pide_motivo(base):
    r = ingreso(base)
    with pytest.raises(ErrorDeDatos, match="motivo"):
        base.anular(r.id, "  ")


def test_los_registros_y_el_historial_no_se_borran(base):
    r = ingreso(base)
    with pytest.raises(sqlite3.DatabaseError, match="no se borran"):
        base.conn.execute("DELETE FROM registros WHERE id = ?", (r.id,))
    with pytest.raises(sqlite3.DatabaseError, match="no se puede modificar"):
        base.conn.execute("UPDATE historial SET guardia = 'otra'")


def test_registro_inexistente(base):
    with pytest.raises(ErrorDeDatos, match="No existe el registro Nº 99"):
        base.obtener(99)


# --- Consultas -------------------------------------------------------------------

def test_reportes_por_fecha(base, reloj):
    ingreso(base)
    reloj.avanzar(days=1)
    ingreso(base, dominio="AC908LT")
    reloj.avanzar(days=1)
    ingreso(base, dominio="AD417KM")
    assert len(base.del_dia(date(2026, 10, 25))) == 1
    assert len(base.entre_fechas(date(2026, 10, 24), date(2026, 10, 25))) == 2


def test_buscar(base):
    ingreso(base)
    ingreso(base, dominio="AC 908 LT", empresa="Molinos del Plata S.A.", particular="Carla Benítez")
    assert [r.dominio for r in base.buscar("ab-123")] == ["AB123CD"]
    assert [r.particular for r in base.buscar("molinos")] == ["Carla Benítez"]
    assert base.buscar("100%") == []  # los comodines se buscan como texto


def test_sugerencias_mas_usadas_primero(base):
    ingreso(base, empresa="Molinos del Plata S.A.")
    ingreso(base, empresa="Transportes del Sur S.R.L.")
    ingreso(base, empresa="Transportes del Sur S.R.L.")
    assert base.sugerencias("empresa") == ["Transportes del Sur S.R.L.", "Molinos del Plata S.A."]
    assert base.sugerencias("empresa", "mol") == ["Molinos del Plata S.A."]
    with pytest.raises(ErrorDeDatos):
        base.sugerencias("dominio")


# --- Turnos y ajustes ---------------------------------------------------------------

def test_turnos(base, reloj):
    assert base.turno_actual().guardia == "Lucía Ramírez"
    reloj.avanzar(hours=8)
    base.iniciar_turno("  Pablo   Acosta ")
    assert base.turno_actual().guardia == "Pablo Acosta"
    assert base.guardias() == ["Lucía Ramírez", "Pablo Acosta"]
    abiertos = base.conn.execute("SELECT COUNT(*) FROM turnos WHERE fin IS NULL").fetchone()[0]
    assert abiertos == 1
    with pytest.raises(ErrorDeDatos):
        base.iniciar_turno(" ")


def test_ajustes(base):
    assert base.ajuste("correo_destino") is None
    base.guardar_ajuste("correo_destino", "encargado@ejemplo.com")
    base.guardar_ajuste("correo_destino", "otro@ejemplo.com")
    assert base.ajuste("correo_destino") == "otro@ejemplo.com"


# --- Migración desde la versión 1.0 ------------------------------------------------------

def crear_base_v1(ruta, filas):
    """Crea un archivo igual al que generaba IngresosApp 1.0."""
    con = sqlite3.connect(ruta)
    con.execute(
        """CREATE TABLE empleado (
            ID INTEGER PRIMARY KEY AUTOINCREMENT, DATE VARCHAR(50) NOT NULL,
            HOUR VARCHAR(50) NOT NULL, DOMAIN VARCHAR(50) NOT NULL,
            BUSINESS VARCHAR(50) NOT NULL, PARTICULAR VARCHAR(50) NOT NULL,
            DESTINATION VARCHAR(50) NOT NULL)"""
    )
    con.executemany(
        "INSERT INTO empleado (DATE, HOUR, DOMAIN, BUSINESS, PARTICULAR, DESTINATION) VALUES (?,?,?,?,?,?)",
        filas,
    )
    con.commit()
    con.close()


def test_migracion_v1(tmp_path, reloj):
    v1 = tmp_path / "v1" / "base"
    v1.parent.mkdir()
    crear_base_v1(
        v1,
        [
            ("2025-07-03", "17:19:44", "ABL 312", "Don Juan S.A", "Santoro", "Oficina"),
            ("2025-07-03", "17:20:10", "", "Cargas Ruar", "Saenz", "Planta"),
        ],
    )
    contenido_original = v1.read_bytes()

    base, importados = abrir(tmp_path / "nueva.db", [v1], reloj=reloj)
    with base:
        assert importados == 2
        registros = base.del_dia(date(2025, 7, 3))
        assert [(r.ingreso, r.dominio, r.tipo, r.origen) for r in registros] == [
            ("2025-07-03 17:19:44", "ABL312", "vehiculo", "v1"),
            ("2025-07-03 17:20:10", "", "peaton", "v1"),
        ]
        assert base.adentro() == []  # la v1 no registraba salidas
        assert "registro original Nº 1" in base.historial(registros[0].id)[0].detalle
        assert base.importar_base_v1(v1) == 0  # no se importa dos veces

    assert v1.read_bytes() == contenido_original  # el archivo de la v1 queda intacto


def test_migracion_ignora_archivos_sin_tabla(tmp_path, reloj):
    v1 = tmp_path / "base"
    sqlite3.connect(v1).close()
    base, importados = abrir(tmp_path / "nueva.db", [v1], reloj=reloj)
    with base:
        assert importados == 0


def test_no_importa_si_la_base_ya_existia(tmp_path, reloj):
    v1 = tmp_path / "base"
    crear_base_v1(v1, [("2025-07-03", "17:19:44", "ABL 312", "Don Juan S.A", "Santoro", "Oficina")])
    BaseDeDatos(tmp_path / "nueva.db", reloj=reloj).cerrar()
    base, importados = abrir(tmp_path / "nueva.db", [v1], reloj=reloj)
    with base:
        assert importados == 0


def test_base_de_una_version_futura(tmp_path):
    ruta = tmp_path / "futura.db"
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA user_version = 99")
    con.close()
    with pytest.raises(ErrorDeDatos, match="versión más nueva"):
        BaseDeDatos(ruta)


# --- Copias de seguridad ---------------------------------------------------------------

def test_respaldos(base, reloj, tmp_path):
    carpeta = tmp_path / "respaldos"
    ingreso(base)
    primera = base.respaldar(carpeta, conservar=3)
    assert primera.name == "ingresos-2026-10-24.db"
    copia = sqlite3.connect(primera)
    assert copia.execute("SELECT COUNT(*) FROM registros").fetchone()[0] == 1
    copia.close()
    for _ in range(4):
        reloj.avanzar(days=1)
        base.respaldar(carpeta, conservar=3)
    assert [p.name for p in sorted(carpeta.iterdir())] == [
        "ingresos-2026-10-26.db",
        "ingresos-2026-10-27.db",
        "ingresos-2026-10-28.db",
    ]


# --- Agenda, «Autorizó» y migración del esquema 2 al 3 -----------------------------

def test_autorizo_se_guarda_y_se_modifica_con_historial(base):
    r = ingreso(base, autorizo="  Pérez,  Lote 34 ")
    assert r.autorizo == "Pérez, Lote 34"
    r = base.modificar(r.id, autorizo="Pérez por teléfono")
    assert json.loads(base.historial(r.id)[-1].detalle) == {"autorizo": ["Pérez, Lote 34", "Pérez por teléfono"]}


def test_agenda_alta_edicion_y_baja(base):
    c = base.guardar_contacto(nombre=" Lote 34 ", contacto="Familia Pérez", telefonos="11 5555-1234")
    assert (c.nombre, c.telefonos) == ("Lote 34", "11 5555-1234")
    c = base.guardar_contacto(c.id, nombre="Lote 34", contacto="Familia Pérez", telefonos="11 5555-9999")
    assert base.contacto(c.id).telefonos == "11 5555-9999"
    assert len(base.agenda()) == 1
    base.eliminar_contacto(c.id)
    assert base.agenda() == []
    assert base.conn.execute("SELECT COUNT(*) FROM agenda").fetchone()[0] == 0  # se borra de verdad
    with pytest.raises(ErrorDeDatos, match="ya no está en la agenda"):
        base.eliminar_contacto(c.id)


def test_agenda_valida(base):
    with pytest.raises(ErrorDeDatos, match="Falta el nombre"):
        base.guardar_contacto(nombre=" ", telefonos="123")
    with pytest.raises(ErrorDeDatos, match="desconocidos"):
        base.guardar_contacto(nombre="Lote 1", dni="123")


def test_agenda_busca_y_sugiere_para_el_formulario(base):
    base.guardar_contacto(nombre="Lote 34", contacto="Familia Pérez", telefonos="11 5555-1234")
    base.guardar_contacto(nombre="Molinos del Plata S.A.", ubicacion="Planta 2", telefonos="0800 444 1234")
    base.guardar_contacto(nombre="Lote 35", contacto="Familia Gómez")
    assert [c.nombre for c in base.agenda("pérez")] == ["Lote 34"]
    assert [c.nombre for c in base.contactos_para("Lote 34 (casa del fondo)")] == ["Lote 34"]
    assert [c.nombre for c in base.contactos_para("", "molinos")] == ["Molinos del Plata S.A."]
    assert [c.nombre for c in base.contactos_para("planta 2")] == ["Molinos del Plata S.A."]
    assert base.contactos_para("x") == []


def test_la_agenda_no_afecta_a_los_registros(base):
    c = base.guardar_contacto(nombre="Lote 34")
    r = ingreso(base, destino="Lote 34")
    base.eliminar_contacto(c.id)
    assert base.obtener(r.id).destino == "Lote 34"


def test_migracion_del_esquema_2_al_3(tmp_path):
    from ingresosapp.db import ESQUEMA

    ruta = tmp_path / "v2.db"
    con = sqlite3.connect(ruta)
    con.executescript(ESQUEMA)
    con.execute("PRAGMA user_version = 2")
    con.execute(
        "INSERT INTO registros (tipo, dominio, particular, destino, ingreso) "
        "VALUES ('vehiculo', 'AB123CD', 'Ramiro', 'Planta', '2026-10-24 08:00:00')"
    )
    con.commit()
    con.close()
    with BaseDeDatos(ruta) as b:
        assert b.conn.execute("PRAGMA user_version").fetchone()[0] == 3
        assert b.obtener(1).autorizo == ""
        b.guardar_contacto(nombre="Lote 1")
        assert len(b.agenda()) == 1
