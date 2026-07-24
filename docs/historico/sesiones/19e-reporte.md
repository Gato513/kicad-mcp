# Sesión 19e — Fix socket path resolution + investigación `get_world_context(kind=sch)`

**Rama:** `sesion/19e-socket-path-fix` (desde `master`, tras merge de 19+19d+19b)
· **Fecha:** 2026-07-22.

## Resumen

Blocker F-19b-09 cerrado: `IpcBridge` ya no depende de un symlink manual en
`/tmp/kicad/api.sock` para conectar con KiCad 10.0.4. Resolución en
cascada, existence-aware, con **8 tests nuevos** (6 de la cascada + 2 de
robustez R11) y **2 tests de sesión-04 reescritos** al nuevo contrato.
**Los 3 escenarios de verificación en vivo pasan**, incluyendo un bug real
(no cubierto por el prompt original) encontrado y corregido durante la
verificación: la resolución se congelaba en el constructor y no
sobrevivía a un reinicio de KiCad a mitad de la vida del server MCP — ver
§"Hallazgo en vivo" abajo.

19e.2 (F-19b-06) investigado y cerrado como **documentar + diferir a 20b**:
causa raíz confirmada, no es un bug de código sino una divergencia
sistemática y esperada entre dos fuentes de datos legítimas.

---

## 19e.1 — Fix `_resolve_kicad_socket()`

### Diagnóstico

`_DEFAULT_SOCKET_LINUX = "ipc:///tmp/kicad/api.sock"` (hardcodeado, sin PID)
nunca existe contra KiCad 10.0.4 real, que crea
`/tmp/kicad/api-<PID>.sock`. `health()` reportaba `KICAD_NOT_RUNNING` con
KiCad y el API server corriendo.

### Decisión de diseño (usuario, antes de implementar)

El prompt original proponía que un override explícito (env var
`KICAD_API_SOCKET` o arg del constructor) sólo se use si su path existe,
cayendo a la cascada si no — pero **dos tests de sesión 04 codificaban el
contrato opuesto** ("env gana incondicionalmente y fast-failea", con
docstring explícito). Se preguntó al humano: mantener el fast-fail
incondicional (tests intactos) vs. seguir el prompt literal (tests
reescritos). **Se eligió existence-aware** — `tests/test_ipc.py` no es F1,
así que reescribir es admisible con sign-off explícito.

### Implementación

`src/kicad_mcp/bridge/ipc.py`:

```python
_KICAD_SOCKET_DIR = Path("/tmp/kicad")
_LEGACY_SOCKET_NAME = "api.sock"
_PID_SOCKET_GLOB = "api-*.sock"


def _resolve_kicad_socket(explicit_arg: str | None = None) -> str | None:
    """Cascada: KICAD_API_SOCKET (si existe) → explicit_arg (si existe) →
    legacy api.sock (si existe) → glob api-<PID>.sock (1 match, o el más
    reciente por mtime con warning si hay varios) → último recurso: el
    override explícito aunque falte (fast-fail) → None."""
    env = os.environ.get("KICAD_API_SOCKET")
    if env and not _socket_file_missing(env):
        return env
    if explicit_arg and not _socket_file_missing(explicit_arg):
        return explicit_arg
    legacy = _socket_uri(_KICAD_SOCKET_DIR / _LEGACY_SOCKET_NAME)
    if not _socket_file_missing(legacy):
        return legacy
    matches = sorted(
        _KICAD_SOCKET_DIR.glob(_PID_SOCKET_GLOB),
        key=lambda p: p.stat().st_mtime,
    )
    if matches:
        if len(matches) > 1:
            log_socket_glob_ambiguous(chosen=str(matches[-1]), count=len(matches))
        return _socket_uri(matches[-1])
    return env or explicit_arg or None
```

Constantes de descubrimiento separadas de `_DEFAULT_SOCKET_LINUX` (que se
mantiene, ahora solo referencia/legacy) para que los tests las
`monkeypatch.setattr` y redirijan a un `tmp_path`, sin tocar nunca el
`/tmp/kicad` real del dev. Helper puro salvo un log warning
(`log_socket_glob_ambiguous`, nuevo en `logging_config.py`, mismo patrón
que `log_ipc_retry`) cuando hay múltiples sockets per-PID.

`IpcBridge.__init__` pasó de resolver inline a delegar en el helper:
`self._socket_path = _resolve_kicad_socket(socket_path)`.

