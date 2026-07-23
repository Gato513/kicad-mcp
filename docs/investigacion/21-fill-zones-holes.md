# Investigación 21.1 (F-D3-01/F-D3-03) — Fill de zona y hole clearance

**Sesión 21**, Fase A de la Tarea 21.1. Objetivo: entender el pipeline de
fill de zona de kicad-mcp y determinar la causa raíz de "clearance
0.0000mm contra agujeros PTH/NPTH" reportado en el Dogfooding 3
(`docs/dogfooding/dogfood3-fricciones.md`, F-01/F-03), para diseñar el fix
correcto (pipeline propio vs workaround post-fill vs limitación de kipy).

Entorno: KiCad **10.0.4** vivo (proyecto `gui-test-project`, copia de
trabajo del fixture `despertador-routed`), kipy vía IPC real (no mocks),
`pcbnew` (python de sistema) para scripts de investigación fuera de
kicad-mcp. F4 vigente: nada acá se extrapola a KiCad 11.

---

## 1. ¿Dónde vive el fill computation?

**100% delegado al motor de KiCad — no hay matemática de clearance del
lado de kicad-mcp.** Confirmado por lectura de código (no sólo inferencia):

- `add_zone` (`bridge/ipc.py:1665-1716`): construye un `Zone()` de kipy
  (outline, net, layers, priority) y, si `fill=True`, llama
  `raw_board.refill_zones()` — una única llamada IPC, sin parámetros de
  clearance.
- `fill_zones` (tool, `tools/pcb.py:2017-2072` → bridge
  `refill_zones`, `ipc.py:1766-1784`): idéntico — `raw_board.refill_zones()`
  sin argumentos, refillea TODAS las zonas de cobre del board (kipy 0.7.1
  no tiene fill selectivo por zona, documentado ya en sesión 19,
  `docs/investigacion/19-zonas-ipc.md` §1).
- El refill interno de `route_board` (`tools/pcb.py:2255-2261`) usa la
  MISMA función `bridge.refill_zones()`.
- Grep de `hole_clearance` en `src/`: **cero resultados**. kicad-mcp nunca
  lee ni razona sobre esa regla — el fill (y su clearance, incluida la de
  agujeros) es responsabilidad exclusiva del motor de KiCad invocado vía
  `Board.refill_zones()`.

## 2. ¿Qué reglas usa el fill?

El fill vive en el board **abierto en KiCad** (vía IPC), que carga sus
`BOARD_DESIGN_SETTINGS` directamente del `.kicad_pro`/`.kicad_pcb` al abrir
el proyecto — no hay un paso intermedio de kicad-mcp que inyecte o
sincronice reglas antes del fill (a diferencia de `autoroute.py:752`, que sí
inyecta reglas al DSN para Freerouting). `rules_reader.py` (sesión 17) sólo
lee `min_copper_edge_clearance` + netclass (`clearance`, `track_width`,
`via_diameter`, `via_drill`) para **otros** propósitos (colisión de
`add_track`, inyección DSN) — nunca se consulta para el fill. Confirmado
empíricamente (§4): `board.GetDesignSettings()` reporta
`m_HoleClearance=0.25mm` en el proyecto de prueba, consistente con lo
citado en el D3.

## 3. Modelo de pad: drill vs SMD

`PadDetail` (`ipc.py:133-152`) y `PadGeom` (`ipc.py:238-260`, usado por
`add_track` para colisión) **no leen el drill de los pads** — sólo tamaño
de cobre, posición, capa. El drill sólo se lee para **vías**
(`_kipy_copper_to_item`, `ipc.py:399`: `drill = it.padstack.drill`). Esto es
irrelevante para el fill en sí (que kipy delega 100% al motor de KiCad,
que sí tiene acceso al padstack completo incluido el drill vía su propio
modelo interno, no vía lo que kicad-mcp expone) — pero es **relevante para
21.3**, que si quiere reportar holes de pads necesita una lectura nueva.

## 4. Experimento discriminante — ¿"fresh" vs "refill" explican el bug?

### 4.1 Motor de fill en abstracto (pcbnew, sintético, fuera de kicad-mcp)

Se replicó el patrón de sesión 19 (`docs/investigacion/19-zonas-ipc.md`
§2.3): board sintético sobre `tests/fixtures/005_pcb_limpio` (copiado a
tmpdir, nunca mutado in-place), usando `pcbnew.ZONE_FILLER` (system
python). Un pad PTH (net_a, drill 1.0mm) + un pad NPTH mecánico (drill
1.0mm, sin net) + una zona GND cubriendo ambos.

**Resultado: clearance idéntica bit-a-bit** entre "pads antes del primer
fill" (fresh) y "zona rellena antes, pads agregados después, refill"
(orden invertido):

| | PTH (net_a) | NPTH (mecánico) |
|---|---:|---:|
| Fresh | 0.9005 mm | **0.2505 mm** |
| Refill tras agregar pads | 0.9005 mm | **0.2505 mm** |

`hole_clearance` del proyecto = 0.25mm → el NPTH midió 0.2505mm, correcto
dentro de ruido de precisión. **El motor de fill de KiCad, en abstracto, sí
computa hole clearance correctamente y es indiferente al orden
fresh/refill** cuando la geometría final es idéntica.

### 4.2 Contra el board real, vía el pipeline exacto de kicad-mcp

