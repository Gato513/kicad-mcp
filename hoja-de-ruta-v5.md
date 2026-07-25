# Hoja de ruta v5 — kicad-mcp (Fase 4, arranca post-sesión 29, 2026-07-25)

**Evidencia base:** cierre de Fase 3 con 3 verdes consecutivos, ambición
estratégica del arquitecto y humano post-D7, formalización de D-30.1 a
D-30.4 en `docs/DECISIONES.md`, marco de Fase 4 en `docs/CONTEXT.md`
§"Fases del proyecto".

**Documentos hermanos:**
- `docs/CONTEXT.md` — fuente de verdad del estado del ciclo, sesión por
  sesión.
- `docs/DECISIONES.md` — índice de ADR + decisiones informales vigentes.
- `docs/adr/0012-route-board-persist-contract.md` — contrato D-23.2.
- `docs/historico/roadmaps/hoja-de-ruta-v4.md` — hoja de ruta anterior
  (Fase 3), archivada por trazabilidad.
- `docs/historico/investigacion/26-solder-mask-ant1.md` — investigación
  parcial del P1 solder mask ANT1 (base para sesión 30).

---

## Ambición estratégica de Fase 4

Convertir la arquitectura estable de Fase 3 en un **proyecto Open Source
de alta calidad, con evidencia suficiente para respaldar cada decisión
importante**. NO es expansión desordenada de capabilities.

**Criterio orientador** (D-30.2): cada decisión de Fase 4 se evalúa
preguntando si aumenta calidad, mantenibilidad, confianza, o experiencia
de futuros colaboradores.

**Criterio de éxito operacional** (D-30.2 vigente): el éxito de una sesión
se mide principalmente por el aumento de confianza que aporta al proyecto,
no por el volumen de código escrito.

---

## Secuencia estricta de Fase 4

| Sesión | Contenido | Estado |
|---|---|---|
| 30 | **Investigación P4.0-style del P1 solder mask ANT1** — única deuda técnica arrastrada de Fase 3, cierre honesto sin fix si no se llega. Aplica D-30.1. | ← Siguiente |
| 31 | **Validation Suite: primera validación de nivel A** — primer dogfooding sobre placa ajena al despertador. Fusiona escalada de complejidad + arranque de Suite. | Pendiente |
| 32 | **Validation Suite: nivel B** — proyecto de complejidad media. Aplica criterio de diversidad (D-30.4). | Pendiente |
| 33 | **Validation Suite: nivel C** — proyecto complejo. Aplica criterio de diversidad. | Pendiente |
| 34+ | **Preparación de release Open Source** — solo cuando las 3 validaciones hayan cerrado. Docs, licencia, ADRs, guía de contribución, limpieza del repositorio. | Pendiente |
| post-release | **Features nuevas según demanda real** — no por especulación. | Sin agendar |

**Nota importante:** la secuencia es ordenada, no paralela. La sesión 34
(preparación de release) NO arranca hasta que las 3 validaciones (sesiones
31-33) hayan cerrado con éxito. Si alguna validación abre un P0/P1 nuevo,
se agenda una sesión de fix intermedia y el orden se preserva.

**Consecuencia sobre timing:** el release público no tiene fecha
prometida. Depende de cuánto tarde la investigación P1 (variable) y de
cuánto tarden las 3 validaciones (~2-3h cada una, más el fix intermedio si
aparece).

---

## Validation Suite: metodología

**Objetivo:** construir un corpus de validación con proyectos ajenos al
despertador, comparados contra su ground truth (PCB fabricada por el autor
original). Convierte el testing en activo permanente del proyecto y
transmite confianza objetiva a colaboradores futuros.

**Estructura de directorios** (a formalizar tras las primeras 3 validaciones,
no antes — evita sobreingeniería prematura):

```
validation-suite/
├── level-a/           # Placas simples — regresión rápida
├── level-b/           # Placas medias — uso normal
├── level-c/           # Placas complejas — estrés del algoritmo
├── level-d/           # Casos especiales — buscar bugs específicos
└── reports/
    ├── coverage-matrix.md    # Matriz de features cubiertas (viva)
    ├── validation-001.md
    ├── validation-002.md
    └── ...
```

