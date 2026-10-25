"""Envío de reportes por correo.

El encargado configura una sola vez la cuenta que envía (por ejemplo una
cuenta de Gmail creada para la garita, con una contraseña de aplicación) y
las direcciones que reciben. La contraseña se guarda en el almacén seguro
del sistema (el Administrador de credenciales de Windows), nunca en la base
de datos ni en un archivo. La agenda nunca se envía.
"""

from __future__ import annotations

import re
import smtplib
import socket
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

from .db import BaseDeDatos

SERVICIO_CREDENCIALES = "IngresosApp"
AYUDA_GMAIL = "https://support.google.com/accounts/answer/185833"
PROVEEDORES = {
    "gmail": ("Gmail", "smtp.gmail.com", 587),
    "otro": ("Otro servidor de correo (SMTP)", "", 587),
}
_CORREO = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


class ErrorDeCorreo(Exception):
    """Error con un mensaje listo para mostrar."""


@dataclass
class ConfigCorreo:
    destinatarios: str = ""
    remitente: str = ""
    proveedor: str = "gmail"
    servidor: str = "smtp.gmail.com"
    puerto: int = 587

    @property
    def completa(self) -> bool:
        return bool(self.destinatarios and self.remitente and self.servidor)

    def lista_destinatarios(self) -> list[str]:
        return separar_direcciones(self.destinatarios)


def separar_direcciones(texto: str) -> list[str]:
    direcciones = [d.strip() for d in re.split(r"[,;\s]+", texto or "") if d.strip()]
    malas = [d for d in direcciones if not _CORREO.match(d)]
    if malas:
        raise ErrorDeCorreo(f"Revisá esta dirección de correo: {malas[0]}")
    return direcciones


def leer_config(base: BaseDeDatos) -> ConfigCorreo:
    proveedor = base.ajuste("correo_proveedor", "gmail") or "gmail"
    _, servidor_defecto, puerto_defecto = PROVEEDORES.get(proveedor, PROVEEDORES["otro"])
    return ConfigCorreo(
        destinatarios=base.ajuste("correo_destinatarios", "") or "",
        remitente=base.ajuste("correo_remitente", "") or "",
        proveedor=proveedor,
        servidor=base.ajuste("correo_servidor", servidor_defecto) or servidor_defecto,
        puerto=int(base.ajuste("correo_puerto", str(puerto_defecto)) or puerto_defecto),
    )


def guardar_config(base: BaseDeDatos, config: ConfigCorreo, contrasena: str | None = None) -> None:
    """Guarda la configuración. Si `contrasena` es None, se conserva la que había."""
    config.lista_destinatarios()
    if config.remitente and not _CORREO.match(config.remitente):
        raise ErrorDeCorreo(f"Revisá el correo que envía: {config.remitente}")
    if not config.servidor:
        raise ErrorDeCorreo("Falta el servidor de correo (SMTP).")
    anterior = base.ajuste("correo_remitente", "") or ""
    if contrasena:
        _guardar_contrasena(config.remitente, contrasena.replace(" ", ""))
        if anterior and anterior != config.remitente:
            _borrar_contrasena(anterior)
    base.guardar_ajuste("correo_destinatarios", ", ".join(config.lista_destinatarios()))
    base.guardar_ajuste("correo_remitente", config.remitente)
    base.guardar_ajuste("correo_proveedor", config.proveedor)
    base.guardar_ajuste("correo_servidor", config.servidor)
    base.guardar_ajuste("correo_puerto", str(config.puerto))


def _keyring():
    try:
        import keyring

        return keyring
    except Exception as e:  # sin la librería o sin almacén seguro disponible
        raise ErrorDeCorreo(
            "Este equipo no tiene un lugar seguro para guardar la contraseña del correo."
        ) from e


def _guardar_contrasena(remitente: str, contrasena: str) -> None:
    try:
        _keyring().set_password(SERVICIO_CREDENCIALES, remitente, contrasena)
    except ErrorDeCorreo:
        raise
    except Exception as e:
        raise ErrorDeCorreo(f"No se pudo guardar la contraseña de forma segura: {e}") from e


def _borrar_contrasena(remitente: str) -> None:
    try:
        _keyring().delete_password(SERVICIO_CREDENCIALES, remitente)
    except Exception:
        pass


def contrasena_guardada(remitente: str) -> str | None:
    if not remitente:
        return None
    try:
        return _keyring().get_password(SERVICIO_CREDENCIALES, remitente)
    except Exception:
        return None


def armar_mensaje(config: ConfigCorreo, asunto: str, cuerpo: str, adjunto: Path | None) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["From"] = config.remitente
    mensaje["To"] = ", ".join(config.lista_destinatarios())
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)
    if adjunto:
        mensaje.add_attachment(Path(adjunto).read_bytes(), maintype="application", subtype="pdf",
                               filename=Path(adjunto).name)
    return mensaje


def enviar(config: ConfigCorreo, contrasena: str, asunto: str, cuerpo: str,
           adjunto: Path | None = None, espera: int = 30) -> None:
    """Envía el correo. Pensado para correr fuera del hilo de la ventana."""
    if not config.completa:
        raise ErrorDeCorreo("Falta configurar el envío por correo (Configuración → Envío por correo).")
    mensaje = armar_mensaje(config, asunto, cuerpo, adjunto)
    contexto = ssl.create_default_context()
    try:
        if config.puerto == 465:
            servidor = smtplib.SMTP_SSL(config.servidor, config.puerto, timeout=espera, context=contexto)
        else:
            servidor = smtplib.SMTP(config.servidor, config.puerto, timeout=espera)
            servidor.starttls(context=contexto)
        with servidor:
            servidor.login(config.remitente, contrasena)
            servidor.send_message(mensaje)
    except smtplib.SMTPAuthenticationError as e:
        raise ErrorDeCorreo(
            "El servidor rechazó el correo o la contraseña. Si es Gmail, hay que usar una "
            "«contraseña de aplicación», no la contraseña habitual de la cuenta."
        ) from e
    except smtplib.SMTPException as e:  # va antes que OSError: SMTPException hereda de OSError
        raise ErrorDeCorreo(f"El servidor de correo respondió con un error: {e}") from e
    except (socket.gaierror, socket.timeout, ConnectionError, OSError) as e:
        raise ErrorDeCorreo(
            f"No se pudo conectar con {config.servidor}. Revisá que el equipo tenga internet. ({e})"
        ) from e


def enlace_mailto(destinatarios: str, asunto: str, cuerpo: str) -> str:
    """Para abrir el programa de correo del equipo cuando no hay envío configurado."""
    return f"mailto:{quote(destinatarios, safe='@,')}?subject={quote(asunto)}&body={quote(cuerpo)}"
