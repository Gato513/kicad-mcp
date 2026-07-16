# Sesión 12 — Flujo sch mínimo + Edge.Cuts + DRC presupuestado

**Rama:** `sesion-12` (desde `master`). Un commit por tarea. No pushear.
**Entorno:** KiCad 10.0.4 abierto con el PCB Editor sobre
`/tmp/gui-test-project/`, env vars, `verificar_entorno.py` verde. Gran
parte de esta sesión es trabajo sch en disco (kicad-skip), pero T4 y T5
necesitan el board vivo.

Leé antes: `CLAUDE.md`, `docs/HOJA-DE-RUTA-V2.1.md`,
`docs/sesiones/11-reporte.md` (§6: notas que esta sesión hereda) y el
diseño previo de `add_symbol` (sesión 08, `tools/sch.py`).

**Recordatorio F1 (validado la sesión pasada):** si algo necesita tocar
`docs/specs/toon-v1.md` u otro archivo denegado, se redacta el parche
para que el humano lo aplique — Opción A, como la 11. El humano ya
sincronizó la gramática de cabecera.

---

## Decisiones vinculantes del arquitecto

- **D-12.1 (`set_value` / `set_footprint`):** dos tools sch vía
  kicad-skip sobre disco, patrón `add_symbol`: validación de ref
  existente, G1 backup, write, **snapshot de DISCO post-write**
  (D-06.2), confirm ≤50 tok con snap nuevo, audit. Sanitización regla 6
  sobre `value`/`footprint_id` (van a un archivo). `set_footprint`
  valida formato `lib:name` pero NO que exista en librerías del sistema
  (no hay acceso; documentar la limitación — KiCad lo marcará en F8).
- **D-12.2 (`connect_pins` por labels, D-R6):** semántica: conectar
  `REF.PIN` ↔ `REF.PIN` colocando **labels locales con el mismo nombre**
  en las posiciones de los pines — práctica estándar de KiCad, no un
  hack; el nombre de la tool se queda. Spike PRIMERO (medio día máx):
  con kicad-skip sobre copia de `001_basico`, (a) obtener la posición
  absoluta de un pin de símbolo (¿kicad-skip la expone o hay que
  calcular origen+offset+rotación?), (b) crear el label local anclado
  ahí, (c) verificar con `kicad-cli sch erc` + export netlist que KiCad
  efectivamente netea los dos pines juntos. Si (c) falla, STOP y
  reportá — la tool no se construye sobre un spike rojo. Nombre de net:
  parámetro `net_name` obligatorio (el agente LLM elige nombres
  significativos; autogenerar invita a basura).
- **D-12.3 (hoja paleta, A3):** decisión de diseño con mi preferencia:
  la paleta es un archivo `paleta.kicad_sch` SEPARADO dentro del
  proyecto (no parte de la jerarquía), y `add_symbol` gana un parámetro
  opcional `source` que por defecto busca `paleta.kicad_sch` en la raíz
  del proyecto y clona DESDE ahí HACIA el sch destino (clone
  cross-file). El spike de D-12.2 verifica de paso si kicad-skip
  soporta clonar entre archivos; si NO lo soporta, fallback documentado:
  la paleta vive como región de símbolos en el propio sch (y `add_symbol`
  sigue clonando intra-archivo, como hoy). Entregable en cualquier
  caso: `docs/guia-paleta.md` — cómo el humano arma y mantiene su
  paleta (convenciones de nombres, un ejemplo mínimo con 5-6 símbolos
  típicos: R, C, LED, conector, regulador, MCU genérico).
