Reporte de Sesión 11 — Cerrar el loop de escritura PCB

DoD — estado final

┌────────────────────────────────────────────────┬────────────────────────────────────────────────┐
│                      Gate                      │                   Resultado                    │
├────────────────────────────────────────────────┼────────────────────────────────────────────────┤
│ pytest -m "not integration and not             │ 143 passed (arranque 123 + 20 nuevos), 15–30 s │
│ integration_gui"                               │                                                │
├────────────────────────────────────────────────┼────────────────────────────────────────────────┤
│ pytest -m integration                          │ verde (exit 0), < 5:00                         │
├────────────────────────────────────────────────┼────────────────────────────────────────────────┤
│ pytest -m integration_gui                      │ mis tests T1–T6 verdes; ver nota de contención │
│                                                │  abajo                                         │
├────────────────────────────────────────────────┼────────────────────────────────────────────────┤
│ mypy src/                                      │ Success (31 files, strict)                     │
├────────────────────────────────────────────────┼────────────────────────────────────────────────┤
│ ruff check + format --check                    │ clean (52 files)                               │
└────────────────────────────────────────────────┴────────────────────────────────────────────────┘

Commits en sesion-11 (sin push): 6d6932a (T1–T4 core), cee6cad (T5 quick wins), dfe435f (tests gui + T6).

---
1. Estado por tarea

- T1 save_board — HECHO. kipy expone el save como Board.save() (kipy/board.py:285-288):
def save(self):
    command = editor_commands_pb2.SaveDocument()
    command.document.CopyFrom(self._doc)
    self._kicad.send(command, Empty)
- Envía el comando IPC SaveDocument (no requiere begin_commit; ~900 ms en el board grande). Tras el save registro un snapshot de disco con mtimes frescos (no mtimes=None) y ecoo su snap_id. Confirm con ruta absoluta.
- T2 delete_track/delete_via — HECHO. Sin G2 (ADR-0010 nuevo). Matching geométrico puro en el tool (testeable con fakes) sobre list_net_copper (get_items_by_net, ~10× más barato: 156 ms/574 ítems vs 1700 ms/7932). Ambigüedad → INVALID_PARAMS con data.candidates; nunca borra el más cercano.
- T3 get_component_detail — HECHO. Sale de reservados. Hallazgo clave: kipy entrega los pads con posición absoluta ya rotada (FootprintInstance.position setter: "KiCad footprint children are stored with absolute positions") — las 40 líneas de cuenta a mano del dogfooding (F-04) son innecesarias. Bbox del courtyard cuando existe, si no envolvente de pads.
- T4 add_track a pads — HECHO. from_pad/to_pad "REF.PAD", excluyentes con coords crudas. Verificado ±1 nm contra pads reales (U19.1→U19.39).
- T5 quick wins — HECHO. F-01 (area:full/area:rN@ref + doc), F-02 (rutas absolutas en todos los export y save), F-03 (bbox + outline: en cabecera pcb). Goldens byte-idénticos (tokens nuevos solo en casos pcb/foco no cubiertos por goldens; snap: sigue terminal).
- T6 loop completo — HECHO. Ver §2.

---
2. Output literal del loop completo (T6) — F-05 y F-08 muertos

{"tool_name":"export_render","tokens_est":27,"latency_ms":14247,"kind":"pcb_png"}
{"tool_name":"get_world_context","snap_id":1,"tokens_est":7737,"latency_ms":3453,"focus_ref":"U19","radius_mm":25.0,"max_tokens":12000,"kind":"pcb"}
{"tool_name":"get_component_detail","tokens_est":893,"latency_ms":3114,"ref":"U19","kind":"pcb","n_pads":75}
{"tool_name":"move_footprint","snap_id":2,"tokens_est":13,"latency_ms":4640,"ref":"U19"}
{"tool_name":"add_track","snap_id":3,"tokens_est":18,"latency_ms":8435,"net":"GND","layer":"F.Cu"}
{"tool_name":"save_board","snap_id":4,"tokens_est":22,"latency_ms":5400,"path":"/tmp/gui-test-project/video.kicad_pcb"}
{"tool_name":"export_render","tokens_est":27,"latency_ms":12560,"kind":"pcb_png"}
{"tool_name":"run_drc","tokens_est":18956,"latency_ms":41968,"min_severity":"error","total":283}
{"tool_name":"delete_track","snap_id":5,"tokens_est":12,"latency_ms":0.0,"net":"GND"}
{"tool_name":"save_board","snap_id":6,"tokens_est":22,"latency_ms":6439,"path":"/tmp/gui-test-project/video.kicad_pcb"}
{"tool_name":"run_drc","tokens_est":18899,"latency_ms":28182,"min_severity":"error","total":282}

