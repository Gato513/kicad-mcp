# Sesión 32c — Investigación P1 Fase 4: patrón F-D5-01

**Rama:** `sesion/32c-investigacion-f-d5-01` (desde `fb00a73`, tip de
`sesion/32b-fix-refill-silencioso` — `master` no tenía mergeado el fix
de 32b al arrancar; precondición verificada al inicio, resuelta
ramificando desde el tip, mismo patrón que sesiones 31c/32).
**Tipo:** sesión de investigación pura (no fix), sobre el patrón
F-D5-01/F-V1c-01/F-V2-VIA-HUERFANA (3ª instancia, promovido a P1 en
sesión 32).

## Resumen ejecutivo

**Mecanismo raíz aislado y confirmado causalmente sobre el motor real de
KiCad** (patrón sesión 30). Fix diferido a sesión 32d — vive en el
pipeline de zonas/refill de `route_board`, fuera del "SI Y SÓLO SI" de
alcance quirúrgico acordado. Cierra en el escenario de éxito #2 del
prompt: "mecanismo raíz aislado + fix diferido con hipótesis concreta".

**Mecanismo:** Freerouting rutea tracks de OTROS nets sin reservar
corredor para que el flood-fill del plano GND alcance pads específicos
(refinamiento medido de D-19.1, ya documentado). Cuando ese track ajeno
corre en paralelo al borde de la zona, en el mismo rango Y que un pad
GND situado en un corredor angosto (aquí ~3mm entre el pad y el borde de
zona), el clearance obligatorio de esa copper ajena consume el corredor
por completo — el pad se queda sin conexión al plano, sin que
Freerouting (que no modela el plano como conductor) tenga forma de
saberlo. Confirmado con dos experimentos de borrado dirigido +
re-fillado real (`kicad-cli pcb drc --refill-zones --save-board`) sobre
copias desechables, nunca sobre los fixtures del repo.

**Link al reporte completo:** `docs/investigacion/32c-f-d5-01.md`.

## Corrección de encuadre a mitad de sesión (relevante para futuras)

