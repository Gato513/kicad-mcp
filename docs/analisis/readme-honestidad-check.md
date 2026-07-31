# Verificación D-33.1 de afirmaciones públicas — sesión 34b

**Objetivo:** cada afirmación pública en `README.md`/`README.es.md`/
`CONTRIBUTING.md` pasa por el filtro D-33.1 antes de publicarse: ¿qué
evidencia la sostiene, y qué la refutaría? Registro auditable, no
narrativo — una fila por afirmación con verdadera consecuencia si falla.

| # | Afirmación pública | Evidencia que la sostiene | Qué la refutaría | Veredicto |
|---|---|---|---|---|
| 1 | "32 purpose-built tools" | `grep -rA2 "@mcp.tool" src/kicad_mcp/tools/*.py` → 32 nombres únicos, verificado esta sesión | Un conteo distinto al correr el mismo grep tras un cambio de código | **Sostenida** — verificada por comando, no copiada del prompt (que decía "20+"/31) |
| 2 | "The full PCB write loop... has been closed and re-validated... for months" | Dogfoodings D1-D7 (`docs/ROADMAP.md`), Validation Suite A/B (sesiones 31-32) completos con DRC 0 eléctricos/estructurales nuevos | Un P0 de regresión activo sin cerrar en el loop de escritura | **Sostenida con matiz** — cierta para Nivel A/B (2 capas); no se afirma para Nivel C (4 capas), donde explícitamente no completó |
| 3 | "Validated scale... up to 63 footprints / 48 nets / 2 layers" | `validation-suite-sintesis-A-B-C.md` tabla comparativa, Nivel B completó ruteo (328.9s) con 3/4 criterios D-30.3 | Un 4º criterio (vías) en el borde exacto (+20.00%), no un incumplimiento — se reporta igual como "borde", no se oculta | **Sostenida**, con el borde declarado explícitamente en el README (no se redondea a "cumple limpio") |
| 4 | "the autorouter did not complete" (HackRF One, 437 fp/4 capas) | `docs/BACKLOG.md` F-V3-ROUTER-TIMEOUT-HARD: `route_board(timeout_s=3600)` no completó, crash-loop interno de Freerouting documentado con logs | Un log mostrando que sí completó o que fue cancelado por el usuario, no por el motor | **Sostenida** — reproducido y documentado, causa raíz upstream, no ambigua |
| 5 | "add_zone(fill=true) can crash KiCad after 3-4 consecutive calls... Root cause is not conclusively identified" | Auditoría 34a §4: 3/3 reproducciones con geometrías distintas, análisis de código sin causa del lado del bridge, harness sintético no ejecutado (bloqueado, documentado por qué) | Una repro exitosa contra un board sintético que aislara la causa (bridge vs. pcbnew) | **Sostenida explícitamente como no concluyente** — el README no la presenta como "bug conocido de pcbnew", dice literalmente que no se confirmó |
| 6 | "Only route_board, fill_zones, and add_zone(fill=true) guarantee disk == memory" | `ADR-0012`, matriz de auditoría 34a §2 (Eje 1: 3 W-COMPOSITE con "C", 6 W-IPC con "C-m por diseño") | Una tool W-IPC que sí guarda a disco incondicionalmente, no documentada como tal | **Sostenida** — matriz completa revisada línea por línea contra código en 34a |
| 7 | "delete_tracks_bulk refills copper zones in memory but doesn't persist or re-check hole clearance" | Auditoría 34a §5.2 A1: refill inline sin `_refill_enforce_and_save`, `docs/BACKLOG.md` P1 con línea de código citada (pcb.py:2039) | Un test de regresión mostrando que sí persiste hoy | **Sostenida** — asimetría real, P1, fix ya agendado (34a-fix-1), consistente con lo que dice el README |
| 8 | "A specific same-layer variant... isn't fixed by the existing post-route stitching yet" (F-D5-01-B) | `docs/BACKLOG.md` "Abierto — F-D5-01-B", origen sesión 32d, geometría del caso descrita (mismo layer B.Cu, pad+zona+track) | El stitching de D-32d.1 extendido para cubrir same-layer, sin reabrir el hallazgo | **Sostenida** — abierto en BACKLOG, sin fix reportado |
| 9 | "Long-running tool calls... can exceed an MCP client's idle timeout (~1818s observed)" | `docs/historico/sesiones/33-reporte.md:37` cita el número exacto observado y el workaround usado | Un valor distinto o inexistente en el reporte de sesión 33 | **Sostenida** — cifra tomada literal del reporte, no estimada |
| 10 | "GUI-dependent tests require a human... not automated... a constraint of KiCad's current IPC API" | `docs/guias/pruebas-gui.md:1-7` lo declara explícitamente igual, marcas `integration_gui`/`integration_gui_slow` en `pyproject.toml` | Una forma de scriptear "abrir proyecto en GUI" ya disponible y no usada | **Sostenida** — mismo lenguaje que el propio protocolo interno, no una excusa nueva inventada para el README |
| 11 | "Practically Linux-only" | `docs/adr/0005-linux-como-plataforma.md`, `CLAUDE.md` F4 (frontera KiCad 10.0.4 objetivo) | Evidencia de soporte real en macOS/Windows en el repo (CI, scripts) | **Sostenida** — no hay ningún path multiplataforma en el proyecto |
| 12 | Elevator pitch: evita "end-to-end", "automates full PCB design", "works on any board" | Restricción impuesta antes de escribir (ver plan Bloque 2); Nivel C es evidencia directa de que ninguna de las tres frases sobrevive | Aparición de esas frases en el texto final | **Sostenida** — verificado por lectura del README publicado (Bloque 5.3), ninguna de las tres frases aparece |
| 13 (CONTRIBUTING) | Ejemplo "route_board(refill=true) discarded a failed disk reload inside a bare except and reported success anyway" | `docs/DECISIONES.md` D-32b.1: mecanismo confirmado, cita exacta del bug (F-V2-REFILL-SILENCIOSO) | El código pre-fix no mostrando ese patrón exacto | **Sostenida** — descripción consistente con D-32b.1, sin inventar detalles no confirmados |
| 14 (CONTRIBUTING) | Los 4 ejes (persistencia / errores / sync / reload) como checklist de PR | `docs/DECISIONES.md` D-34a.1, adoptado tras auditar las 32 tools existentes | Que la auditoría 34a no haya, de hecho, cubierto las 32/32 | **Sostenida** — auditoría 34a cubre 20 filas de matriz (19 tools únicas + `add_zone` dual), confirmado por lectura directa del documento |
| 15 (NOTICE) | `kicad-skip` es LGPL-2.1-or-later (no MIT, como asumía el prompt original de esta sesión) | `.venv/.../kicad_skip-0.2.5.dist-info/METADATA`: `Classifier: ... LGPLv2+` | Un cambio de licencia en una versión más nueva del paquete no reflejado en el lockfile | **Sostenida** — corregido activamente respecto a la premisa incorrecta del prompt, verificado en el propio entorno instalado |
| 16 (NOTICE) | `pcbnew` se invoca vía subprocess contra Python del sistema, nunca importado en el venv del proyecto | `src/kicad_mcp/bridge/autoroute.py:57-73` (comentarios explícitos + patrón `python3 -c`) | Un `import pcbnew` directo en algún módulo de `src/` | **Sostenida** — verificado por lectura del código citado |

## Afirmaciones descartadas antes de publicar (no llegaron a la versión final)

- *"kicad-mcp automates the canonical KiCad flow end-to-end"* — descartada
  en el elevator pitch por ser refutable con Nivel C (HackRF One no
  completó el ruteo). Reformulada como "automates the canonical... flow"
  sin "end-to-end", con la escala validada declarada aparte.
- *"validated against 3 real-world open hardware projects"* sin matiz —
  descartada como frase suelta porque sugiere 3 validaciones exitosas
  cuando la síntesis A+B+C es explícita en que Nivel C es refutación por
  escalabilidad, no un 3er punto exitoso. El README dice esto directamente
  ("found the scaling ceiling, not a routed result").

## Conclusión

16/16 afirmaciones verificadas revisadas sobreviven el filtro D-33.1 con
veredicto **Sostenida** (2 de ellas con matiz explícito ya incorporado al
texto, no oculto). Ninguna requirió suavizarse en la redacción final más
allá de lo que ya reflejaba la evidencia disponible. Las 2 correcciones de
premisa del prompt original (licencia de `kicad-skip`, invocación de
`pcbnew`) se registran también en el plan de sesión y en `NOTICE`
directamente.