=== T6 LOOP COMPLETO SIN HUMANO (F-05 + F-08 muertos) ===
  render md5: inicial=1c914428d6e2b61b6c7748182f56f34c  post-save=8ad8bef7f243a909b11936c46034e94e  (distintos ✓)
  DRC errores: post-ruteo=283  post-borrado=282  (v2<=v1 ✓)
  save1: OK save_board video.kicad_pcb -> /tmp/gui-test-project/video.kicad_pcb [snap:4]
  save2: OK save_board video.kicad_pcb -> /tmp/gui-test-project/video.kicad_pcb [snap:6]

El PNG cambió tras save_board (md5 distinto — el test literal que falló en F-05) y delete_track bajó el DRC de 283→282, todo sin un solo Ctrl+S humano.

---
3. Tokens

┌────────────────────────────────────────────────┬────────────┬─────────────────┐
│                      Ítem                      │ tokens_est │   Presupuesto   │
├────────────────────────────────────────────────┼────────────┼─────────────────┤
│ get_component_detail U19 (75 pads¹)            │ 893        │ conector grande │
├────────────────────────────────────────────────┼────────────┼─────────────────┤
│ get_component_detail R1 (2 pads)               │ 48         │ ✓               │
├────────────────────────────────────────────────┼────────────┼─────────────────┤
│ get_component_detail IC ~30 pads (extrapolado) │ ~350       │ ≤~300 (rozando) │
├────────────────────────────────────────────────┼────────────┼─────────────────┤
│ confirm save_board                             │ 22         │ ≤50 ✓           │
├────────────────────────────────────────────────┼────────────┼─────────────────┤
│ confirm delete_track/delete_via                │ 12         │ ≤50 ✓           │
├────────────────────────────────────────────────┼────────────┼─────────────────┤
│ confirm add_track (a pads)                     │ 18         │ ≤50 ✓           │
└────────────────────────────────────────────────┴────────────┴─────────────────┘

Promedio de confirms ≪ 50. ¹ U19 tiene 75 pads reales (no 72): 72 numerados + 3 mecánicos PTH. Un IC de 30 pads cae ~350 tok; el techo "≤~300" queda rozado por los nombres de net — honesto reportarlo.

---
4. Mapa fricción → estado (abre el Dogfooding 2)

┌──────┬──────────────────┬───────────────────────────────────────────────────────────────────────┐
│  #   │      Estado      │                                Detalle                                │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-01 │ CERRADA (T5)     │ focus_ref sin radius_mm documentado; header area:full/area:rN@ref.    │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-02 │ CERRADA (T5)     │ Todos los export + save_board devuelven ruta absoluta.                │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-03 │ PARCIAL (T5)     │ Header pcb ya trae bbox + outline:none|WxHmm. Dibujar Edge.Cuts →     │
│      │                  │ sesión 12.                                                            │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-04 │ CERRADA (T3)     │ get_component_detail: pads absolutos + bbox/courtyard. Sin parseo     │
│      │                  │ crudo.                                                                │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-05 │ CERRADA (T1)     │ save_board baja live→disco; render/DRC ven lo mutado (probado en T6). │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-06 │ PARCIAL (T4)     │ add_track(from_pad,to_pad) elimina el cálculo de coords.              │
│      │                  │ Clearance-check DIFERIDO (D-R10).                                     │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-07 │ CERRADA (T3/T4)  │ Posición del pin objetivo disponible al colocar/rutear.               │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-08 │ CERRADA (T2)     │ delete_track/delete_via; loop de DRC cierra (T6).                     │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-09 │ DIFERIDA (D-R10) │ add_track sin clearance-check; se reabre si Dogfooding 2 reprueba.    │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-10 │ DIFERIDA (sesión │ DRC enriquecido/paginado.                                             │
│      │  12)             │                                                                       │
├──────┼──────────────────┼───────────────────────────────────────────────────────────────────────┤
│ F-11 │ CERRADA (T3)     │ Courtyard por componente disponible para evitar solapes.              │
└──────┴──────────────────┴───────────────────────────────────────────────────────────────────────┘

