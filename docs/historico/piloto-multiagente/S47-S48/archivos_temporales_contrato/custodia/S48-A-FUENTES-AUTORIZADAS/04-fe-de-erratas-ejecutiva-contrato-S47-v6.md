# FE DE ERRATAS EJECUTIVA — CONTRATO S47 v6
## Anexo interpretativo, no reescritura

**Autor:** Arquitecto principal (Claude Chat)
**Fecha:** 2026-08-08
**Contrato base:** `contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md` — **CONGELADO**
**Naturaleza de este documento:** anexo interpretativo. NO modifica los bytes de v6.

---

## 1. Motivación

Tras seis iteraciones del contrato de S47 (v1 → v6), la meta-auditoría del flujo (2026-08-08) concluye que el ciclo entró en sobrecontrol: cada revisión encontró nuevas imprecisiones formales, pero ninguna reducía riesgo operativo real. S47 es una investigación READ-ONLY que no modifica el repositorio, no autoriza implementación y produce un reporte que puede legítimamente contener limitaciones.

Esta fe de erratas congela v6 como contrato de referencia y establece seis reglas interpretativas que gobiernan cómo se lee v6 en ejecución. Nada de v6 se reescribe.

---

## 2. Reglas interpretativas vinculantes

### Regla 1 — Naturaleza inalterada

S47 sigue siendo estrictamente READ-ONLY sobre el repositorio autoritativo, en el sentido definido por §5.1 de v6.

### Regla 2 — Sin puente a implementación

Ningún resultado de S47, incluidos GO, GO_DENTRO_DEL_PRESUPUESTO y GO_CONDICIONAL_PROPUESTO, autoriza implementar DT1 Slice 2. La secuencia canónica S47 → S48 → S49 y las autoridades humanas H1–H13 de §18–§19 permanecen intactas.

### Regla 3 — M2 como indicador cualitativo

Las mediciones de M2 (`M2_estado_actual`, `M2_estado_proyectado`) y su comparación por dominancia u orden lexicográfico son **guías refutables**, no gates matemáticos rígidos. Si el ejecutor encuentra que dos estados no admiten una comparación homogénea limpia sobre un candidato concreto, el candidato se documenta cualitativamente con las dimensiones que sí son comparables, se declara la limitación en la ficha, y S8/R11 se evalúan según el juicio del ejecutor con evidencia registrada. Codex puede refutar el juicio; el humano decide. Esto no bloquea la investigación.

### Regla 4 — Limitaciones como salida legítima

Referencias `REFERENCIA_AMBIGUA` (§7.1.1.bis de v6), candidatos `NO_CLASIFICABLE` (R-BL.3.a), o mezclas que activen la regla 11 de §11.3, se registran como **limitaciones explícitas** en el reporte y pueden conducir a `EVIDENCIA_INSUFICIENTE` sobre esos candidatos concretos. No bloquean la recolección ni la publicación de evidencia sobre los demás candidatos. El reporte declara qué subconjunto se pudo clasificar y qué subconjunto quedó limitado.

### Regla 5 — Sin pretensión de exhaustividad universal

S47 no afirmará haber refutado un universo que no evaluó exhaustivamente. Si `N_excluidos_presup > 0` o `N_excluidos_institucional > 0` o queda cualquier candidato relevante sin clasificar, el veredicto positivo apropiado es `GO_DENTRO_DEL_PRESUPUESTO`, y el veredicto negativo apropiado es `NO_GO_POR_PRESUPUESTO` o `EVIDENCIA_INSUFICIENTE`. `NO_GO` estricto se reserva a la refutación universal completa. Esto no es un cambio de v6; es el énfasis operativo de que la limitación es aceptable.

### Regla 6 — Umbral único de `NO_GO_ENTRADA`

Solo cuatro condiciones producen `NO_GO_ENTRADA`:

1. **Preflight fallido** — base o identidad del repo no verificable, HEAD detached, working tree sucio, worktree adicional sucia, versiones o entorno no disponibles (R-P0.1–R-P0.8, R-P0.11–R-P0.14).
2. **Mutación intentada o inevitable** — comandos prohibidos por §5.1/§13.2 sin alternativa observacional.
3. **Violación de scope** — el trabajo requiere tocar zonas prohibidas, F1–F5, G1–G5, o cruzar deudas segregadas como PRERREQUISITO no aislable.
4. **Ausencia de autorización humana** — nota §11.9 ausente, mal formada, o no referida al hash exacto del contrato aprobado (R-P0.10).

Cualquier otra imprecisión detectada durante la ejecución se documenta en el reporte como limitación, hallazgo §14, o produce `EVIDENCIA_INSUFICIENTE`. **No** produce `NO_GO_ENTRADA`.

En particular, no producen `NO_GO_ENTRADA`:
- Métricas M2 no comparables homogéneamente en un candidato.
- Referencias AST ambiguas en cantidad razonable.
- Candidatos NO_CLASIFICABLE por R-BL.3.a mientras exista al menos otro candidato clasificable o evaluable.
- Ausencia de un candidato APTO — eso es `NO_GO`, `NO_GO_POR_PRESUPUESTO` o `EVIDENCIA_INSUFICIENTE`, resultados válidos.

---

## 3. Compromisos del arquitecto para futuros contratos READ-ONLY

Para no repetir el sobrecontrol:

- Los contratos de investigación READ-ONLY futuros seguirán la plantilla mínima de §7 de la meta-auditoría (objetivo, preflight, scope, comandos, evidencia esperada, formato, condiciones de detención, autoridad siguiente).
- Los algoritmos, métricas y rankings del contrato se marcarán explícitamente como **guías refutables**, no como sistema formal.
- El presupuesto máximo antes de decisión humana será 90 minutos de trabajo combinado (arquitectura + auditoría + corrección + verificación).
- Máximo dos rondas de auditoría; una tercera solo con decisión humana explícita.
- Un BLOCKER solo se emite si cumple los criterios estrictos del nuevo protocolo (§6 de la meta-auditoría).

---

## 4. Secuencia inmediata

```
1. Humano lee esta fe de erratas y v6 congelado.
2. Humano decide: aceptar el paquete (v6 + fe de erratas) o rechazarlo.
3. Si acepta:
   3.a. ChatGPT hace verificación delta breve (no reauditoría completa)
        para confirmar que la fe de erratas no contradice v6 ni introduce
        riesgo nuevo.
   3.b. Humano emite nota de invocación §11.9 apuntando al hash de v6
        y referenciando esta fe de erratas.
   3.c. Claude Code ejecuta S47 READ-ONLY.
   3.d. Codex revisa el paquete.
   3.e. ChatGPT reconcilia solo discrepancias materiales.
   3.f. Humano decide sobre S48.
4. Si rechaza:
   → cancelar S47 en su forma actual;
   → replantear el objetivo de DT1 con nuevo scope o suspender DT1.
```

---

## 5. Nota final

La disciplina "investigación separada del fix" no es solo evitar cambiar código sin autorización. También es aceptar que la investigación puede terminar con **evidencia parcial declarada honestamente**, y que esa parcialidad es información útil para el humano que decide S48. Un contrato de S47 que no permita evidencia parcial no está describiendo una investigación: está intentando pre-derivar la conclusión sin observar el repositorio.

v6 permite evidencia parcial. Esta fe de erratas hace explícito que esa permisividad es la conducta correcta, no un fallo del contrato.

---

**Fin de la fe de erratas.** v6 permanece congelado. Este anexo no requiere byte alguno de modificación en v6.
