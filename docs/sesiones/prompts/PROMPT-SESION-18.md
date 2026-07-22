# Sesión 18 — P3: Recarga programática post-route (eliminar el revert humano)

**Tipo:** DEV sobre kicad-mcp, **nueva rama** `sesion/18-recarga-programatica`
desde `master` (tras merge de `sesion/17-route-board-robusto`).

**Origen:** D-V3.1 (hoja de ruta v3, revoca parte de D-R2/D-14.1). El D2 tuvo
3 File→Revert humanos (no 1 como asumía D-14.1); la sesión 17 confirmó
empíricamente el split-brain con un caso donde la corrida A del fixture pisó
el ruteo real porque el board vivo nunca se recargó. Sin resolver esto, la
sesión 20 (Dogfooding 3) va a repetir la fricción.

**Criterio de cierre (gate):** una sesión de ruteo del despertador con
**cero** contactos humanos de recarga (o exactamente uno, y solo si es
batching documentado). El test E2E ejecuta `route_board` → mutación de cobre
→ `save_board` sin que el board vivo pise el ruteo. `get_tracks` post-route
ve el cobre del ruteo, no el estado pre-route.

## Fronteras

F1–F5 vigentes. **F4 explicitado** por decisión del humano (2026-07-20):
asume KiCad 10.0.4 exclusivamente; no asumir compatibilidad ni comportamiento
de KiCad 11 hasta que exista una decisión formal de migración. Todo hallazgo
de IPC debe reflejar la superficie de KiCad 10.0.4 vía `kipy`, no de versiones
posteriores.

Las decisiones D-14.1 (guard `live_stale`) y D-14.2 (excepto por D-17.1 en
`route_board`) siguen vigentes. Esta sesión NO las revoca — extiende el
mecanismo para que la recarga sea automática cuando sea posible.

---

## Tarea P3.0 — Investigación: ¿qué expone KiCad 10.0.4 vía IPC para recargar?

**Sesión de investigación primero, código después.** No hay decisión firme
sobre el mecanismo — el prompt anterior (v3) menciona "IPC RevertBoard si
existe" como conjetura, pero D-12.4 dice que reload_in_gui es imposible en
KiCad 10. Necesito evidencia empírica antes de comprometerme a un diseño.

**Investigar (documentar hallazgos en `docs/investigacion/18-recarga-ipc.md`)
antes de escribir cualquier tool:**

1. Enumerar todos los métodos de `kipy.Board` y `kipy.KicadClient` que puedan
   afectar el estado del board editor. `dir()` + inspección de firmas + lectura
   del código kipy si está accesible.
2. Probar en vivo (con KiCad 10.0.4 abierto sobre el proyecto de prueba) cada
   candidato prometedor. Documentar: qué hace realmente, si mueve el estado
   vivo tras un cambio externo en disco, si requiere permisos especiales, si
   dispara diálogos GUI, si es reversible.
3. Ubicar en `kipy` los métodos ya usados por el bridge (`GetOpenBoard`,
   `RefreshEditor` si existe, etc.) y su comportamiento real (no el
   documentado — kipy tiene lagunas de documentación).
4. Si nada de kipy resuelve el problema, evaluar rutas alternativas:
   - Emitir un evento IPC de "board dirty" que fuerce a KiCad a re-leer
   - Usar `RunAction` (si existe) con la acción interna de KiCad para revert
   - Rutear directo contra el board vivo vía IPC (sin ir a disco) — cambia
     el modelo mental de route_board pero elimina la necesidad de recarga
5. Reportar TRES opciones ranqueadas, con:
   - Costo de implementación
   - Robustez (¿rompe con actualización de KiCad?)
   - Alcance (¿resuelve solo route_board o también otras mutaciones externas?)

**Decisión del arquitecto en base a la investigación:** después del reporte
P3.0, el agente ESPERA confirmación humana sobre qué opción implementar. No
avanza a P3.1 sin ese input. Si el humano no responde en la sesión, ejecutar
la opción #1 del ranking del propio agente y documentar la asunción.

---

## Tarea P3.1 — Implementación de la recarga (post-decisión)

**Sujeto al resultado de P3.0.** Diseño esperable si sale por la ruta más
probable (IPC de recarga):

Nueva tool `reload_board_from_disk()` (o modificación de las existentes
según lo que la investigación revele):
- Fuerza al PCB Editor vivo a re-leer el archivo desde disco.
- Devuelve `{"reloaded": true, "snap_id": <nuevo>, "tracks": N, "vias": M}`
  para que el agente confirme el estado.
