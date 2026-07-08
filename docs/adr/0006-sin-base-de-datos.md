# ADR-0006 — Sin base de datos: JSONL + backups en `.kicad-mcp/` (D6)

**Fecha:** 2026-07-08 · **Estado:** aceptado · **Fuente:** arquitectura §11 D6, §4.6

## Contexto

La pregunta P6 era si el sistema necesita persistencia estructurada
(historial multi-sesión consultable, métricas agregadas, cache persistente).
El estado canónico ya vive en los archivos KiCad (`.kicad_sch`,
`.kicad_pcb`); los snapshots son efímeros por diseño (fuente de verdad del
delta durante la sesión). Añadir una BD sería infraestructura sin requisito
funcional que la justifique.

## Decisión

- **Sin base de datos** en el MVP y previsiblemente nunca.
- **Audit log:** JSONL rotativo en `.kicad-mcp/audit.jsonl` del proyecto.
- **Backups:** copias de `.kicad_sch` / `.kicad_pcb` en `.kicad-mcp/backups/`
  al disparar G1 (ver [ADR-0003](0003-gates-de-autonomia.md)).
- **Sin cache persistente:** los snapshots viven en memoria del proceso y
  mueren con él. Reiniciar el servidor implica pedir contexto completo — es
  correcto y explícito.
- **Migración si aparece requisito:** SQLite embebido. La fuente sigue siendo
  el JSONL, así que la migración es trivial (script de carga).

## Consecuencias

- Un requisito de "historial de sesiones anteriores consultable" está
  explícitamente fuera de alcance hasta que exista un caso de uso concreto.
- Backups pre-mutación son responsabilidad de G1, no de un job aparte. Si el
  usuario deshabilita G1, pierde el rollback trivial; el sistema lo permite
  pero lo declara.
- Rotación del JSONL: por tamaño (10 MB por default) para no crecer sin
  límite en sesiones largas. Los archivos rotados quedan en el proyecto; el
  usuario los borra o los commitea a git a su discreción.
- El directorio `.kicad-mcp/` debe estar en `.gitignore` recomendado por el
  README para que los backups no ensucien la historia del repo del hardware.