---
5. Tiempos de suites

- unit + golden: 15–30 s (143 tests).
- integration (non-gui): < 5:00, verde.
- integration_gui: suite completa ~7 min, dominada por T6 (2 renders ~13 s + 2 DRC ~42 s/28 s sobre 189 fp / 7932 tracks).

---
6. Dudas abiertas y notas para la sesión 12

1. Sync de spec pendiente (F1). El header TOON extendido (F-01/F-03) está implementado y documentado en tool-catalog.md, pero docs/specs/toon-v1.md §2 NO se pudo actualizar — está bloqueado por permisos (F1 enforced al nivel del harness; solo tool-catalog.md tiene el carve-out). Acción humana: sincronizar la gramática cabecera para admitir los tokens opcionales bbox:/outline:/area: antes de snap: (que queda terminal). Los goldens siguen byte-idénticos, así que ningún golden se tocó.
2. Contención IPC bajo carga. Correr toda la suite integration_gui en un proceso (con el loop pesado de T6: 2 renders + 2 DRC) puede transitoriamente starvar el IPC de KiCad: 4 tests pre-existentes (test_ipc, test_context_delta, test_world_context) fallaron con AS_UNHANDLED en la corrida combinada y pasan en retry aislado. No es regresión — la tool mapea el transitorio a error tipado. Sesión 12 debería considerar -p no:randomly/serializar o marcar T6 para correr aislado.
3. save_board re-lee todo el board (build_state_from_board, ~3.5 s) solo para registrar el snapshot de disco. Barato de optimizar si molesta (derivar del último snap conocido), pero save no es hot-path.
4. Presupuesto de get_component_detail en conectores gigantes (~900 tok para 75 pads). Si el Dogfooding 2 lo usa mucho en ICs grandes, evaluar colapsar pads de igual tamaño/net.
5. Flake transitorio de save_board en conexión fría observado una vez (KICAD_NOT_RUNNING al primer save de la sesión); pasa al reintentar. Comportamiento correcto (error tipado), pero vale tenerlo presente.

✻ Worked for 1h 9m 53s · 4 shells still running

❯ update toon-v1.md spec grammar for the new header tokens

The user is now explicitly asking me to update the spec, which authorizes the F1 edit. Let me apply it:

● Update(docs/specs/toon-v1.md)
Error editing file

