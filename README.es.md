# kicad-mcp

*(This is a summarized Spanish translation. The [English README](README.md)
is the primary, complete version — read it for the full quickstart,
documentation links, and acknowledgments.)*

Servidor MCP (Model Context Protocol) que permite a un agente LLM operar
[KiCad](https://www.kicad.org/) directamente: leer esquemáticos y PCBs en
un formato comprimido pensado para el consumo de tokens, colocar
footprints, dibujar cobre, correr un autorouter, validar con ERC/DRC y
exportar archivos de manufactura — a través de 32 herramientas (tools)
específicas, en vez de editar archivos a mano.

**Estado:** superó el estadio de MVP. El loop completo de escritura de PCB
(colocación → contorno → zonas/plano GND → autorruteo → DRC → export)
está cerrado y revalidado contra KiCad 10.0.4 real durante meses. Hoy está
en fase de consolidación pre-release: una [Validation
Suite](validation-suite/) estructurada ejercita el flujo contra proyectos
reales de hardware abierto para encontrar dónde deja de funcionar, a
propósito, antes de que lo descubra alguien más. Ver "Limitaciones
conocidas" abajo — este README las pone primero, no las esconde al final.

## Qué hace

Automatiza el flujo canónico de PCB de KiCad: colocar footprints → dibujar
contorno de placa → agregar zonas de cobre/plano GND → rutear con
[Freerouting](https://github.com/freerouting/freerouting) (autorouter
headless) → refill de zonas y DRC final → exportar gerbers/BOM/renders. El
estado se expone al agente LLM como [TOON](docs/specs/toon-v1.md), una
codificación compacta pensada para mantener bajo el consumo de tokens a lo
largo de muchas llamadas pequeñas, en vez de re-serializar la placa
completa cada vez.

Se comunica con una **instancia de KiCad corriendo** vía la API IPC propia
de KiCad (`kicad-python`) para ediciones en vivo, y ejecuta `kicad-cli`
como subproceso para DRC/ERC/export — no parsea ni edita a mano archivos
`.kicad_pcb`/`.kicad_sch` para el trabajo de PCB (la edición de
esquemático es la única excepción, ver limitación 7 abajo).

**Escala validada, dicha sin rodeos:** el flujo completó de punta a punta,
con resultados dentro de los umbrales de aceptación propios del proyecto,
en placas de hasta **63 footprints / 48 nets / 2 capas**. También se
corrió contra una placa de **437 footprints / 380 nets / 4 capas**
(HackRF One) específicamente para encontrar el techo de escalabilidad — el
autorouter no completó en esa placa (ver limitación 2). Tratar "placa
pequeña-mediana de 2 capas" como el punto dulce demostrado hoy, no
"cualquier proyecto de KiCad".

## Limitaciones conocidas

Cada ítem enlaza a la sesión o documento donde se encontró y verificó —
nada acá es una suposición.

- **Validado hasta 63 footprints / 2 capas; una placa de 437
  footprints / 4 capas encontró el techo de escalabilidad, no un
  resultado ruteado.** Ver
  [`docs/analisis/validation-suite-sintesis-A-B-C.md`](docs/analisis/validation-suite-sintesis-A-B-C.md).
- **Freerouting 2.1.0 puede entrar en un crash-loop interno en placas
  grandes/complejas** — bug upstream de Freerouting, no de kicad-mcp.
  Ver `docs/BACKLOG.md` (`F-V3-ROUTER-TIMEOUT-HARD`).
- **`add_zone(fill=true)` puede crashear KiCad tras 3-4 llamadas
  consecutivas en placas grandes.** Causa no concluyente — mitigación:
  llamar `fill_zones()` una sola vez al final en vez de `fill=true` por
  zona. Detalle: [`docs/analisis/auditoria-contratos-bridge.md`](docs/analisis/auditoria-contratos-bridge.md) §4.
- **La mayoría de las tools de escritura no persisten a disco solas** —
  el llamador debe invocar `save_board()` explícitamente. Solo
  `route_board`, `fill_zones` y `add_zone(fill=true)` garantizan
  disco==memoria al terminar exitosamente
  ([ADR-0012](docs/adr/0012-route-board-persist-contract.md)).
- **`delete_tracks_bulk` refilla en memoria pero no persiste ni
  re-verifica clearance** — llamar `fill_zones()` si el borrado tocó una
  zona. `delete_zone` y `add_keepout_zone` tampoco recalculan fills
  vecinos solos.
- **Freerouting no trata un plano GND como zona de exclusión para nets
  ajenos** — una variante same-layer del patrón de vía huérfana resultante
  no está cubierta todavía por el stitching post-ruteo existente.
- **La edición de esquemático es mutación directa de archivo
  (`kicad-skip`), no IPC** — KiCad 10 no expone API de esquemático. Las
  tools de escritura de esquemático son puramente aditivas hoy (sin
  borrado).
- **Llamadas largas pueden exceder el idle-timeout de un cliente MCP**
  antes de que KiCad/Freerouting termine — mitigado corriendo la llamada
  desde un proceso desacoplado (`nohup`+`disown`).
- **Los tests dependientes de GUI requieren un humano con KiCad abierto y
  no están automatizados** — restricción de la API IPC de KiCad en esta
  versión, no un atajo del proyecto.
- **Prácticamente solo Linux** ([ADR-0005](docs/adr/0005-linux-como-plataforma.md)).
  KiCad 10.0.4 es el objetivo validado; 9.0 el mínimo documentado.

## Más información

Para el quickstart completo, la lista de documentación, y los
agradecimientos, ver el [README en inglés](README.md) — es la versión
principal y la que se mantiene actualizada primero.
