# ADR-0001 — Mono-usuario local, transporte stdio (D1)

**Fecha:** 2026-07-08 · **Estado:** aceptado · **Fuente:** arquitectura §11 D1

## Contexto

La pregunta P1 del diseño era si el sistema debía soportar uso remoto/equipo
además del uso local mono-usuario. Cada alternativa tira de la arquitectura en
direcciones opuestas: transporte (stdio vs. HTTP), autenticación (ninguna vs.
OAuth 2.1 conforme al spec MCP jun-2025), modelo de sesión (proceso local vs.
multi-cliente), y superficie de seguridad (proceso local del mismo usuario vs.
red pública).

El usuario objetivo declarado es un ingeniero/maker individual con KiCad de
escritorio y un cliente MCP local (Claude Code / Desktop / Cursor).

## Decisión

Mono-usuario local, **stdio como único transporte**. OAuth 2.1 y Streamable
HTTP se **eliminan del backlog** — no "diferidos": un backlog fantasma
distorsiona decisiones futuras. Si más adelante aparece un requisito remoto,
se abordará como un proyecto aparte.

## Consecuencias

- La superficie de seguridad se reduce a las filas 1–4 de la tabla de amenazas
  (arquitectura §7): prompt injection vía archivo, mutaciones destructivas,
  path traversal, socket IPC accesible localmente. No se trata autenticación,
  TLS ni rate limiting.
- El Snapshot Store nunca necesita ser compartido ni serializable entre
  procesos: vive en memoria del proceso del servidor.
- Simplifica el packaging (un solo binario/entry-point CLI) y la matriz de
  tests: no hay que probar transporte alternativo.
- Cierra la puerta a casos de uso remoto sin autorización explícita. Cualquier
  PR que introduzca dependencias HTTP/OAuth debe reabrir esta decisión.
