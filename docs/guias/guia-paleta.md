# Guía de la paleta de símbolos (`paleta.kicad_sch`)

**Para el humano.** Este documento explica cómo armar y mantener la
**paleta**: un archivo de plantillas desde el que el agente clona símbolos
al esquemático de diseño con `add_symbol`. Es el complemento humano del
flujo sch mínimo (sesión 12, D-12.3).

## Por qué existe

El MVP **no** hace pick de librerías del sistema de KiCad (F4/D-08.5: sin
acceso al gestor de símbolos por IPC en KiCad 10). `add_symbol` sólo sabe
**clonar** un símbolo que ya esté instanciado en algún `.kicad_sch`. La
paleta resuelve el arranque en frío: es una hoja donde **vos** (humano)
colocás, una vez, un ejemplar de cada símbolo que el agente podría
necesitar. A partir de ahí el agente clona desde la paleta sin tocar
librerías.

## Diseño (D-12.3)

- La paleta es un archivo **separado**: `paleta.kicad_sch` en la **raíz del
  proyecto** (junto al `.kicad_sch` de diseño). **No es parte de la
  jerarquía de diseño**: no la referencia ninguna hoja, no entra al netlist,
  y sus refs de plantilla **no cuentan como colisión** ni aparecen en los
  hints de "hojas disponibles".
- `add_symbol` resuelve la fuente así:
  1. `source` explícito (p. ej. `source="otra_paleta.kicad_sch"`), o
  2. `paleta.kicad_sch` en la raíz **si existe**, o
  3. la propia hoja destino (clone intra-archivo — el comportamiento
     histórico cuando no hay paleta).
- El clone **cross-file** copia la definición de librería del símbolo (una
  sola vez; si el destino ya la tiene, no la duplica) y anexa la instancia
  con **ref, uuid y posición nuevos**. Verificado por netlist (spike sesión
  12): el símbolo clonado aparece como componente real del diseño.

## Cómo armar la paleta (paso a paso, en KiCad)

1. Abrí el proyecto en KiCad y creá un esquemático nuevo, o abrí uno vacío.
2. Colocá **un ejemplar** de cada símbolo que quieras que el agente pueda
   usar (Add Symbol / tecla `A`). No importa dónde los pongas ni cómo los
   cablees — la paleta es un catálogo, no un circuito.
3. Guardá ese esquemático como **`paleta.kicad_sch` en la raíz del
   proyecto** (junto a tu `.kicad_sch` de diseño). No lo agregues como hoja
   jerárquica del diseño.
4. Listo. El agente ya puede `add_symbol(..., lib_id="Device:R", ref="R5",
   ...)` y el símbolo se clona desde la paleta.

## Convenciones de nombres

- **`lib_id` = la fuente de la verdad.** El agente pide un símbolo por su
  `lib_id` (p. ej. `Device:R`, `Device:C`, `Device:LED`, `Connector:Conn_01x04`).
  Es el mismo `lib_id` que muestra KiCad al colocar el símbolo. Mantené en
  la paleta símbolos con `lib_id` **estándar y estables** — así el agente
  puede pedirlos por nombres que ya conoce del ecosistema KiCad.
- **Refs de plantilla:** las refs de los ejemplares de la paleta (R?, C?,
  U?…) son irrelevantes — el agente les asigna una ref nueva al clonar y la
  paleta se excluye de la validación de colisión. Dejá las que ponga KiCad.
- **Un `lib_id` por símbolo:** si ponés dos ejemplares del mismo `lib_id`,
  el agente clona el primero que encuentre. No hace daño, pero no aporta.
- **Valores (`Value`) genéricos:** el símbolo de la paleta puede tener un
  Value placeholder (`R`, `C`, `10k`…). Tras clonar, el agente ajusta el
  valor real con `set_value` y la huella con `set_footprint`.

## Ejemplo mínimo (6 símbolos típicos)

Una paleta de arranque razonable para diseño digital/analógico básico. Los
`lib_id` son los estándar de las librerías que KiCad trae de fábrica:

| Símbolo | `lib_id` sugerido | Uso típico |
|---|---|---|
| Resistencia | `Device:R` | pull-ups, divisores, límite de corriente |
| Capacitor | `Device:C` | desacople, filtrado |
| LED | `Device:LED` | indicadores |
| Conector 4 pines | `Connector:Conn_01x04` | headers, I2C/UART breakout |
| Regulador LDO | `Regulator_Linear:AMS1117-3.3` | alimentación 3V3 |
| MCU genérico | `MCU_ST_STM32F1:STM32F103C8Tx` | microcontrolador |