Still blocked — this is a hard deny rule in the permission settings (docs/specs/**), not an interactive prompt, so the file-write tools can't touch it even with your in-chat request. Let me look at how the permission is configured so I can tell you the precise fix:

  Ran 1 shell command

The block is a deliberate, checked-in F1 guardrail: .claude/settings.json has "Edit(./docs/specs/toon-v1.md)" in its deny list — and .claude/** is also denied, so I can't lift it from my side either. This is F1 working exactly as designed: the spec frontier is inviolable by construction — no prompt (yours included) can move it through me. That's the point of it.

So this one needs your hand. Two ways:

Option A — you paste the patch (recommended; keeps the guardrail intact). In docs/specs/toon-v1.md §2, replace:

documento   := cabecera "\n" seccion_C "\n" seccion_N
cabecera    := ("SCH"|"PCB") "|v1|" INT "c|" INT "n|snap:" INT
seccion_C   := "[C]" "\n" linea_comp*

with:

documento   := cabecera "\n" seccion_C "\n" seccion_N
cabecera    := ("SCH"|"PCB") "|v1|" INT "c|" INT "n" extras "|snap:" INT
extras      := bbox_tok? outline_tok? area_tok        ; sesión 11, opcionales
bbox_tok    := "|bbox:" NUM "," NUM ";" NUM "," NUM    ; F-03, solo kind=PCB
outline_tok := "|outline:" ("none" | DIM)             ; F-03, solo kind=PCB
area_tok    := ("|area:full" | "|area:r" INT "@" REF)? ; F-01, si hubo foco
DIM         := NUM "x" NUM "mm"                        ; p. ej. 312.0x106.7mm
seccion_C   := "[C]" "\n" linea_comp*

Key invariant to preserve: snap: stays the terminal token — the extras go between {n}n and |snap: (the agent and several tests extract snap via split("snap:") / rsplit(":",1)). And note in the prose that these tokens are optional and never appear in the golden 001/002 cases (so the goldens remain byte-identical).

Option B — you temporarily lift the deny. Remove the line "Edit(./docs/specs/toon-v1.md)" from the deny array in .claude/settings.json and tell me; I'll apply the patch and you can re-add the deny after. I won't touch .claude/settings.json myself — it's also deny-listed, and self-authorizing past an F1 guardrail is exactly what the frontier forbids.

Which do you want? If you type ! git apply won't help here (no patch file), but pasting the block above into the file is a 10-second edit.

✻ Baked for 1m 24s · 4 shells still running

❯ op

Let me try the edit — if you've lifted the deny, it'll go through:

● Update(docs/specs/toon-v1.md)
Error editing file

Still denied — the "Edit(./docs/specs/toon-v1.md)" line is still in the deny array of .claude/settings.json, so the guardrail is intact and I can't write the file. I can't remove that line myself either (.claude/** is also deny-listed by design).

To go with Option B, you need to remove that one line first. Quickest path — run this yourself with the ! prefix so it executes in-session:

! sed -i '/"Edit(.\/docs\/specs\/toon-v1.md)"/d' .claude/settings.json

Then say "go" and I'll apply the grammar patch. Re-add the line afterward (or git checkout .claude/settings.json) to restore the guardrail.

If you'd rather keep the deny untouched, paste the grammar block from my previous message straight into docs/specs/toon-v1.md §2 — it's a 10-second manual edit and doesn't require loosening anything.

✻ Crunched for 30s · 4 shells still running

❯ Opcion A

Option A it is — you apply it, the guardrail stays untouched. Here's the copy-paste-ready change for docs/specs/toon-v1.md §2.

Replace this block:
documento   := cabecera "\n" seccion_C "\n" seccion_N
cabecera    := ("SCH"|"PCB") "|v1|" INT "c|" INT "n|snap:" INT
seccion_C   := "[C]" "\n" linea_comp*

with:
documento   := cabecera "\n" seccion_C "\n" seccion_N
cabecera    := ("SCH"|"PCB") "|v1|" INT "c|" INT "n" extras "|snap:" INT
extras      := bbox_tok? outline_tok? area_tok        ; sesión 11, opcionales
bbox_tok    := "|bbox:" NUM "," NUM ";" NUM "," NUM    ; F-03, solo kind=PCB
outline_tok := "|outline:" ("none" | DIM)             ; F-03, solo kind=PCB
area_tok    := ("|area:full" | "|area:r" INT "@" REF)? ; F-01, si hubo foco
DIM         := NUM "x" NUM "mm"                        ; p. ej. 312.0x106.7mm
seccion_C   := "[C]" "\n" linea_comp*

And optionally add one line to the "Reglas de formato" list to record the invariant:

- Los tokens `extras` (sesión 11) son **opcionales** y van SIEMPRE entre
  `{n}n` y `|snap:` — `snap:` permanece el campo terminal de la cabecera.
  No aparecen en los casos de los golden 001/002 (que quedan byte-idénticos).

Two things worth keeping in mind as you paste:
- snap: must stay terminal — the extras go before |snap:, never after.
- The golden files don't need touching — these tokens only appear in kind=pcb / focused outputs, which no golden covers.

That closes the last open item from the session report (§6 point 1). Nothing else on my side is pending — the code, catalog, ADR, and tests are already committed on sesion-11.