Las primeras 3 validaciones (sesiones 31-33) se archivan como
`validation-suite/level-{a,b,c}/<proyecto>/` con reports ad-hoc. Con esa
evidencia acumulada, se decide la estructura definitiva.

**Criterios de admisión de un proyecto candidato:**

Requisitos obligatorios:
1. PCB fabricada (existe hardware físico con ese diseño).
2. Proyecto mantenido (repositorio activo).
3. Buenas prácticas de KiCad (revisión manual del arquitecto).
4. Licencia compatible con inclusión en Validation Suite.
5. Esquemático + PCB completos.
6. Sin errores DRC conocidos en el ground truth.

Requisito adicional (D-30.4, aplicable desde el segundo proyecto de cada
nivel):
7. **Diversidad**: agrega al menos una feature no cubierta en la matriz
   vigente al momento de la admisión.

**Criterio de aceptación de una validación cerrada** (D-30.3):

Una PCB producida por el flujo automatizado se considera "igualmente
válida" respecto al ground truth si cumple los 4 criterios simultáneos:

1. DRC 0 errores / 0 warnings (o warnings compartidos con el ground truth).
2. Longitud total de tracks dentro de ±30% del ground truth.
3. Número de vías dentro de ±20% del ground truth.
4. Área ocupada por cobre dentro de ±25% del ground truth.

**Umbrales sujetos a revisión** tras las primeras 3 validaciones cerradas.

**Selección de proyectos** (D-30.4 consideración adicional): para
validaciones posteriores al primero de cada nivel, considerar selección
menos sesgada (top-K de GitHub con etiqueta `kicad-project` que cumpla los
6 requisitos, o criterio automático equivalente). Reemplaza sesgo humano
por sesgo del ecosistema — que es lo que efectivamente vamos a exponer en
Open Source.

**Cada validación cerrada actualiza:**
- Report específico del proyecto.
- Matriz de cobertura (`coverage-matrix.md`).
- Nueva entrada en `docs/historico/sesiones/*.md` con el mismo formato de
  dogfoodings previos.

---

## Criterio de convergencia de Fase 4

Fase 4 cierra cuando **las 4 condiciones se cumplen simultáneamente**:

1. **P1 solder mask ANT1 resuelto o cerrado con nota explícita** (según
   resultado de sesión 30).
2. **3 validaciones exitosas** cubriendo niveles A, B y C, sin P0/P1
   nuevos sin resolver.
3. **Release Open Source lanzado** — con licencia, README, CONTRIBUTING,
   ADRs consolidados, docs de arquitectura para colaboradores, matriz de
   cobertura publicada.
4. **Estabilidad post-release durante N semanas** — sin regresiones
   reportadas por colaboradores externos ni por uso propio. N a definir
   según ritmo de adopción, mínimo 4 semanas.

**Convergencia parcial** (sin cierre pleno pero con hitos importantes):
- Investigación P1 cerrada (sesión 30) → habilita sesiones 31-33.
- 3 validaciones cerradas (sesión 33) → habilita sesión 34.
- Release lanzado (sesión 34+) → habilita observación de estabilidad
  post-release.

---

## Interpretación de resultados en Fase 4

**Cambio de disposición respecto a Fase 3:** durante Fase 3, un P0 nuevo
en un dogfooding se sospechaba regresión hasta prueba en contrario
(variable controlada, misma placa). En Fase 4, con placas ajenas al
despertador, un P0 nuevo puede ser gap legítimo del flujo sobre decisiones
de diseño no ejercitadas antes — **NO regresión por default**.

**Interpretación operacional en Fase 4:**
- **P0 en validación externa:** gap legítimo del flujo. Investigar,
  agendar fix, ratificar. No sospechar regresión salvo evidencia
  específica.
- **P0 en test de regresión existente:** regresión. Fix mandatorio antes
  de continuar con la validación en curso.
