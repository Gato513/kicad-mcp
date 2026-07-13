# ADR-0009 — Port a Rust v0.4: diferido con condiciones

**Fecha:** 2026-07-11 · **Estado:** aceptado · **Fuente:** sesión 09 D-09.5 ·
**Ratificado por:** el humano (2026-07-11)

## Contexto

El objetivo 2 del proyecto (hoja de ruta v2 §objetivos) contempla portar el
núcleo a Rust en una v0.4. `arquitectura.md §10` puso la condición explícita
para hacerlo: *"que duela el rendimiento o la mantenibilidad"*. Tras 8
sesiones con el pipeline PCB construido, medido y validado E2E contra KiCad
real, hay datos duros para decidir con evidencia en vez de romanticismo.

## Datos (de `ANALISIS-ESTADO-Y-BACKLOG.md §1.4`, medición sesión 08)

Descomposición de una mutación (`move_footprint`, board real de 202 refs,
μ de 5 corridas, 3.483 ms totales):

| Componente | ms | % | ¿Rust lo acelera? |
|---|---|---|---|
| `read_ms` — `GetItems` IPC (hilo UI de KiCad) | 2.887 | 83 % | No (espera de red/UI) |
| `lookup_ms` — `get_items_by_id` IPC | 53 | 1.5 % | No |
| `verify_ms` — verificación KIID IPC | 171 | 5 % | No |
| Resto (G1 backup, derivación, encode, logging) | 372 | 11 % | Parcialmente |

- **89 % de la latencia es IPC/UI de KiCad.** El cómputo Python puro medido
  hoy (encoder TOON con degradación 9,3 ms/op; encode_delta 3,9 ms/op; cache
  hit 0,17 ms) es una fracción del "resto"; el core Rust atacaría **<0,3 %**
  de la latencia de mutación y ~1 % de la de lectura fría (780 ms de
  `kicad-cli sch export netlist`, subproceso que Rust tampoco acelera).
- **Ahorro de tokens = 0.** El costo en tokens depende del formato TOON y de
  la información; portar el encoder produce los mismos bytes.
- **0 bugs de lenguaje en 8 sesiones.** Los bugs reales fueron de dominio
  (semántica de property-setter de kipy — ADR-0008; delta kind-aware —
  D-06.1v2; netlist que no incluía el símbolo nuevo — 08 T4). Ninguno es
  prevenible por el sistema de tipos de Rust (coincide con S5 de la
  arquitectura). Crashes/races/leaks atribuibles a Python: cero.
- El binding IPC oficial de KiCad es **Python** (`kipy`); el de Rust es
  experimental sin mantenimiento declarado (`arquitectura.md §3.1`).

## Decisión

**Se DIFIERE el port a Rust.** La condición que la propia arquitectura fijó
—que duela el rendimiento/mantenibilidad— **no se cumple hoy**: el cuello es
el hilo de UI de KiCad y kicad-cli, exactamente como predijo RNF1. Portar
ahora invertiría sesiones L en <0,3 % de mejora mientras el flujo real
(esquemático) sigue trunco.

## Condiciones de re-entrada

El port vuelve a evaluarse sólo si se cumplen **ambas**:

1. **La Eval A valida el encoder que se portaría** (TOON vs JSON/CSV con el
   tokenizador real de Claude): sin premisa de formato validada, portar el
   encoder a Rust carece de sentido.
2. **El dogfooding revela un cuello de botella que es NUESTRO y no de KiCad**
   (no IPC, no kicad-cli, no hilo de UI).

Si el objetivo 2 se mantiene sin cumplirse estas condiciones, sería por
aprendizaje (objetivo 4, declarado no-guía por el humano), no por beneficio
técnico demostrado.

## Consecuencias

- El esfuerzo de las próximas sesiones va al flujo esquemático (Tema A) y al
  dogfooding, no a re-implementar encoder + delta + store + contrato del
  bridge en Rust (más packaging dual, riesgo R6).
- Esta decisión se revisa tras cada dogfooding (hoja de ruta v2 §puntos de
  re-evaluación). Cuando evidencia y plan choquen, gana la evidencia.

## Nota relacionada (D-R7): `discover_tools` eliminada del diseño

En la misma sesión se resolvió la deuda de contrato del catálogo (D-09.4).
`discover_tools` / router por categorías se ELIMINA del diseño (nunca se
escribió código): resolvía "100+ schemas queman la ventana"
(`arquitectura.md §4.1`), pero este server expone ~13 tools y el roadmap
realista suma <10 más. **12-13 tools no justifican un router** (D-R7); el
costo de mantener un indirection layer supera el de exponer las tools
directas. Las tools fantasma `get_component_detail`, `get_net_detail` y
`list_unconnected` se mueven a "Nombres reservados" del catálogo hasta que el
dogfooding demuestre que el agente las necesita.