El Bloque 0 (reproducir las 3 manifestaciones) pareció fallar en las 3
al arrancar, lo que llevó — con aprobación del arquitecto vía
`AskUserQuestion` — a adoptar una hipótesis completa (H4, "artefacto
disco≠vivo", análoga a F-V2-REFILL-SILENCIOSO) sobre esa premisa. La
premisa era falsa: los scripts de la sesión leían `violations[].type ==
"unconnected_items"`, pero esa clave vive en un array de **nivel
superior** del JSON de `kicad-cli pcb drc`, separado de `violations[]`.
Se verificó que el código productivo (`src/kicad_mcp/bridge/rules.py`)
lee la clave correcta — el bug fue exclusivo de los scripts desechables
de esta sesión. Al corregir, el Bloque 0 **sí reproduce en 2 de 3
fixtures** con coincidencia exacta de refs. Se reportó la corrección
al arquitecto de inmediato (segundo `AskUserQuestion`, ya que invalidaba
la decisión anterior) y se retomó el protocolo original del prompt
(sub-líneas H1.a-d) con su aprobación.

Una segunda auto-corrección menor ocurrió durante el aislamiento causal:
`zone.HitTestFilledArea()` resultó ser un test poco fiable para
conectividad pad-a-zona (daba `False` incluso para un pad sano
confirmado por `unconnected_items` real) y casi produjo una conclusión
de "refutado" incorrecta sobre la hipótesis de clearance de copper
ajena, que en realidad SÍ era la causa (confirmado releyendo el
`unconnected_items` real del mismo experimento). Documentado en detalle
en el reporte de investigación como lección metodológica.

## Hallazgos

- **3 hipótesis específicas refutadas con experimentos causales** (no
  solo por inspección): `island_removal_mode` ALWAYS→NEVER no cambia el
  resultado; el keepout de `enforce_hole_clearance` más cercano está a
  9.3mm (sin relación); despojar el fill completo no reproduce el
  defecto (el motor trata cualquier pad dentro del *outline* de zona
  como conectado para ratsnest, con o sin fill real — hace falta el
  motor de fill real actuando sobre geometría real).
- **Mecanismo confirmado causalmente en anavi-macro-pad-12**: borrar
  únicamente el track troncal `+5V` que corre en el rango Y de `J4.3`/
  `J5.3` resuelve `J5.3` por completo (tenía backbone de cobre real,
  solo le faltaba el contacto local); `J4.3` necesita además borrar el
  track serpenteante de su propio pin 2 (no tiene ningún track/vía GND
  propio — depende 100% del plano, patrón original de sesión 25).
- **Generalización a anavi-dev-mic**: `MK1.3` (0.30×0.30mm) está
  rodeado por sus propios 4 pines hermanos a 0.85–2.94mm — misma familia
  de mecanismo (clearance de copper ajena estrangulando el corredor
  local), confirmación de correlación fuerte, no aislamiento causal de
  segundo orden (no se repitió el experimento de borrado completo aquí,
  fuera del timebox razonable tras confirmar dos veces en el fixture
  central).
- **Hallazgo lateral, no reportado antes**: `L9.1` en anavi-macro-pad-12
  comparte la misma dependencia estructural 100%-de-la-zona que `J4.3`
  (SL-0), sin generar `unconnected_items` en el estado actual — candidato
  de vigilancia, no acción.
- **despertador-routed no reproduce** (0 `unconnected_items`) —
  coherente con ser el estado YA CORREGIDO (`add_via` de sesión 25 ya
  aplicado), no el estado crudo de D5. No contradice el mecanismo.

## Fix: diferido a sesión 32d

Cualquier fix real vive en el pipeline de refill/zonas de `route_board`
(detectar `unconnected_items` post-refill sobre nets con zona propia y
reaccionar) — automáticamente fuera del "SI Y SÓLO SI" acordado
("no modifica pipelines críticos de zonas/keepouts"). Hipótesis de fix
completamente especificada en `docs/investigacion/32c-f-d5-01.md`
§"Hipótesis de fix para sesión 32d": detectar tras D-23.2 + DRC
post-route si hay `unconnected_items` sobre un net con zona de cobre;
intentar stitching automático con `add_via` (ya existe la tool) solo si
el pad cae dentro del outline de una zona de su mismo net; si no es
seguro automatizar, al menos exponer el conteo en una clave explícita
del payload en vez de diluirlo en `por_tipo`.

## Estado del BACKLOG

`F-D5-01`/`F-V1c-01`/`F-V2-VIA-HUERFANA`: de "P1 investigación, mecanismo
desconocido" a **"P1 activo, mecanismo aislado y confirmado
causalmente, hipótesis de fix completa para sesión 32d"**. Ver
`docs/BACKLOG.md`.

## D-32c.1 (obligatoria) y D-32c.2

Registradas en `docs/DECISIONES.md`. D-32c.1 formaliza la directriz
metodológica de Fase 4 (el objetivo de una investigación es reducir
incertidumbre, no producir fix — precedentes sesión 23, 26, 30).
D-32c.2 registra la decisión técnica: mecanismo aislado + fix diferido,
sin ADR nuevo (no se cambió ningún contrato — el mecanismo describe un
comportamiento existente de Freerouting/KiCad, no una decisión
arquitectónica del proyecto).

## Verificación pre-merge

- `uv run pytest -m "not integration"`: sin cambios en `src/`, debe
  quedar idéntico al estado heredado de `fb00a73`.
- `uv run ruff check` / `uv run mypy src/`: idem, sin cambios de código.
- Gate GUI del DoD: **no requerido** (patrón sesión 26 — sin fix
  aplicado esta sesión).
- Fixtures del repo (`tests/fixtures/`, `validation-suite/`):
  verificados de solo lectura durante toda la sesión — todas las
  mutaciones ocurrieron en copias bajo `/tmp/f-d5-01-*`.

## Próxima sesión

**32d** — aplicación del fix con la hipótesis de esta sesión como
input completo (stitching automático o exposición explícita de
`unconnected_items` sobre nets con zona propia en `route_board`).
Después, **33** (Nivel C), sin bloqueo — el patrón F-D5-01 no impidió
que 31c/32 completaran sus flujos canónicos (14/15 y 42/42 nets
ruteables respectivamente).
