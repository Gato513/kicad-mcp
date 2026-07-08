# ADR-0002 — KiCad 10 objetivo, 9.0 mínimo, sin 11/nightlies (D2)

**Fecha:** 2026-07-08 · **Estado:** aceptado · **Fuente:** arquitectura §11 D2 · **Refuerza:** [ADR-0000](0000-fronteras-inviolables.md) F4

## Contexto

KiCad tiene cadencia anual: 9.0 (feb 2025), 10 (feb 2026), 11 anunciado (~feb
2027). El IPC API se liberó en 9.0 y maduró en 10; kicad-python soporta 9+.
KiCad 11 añade capacidades atractivas (headless api-server, exports vía IPC,
schematic IPC) pero solo en nightlies a julio 2026. Elegir el objetivo mueve
tanto la superficie del sistema como la deuda: apuntar demasiado bajo pierde
el IPC maduro; apuntar demasiado alto ata el proyecto a features inestables
que pueden cambiar antes del release.

## Decisión

- **Objetivo primario:** KiCad 10.
- **Mínimo best-effort:** KiCad 9.0 (matriz de CI 9/10).
- **Regla dura (frontera F4):** ninguna feature del sistema puede depender de
  KiCad 11 ni de nightlies. Las capacidades futuras (headless api-server,
  schematic IPC) se tratan como mejoras oportunistas cuando 11 sea estable
  (~feb 2027), momento en que se re-evalúa retirar kicad-skip (roadmap v1.0).

## Consecuencias

- kicad-skip queda en la arquitectura para el ciclo del MVP y hasta v0.2/v0.3.
  Es el punto más frágil del sistema (riesgo R1), pero es la única vía a KiCad
  10.
- El bridge lee/escribe protobuf compatible con el IPC de 9/10. Los .proto
  cambian entre releases; el bridge lleva capa de adaptación y matriz de CI.
- La detección de instancia usa `KICAD_API_TOKEN` (disponible desde 9.0).
- Se prohíbe explícitamente: `import` o subprocess de binarios anunciados solo
  en 11, referencias a `kicad-cli api-server`, uso de schematic IPC API.
- La regeneración cuando 11 sea estable es un cambio compatible-hacia-atrás:
  se añaden módulos alternativos detrás de un flag, no se reescribe el core.
