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
from dataclasses import dataclass
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


def _default_client_factory(
    socket_path: str | None, timeout_ms: int, kicad_token: str | None
) -> KiCadClientLike:
    """Fábrica real: instancia ``kipy.KiCad``.

    Import perezoso: no se resuelve ``kipy`` hasta que un llamador lo
    necesita (mantiene el server arrancable si el paquete falla al
    importar por razones ambientales).
    """
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
                "Abrí KiCad y habilitá el API server en "
                "Preferences → Plugins → Enable API server."
            ),
        ) from exc


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
            self._client = self._client_factory(
                self._socket_path, self._timeout_ms, token
            )
            self._instance_token = token
        return self._client

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
            try:
                raw = client.get_board()
            except KicadMcpError:
                raise
            except Exception as exc:
                # Algunos códigos de ``kipy.ApiError`` (por ejemplo, no board
                # abierto) llegan como ApiError. No mapeamos aquí — el
                # llamador decide si "no hay board" es un error o un caso.
                message = str(exc)[:200]
                raise KicadMcpError(
                    code=ErrorCode.KICAD_CLI_FAILED,
                    message="Fallo IPC al recuperar el board abierto.",
                    hint=message or "sin detalle disponible",
                ) from exc
            return BoardHandle(_raw=raw) if raw is not None else None
