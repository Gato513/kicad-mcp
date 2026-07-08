# ADR-0005 — Linux como única plataforma soportada (D5)

**Fecha:** 2026-07-08 · **Estado:** aceptado · **Fuente:** arquitectura §11 D5

## Contexto

La pregunta P5 era qué plataformas soportar oficialmente. Cada plataforma
añade una dimensión completa a la matriz de CI, packaging (named pipes en
Windows, `.app` bundle en macOS), y superficie de bugs específica del socket
IPC (Unix socket / named pipe). El equipo es de una persona; el usuario
declarado usa Linux.

## Decisión

**Linux es la única plataforma soportada oficialmente.** Unix socket
`/tmp/kicad/api.sock` para el IPC. Windows queda **eliminado del roadmap**
(no aplazado). macOS queda "posiblemente funcional" — probablemente
funciona porque comparte mecanismo, sin CI y sin garantías.

## Consecuencias

- Se elimina named pipes del bridge, packaging dual para Windows y una
  dimensión de la matriz de CI. La estimación original del roadmap se recorta
  ~2–3 semanas.
- El instalador y la documentación asumen Linux. Los issues abiertos desde
  Windows se cierran con la referencia a este ADR: no es un bug, es fuera de
  alcance.
- Si un contribuyente futuro quiere macOS oficialmente soportado, el trabajo
  es: matriz de CI, packaging, tests de integración contra KiCad para macOS.
  Requiere abrir un ADR-006x.
- El README y el script `verificar_entorno.py` fallan explícito si el sistema
  no es Linux, con mensaje que apunta a este ADR — no dejan al usuario
  descubriéndolo a mitad de sesión.
