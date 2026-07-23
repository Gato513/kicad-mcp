# Sesión 21 — Fix P0 (F-D3-01, F-D3-03) + P1 (get_footprint_neighbors)

**Tipo:** DEV sobre kicad-mcp, **nueva rama** `sesion/21-p0-p1-hardening`
desde `master` (tras merge del Dogfooding 3).

**Origen:** CONTEXT v4 §Backlog priorizado v4. Dos bugs P0 detectados en
el Dogfooding 3 son bloqueantes para calidad de referencia (riesgo de
placas con shorts físicos reales invisibles) + una tool P1 identificada
como necesaria (reduciría 30 min de cirugía a ciegas).

**Filosofía de la sesión (vinculante):** hardening conservador. Cada fix
trae test de regresión que impide reintroducción. Cero refactoring
oportunista. Cero features adicionales. Cero mezcla con items P3/P4 aunque
sean rápidos. **La sesión 21 es exclusivamente 3 items.**

**Criterio de cierre (gate):** los 3 items cerrados con:
- Test unit + integration_gui verde que reproduce el escenario del bug
  y demuestra que el fix funciona.
- Test de regresión que fallaría si el bug volviera.
- Verificación en vivo contra KiCad 10.0.4 real (no solo fake-bridge).

## Fronteras

F1–F5 vigentes. F4: KiCad 10.0.4. **Adicional para esta sesión:**
- Cero cambios a la superficie pública de tools ya existentes salvo lo
  estrictamente necesario para cerrar los P0.
- Cero renombramiento de códigos de error (F3).
- Cero optimización de rendimiento oportunista.
- Cero limpieza de código no relacionada con los 3 items.

---

## Tarea 21.1 — Fix F-D3-01: `add_zone`/`fill_zones` respeta hole clearance contra PTH/NPTH

### Diagnóstico del D3

El fill que produce `add_zone(fill=true)` respeta correctamente los pads
SMD ajenos pero no respeta agujeros PTH/NPTH ajenos. Clearance real
computado contra pads con drill = 0.0000mm. Confirmado empíricamente
sobre ANT1 (PTH) y los 3 agujeros mecánicos NPTH de J1 en el D3.

El refill interno de `route_board` (`zones.refilladas:1`) dispara el
mismo bug al recalcular la zona post-ruteo. Los tracks nuevos de nets
ajenos quedan con 0.0000mm contra el plano GND (D3 F-D3-03 lo enmascaró
por coincidencia numérica del total DRC).

### Investigación previa obligatoria (timebox: 45 min)

Antes de codear el fix, entender el pipeline actual. Reportar en
`docs/investigacion/21-fill-zones-holes.md`:

1. **Dónde vive el fill computation.** ¿Es kipy quien fillea? ¿Es `pcbnew`
   vía subprocess? ¿Es una operación IPC dedicada?
2. **Qué reglas del proyecto lee el fill actual.** Cross-check con la
   lectura de sesión 17 (`rules_reader.py`). ¿Está usando el mismo
   pipeline o hay otro camino?
3. **Cómo modela un pad con drill vs un pad SMD.** ¿Es el mismo tipo
   `Pad` con `drill` opcional, o son tipos distintos? ¿El clearance rule
   se resuelve por type o por presencia del drill?
4. **¿El bug está en el clearance rule mismo o en el modelo geométrico
   del pad?** Diferenciar: (a) la regla se lee correctamente pero se
   aplica solo al copper del pad no al drill, vs (b) la regla se ignora
   sistemáticamente para pads con drill.

Si la investigación revela que el bug es de kipy 0.7.1 (no de kicad-mcp),
la estrategia cambia. Reportar al humano vía `AskUserQuestion` antes de
proceder — el fix podría ser un workaround post-fill en vez de un fix del
pipeline.

### Diseño del fix (post-investigación)

Depende del hallazgo. Escenarios probables:

- **Si el bug es que `add_zone`/`fill_zones` no pasan la geometría del
  hole al computador de clearance:** fix en el bridge, agregando el
  hole radius al set de exclusion regions.
- **Si el bug es que kipy no expone la API correcta:** workaround
  post-fill que trace el fill result contra los holes de otros nets y
  aplique substracción manual.
- **Si el bug es específico del refill interno de `route_board`:** fix
  ahí + regression test que reproduzca el escenario del D3.

### Test de regresión obligatorio

Reproducir empíricamente el escenario del D3:
- Board sintético con: (a) un pad PTH de net_a cerca de la zona, (b) un
  agujero NPTH (mounting hole) de net_a cerca de la zona, (c) una zona
  de net_b (por ejemplo GND) cubriendo el área.
