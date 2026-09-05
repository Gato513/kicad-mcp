Creado a mano en KiCad 10.0.5 (formato de archivo, no dibujado en el editor).

PCB sintética mínima, 4 capas de cobre (F.Cu, In1.Cu, In2.Cu, B.Cu), sin
footprints: borde Edge.Cuts 40x30mm, una vía pasante F.Cu-B.Cu sobre el net
GND (cubre las dos capas internas), un segmento en F.Cu y un segmento en
In1.Cu conectados a través de la vía.

Propósito: único fixture del repo con capas internas de cobre habilitadas Y
lo bastante chico para no exceder el presupuesto de tokens de `get_tracks`
(a diferencia de `004_real`, que también es de 4 capas pero con 808 vías —
inutilizable para este caso porque `get_tracks` no trunca, lanza
`CONTEXT_BUDGET_IMPOSSIBLE`). Sirve para ejecutar
`tests/test_pcb_session43_multilayer_via_span_gui.py` (sesión 43, fix
`_copper_on_layer`: una vía pasante debe contar como presente en las capas
internas que atraviesa).

DRC verificado (kicad-cli 10.0.5): 0 errores, 0 unconnected items — sólo 2
warnings `track_dangling` en los extremos abiertos de los dos segmentos
(esperado: son stubs sin pad en las puntas, no un net completamente
enrutado). Cargado y verificado también con el módulo `pcbnew` de KiCad 10
(`GetCopperLayerCount()==4`, capas habilitadas correctas, vía F.Cu→B.Cu).

`.kicad_pro` basado en la plantilla en blanco de KiCad
(`/usr/share/kicad/template/kicad.kicad_pro`), sin modificar más que
`meta.filename`. Sin `.kicad_prl`: es estado local de UI (posiciones de
ventana), KiCad lo genera solo al abrir el proyecto y no lo necesita el
camino IPC del PCB Editor ni este test.