- **D-12.4 (`reload_in_gui`, A5 — verificar honestidad primero):** la
  IPC de esquemático es KiCad 11 (F4), así que forzar la recarga del
  Schematic Editor probablemente NO sea posible en KiCad 10. Spike de
  1 hora máximo: buscá en kipy si existe algún comando de reload de
  documento agnóstico del editor. Si NO existe: A5 se cierra como
  "no factible en KiCad 10, diferido a 11", el hazard queda documentado
  en `guia-paleta.md` y el catálogo ("tras mutar el sch con KiCad
  abierto, el humano acepta el aviso de recarga"), y NO se construye
  nada. No inventes soluciones con xdotool ni similares.
- **D-12.5 (`draw_board_outline`):** tool que crea un contorno
  rectangular en Edge.Cuts vía IPC (`create_items` con el tipo gráfico
  que kipy exponga — verificá en el código instalado qué shapes
  soporta). Superficie mínima: `draw_board_outline(x_mm, y_mm,
  width_mm, height_mm)` — un rectángulo; formas complejas fuera de
  scope. Validación: si ya existe contorno → error tipado con hint
  (no apilar bordes); el header `outline:` de la sesión 11 te lo dice
  barato. Confirm ≤50, snapshot vivo post-mutación (patrón T5/D-08.2),
  y el loop cierra con `save_board`. Si kipy NO soporta crear gráficos
  → reportá con evidencia y la tool se difiere (no la fuerces por
  archivo: chocaría con el editor vivo).
- **D-12.6 (F-10: DRC presupuestado — tarea de NÚCLEO):** el T6 de la
  11 midió `run_drc` en 18 956 tokens / 42 s. Inaceptable (47× D4).
  Rediseño de la respuesta:
  - Modo default = RESUMEN: conteo por tipo de violación + las
    primeras N=5 muestras por tipo (con coords y, cuando el JSON de
    kicad-cli lo trae, nets/objetos involucrados). Presupuesto: ≤2 000
    tokens con 283 violaciones.
  - `exclude_types` (p. ej. `["unconnected_items"]`) y filtro de
    severidad que realmente excluya lo filtrado del payload.
  - Paginación para el detalle: `detail_type` + `offset`/`limit` para
    pedir violaciones completas de UN tipo por páginas.
  - Compatibilidad: los tests existentes de run_drc se adaptan; el
    Gate G3 usa el conteo total (sin cambio de semántica — G3 es F2,
    su lógica NO se toca, solo consume el mismo dato de siempre).
- **D-12.7 (contención IPC en suite):** documentar en
  `docs/pruebas-gui.md` el orden de corrida recomendado y el fenómeno
  (4 tests con AS_UNHANDLED transitorio bajo carga, pasan aislados).
  Si concluís que hace falta un marker `integration_gui_slow` para el
  loop de T6, proponelo en el reporte con la línea exacta de pyproject
  para que el humano la agregue (F5: vos no tocás pyproject).

---

## Orden sugerido

Fase 0 (verificador + suite) → T1 spikes (D-12.2a-c + D-12.4 + qué
soporta kipy para D-12.5; TODO en scratchpad, reportar veredictos antes
de construir) → T2 `set_value`/`set_footprint` → T3 `connect_pins` (si
spike verde) → T4 `draw_board_outline` (si kipy puede) → T5 DRC
presupuestado → T6 `guia-paleta.md` + doc D-12.7 + catálogo al día.

Tests por tool: unit con copias en tmp_path (regla 7) + verificación de
efecto SIEMPRE (D-06.3): re-leer el archivo/board y confirmar el cambio
(valor nuevo presente, label creado y neteo verificado vía netlist,
contorno presente). Para `connect_pins`, el test de oro es: dos pines →
tool → export netlist → ambos pines en la misma net con el nombre
pedido.

## Fuera de scope

- Autorouter (sesión 13, D-R11). Clearance-check (D-R10). Multi-hoja.
- `set_value`/`set_footprint` masivos (batch) — de a uno alcanza.
- Editar pyproject, specs, goldens (F1/F5 — Opción A si hace falta).

## Definition of Done

```
unit + golden → verde · integration → verde (<5:00) · integration_gui →
verde (con el orden documentado en D-12.7) · mypy strict → Success ·
ruff → clean
```

## Reporte final obligatorio

1. Veredicto de cada spike (D-12.2, D-12.4, D-12.5, cross-file clone)
   con evidencia — especialmente el (c) de connect_pins: la salida de
   netlist que demuestra el neteo.
2. tokens_est del `run_drc` nuevo en modo resumen sobre el board con
   283 violaciones (objetivo ≤2 000) y de una página de detalle.
3. Confirms de las tools nuevas (≤50) y promedios.
4. Estado del flujo sch end-to-end tras esta sesión: con paleta + F8
   humanos, ¿qué pasos del flujo de 9 (análisis 1.3) quedan cubiertos
   y cuáles no?
5. Si D-12.4/D-12.5 resultaron no-factibles: la evidencia y dónde
   quedaron documentados.
6. Propuesta de marker si aplica (D-12.7) y tiempos de suites.
7. Dudas abiertas y lo que el spike de autorouting (sesión 13) debería
   saber.