- Idempotente: llamarla dos veces seguidas no rompe nada.
- Si el editor no está abierto o la recarga falla: error nuevo
  `RELOAD_FAILED` con hint accionable ("KiCad no expuso el método esperado;
  hacer File→Revert manualmente").

**Integración con `route_board`:**
- Después de que route_board escriba a disco, llama automáticamente a
  `reload_board_from_disk()`.
- El resultado JSON de route_board (contrato de sesión 17) gana un campo
  `"reloaded": true|false|"skipped_editor_closed"`.
- Si `reloaded=false`, el guard `live_stale` se activa como antes (D-14.1)
  y el agente sabe que hay un revert pendiente.

**Fallback si P3.0 concluye "no hay recarga programática posible":**
- Documentar formalmente en un ADR (`docs/adr/ADR-0013-recarga-imposible-kicad-10.md`)
  que la recarga programática es infactible en KiCad 10.0.4.
- Implementar batching documentado: `route_board` gana un flag `batch=true`
  que suprime el aviso live_stale hasta que el agente llame explícitamente
  a `flush_pending_reload()` (que solo emite un aviso final "hacer File→Revert
  ahora"). Un solo revert por sesión de ruteo iterativo.
- Esto NO cumple el gate ideal (cero contactos), pero SÍ cumple la reducción
  medida: de 3 reverts en el D2 a 1 en el D3. Es un cierre honesto.

---

## Tarea P3.2 — Guard reforzado post-mutación externa

Independiente del resultado de P3.0. El split-brain de la corrida A del
fixture (sesión 17) demostró que `save_board` sobre un board vivo obsoleto
puede pisar el estado real en disco. Fortalecer:

1. Antes de cada `save_board` (y cualquier tool de escritura de cobre
   `add_track`, `add_via`, `delete_track`, `delete_via`), verificar si el
   archivo en disco tiene `mtime` posterior al último `snap_id` cargado.
2. Si sí: rechazar la operación con `EXTERNAL_EDIT_DETECTED` (código
   existente, F3 no se rompe) + hint específico "el archivo cambió en disco;
   recargar el board vivo con `reload_board_from_disk()` (o File→Revert) y
   reintentar".
3. Test unit + integration_gui que reproduce el escenario de la corrida A
   inválida: `route_board` escribe → intentar `save_board` sin recargar →
   debe fallar con EXTERNAL_EDIT_DETECTED, no pisar el disco.

Este guard es **red de seguridad**: aunque la recarga programática funcione,
si algún día se rompe (por bug de kipy, por versión distinta de KiCad, etc.)
este guard evita pérdida de datos silenciosa.

---

## Tarea P3.3 — Test E2E del gate (contra fixture)

Sobre `tests/fixtures/despertador-routed/` (fixture generado en sesión 17):

Escenario "sesión de ruteo iterativo típico":
1. Abrir el fixture (copia a tmpdir) con `open_project`.
2. Estado inicial verificable: `get_tracks(net=<alguna>)` devuelve N tracks.
3. Simular una mutación de sesión: `delete_track(id=)` (uno de los tracks del
   fixture) → `route_board` (para re-conectar) → `get_tracks(net=<misma>)`
   debe ver el NUEVO cobre, no el pre-route.
4. Repetir el ciclo 2 veces más (3 iteraciones total). Cada iteración: 0
   contactos humanos.
5. Al final: `save_board` → verificar el archivo en disco contiene los tracks
   del último route_board.

**Métrica de éxito:** el test corre sin `pytest.skip`, sin fallar, sin
requerir `KICAD_MCP_MANUAL_INTERVENTION=1` o equivalente. Si la ruta fallback
(batching, sección P3.1) es la que quedó, el test acepta exactamente 1
llamada al método de flush como toque humano equivalente.

---

## Fuera de alcance (17b + 19 no se tocan)

- A* de bloqueador concreto (17b).
- Zonas (P4, sesión 19).
- Sch del despertador (sesión 19b, mi trabajo).
- Migrar a KiCad 11.

---

## Reporte final (`docs/sesiones/18-reporte.md`)

- **Reporte P3.0 completo** — las 3 opciones investigadas, ranking, opción
  elegida y justificación (del agente o del humano).
- Diff-resumen por tarea.
- Contrato final de `reload_board_from_disk` (o el mecanismo equivalente).
- Cambios al contrato JSON de `route_board` (campo `reloaded`).
- Estado del guard reforzado (P3.2).
- Test E2E de P3.3: pass/fail + tokens/tiempo del ciclo iterativo.
- **Comparación empírica**: sesión de ruteo iterativo con el nuevo mecanismo
  vs. simulación del flujo del D2 (3 reverts). Reportar contactos humanos
  reales del test E2E.
- Bugs reales encontrados (esperado: alguna sorpresa de kipy o de IPC en
  KiCad 10.0.4). Reportar sin arreglar si están fuera de scope; agregar al
  backlog de 17b si aplica.

## Cierre esperado

Sesión 18 cerrada → sesión 19 (P4, zonas) → sesión 19b (yo corrijo sch) →
sesión 20 (Dogfooding 3, meta ≥8/10).