Se descartó reproducir con `route_board` (Freerouting) por costo/tiempo;
en su lugar se replicó el mecanismo EXACTO que usa `route_board`
internamente (`os.replace()` del `.kicad_pcc` en disco desde fuera de la
sesión IPC + `reload_board_from_disk()` + `refill_zones()`), usando
`pcbnew` para inyectar el ítem nuevo directo en el archivo — sobre una
copia de trabajo del fixture `despertador-routed` real (24 footprints,
ANT1/J1 con sus PTH/NPTH reales), restaurada desde el fixture golden antes
y después de cada experimento (nunca se tocó `tests/fixtures/` in-place).

Tres configuraciones probadas, todas con: zona chica creada+rellena PRIMERO
sobre un área verificada vacía (sin tracks/vías/pads/courtyards — el primer
intento se contaminó por no chequear courtyards, ver nota abajo), item
nuevo inyectado DESPUÉS directo en el `.kicad_pcb` (bypassing el guard IPC
`NET_ASSIGNMENT_MISMATCH` de `add_via`), `reload_board_from_disk()` +
`fill_zones()` (refill, sin recrear la zona) + `run_drc()`:

1. **Vía nueva, net distinto de la zona** → el via se reconcilió
   silenciosamente al net de la zona (GND) al hacer `revert()` — KiCad
   corrige el netcode de un ítem sin conexión propia (sin track) que queda
   embebido en cobre de otro net al recargar. **Hallazgo secundario**: un
   ítem "flotante" (sin conexión eléctrica propia) no sirve para testear
   mismatch de net vía inyección directa de archivo — KiCad lo resuelve
   antes de que el DRC lo vea.
2. **Pad PTH con net real pero no relacionado** (`Net-(ANT1-A)`, con
   conexión genuina en otro lugar del board — no flotante) → **0 errores
   de `hole_clearance`/`clearance`** tras refill.
3. **NPTH real (sin net, mecánico — igual que los 3 agujeros de J1)** →
   **0 errores de `hole_clearance`/`clearance`** tras refill (en la
   ubicación verificada limpia; un primer intento en una ubicación
   contaminada por el courtyard/pad real de BT1 sí mostró 1 violación de
   `hole_clearance`, pero de 0.2177mm vs 0.25mm requerido — un déficit de
   sólo 0.03mm consistente con proximidad real a un pad GND gigante de
   BT1, no con el patrón "0.0000mm total" del D3; se descartó como
   contaminación del test, no evidencia del bug).

**Ningún experimento controlado reprodujo el patrón "0.0000mm" del D3.**

### 4.3 Lectura honesta del resultado

Este es un **resultado negativo bien establecido, no una prueba de
ausencia de bug**. El log del D3 es un reporte de primera mano, con
`run_drc()` real mostrando 6 violaciones concretas (4×hole_clearance +
1×clearance + 1×solder_mask_bridge) contra ANT1 y J1, y — de forma más
grave (F-03) — 53 violaciones nuevas post-`route_board` con el mismo
patrón, resueltas de forma reproducible por el propio agente con
`delete_zone`+`add_zone(polygon=...)` fresco. No hay razón para dudar de
esas observaciones.

La diferencia entre mis experimentos (negativos) y el D3 (positivo) más
probable, en orden de sospecha:

1. **La zona original del D3 se creó y rellenó en un board con CERO
   footprints** ("Fase 1, ANTES de colocar componentes" — literal del log
   F-01). Mis experimentos siempre insertaron la zona de prueba en un
   board con las 23 OTRAS footprints reales ya presentes — nunca probé la
   condición "fill inicial sobre board completamente vacío". Esto pudo
   importar si el motor de fill cachea o inicializa su índice espacial de
   forma distinta cuando arranca de cero vs cuando ya hay geometría
   circundante compleja.
2. **El round-trip real de Freerouting** (`route_board`, DSN
   export→SES import) no se probó — sólo se replicó su mecanismo de
   reemplazo de archivo con una inyección quirúrgica simple. Es posible
   que el DSN/SES real deje el board en un estado sutilmente distinto
   (p. ej. reordenamiento de nets, reconstrucción de conectividad
   incompleta) que mi inyección directa no reproduce.
3. **Múltiples agujeros NPTH clusterizados** (J1 tiene 3, muy juntos) vs.
   mi prueba con 1 solo agujero aislado — no se probó si el fallo requiere
   la interacción de varias regiones de exclusión cercanas.
4. Algo específico de la **secuencia exacta de llamadas IPC** del D3 (fill
   Fase 1 → colocación Fase 2 → **ningún** refill intermedio hasta el
   `run_drc()` final) que mis pruebas, todas con refill explícito
   inmediatamente después de cada cambio, no capturan.

## 5. Conclusión y siguiente paso

**No se pudo aislar la causa raíz exacta dentro del timebox +
extensión razonable de esta investigación**, a pesar de un esfuerzo
sustancial (motor sintético vía pcbnew, 3 configuraciones vía el pipeline
real de kicad-mcp sobre el fixture real, restauración limpia entre cada
prueba). El motor de fill de KiCad, en las condiciones que sí pude probar,
computa hole clearance correctamente y es indiferente al orden
fresh/refill — lo que **descarta parcialmente** la hipótesis original
("todo refill de una zona preexistente ignora hole clearance") tal como
estaba formulada, pero **no descarta** que exista una condición más
específica (board vacío al fill inicial, round-trip real de Freerouting,
o clusters de agujeros) que sí la dispare — condición que es, además,
exactamente la que ocurrió en producción durante el D3.

Dado que F-01/F-03 son bugs P0 de seguridad física real (shorts
invisibles), y que la causa raíz sigue sin aislar con confianza, se activa
el gate mandatorio de la Fase A: **consultar al humano antes de diseñar el
fix**, en vez de adivinar un workaround sobre un mecanismo no confirmado.
Ver `AskUserQuestion` en la sesión para las opciones evaluadas.