- `add_zone(net="GND", ..., fill=true)`.
- `run_drc()` debe reportar 0 errores de `hole_clearance` y `clearance`.
- `get_zones()` debe reflejar el fill correcto (con muescas alrededor de
  los holes).

**Test debe fallar antes del fix, pasar después.** Comitear ambos estados
como evidencia si es didáctico.

### Verificación en vivo

Reproducir el caso del D3 sobre el fixture `despertador-routed` regenerado:
- Restaurar fixture al estado del D3 (plano GND uniforme, pre-workaround).
- Recomputar `fill_zones()`.
- `run_drc()` debe reportar 0 errores (antes del fix reportaba 6).

---

## Tarea 21.2 — Fix F-D3-03: `route_board.drc.err_introducidos` compara identidad, no totales

### Diagnóstico del D3

El contrato JSON de `route_board` (D-17.1) reporta:
```json
"drc": {
  "err_preexistentes": 56,
  "err_post": 56,
  "err_introducidos": 0    // FALSO
}
```

En el D3, las 56 pre-route eran `unconnected_items`; las 56 post-route
eran `clearance:38 + hole_clearance:15 + copper_edge_clearance:3`. Total
coincide, composición 100% diferente. `err_introducidos` es la resta de
totales, no la diferencia de conjuntos.

El contrato existe **exactamente para evitar que el agente re-verifique**.
Que mienta anula su propósito.

### Diseño del fix

Cambiar el cómputo de `err_introducidos` de resta de totales a comparación
de identidad. Cada violación DRC tiene:
- `type` (ej: `clearance`, `hole_clearance`, `unconnected_items`)
- `severity`
- `pos` (coordenadas, con tolerancia de comparación por precisión)
- `items` (referencias a los ítems involucrados)

**Identidad de violación** = tupla `(type, pos_rounded_to_0.1mm, sorted_items)`.
Dos violaciones son "la misma" si su identidad coincide. Puede haber
falsos positivos residuales por reruteo (una violación pre-route "misma
identidad" que persiste puede tener coordenadas ligeramente distintas si
el track ofensor se movió); documentar la tolerancia elegida.

`err_introducidos` = `|post - pre|` como conjuntos de identidades.
`err_resueltos` = `|pre - post|` (bonus: cuántas violaciones pre-route se
resolvieron con el ruteo).

Contrato JSON extendido:
```json
"drc": {
  "err_preexistentes": <int>,
  "err_post": <int>,
  "err_introducidos": <int>,        // NUEVO: identidad, no total
  "err_resueltos": <int>,           // NUEVO: cuántas pre-route se cerraron
  "por_tipo_introducidos": {...}    // NUEVO: desglose de las nuevas
}
```

Los 3 campos nuevos deben coexistir con el comportamiento anterior — NO
renombrar `err_introducidos`. La semántica cambia (de resta de totales a
resta de conjuntos) y ese cambio se documenta en `tool-catalog.md`.

### Test de regresión obligatorio

Test unit con violaciones DRC sintéticas donde el total coincide pero la
composición no:
- 3 violaciones pre-route de tipo A.
- 3 violaciones post-route de tipo B (identidad completamente distinta).
- Con la lógica vieja: `err_introducidos = 0` (bug).
- Con la lógica nueva: `err_introducidos = 3`, `err_resueltos = 3`.

Test integration_gui que reproduce el escenario del D3 en vivo sobre el
fixture regenerado.

### Consideración adicional: causa raíz común con 21.1

F-D3-03 fue disparado por F-D3-01 (el refill interno de zona metió las
53 violaciones nuevas). Si 21.1 cierra bien F-D3-01, el escenario del
D3 no debería producir violaciones nuevas — pero 21.2 sigue siendo
necesario para cualquier escenario futuro donde `route_board` sí
introduzca violaciones legítimas (ej: un ruteo denso con clearance
violations reales que el router no pudo evitar).

---

## Tarea 21.3 — P1: nueva tool `get_footprint_neighbors`

### Motivación

D3 F-D3-04: 35 min y 5 intentos en corredor J1↔borde↔agujeros, en gran
parte porque no había forma de saber qué había alrededor de J1 sin
reconstruir el mapa a mano con `get_tracks(bbox=)` iterativo.

### Firma propuesta

```
get_footprint_neighbors(
  ref: str,
  radius_mm: float = 5.0,
  include_pads: bool = True,        # pads de otros footprints
  include_tracks: bool = True,      # segmentos de cobre
  include_vias: bool = True,        # vías
  include_holes: bool = True,       # PTH/NPTH holes propios y ajenos
  include_edge: bool = True,        # distancia al borde del board si <radius
  max_tokens: int | None = None
) -> JSON
```

### Devuelve

