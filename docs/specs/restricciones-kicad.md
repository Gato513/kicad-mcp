# Restricciones técnicas de KiCad (verdades no negociables)

**Propósito:** todo lo que Claude Code no puede descubrir por sí mismo sin
perder días. Verificado contra documentación oficial a julio 2026. Si algo de
aquí contradice una suposición tuya, gana este documento; si contradice el
comportamiento observado de KiCad, repórtalo al humano — no lo "resuelvas".

## Versiones (decisión D2)

- **Objetivo primario: KiCad 10.x** (estable desde feb 2026). Mínimo
  best-effort: 9.0. Prohibido depender de KiCad 11/nightlies (frontera F4).
- `kicad-python` **0.7.x pineado exacto** en pyproject (es 0.x: breaking
  changes probables entre minors). SWIG/pcbnew: no usar nunca (legado,
  removido en KiCad 11).

## El socket IPC: modelo mental correcto

1. **KiCad es el servidor; nosotros el cliente.** Socket Unix en
   `/tmp/kicad/api.sock` (configurable). Protobuf sobre nng.
2. **Request-reply estricto. NO existen notificaciones asíncronas.** Nada en
   el diseño puede esperar eventos de KiCad. Detección de cambios externos =
   polling de mtime de archivos, exclusivamente.
3. **Todo request se procesa en el hilo de UI de KiCad.** Consecuencias
   obligatorias: timeout duro de 2000 ms por request; cola interna de
   profundidad 1 (los requests son secuenciales del lado de KiCad de todos
   modos); jamás loops de polling contra el socket; operaciones grandes se
   trocean o se rechazan.
4. **`KICAD_API_TOKEN` identifica la instancia, no autentica.** Cambia en
   cada arranque de KiCad → es el mecanismo para detectar
   `KICAD_RESTARTED` y descartar todos los snapshots.
5. Requiere KiCad **con GUI abierta** y el API habilitado
   (Preferences → Plugins → Enable API server). No hay modo headless del IPC
   en KiCad 9/10 (existe en desarrollo para 11: irrelevante por F4).
6. **Cobertura del IPC en 9/10: solo el editor de PCB.** El editor de
   esquemáticos NO tiene IPC. Lectura de esquemático en el MVP: ver siguiente
   sección.

## Lectura de esquemático sin IPC (estrategia del MVP)

Dos fuentes complementarias, ambas sin tocar la GUI:

- **Conectividad (la parte crítica):** `kicad-cli sch export netlist` →
  parsear la netlist exportada. Es la fuente MÁS robusta de refs, valores,
  footprints y membresía de nets: la genera el propio KiCad con su motor de
  conectividad real (junctions, labels y jerarquía ya resueltos).
- **Posiciones (para TOON y área local):** parse directo del `.kicad_sch`
  (S-expressions) extrayendo solo `(symbol ... (at x y rot))` y la propiedad
  Reference. NO reimplementar conectividad desde el archivo: los wires y
  junctions del archivo NO son la verdad de conectividad, la netlist sí.
- Cruce por ref. Si un ref está en el archivo y no en la netlist (o
  viceversa): estado inconsistente → error, no adivinar.

## Unidades y coordenadas (fuente #1 de bugs)

- Archivos (`.kicad_sch`, `.kicad_pcb`): **milímetros** (float).
- IPC API: **nanómetros** (int64). Conversión SOLO en el borde del bridge,
  con tipos distintos (`Nm = NewType("Nm", int)`, `Mm = NewType("Mm", float)`)
  para que mypy atrape mezclas.
- TOON y todo lo que ve el LLM: **mm con 1 decimal**, siempre.
- Grilla de esquemático: **1,27 mm (50 mil)**. Un pin fuera de grilla no
  conecta. (Irrelevante en MVP solo-lectura; crítico desde v0.2 — se deja
  escrito ahora para que exista cuando importe.)

## kicad-cli: matriz de comandos autorizados

| Necesidad | Comando | Notas |
|---|---|---|
| Netlist | `kicad-cli sch export netlist --format kicadxml -o OUT IN.kicad_sch` | XML es el formato más parseable |
| ERC | `kicad-cli sch erc --format json -o OUT IN.kicad_sch` | Exit code ≠ 0 con violaciones: NO es fallo del comando |
| DRC | `kicad-cli pcb drc --format json -o OUT IN.kicad_pcb` | Ídem |
| BOM | `kicad-cli sch export bom -o OUT IN.kicad_sch` | |
| Gerbers | `kicad-cli pcb export gerbers -o OUTDIR IN.kicad_pcb` | |
| Drill | `kicad-cli pcb export drill -o OUTDIR IN.kicad_pcb` | |
| PDF sch | `kicad-cli sch export pdf -o OUT IN.kicad_sch` | |
| Render PCB | `kicad-cli pcb render -o OUT.png IN.kicad_pcb` | |

Reglas de invocación: SIEMPRE `subprocess` con lista de argumentos (jamás
`shell=True`); rutas canonicalizadas contra la raíz del proyecto ANTES de
construir el comando; timeout 60 s (los renders/STEP pueden ser lentos);
capturar stderr y sanearlo antes de que llegue a un mensaje de error.

## Concurrencia y estado en disco

- KiCad GUI mantiene estado **en memoria** no volcado a disco hasta que el
  usuario guarda. Leer el archivo ≠ leer lo que el usuario ve. El MVP
  solo-lectura debe declarar esto en la respuesta de `health` si el mtime es
  viejo y KiCad está corriendo ("posibles cambios sin guardar").
- No existe mecanismo de lock. El modo exclusivo (arquitectura §4.4) es una
  convención documentada, no una garantía técnica.
- Backups (gate G1) se hacen ANTES de cualquier sesión de mutación (v0.2+);
  en el MVP no aplican pero el módulo `gates/` ya reserva el punto de entrada.

## Multi-hoja (jerarquía)

Los esquemáticos reales suelen ser multi-hoja. **El MVP soporta hoja única**
y falla con `UNSUPPORTED_HIERARCHY` al detectar `(sheet ...)` en el archivo
raíz. Prohibido procesar parcialmente en silencio: un contexto que omite
media jerarquía es peor que un error, porque el LLM razonará sobre un
circuito incompleto creyéndolo completo.
