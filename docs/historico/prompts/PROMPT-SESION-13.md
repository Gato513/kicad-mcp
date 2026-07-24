# Sesión 13 — Spike de autorouting (D-R11)

**Tipo:** SPIKE. Todo en `scratchpad/spike-autoroute/`. CERO código de
producción, CERO dependencias en pyproject (F5), CERO ediciones fuera de
scratchpad salvo el reporte. El entregable es un VEREDICTO con números,
no una feature.
**Rama:** `sesion-13` (desde `master`). Commits solo de scratchpad/docs.
**Entorno:** KiCad 10.0.4 vivo + un proyecto de spike que el humano
preparó en `/tmp/spike-route-proyecto/` (copia de una placa real suya de
~27 footprints, sch completo, F8 hecho, SIN rutear o con ruteo parcial).
Las tools MCP de kicad-mcp están disponibles — USALAS donde sirvan
(`draw_board_outline` si falta el contorno, `save_board`, `run_drc`
presupuestado, `get_component_detail`).

Leé antes: `docs/HOJA-DE-RUTA-V2.1.md` (D-R3/D-R11),
`docs/sesiones/dogfood-fricciones.md` (F-09 y el veredicto de ruteo con
números — ese es el problema a resolver) y
`docs/sesiones/12-reporte.md §7` (lo que esta sesión hereda: loop de
escritura cerrado, DRC barato, contención IPC).

---

## La pregunta que este spike responde

El Dogfooding 1 midió que el ruteo manual por LLM no es viable
(~300 tok/track, 13 shorts en el subconjunto fácil, 25-40 turnos
extrapolados). La pregunta: **¿existe un camino de autorouting headless
integrable en KiCad 10 que produzca ruteo completo con DRC limpio en una
placa de 10-60 componentes, y a qué costo?**

Candidato principal: **Freerouting** (Java, headless:
`java -jar freerouting.jar -de in.dsn -do out.ses -da…`). Candidato a
descartar rápido: router interno de KiCad vía IPC (casi seguro no
expuesto — verificá y cerrá con evidencia en <30 min).

## El problema real a resolver: el round-trip DSN/SES sin GUI

Freerouting habla Specctra: necesita un **DSN de entrada** (export del
board) y devuelve un **SES** que hay que **importar de vuelta**. En la
GUI de KiCad ambos existen (File → Export/Import Specctra). El spike
vive o muere por hacerlos SIN humano. Caminos a inventariar CON
EVIDENCIA (probados, no leídos):

1. `kicad-cli pcb export --help` — ¿existe subcomando specctra/dsn en
   10.0.4? ¿E import?
2. El módulo Python SWIG de KiCad (`pcbnew`): ¿sigue empaquetado en
   KiCad 10 en Arch? (`python -c "import pcbnew"` con el python del
   sistema, no el del venv). Históricamente expone
   `ExportSpecctraDSN`/`ImportSpecctraSES`. Si funciona: es un proceso
   hijo aparte (python del sistema), NO una dependencia del proyecto —
   anotá las implicancias (fragilidad, deprecación anunciada de SWIG)
   para el veredicto.
3. El plugin oficial de Freerouting para KiCad (gestor de plugins):
   ¿cómo hace el round-trip en KiCad 10, es invocable sin GUI?
4. Cualquier otro camino que encuentres (con evidencia).

Si NINGÚN camino headless funciona, el veredicto es "no integrable hoy"
con la evidencia — eso también es un resultado válido del spike.

## Requisito de sistema (coordinar con el humano)

Freerouting necesita Java. Verificá `java -version`; si falta, dale al
humano el comando exacto de Arch (`sudo pacman -S jre-openjdk` o el que
corresponda) y el link de release del jar
(github.com/freerouting/freerouting/releases — descargalo a
`scratchpad/spike-autoroute/`). Nada de esto entra a pyproject: si el
veredicto es integrar, Java+jar serán requisito de sistema documentado
(como kicad-cli), decisión del humano en la 14.

## Protocolo del spike (una vez resuelto el round-trip)

Sobre `/tmp/spike-route-proyecto/` (¡verificá que sea la copia, no el
original!):

1. Estado inicial: `run_drc` (baseline), conteo de nets sin rutear,
   render inicial.
2. Si falta contorno: `draw_board_outline` + `save_board`.
3. Export DSN → Freerouting headless (medí tiempo de router) → import
   SES → `save_board` si aplica → `run_drc` final → render final.
4. Repetir la corrida completa 2 veces para ver estabilidad.

## Métricas obligatorias del veredicto

- **Completitud:** % de ratsnest ruteado (nets ruteadas / total).
- **Calidad:** DRC post-route (errores por tipo, con el run_drc
  presupuestado); ¿quedaron shorts/clearance?
- **Tiempo:** wall-clock del round-trip completo y del router solo.
- **Costo de contexto:** tokens consumidos por el agente para orquestar
  una corrida (debería ser ~decenas: el router no habla con el LLM).
- **Fricción de integración:** pasos frágiles del round-trip, y qué
  superficie tendría la tool (`route_board(policy?)` → confirm) si se
  integra.
- **Comparación contra el baseline del Dogfooding 1:** tabla
  ruteo-LLM vs autorouter en tokens, tiempo, shorts.

## Entregables

1. `scratchpad/spike-autoroute/informe.md` con: inventario de caminos
   (evidencia por camino), el camino elegido, las métricas, los renders
   antes/después (rutas en /tmp), y tu recomendación argumentada:
   INTEGRAR (con qué diseño y qué requisitos de sistema) /
   NO INTEGRAR (por qué, y qué alternativa queda para el paso 7).
2. Reporte de sesión estándar en `docs/sesiones/13-reporte.md` — breve,
   apuntando al informe. (Regla nueva del proceso: el reporte SIEMPRE
   queda en docs/sesiones/ en el commit final, no solo en el chat.)
3. Los scripts del round-trip en scratchpad, ejecutables, para que la
   sesión 14 los promueva a producción si el veredicto es integrar.

## Fuera de scope

- Construir la tool de producción (eso es la 14, si el veredicto da).
- Tocar pyproject, specs, goldens.
- Optimizar el resultado del router (ajuste fino de perfiles de
  Freerouting: probá el default y A LO SUMO un perfil alternativo si el
  default decepciona — no es una sesión de tuning).

## Reporte final

El informe del spike ES el reporte. Además: dudas abiertas y qué
necesita la sesión 14 (integración o plan B) del humano y del
arquitecto.
