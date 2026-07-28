# Sesión 30 — Investigación P4.0-style del P1 solder mask ANT1

**Tipo:** investigación de causa raíz + eventual fix quirúrgico + eventual
test de regresión. **Primera sesión de Fase 4.** Nueva rama
`sesion/30-investigacion-solder-mask` desde `master` **post-merge de la
rama de docs de consolidación post-sesión 29** (que incluye cierre de
Fase 3 + formalización D-30.1 a D-30.4 + hoja-de-ruta-v5).

**Origen:** P1 vigente desde D4 (sesión 22, log de dogfoodings). Investigación
parcial completada en sesión 26
(`docs/historico/investigacion/26-solder-mask-ant1.md`) que cerró sin fix:
bug real y reproducible, pero el fix acordado no aguantó verificación
empírica y el mecanismo real no se aisló dentro del timebox de esa sesión.
D6/D7 confirmaron que el bug no bloquea el flujo canónico (el fixture
despertador usa `pad_to_mask_clearance=0`, no expuesto), pero es deuda
arrastrada de Fase 3 que Fase 4 debe cerrar antes del release Open Source.

**Contexto de Fase 4:** primera sesión bajo el nuevo marco. Aplica
principio D-30.2 (éxito por confianza, no por código) — un cierre honesto
sin fix es resultado válido si aumenta confianza en el proceso, análogo a
sesión 23 y sesión 26.

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4.

**Regla operacional específica de esta sesión:** D-30.1 aplica de manera
estricta. La sección "Estrategia de validación" abajo define hipótesis,
evidencia confirmatoria/refutatoria y protección contra regresiones ANTES
de tocar código. Si durante la sesión aparece que la hipótesis no encaja
con lo observado, `AskUserQuestion` obligatoria antes de continuar.

---

## Estrategia de validación (D-30.1)

**Hipótesis principal (H1):** el mecanismo de `solder_mask_bridge` de
KiCad involucra al menos una variable no identificada en sesión 26 —
candidatas listadas en §6 de la investigación previa: (a) apotema del
polígono del keepout auto-generado, (b) algoritmo de fill que privilegia
alguna condición sobre el máximo de clearances, (c) `SolderMaskMinWidth`
u otra configuración avanzada no expuesta en `.kicad_pro`/`.kicad_pcb`
estándar, (d) chequeo de máscara sobre proyección intermedia distinta al
polígono de fill real. Aislar cuál (o cuáles) intervienen es el objetivo.

**Hipótesis secundaria (H2):** si H1 se aísla, existe un fix quirúrgico
implementable dentro del scope de un follow-up (extensión de
`enforce_hole_clearance` con nueva fórmula o segundo keepout específico
de máscara) que resuelve el bug para el rango realista de
`pad_to_mask_clearance` (0.20-0.30mm).

**Evidencia confirmatoria:**
- Para H1: experimento controlado o inspección de código fuente de KiCad
  que muestre exactamente qué variable adicional interviene y cómo se
  compone con las conocidas.
- Para H2: barrido de valores de `pad_to_mask_clearance` (0.20, 0.22,
  0.25, 0.30mm) con el fix candidato aplicado → 0 violaciones
  `solder_mask_bridge` en todos los casos.

**Evidencia refutatoria:**
- Para H1: si tras N experimentos aislantes (mínimo 3 con métodos
  distintos) el mecanismo sigue sin identificarse, cerrar honestamente
  como "mecanismo no aislable con recursos disponibles" — documentar lo
  aprendido, mantener P1 como deuda con nota explícita para el release,
  y proceder a sesión 31.
- Para H2: si el fix candidato solo resuelve algunos valores del rango
  (por ejemplo, funciona para 0.30 pero falla para 0.22), tratar como
  refutación parcial — revertir y volver a diseñar.

**Protección contra regresiones:**
- Si el fix aterriza: test de regresión análogo a sesión 24, con barrido
  de valores de `pad_to_mask_clearance` (0.0, 0.20, 0.22, 0.25, 0.30mm)
  sobre fixture sintético reproducible por helper runtime (D-24.1).
- Test es **gate del merge** — no aceptable mergear sin él.
- Además: fixture despertador se re-valida (`pad_to_mask_clearance=0`,
  esperado sin cambio de comportamiento) — verificar que el fix no
  introduce regresión en el flujo canónico.

