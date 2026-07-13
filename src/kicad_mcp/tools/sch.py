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

import difflib
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


# Sanitización de campos de texto que van a un archivo (regla 6). El encoder
# TOON re-sanitiza ``value`` al LEERLO (encoder.py:_sanitize, §5); esta capa de
# ESCRITURA rechaza lo que rompería el archivo o el confirm: caracteres de
# control/saltos de línea y longitudes absurdas. Los caracteres estructurales
# de TOON (``>|:``) NO se rechazan acá — el ``footprint_id`` legítimamente lleva
# ``:`` (lib:name), y el encoder los neutraliza al mostrar.
_MAX_FIELD_LEN = 40
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# ``lib:name`` — dos segmentos no vacíos de chars válidos de librería KiCad.
# NO valida existencia en las librerías del sistema (D-12.1: sin acceso; KiCad
# lo marcará en F8 → File → Update PCB / al asignar footprints).
_FOOTPRINT_RE = re.compile(r"^[A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+$")


def _validate_field_text(text: str, field: str) -> None:
    """Rechaza texto no escribible a un ``.kicad_sch`` (regla 6, borde de escritura)."""
    if _CONTROL_RE.search(text):
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"El campo {field} contiene caracteres de control o saltos de línea.",
            hint="Usá texto plano imprimible (sin \\n, \\t ni control).",
        )
    if len(text) > _MAX_FIELD_LEN:
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"El campo {field} excede {_MAX_FIELD_LEN} chars ({len(text)}).",
            hint=f"Acortá el {field} a ≤{_MAX_FIELD_LEN} caracteres.",
        )


def _validate_value(value: str) -> None:
    """Valida ``value`` para ``set_value`` (regla 6 + no vacío)."""
    if not value.strip():
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message="El value no puede estar vacío.",
            hint="Pasá el valor del componente, p. ej. '22k', '100nF', 'STM32F103'.",
        )
    _validate_field_text(value, "value")


def _validate_footprint_id(footprint_id: str) -> None:
    """Valida FORMATO ``lib:name`` (regla 6 + D-12.1). NO valida existencia."""
    _validate_field_text(footprint_id, "footprint_id")
    if not _FOOTPRINT_RE.match(footprint_id):
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"footprint_id {footprint_id!r} no tiene formato 'lib:name'.",
            hint=(
                "Formato 'Librería:Huella', p. ej. 'Resistor_SMD:R_0805_2012Metric'. "
                "No se valida existencia en librerías del sistema (KiCad lo marcará al asignar)."
            ),
        )


def _list_project_sheets(root: Path) -> list[Path]:
    """Hojas de DISEÑO del proyecto (root + hojas hijas), excluyendo la paleta.

    ``paleta.kicad_sch`` es un archivo separado de plantillas (D-12.3), NO
    parte de la jerarquía de diseño: sus refs de template no deben contar como
    colisiones ni aparecer en los hints de "hojas disponibles".
    """
    return sorted(p.resolve() for p in root.glob("*.kicad_sch") if p.name != _PALETTE_FILENAME)


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


_PALETTE_FILENAME = "paleta.kicad_sch"


def _resolve_source(source: str | None, root: Path, sheet_path: Path) -> Path:
    """Resuelve la hoja-fuente del template (D-12.3).

    Prioridad: ``source`` explícito (relativo al proyecto, regla 4) >
    ``paleta.kicad_sch`` en la raíz si existe > la hoja destino (clone
    intra-archivo, comportamiento histórico cuando no hay paleta). Devolver
    ``sheet_path`` señaliza el camino intra-archivo al llamador.
    """
    if source is not None:
        source_path = canonicalize_within_project_root(source, root)
        if source_path.suffix != ".kicad_sch":
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message=f"source debe ser un .kicad_sch (recibido: {source_path.name}).",
                hint="Pasá el nombre relativo, p. ej. 'paleta.kicad_sch'.",
            )
        if not source_path.is_file():
            raise KicadMcpError(
                code=ErrorCode.PROJECT_NOT_FOUND,
                message=f"La paleta/fuente {source_path.name} no existe en el proyecto.",
                hint="Creá la paleta o pasá el nombre correcto (ver docs/guia-paleta.md).",
            )
        return source_path
    palette = (root / _PALETTE_FILENAME).resolve()
    if palette.is_file():
        return palette
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


