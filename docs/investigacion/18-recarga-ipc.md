# Investigación P3.0 — Recarga programática del PCB Editor vía IPC

**Sesión 18.** Objetivo: encontrar un mecanismo por el cual `route_board`
(que escribe el ruteo a **disco**, headless) pueda hacer que el PCB Editor
**vivo** de KiCad refleje ese ruteo sin intervención humana (File→Revert),
cumpliendo el gate D-V3.1: `get_tracks` post-`route_board` ve el cobre nuevo,
cero contactos humanos.

Entorno de la investigación: KiCad **10.0.4** corriendo con API IPC habilitada
(`/tmp/kicad/api.sock`), `kicad-python` (kipy) **0.7.1** instalado en el venv
del proyecto (`KICAD_API_VERSION = "10.0.1-0-g2db9e5a72b"`). F4 vigente: todo
lo documentado acá es específico de esta combinación de versiones — nada se
extrapola a KiCad 11.

## 1. Superficie enumerada

### `kipy.board.Board` (métodos públicos relevantes a estado del editor)

| Método | Proto enviado | Categoría |
|---|---|---|
| `save()` | `SaveDocument` | Escritura vivo→disco. **Ya usado** por `bridge.save_board` (`ipc.py:1394`). |
| `save_as(filename, overwrite, include_project)` | `SaveCopyOfDocument` | Copia a otra ruta. No aplica a este problema. |
| **`revert()`** | `RevertDocument` | *"Reverts the board to the last saved state"*. Candidato principal — ver §2. |
| `begin_commit()` / `push_commit(commit)` / `drop_commit(commit)` | `BeginCommit` / `EndCommit(action=CMA_COMMIT\|CMA_DROP)` | Transacciones de mutación agrupada del board vivo (para Opción #2, ver §3). |
| `create_items(items)` | `CreateItems` | Crea ítems (tracks/vias/footprints) directo en el board vivo, sin pasar por disco. |
| `get_items` / `get_items_by_id` / `get_items_by_net` / `get_items_by_netclass` | `GetItems` / `GetItemsById` | Lecturas — ya usadas extensivamente por el bridge (`list_net_copper`, etc.). |
| `get_title_block_info()` / `set_title_block_info(tb)` | `GetTitleBlockInfo` / `SetTitleBlockInfo` | Usado como sonda no destructiva en la verificación (§2). |
| `get_as_string()` / `get_selection_as_string()` | `SaveDocumentToString` | Serializa a texto S-expr sin tocar el archivo. No resuelve la recarga. |

No existe ningún método `Board.reload()`, `Board.sync()` ni `Board.refresh()`
en la superficie pública de kipy 0.7.1.

### `kipy.kicad.KiCad` (cliente de nivel aplicación)

| Método | Proto enviado | Nota |
|---|---|---|
| `get_board()` | `GetOpenDocuments(DOCTYPE_PCB)` + construye `Board` | Ya usado (`bridge.get_open_board`). Confirmado (§2.3): el `Board` handle devuelto **sigue siendo válido** tras un `revert()` posterior — no hace falta reobtenerlo, aunque el bridge lo hará de todos modos por higiene. |
| `run_action(action: str)` | `RunAction` | Docstring de kipy: **"WARNING: This is an unstable API... KiCad does not guarantee the stability of action names"**. Candidato descartado (Opción #3, §3). |
| `get_open_documents(doc_type)` | `GetOpenDocuments` | Ya usado (`bridge.has_open_pcb`). |
| `ping()` | — | Liveness, no aplica. |

### Nivel proto (sin wrapper público)

`kipy/proto/common/commands/editor_commands_pb2.py` define un mensaje
**`RefreshEditor`** (campo `frame: FrameType`) que **ningún método de
`Board` ni `KiCad` envuelve**. Usarlo exigiría construir el comando protobuf
crudo y enviarlo por `client.send(...)` directamente — API interna no
soportada por kipy, más frágil que `revert()` (que sí tiene wrapper oficial
mantenido). Se descarta como base de diseño; se documenta por completitud.

## 2. Verificación en vivo

Ejecutada contra el proyecto real abierto en la instancia de KiCad del
usuario (`despertador_inteligente`, `/tmp/gui-test-project/`, 24 footprints,
313 tracks, snap:2) — **con confirmación explícita del humano** de que no
había ediciones sin guardar, dado que `revert()` es potencialmente
destructivo de estado no persistido. Los tests fueron diseñados para no
escribir el `.kicad_pcb` real en ningún momento (usan sólo mutación IPC
in-memory sobre `comment9` del title block, un campo sin uso funcional).

### 2.1 ¿`revert()` descarta ediciones IPC no guardadas y re-lee disco?

```
comment9 original (disco/vivo):        ''
comment9 tras set_title_block_info():  'sesion18-verify-revert-DESCARTAR'  (vivo, sin guardar)
board.revert()
comment9 tras revert():                ''
RESULTADO: revert() RE-LEYÓ DISCO. Descartó la edición IPC no guardada.
```

**Confirmado.** `revert()` no es un simple "undo" del último comando: hace que
el estado vivo converja exactamente con el contenido *actual* del archivo en
disco, descartando cualquier cambio in-memory no persistido — sea ese cambio
una edición IPC no guardada (este test) o, por el mismo mecanismo, un
`os.replace` externo del archivo hecho por `route_board` (caso real; ver
razonamiento de equivalencia abajo).

**Por qué el resultado generaliza al caso real de `route_board`:** el
mecanismo de `revert()` no distingue el origen ni la magnitud del diff entre
el grafo en memoria y los bytes en disco — sencillamente descarta el primero
y re-parsea el segundo. Da igual si esos bytes cambiaron porque el usuario no
guardó una edición del title block (probado acá) o porque un subprocess
reemplazó el archivo completo con `os.replace` tras un ruteo (`route_board`,
`pcb.py:1406`). El caso real se confirma de punta a punta en la tarea P3.3
(E2E contra un `route_board` real), pero no hay razón mecánica para esperar
un comportamiento distinto, y esta prueba evita el riesgo de editar a mano el
S-expression del `.kicad_pcb` real del usuario.

### 2.2 ¿El handle `Board` sigue siendo válido después de `revert()`?

```
footprints antes:                          24   tracks antes: 313
footprints (MISMO handle post-revert):     24   -> handle SIGUE VÁLIDO
footprints (handle NUEVO post-revert):     24
footprints tras SEGUNDO revert() consecutivo: 24 -> idempotente OK
```

**Confirmado.** El objeto `Board` no queda invalidado tras `revert()` (el
`DocumentSpecifier` interno sigue apuntando al mismo documento abierto); no
es estrictamente necesario volver a llamar `kicad.get_board()`. El bridge lo
hará de todas formas por consistencia con el patrón `BoardHandle` existente
(evita asumir invariantes de kipy no documentados formalmente).

**`revert()` es idempotente**: llamarlo dos veces seguidas no produce error
ni cambia el resultado — cumple el requisito de idempotencia de
`reload_board_from_disk()` pedido en P3.1.

### 2.3 Estado final verificado

```
comment9 final (sin residuos del test): ''
footprints: 24   tracks: 313
```

Sin efectos colaterales sobre el proyecto real del usuario: nunca se escribió
el `.kicad_pcb`, y el estado vivo terminó idéntico al inicial.

## 3. Corrección de alcance de D-12.4

D-12.4 (sesión 12, `docs/guia-paleta.md:125`) concluyó que **"no hay recarga
automática en KiCad 10"**, citando que `Schematic.revert()` es
`versionadded 0.7.0` (mapea a KiCad 11) y que KiCad 10.0.4 responde
`no handler available` a peticiones sobre documentos de tipo **schematic**.

Esa conclusión es correcta para el **Schematic Editor** (su IPC es
efectivamente KiCad 11, F4 lo prohíbe) pero **nunca se extendía al PCB
Editor** — el propio `guia-paleta.md:133` ya lo señalaba de pasada ("El PCB
Editor sí tiene IPC (KiCad 10)") sin que nadie llegara a probar
`Board.revert()` específicamente. La sesión 12 fue un spike centrado en el
flujo sch→pcb (RF5/A5 del backlog), no en el problema post-`route_board`
(que nace recién en sesión 14). `Board.revert()` es un método distinto del
`Schematic.revert()` que descartó D-12.4, con su propio comando proto
(`RevertDocument` sobre un `DocumentSpecifier` de tipo `DOCTYPE_PCB`), y
kipy 0.7.1 lo expone sin marcarlo `versionadded 0.7.0` ni inestable.

**D-12.4 sigue vigente para el Schematic Editor.** Esta investigación no lo
revoca — lo acota: la recarga programática es infactible para `.kicad_sch`
en KiCad 10 (F4 sigue bloqueando IPC de esquemático), pero **sí es factible
para `.kicad_pcb`**, que es exactamente el caso que D-14.1/D-V3.1 necesitan
resolver.

## 4. Tres opciones ranqueadas

### Opción #1 (recomendada) — `Board.revert()` + tool `reload_board_from_disk`

Nuevo método de bridge que envuelve `board.raw.revert()`; nueva tool MCP que
lo expone; `route_board` la invoca automáticamente tras el `os.replace` a
disco.

- **Costo de implementación:** bajo. Un método de bridge (patrón idéntico a
  `save_board`, `ipc.py:1394`), una tool nueva, un punto de integración en
  `route_board`, un código de error nuevo (`RELOAD_FAILED`, adición — no
  rompe F3).
- **Robustez:** alta. `RevertDocument` es un comando estable y
  explícitamente documentado del proto (`editor_commands.proto`), con
  wrapper oficial mantenido por el equipo de kipy — no es la superficie
  "unstable" que kipy marca en `run_action`. Verificado empíricamente en vivo
  contra KiCad 10.0.4 (§2): re-lee disco, es idempotente, no invalida el
  handle.
- **Alcance:** primitiva general. Resuelve `route_board` y **cualquier
  mutación externa a disco futura** (p. ej. si algún día se edita el
  `.kicad_pcb` con otra herramienta externa mientras el editor está abierto).

### Opción #2 — Rutear directo contra el board vivo por IPC (sin pasar por disco)

Parsear el `.ses` que devuelve Freerouting y aplicar los tracks/vias
resultantes directamente al board vivo con `create_items` dentro de un
`begin_commit()`/`push_commit()`, eliminando el round-trip a disco por
completo (y por lo tanto la necesidad de recarga).

- **Costo de implementación:** alto. Reescribe el modelo mental actual de
  `route_board` (hoy: DSN→Freerouting→SES→reemplazo atómico de archivo);
  requiere un parser SES→protos de kipy (unidades, capas, tipos de track/vía,
  nets) que hoy no existe, y pierde la garantía de "reemplazo atómico de
  archivo" que da `os.replace` (si la escritura por IPC falla a mitad de
  camino, el board vivo puede quedar en un estado parcialmente ruteado sin
  un mecanismo de rollback tan simple como "no reemplazar el archivo").
- **Robustez:** `create_items`/`begin_commit` son APIs estables, pero el
  parser SES→kipy sería superficie de bug nueva y no verificada.
- **Alcance:** resuelve *sólo* `route_board`. No generaliza a otras
  mutaciones externas al proceso del agente.

### Opción #3 — `KiCad.run_action()` con una acción interna de revert

Invocar `kicad.run_action("pcbnew.RevertBoard")` (o el nombre de acción
interno equivalente) en vez de `Board.revert()`.

- **Costo de implementación:** bajo-medio (hay que descubrir/confirmar el
  nombre exacto de la acción, que no es API pública).
- **Robustez:** baja. kipy marca `run_action` explícitamente como API
  **inestable** ("KiCad does not guarantee the stability of action names") —
  viola el espíritu de F4 (no depender de superficie no garantizada entre
  versiones). Estrictamente peor que la Opción #1: si existe una acción
  interna de revert, con altísima probabilidad termina invocando el mismo
  comando `RevertDocument` que `Board.revert()` ya envuelve de forma
  estable y pública.
- **Alcance:** igual que #1, pero sobre una base más frágil.
- **Descartada** — no hay escenario en que #3 sea preferible a #1.

## 5. Decisión

El humano confirmó (2026-07-20, vía `AskUserQuestion` en la misma sesión) la
**Opción #1** tras revisar este reporte. Se procede a P3.1 con
`Board.revert()` como mecanismo de `reload_board_from_disk()`.

El fallback documentado en el prompt de sesión (ADR-0013,
batching/`flush_pending_reload`) **no aplica**: la verificación en vivo de
§2 confirmó que la Opción #1 funciona en KiCad 10.0.4 sin necesidad de caer
a un mecanismo degradado.
