"""Tools de la categoría ``sch``: primeras mutaciones sobre esquemáticos.

Sesión 08 T4 (D-08.5). Basada en el spike de sesión 05 T6 (kicad-skip 0.2.5):
``template.clone()`` + ``Reference.value`` + ``at.value`` + ``sch.write()``.

Alcance permanente v0.2 (D-08.5, fuera de scope hasta nueva decisión):

1. **Librería:** solo clonado desde un símbolo ya instanciado en el
   archivo objetivo (``lib_id`` existente). Pick de librerías externas
   queda fuera de scope permanente hasta nueva decisión.
2. ``add_symbol`` **coloca**, no conecta. Cableado en ``connect_pins``
   (v0.5).
3. ``add_symbol`` toca SOLO el ``.kicad_sch`` indicado. No genera
   footprint ni toca el ``.kicad_pcb`` — la re-anotación/sync sch↔pcb
   la hace KiCad, no el MVP.
4. **Snapshot Store:** snapshot de DISCO post-write con mtimes frescos
   (D-06.2). El patrón vivo (``mtimes=None``) es exclusivo de las
   mutaciones IPC (``move_footprint``, ``add_track``).

Hazard del editor abierto: si el usuario tiene el ``.kicad_sch`` abierto
en KiCad al momento de la mutación, KiCad mostrará un aviso "el archivo
cambió en disco, ¿recargar?" cuando el usuario vuelva a la ventana. El
MVP **documenta** el hazard (ver `docs/adr/…` y catálogo); no lo
resuelve automáticamente. Cerrar el archivo en KiCad antes de mutar es
la práctica segura.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..audit.logger import record as audit_record
from ..bridge.state_builder import build_state_cached
from ..errors import ErrorCode, KicadMcpError
from ..gates.g1 import ensure_session_backup
from ..logging_config import estimate_tokens, log_tool_call, tool_call_timer
from ..paths import canonicalize_within_project_root
from ..snapshots import collect_project_mtimes, get_default_store, validate_base_snap
from ..tools.world import _resolve_root_schematic
from ..toon.schema import Component, NormalizedState, Pin

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# Sanitización de ``ref`` (regla 6): KiCad acepta refs con formato
# ``<prefijo alfanumérico><sufijo numérico>`` (U1, RR1, POT1, BUS1). El
# encoder TOON encapsula la ref sin escaparla; una ref con backtick o
# pipe rompería el output. Este regex fuerza:
# - primer char letra,
# - caracteres válidos ``[A-Za-z0-9_]``,
# - termina en al menos un dígito,
# - largo total ≤ 16.
# Cualquier ref del inventario 004 (docs/componentes-pcb.md) pasa.
_REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,14}[0-9]$")


def _project_root() -> Path:
    return _resolve_root_schematic().parent


def _validate_ref(ref: str) -> None:
    """Sanitiza ``ref`` (regla 6). Levanta ``INVALID_PARAMS`` si no valida."""
    if not _REF_RE.match(ref):
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"Ref {ref!r} no válida.",
            hint=(
                "Formato: <Letra><[A-Za-z0-9_]…><Dígito>, ≤16 chars (p. ej. U6, R42, RR1, POT1)."
            ),
        )


def _list_project_sheets(root: Path) -> list[Path]:
    """Todos los ``.kicad_sch`` del proyecto (root + hojas hijas)."""
    return sorted(p.resolve() for p in root.glob("*.kicad_sch"))


def _collect_all_refs(root: Path) -> dict[str, Path]:
    """Refs presentes en el proyecto → hoja donde vive cada una.

    Recorre todos los ``.kicad_sch`` del root con kicad-skip. El resultado
    permite validar colisiones "en NINGUNA hoja" antes de mutar (D-08.5).
    kicad-skip abre cada archivo independientemente (spike sesión 05 T6);
    no materializa la jerarquía sino que enumera las hojas planamente,
    que es lo que necesitamos para el check de colisión.
    """
    from skip import Schematic  # type: ignore[import-untyped]

    refs: dict[str, Path] = {}
    for sheet in _list_project_sheets(root):
        try:
            sch = Schematic(str(sheet))
        except Exception as exc:
            raise KicadMcpError(
                code=ErrorCode.KICAD_CLI_FAILED,
                message=f"No se pudo parsear {sheet.name}.",
                hint=str(exc)[:200] or "sin detalle disponible",
            ) from exc
        for sym in sch.symbol:
            try:
                ref_value = str(sym.Reference.value)
            except AttributeError:
                continue
            # Refs con placeholders (Reference vacía en templates) se ignoran.
            if ref_value and ref_value not in refs:
                refs[ref_value] = sheet
    return refs


def _load_target_sheet(sheet_arg: str, root: Path) -> Path:
    """Resuelve ``sheet`` (relativo al proyecto) a un path canónico existente.

    ``sheet_arg`` es un nombre relativo — por ejemplo ``"video.kicad_sch"``
    o ``"muxdata.kicad_sch"``. La canonicalización usa la regla #4 y
    verifica extensión + existencia. NO acepta hojas fuera del root.
    """
    sheet_path = canonicalize_within_project_root(sheet_arg, root)
    if sheet_path.suffix != ".kicad_sch":
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"El sheet debe ser un .kicad_sch (recibido: {sheet_path.name}).",
            hint="Pasá el nombre relativo al proyecto, p. ej. 'video.kicad_sch'.",
        )
    if not sheet_path.is_file():
        raise KicadMcpError(
            code=ErrorCode.PROJECT_NOT_FOUND,
            message=f"Hoja {sheet_path.name} no existe en el proyecto.",
            hint=f"Hojas disponibles: {', '.join(p.name for p in _list_project_sheets(root))}.",
        )
    return sheet_path


def _find_template(sch: Any, lib_id: str) -> Any:
    """Localiza el primer símbolo instanciado con ``lib_id`` (template a clonar).

    D-08.5 #1: el lib_id DEBE estar YA instanciado en la hoja. No
    hacemos pick de librerías externas. Si el símbolo no está, error
    tipado con hint listando los lib_ids disponibles en la hoja.
    """
    seen: set[str] = set()
    for sym in sch.symbol:
        try:
            candidate = str(sym.lib_id.value)
        except AttributeError:
            continue
        seen.add(candidate)
        if candidate == lib_id:
            return sym
    hint_list = ", ".join(sorted(seen)[:5]) if seen else "hoja sin símbolos"
    raise KicadMcpError(
        code=ErrorCode.INVALID_PARAMS,
        message=f"lib_id {lib_id!r} no está instanciado en la hoja.",
        hint=f"lib_ids disponibles: {hint_list}",
    )


def _bbox_of_sheet(sch: Any) -> tuple[float, float, float, float]:
    """Bounding box de los símbolos instanciados en la hoja + margen 200 mm.

    Sirve como validación conservadora: rechaza coordenadas absurdas sin
    ser pixel-perfect. Coincide con la estrategia de ``board_bbox_mm``.
    Si la hoja está vacía se acepta cualquier coordenada finita (rango
    grande simétrico).
    """
    xs: list[float] = []
    ys: list[float] = []
    for sym in sch.symbol:
        try:
            at = sym.at.value
        except AttributeError:
            continue
        if isinstance(at, list) and len(at) >= 2:
            xs.append(float(at[0]))
            ys.append(float(at[1]))
    if not xs:
        return (-1e6, -1e6, 1e6, 1e6)
    margin = 200.0
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def _pin_ids_of_lib_id(sch: Any, lib_id: str) -> tuple[str, ...]:
    """Extrae la lista de ``pin.number`` del ``lib_symbols`` para ``lib_id``.

    Los ``lib_symbols`` viven en el ``.kicad_sch`` (definiciones locales
    del proyecto). kicad-skip los expone como atributos con ``:``
    reemplazado por ``_``. Cada uno tiene sub-símbolos (``symbol[]``);
    los pines viven dentro de esos.

    Sirve al camino de derivación: el netlist post-write NO refleja el
    símbolo añadido (kicad-cli no lo procesa hasta que KiCad re-anota),
    así que el snapshot post lo construimos localmente con estos pines
    marcados como sin conectar (D-08.5 #2 — add_symbol no conecta).
    """
    key = lib_id.replace(":", "_")
    ls = getattr(sch.lib_symbols, key, None)
    if ls is None:
        return ()
    pin_ids: list[str] = []
    for sub in ls.symbol:
        pins = getattr(sub, "pin", None)
        if pins is None:
            continue
        for p in pins:
            try:
                pin_ids.append(str(p.number.value))
            except AttributeError:
                continue
    return tuple(pin_ids)


def _template_value(template: Any) -> str:
    """Extrae el ``Value`` (p. ej. ``"10k"``, ``"C2"``) del template a clonar."""
    try:
        return str(template.Value.value)
    except AttributeError:
        return ""


def _add_symbol_to_sheet(
    sheet_path: Path,
    lib_id: str,
    ref: str,
    x_mm: float,
    y_mm: float,
) -> dict[str, Any]:
    """Clona el template + Reference + at + write. Escribe sobre ``sheet_path``.

    Delega en el spike de sesión 05 T6 (clone/at/Reference/write). El
    ``sch.write`` sobreescribe el archivo; el llamador ya hizo el G1
    backup y validó todo. La rotación (grado 3 de ``at.value``) se
    conserva de la del template — MVP no expone rotación.

    Devuelve un dict con el ``value`` del template y los ``pin_ids`` del
    lib_symbol, para que el llamador derive el post-estado sch sin
    depender de que ``kicad-cli sch export netlist`` regenere el netlist
    (que no lo hace hasta que KiCad re-anota — ver comentario en
    ``register.add_symbol``).
    """
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    template = _find_template(sch, lib_id)
    clone = template.clone()
    # Posición nueva; preservar rotación del template.
    old_at = template.at.value
    rotation = float(old_at[2]) if isinstance(old_at, list) and len(old_at) >= 3 else 0.0
    clone.at.value = [float(x_mm), float(y_mm), rotation]
    clone.Reference.value = ref
    template_value = _template_value(template)
    pin_ids = _pin_ids_of_lib_id(sch, lib_id)
    sch.write(str(sheet_path))
    return {"value": template_value, "pin_ids": pin_ids}


def _derive_post_state_sch(
    pre_state: NormalizedState,
    *,
    ref: str,
    lib_id: str,
    value: str,
    pin_ids: tuple[str, ...],
    x_mm: float,
    y_mm: float,
) -> NormalizedState:
    """Post-estado sch = pre-estado + Component nuevo (pines desconectados).

    D-08.5 #2: ``add_symbol`` NO conecta pines. Los pines del componente
    nuevo se emiten con ``net=None`` (spec §2: pin sin conectar → ``">-"``).
    La netlist real la producirá KiCad cuando el usuario re-anote; hasta
    entonces el snapshot vivo/de-disco refleja el símbolo como aislado.

    El ``snap`` se emite como 0; el llamador lo sobrescribe con el
    ``snap_id`` del store.
    """
    new_component = Component(
        ref=ref,
        value=value,
        lib=lib_id,
        x=float(x_mm),
        y=float(y_mm),
        pins=tuple(Pin(p=pid, net=None) for pid in pin_ids),
    )
    return NormalizedState(
        kind=pre_state.kind,
        snap=0,
        components=(*pre_state.components, new_component),
    )


def _verify_effect(
    sheet_path: Path,
    ref: str,
    lib_id: str,
    x_mm: float,
    y_mm: float,
) -> dict[str, Any]:
    """Re-lee el ``.kicad_sch`` escrito y verifica el efecto (D-06.3).

    Devuelve un pequeño dict con el conteo total y la posición leída del
    símbolo nuevo. El caller lo emite en el log JSON de la tool. Si el
    símbolo no aparece o su lib_id/posición no coincide, levanta
    ``KICAD_CLI_FAILED`` para que la tool falle loud — la mutación
    quedó en un estado inconsistente (poco probable pero no impensable
    ante una race con el usuario).
    """
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    total = 0
    found: Any = None
    for sym in sch.symbol:
        total += 1
        try:
            if str(sym.Reference.value) == ref:
                found = sym
        except AttributeError:
            continue
    if found is None:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"Verificación de efecto: no se encontró {ref} tras write.",
            hint="El archivo se escribió pero el símbolo nuevo no aparece; posible race.",
        )
    live_lib_id = str(found.lib_id.value)
    if live_lib_id != lib_id:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"Verificación de efecto: lib_id incorrecto ({live_lib_id} != {lib_id}).",
            hint="El clon del template escribió un lib_id distinto — bug interno.",
        )
    at = found.at.value
    live_x = float(at[0]) if isinstance(at, list) and len(at) >= 1 else 0.0
    live_y = float(at[1]) if isinstance(at, list) and len(at) >= 2 else 0.0
    if abs(live_x - x_mm) > 1e-3 or abs(live_y - y_mm) > 1e-3:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"Verificación de efecto: posición leída ({live_x}, {live_y}) != pedida.",
            hint="El write persistió otra posición — bug interno.",
        )
    return {"total": total, "x_mm": live_x, "y_mm": live_y}


def _audit_error(
    root: Path,
    tool: str,
    params: dict[str, Any],
    code: ErrorCode,
) -> None:
    """Registra una mutación rechazada. No suprime la excepción del llamador."""
    audit_record(root, tool=tool, params=params, error_code=code.value)


def register(mcp: FastMCP) -> None:
    """Registra las tools de mutación de esquemático en la instancia FastMCP."""

    @mcp.tool(
        name="add_symbol",
        description="Clona un símbolo ya presente en una hoja y lo coloca con nueva ref",
    )
    def add_symbol(
        sheet: str,
        lib_id: str,
        ref: str,
        x_mm: float,
        y_mm: float,
        base_snap: int | None = None,
    ) -> str:
        with tool_call_timer() as timer:
            root = _project_root()
            # Validación de snap ANTES de tocar disco (paralelo a move_footprint).
            if base_snap is not None:
                validate_base_snap(get_default_store(), base_snap, _resolve_root_schematic())

            params_for_audit = {
                "sheet": sheet,
                "lib_id": lib_id,
                "ref": ref,
                "x_mm": x_mm,
                "y_mm": y_mm,
            }
            # Regla 6: sanitizar TODO string que vaya al archivo.
            try:
                _validate_ref(ref)
            except KicadMcpError as err:
                _audit_error(root, "add_symbol", params_for_audit, err.code)
                raise

            sheet_path = _load_target_sheet(sheet, root)
            all_refs = _collect_all_refs(root)
            if ref in all_refs:
                _audit_error(root, "add_symbol", params_for_audit, ErrorCode.INVALID_PARAMS)
                collision_sheet = all_refs[ref].name
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"Ref {ref!r} ya existe en el proyecto.",
                    hint=f"Colisión en {collision_sheet}. Elegí otro ref.",
                )

            # Bbox de la hoja (con margen) para rechazar coords absurdas.
            from skip import Schematic

            probe = Schematic(str(sheet_path))
            bbox = _bbox_of_sheet(probe)
            if not (bbox[0] <= x_mm <= bbox[2] and bbox[1] <= y_mm <= bbox[3]):
                _audit_error(root, "add_symbol", params_for_audit, ErrorCode.INVALID_PARAMS)
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=f"Coordenadas ({x_mm}, {y_mm}) fuera del área de la hoja.",
                    hint=(
                        f"Rango permitido en {sheet_path.name}: "
                        f"x∈[{bbox[0]:.1f}, {bbox[2]:.1f}], y∈[{bbox[1]:.1f}, {bbox[3]:.1f}] (mm)."
                    ),
                )
            # Valida presencia del lib_id ANTES del G1 (barato y trivialmente
            # falseable — no ensuciamos backups por un typo del agente).
            _find_template(probe, lib_id)

            # Pre-estado del proyecto ANTES de la mutación: base del
            # snapshot post-write que se construirá por derivación local.
            # Motivo: ``kicad-cli sch export netlist`` NO incluye el
            # símbolo recién añadido (KiCad re-anota jerarquía al abrir
            # el sch), así que reconstruir con ``build_state_cached``
            # post-write dispararía "netlist sin posición: <ref>". La
            # derivación local es fiel: el símbolo existe en el sch, con
            # su lib_id, sus pines conocidos, y sin conexiones — que es
            # exactamente lo que ``add_symbol`` produce (D-08.5 #2).
            root_sch = _resolve_root_schematic()
            pre_state = build_state_cached(root_sch, snap=0)[0]

            backup_info = ensure_session_backup(root)  # Gate G1
            template_info = _add_symbol_to_sheet(sheet_path, lib_id, ref, x_mm, y_mm)

            # D-06.3: verificar el EFECTO leyendo el archivo escrito.
            effect = _verify_effect(sheet_path, ref, lib_id, x_mm, y_mm)

            # D-06.2 / D-08.5 #4: snapshot de DISCO post-write con mtimes
            # frescos. El estado se DERIVA localmente del pre + Component
            # nuevo (pines desconectados). Registrarlo con mtimes reales
            # del proyecto post-write mantiene el chequeo de
            # ``EXTERNAL_EDIT_DETECTED`` activo para futuras deltas
            # (patrón vivo NO aplica: es exclusivo de mutaciones IPC).
            new_state = _derive_post_state_sch(
                pre_state,
                ref=ref,
                lib_id=lib_id,
                value=str(template_info["value"]),
                pin_ids=tuple(template_info["pin_ids"]),
                x_mm=x_mm,
                y_mm=y_mm,
            )
            fresh_mtimes = collect_project_mtimes(root_sch)
            snap_id = get_default_store().register(new_state, fresh_mtimes)

            audit_record(
                root,
                tool="add_symbol",
                params={**params_for_audit, "base_snap": base_snap},
                result={
                    "snap": snap_id,
                    "backup": backup_info.get("backup"),
                    "sheet_total": effect["total"],
                },
            )
            confirmation = (
                f"OK add_symbol {ref} {lib_id} @({x_mm:.1f},{y_mm:.1f})"
                f" in {sheet_path.name} [snap:{snap_id}]"
            )
        extra: dict[str, Any] = {
            "ref": ref,
            "lib_id": lib_id,
            "sheet": sheet_path.name,
            "base_snap": base_snap,
            "backup_already_done": backup_info.get("already_done"),
            "sheet_total": effect["total"],
        }
        log_tool_call(
            tool_name="add_symbol",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra=extra,
        )
        return confirmation