# --- clone cross-file desde una paleta (D-12.3, spike sesión 12) --------------
#
# kicad-skip bloquea el clone entre archivos vía sus wrappers de colección
# (``symbol.new_from_list``/``lib_symbols.raw`` levantan "Unknown element"). El
# spike de la sesión 12 verificó que sí funciona a nivel del árbol S-expr crudo
# (``sch.tree``): se copia la definición ``(symbol "LIB:ID" ...)`` de la paleta
# a ``lib_symbols`` del destino (dedup si ya está) y se anexa una instancia
# ``(symbol (lib_id ...))`` con ref/uuid/posición nuevos. El netlist reconoce
# el símbolo clonado.


def _sexp_head(node: Any) -> str | None:
    """Cabeza de un nodo S-expr (``str`` del primer átomo) o None si no es lista."""
    if isinstance(node, list) and node:
        return str(node[0])
    return None


def _find_sexp_child(tree: Any, head: str) -> Any:
    """Primer sub-nodo ``(head ...)`` dentro de ``tree`` (o None)."""
    if not isinstance(tree, list):
        return None
    for child in tree:
        if _sexp_head(child) == head:
            return child
    return None


def _find_lib_def(lib_node: Any, lib_id: str) -> Any:
    """Definición ``(symbol "LIB:ID" ...)`` dentro de ``lib_symbols`` (o None)."""
    if lib_node is None:
        return None
    for child in lib_node[1:]:
        if _sexp_head(child) == "symbol" and len(child) > 1 and str(child[1]) == lib_id:
            return child
    return None


def _find_instance_by_libid(root: Any, lib_id: str) -> Any:
    """Primera instancia ``(symbol (lib_id "LIB:ID") ...)`` en el nivel raíz (o None)."""
    for child in root:
        if _sexp_head(child) == "symbol":
            lid = _find_sexp_child(child, "lib_id")
            if lid is not None and len(lid) > 1 and str(lid[1]) == lib_id:
                return child
    return None


def _regen_uuids(node: Any) -> None:
    """Reasigna todos los ``(uuid ...)`` del subárbol a uuid4 nuevos (evita colisión)."""
    import uuid as _uuid

    from sexpdata import Symbol  # type: ignore[import-untyped]

    if not isinstance(node, list):
        return
    if _sexp_head(node) == "uuid" and len(node) >= 2:
        node[1] = Symbol(str(_uuid.uuid4()))
        return
    for child in node:
        _regen_uuids(child)


def _set_instance_at(inst: Any, x_mm: float, y_mm: float) -> None:
    """Fija ``(at x y rot)`` de la instancia preservando la rotación del template."""
    at = _find_sexp_child(inst, "at")
    if at is None:
        return
    rot = at[3] if len(at) >= 4 else 0
    at[1] = float(x_mm)
    at[2] = float(y_mm)
    if len(at) >= 4:
        at[3] = rot


def _set_instance_ref(inst: Any, ref: str) -> None:
    """Reescribe la Reference: propiedad + el bloque ``(instances ... (reference ...))``.

    KiCad usa la reference del bloque ``instances`` para netlist/anotación, así
    que ambas deben quedar en ``ref`` (si no, el clon saldría con el ref del
    template de la paleta).
    """
    for child in inst:
        if _sexp_head(child) == "property" and len(child) >= 3 and str(child[1]) == "Reference":
            child[2] = ref
    instances = _find_sexp_child(inst, "instances")
    if instances is not None:
        for project in instances[1:]:
            if _sexp_head(project) == "project":
                for path in project[1:]:
                    if _sexp_head(path) == "path":
                        reference = _find_sexp_child(path, "reference")
                        if reference is not None and len(reference) >= 2:
                            reference[1] = ref


