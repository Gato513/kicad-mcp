# Sesión 19e — Fix socket path resolution + investigación get_world_context(kind=sch)

**Tipo:** DEV sobre kicad-mcp, **nueva rama** `sesion/19e-socket-path-fix`
desde `master` (tras merge de sesiones 19 + 19d + 19b).

**Origen:** Blocker F-19b-09 identificado en sesión 19b. El bug del socket
path bloqueó `health()` durante toda la sesión de investigación 19b; el
workaround (symlink manual) es frágil ante crashes de KiCad (R11) y
diagnósticamente opaco para el agente del D3.

**Criterio de cierre (gate):** `health()` reporta `ipc_responde: ok` contra
KiCad 10.0.4 sin symlink en `/tmp/kicad/`. Los 3 modos de resolución
(env var, path fijo legacy, glob per-PID) tienen test de regresión.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4 exclusivamente. **Sesión corta, alcance
acotado.** No features nuevos. No CRUD de sch (diferido a 20b). No
refactor amplio del bridge — sólo el sitio del bug.

---

## Tarea principal 19e.1 — Fix `_DEFAULT_SOCKET_LINUX` resolution

### Diagnóstico existente (F-19b-09)

- Archivo: `src/kicad_mcp/bridge/ipc.py`, línea ~972.
- Actual: `_DEFAULT_SOCKET_LINUX = "/tmp/kicad/api.sock"` (hardcodeado).
- Real KiCad 10.0.4: crea `/tmp/kicad/api-<PID>.sock` con sufijo de PID.
- Consecuencia: `IpcBridge` conecta a un path que nunca existe → `health()`
  reporta `KICAD_NOT_RUNNING` incluso con KiCad + API habilitados.

### Estrategia de resolución en cascada

Nuevo helper `_resolve_kicad_socket()` en `bridge/ipc.py` que intenta en
orden:

1. **`KICAD_API_SOCKET` env var** — si está seteada y el path existe →
   usar ese. Permite override explícito para tests y ambientes atípicos.
2. **Path fijo legacy** — `/tmp/kicad/api.sock` — si existe (para versiones
   futuras o instalaciones que sí usen el nombre canónico) → usar.
3. **Glob per-PID** — `/tmp/kicad/api-*.sock`:
   - Si hay exactamente 1 match → usar.
   - Si hay múltiples matches → tomar el más reciente por `mtime` (el
     KiCad más recientemente iniciado) + log a nivel warning.
   - Si hay 0 matches → devolver `None` → el caller decide qué hacer
     (típicamente `KICAD_NOT_RUNNING`).

**Consideraciones:**
- No hacer symlinks automáticos (frágil, potencialmente destructivo, y
  requiere permisos de escritura en `/tmp/kicad/`).
- El helper es puro, sin side effects. Todo el logging del descubrimiento
  va al `logging_config` estándar.
- Documentar en docstring que en Linux la resolución es cascada; en otras
  plataformas mantener el path canónico como está.

### Tests de regresión (`tests/test_ipc.py`)

Con `tmp_path` y mocks del filesystem:
- Env var seteada + path existe → devuelve env var.
- Env var seteada + path no existe → cae al siguiente nivel.
- Path fijo `/tmp/kicad/api.sock` existe → devuelve ese.
- Solo existe `/tmp/kicad/api-1234.sock` → devuelve ese.
- Existen `/tmp/kicad/api-1234.sock` + `/tmp/kicad/api-5678.sock` con
  `mtime` distintos → devuelve el más reciente.
- Nada existe → devuelve `None`.

### Verificación en vivo (obligatoria)

Antes de cerrar 19e.1, contra KiCad 10.0.4 real:

1. **SIN symlink** en `/tmp/kicad/` → `health()` debe reportar
   `ipc_responde: ok` (el fix resuelve automáticamente por glob).
2. Cerrar KiCad, abrir de nuevo (nuevo PID) → `health()` debe seguir
   funcionando sin intervención.
3. Con env var `KICAD_API_SOCKET` apuntando a un path que no existe →
   `health()` debe caer al fallback y funcionar igual.

---

## Tarea 19e.2 — Investigar F-19b-06 (`get_world_context(kind=sch)`) (timeout: 30 min)

Reportado en 19b como `KICAD_CLI_FAILED` con "estado inconsistente entre
netlist y posiciones, `#FLG01/#FLG02/#PWR01`" al invocar
`get_world_context(kind="sch")` sobre el proyecto despertador.

### Investigación acotada

1. Reproducir el fallo contra el sch corregido en `/tmp/gui-test-project/`.
2. Identificar si es (a) bug de código en el bridge/tools, (b) limitación
   de kipy 0.7.1 con símbolos `#FLG*`/`#PWR*`, o (c) inconsistencia real
   del sch (¿flags flotantes, símbolos duplicados en netlist vs posiciones?).
3. Si es (a) y fix < 20 líneas → aplicar con test de regresión.
4. Si es (b) o (c) → documentar la causa raíz y agendar como item para
   20b, sin implementar workaround. El agente del D3 puede parsear
   `export_netlist()` como hizo 19b (documentado en el reporte).

**Timeout duro 30 min.** Si la investigación se complica, documentar y
salir. Este item NO es blocker del D3 — el workaround existe y funciona.

---

## Fuera de alcance

- CRUD de sch (`delete_wire`, `delete_label`, `add_no_connect`,
  `set_symbol_attr`, `sync_symbol_from_library`) — diferido a 20b.
- F-19b-12 (`run_erc` unidades ÷100) — diferido a 20b.
- F-19b-10 (`get_pin_net_membership`) — diferido a 20b.
- Cualquier refactor del bridge más allá del helper puntual.
- Cualquier cambio a route_board, add_zone, delete_tracks_bulk, etc.

---

## Reporte final (`docs/sesiones/19e-reporte.md`)

- Fix aplicado con snippet del helper `_resolve_kicad_socket()`.
- Los 6 tests de regresión (unit) — verde/rojo por caso.
- Verificación en vivo (sin symlink, con nuevo PID de KiCad, con env var
  inválida) — resultado documentado.
- Resultado de 19e.2:
  - Si aplicaste fix: detalle del cambio + test.
  - Si documentaste: causa raíz, workaround vigente (`export_netlist`),
    agendado para 20b.
- Cambios a `docs/arquitectura.md` §RNF6 (path del socket) si aplican.

## Env vars

Las mismas de siempre:

```bash
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

**Preparación obligatoria:**
1. Merge de 19+19d+19b a master ya completado.
2. `rm /tmp/kicad/api.sock` — eliminar symlink hackeado para reproducir
   el bug limpiamente.
3. KiCad reiniciado desde cero con el proyecto de prueba abierto.

## Cierre esperado

Sesión 19e cerrada → sesión 20 (Dogfooding 3) tiene `health()` funcionando
nativamente sin trucos de symlink, robusto ante crashes de KiCad (R11).
