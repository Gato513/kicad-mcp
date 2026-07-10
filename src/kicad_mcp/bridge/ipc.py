"""Puente IPC con KiCad vía ``kicad-python`` (``kipy``).

Responsabilidades del bridge (arquitectura §10, restricciones-kicad.md):
- Establecer conexión al socket IPC (``KICAD_API_SOCKET`` o el default de
  la librería), reportar versión, y proveer acceso al ``Board`` abierto.
- **Timeout duro de 2 s** por request (impuesto por ``kipy``).
- **Cola de profundidad 1**: un ``threading.Lock`` alrededor de toda
  llamada IPC. KiCad procesa cada request en el hilo de UI; enviarle
  concurrencia lo bloquea.
- **Detección de reinicio**: ``KICAD_API_TOKEN`` cambia por instancia.
  Si cambia entre dos llamadas, la operación en curso falla con
  ``KICAD_RESTARTED``.
- **Unidades**: ``Nm`` (nanómetros del IPC) y ``Mm`` (milímetros de todo
  el resto del sistema) son ``NewType`` distintos. Los conversores están
  aquí; ninguna otra capa ve nanómetros jamás.

No expone envelopes ni tipos de ``kipy`` fuera del bridge: quien llama
recibe primitivos o dataclasses de este módulo. Frontera de proceso →
validación en el borde (regla #5).
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NewType, Protocol, TypeVar

from ..errors import ErrorCode, KicadMcpError
from ..logging_config import log_ipc_retry

_T = TypeVar("_T")

# --- Unidades del dominio -----------------------------------------------------

Nm = NewType("Nm", int)
"""Nanómetros — la unidad interna del IPC de KiCad."""

Mm = NewType("Mm", float)
"""Milímetros — la unidad que el resto del sistema (TOON, tools, agente) usa."""


def nm_to_mm(value: Nm) -> Mm:
    """Convierte nanómetros → milímetros. Único punto de conversión."""
    return Mm(value / 1_000_000)


def mm_to_nm(value: Mm) -> Nm:
    """Convierte milímetros → nanómetros. Redondeo half-even (banker)."""
    return Nm(round(value * 1_000_000))


# --- Dataclasses de retorno (nunca expone tipos de kipy) ----------------------


@dataclass(frozen=True)
class IpcVersion:
    """Versión reportada por KiCad. Formato normalizado."""

    full: str
    major: int
    minor: int
    patch: int


@dataclass(frozen=True)
class BoardHandle:
    """Handle opaco a un board abierto. Detalles internos privados al bridge."""

    _raw: Any  # ``kipy.board.Board`` — no se filtra fuera del bridge

    @property
    def raw(self) -> Any:
        """Escape controlado: acceso al ``Board`` de ``kipy`` para operaciones IPC.

        Uso restringido al mismo módulo ``bridge`` (regla implícita: los
        tipos de ``kipy`` no viajan a ``tools/`` ni al agente).
        """
        return self._raw


@dataclass(frozen=True)
class BBoxMm:
    """Bounding box del board en milímetros."""

    min_x: Mm
    min_y: Mm
    max_x: Mm
    max_y: Mm

    def contains(self, x: Mm, y: Mm) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y


@dataclass(frozen=True)
class FootprintPadData:
    """Pad de un footprint expuesto por el bridge para construir estado.

    Datos primitivos: el bridge nunca deja escapar tipos de kipy fuera de
    su borde (regla #5). Sesión 05 T5.
    """

    number: str
    net_name: str | None


@dataclass(frozen=True)
class FootprintData:
    """Footprint del board expuesto por el bridge para construir estado.

    Sesión 05 T5: alimenta al ``state_builder.build_state_from_board`` para
    registrar snapshots vivos tras mutaciones IPC (ADR-0007).
    """

    ref: str
    value: str
    x_mm: Mm
    y_mm: Mm
    pads: tuple[FootprintPadData, ...]


# --- Protocolo del cliente (para inyección en tests) --------------------------


class KiCadClientLike(Protocol):
    """Subset del API de ``kipy.KiCad`` que consume el bridge.

    Permite reemplazar el cliente real por un fake en tests unit sin
    montar ni ``pynng`` ni un socket real.
    """

    def get_version(self) -> Any: ...

    def get_board(self) -> Any: ...

    def get_open_documents(self, doc_type: Any) -> Any: ...


class _ClientFactory(Protocol):
    """Fábrica de clientes IPC — inyectable por tests."""

    def __call__(
        self, socket_path: str | None, timeout_ms: int, kicad_token: str | None
    ) -> KiCadClientLike: ...


def _socket_file_missing(socket_uri: str | None) -> bool:
    """``True`` si ``socket_uri`` es un ``ipc://`` con path filesystem inexistente.

    El check habilita el **fast-fail** (sesión 04): sin este, un ``KiCad(...)``
    con KiCad cerrado espera 2 s de timeout en cada llamada. Para esquemas no
    filesystem (``tcp://``, etc.) devuelve ``False`` — que resuelva el factory.
    """
    if not socket_uri or not socket_uri.startswith("ipc://"):
        return False
    fs_path = socket_uri[len("ipc://") :]
    if not fs_path:
        return False
    return not Path(fs_path).exists()


def _default_client_factory(
    socket_path: str | None, timeout_ms: int, kicad_token: str | None
) -> KiCadClientLike:
    """Fábrica real: instancia ``kipy.KiCad``.

    Import perezoso: no se resuelve ``kipy`` hasta que un llamador lo
    necesita (mantiene el server arrancable si el paquete falla al
    importar por razones ambientales).

    **Fast-fail (sesión 04)**: si el socket es un ``ipc://<path>`` y ese
    ``<path>`` no existe, se levanta ``KICAD_NOT_RUNNING`` inmediatamente
    en vez de esperar los 2 s del timeout IPC. Reduce la latencia de
    ``health`` con KiCad cerrado de 2 s a milisegundos.
    """
    if _socket_file_missing(socket_path):
        raise KicadMcpError(
            code=ErrorCode.KICAD_NOT_RUNNING,
            message="No se pudo conectar al socket IPC de KiCad.",
            hint=(
                "Abrí KiCad y habilitá el API server en Preferences → Plugins → Enable API server."
            ),
        )

    from kipy import KiCad
    from kipy.errors import ConnectionError as _KConn

    try:
        return KiCad(
            socket_path=socket_path,
            timeout_ms=timeout_ms,
            kicad_token=kicad_token,
        )
    except _KConn as exc:
        raise KicadMcpError(
            code=ErrorCode.KICAD_NOT_RUNNING,
            message="No se pudo conectar al socket IPC de KiCad.",
            hint=(
                "Abrí KiCad y habilitá el API server en Preferences → Plugins → Enable API server."
            ),
        ) from exc


# --- Clasificación de fallos IPC (supervisión, sesión 04 T3) ------------------

# Constantes ``ApiStatusCode`` del proto de kipy (envelope_pb2.pyi:70-77).
# Se copian como int para preservar el contrato perezoso del bridge (nada de
# kipy importado a nivel de módulo, sesión 04). Son estables por proto y el
# atributo ``ApiError.code`` se compara por igualdad de int (kipy
# ``client.py:89-91`` lo asigna desde ``reply.status.status``).
_AS_UNHANDLED = 5
_AS_BUSY = 7


def _map_ipc_failure(op_name: str, exc: BaseException) -> KicadMcpError:
    """Traduce excepciones que atraviesan una operación IPC a errores del catálogo.

    Regla:
    - ``TimeoutError`` (builtin, socket, kipy) → ``KICAD_TIMEOUT``.
    - ``ConnectionError`` (builtin) o ``kipy.errors.ConnectionError`` →
      ``KICAD_NOT_RUNNING``.
    - ``kipy.errors.ApiError`` con ``code == AS_BUSY`` (7) → ``KICAD_CLI_FAILED``
      con hint fijo accionable y ``data.ipc_status = "busy"`` (D-07.2). Estado
      protocolar de KiCad (envelope_pb2.pyi:74-75): la UI está ocupada
      procesando otro trabajo (refill zones, DRC realtime, router).
    - ``kipy.errors.ApiError`` con ``code == AS_UNHANDLED`` (5) →
      ``KICAD_CLI_FAILED`` con hint apuntando a abrir el editor requerido y
      ``data.ipc_status = "unhandled"`` (D-07.2). Es el error que emite
      KiCad cuando el request no tiene handler para el estado actual (p. ej.
      pedir el board sin PCB Editor abierto — ver ``kipy/kicad.py:225-230``).
    - Cualquier otra excepción (incluyendo ``ApiError`` con code no
      distinguido) → ``KICAD_CLI_FAILED`` con el detalle sanitizado en el
      hint.

    Se identifica ``kipy.errors.ConnectionError`` y ``kipy.errors.ApiError``
    por ``__qualname__`` **más** ``__module__.startswith("kipy")``, para no
    forzar el import de ``kipy`` en un ciclo perezoso y a la vez no confundir
    homónimos definidos por otra librería que corra dentro del bloque
    supervisado (sesión 05 T1).
    """
    if isinstance(exc, TimeoutError):
        return KicadMcpError(
            code=ErrorCode.KICAD_TIMEOUT,
            message=f"IPC excedió el timeout durante {op_name}.",
            hint="Reintentar o reducir el alcance de la operación.",
        )
    exc_type = type(exc)
    exc_module = exc_type.__module__ or ""
    is_from_kipy = exc_module.startswith("kipy")
    is_kipy_conn_error = exc_type.__qualname__ == "ConnectionError" and is_from_kipy
    if isinstance(exc, ConnectionError) or is_kipy_conn_error:
        return KicadMcpError(
            code=ErrorCode.KICAD_NOT_RUNNING,
            message="Conexión IPC con KiCad perdida durante la operación.",
            hint="Abrí KiCad y habilitá el API server; el próximo request reconectará.",
        )
    # ApiError con ``code`` reconocido: F3 intacta, el código sigue siendo
    # ``KICAD_CLI_FAILED``; sólo cambian el hint (accionable, fijo) y el
    # ``data.ipc_status`` (canal estructurado, documentado en el catálogo).
    if is_from_kipy and exc_type.__qualname__ == "ApiError":
        api_code = getattr(exc, "code", None)
        # ``ApiStatusCode`` en el proto es un int-enum; la igualdad por int
        # cubre tanto el enum como cualquier alias plano.
        if isinstance(api_code, int) and not isinstance(api_code, bool):
            if api_code == _AS_BUSY:
                return KicadMcpError(
                    code=ErrorCode.KICAD_CLI_FAILED,
                    message=f"KiCad está ocupado durante {op_name}.",
                    hint=(
                        "KiCad está ocupado con una operación en curso; reintentá en unos segundos."
                    ),
                    data={"ipc_status": "busy"},
                )
            if api_code == _AS_UNHANDLED:
                return KicadMcpError(
                    code=ErrorCode.KICAD_CLI_FAILED,
                    message=f"KiCad no puede manejar {op_name} en el estado actual.",
                    hint="El editor requerido no está abierto en KiCad (abrí el PCB Editor).",
                    data={"ipc_status": "unhandled"},
                )
    return KicadMcpError(
        code=ErrorCode.KICAD_CLI_FAILED,
        message=f"Fallo IPC en {op_name}.",
        hint=(str(exc)[:200] or "sin detalle disponible"),
    )


def _is_busy(exc: KicadMcpError) -> bool:
    """``True`` si el envelope trae ``data.ipc_status == "busy"`` (D-07.2)."""
    return (
        exc.code is ErrorCode.KICAD_CLI_FAILED
        and exc.data is not None
        and exc.data.get("ipc_status") == "busy"
    )


# --- Retry acotado para lecturas idempotentes (D-07.1) ------------------------

# Whitelist EXPLÍCITA de operaciones a las que se les puede aplicar retry ante
# ``AS_BUSY``. Todas son solo-lectura y no tienen efectos colaterales en KiCad.
# Añadir una entrada requiere leer D-07.1 y verificar que reintentar sea
# semánticamente seguro (el request puede haber sido aceptado y la mutación
# duplicaría). Las mutaciones NO viajan por este camino: usan ``_supervise``
# directamente, así que este set NO es un flag encendible por accidente.
_IDEMPOTENT_OPS: frozenset[str] = frozenset(
    {
        "get_version",
        "get_open_board",
        "get_open_documents_pcb",  # sesión 07 T3 — probe del health fino
        "list_footprint_refs",
        "list_net_names",
        "board_bbox_mm",
        "snapshot_footprints",
        "get_footprint_position",
    }
)

# Backoff exponencial acotado (< 1 s total adicional). D-07.1: máximo 2
# reintentos, para no propagar en cascada un busy que persiste (KiCad
# probablemente está genuinamente ocupado con router/DRC/refill y no
# terminará en el próximo cuarto de segundo).
_BUSY_RETRY_BACKOFFS_MS: tuple[int, ...] = (250, 500)


# --- Bridge -------------------------------------------------------------------


_DEFAULT_TIMEOUT_MS = 2000
_DEFAULT_SOCKET_LINUX = "ipc:///tmp/kicad/api.sock"


class IpcBridge:
    """Cliente IPC serializado con detección de reinicio de KiCad.

    Estado interno mínimo: el ``KiCadClientLike`` conectado y el último
    ``KICAD_API_TOKEN`` visto. No mantiene caches de dominio (eso lo
    hace el Snapshot Store).
    """

    def __init__(
        self,
        *,
        socket_path: str | None = None,
        client_factory: _ClientFactory = _default_client_factory,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
    ) -> None:
        # Resolución del socket: env → argumento → default de la plataforma.
        env_socket = os.environ.get("KICAD_API_SOCKET")
        self._socket_path: str | None = env_socket or socket_path or _DEFAULT_SOCKET_LINUX
        self._timeout_ms = timeout_ms
        self._client_factory = client_factory
        self._client: KiCadClientLike | None = None
        # Token de la instancia — se congela al primer contacto y se
        # compara contra el env de cada llamada para detectar reinicios.
        self._instance_token: str | None = None
        # Cola de profundidad 1 sobre TODA llamada IPC (thread-safe).
        self._lock = threading.Lock()

    # -- ciclo de vida --------------------------------------------------------

    def _current_env_token(self) -> str | None:
        raw = os.environ.get("KICAD_API_TOKEN")
        return raw or None

    def socket_present(self) -> bool:
        """``True`` si el fichero del socket IPC existe (fast-fail, sesión 04).

        Cheap check para el nivel más bajo de ``health`` (sesión 07 D-07.3):
        KiCad crea el socket al arrancar y lo borra al salir, así que su
        presencia distingue "KiCad no está corriendo" (missing) de "KiCad
        corriendo pero el server IPC puede estar ocupado o cerrado". No
        toca red ni el hilo UI.
        """
        return not _socket_file_missing(self._socket_path)

    def _ensure_client(self) -> KiCadClientLike:
        if self._client is None:
            token = self._current_env_token()
            self._client = self._client_factory(self._socket_path, self._timeout_ms, token)
            self._instance_token = token
        return self._client

    @contextmanager
    def _supervise(self, op_name: str) -> Iterator[None]:
        """Supervisa un bloque de operación IPC (sesión 04 T3).

        Si el bloque levanta una excepción no tipada (``ApiError``,
        ``ConnectionError``, ``TimeoutError``, o cualquier otra fuera de
        ``KicadMcpError``), mapea a error tipado del catálogo y —salvo por
        ``AS_BUSY`` (D-07.1)— invalida ``self._client`` para forzar reconexión
        en el próximo request. ``_supervise`` **no** hace retry: eso vive en
        ``_run_supervised_read`` para lecturas idempotentes en whitelist. Las
        mutaciones se supervisan directamente y jamás se reintentan.

        AS_BUSY es un rechazo transitorio de KiCad (la UI está ocupada);
        la conexión IPC sigue viva. Preservar el cliente evita que el
        wrapper de retry pague una reconexión al socket a cambio de nada.
        """
        try:
            yield
        except KicadMcpError:
            raise
        except BaseException as exc:
            mapped = _map_ipc_failure(op_name, exc)
            if not _is_busy(mapped):
                # Cliente sospechoso → descartar para que el próximo request
                # reconstruya la conexión. Busy no afecta la conexión.
                self._client = None
            raise mapped from exc

    def _run_supervised_read(self, op_name: str, do: Callable[[], _T]) -> _T:
        """Ejecuta ``do()`` dentro de ``_supervise(op_name)`` con retry acotado
        para ``AS_BUSY`` (D-07.1).

        ``op_name`` DEBE estar en ``_IDEMPOTENT_OPS`` — el ``assert`` es la
        **frontera estructural** entre lecturas y mutaciones: no existe otra
        vía para aplicar retry, así que ninguna mutación puede reintentarse
        por accidente ni por un flag encendible. Añadir un op a la whitelist
        exige leer D-07.1 y auditar el determinismo del request.

        Retorna el resultado de ``do()`` a la primera respuesta OK. Backoff
        exponencial 250 → 500 ms entre intentos (< 1 s total adicional). Si
        el busy persiste, propaga el ``KICAD_CLI_FAILED`` (``data.ipc_status
        = "busy"``) del último intento. Cualquier otro fallo del catálogo se
        propaga sin retry en el primer intento.
        """
        if op_name not in _IDEMPOTENT_OPS:
            raise AssertionError(f"{op_name!r} no está en la whitelist idempotente (D-07.1)")
        attempt_i = 0
        max_retries = len(_BUSY_RETRY_BACKOFFS_MS)
        while True:
            try:
                with self._supervise(op_name):
                    return do()
            except KicadMcpError as exc:
                if attempt_i >= max_retries or not _is_busy(exc):
                    raise
                backoff_ms = _BUSY_RETRY_BACKOFFS_MS[attempt_i]
                attempt_i += 1
                log_ipc_retry(op_name=op_name, attempt=attempt_i, backoff_ms=backoff_ms)
                time.sleep(backoff_ms / 1000.0)

    def _detect_restart(self) -> None:
        """Compara el token actual con el guardado; lanza ``KICAD_RESTARTED`` si cambió.

        El caso "ambos None" no es reinicio: puede que el server no reciba
        el env de KiCad (por ejemplo, arrancado fuera de un plugin) y aún
        así el socket sea válido.
        """
        current = self._current_env_token()
        if self._instance_token is None:
            self._instance_token = current
            return
        if current is None:
            return  # falta de env no cuenta como reinicio
        if current != self._instance_token:
            # Descarta el cliente: el próximo request reconectará.
            self._client = None
            self._instance_token = current
            raise KicadMcpError(
                code=ErrorCode.KICAD_RESTARTED,
                message="KiCad se reinició durante la sesión (token de instancia distinto).",
                hint="Pedí get_world_context: los snapshots previos quedaron inválidos.",
            )

    # -- operaciones ----------------------------------------------------------

    def get_version(self) -> IpcVersion:
        """Versión de KiCad reportada por IPC. Puede levantar ``KICAD_NOT_RUNNING``."""
        with self._lock:
            self._detect_restart()
            client = self._ensure_client()

            def _do() -> IpcVersion:
                proto = client.get_version()
                return IpcVersion(
                    full=str(getattr(proto, "full_version", "")) or "unknown",
                    major=int(getattr(proto, "major", 0)),
                    minor=int(getattr(proto, "minor", 0)),
                    patch=int(getattr(proto, "patch", 0)),
                )

            return self._run_supervised_read("get_version", _do)

    def get_open_board(self) -> BoardHandle | None:
        """Devuelve un handle al ``Board`` abierto, o ``None`` si no hay board.

        Nunca expone tipos de ``kipy`` fuera del bridge: se envuelve en
        ``BoardHandle`` (frontera de proceso, regla #5).
        """
        with self._lock:
            self._detect_restart()
            client = self._ensure_client()

            def _do() -> BoardHandle | None:
                raw = client.get_board()
                return BoardHandle(_raw=raw) if raw is not None else None

            return self._run_supervised_read("get_open_board", _do)

    def has_open_pcb(self) -> bool:
        """``True`` si KiCad tiene un PCB Editor abierto (sesión 07 T3).

        Consulta ``get_open_documents(DOCTYPE_PCB)`` en lugar de intentar
        ``get_board()`` para no traer el proto del board completo. Distingue:

        - Lista no-vacía → PCB Editor abierto (``True``).
        - Excepción ``AS_UNHANDLED`` (mapeada por ``_map_ipc_failure`` a
          ``KICAD_CLI_FAILED`` con ``data.ipc_status="unhandled"``) → sólo
          project manager sin PCB Editor abierto (``False``).

        Cualquier otro error IPC (busy tras retry, timeout, socket muerto)
        se propaga: ``health`` decide qué reportar en cada nivel del
        payload sin engañar al agente con un ``False`` que en realidad es
        "no lo sé".
        """
        from kipy.proto.common.types import DocumentType

        with self._lock:
            self._detect_restart()
            client = self._ensure_client()

            def _do() -> bool:
                docs = client.get_open_documents(DocumentType.DOCTYPE_PCB)
                return len(docs) > 0

            try:
                return self._run_supervised_read("get_open_documents_pcb", _do)
            except KicadMcpError as exc:
                if (
                    exc.code is ErrorCode.KICAD_CLI_FAILED
                    and exc.data is not None
                    and (exc.data.get("ipc_status") == "unhandled")
                ):
                    return False
                raise

    # -- consultas del board (para validación previa a mutaciones) ------------

    def list_footprint_refs(self, board: BoardHandle) -> list[str]:
        """Refs (``U1``, ``R42``…) de todos los footprints del board."""
        with self._lock:
            self._detect_restart()

            def _do() -> list[str]:
                return [str(fp.reference_field.text.value) for fp in board.raw.get_footprints()]

            return self._run_supervised_read("list_footprint_refs", _do)

    def list_net_names(self, board: BoardHandle) -> list[str]:
        """Nombres de los nets del board."""
        with self._lock:
            self._detect_restart()

            def _do() -> list[str]:
                return [str(n.name) for n in board.raw.get_nets()]

            return self._run_supervised_read("list_net_names", _do)

    def board_bbox_mm(self, board: BoardHandle) -> BBoxMm:
        """Bounding box del board en milímetros.

        Preferencia: usar la superficie declarada del board (Edge.Cuts).
        Fallback: unión de bounding boxes de todos los footprints. En el
        MVP nos apoyamos en un bbox amplio: el objetivo del check es
        rechazar coordenadas absurdas, no ser pixel-perfect.
        """
        with self._lock:
            self._detect_restart()

            def _do() -> BBoxMm:
                items = list(board.raw.get_footprints())
                if not items:
                    # Board vacío: no hay bbox útil; devolvemos un rango grande
                    # que no rechaza nada razonable (1e6 mm es el borde
                    # razonable de KiCad).
                    return BBoxMm(Mm(-1e6), Mm(-1e6), Mm(1e6), Mm(1e6))
                xs: list[float] = []
                ys: list[float] = []
                for fp in items:
                    pos = fp.position
                    xs.append(nm_to_mm(Nm(int(pos.x))))
                    ys.append(nm_to_mm(Nm(int(pos.y))))
                # Margen de 100 mm alrededor del enjambre de footprints.
                margin = 100.0
                return BBoxMm(
                    Mm(min(xs) - margin),
                    Mm(min(ys) - margin),
                    Mm(max(xs) + margin),
                    Mm(max(ys) + margin),
                )

            return self._run_supervised_read("board_bbox_mm", _do)

    def snapshot_footprints(self, board: BoardHandle) -> tuple[FootprintData, ...]:
        """Datos primitivos de todos los footprints — para el snapshot post-mutación.

        Sesión 05 T5. Se ejecuta bajo el lock del bridge; devuelve dataclasses
        propias (nunca tipos de kipy) para que ``state_builder.build_state_from_board``
        materialice un ``NormalizedState`` sin volver a IPC.
        """
        with self._lock:
            self._detect_restart()

            def _do() -> tuple[FootprintData, ...]:
                items: list[FootprintData] = []
                for fp in board.raw.get_footprints():
                    ref = str(fp.reference_field.text.value)
                    value = str(fp.value_field.text.value)
                    pos = fp.position
                    x = nm_to_mm(Nm(int(pos.x)))
                    y = nm_to_mm(Nm(int(pos.y)))
                    pads: list[FootprintPadData] = []
                    for pad in fp.definition.pads:
                        number = str(pad.number)
                        net = pad.net
                        # net.name puede ser cadena vacía para pads no conectados.
                        net_name = str(net.name) if net is not None and net.name else None
                        pads.append(FootprintPadData(number=number, net_name=net_name))
                    items.append(
                        FootprintData(
                            ref=ref,
                            value=value,
                            x_mm=x,
                            y_mm=y,
                            pads=tuple(pads),
                        )
                    )
                return tuple(items)

            return self._run_supervised_read("snapshot_footprints", _do)

    def get_footprint_position(self, board: BoardHandle, ref: str) -> tuple[Mm, Mm]:
        """Posición ``(x_mm, y_mm)`` del footprint ``ref`` según el board vivo.

        Interno del bridge (sesión 04 T6): lo consume el test integration_gui
        para verificar que ``move_footprint`` persistió las coordenadas.
        No se expone como tool MCP; el catálogo permanece igual.

        Levanta ``COMPONENT_NOT_FOUND`` si el ref no está.
        """
        with self._lock:
            self._detect_restart()

            def _do() -> tuple[Mm, Mm]:
                for fp in board.raw.get_footprints():
                    if str(fp.reference_field.text.value) == ref:
                        pos = fp.position
                        return (
                            nm_to_mm(Nm(int(pos.x))),
                            nm_to_mm(Nm(int(pos.y))),
                        )
                raise KicadMcpError(
                    code=ErrorCode.COMPONENT_NOT_FOUND,
                    message=f"Footprint {ref} no está en el board.",
                    hint="Verificá que el ref exista y que el board correcto esté abierto.",
                )

            return self._run_supervised_read("get_footprint_position", _do)

    # -- mutaciones -----------------------------------------------------------

    def move_footprint(
        self,
        board: BoardHandle,
        ref: str,
        x_mm: Mm,
        y_mm: Mm,
        *,
        timings: dict[str, float] | None = None,
    ) -> None:
        """Mueve el footprint ``ref`` a ``(x_mm, y_mm)`` y persiste el commit.

        Precondición: el llamador ya validó existencia de ``ref`` y que
        las coordenadas están dentro del bounding box. La validación se
        hace afuera para poder emitir errores tipados con hints ricos.

        Si ``timings`` es un dict, se rellena ``timings["lookup_ms"]`` con
        la latencia de la búsqueda O(board) de la ref (sesión 07 T5,
        D-07.5). Sirve como instrumento de medición para decidir si vale
        la pena optimizar la búsqueda (cache ref→item, GetItems filtrado,
        etc.). El logging es aditivo — F3 intacta.
        """
        # ``fp.position`` es un getter que devuelve ``Vector2(self._proto.position)``
        # (kipy geometry.py:38-42: Vector2 hace CopyFrom del proto). Escribir
        # ``fp.position.x = …`` muta una copia local y update_items envía el
        # proto original sin cambios → mutación silenciosamente perdida
        # (sesión 06 T1). El setter ``fp.position = Vector2(...)`` sí escribe
        # sobre el proto interno del FootprintInstance y además arrastra
        # fields/pads por delta (board_types.py:1939-1964).
        from kipy.geometry import Vector2

        with self._lock:
            self._detect_restart()
            with self._supervise("move_footprint"):
                raw_board = board.raw
                lookup_start = time.perf_counter()
                target_fp = None
                for fp in raw_board.get_footprints():
                    if str(fp.reference_field.text.value) == ref:
                        target_fp = fp
                        break
                if timings is not None:
                    timings["lookup_ms"] = (time.perf_counter() - lookup_start) * 1000
                if target_fp is not None:
                    target_fp.position = Vector2.from_xy(int(mm_to_nm(x_mm)), int(mm_to_nm(y_mm)))
                    raw_board.update_items(target_fp)
                    return
                # Consistencia: si no lo encontramos, es un bug del llamador.
                raise KicadMcpError(
                    code=ErrorCode.COMPONENT_NOT_FOUND,
                    message=f"Footprint {ref} no está en el board (post-validación).",
                    hint="Snapshot del board cambió entre la validación y la mutación.",
                )

    def add_track(
        self,
        board: BoardHandle,
        net: str,
        start_mm: tuple[Mm, Mm],
        end_mm: tuple[Mm, Mm],
        width_mm: Mm,
        layer: str,
        *,
        timings: dict[str, float] | None = None,
    ) -> None:
        """Agrega un track lineal entre ``start`` y ``end`` en ``layer``.

        Precondición: net y layer válidos, coordenadas dentro del bbox.
        Segmentos múltiples (points_mm en la spec) se representan como
        múltiples add_track por la simplicidad del MVP.

        Si ``timings`` es un dict, se rellena ``timings["lookup_ms"]`` con
        la latencia de la búsqueda O(nets) del net por nombre (sesión 07
        T5, D-07.5).
        """
        # Import perezoso de tipos de kipy: mantiene el bridge testable
        # con fakes sin pagar el costo cuando kipy no se usa.
        from kipy.board_types import Track
        from kipy.geometry import Vector2
        from kipy.proto.board.board_types_pb2 import BoardLayer

        with self._lock:
            self._detect_restart()
            with self._supervise("add_track"):
                raw_board = board.raw
                lookup_start = time.perf_counter()
                net_obj = next(
                    (n for n in raw_board.get_nets() if str(n.name) == net),
                    None,
                )
                if timings is not None:
                    timings["lookup_ms"] = (time.perf_counter() - lookup_start) * 1000
                if net_obj is None:
                    raise KicadMcpError(
                        code=ErrorCode.NET_NOT_FOUND,
                        message=f"Net {net} no está en el board (post-validación).",
                        hint="Snapshot del board cambió entre la validación y la mutación.",
                    )
                # Layer string ("F.Cu", "B.Cu", "F.SilkS") → enum BoardLayer (BL_F_Cu,…).
                try:
                    layer_value = BoardLayer.Value(f"BL_{layer.replace('.', '_')}")
                except ValueError as exc:
                    raise KicadMcpError(
                        code=ErrorCode.INVALID_PARAMS,
                        message=f"Layer {layer!r} no reconocido por KiCad.",
                        hint="Valores esperados: F.Cu, B.Cu, F.SilkS, B.SilkS, Edge.Cuts, …",
                    ) from exc
                track = Track()
                track.start = Vector2.from_xy(
                    int(mm_to_nm(start_mm[0])), int(mm_to_nm(start_mm[1]))
                )
                track.end = Vector2.from_xy(int(mm_to_nm(end_mm[0])), int(mm_to_nm(end_mm[1])))
                track.width = int(mm_to_nm(width_mm))
                track.layer = layer_value
                track.net = net_obj
                raw_board.create_items(track)