def _add_symbol_cross_file(
    source_path: Path,
    target_path: Path,
    lib_id: str,
    ref: str,
    x_mm: float,
    y_mm: float,
) -> dict[str, Any]:
    """Clona el símbolo ``lib_id`` DESDE ``source_path`` HACIA ``target_path`` (D-12.3).

    Copia la definición de librería (dedup si el destino ya la tiene) y anexa
    una instancia con ref/uuid/posición nuevos. Devuelve ``value`` + ``pin_ids``
    para derivar el post-estado (igual que el clone intra-archivo).
    """
    import copy

    from skip import Schematic

    ssch = Schematic(str(source_path))
    proot = ssch.tree
    slib = _find_sexp_child(proot, "lib_symbols")
    lib_def = _find_lib_def(slib, lib_id)
    template_inst = _find_instance_by_libid(proot, lib_id)
    if lib_def is None or template_inst is None:
        seen = {
            str(child[1])
            for child in (slib[1:] if slib else [])
            if _sexp_head(child) == "symbol" and len(child) > 1
        }
        hint_list = ", ".join(sorted(seen)[:5]) if seen else "paleta sin símbolos"
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"lib_id {lib_id!r} no está instanciado en {source_path.name}.",
            hint=f"lib_ids en la paleta: {hint_list}",
        )

    tsch = Schematic(str(target_path))
    troot = tsch.tree
    tlib = _find_sexp_child(troot, "lib_symbols")
    if tlib is None:
        # Destino sin lib_symbols: crear el nodo mínimo.
        from sexpdata import Symbol

        tlib = [Symbol("lib_symbols")]
        troot.append(tlib)
    if _find_lib_def(tlib, lib_id) is None:
        tlib.append(copy.deepcopy(lib_def))

    new_inst = copy.deepcopy(template_inst)
    _set_instance_at(new_inst, x_mm, y_mm)
    _set_instance_ref(new_inst, ref)
    _regen_uuids(new_inst)
    troot.append(new_inst)
    tsch.overwrite = True
    tsch.write(str(target_path))

    template_value = _template_value(template_inst_wrapper(ssch, lib_id))
    reopened = Schematic(str(target_path))
    pin_ids = _pin_ids_of_lib_id(reopened, lib_id)
    return {"value": template_value, "pin_ids": pin_ids}


def template_inst_wrapper(sch: Any, lib_id: str) -> Any:
    """Localiza el símbolo-wrapper de kicad-skip con ``lib_id`` (para leer Value)."""
    return _find_template(sch, lib_id)


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


def _find_symbol_by_ref(sch: Any, ref: str) -> Any:
    """Localiza el ``(symbol ...)`` instanciado cuya Reference sea ``ref`` (o None)."""
    for sym in sch.symbol:
        try:
            if str(sym.Reference.value) == ref:
                return sym
        except AttributeError:
            continue
    return None


def _get_property(sym: Any, name: str) -> Any:
    """Devuelve el elemento ``(property "<name>" ...)`` del símbolo, o None.

    kicad-skip expone el atajo ``sym.Value``/``sym.Reference`` pero devuelve
    ``None`` cuando el valor es vacío (caso típico de ``Footprint`` recién
    plantillado). Iterar la ``PropertyCollection`` es la vía robusta: cada
    entrada tiene ``.name`` y ``.value`` fiables sin importar el contenido.
    """
    for prop in sym.property:
        if str(prop.name) == name:
            return prop
    return None


def _set_symbol_property(sheet_path: Path, ref: str, prop_name: str, new_value: str) -> str:
    """Escribe ``prop_name`` = ``new_value`` en el símbolo ``ref``. Devuelve el valor viejo.

    Precondición: ``ref`` existe en el proyecto (validado por el llamador con
    ``_collect_all_refs``). Si el símbolo o la propiedad no aparecen al abrir la
    hoja es una race con edición externa → ``KICAD_CLI_FAILED`` (loud, no
    silencioso). El ``sch.write`` sobreescribe la hoja; el G1 backup ya se hizo.
    """
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    sym = _find_symbol_by_ref(sch, ref)
    if sym is None:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"El símbolo {ref} desapareció de {sheet_path.name} antes del write.",
            hint="Posible edición externa concurrente; re-sincronizá con get_world_context.",
        )
    prop = _get_property(sym, prop_name)
    if prop is None:
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"El símbolo {ref} no tiene la propiedad {prop_name}.",
            hint=f"El símbolo debe declarar '{prop_name}' en su definición de librería.",
        )
    old_value = str(prop.value)
    prop.value = new_value
    sch.write(str(sheet_path))
    return old_value


def _verify_property(sheet_path: Path, ref: str, prop_name: str, expected: str) -> dict[str, Any]:
    """Re-lee la hoja y confirma que ``prop_name`` quedó en ``expected`` (D-06.3)."""
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    sym = _find_symbol_by_ref(sch, ref)
    total = sum(1 for _ in sch.symbol)
    if sym is None:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"Verificación de efecto: no se encontró {ref} tras write.",
            hint="El archivo se escribió pero el símbolo no aparece; posible race.",
        )
    prop = _get_property(sym, prop_name)
    live = str(prop.value) if prop is not None else None
    if live != expected:
        raise KicadMcpError(
            code=ErrorCode.KICAD_CLI_FAILED,
            message=f"Verificación de efecto: {prop_name} leído {live!r} != {expected!r}.",
            hint="El write persistió otro valor — bug interno.",
        )
    return {"total": total, "old_hidden": False, prop_name: live}