```json
{
  "ref": "J1",
  "center": [x, y],                 // centroide del footprint
  "bbox": [min_x, min_y, max_x, max_y],
  "neighbors": {
    "pads": [
      {"ref": "R3", "pad": "1", "at": [x,y], "net": "+3V3", "dist_mm": 2.3}
    ],
    "tracks": [
      {"id": <kiid>, "net": "/MOSI", "layer": "F.Cu",
       "closest_point": [x,y], "dist_mm": 1.8}
    ],
    "vias": [...],
    "holes": [
      {"kind": "npth", "at": [x,y], "diameter_mm": 1.0,
       "belongs_to": "J1", "dist_mm": 0.5}
    ],
    "edge": {
      "closest_edge": "right",
      "dist_mm": 0.5
    }
  }
}
```

Distancia = mínimo entre bbox del footprint y el ítem vecino.

### Restricciones de diseño

- Read-only, sin mutación.
- Sujeto al guard `live_stale` como el resto de las lecturas.
- Presupuesto de tokens como `get_tracks` (D-V3.2). Si el radio incluye
  demasiado → `CONTEXT_BUDGET_IMPOSSIBLE` con hint de achicar radius.
- **NO reinventar geometría**: reutilizar helpers existentes de
  `get_tracks`, `get_component_detail`, `get_zones`.

### Tests

- Unit: escenarios sintéticos con vecinos en cada dirección.
- Unit: escenarios con edge cercano, con holes propios, con holes ajenos.
- Unit: presupuesto de tokens (radius grande → error).
- Integration_gui: sobre el fixture `despertador-routed` regenerado,
  invocar sobre J1 y verificar que devuelve los 3 agujeros NPTH propios,
  el borde derecho a ~0.5mm, y los pads vecinos.

**NO agregar test que dependa de tolerancias exactas de fill de zona**
(21.1 lo cubre por separado).

---

## Fuera de alcance (mandatorio respetar)

- CRUD de sch (R12) — diferido a P3.
- F-19b-12 (`run_erc` ÷100) — diferido a P3.
- F-19b-10 (`get_pin_net_membership`) — diferido a P3.
- F-19b-06 / D-19e.2 (`#PWR`/`#FLG` filter) — diferido a P3.
- **F-D3-05 (`delete_track` reporta net incorrecto en confirmación)** —
  cosmético, diferido a P3. NO tocar en esta sesión aunque el fix sea
  trivial: el humano fue explícito sobre no mezclar críticos con cosméticos.
- Cualquier feature nuevo no listado en 21.1/21.2/21.3.
- Optimización de rendimiento.
- Refactor de módulos existentes.

---

## Reporte final (`docs/sesiones/21-reporte.md`)

- **Reporte P4.0-style de investigación de F-D3-01** en
  `docs/investigacion/21-fill-zones-holes.md` (referenciado desde el
  reporte de sesión).
- Diff-resumen por tarea (21.1, 21.2, 21.3).
- Contratos finales: `route_board.drc` extendido, `get_footprint_neighbors`.
- Tests de regresión: cada bug tiene su test que fallaría si volviera.
- Verificación en vivo:
  - **21.1**: reproducir el escenario del D3 (plano uniforme, PTH+NPTH
    de otros nets) y confirmar 0 errores DRC.
  - **21.2**: ejercitar `route_board` sobre un caso donde el total DRC
    coincide pre/post pero composición cambia. Confirmar
    `err_introducidos > 0` cuando corresponde.
  - **21.3**: `get_footprint_neighbors("J1", radius_mm=5.0)` sobre el
    fixture del D3 → devuelve los 3 agujeros NPTH y el borde.
- **Estado de D-D3.2**: con los P0 cerrados, ¿la regla operacional
  "correr `run_drc()` manual después de cada `route_board`" queda
  revocada? Ratificar sí/no con evidencia.

## Env vars

```bash
export KICAD_MCP_GUI_TEST=1
export KICAD_MCP_PROJECT=/tmp/gui-test-project
export KICAD_MCP_GUI_REF=U1
export KICAD_MCP_FREEROUTING_JAR=/home/astra/.local/share/kicad/9.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.1.0.jar
```

En `~/.claude.json` como siempre. **Verificar que `KICAD_MCP_FREEROUTING_JAR`
está seteada antes de arrancar** — el D3 se bloqueó por esto (F-D3-02).

**KiCad reiniciado limpio.** `/tmp/gui-test-project/` restaurado desde
Desktop.

## Cierre esperado

Sesión 21 cerrada → sesión 22 = **Dogfooding 4 sobre el mismo despertador**
(variable controlada). Objetivo: ≥9/10 con los P0 cerrados. Si D4
confirma cierre real → escalar a placa distinta o despertador con
regulador externo (D5). Si D4 aparece con P0 nuevos → sesión 23 fix y
D5 con el mismo despertador.
