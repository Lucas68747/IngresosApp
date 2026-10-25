import smtplib
import sys
import types

import pytest

from ingresosapp import correo
from ingresosapp.db import BaseDeDatos


@pytest.fixture
def almacen(monkeypatch):
    """Reemplaza el almacén seguro del sistema por uno en memoria."""
    guardadas = {}
    falso = types.SimpleNamespace(
        set_password=lambda s, u, p: guardadas.__setitem__((s, u), p),
        get_password=lambda s, u: guardadas.get((s, u)),
        delete_password=lambda s, u: guardadas.pop((s, u), None),
    )
    monkeypatch.setitem(sys.modules, "keyring", falso)
    return guardadas


@pytest.fixture
def base(tmp_path):
    with BaseDeDatos(tmp_path / "ingresos.db") as b:
        yield b


class ServidorFalso:
    enviados = []
    rechazar = False

    def __init__(self, servidor, puerto, timeout=None, context=None):
        self.servidor, self.puerto = servidor, puerto

    def starttls(self, context=None):
        pass

    def login(self, usuario, clave):
        if ServidorFalso.rechazar:
            raise smtplib.SMTPAuthenticationError(535, b"Bad credentials")
        self.usuario, self.clave = usuario, clave

    def send_message(self, mensaje):
        ServidorFalso.enviados.append((self.servidor, self.usuario, self.clave, mensaje))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_direcciones():
    assert correo.separar_direcciones("a@b.com, c@d.com.ar; e@f.org") == ["a@b.com", "c@d.com.ar", "e@f.org"]
    with pytest.raises(correo.ErrorDeCorreo, match="no-es-un-correo"):
        correo.separar_direcciones("a@b.com, no-es-un-correo")


def test_la_contrasena_no_va_a_la_base(base, almacen):
    config = correo.ConfigCorreo(destinatarios="encargado@ejemplo.com", remitente="garita@gmail.com")
    correo.guardar_config(base, config, "abcd efgh ijkl mnop")
    assert almacen[("IngresosApp", "garita@gmail.com")] == "abcdefghijklmnop"
    filas = base.conn.execute("SELECT valor FROM ajustes").fetchall()
    assert not any("abcd" in f[0] for f in filas)
    assert correo.leer_config(base).destinatarios == "encargado@ejemplo.com"


def test_enviar_con_adjunto(monkeypatch, tmp_path):
    monkeypatch.setattr(smtplib, "SMTP", ServidorFalso)
    ServidorFalso.enviados.clear()
    pdf = tmp_path / "ingresos_2026-10-24.pdf"
    pdf.write_bytes(b"%PDF-1.4 prueba")
    config = correo.ConfigCorreo(destinatarios="a@b.com, c@d.com", remitente="garita@gmail.com")
    correo.enviar(config, "clave", "Asunto", "Cuerpo", pdf)
    servidor, usuario, clave, mensaje = ServidorFalso.enviados[0]
    assert (servidor, usuario, clave) == ("smtp.gmail.com", "garita@gmail.com", "clave")
    assert mensaje["To"] == "a@b.com, c@d.com"
    adjuntos = [p.get_filename() for p in mensaje.iter_attachments()]
    assert adjuntos == ["ingresos_2026-10-24.pdf"]


def test_error_de_contrasena_explica_la_contrasena_de_aplicacion(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", ServidorFalso)
    monkeypatch.setattr(ServidorFalso, "rechazar", True)
    config = correo.ConfigCorreo(destinatarios="a@b.com", remitente="garita@gmail.com")
    with pytest.raises(correo.ErrorDeCorreo, match="contraseña de aplicación"):
        correo.enviar(config, "mala", "A", "B")


def test_sin_configurar():
    with pytest.raises(correo.ErrorDeCorreo, match="Falta configurar"):
        correo.enviar(correo.ConfigCorreo(), "x", "A", "B")


def test_mailto():
    enlace = correo.enlace_mailto("a@b.com", "Reporte 24/10/2026", "Hola, adjunto el PDF.")
    assert enlace.startswith("mailto:a@b.com?subject=Reporte%2024/10/2026")