def _parse_pin_ref(spec: str) -> tuple[str, str]:
    """``"U1.5"`` → ``("U1", "5")``. Levanta ``INVALID_PARAMS`` si no matchea."""
    ref, sep, pin = spec.partition(".")
    if not sep or not ref or not pin:
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message=f"Formato de pin inválido: {spec!r}.",
            hint='Usá "REF.PIN", p. ej. "U1.5".',
        )
    return ref, pin


def _validate_net_name(net_name: str) -> None:
    """Valida ``net_name`` para ``connect_pins`` (regla 6 + no vacío)."""
    if not net_name.strip():
        raise KicadMcpError(
            code=ErrorCode.INVALID_PARAMS,
            message="net_name no puede estar vacío.",
            hint="Elegí un nombre de net significativo, p. ej. 'SDA', 'VCC_3V3'.",
        )
    _validate_field_text(net_name, "net_name")


def _pin_locations_on_sheet(
    sheet_path: Path, endpoints: list[tuple[str, str]]
) -> list[tuple[float, float]]:
    """Posición ABSOLUTA de cada ``(ref, pin_number)`` en la hoja (spike D-12.2).

    kicad-skip expone ``SymbolPin.location`` = ``AtValue(x, y, rot)`` ya
    resuelta (origen + offset + rotación) — no calculamos geometría acá. Pin
    inexistente → ``INVALID_PARAMS`` con los números disponibles del símbolo.
    """
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    locs: list[tuple[float, float]] = []
    for ref, pin_number in endpoints:
        sym = _find_symbol_by_ref(sch, ref)
        if sym is None:
            raise KicadMcpError(
                code=ErrorCode.COMPONENT_NOT_FOUND,
                message=f"El símbolo {ref} no está en {sheet_path.name}.",
                hint="Verificá el ref con get_world_context.",
            )
        found = None
        available: list[str] = []
        for pin in sym.pin:
            num = str(pin.number)
            available.append(num)
            if num == pin_number:
                found = pin
        if found is None:
            raise KicadMcpError(
                code=ErrorCode.INVALID_PARAMS,
                message=f"El pin {pin_number!r} no existe en {ref}.",
                hint=f"Pines de {ref}: {', '.join(sorted(set(available))[:12]) or 'sin pines'}.",
            )
        at = found.location.value
        locs.append((float(at[0]), float(at[1])))
    return locs


def _place_labels_on_sheet(
    sheet_path: Path, net_name: str, locations: list[tuple[float, float]]
) -> None:
    """Coloca un label local ``net_name`` en cada posición y escribe la hoja.

    D-12.2: dos labels locales con el mismo nombre en las posiciones de los
    pines los netean juntos (práctica estándar de KiCad, verificada por
    netlist en el spike). El G1 backup ya lo hizo el llamador.
    """
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    for x_mm, y_mm in locations:
        label = sch.label.new()
        label.value = net_name
        label.at.value = [x_mm, y_mm, 0]
    sch.write(str(sheet_path))


def _verify_labels(
    sheet_path: Path, net_name: str, locations: list[tuple[float, float]]
) -> dict[str, Any]:
    """Re-lee la hoja y confirma un label ``net_name`` en cada posición (D-06.3)."""
    from skip import Schematic

    sch = Schematic(str(sheet_path))
    present = [
        (float(lbl.at.value[0]), float(lbl.at.value[1]))
        for lbl in sch.label
        if str(lbl.value) == net_name
    ]
    for x_mm, y_mm in locations:
        if not any(abs(px - x_mm) < 1e-3 and abs(py - y_mm) < 1e-3 for px, py in present):
            raise KicadMcpError(
                code=ErrorCode.KICAD_CLI_FAILED,
                message=f"Verificación de efecto: falta el label {net_name} en ({x_mm}, {y_mm}).",
                hint="El write no persistió el label esperado — bug interno.",
            )
    return {"labels": len(present)}


