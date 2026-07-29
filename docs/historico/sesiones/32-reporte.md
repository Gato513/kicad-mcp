# Sesión 32 — Validation Suite Nivel B-01 (ANAVI Macro Pad 12)

**Rama:** `sesion/32-validation-B-anavi-macro-pad-12` (branch desde
`sesion/31c-reintento-anavi-dev-mic` — master no tenía mergeada la
secuencia 31→31b→31c al arrancar; precondición verificada al inicio,
resuelta encadenando la rama, mismo patrón que sesión 31c).
**Tipo:** segunda validación externa del flujo canónico (Nivel B,
complejidad media, criterio de diversidad D-30.4).

## Resumen ejecutivo

**Escenario 3 de 7 — "éxito con matiz de fricciones P2/P3"**, con
elementos del **Escenario 2 — "éxito con matiz de umbrales"**. El flujo
canónico generalizó sobre ANAVI Macro Pad 12 (63 footprints, 48 nets,
~3x la escala de Nivel A): `route_board` completó (42/42 nets ruteables,
0 bloqueadas), colocación 63/63 limpia. De los 4 criterios D-30.3, **3 de
4 cumplen** (tracks −4.05%, vías +20.00% exacto en el borde, cobre
+3.23%) — resultado muy superior a Nivel A (1/4). El único que no
cumple es DRC, por un hallazgo de conectividad GND puntual (3ª
instancia del patrón F-D5-01/F-V1c-01).

**Hallazgo independiente más valioso de la sesión:** `route_board`'s
refill interno (`refill=true`) puede fallar en silencio — sin
`POST_ROUTE_PERSIST_FAILED`, sin ningún error visible — cuando
`reload_board_from_disk` (mutación sin reintento, D-07.1) lanza una
excepción transitoria. Esto dejó 259 violaciones DRC reales (236
`clearance` + 23 `hole_clearance`, 100% contra la zona GND) sin resolver
hasta recuperación manual. **Confirmado reproducible**: el audit log de
`/tmp/gui-test-project` conserva la llamada `route_board` original de
sesión 31c mostrando el mismo patrón exacto (`reloaded: false,
zones_refilladas: 0`), nunca antes documentado porque el paso
"Refill final" ya prescripto en el flujo canónico lo compensaba sin que
nadie cruzara esos campos contra la promesa de `refill=true`.

**Link al reporte completo:**
`validation-suite/level-b/anavi-macro-pad-12/validation-report.md`.

## Desviaciones detectadas vs el prompt de la sesión

1. **Candidato prescrito refutado en Bloque 0.** El prompt prescribía
   ANAVI Miracle Emitter. Verificación directa contra el repo real (no
   sólo el prompt) mostró: sin diversidad D-30.4 genuina (sin cobre
   propio de USB-C, sin WS2812B como footprint — ambos viven en módulos
   externos al board) y escala menor que Nivel A (15 fp/19 nets vs
   13/20). "ESP32-C3 vs ESP8266 del Nivel A" del prompt también era
   falso — Nivel A nunca usó ESP8266. `AskUserQuestion` antes de activar
   respaldo; `anavi-macro-pad-12` admitido en el primer intento.
2. **H1b reformulada.** El prompt planteaba verificar si `route_board`
   respeta la netclass diff-pair de USB-C. Investigación de código
   (`src/kicad_mcp/bridge/rules_reader.py:217`) confirmó que el flujo
   descarta silenciosamente `diff_pair_width`/`diff_pair_gap` — y que
   **ningún** proyecto ANAVI verificado asigna netclasses (`"nets": []`
   en todos). H1b se reformuló sobre las features que el candidato sí
   ejercita (matriz de teclas, backlighting, hot-swap, migración de
   formato); la brecha de netclasses se registró como ítem de BACKLOG
   independiente, no como refutación de H1b.
3. **Contaminación accidental de la muestra representativa de
   colocación.** Durante el diagnóstico del incidente de proyecto
   erróneo (ver punto 4), un `get_world_context` expuso sin querer las
   63 posiciones del ground truth antes de la colocación real.
   Reportado de inmediato; decisión del arquitecto: usar las
   coordenadas del GT para los 63 footprints (mecánicamente correctas
   de todos modos) y reservar `get_footprint_neighbors` para
   verificación, no descubrimiento. Documentado como gap honesto de
   evidencia sobre D-D4.1 en esta sesión.