**Criterio de refutación limpio:** si tras 3 bloques de investigación
(120 min máximo) el mecanismo no se aísla, la sesión cierra con reporte
de causa raíz identificada parcialmente + P1 documentado como bug
conocido con umbral (`pad_to_mask_clearance ≥ 0.22mm`). NO se fuerza fix
prematuro.

---

## Preparación (antes del Bloque 1)

1. Verificar que la rama de docs post-D7 ya está mergeada en `master`.
2. `git checkout master && git pull`.
3. `git checkout -b sesion/30-investigacion-solder-mask`.
4. `/tmp/gui-test-project/` NO se toca en esta sesión (el bug no depende
   del despertador — se investiga sobre boards sintéticos y sobre copias
   del fixture con `pad_to_mask_clearance` modificado).
5. **Lectura obligatoria** antes de arrancar:
   - `docs/historico/investigacion/26-solder-mask-ant1.md` completo —
     esta sesión NO reinventa lo que ya se investigó. §1-§6 son la base
     de partida.
   - `docs/DECISIONES.md` D-30.1 completa.
   - `src/kicad_mcp/bridge/ipc.py` líneas 1902-2036
     (`enforce_hole_clearance`) — sin modificar.
   - `src/kicad_mcp/bridge/rules_reader.py` — extensión hecha en sesión
     26 (lectura de `pad_to_mask_clearance` y
     `solder_mask_to_copper_clearance`), reutilizable.

6. **Consideración operacional específica de Fase 4:** si la
   investigación requiere inspeccionar código fuente de KiCad
   (`pcbnew`/`kicad-cli`), el agente ejecutor puede clonar el repositorio
   de KiCad en `/tmp/kicad-source/` (no dentro del repo del proyecto).
   La lectura de código externo es lectura, no dependencia — no viola F5
   (dependencias en `pyproject.toml`). Si se hace, documentar la versión
   exacta consultada (tag/commit) en el reporte de sesión.

---

## Bloque 1 — Reproducción y calibración del harness (timeout: 30 min)

**Objetivo:** confirmar que el bug sigue siendo reproducible con el
harness de sesión 26 y calibrar el entorno de trabajo.

### Pasos

1. Reproducir la evidencia de §3 de sesión 26: sobre copia del fixture
   `despertador-routed` con `pad_to_mask_clearance` modificado a 0.22mm
   → `kicad-cli pcb drc --refill-zones --save-board` → verificar que
   aparece `solder_mask_bridge` en ANT1 vs Zone GND (esperable según
   sesión 26). Si no aparece, algo cambió y hay que investigar antes de
   continuar.
2. Reproducir §5 de sesión 26: aplicar el fix intentado (radio del
   keepout = 1.82mm por fórmula, radio efectivo del cobre 1.50 +
   `pad_to_mask_clearance` 0.30 + margen 0.02 = 1.82) → verificar que
   la violación persiste (esperable, ese fue el hallazgo).
3. Reproducir §6 de sesión 26: barrido de radio de keepout (1.82, 2.0,
   2.5, 3.0mm) → confirmar umbral entre 1.82 (falla) y 2.0 (resuelve).

### Salida esperada del Bloque 1

Confirmación de que el harness reproduce el estado documentado en sesión
26. Cualquier discrepancia se registra y se investiga antes de continuar.

Si todo reproduce como esperado, el Bloque 2 arranca con base sólida.

---

## Bloque 2 — Investigación empírica del mecanismo (timeout: 90 min)

**Objetivo:** aislar cuál (o cuáles) de las 4 variables candidatas
identificadas en sesión 26 interviene en el chequeo de
`solder_mask_bridge` de KiCad. Aplicar D-30.1: cada línea de investigación
formulada como sub-hipótesis con evidencia confirmatoria/refutatoria.

### Sub-línea 2.1 — Apotema del polígono del keepout (30 min)

**Sub-hipótesis:** el chequeo de `solder_mask_bridge` en KiCad compara
contra el polígono del keepout (16-gono con apotema = r·cos(π/16) ≈
r·0.9808), no contra un círculo ideal de radio r. La apertura de máscara
del pad (círculo real, r_mask = r_cobre + `pad_to_mask_clearance`) puede
"asomar" por el punto medio de una arista del keepout aunque los
vértices estén más lejos.