### Hallazgo en vivo: la resolución debía ser dinámica, no solo en `__init__` (R11)

La primera pasada implementó la cascada, pero solo la ejecutaba **una vez**,
al construir `IpcBridge` (server startup). Al verificar en vivo el
escenario "cerrar y reabrir KiCad" (ver abajo), `health()` siguió
reportando `KICAD_NOT_RUNNING` tras el reinicio: el bridge — que vive tanto
como el proceso del server MCP, mucho más que una sesión de KiCad — se
había quedado con `self._socket_path` apuntando al socket viejo (muerto),
y nada volvía a resolver la cascada. Esto contradice directamente el
criterio de cierre de la sesión ("robusto ante crashes de KiCad, R11").

Fix: `socket_present()` y `_ensure_client()` re-resuelven la cascada en
cada llamada (barato: unos pocos `stat` + un `glob`), en vez de leer un
valor congelado:

```python
def socket_present(self) -> bool:
    self._socket_path = _resolve_kicad_socket(self._socket_path_arg)
    if self._socket_path is None:
        return False
    return not _socket_file_missing(self._socket_path)

def _ensure_client(self) -> KiCadClientLike:
    resolved = _resolve_kicad_socket(self._socket_path_arg)
    if resolved != self._socket_path:
        self._client = None          # socket cambió: cliente viejo, descartar
        self._socket_path = resolved
    if self._client is None:
        ...
```

De paso apareció un segundo bug, más sutil: `_socket_file_missing(None)`
devuelve `False` por diseño (delega en el factory para esquemas no
verificables) — pero `socket_present()` hacía `not _socket_file_missing(...)`,
así que con `self._socket_path is None` (nada descubrible en absoluto)
`socket_present()` devolvía `True` por doble negación. Corregido con un
check explícito de `None` antes de delegar en `_socket_file_missing`.

### Tests (`tests/test_ipc.py`)

**6 nuevos** (sección `# --- resolución cascada del socket (sesión 19e,
F-19b-09) ---`), todos verdes:

| Test | Caso | Resultado |
|---|---|---|
| `test_resolve_socket_env_var_wins_when_path_exists` | env existe | ✅ devuelve env |
| `test_resolve_socket_env_var_missing_falls_through_to_last_resort` | env no existe, nada más | ✅ devuelve env igual (fast-fail aguas abajo) |
| `test_resolve_socket_legacy_path_used_when_present` | solo `api.sock` | ✅ devuelve legacy |
| `test_resolve_socket_single_pid_glob_match` | solo `api-1234.sock` | ✅ devuelve ese |
| `test_resolve_socket_multiple_pid_globs_picks_newest_and_warns` | `api-1234.sock` + `api-5678.sock`, mtimes distintos | ✅ devuelve el más reciente + warning capturado (`caplog`) |
| `test_resolve_socket_nothing_found_returns_none` | nada | ✅ `None` |
| `test_socket_present_reflects_live_filesystem_changes` | socket aparece/desaparece sin reconstruir el bridge | ✅ `socket_present()` refleja cada cambio |
| `test_bridge_reconnects_when_socket_changes_after_kicad_restart` | socket viejo desaparece, aparece uno con otro nombre; `get_version()` dos veces | ✅ factory invocado con ambos paths, en orden |

**2 reescritos** (contrato existence-aware, sesión 04 → 19e):

- `test_default_factory_fast_fails_when_ipc_socket_missing` — mismo intent
  (fast-fail <100 ms), hermetizado con `_KICAD_SOCKET_DIR` → `tmp_path`
  vacío para que el env inexistente + nada descubrible caiga al último
  recurso. ✅
- `test_default_factory_resolves_socket_env_over_arg` →
  **`test_default_factory_resolves_arg_when_env_missing`**: nuevo
  contrato — con env inexistente, gana el arg (que sí existe), no falla.
  Docstring reescrito para explicar el cambio de contrato. ✅

Suite completa final: `325 passed, 29 skipped` (`pytest -m "not
integration"`), `ruff check` limpio, `ruff format --check` limpio, `mypy
src/` limpio (33 archivos).

### Verificación en vivo (contra KiCad 10.0.4 real, `/tmp/gui-test-project`) — 3/3 PASS

Estado de `/tmp/kicad/` al iniciar: `api-5640.sock` (KiCad ya corriendo),
`api.lock`, **sin symlink legacy**.