4. **Incidente de entorno no previsto en el prompt.** El servidor
   `kicad-mcp` resuelve el proyecto activo vía `KICAD_MCP_PROJECT` (fijo
   desde el arranque), independiente del GUI vivo — que seguía
   apuntando a un leftover de ANAVI Dev Mic (sesión 31c). Diagnosticado
   y resuelto con el patrón D-27.1 (reubicación no destructiva).

## Estado de la secuencia de Fase 4

1. Investigación P1 solder mask ANT1 — ✅ cerrada (sesión 30).
2. Validation Suite Nivel A — ✅ cerrada (sesión 31→31b→31c).
3. **Validation Suite Nivel B — ✅ cerrada (sesión 32).** 3/4 criterios
   D-30.3 cumplen (mejor que Nivel A). Segundo punto de evidencia real
   sobre H2: con base de vías 15x mayor, el umbral ±20% resultó
   razonablemente calibrado (borde, no falla amplia) — apoya la
   hipótesis de que el problema de 31c era el tamaño de la base.
4. Validation Suite Nivel C — pendiente, próxima sesión (33).
5. Preparación de release OSS — condicionada al cierre de las 3
   validaciones (31-33).

## Fricciones registradas

- **F-V2-REFILL-SILENCIOSO (P0/P1, nueva)** — refill interno de
  `route_board` no persiste bajo falla de `reload_board_from_disk`.
  Reproducible en 2 sesiones independientes (31c y 32). Recomendación:
  sesión de fix intermedia antes de sesión 33.
- **F-V2-VIA-HUERFANA (P2, 3ª instancia del patrón F-D5-01/F-V1c-01)** —
  2 pads GND no conectados al plano/track tras refill. **Cumple el
  trigger de promoción a P1 investigación Fase 4** (3ª instancia en
  régimen distinto: despertador D5 → anavi-dev-mic 31c → macro-pad-12 32).
- **F-V2-ROUTER-TIMEOUT (P2/P3)** — primer intento de `route_board`
  (1500s) no convergió (óptimo local real); segundo intento (3600s)
  completó en 5m29s. Consistente con F-D6-01 (variabilidad
  Freerouting/JVM, cerrada sesión 29).

## Estado del patrón F-D5-01

**Reincidencia confirmada — 3ª instancia** (despertador sesión 25 →
anavi-dev-mic sesión 31c → anavi-macro-pad-12 sesión 32). El mecanismo
exacto difiere entre instancias (via aislada en 31c vs. pad no conectado
al plano en 32), pero el síndrome (conectividad GND que sobrevive al
refill sin cerrar) es el mismo. Cumple el trigger de promoción explícito
del prompt de sesión 32 → **se agenda investigación P1 Fase 4**,
independiente del escenario de cierre del resto de la sesión.

## Análisis H2 (segundo punto de evidencia)

Ver `validation-suite/level-b/anavi-macro-pad-12/metrics.md` §Análisis H2
para el detalle completo. Resumen: el diagnóstico de 31c ("vías mal
calibrado para bases pequeñas") se confirma parcialmente — con una base
15x mayor, el mismo umbral relativo (±20%) pasa a estar justo en el
borde en vez de fallar por +200%. Apoya normalizar el umbral por tamaño
de base en la revisión post-sesión 33, no cambiar el número en sí.
Dimensión nueva: un solo net puede dominar el delta agregado de vías
(GND explicó +8 de +6 netos) — candidato a análisis en sesión 33.

## Gates de cierre

- Suite offline (`pytest -m "not integration"`): pendiente de correr
  antes del merge (sin cambios en `src/` esta sesión).
- Suite integration: pendiente de correr antes del merge.
- Gate GUI del DoD: **2/2 × 2/2 verde**, corrido una sola vez al inicio
  (Bloque A, D-31c.1 — sesión no tocó `src/`).
- `AskUserQuestion` al arquitecto antes de mergear: pendiente.

## Próxima sesión

**Sesión 33 = Nivel C.** Candidato tentativo (a confirmar siguiendo el
patrón de verificación de 32, no prescribir uno solo): PortaPack H1 con
fork migrado, HackRF One como frontera refutatoria. Antes de arrancar 33,
considerar si F-V2-REFILL-SILENCIOSO amerita una sesión de fix
intermedia (32b-style) dado que es P0/P1 y reproducible.
