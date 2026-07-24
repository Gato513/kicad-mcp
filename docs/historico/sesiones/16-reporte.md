# Sesión 16 — P1: Visibilidad del cobre (`get_tracks` + cirugía por ID)

**Rama:** `sesion/16-get-tracks` · **Fecha:** 2026-07-18 · KiCad 10.0.4 (cli
vivo; IPC/GUI **no** disponible durante la sesión, ver §Desviaciones).

## Resumen

Se implementó el P1 de la hoja de ruta v3: `get_tracks` (tool nueva de solo
lectura, cobre con id estable), borrado dirigido por `id`, `add_track` con
endpoints mixtos pad+coordenada, y validación de colisiones de `add_track`
contra pads de otro net (roundrect/circle/oval modelados exactos con una sola
fórmula). De paso se encontró y corrigió un bug estructural más grande que el
reportado: **`data` nunca llegaba al agente en NINGÚN error**, no sólo en la
desambiguación de `delete_track` — el SDK `mcp` vendorizado colapsa toda
excepción a `str(e)` antes de responder, y `KicadMcpError.to_dict()` (que sí
serializa `data`) no se invocaba en ningún punto real del server.

`unit+golden` (214 passed, 1 skipped; +18 nuevos en `test_pcb_session16.py`)
e `integration` (kicad-cli, 22 tests) verdes. `ruff`/`ruff format`/
`mypy --strict` limpios. `integration_gui` (7 tests nuevos) escritos y
colectan bien, pero **no se ejecutaron**: no había una instancia de KiCad
corriendo con el proyecto de prueba abierto durante la sesión (`health()`
reportó `KICAD_NOT_RUNNING`). Ver §Desviaciones.

## Fase 0

`verificar_entorno.py`: 14 OK · 2 WARN · 0 FAIL. Los WARN preexistentes no
bloquean el MVP: `KICAD_MCP_FREEROUTING_JAR` no seteada (route_board está
fuera de alcance de esta sesión) y `npx` ausente (Inspector interactivo; los
tests con cliente MCP in-process no lo requieren). El socket IPC de KiCad
(`/tmp/kicad/api.sock`) figura presente, pero al consultar `health()` durante
el trabajo la respuesta fue `ipc_responde: "error"` / `status: "missing"` —
no había un KiCad GUI vivo respondiendo, sólo el archivo del socket.

## 1. Tools nuevas/modificadas — firmas finales

### `get_tracks` (nueva, solo lectura)

```python
get_tracks(net: str | None = None, bbox: list[float] | None = None,
           layer: str | None = None, max_tokens: int | None = None) -> str
```

- Al menos un filtro obligatorio; sin ninguno → `INVALID_PARAMS`.
- `bbox=[min_x,min_y,max_x,max_y]` (mm); un segmento aparece si **cruza** el
  bbox (clipping Liang-Barsky), no sólo si un endpoint cae adentro — pedido
  explícito del test (b).
- `layer` filtra por capa de cobre; una via pasante cuenta para cualquier capa
  de su span (`via_layers`).
- Segmento: `id, net, layer, width, start=[x,y], end=[x,y]` (+ punto medio si
  es arco). Vía: `id, net, at=[x,y], size, drill, layers=[F.Cu,B.Cu]`.
- Presupuesto de tokens: mismo default D4 (800 tok) que `get_world_context`;
  `CONTEXT_BUDGET_IMPOSSIBLE` si no entra, con el mínimo estimado en el hint.
  **Simplificación deliberada** frente al TOON completo: no hay cascada de
  niveles de degradación — el hint sugiere achicar `net`/`bbox`/`layer`, que
  es la palanca natural de esta tool (a diferencia del contexto de mundo
  completo, `get_tracks` es inherentemente recortable por el llamador). Ver
  §Desviaciones.
- No es TOON (F1 intacto): formato compacto propio (`TRACKS|v1|...`), tool
  separada.
- Sujeta al aviso `live_stale` (D-14.1) en modo warn-only, como
  `get_world_context` — no bloquea, prepende `[AVISO]`.

### `delete_track` / `delete_via` — nueva firma por `id`

```python
delete_track(id: str | None = None, net: str | None = None,
             near_x_mm: float | None = None, near_y_mm: float | None = None,
             base_snap: int | None = None) -> str
delete_via(id: str | None = None, net: str | None = None,
           x_mm: float | None = None, y_mm: float | None = None,
           base_snap: int | None = None) -> str
```

- `id` (de `get_tracks`) y `net`+coordenadas son **mutuamente excluyentes**
  (`INVALID_PARAMS` si se mezclan o si falta ambos).
- La firma por coordenadas se conserva íntegra (compatibilidad).
- **Bug corregido:** el error de desambiguación por coordenadas ahora sí
  entrega `data.candidates` (con `id` en cada candidato) — ver §2.

### `add_track` — mismos parámetros, exclusión relajada por endpoint

