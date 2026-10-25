"""Base de datos de IngresosApp (SQLite).

Reglas que sostiene esta capa, sin importar cómo sea la interfaz:

- La fecha y la hora de ingreso y de salida las pone la app, nunca la
  persona que carga, y modificar un registro no las cambia.
- Los registros no se borran: se anulan con un motivo.
- Cada ingreso, salida, modificación y anulación queda en un historial
  con la hora y la guardia que lo hizo.
- Los datos de la versión 1.0 se importan sin modificar el archivo original.
- La agenda de contactos es distinta: guarda datos personales (nombres y
  teléfonos), así que sus entradas se pueden corregir y eliminar de verdad,
  y nunca salen en los reportes.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

from .patentes import normalizar_dominio

VERSION_ESQUEMA = 3
FORMATO_FECHA_HORA = "%Y-%m-%d %H:%M:%S"
TIPOS = ("vehiculo", "peaton")
CAMPOS_EDITABLES = ("tipo", "dominio", "empresa", "particular", "destino", "autorizo", "observaciones")
CAMPOS_CON_SUGERENCIAS = ("empresa", "particular", "destino")
LARGO_MAXIMO = {
    "dominio": 15, "empresa": 120, "particular": 120, "destino": 120, "autorizo": 120, "observaciones": 500,
}
CAMPOS_AGENDA = ("nombre", "ubicacion", "telefonos", "contacto", "notas")
LARGO_AGENDA = {"nombre": 120, "ubicacion": 120, "telefonos": 120, "contacto": 120, "notas": 500}

# Esquema inicial (versión 2). Los cambios posteriores están en MIGRACIONES,
# así una base creada con una versión anterior se actualiza sola.
ESQUEMA = """
CREATE TABLE registros (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT    NOT NULL DEFAULT 'vehiculo' CHECK (tipo IN ('vehiculo', 'peaton')),
    dominio         TEXT    NOT NULL DEFAULT '',
    empresa         TEXT    NOT NULL DEFAULT '',
    particular      TEXT    NOT NULL,
    destino         TEXT    NOT NULL,
    observaciones   TEXT    NOT NULL DEFAULT '',
    ingreso         TEXT    NOT NULL,
    salida          TEXT,
    guardia_ingreso TEXT    NOT NULL DEFAULT '',
    guardia_salida  TEXT    NOT NULL DEFAULT '',
    anulado         INTEGER NOT NULL DEFAULT 0,
    anulado_motivo  TEXT    NOT NULL DEFAULT '',
    anulado_en      TEXT,
    anulado_por     TEXT    NOT NULL DEFAULT '',
    origen          TEXT    NOT NULL DEFAULT 'app'  -- 'app', o 'v1' si se importó de la versión 1.0
);
CREATE INDEX idx_registros_ingreso ON registros (ingreso);
CREATE INDEX idx_registros_dominio ON registros (dominio);
CREATE INDEX idx_registros_adentro ON registros (salida, anulado);