**Nota operacional:** el fix vive en el código Python del server
`kicad-mcp`; el proceso MCP ya corriendo tenía el código viejo cacheado en
memoria. Cada cambio de código relevante exigió matar el proceso (`kill
<pid>`) y pedirle al humano `/mcp reconnect` — el host (Claude Code) no
reconecta automáticamente. Con el hallazgo en vivo de más arriba, esto
pasó **tres veces** en la sesión (fix inicial → hallazgo R11 → fix R11).
Fricción real para cualquier sesión futura que edite `bridge/` o `tools/`
con el server MCP activo — anotado también en §"Fricción operacional".

1. **Sin symlink** → `health()`:
   ```json
   {"kicad_ipc":{"socket":"ok","ipc_responde":"ok","version":"10.0.4",
     "pcb_editor_abierto":"yes","status":"ok"}}
   ```
   ✅ **PASS** — resuelto por glob per-PID (`api-5640.sock`), sin
   intervención.

2. **Nuevo PID (cerrar/reabrir KiCad real, hecho por el humano)** —
   primera pasada **FALLÓ** (`ipc_responde` volvió a `"unknown"` /
   `KICAD_NOT_RUNNING`): expuso el bug de resolución congelada en
   `__init__` descrito arriba. Curiosamente la segunda instancia de KiCad
   creó el socket como `api.sock` **sin sufijo de PID** (no
   `api-<PID>.sock` como la primera) — confirma que el naming del socket
   no es 100% predecible y refuerza que la cascada, no solo el glob, tenía
   que cubrir el caso legacy también. Tras el fix R11 (re-resolución
   dinámica) y reconexión del server: ✅ **PASS** —
   `{"ipc_responde":"ok", ...}` sin ningún symlink ni intervención más
   allá de reiniciar KiCad.

3. **Env var inválida** — primer intento con `export
   KICAD_API_SOCKET=...` en la shell interactiva del humano **no llegó al
   proceso real**: el server MCP se lanza vía `~/.claude.json`
   (`projects."<repo>".mcpServers."kicad-mcp".env`), con su propio dict de
   env fijo — no hereda exports de la shell del humano. Verificado
   inspeccionando `/proc/<pid>/environ` del proceso tras reconectar: seguía
   con el valor previo válido. Corregido seteando el valor inválido
   (`ipc:///tmp/kicad/nonexistent-19e-test.sock`) directamente en esa
   config, con `/mcp reconnect` — confirmado por `/proc/<pid>/environ` que
   el valor inválido sí llegó al proceso esta vez. Resultado: ✅ **PASS** —
   `{"ipc_responde":"ok", ...}`, cayó a la resolución legacy/glob. Config
   restaurada al valor original (`ipc:///tmp/kicad/api.sock`) inmediatamente
   después, con reconexión final.

### `docs/arquitectura.md` §RNF6

Actualizado: el socket ya no se describe como el path fijo
`/tmp/kicad/api.sock`, sino como la cascada implementada (env → legacy →
glob per-PID con `mtime` como desempate), con referencia a
`bridge/ipc.py::_resolve_kicad_socket()`.

---

## 19e.2 — Investigación F-19b-06 (`get_world_context(kind=sch)`) · documentar + diferir

**Reproducido en vivo** contra `/tmp/gui-test-project` (sch ya corregido
post-19b):

```
KICAD_CLI_FAILED: Estado inconsistente entre netlist y posiciones.
hint: posición sin netlist: #FLG01, #FLG02, #PWR01
```

### Causa raíz confirmada

`_rebuild` (`state_builder.py:181-195`) hace un set-difference estricto
entre refs de dos fuentes:

- **Posiciones** (`sch_positions.py::parse_root_positions`): escanea TODO
  símbolo raíz con `lib_id` + propiedad `Reference`, sin distinguir tipo.
- **Netlist** (`netlist.py` vía `kicad-cli sch export netlist --format
  kicadxml`): lista de componentes del export de kicad-cli.

Verificado con `export_netlist()` sobre el mismo proyecto: el `.kicad_sch`
tiene **26 pseudo-símbolos** de potencia/flag (`#PWR01`…`#PWR024`,
`#FLG01`, `#FLG02` — confirmado por grep de `property "Reference" "#..."`
en el `.kicad_sch`), y **ninguno de los 26** aparece en el netlist
exportado (`grep -oP '\(ref "\K[^"]+' netlist.net | grep '^#'` → vacío).
El hint del error trunca a los primeros 3 (`only_in_positions[:3]`, código
existente) — el mensaje sugiere una inconsistencia puntual, pero es en
realidad **sistemática**: TODO símbolo `#`-prefijado del schematic cae en
esta asimetría, siempre.