```python
add_track(net: str, start_x_mm=None, start_y_mm=None, end_x_mm=None,
          end_y_mm=None, from_pad=None, to_pad=None, width_mm=0.25,
          layer="F.Cu", base_snap=None) -> str
```

Firma **sin cambios** (cumple "mantener las firmas actuales intactas"). Lo
que cambió es la validación: antes la exclusión pad↔coordenadas era GLOBAL
(o todo pads, o todo coordenadas); ahora es **por endpoint** — `start` elige
independientemente de `end`. `add_track(net=.., from_pad="U1.1",
end_x_mm=.., end_y_mm=..)` funciona; mezclar pad y coordenadas en el MISMO
extremo sigue rechazado.

Además, `add_track` gana una validación nueva: rechaza el track si invade un
pad de **otro net** (misma capa o pasante), modelando roundrect exacto — ver
§3.

## 2. Errores nuevos / cambios de catálogo

| Código | Cuándo | Hint |
|---|---|---|
| `TRACK_ID_STALE` (nuevo) | `id` de `get_tracks` no resuelve (board mutado/recargado) o apunta a otro `kind`; también si el ítem se borró por otra vía entre el `get_tracks` y el `delete_*` | "re-listá con get_tracks y usá un id vigente" |

Sin renombrar códigos existentes (F3 intacta). Cambios de `data` (no son
códigos nuevos, son payloads nuevos en códigos existentes):

- `INVALID_PARAMS` de `delete_track`/`delete_via` (ambigüedad) →
  `data.candidates[].id` agregado (antes sólo `kind/net/pos|start,end/layer`,
  y ni siquiera llegaba — ver el bug de §0).
- `INVALID_PARAMS` de `add_track` (colisión) → `data.pad_net`,
  `data.pad_pos`, `data.clearance_mm` (nuevo emisor).

**El fix de fondo** vive en `src/kicad_mcp/errors.py`
(`KicadMcpError.__init__`): `data` ahora se embebe como JSON al final del
mensaje de la excepción (única cosa que de verdad cruza la frontera MCP hoy,
confirmado leyendo el SDK vendorizado: `mcp/server/lowlevel/server.py` hace
`except Exception as e: return self._make_error_result(str(e))`). Beneficia
a **todo** emisor de `data` preexistente (`SNAPSHOT_STALE`,
`KICAD_CLI_FAILED` con `ipc_status`, los de `route_board`) sin tocar el SDK
(F5 intacta) ni sus propios códigos.

## 3. Contrato de estabilidad de IDs

Documentado en `docs/specs/tool-catalog.md` (sección `get_tracks`, prosa
"Contrato de estabilidad del `id`") — resumen:

- `id` es el **KIID nativo de KiCad** (`str(item.id.value)` vía kipy), no un
  hash calculado por el server.
- Determinista mientras el board no cambie.
- **Se invalida tras cualquier mutación de cobre** (`add_track`, `add_via`,
  `delete_track`, `delete_via`, `route_board`) **o recarga del board**.
- Un `id` vencido → `TRACK_ID_STALE`; el agente debe re-listar con
  `get_tracks` antes de reintentar.

## 4. Resultado de los tests E2E

Los 7 tests pedidos por el prompt existen; **a–d y g corren y pasan** (unit,
fake bridge); **e–f existen como `integration_gui`** pero no se ejecutaron
esta sesión (sin KiCad vivo, ver §Desviaciones).

| # | Escenario | Archivo | Estado |
|---|---|---|---|
| a | `get_tracks(net="GND")` lista segmentos+vías con ids | `tests/test_pcb_session16.py::test_get_tracks_by_net_lists_segments_and_vias_with_ids` | **PASA** (unit) |
| b | `get_tracks(bbox=)` recorta correctamente (cruza→aparece, afuera→no) | `...::test_get_tracks_bbox_crops_crossing_segment` | **PASA** (unit) |
| c | Delete por id borra exactamente ese segmento | `...::test_delete_track_by_id_removes_exact_segment` | **PASA** (unit) |
| d | Desambiguación → candidates+ids → delete por id del candidato correcto | `...::test_delete_track_ambiguity_carries_candidates_with_ids` | **PASA** (unit) |
| e | `add_track(from_pad, to=[x,y])` crea el segmento; DRC no empeora | `tests/test_pcb_session16_gui.py::test_add_track_pad_to_point_does_not_worsen_drc` | Escrito, **no ejecutado** (`integration_gui`) |
| f | Escenario F-13: hueco visible → reparado con `add_track` pad→punto → DRC limpio, sin parsear el `.kicad_pcb` por fuera | `...::test_f13_scenario_gap_visible_and_repaired_without_external_parsing` | Escrito, **no ejecutado** (`integration_gui`) |
| g | `TRACK_ID_STALE`: mutar el board entre list y delete | `tests/test_pcb_session16.py::test_delete_track_id_stale_when_board_mutated` | **PASA** (unit) |