- **P0 durante preparación de release:** revisar exhaustivamente antes de
  lanzar. Un release con P0 conocido es fracaso metodológico dado el
  criterio de Fase 4.

**Interpretación de "verde" en Fase 4:**
- Validación externa verde = evidencia de que el flujo maneja diseños no
  familiares. Aumenta confianza en el proyecto como referencia.
- Investigación cerrada honestamente sin fix = evidencia de rigor
  intelectual del proyecto (patrón sesión 23, sesión 26). Aumenta
  confianza en el proceso.
- Release lanzado = cristalización de la confianza acumulada.

---

## Principios metodológicos vigentes en Fase 4

- **D-30.1** — Estrategia de validación explícita (hipótesis / evidencia
  confirmatoria / evidencia refutatoria / protección contra regresiones)
  antes de implementar. Aplica a sesiones con hipótesis técnica.
- **D-30.2** — Éxito por confianza, no por código.
- **D-30.3** — Comparación cuantitativa contra ground truth en Validation
  Suite (DRC 0/0 + longitud ±30% + vías ±20% + área cobre ±25%).
- **D-30.4** — Criterio de diversidad para admisión a Validation Suite.
- **D-27.1** — Restore no destructivo del entorno GUI vivo (heredada de
  Fase 3).
- **D-28.1** — Cambios de orden de fases requieren AskUserQuestion
  (heredada).
- **D-28.2** — Barrido completo al generar diffs de decisiones (heredada).
- **D-26.1** — Refill obligatorio post-colocación pre-baseline DRC
  (heredada, ratificada sin confusor en D7).
- **D-D3.1** — Margen conectores densos ≥1.5-2mm (heredada).
- **D-D4.1** — `get_footprint_neighbors` inclusivo (heredada).
- **D-19.1** — Freerouting no respeta plano GND como exclusión (heredada,
  documentada en ADR-0012).
- **D-24.1** — Fixtures y tests derivan bbox/zonas en runtime, no
  hardcoded (heredada, aplicada en 6+ tests GUI existentes).

---

## Deuda diferida a post-Fase 4

- **Unificación de `POST_ROUTE_PERSIST_FAILED` y `POST_ZONE_PERSIST_FAILED`**
  en un solo código compartido (P4, ADR-0012 §"Extensión de alcance
  (sesión 27)").
- **Loop de vías de `enforce_hole_clearance`** (D-23.3/R16) — código
  posiblemente muerto identificado en sesión 23. NO se toca hasta que
  aparezca evidencia de que importa.
- **F-D4-01** (R13, `get_world_context(kind="sch")` con `#PWR*/#FLG*`) —
  P3, sin novedad. Se puede atender post-release según demanda.

---

## Consideraciones sobre el timing del release

**No hay fecha prometida.** El release público arranca cuando:
- Sesión 30 cierra (P1 resuelto o cerrado honestamente).
- Sesiones 31-33 cierran las 3 validaciones exitosamente.
- El arquitecto y humano confirman que la evidencia acumulada es
  suficiente.

**Estimación de rango razonable** (sin compromiso): 4-6 sesiones desde
D7 hasta release. Si aparecen bugs P0/P1 en validaciones externas, agregar
sesiones de fix. Si el P1 solder mask requiere más de una sesión de
investigación, agregar sesiones adicionales.

**Anti-patrón que evitamos:** anunciar fecha, comprometer artificialmente,
y aceptar release con calidad menor de la que Fase 3 estableció. La
disciplina "primero convergencia con evidencia, después release" que dio
buenos resultados en Fase 3 se mantiene en Fase 4.

---

## Cierre de Fase 4

Cuando las 4 condiciones de convergencia se cumplan, se cierra Fase 4 y
se archiva `hoja-de-ruta-v5.md` en `docs/historico/roadmaps/`. La decisión
sobre Fase 5 (mantenimiento, features nuevas por demanda, o etapa
distinta) queda para consenso arquitecto + humano en ese momento, sin
compromiso previo.