Colocá uno de cada en `paleta.kicad_sch` y guardá. A partir de ahí, por
ejemplo, el agente puede: `add_symbol(sheet="design.kicad_sch",
lib_id="Device:R", ref="R1", x_mm=100, y_mm=80)` → clona la resistencia →
`set_value("R1", "10k")` → `set_footprint("R1", "Resistor_SMD:R_0805_2012Metric")`.

> Los `lib_id` de arriba son ejemplos; usá los que tengas instalados. Lo que
> importa es que **el ejemplar esté en la paleta** para que el clone tenga de
> dónde copiar.

## Flujo completo de 9 pasos (con la paleta)

Numeración canónica del flujo end-to-end (tabla 1.3 de
`ANALISIS-ESTADO-Y-BACKLOG.md`). Tras la sesión 14, **el paso 7 (rutear) lo
automatiza `route_board`** — el único ruteo autónomo con calidad (100% del
ratsnest, 0 shorts; ver ADR-0011). Sólo **1** y **5** quedan en manos del
humano en KiCad 10:

```
1. (HUMANO)  crear/abrir el proyecto (KICAD_MCP_PROJECT) + armar paleta.kicad_sch
2. (agente)  add_symbol → clona símbolos con ref nueva
             set_value  → fija el valor real (10k, 100nF, …)
             connect_pins → conecta pines por labels locales (misma hoja)
3. (agente)  run_erc → valida el esquemático
4. (agente)  set_footprint → asigna la huella (lib:name; existencia la valida KiCad)
5. (HUMANO)  en KiCad: File → Update PCB from Schematic (F8) — re-anota y
             baja los componentes al PCB con sus huellas (no automatizable en KiCad 10)
6. (agente)  draw_board_outline + move_footprint → contorno y placement
7. (agente)  route_board → AUTOROUTING headless a DISCO (Freerouting). Confirm:
             `OK route_board 64/64 nets +NNN tracks +NN vias drc_err=0 [snap:N]`
8. (HUMANO)  recargar el board en KiCad (File→Revert) — D-14.1, ver abajo;
   (agente)  get_world_context(kind='pcb', confirm_reloaded=true) → destraba el flag
             run_drc → confirma DRC limpio (post-route)
9. (agente)  export_manufacturing → gerbers + drill (Gate G3: exige DRC sin errores)
```

Nota: el paso 8 (recarga) es una acción de segundos, no un paso de diseño — el
ruteo ya está en disco y correcto; la recarga sólo re-sincroniza el editor vivo
para que futuras mutaciones IPC no lo pisen.

## Hazard del editor abierto y recarga (D-12.4)

Las mutaciones de esquemático del MVP escriben el `.kicad_sch` **en disco**
con `kicad-skip` (no por IPC — la IPC de esquemático es KiCad 11, F4). Si
tenés la hoja abierta en el **Schematic Editor** de KiCad mientras el agente
la muta, KiCad detectará el cambio en disco y, al volver a la ventana, te
mostrará **"El archivo cambió en disco, ¿recargar?"** — aceptá para ver los
cambios del agente.

**No hay recarga automática en KiCad 10.** El spike de la sesión 12 (D-12.4)
lo confirmó: no existe un comando de reload agnóstico del editor; la API de
documento de esquemático (`Schematic` + `revert()`) es `versionadded 0.7.0
(KiCad 11)`; y KiCad 10.0.4 responde `no handler available` a peticiones de
documento de tipo schematic. Por eso `reload_in_gui` **no se construyó** y
queda diferido a KiCad 11.

**Práctica segura:** cerrá la hoja en el Schematic Editor antes de que el
agente la mute, o aceptá el aviso de recarga cuando aparezca. El PCB Editor
sí tiene IPC (KiCad 10): las mutaciones de PCB (`move_footprint`, `add_track`,
`draw_board_outline`, …) se ven en vivo y se bajan a disco con `save_board`.

## Hazard post-`route_board` (split-brain inverso, D-14.1)

`route_board` es el caso **inverso**: escribe el ruteo a **disco** (headless,
subprocess) y el **PCB Editor vivo queda detrás**. El peligro no es cosmético —
una mutación IPC + `save_board` posteriores PISARÍAN el ruteo con el cobre
viejo del editor. Por eso `route_board` activa un flag `live_stale` que
**bloquea** `move_footprint`/`add_track`/`add_via`/`delete_track`/`delete_via`/
`save_board` con `EXTERNAL_EDIT_DETECTED` hasta que recargues el board.
**Protocolo de recarga:** ver `docs/pruebas-gui.md §recarga post-route`. En
corto: en KiCad **File → Revert** (o cerrar y reabrir el `.kicad_pcb`), y luego
el agente confirma con `get_world_context(kind='pcb', confirm_reloaded=true)`.
Las lecturas de disco (`run_drc`, `export_*`, tools `sch`) NO se bloquean.