Cobertura adicional más allá de los 7 pedidos (18 tests unit en total en
`test_pcb_session16.py`, + 7 `integration_gui` en `test_pcb_session16_gui.py`):
filtro por `layer`, `CONTEXT_BUDGET_IMPOSSIBLE`, `NET_NOT_FOUND` de
`get_tracks`, id de otro `kind` → `TRACK_ID_STALE`, mezcla `id`+coordenadas
rechazada, endpoints mixtos en ambos sentidos (pad→punto y punto→pad), mezcla
en el MISMO endpoint sigue rechazada, colisión con pad de otro net
(rechazada), pad del mismo net (ignorado), pad en otra capa (ignorado), y el
caso específico de la fricción original: un track que sólo pasa por la cuña
recortada de un pad roundrect (dentro del cuadrado envolvente, fuera de la
forma real) **no** se rechaza falsamente — verificado con la fórmula SDF
exacta, no con un caso de humo.

Suites completas: `uv run pytest -m "not integration and not
integration_gui"` → 214 passed, 1 skipped. `uv run pytest -m integration` →
22 passed. `ruff check`/`ruff format --check`/`mypy --strict src/` limpios.

## 5. Desviaciones del prompt (con justificación)

1. **Tests `integration_gui` (e, f) no se ejecutaron.** El prompt exige el
   patrón "borrar→verificar→añadir ejecutable" como criterio de cierre, que
   por naturaleza necesita un board real y DRC real. No había KiCad GUI
   corriendo con el proyecto de prueba abierto en ningún momento de la sesión
   (verificado con `health()`: `KICAD_NOT_RUNNING`). Los 7 tests están
   escritos siguiendo el mismo patrón verificado de `test_pcb_session11_gui.py`
   (revert en `finally`, verificación contra `board.raw.get_tracks()`/
   `get_vias()` y contra DRC real), colectan sin error
   (`pytest --collect-only -m integration_gui` → 7), pero quedan pendientes
   de una corrida manual siguiendo `docs/pruebas-gui.md`. Reporto esto como
   limitación explícita, no como "hecho": no afirmo un resultado que no
   observé.

2. **`get_tracks` no reimplementa la cascada de degradación de niveles del
   encoder TOON.** El prompt pide "mismo mecanismo, mismo error
   `CONTEXT_BUDGET_*`". Implementé el mismo *error* (`CONTEXT_BUDGET_IMPOSSIBLE`
   con hint del mínimo estimado) pero no la cascada de niveles (colapsar nets
   de poder, omitir posiciones, etc.) porque esa cascada está diseñada para
   `NormalizedState` (footprints+pines) y no tiene un análogo natural en una
   lista de segmentos/vías. `get_tracks` es inherentemente recortable por el
   llamador (`net`/`bbox`/`layer`, a diferencia de "todo el mundo"), así que
   el hint dirige ahí en vez de degradar automáticamente. Documentado
   explícitamente en el catálogo como simplificación deliberada.

3. **Clearance de colisión de `add_track` es un piso fijo (0.2 mm), no la
   regla real de netclass.** El prompt autoriza explícitamente este fallback
   ("como mínimo, inflar el rectángulo con el clearance de la netclass y
   documentar la aproximación") si la vía completa resulta cara. Leer reglas
   de netclass reales requeriría plumbing IPC nuevo que no existe hoy en el
   bridge (no hay ningún método que lea `.kicad_pro`/netclasses). Lo que sí
   implementé completo y exacto es el modelado de forma del pad (roundrect/
   circle/oval vía una sola fórmula SDF), que es la parte que el prompt pedía
   con más énfasis ("costó 2 iteraciones DRC al agente") y es geométricamente
   exacta, no aproximada.

4. **La validación de colisiones no conoce la `ref` del pad ofensor**, sólo
   su net y posición (`data.pad_net`, `data.pad_pos`). `Board.get_pads()`
   (la llamada IPC usada, una sola pasada para todo el board) no expone un
   link directo al footprint padre en la superficie de kipy que encontré; el
   agente puede ubicar el pad con `get_component_detail`/`get_tracks` a
   partir de la posición. No bloquea el caso de uso (identifica el conflicto
   igual), pero es menos directo que idealmente.

## 6. Nota sobre el hallazgo del bug de `data`

El prompt pedía arreglar específicamente que `delete_track` prometiera
`data.candidates` sin entregarlo. Al rastrear la causa (`KicadMcpError.to_dict()`
nunca invocado en el camino real del server → SDK vendorizado colapsa
cualquier excepción a `str(e)`), quedó claro que el bug no era de
`delete_track`: **ningún** emisor de `data` en todo el server llegaba al
agente (`SNAPSHOT_STALE.data.base_snap`, `KICAD_CLI_FAILED.data.ipc_status`,
los ocho emisores de `route_board`). El fix en `errors.py` es de una función
y beneficia a todos por igual — se documentó como tal en el catálogo en vez
de limitarlo a `delete_track` para no dejar una media verdad en la
documentación.