### Clasificación

**No es (a) bug de código, ni (c) inconsistencia real del sch.** Es (b):
comportamiento esperado de KiCad — los pseudo-símbolos de potencia/flag
(`#PWR*`, `#FLG*`) son anotaciones de conectividad, no componentes reales;
`kicad-cli` los excluye deliberadamente de la lista de componentes del
netlist (no representan partes que se sueldan). `sch_positions.py`, al
escanear posiciones sin filtrar por tipo, sí los incluye. El invariante
actual de `state_builder` ("una ref en una fuente y ausente en la otra ⇒
estado inconsistente, jamás adivinar" — comentario en el módulo) es
correcto para refs de componentes reales pero demasiado estricto para esta
clase completa de pseudo-símbolos.

### Decisión (usuario, antes de investigar)

Documentar + diferir a 20b, sin tocar el invariante en esta sesión corta.
El fix natural — filtrar refs `#`-prefijadas de ambos lados antes del
diff, en `_rebuild` (`state_builder.py:181-184`) o en las dos fuentes de
parseo — es sencillo en líneas de código, pero cambia un invariante de
diseño deliberado documentado en el módulo; amerita revisión propia en
20b, no una sesión de 30 min.

**Workaround vigente** (usado en 19b, sigue funcionando): el agente del
D3 puede parsear `export_netlist()` directamente para obtener
conectividad, evitando `get_world_context(kind="sch")` cuando el
schematic tiene símbolos de potencia/flag (prácticamente siempre).

**Agendado para 20b:** filtrar refs `#PWR*`/`#FLG*` (o más generalmente,
cualquier ref con prefijo `#` — convención de KiCad para símbolos
virtuales) de ambos lados del diff en `_rebuild`, con test de regresión
usando un fixture con power symbols.

Tiempo insumido: ~15 min (dentro del timeout de 30 min).

---

## Fuera de alcance (confirmado, sin tocar)

CRUD de sch, F-19b-12 (`run_erc` ÷100), F-19b-10
(`get_pin_net_membership`), refactor amplio del bridge, cambios a
route_board/zones/tracks. Fix de 19e.2 no aplicado (documentado +
diferido, según lo acordado).

## Fricción operacional nueva (no estaba en el prompt)

1. **Editar código consumido por el server `kicad-mcp` en runtime requiere
   matar el proceso viejo y que el humano ejecute `/mcp reconnect`** — no
   hay auto-reload ni auto-reconexión. Pasó 3 veces en esta sesión (fix
   inicial, hallazgo R11, restauración de config). Anotarlo para
   cualquier sesión futura que itere sobre `bridge/` o `tools/` con el
   server MCP activo.

2. **La env del server MCP no es la de la shell interactiva del humano** —
   vive fijada en `~/.claude.json` (`projects.<repo>.mcpServers.kicad-mcp.env`),
   fuera del repo. `export FOO=bar` en la terminal del humano no llega al
   proceso del server salvo que también se edite esa config. Costó un
   round-trip completo en el escenario 3 antes de detectarlo (verificado
   con `/proc/<pid>/environ`, no asumido).

3. **El naming del socket de KiCad no es 100% predecible entre
   reinicios** — la primera instancia de este dogfooding creó
   `api-5640.sock` (con PID), la segunda `api.sock` (sin PID), en el
   mismo binario/versión. Confirma que la cascada necesitaba cubrir tanto
   el path legacy como el glob per-PID, no uno solo.

## Cierre

19e.1: fix implementado y corregido en vivo (bug de resolución congelada
en `__init__`, no sobrevivía a un reinicio de KiCad — encontrado durante
la propia verificación de este ítem, no en el prompt original). Testeado:
10/10 tests de socket verdes (8 nuevos + 2 reescritos), suite completa
`325 passed, 29 skipped`, `ruff`/`mypy` limpios. **3/3 escenarios de
verificación en vivo confirmados** contra KiCad 10.0.4 real, incluyendo
los dos que requerían intervención manual del humano (reinicio de KiCad;
edición + reconexión de la config del server MCP).

19e.2: cerrado como documentado + diferido a 20b, sin código nuevo. Causa
raíz confirmada en vivo con evidencia concreta (26 pseudo-símbolos, 0 en
netlist).

`docs/arquitectura.md` §RNF6 actualizado. Listo para commit.