**Prueba:** aumentar la resolución del polígono del keepout (32, 64,
128 vértices) → si el umbral entre "falla" y "resuelve" **se reduce**
proporcionalmente hacia el valor "ideal" (r_v = r_mask + margen),
apotema es parte del mecanismo. Si no cambia, apotema no es la causa
principal.

**Confirma sub-hipótesis:** umbral converge a r_mask + margen con
polígono de 128 vértices.

**Refuta sub-hipótesis:** umbral sigue en ~2.0mm independiente de la
resolución del polígono.

**Nota:** sesión 26 §6 formuló esta hipótesis pero no la testeó
directamente. Solo aritmética consistente. Bloque 2.1 la testea
empíricamente.

### Sub-línea 2.2 — Algoritmo de fill de KiCad (30 min)

**Sub-hipótesis:** el algoritmo de fill de KiCad no toma el máximo entre
el keepout explícito y la clearance natural del pad — puede privilegiar
uno sobre otro según alguna condición no aislada.

**Prueba:** experimento con dos configuraciones:
- (a) keepout radio r=2.0mm + `pad_to_mask_clearance=0.30mm` (r_mask=1.80mm)
  → esperable resolver.
- (b) sin keepout + `pad_to_mask_clearance=0.30mm` + clearance natural del
  pad de 0.5mm (borde del fill a 2.0mm del centro) → si el fill "usa" la
  clearance natural + margen suficiente, esperable resolver también.
  Si el fill NO usa la clearance natural y solo respeta el keepout
  explícito, (b) va a fallar.

**Confirma sub-hipótesis:** discrepancia entre (a) y (b) — algoritmo de
fill no maxifica.

**Refuta sub-hipótesis:** (a) y (b) dan mismo resultado — el fill sí
usa el máximo entre keepout y clearance natural.

### Sub-línea 2.3 — Inspección del código fuente de KiCad (30 min)

**Sub-hipótesis:** el chequeo de `solder_mask_bridge` en KiCad tiene una
lógica que no se puede inferir por experimento — inspección del código
fuente puede resolver la incógnita más rápidamente que N experimentos
adicionales.

**Prueba:** clonar KiCad 10.0.4 (tag correspondiente) en
`/tmp/kicad-source/`, localizar el chequeo de `solder_mask_bridge` en el
DRC engine, leer la lógica.

Comandos de referencia (no ejecutar tal cual, adaptar según lo que
aparezca):
```bash
mkdir -p /tmp/kicad-source
cd /tmp/kicad-source
git clone --depth 1 --branch 10.0.4 https://gitlab.com/kicad/code/kicad.git .
grep -rn "solder_mask_bridge" pcbnew/drc/
grep -rn "SolderMaskMinWidth" pcbnew/
```

**Confirma sub-hipótesis:** encontrar la lógica exacta y las variables
involucradas.

**Refuta sub-hipótesis:** el código es tan intrincado o depende de tantas
variables que la lectura no aísla el mecanismo en 30 min.

### Coordinación entre sub-líneas

Las 3 sub-líneas se ejecutan **secuencialmente**, no en paralelo. Si 2.1
confirma la sub-hipótesis del apotema y explica todo el fenómeno, no es
necesario continuar con 2.2/2.3. Si 2.1 refuta, ir a 2.2. Si 2.2
también refuta, ir a 2.3.

Si las 3 sub-líneas se agotan (90 min) sin identificar el mecanismo,
Bloque 3 se salta y la sesión cierra con refutación honesta de H1.

---

## Bloque 3 — Propuesta de fix (timeout: 30 min, condicional)

**Condicional:** solo se ejecuta si el Bloque 2 identificó el mecanismo.
Si el Bloque 2 cerró con "no aislable", este bloque se salta.

**Objetivo:** diseñar un fix quirúrgico basado en el mecanismo aislado.

### Guías

1. Preferir extensión de `enforce_hole_clearance` sobre segundo keepout
   dedicado (misma preferencia que sesión 26).
2. Si el mecanismo del apotema fue confirmado, el fix puede ser:
   - Aumentar la resolución del polígono del keepout (más vértices).
   - Recalcular el radio del keepout considerando el apotema
     (r_v = r_deseado / cos(π/N) para N vértices).
3. Si el mecanismo del algoritmo de fill fue confirmado, el fix puede ser:
   - Emitir clearance mínimo del pad al DSN de manera que el fill
     respete la geometría correcta.
4. Si el mecanismo se descubrió por inspección de código KiCad, el fix
   se diseña específicamente para el chequeo identificado.

