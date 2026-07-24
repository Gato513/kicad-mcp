# Dogfooding Etapa 1 — Colocar y rutear una placa real con kicad-mcp

**QUÉ ES ESTA SESIÓN:** NO es una sesión de desarrollo. Vas a USAR el
servidor MCP `kicad-mcp` (sus tools están conectadas a esta sesión) para
colocar y rutear una placa real del humano. Sos el primer usuario real
de la herramienta, y tu experiencia de uso es el producto principal.

**PROHIBIDO:** editar el repositorio de kicad-mcp. Si una tool falla o
te falta algo, se REGISTRA en el log de fricciones, no se arregla. Si
una tool devuelve un error, leé el hint y actuá según él — así se
diseñó la herramienta y estamos midiendo si ese diseño funciona.

**ENTREGABLES (en orden de importancia):**
1. `/tmp/dogfood-fricciones.md` — el registro de fricciones (ver abajo).
2. La placa colocada y ruteada hasta donde llegues, con DRC limpio si
   es posible, y exports generados.
3. Un resumen final honesto de qué tan usable es la herramienta.

---

## El trabajo

El humano preparó una copia descartable de un proyecto real suyo en la
ruta indicada por `KICAD_MCP_PROJECT`, con el esquemático terminado, F8
ejecutado (los footprints existen en el board, sin colocar o mal
colocados), y KiCad abierto con el PCB Editor cargado.

Tu objetivo, en fases:

1. **Reconocimiento.** `health` primero. Después
   `get_world_context(kind="pcb", focus_ref=…, max_tokens=…)` —
   **SIEMPRE con focus y budget** (empezá con max_tokens≈2000; sin
   focus, un board mediano puede pedir miles de tokens). Explorá por
   zonas si hace falta. Entendé qué componentes hay y cómo se conectan
   (las nets del TOON).
2. **Plan de colocación.** Antes de mover nada, escribí tu plan: qué
   agrupás (desacoples junto a su IC, conectores al borde, cristal
   junto al micro), qué restricciones ves. Pedile al humano
   confirmación del plan en una frase (él conoce la placa).
3. **Colocación.** `move_footprint` componente por componente,
   encadenando `base_snap` (el confirm de cada mutación te da el snap
   nuevo; usá `get_context_delta` para verificar en vez de re-leer el
   mundo entero — es 10-100× más barato).
4. **Inspección visual.** `export_render` (pcb_png) para VER el board.
   Usalo con criterio (cuesta ~11 s): tras terminar la colocación, y
   tras hitos de ruteo — no tras cada movimiento.
5. **Ruteo.** `add_track` + `add_via`. Rutea primero poder/tierra, después
   señales. No busques perfección: buscá DRC limpio y conexiones
   completas. Si el ruteo manual por tool se vuelve impracticable,
   REGISTRALO con detalle (cuántas tracks llevás, cuánto tiempo/tokens
   por conexión) — ese dato decide si integramos un autorouter.
6. **Validación.** `run_drc` iterativo. Arreglá lo que reporte.
7. **Cierre.** Con DRC limpio: `export_manufacturing` (pasa por el Gate
   G3). Render final. Resumen.

Si algo bloquea una fase (bug, límite de la herramienta, KiCad busy),
registrá la fricción, contale al humano el estado y qué necesitás de
él, y seguí con lo que puedas.

---

## El registro de fricciones (el entregable que más importa)

Creá `/tmp/dogfood-fricciones.md` AL INICIO y andá agregando entradas
EN EL MOMENTO en que ocurren (no reconstruyas al final — la memoria
edulcora). Formato por entrada:

```
## F-NN · [hora] · [tool o fase]
**Qué pasó:** (literal: el error, el output confuso, la espera)
**Qué esperaba:** (qué habrías necesitado que pasara)
**Workaround:** (cómo seguiste, si pudiste)
**Costo:** (tokens/tiempo/turnos perdidos, estimado)
**Severidad:** bloqueante | molesto | cosmético
```

Registrá TODO, incluyendo lo que te dé vergüenza ajena admitir:
- Errores de tools con hints que no alcanzaron para destrabarte.
- Cada vez que quisiste una tool que no existe (¡especialmente estas!
  p. ej. "quise borrar una track mal puesta y no hay tool de borrado",
  "quise rotar un footprint", "quise ver las design rules").
- Cada vez que el TOON no te dio la información que necesitabas o te
  costó interpretarlo.
- Cada vez que gastaste tokens de más (re-lecturas evitables, payloads
  gordos).
- Latencias que rompieron tu flujo.
- Cosas que funcionaron sorprendentemente BIEN también (sección aparte
  al final: "Aciertos") — sirven para no romper lo que funciona.

**Momentos de fricción ≠ fracaso.** Un dogfooding sin fricciones
registradas es un dogfooding mal hecho.

---

## Presupuesto y disciplina de contexto

- Reportá al final: tokens totales estimados consumidos en tools
  (sumá los tokens_est de los logs si podés, o estimá por conteo de
  llamadas), número de llamadas por tool, y tiempo total de sesión.
- Preferí siempre: delta > mundo con focus > mundo completo.
- Si un board chico igual te obliga a pedir el mundo completo varias
  veces, eso es una fricción de primera clase: registrala.

## Resumen final (última sección del log de fricciones)

1. ¿Hasta dónde llegaste? (colocado %, ruteado %, DRC, exports)
2. Las 3 fricciones más caras, con tu propuesta de qué tool o cambio
   las eliminaría.
3. Veredicto de ruteo (D-R3 de la hoja de ruta): ¿el ruteo por
   add_track/add_via es viable para placas de 10-60 componentes, o
   hace falta un autorouter? Con números (tracks/hora, tokens/track).
4. ¿Qué harías distinto en el Dogfooding Etapa 2?
5. Nota de usabilidad global 1-10 con justificación de una línea.
