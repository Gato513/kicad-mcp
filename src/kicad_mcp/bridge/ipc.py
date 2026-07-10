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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NewType, Protocol

from ..errors import ErrorCode, KicadMcpError

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


def _map_ipc_failure(op_name: str, exc: BaseException) -> KicadMcpError:
    """Traduce excepciones que atraviesan una operación IPC a errores del catálogo.

    Regla:
    - ``TimeoutError`` (builtin, socket, kipy) → ``KICAD_TIMEOUT``.
    - ``ConnectionError`` (builtin) o ``kipy.errors.ConnectionError`` →
      ``KICAD_NOT_RUNNING``.
    - Cualquier otro (p. ej. ``kipy.errors.ApiError``) → ``KICAD_CLI_FAILED``
      con el detalle sanitizado en el hint.

    Se identifica ``kipy.errors.ConnectionError`` por ``__qualname__`` **más**
    ``__module__.startswith("kipy")``, para no forzar el import de ``kipy``
    en un ciclo perezoso y a la vez no confundir un ``ConnectionError``
    homónimo definido por otra librería que corra dentro del bloque
    supervisado (sesión 05 T1).
    """
    if isinstance(exc, TimeoutError):
        return KicadMcpError(
            code=ErrorCode.KICAD_TIMEOUT,
            message=f"IPC excedió el timeout durante {op_name}.",
            hint="Reintentar o reducir el alcance de la operación.",
        )
    exc_type = type(exc)
    is_kipy_conn_error = exc_type.__qualname__ == "ConnectionError" and (
        exc_type.__module__ or ""
    ).startswith("kipy")
    if isinstance(exc, ConnectionError) or is_kipy_conn_error:
        return KicadMcpError(
            code=ErrorCode.KICAD_NOT_RUNNING,
            message="Conexión IPC con KiCad perdida durante la operación.",
            hint="Abrí KiCad y habilitá el API server; el próximo request reconectará.",
        )
    return KicadMcpError(
        code=ErrorCode.KICAD_CLI_FAILED,
        message=f"Fallo IPC en {op_name}.",
        hint=(str(exc)[:200] or "sin detalle disponible"),
    )


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
        ``KicadMcpError``), invalida ``self._client`` para forzar reconexión
        en el próximo request y mapea a error tipado del catálogo. **NO** se
        hace retry silencioso: la operación fallida responde su error; la
        reconexión es responsabilidad del request siguiente.
        """
        try:
            yield
        except KicadMcpError:
            raise
        except BaseException as exc:
            # Cualquier fallo mid-op → cliente sospechoso. Descartar para
            # que el próximo request reconstruya la conexión al socket.
            self._client = None
            raise _map_ipc_failure(op_name, exc) from exc

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
            with self._supervise("get_version"):
                proto = client.get_version()
                return IpcVersion(
                    full=str(getattr(proto, "full_version", "")) or "unknown",
                    major=int(getattr(proto, "major", 0)),
                    minor=int(getattr(proto, "minor", 0)),
                    patch=int(getattr(proto, "patch", 0)),
                )

    def get_open_board(self) -> BoardHandle | None:
        """Devuelve un handle al ``Board`` abierto, o ``None`` si no hay board.

        Nunca expone tipos de ``kipy`` fuera del bridge: se envuelve en
        ``BoardHandle`` (frontera de proceso, regla #5).
        """
        with self._lock:
            self._detect_restart()
            client = self._ensure_client()
            with self._supervise("get_open_board"):
                raw = client.get_board()
                return BoardHandle(_raw=raw) if raw is not None else None

    # -- consultas del board (para validación previa a mutaciones) ------------

    def list_footprint_refs(self, board: BoardHandle) -> list[str]:
        """Refs (``U1``, ``R42``…) de todos los footprints del board."""
        with self._lock:
            self._detect_restart()
            with self._supervise("list_footprint_refs"):
                return [str(fp.reference_field.text.value) for fp in board.raw.get_footprints()]

    def list_net_names(self, board: BoardHandle) -> list[str]:
        """Nombres de los nets del board."""
        with self._lock:
            self._detect_restart()
            with self._supervise("list_net_names"):
                return [str(n.name) for n in board.raw.get_nets()]

    def board_bbox_mm(self, board: BoardHandle) -> BBoxMm:
        """Bounding box del board en milímetros.

        Preferencia: usar la superficie declarada del board (Edge.Cuts).
        Fallback: unión de bounding boxes de todos los footprints. En el
        MVP nos apoyamos en un bbox amplio: el objetivo del check es
        rechazar coordenadas absurdas, no ser pixel-perfect.
        """
        with self._lock:
            self._detect_restart()
            with self._supervise("board_bbox_mm"):
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

    def snapshot_footprints(self, board: BoardHandle) -> tuple[FootprintData, ...]:
        """Datos primitivos de todos los footprints — para el snapshot post-mutación.

        Sesión 05 T5. Se ejecuta bajo el lock del bridge; devuelve dataclasses
        propias (nunca tipos de kipy) para que ``state_builder.build_state_from_board``
        materialice un ``NormalizedState`` sin volver a IPC.
        """
        with self._lock:
            self._detect_restart()
            with self._supervise("snapshot_footprints"):
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

    def get_footprint_position(self, board: BoardHandle, ref: str) -> tuple[Mm, Mm]:
        """Posición ``(x_mm, y_mm)`` del footprint ``ref`` según el board vivo.

        Interno del bridge (sesión 04 T6): lo consume el test integration_gui
        para verificar que ``move_footprint`` persistió las coordenadas.
        No se expone como tool MCP; el catálogo permanece igual.

        Levanta ``COMPONENT_NOT_FOUND`` si el ref no está.
        """
        with self._lock:
            self._detect_restart()
            with self._supervise("get_footprint_position"):
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

    # -- mutaciones -----------------------------------------------------------

    def move_footprint(self, board: BoardHandle, ref: str, x_mm: Mm, y_mm: Mm) -> None:
        """Mueve el footprint ``ref`` a ``(x_mm, y_mm)`` y persiste el commit.

        Precondición: el llamador ya validó existencia de ``ref`` y que
        las coordenadas están dentro del bounding box. La validación se
        hace afuera para poder emitir errores tipados con hints ricos.
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
                for fp in raw_board.get_footprints():
                    if str(fp.reference_field.text.value) == ref:
                        fp.position = Vector2.from_xy(int(mm_to_nm(x_mm)), int(mm_to_nm(y_mm)))
                        raw_board.update_items(fp)
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
    ) -> None:
        """Agrega un track lineal entre ``start`` y ``end`` en ``layer``.

        Precondición: net y layer válidos, coordenadas dentro del bbox.
        Segmentos múltiples (points_mm en la spec) se representan como
        múltiples add_track por la simplicidad del MVP.
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
                net_obj = next(
                    (n for n in raw_board.get_nets() if str(n.name) == net),
                    None,
                )
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