### Diseño

Aplicar D-30.1 al diseño del fix:
- Hipótesis: el fix diseñado resuelve el bug para el rango
  0.20-0.30mm de `pad_to_mask_clearance`.
- Evidencia confirmatoria: barrido de valores con test empírico.
- Evidencia refutatoria: si algún valor del rango sigue fallando.
- Protección contra regresiones: test de regresión con barrido en el
  gate del merge.

### Implementación

Si el diseño es sólido y el fix es <30 líneas de código, implementar en
el Bloque 3. Si es más grande, documentar el diseño y agendar sesión de
follow-up.

---

## Bloque 4 — Reporte y cierre (timeout: 30 min)

**Objetivo:** producir el reporte de sesión con la evidencia acumulada,
sea el resultado un fix aterrizado, un mecanismo identificado sin fix, o
un cierre honesto sin mecanismo identificado.

### Reporte

Archivar en `docs/historico/investigacion/30-solder-mask-ant1.md`
(continuación temática de `26-solder-mask-ant1.md`, no reemplazo).

Estructura:
- Resumen ejecutivo con el resultado (fix / mecanismo sin fix /
  refutación).
- Sub-líneas del Bloque 2 con evidencia de cada una.
- Comparación con sesión 26 (qué hipótesis se confirmaron/refutaron desde
  entonces).
- Si hubo fix: diff resumido + resultado del test de regresión.
- Si no hubo fix: recomendación explícita para P1 en el backlog (mantener
  vigente con nota, cerrar como bug conocido, agendar otra sesión, etc.).

### Deuda vigente actualizada

Si el fix aterrizó: cerrar P1 en `docs/BACKLOG.md`.
Si no aterrizó pero se identificó mecanismo: mantener P1 con notas
específicas sobre lo que se sabe.
Si no se identificó mecanismo: cerrar P1 como **bug conocido con umbral**
(`pad_to_mask_clearance ≥ 0.22mm`) — proyectos que usen ese valor o
mayor deben conocerlo.

### AskUserQuestion antes del merge

Igual que sesión 24 y sesión 27: diff completo + resultado del test (si
aplica) + reporte para revisión del arquitecto antes de mergear.

---

## Aplicación de D-30.2 en esta sesión

**Éxito por confianza, no por código.** Los 4 resultados posibles de
sesión 30 son válidos si aumentan confianza:

1. **Fix aterrizado con test de regresión** → confianza en la
   herramienta (P1 resuelto).
2. **Mecanismo identificado, fix documentado para sesión posterior** →
   confianza en el proceso (rigor mantenido, no forzamos código
   prematuro).
3. **Mecanismo no identificado en 90 min, P1 documentado con umbral** →
   confianza intelectual (honestidad sobre límites).
4. **Investigación revela algo distinto de lo esperado que amerita
   redirección** → confianza en la capacidad de detectar señales nuevas.

El resultado 3 sigue siendo aceptable — es el patrón sesión 23 y 26. NO
se fuerza fix bajo presión.

---

## Fuera de alcance

- Modificar `route_board`, `fill_zones`, `add_zone` (D-23.2 cerrado).
- Modificar el loop de vías de `enforce_hole_clearance` (D-23.3/R16).
- Arrancar cualquier validación externa de Validation Suite (sesión 31).
- Features nuevas.
- Escalada de complejidad (placas nuevas).
- Preparación de release Open Source.

## Env vars

Sin cambios respecto a sesiones anteriores. `KICAD_MCP_FREEROUTING_JAR`
puede seguir seteada aunque probablemente no se use (esta investigación
no requiere Freerouting).

## Cierre esperado

Sesión 30 cerrada con:

- Reporte en `docs/historico/investigacion/30-solder-mask-ant1.md`.
- Estado de P1 solder mask ANT1 actualizado en BACKLOG según resultado.
- Rama `sesion/30-investigacion-solder-mask` lista para merge (si hubo
  fix) o para archivar (si no hubo).

**Próxima sesión: 31 = primera validación de Validation Suite (nivel A).**
Arranca solo cuando sesión 30 esté mergeada / archivada con conclusión
clara.

**Recordatorio operacional:** primera sesión de Fase 4. Los principios
D-30.1 y D-30.2 son vigentes por primera vez en producción. Si aparece
tensión entre "escribir código" y "consolidar evidencia", elegir
consolidar.