CREATE TABLE historial (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id INTEGER NOT NULL REFERENCES registros (id),
    momento     TEXT    NOT NULL,
    guardia     TEXT    NOT NULL DEFAULT '',
    accion      TEXT    NOT NULL,  -- ingreso, salida, modificacion, anulacion, importado
    detalle     TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX idx_historial_registro ON historial (registro_id);

CREATE TABLE guardias (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE turnos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    guardia TEXT NOT NULL,
    inicio  TEXT NOT NULL,
    fin     TEXT
);

CREATE TABLE ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

-- Barandas: los registros se anulan, no se borran, y el historial no se toca.
CREATE TRIGGER registros_no_se_borran BEFORE DELETE ON registros
BEGIN
    SELECT RAISE(ABORT, 'Los registros no se borran: se anulan con un motivo.');
END;
CREATE TRIGGER historial_no_se_modifica BEFORE UPDATE ON historial
BEGIN
    SELECT RAISE(ABORT, 'El historial no se puede modificar.');
END;
CREATE TRIGGER historial_no_se_borra BEFORE DELETE ON historial
BEGIN
    SELECT RAISE(ABORT, 'El historial no se puede borrar.');
END;
"""

MIGRACIONES = {
    3: """
    -- Quién autorizó el ingreso (por ejemplo, el vecino que atendió el llamado).
    ALTER TABLE registros ADD COLUMN autorizo TEXT NOT NULL DEFAULT '';

    -- Agenda de la guardia: lotes, casas, empresas o sectores con sus teléfonos.
    CREATE TABLE agenda (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre      TEXT NOT NULL,
        ubicacion   TEXT NOT NULL DEFAULT '',
        telefonos   TEXT NOT NULL DEFAULT '',
        contacto    TEXT NOT NULL DEFAULT '',
        notas       TEXT NOT NULL DEFAULT '',
        actualizado TEXT NOT NULL
    );
    CREATE INDEX idx_agenda_nombre ON agenda (nombre COLLATE NOCASE);
    """,
}


class ErrorDeDatos(ValueError):
    """Error con un mensaje listo para mostrarle a la guardia."""


@dataclass(frozen=True)
class Registro:
    id: int
    tipo: str
    dominio: str
    empresa: str
    particular: str
    destino: str
    observaciones: str
    ingreso: str
    salida: str | None
    guardia_ingreso: str
    guardia_salida: str
    anulado: bool
    anulado_motivo: str
    anulado_en: str | None
    anulado_por: str
    origen: str
    autorizo: str

    @property
    def adentro(self) -> bool:
        return self.salida is None and not self.anulado and self.origen == "app"

    @property
    def momento_ingreso(self) -> datetime | None:
        return _leer_fecha_hora(self.ingreso)

    @property
    def momento_salida(self) -> datetime | None:
        return _leer_fecha_hora(self.salida)


@dataclass(frozen=True)
class Movimiento:
    registro_id: int
    momento: str
    guardia: str
    accion: str
    detalle: str


@dataclass(frozen=True)
class Contacto:
    id: int
    nombre: str
    ubicacion: str
    telefonos: str
    contacto: str
    notas: str
    actualizado: str


@dataclass(frozen=True)
class Turno:
    guardia: str
    inicio: str


def _leer_fecha_hora(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return datetime.strptime(texto, FORMATO_FECHA_HORA)
    except ValueError:
        return None


def _a_registro(fila: sqlite3.Row) -> Registro:
    datos = dict(fila)
    datos["anulado"] = bool(datos["anulado"])
    return Registro(**datos)


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class BaseDeDatos:
    """Acceso a la base de IngresosApp.

    `reloj` permite fijar la hora en los tests; en la app es datetime.now.
    """

    def __init__(self, ruta: Path | str, reloj: Callable[[], datetime] = datetime.now):
        self.ruta = ruta
        self._reloj = reloj
        self.conn = sqlite3.connect(str(ruta))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._preparar_esquema()

    # ------------------------------------------------------------------
    # Apertura y cierre
    # ------------------------------------------------------------------

    def __enter__(self) -> "BaseDeDatos":
        return self

    def __exit__(self, *_: object) -> None:
        self.cerrar()

    def cerrar(self) -> None:
        self.conn.close()

    def _preparar_esquema(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version > VERSION_ESQUEMA:
            raise ErrorDeDatos(
                "Esta base de datos fue creada con una versión más nueva de IngresosApp. "
                "Actualizá la aplicación para abrirla."
            )
        if version == 0:
            self.conn.executescript(ESQUEMA)
            version = 2
            self.conn.execute(f"PRAGMA user_version = {version}")
        for siguiente in range(version + 1, VERSION_ESQUEMA + 1):
            self.conn.executescript(f"BEGIN; {MIGRACIONES[siguiente]} PRAGMA user_version = {siguiente}; COMMIT;")

    def _ahora(self) -> str:
        return self._reloj().strftime(FORMATO_FECHA_HORA)

    # ------------------------------------------------------------------
    # Turnos y guardias
    # ------------------------------------------------------------------

    def iniciar_turno(self, guardia: str) -> Turno:
        guardia = " ".join(guardia.split())
        if not guardia:
            raise ErrorDeDatos("Escribí el nombre de la guardia que empieza el turno.")
        ahora = self._ahora()
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO guardias (nombre) VALUES (?)", (guardia,))
            self.conn.execute("UPDATE turnos SET fin = ? WHERE fin IS NULL", (ahora,))
            self.conn.execute("INSERT INTO turnos (guardia, inicio) VALUES (?, ?)", (guardia, ahora))
        return Turno(guardia, ahora)

    def turno_actual(self) -> Turno | None:
        fila = self.conn.execute(
            "SELECT guardia, inicio FROM turnos WHERE fin IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return Turno(fila["guardia"], fila["inicio"]) if fila else None

    def guardias(self) -> list[str]:
        filas = self.conn.execute(
            "SELECT nombre FROM guardias WHERE activo = 1 ORDER BY nombre COLLATE NOCASE"
        )
        return [f["nombre"] for f in filas]

    def _guardia_de_turno(self) -> str:
        turno = self.turno_actual()
        return turno.guardia if turno else ""

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    @staticmethod
    def _validar(datos: dict[str, str]) -> dict[str, str]:
        limpio = {
            campo: " ".join(str(datos.get(campo, "") or "").split())
            for campo in CAMPOS_EDITABLES
            if campo != "observaciones"
        }
        limpio["observaciones"] = str(datos.get("observaciones", "") or "").strip()
        limpio["dominio"] = normalizar_dominio(limpio["dominio"])

        if limpio["tipo"] not in TIPOS:
            raise ErrorDeDatos("El tipo de ingreso tiene que ser «Vehículo» o «A pie».")
        if limpio["tipo"] == "peaton":
            limpio["dominio"] = ""
        elif not limpio["dominio"]:
            raise ErrorDeDatos(
                "Falta el dominio del vehículo. Si la persona viene caminando, elegí «A pie»."
            )
        if not limpio["particular"]:
            raise ErrorDeDatos("Falta el nombre y apellido de la persona (campo Particular).")
        if not limpio["destino"]:
            raise ErrorDeDatos("Falta el destino dentro del predio.")
        for campo, maximo in LARGO_MAXIMO.items():
            if len(limpio[campo]) > maximo:
                raise ErrorDeDatos(f"El campo {campo} admite hasta {maximo} caracteres.")
        return limpio

    # ------------------------------------------------------------------
    # Operaciones
    # ------------------------------------------------------------------

    def registrar_ingreso(
        self,
        *,
        tipo: str = "vehiculo",
        dominio: str = "",
        empresa: str = "",
        particular: str,
        destino: str,
        autorizo: str = "",
        observaciones: str = "",
    ) -> Registro:
        datos = self._validar(locals())
        ahora = self._ahora()
        guardia = self._guardia_de_turno()
        with self.conn:
            cursor = self.conn.execute(
                """INSERT INTO registros
                   (tipo, dominio, empresa, particular, destino, autorizo, observaciones, ingreso, guardia_ingreso)
                   VALUES (:tipo, :dominio, :empresa, :particular, :destino, :autorizo, :observaciones,
                           :ingreso, :guardia)""",
                {**datos, "ingreso": ahora, "guardia": guardia},
            )
            registro_id = cursor.lastrowid
            self._anotar(registro_id, "ingreso", "", ahora, guardia)
        return self.obtener(registro_id)

    def registrar_salida(self, registro_id: int) -> Registro:
        registro = self.obtener(registro_id)
        if registro.anulado:
            raise ErrorDeDatos(f"El registro Nº {registro_id} está anulado.")
        if registro.salida:
            hora = registro.salida[11:16]
            raise ErrorDeDatos(f"El registro Nº {registro_id} ya tiene la salida registrada a las {hora}.")
        ahora = self._ahora()
        guardia = self._guardia_de_turno()
        with self.conn:
            self.conn.execute(
                "UPDATE registros SET salida = ?, guardia_salida = ? WHERE id = ?",
                (ahora, guardia, registro_id),
            )
            self._anotar(registro_id, "salida", "", ahora, guardia)
        return self.obtener(registro_id)

    def modificar(self, registro_id: int, **cambios: str) -> Registro:
        """Corrige datos de un registro. La fecha y la hora no se tocan."""
        desconocidos = set(cambios) - set(CAMPOS_EDITABLES)
        if desconocidos:
            raise ErrorDeDatos(f"No se puede modificar: {', '.join(sorted(desconocidos))}.")
        registro = self.obtener(registro_id)
        if registro.anulado:
            raise ErrorDeDatos(f"El registro Nº {registro_id} está anulado y no se puede modificar.")

        actuales = {campo: getattr(registro, campo) for campo in CAMPOS_EDITABLES}
        nuevos = self._validar({**actuales, **cambios})
        diferencias = {
            campo: [actuales[campo], nuevos[campo]]
            for campo in CAMPOS_EDITABLES
            if actuales[campo] != nuevos[campo]
        }
        if not diferencias:
            return registro

        ahora = self._ahora()
        guardia = self._guardia_de_turno()
        asignaciones = ", ".join(f"{campo} = :{campo}" for campo in diferencias)
        with self.conn:
            self.conn.execute(
                f"UPDATE registros SET {asignaciones} WHERE id = :id",
                {**{c: nuevos[c] for c in diferencias}, "id": registro_id},
            )
            self._anotar(
                registro_id, "modificacion", json.dumps(diferencias, ensure_ascii=False), ahora, guardia
            )
        return self.obtener(registro_id)

    def anular(self, registro_id: int, motivo: str) -> Registro:
        motivo = " ".join(motivo.split())
        if len(motivo) < 5:
            raise ErrorDeDatos("Escribí el motivo de la anulación (por ejemplo: «cargado dos veces»).")
        registro = self.obtener(registro_id)
        if registro.anulado:
            raise ErrorDeDatos(f"El registro Nº {registro_id} ya estaba anulado.")
        ahora = self._ahora()
        guardia = self._guardia_de_turno()
        with self.conn:
            self.conn.execute(
                """UPDATE registros
                   SET anulado = 1, anulado_motivo = ?, anulado_en = ?, anulado_por = ?
                   WHERE id = ?""",
                (motivo, ahora, guardia, registro_id),
            )
            self._anotar(registro_id, "anulacion", motivo, ahora, guardia)
        return self.obtener(registro_id)

    def _anotar(self, registro_id: int, accion: str, detalle: str, momento: str, guardia: str) -> None:
        self.conn.execute(
            "INSERT INTO historial (registro_id, momento, guardia, accion, detalle) VALUES (?, ?, ?, ?, ?)",
            (registro_id, momento, guardia, accion, detalle),
        )

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def obtener(self, registro_id: int) -> Registro:
        fila = self.conn.execute("SELECT * FROM registros WHERE id = ?", (registro_id,)).fetchone()
        if fila is None:
            raise ErrorDeDatos(f"No existe el registro Nº {registro_id}.")
        return _a_registro(fila)

    def adentro(self) -> list[Registro]:
        """Quienes entraron y todavía no tienen la salida registrada."""
        filas = self.conn.execute(
            """SELECT * FROM registros
               WHERE salida IS NULL AND anulado = 0 AND origen = 'app'
               ORDER BY ingreso"""
        )
        return [_a_registro(f) for f in filas]

    def adentro_con_dominio(self, dominio: str) -> list[Registro]:
        dominio = normalizar_dominio(dominio)
        if not dominio:
            return []
        return [r for r in self.adentro() if r.dominio == dominio]

    def entre_fechas(self, desde: date, hasta: date) -> list[Registro]:
        """Registros que ingresaron entre dos fechas, ambas incluidas. Incluye anulados."""
        filas = self.conn.execute(
            "SELECT * FROM registros WHERE ingreso >= ? AND ingreso < ? ORDER BY ingreso, id",
            (desde.isoformat(), (hasta + timedelta(days=1)).isoformat()),
        )
        return [_a_registro(f) for f in filas]

    def del_dia(self, dia: date) -> list[Registro]:
        return self.entre_fechas(dia, dia)

    def buscar(
        self,
        texto: str = "",
        desde: date | None = None,
        hasta: date | None = None,
        limite: int = 500,
    ) -> list[Registro]:
        condiciones: list[str] = []
        parametros: list[object] = []
        texto = " ".join(texto.split())
        if texto:
            patron = f"%{_escapar_like(texto)}%"
            patron_dominio = f"%{_escapar_like(normalizar_dominio(texto))}%"
            condiciones.append(
                "(dominio LIKE ? ESCAPE '\\' OR empresa LIKE ? ESCAPE '\\' "
                "OR particular LIKE ? ESCAPE '\\' OR destino LIKE ? ESCAPE '\\' "
                "OR observaciones LIKE ? ESCAPE '\\')"
            )
            parametros += [patron_dominio, patron, patron, patron, patron]
        if desde:
            condiciones.append("ingreso >= ?")
            parametros.append(desde.isoformat())
        if hasta:
            condiciones.append("ingreso < ?")
            parametros.append((hasta + timedelta(days=1)).isoformat())
        donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        filas = self.conn.execute(
            f"SELECT * FROM registros {donde} ORDER BY ingreso DESC, id DESC LIMIT ?",
            (*parametros, limite),
        )
        return [_a_registro(f) for f in filas]

    def sugerencias(self, campo: str, prefijo: str = "", limite: int = 10) -> list[str]:
        """Valores ya cargados para autocompletar, los más usados primero."""
        if campo not in CAMPOS_CON_SUGERENCIAS:
            raise ErrorDeDatos(f"No hay sugerencias para el campo {campo}.")
        filas = self.conn.execute(
            f"""SELECT {campo} AS valor, COUNT(*) AS veces FROM registros
                WHERE anulado = 0 AND {campo} <> '' AND {campo} LIKE ? ESCAPE '\\'
                GROUP BY {campo} COLLATE NOCASE
                ORDER BY veces DESC, valor COLLATE NOCASE
                LIMIT ?""",
            (f"{_escapar_like(prefijo.strip())}%", limite),
        )
        return [f["valor"] for f in filas]

    def historial(self, registro_id: int) -> list[Movimiento]:
        filas = self.conn.execute(
            """SELECT registro_id, momento, guardia, accion, detalle FROM historial
               WHERE registro_id = ? ORDER BY id""",
            (registro_id,),
        )
        return [Movimiento(**dict(f)) for f in filas]

    # ------------------------------------------------------------------
    # Agenda
    # ------------------------------------------------------------------

    def agenda(self, texto: str = "") -> list[Contacto]:
        texto = " ".join(texto.split())
        if texto:
            patron = f"%{_escapar_like(texto)}%"
            filas = self.conn.execute(
                """SELECT * FROM agenda
                   WHERE nombre LIKE ? ESCAPE '\\' OR ubicacion LIKE ? ESCAPE '\\'
                      OR contacto LIKE ? ESCAPE '\\' OR telefonos LIKE ? ESCAPE '\\'
                      OR notas LIKE ? ESCAPE '\\'
                   ORDER BY nombre COLLATE NOCASE""",
                (patron,) * 5,
            )
        else:
            filas = self.conn.execute("SELECT * FROM agenda ORDER BY nombre COLLATE NOCASE")
        return [Contacto(**dict(f)) for f in filas]

    def contacto(self, contacto_id: int) -> Contacto:
        fila = self.conn.execute("SELECT * FROM agenda WHERE id = ?", (contacto_id,)).fetchone()
        if fila is None:
            raise ErrorDeDatos("Ese contacto ya no está en la agenda.")
        return Contacto(**dict(fila))

    def guardar_contacto(self, contacto_id: int | None = None, **datos: str) -> Contacto:
        """Crea un contacto (sin id) o reemplaza los datos de uno existente."""
        desconocidos = set(datos) - set(CAMPOS_AGENDA)
        if desconocidos:
            raise ErrorDeDatos(f"Campos desconocidos en la agenda: {', '.join(sorted(desconocidos))}.")
        limpio = {campo: " ".join(str(datos.get(campo, "") or "").split()) for campo in CAMPOS_AGENDA}
        limpio["notas"] = str(datos.get("notas", "") or "").strip()
        if not limpio["nombre"]:
            raise ErrorDeDatos("Falta el nombre: el lote, la casa, la empresa o el sector.")
        for campo, maximo in LARGO_AGENDA.items():
            if len(limpio[campo]) > maximo:
                raise ErrorDeDatos(f"El campo {campo} admite hasta {maximo} caracteres.")
        limpio["actualizado"] = self._ahora()
        with self.conn:
            if contacto_id is None:
                cursor = self.conn.execute(
                    """INSERT INTO agenda (nombre, ubicacion, telefonos, contacto, notas, actualizado)
                       VALUES (:nombre, :ubicacion, :telefonos, :contacto, :notas, :actualizado)""",
                    limpio,
                )
                contacto_id = cursor.lastrowid
            else:
                self.contacto(contacto_id)
                self.conn.execute(
                    """UPDATE agenda SET nombre = :nombre, ubicacion = :ubicacion, telefonos = :telefonos,
                       contacto = :contacto, notas = :notas, actualizado = :actualizado WHERE id = :id""",
                    {**limpio, "id": contacto_id},
                )
        return self.contacto(contacto_id)

    def eliminar_contacto(self, contacto_id: int) -> None:
        """Borra el contacto de la base. Los registros de ingreso no se tocan."""
        self.contacto(contacto_id)
        with self.conn:
            self.conn.execute("DELETE FROM agenda WHERE id = ?", (contacto_id,))

    def contactos_para(self, *textos: str, limite: int = 3) -> list[Contacto]:
        """Contactos que coinciden con lo escrito en Destino o Empresa, para mostrar el teléfono."""
        encontrados: dict[int, Contacto] = {}
        for texto in textos:
            texto = " ".join((texto or "").split())
            if len(texto) < 2:
                continue
            patron = f"%{_escapar_like(texto)}%"
            filas = self.conn.execute(
                """SELECT * FROM agenda
                   WHERE nombre LIKE ? ESCAPE '\\' OR ? LIKE '%' || nombre || '%' OR ubicacion LIKE ? ESCAPE '\\'
                   ORDER BY (nombre = ? COLLATE NOCASE) DESC, nombre COLLATE NOCASE LIMIT ?""",
                (patron, texto, patron, texto, limite),
            )
            for fila in filas:
                encontrados.setdefault(fila["id"], Contacto(**dict(fila)))
        return list(encontrados.values())[:limite]

    # ------------------------------------------------------------------
    # Ajustes
    # ------------------------------------------------------------------

    def ajuste(self, clave: str, por_defecto: str | None = None) -> str | None:
        fila = self.conn.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
        return fila["valor"] if fila else por_defecto

    def guardar_ajuste(self, clave: str, valor: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
                "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
                (clave, valor),
            )

    # ------------------------------------------------------------------
    # Versión 1.0
    # ------------------------------------------------------------------

    def importar_base_v1(self, archivo: Path) -> int:
        """Copia los registros de una base de la versión 1.0.

        El archivo original se abre solo para lectura y no se modifica. Si
        ya se importó, no se vuelve a importar. Devuelve cuántos registros
        se copiaron.
        """
        archivo = Path(archivo).resolve()
        importados = json.loads(self.ajuste("importado_v1", "[]") or "[]")
        if str(archivo) in importados:
            return 0

        origen = sqlite3.connect(f"{archivo.as_uri()}?mode=ro", uri=True)
        try:
            tiene_tabla = origen.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'empleado'"
            ).fetchone()
            filas = (
                origen.execute(
                    "SELECT ID, DATE, HOUR, DOMAIN, BUSINESS, PARTICULAR, DESTINATION "
                    "FROM empleado ORDER BY ID"
                ).fetchall()
                if tiene_tabla
                else []
            )
        finally:
            origen.close()

        ahora = self._ahora()
        with self.conn:
            for id_v1, fecha, hora, dominio, empresa, particular, destino in filas:
                ingreso = f"{(fecha or '').strip()} {(hora or '').strip()}".strip()
                dominio = normalizar_dominio(dominio)
                cursor = self.conn.execute(
                    """INSERT INTO registros
                       (tipo, dominio, empresa, particular, destino, ingreso, origen)
                       VALUES (?, ?, ?, ?, ?, ?, 'v1')""",
                    (
                        "vehiculo" if dominio else "peaton",
                        dominio,
                        (empresa or "").strip(),
                        (particular or "").strip() or "(sin dato)",
                        (destino or "").strip() or "(sin dato)",
                        ingreso or "(sin fecha)",
                    ),
                )
                self._anotar(
                    cursor.lastrowid,
                    "importado",
                    f"Importado de IngresosApp 1.0 (registro original Nº {id_v1})",
                    ahora,
                    "",
                )
            importados.append(str(archivo))
            self.conn.execute(
                "INSERT INTO ajustes (clave, valor) VALUES ('importado_v1', ?) "
                "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
                (json.dumps(importados, ensure_ascii=False),),
            )
        return len(filas)

    # ------------------------------------------------------------------
    # Copias de seguridad
    # ------------------------------------------------------------------

    def respaldar(self, carpeta: Path, conservar: int = 30) -> Path:
        """Hace la copia de seguridad del día, si todavía no existe.

        Conserva las últimas `conservar` copias y borra las más viejas.
        """
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"ingresos-{self._reloj():%Y-%m-%d}.db"
        if not destino.exists():
            copia = sqlite3.connect(str(destino))
            try:
                self.conn.backup(copia)
            finally:
                copia.close()
        copias = sorted(carpeta.glob("ingresos-????-??-??.db"))
        for vieja in copias[:-conservar] if conservar > 0 else []:
            vieja.unlink()
        return destino


def abrir(ruta: Path, candidatas_v1: Iterable[Path] = (), reloj: Callable[[], datetime] = datetime.now) -> tuple[BaseDeDatos, int]:
    """Abre (o crea) la base y, si es nueva, importa la de la versión 1.0.

    Devuelve la base y la cantidad de registros importados.
    """
    era_nueva = not Path(ruta).exists()
    base = BaseDeDatos(ruta, reloj=reloj)
    importados = 0
    if era_nueva:
        for candidata in candidatas_v1:
            importados += base.importar_base_v1(candidata)
    return base, importados