def _derive_post_state_connect(
    pre_state: NormalizedState, endpoints: list[tuple[str, str]], net_name: str
) -> NormalizedState:
    """Post-estado = pre con la ``net`` de los pines conectados puesta en ``net_name``.

    Derivación local (patrón add_symbol): el label asigna el net a ambos pines.
    Caveat (spike D-12.2): si un pin ya cargaba un label global/jerárquico, el
    netlist real conserva ese nombre (prioridad global); el snapshot derivado
    puede diferir en ese borde. El netlist es la verdad; esto es una vista.
    """
    targets = set(endpoints)
    components: list[Component] = []
    for c in pre_state.components:
        if not any((c.ref, pin.p) in targets for pin in c.pins):
            components.append(c)
            continue
        new_pins = tuple(
            Pin(p=pin.p, name=pin.name, net=net_name) if (c.ref, pin.p) in targets else pin
            for pin in c.pins
        )
        components.append(
            Component(ref=c.ref, value=c.value, lib=c.lib, x=c.x, y=c.y, pins=new_pins)
        )
    return NormalizedState(kind=pre_state.kind, snap=0, components=tuple(components))


def _derive_post_state_set_value(
    pre_state: NormalizedState, ref: str, value: str
) -> NormalizedState:
    """Post-estado = pre con el ``value`` del Component ``ref`` reemplazado.

    ``set_value`` no altera conectividad ni posición: sólo el campo ``value``.
    Derivar localmente evita re-correr el netlist (patrón add_symbol). El
    ``snap`` se emite 0; el llamador lo sobrescribe con el del store.
    """
    components = tuple(
        Component(ref=c.ref, value=value, lib=c.lib, x=c.x, y=c.y, pins=c.pins)
        if c.ref == ref
        else c
        for c in pre_state.components
    )
    return NormalizedState(kind=pre_state.kind, snap=0, components=components)


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
        description=(
            "Clona un símbolo (de la hoja, o de una paleta con source) y lo coloca con nueva ref"
        ),
    )
    def add_symbol(
        sheet: str,
        lib_id: str,
        ref: str,
        x_mm: float,
        y_mm: float,
        base_snap: int | None = None,
        source: str | None = None,
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
                "source": source,
            }
            # Regla 6: sanitizar TODO string que vaya al archivo.
            try:
                _validate_ref(ref)
            except KicadMcpError as err:
                _audit_error(root, "add_symbol", params_for_audit, err.code)
                raise

            sheet_path = _load_target_sheet(sheet, root)
            # D-12.3: fuente del template. source explícito > paleta.kicad_sch
            # en la raíz > la propia hoja (clone intra-archivo, comportamiento
            # histórico si no hay paleta). El clone cross-file usa el árbol
            # S-expr crudo (spike sesión 12).
            try:
                source_path = _resolve_source(source, root, sheet_path)
            except KicadMcpError as err:
                _audit_error(root, "add_symbol", params_for_audit, err.code)
                raise
            cross_file = source_path != sheet_path
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
            # falseable — no ensuciamos backups por un typo del agente). En
            # modo cross-file el template vive en la paleta, no en la hoja.
            try:
                if cross_file:
                    _find_template(Schematic(str(source_path)), lib_id)
                else:
                    _find_template(probe, lib_id)
            except KicadMcpError as err:
                _audit_error(root, "add_symbol", params_for_audit, err.code)
                raise

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
            if cross_file:
                template_info = _add_symbol_cross_file(
                    source_path, sheet_path, lib_id, ref, x_mm, y_mm
                )
            else:
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

    def _set_property_core(
        tool_name: str,
        prop_name: str,
        audit_key: str,
        ref: str,
        new_value: str,
        base_snap: int | None,
        derive: Any,
    ) -> dict[str, Any]:
        """Núcleo compartido de ``set_value`` / ``set_footprint`` (D-12.1).

        Localiza la hoja del ``ref`` (refs son únicos por proyecto), valida
        existencia, dispara G1, escribe la propiedad, verifica el efecto
        (D-06.3) y registra un snapshot de DISCO derivado con mtimes frescos
        (D-06.2 / D-08.5 #4). Devuelve datos para el confirm + log del tool.
        """
        root = _project_root()
        if base_snap is not None:
            validate_base_snap(get_default_store(), base_snap, _resolve_root_schematic())

        params_for_audit = {"ref": ref, audit_key: new_value}
        all_refs = _collect_all_refs(root)
        if ref not in all_refs:
            _audit_error(root, tool_name, params_for_audit, ErrorCode.COMPONENT_NOT_FOUND)
            similars = difflib.get_close_matches(ref, list(all_refs), n=3, cutoff=0.5)
            hint = "refs similares: " + ", ".join(similars) if similars else "sin sugerencias"
            raise KicadMcpError(
                code=ErrorCode.COMPONENT_NOT_FOUND,
                message=f"Ref {ref!r} no existe en el proyecto.",
                hint=hint,
            )
        sheet_path = all_refs[ref]

        # Pre-estado del proyecto ANTES de mutar (base de la derivación local;
        # mismo motivo que add_symbol: evita re-correr el netlist).
        root_sch = _resolve_root_schematic()
        pre_state = build_state_cached(root_sch, snap=0)[0]

        backup_info = ensure_session_backup(root)  # Gate G1
        old_value = _set_symbol_property(sheet_path, ref, prop_name, new_value)
        effect = _verify_property(sheet_path, ref, prop_name, new_value)

        new_state = derive(pre_state)
        fresh_mtimes = collect_project_mtimes(root_sch)
        snap_id = get_default_store().register(new_state, fresh_mtimes)

        audit_record(
            root,
            tool=tool_name,
            params={**params_for_audit, "base_snap": base_snap},
            result={
                "snap": snap_id,
                "backup": backup_info.get("backup"),
                "sheet_total": effect["total"],
                "old": old_value,
            },
        )
        return {
            "old_value": old_value,
            "sheet_path": sheet_path,
            "snap_id": snap_id,
            "backup_info": backup_info,
            "effect": effect,
        }

    @mcp.tool(
        name="set_value",
        description="Cambia el Value de un símbolo existente (p. ej. R1 -> 22k)",
    )
    def set_value(ref: str, value: str, base_snap: int | None = None) -> str:
        with tool_call_timer() as timer:
            try:
                _validate_value(value)
            except KicadMcpError as err:
                _audit_error(_project_root(), "set_value", {"ref": ref, "value": value}, err.code)
                raise
            out = _set_property_core(
                "set_value",
                "Value",
                "value",
                ref,
                value,
                base_snap,
                lambda pre: _derive_post_state_set_value(pre, ref, value),
            )
            sheet_path = out["sheet_path"]
            snap_id = out["snap_id"]
            confirmation = (
                f"OK set_value {ref} {out['old_value']!r}->{value!r}"
                f" in {sheet_path.name} [snap:{snap_id}]"
            )
        log_tool_call(
            tool_name="set_value",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={
                "ref": ref,
                "sheet": sheet_path.name,
                "base_snap": base_snap,
                "backup_already_done": out["backup_info"].get("already_done"),
                "sheet_total": out["effect"]["total"],
            },
        )
        return confirmation

    @mcp.tool(
        name="set_footprint",
        description="Asigna el Footprint (lib:name) de un símbolo existente; no valida existencia",
    )
    def set_footprint(ref: str, footprint_id: str, base_snap: int | None = None) -> str:
        with tool_call_timer() as timer:
            try:
                _validate_footprint_id(footprint_id)
            except KicadMcpError as err:
                _audit_error(
                    _project_root(),
                    "set_footprint",
                    {"ref": ref, "footprint": footprint_id},
                    err.code,
                )
                raise
            # El Footprint NO vive en NormalizedState (Component no lo modela):
            # el post-estado es idéntico al pre en términos de estado normalizado,
            # pero registramos un snapshot de disco fresco para encadenar base_snap
            # y mantener activa la detección de edición externa (patrón add_track).
            out = _set_property_core(
                "set_footprint",
                "Footprint",
                "footprint",
                ref,
                footprint_id,
                base_snap,
                lambda pre: NormalizedState(kind=pre.kind, snap=0, components=pre.components),
            )
            sheet_path = out["sheet_path"]
            snap_id = out["snap_id"]
            confirmation = (
                f"OK set_footprint {ref} ->{footprint_id} in {sheet_path.name} [snap:{snap_id}]"
            )
        log_tool_call(
            tool_name="set_footprint",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={
                "ref": ref,
                "sheet": sheet_path.name,
                "base_snap": base_snap,
                "backup_already_done": out["backup_info"].get("already_done"),
                "sheet_total": out["effect"]["total"],
            },
        )
        return confirmation

    @mcp.tool(
        name="connect_pins",
        description="Conecta dos pines (REF.PIN) por labels locales del mismo net_name",
    )
    def connect_pins(
        pin_a: str,
        pin_b: str,
        net_name: str,
        base_snap: int | None = None,
    ) -> str:
        # D-12.2: nea REF.PIN ↔ REF.PIN colocando labels locales homónimos en
        # las posiciones absolutas de los pines (spike verificado por netlist).
        # Labels locales tienen scope de HOJA → ambos pines deben vivir en la
        # misma hoja. net_name obligatorio (el agente elige nombres con sentido).
        with tool_call_timer() as timer:
            root = _project_root()
            params_for_audit = {"pin_a": pin_a, "pin_b": pin_b, "net_name": net_name}
            try:
                _validate_net_name(net_name)
                ref_a, num_a = _parse_pin_ref(pin_a)
                ref_b, num_b = _parse_pin_ref(pin_b)
            except KicadMcpError as err:
                _audit_error(root, "connect_pins", params_for_audit, err.code)
                raise
            if (ref_a, num_a) == (ref_b, num_b):
                _audit_error(root, "connect_pins", params_for_audit, ErrorCode.INVALID_PARAMS)
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message="pin_a y pin_b son el mismo pin.",
                    hint="Conectá dos pines distintos.",
                )
            if base_snap is not None:
                validate_base_snap(get_default_store(), base_snap, _resolve_root_schematic())

            all_refs = _collect_all_refs(root)
            for ref in (ref_a, ref_b):
                if ref not in all_refs:
                    _audit_error(
                        root, "connect_pins", params_for_audit, ErrorCode.COMPONENT_NOT_FOUND
                    )
                    similars = difflib.get_close_matches(ref, list(all_refs), n=3, cutoff=0.5)
                    hint = (
                        "refs similares: " + ", ".join(similars) if similars else "sin sugerencias"
                    )
                    raise KicadMcpError(
                        code=ErrorCode.COMPONENT_NOT_FOUND,
                        message=f"Ref {ref!r} no existe en el proyecto.",
                        hint=hint,
                    )
            sheet_a, sheet_b = all_refs[ref_a], all_refs[ref_b]
            if sheet_a != sheet_b:
                _audit_error(root, "connect_pins", params_for_audit, ErrorCode.INVALID_PARAMS)
                raise KicadMcpError(
                    code=ErrorCode.INVALID_PARAMS,
                    message=(
                        f"{ref_a} y {ref_b} están en hojas distintas "
                        f"({sheet_a.name}, {sheet_b.name})."
                    ),
                    hint=(
                        "connect_pins usa labels LOCALES (scope de hoja); ambos pines deben "
                        "estar en la misma hoja. Labels globales/jerárquicos: fuera de scope."
                    ),
                )
            sheet_path = sheet_a
            endpoints = [(ref_a, num_a), (ref_b, num_b)]
            # Validar pines (existencia + posición) ANTES del G1 — barato y
            # trivialmente falseable (typo del agente), no ensuciamos backups.
            locations = _pin_locations_on_sheet(sheet_path, endpoints)

            root_sch = _resolve_root_schematic()
            pre_state = build_state_cached(root_sch, snap=0)[0]

            backup_info = ensure_session_backup(root)  # Gate G1
            _place_labels_on_sheet(sheet_path, net_name, locations)
            effect = _verify_labels(sheet_path, net_name, locations)

            new_state = _derive_post_state_connect(pre_state, endpoints, net_name)
            fresh_mtimes = collect_project_mtimes(root_sch)
            snap_id = get_default_store().register(new_state, fresh_mtimes)

            audit_record(
                root,
                tool="connect_pins",
                params={**params_for_audit, "base_snap": base_snap},
                result={
                    "snap": snap_id,
                    "backup": backup_info.get("backup"),
                    "labels": effect["labels"],
                },
            )
            confirmation = (
                f"OK connect_pins {pin_a}<->{pin_b} net={net_name}"
                f" in {sheet_path.name} [snap:{snap_id}]"
            )
        log_tool_call(
            tool_name="connect_pins",
            latency_ms=timer["latency_ms"],
            tokens_est=estimate_tokens(confirmation),
            snap_id=snap_id,
            extra={
                "net_name": net_name,
                "sheet": sheet_path.name,
                "base_snap": base_snap,
                "backup_already_done": backup_info.get("already_done"),
            },
        )
        return confirmation
