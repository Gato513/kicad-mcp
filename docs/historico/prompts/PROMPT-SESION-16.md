# Sesión 16 — P1: Visibilidad del cobre (get_tracks + cirugía por ID)

**Tipo:** DEV sobre el repo kicad-mcp.
**Origen:** Dogfooding 2 (7.5/10). F-13 costó ~50% de la sesión: el agente tuvo
que parsear el `.kicad_pcb` con Python externo para no rutear a ciegas.
**Criterio de cierre:** el patrón borrar→verificar→añadir ejecutable SIN parsear
el archivo por fuera de las tools.

## Fronteras (recordatorio — violarlas invalida la sesión)

F1: `toon-v1.md` NO se toca (get_tracks es tool nueva, no sección TOON).
F2–F5 vigentes: gates, catálogo de errores, KiCad 11, `pyproject.toml` solo con
aprobación. Todo error nuevo entra al catálogo con code + hint accionable.

## Entregables (en orden)

### 1. `get_tracks` — tool nueva de solo lectura

Firma: `get_tracks(net=None, bbox=None, layer=None, max_tokens=None)`
- Al menos un filtro obligatorio (`net`, `bbox` o `layer`); sin filtros →
  INVALID_PARAMS con hint (una placa real puede tener cientos de segmentos).
- Devuelve segmentos Y vías:
  - **Segmento:** `id`, `net`, `layer`, `width`, `start=[x,y]`, `end=[x,y]` (mm)
  - **Vía:** `id`, `net`, `at=[x,y]`, `size`, `drill`, `layers`
- **ID estable:** determinista mientras el board no cambie (propuesta: hash corto
  de (layer,start,end,width,net) o el UUID de KiCad si el IPC lo expone — decidir
  y DOCUMENTAR el contrato de estabilidad: los IDs se invalidan tras cualquier
  mutación de cobre o recarga; el agente debe re-listar tras mutar).
- Respeta presupuesto de tokens como get_world_context (mismo mecanismo, mismo
  error CONTEXT_BUDGET_* si no entra).
- Formato compacto estilo TOON pero NO dentro de TOON (tool separada, F1 intacta).
- Lee del board vivo; sujeta al guard `live_stale` como toda lectura de mundo.

### 2. `delete_track(id=)` / `delete_via(id=)` — selección por ID

- Nueva firma con `id` de get_tracks. La firma por coordenadas se CONSERVA
  (compatibilidad), pero:
- **Bug a arreglar:** el error de desambiguación promete `data.candidates` y no
  llega en la respuesta. Ahora debe llegar, y cada candidate trae su `id` →
  el agente resuelve la ambigüedad con una segunda llamada por ID.
- Si el `id` no existe (board mutado): error nuevo `TRACK_ID_STALE` con hint
  "re-listá con get_tracks".

### 3. `add_track` acepta pad + coordenadas mezcladas

- Caso real de reparación: desde un pad hasta un punto en el cobre.
- `add_track(from_pad="U1.1", to=[x,y], ...)` y viceversa deben funcionar.
- Hoy rechaza la mezcla (2 errores en el dogfooding). Mantener las firmas
  actuales (pad→pad, punto→punto) intactas.

### 4. Validación de colisiones: modelar roundrect

- El verificador interno de add_track trata los pads como rectángulos; los pads
  roundrect reales costaron 2 iteraciones DRC al agente.
- Modelar la esquina redondeada (radio del roundrect del pad) en el chequeo.
- Si el costo de implementación es alto: como mínimo, inflar el rectángulo con
  el clearance de la netclass y documentar la aproximación.

### 5. Tests E2E (gate de la sesión)

Sobre un board de fixture con cobre ruteado:
- a) `get_tracks(net="GND")` lista todos los segmentos+vías de GND con IDs.
- b) `get_tracks(bbox=...)` recorta correctamente (segmento que cruza el bbox
  aparece; el de afuera no).
- c) delete por ID borra exactamente ese segmento (verificar contra disco tras
  save).
- d) Desambiguación por coordenadas ambiguas → error CON candidates+IDs → delete
  por ID del candidate correcto.
- e) `add_track(from_pad, to=[x,y])` crea el segmento y el DRC no empeora.
- f) Escenario integrado F-13: net rota → get_tracks para ver el hueco →
  add_track pad→punto → DRC limpio. Sin tocar el .kicad_pcb por fuera.
- g) `TRACK_ID_STALE`: mutar el board entre list y delete → error correcto.

## Fuera de alcance (NO hacer en esta sesión)

- route_board (P2, sesión 17). No tocar su contrato aunque tiente.
- Recarga programática (P3, sesión 18).
- Zonas (P4, sesión 19).
- Cualquier sección nueva en TOON.

## Reporte final requerido

- Tools nuevas/modificadas con firmas finales.
- Errores nuevos añadidos al catálogo (code + hint).
- Contrato de estabilidad de IDs documentado (dónde quedó escrito).
- Resultado de los 7 tests E2E.
- Cualquier desviación de este prompt, con justificación.
