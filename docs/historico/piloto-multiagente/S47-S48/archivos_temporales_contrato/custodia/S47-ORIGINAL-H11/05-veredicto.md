# 05 — Veredicto

## 1. Estado inicial verificado (`SHA_S47_ENTRADA`)

```
SHA_S47_ENTRADA = 33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
branch = master, HEAD == origin/master, working tree limpio,
1 worktree (la activa), Puerta 0: GO íntegro (00-preflight.md §7).
```

## 2. Baseline actual observado por categoría, con delta contra `HIST_*`

```
BASELINE_ACTUAL_OBSERVADO = { passed: 406, failed: 0, errors: 0,
  deselected: 77, skipped: 0, collected: 483 }

delta vs HIST_PASSED(406)/HIST_DESELECTED(77)/HIST_FAILED(0)/HIST_ERRORS(0):
  0 en las cuatro categorías. R-BL.0 no se activa, R-BL.1 conforme,
  R-BL.2 no se activa (checkpoint exacto, drift 0). Ver 00-preflight.md §5.
```

## 3. Nota humana §11.9 referenciada por hash único

```
Contrato v6:      SHA-256 3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402
Fe de erratas:    SHA-256 63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4
Auditoría delta:  SHA-256 55850fdfb656468fe4758c3b782b7d853ec18d39cc8153ca1d6126ee653ee04a
```

Los tres hashes fueron reverificados por `sha256sum` en Puerta 0 contra los
archivos citados en la nota firmada (`nota-invocacion-S47.md`) y coinciden
exactamente. Nota bien formada; único punto de desviación (`S47_TMP`,
resuelto por ratificación expresa de la Autoridad) documentado en
`00-preflight.md §2` y `04-hallazgos-fuera-de-scope.md` (H-S47-01).

## 4. Inventario resumido

```
pcb.py: 3161 LOC. |V| = 63 (19 mcp_tools, 20 closures [19⊂mcp_tools+1
  _delete_copper], 38 helpers top-level, 5 constantes top-level).
|E| = 92 aristas V-internas. 58 anotaciones tratadas uniformemente
  REFERENCIA_AMBIGUA por PEP 563 (ninguna afecta un símbolo propuesto para
  extracción). REFERENCIA_INEXPRESABLE: 0 (verificado por evidencia).
```

Detalle completo: `01-inventario-actual.md`.

## 5. Grafo tipado y componentes conectados (resumen)

29 clusters tras semillas S1-S4 (19+20+9+0) y expansión C1-C5 a punto fijo,
deduplicados por conjunto exacto de símbolos. 0 componentes S4 (ninguna
componente conexa de tamaño ≥2 del grafo no dirigido es exclusivamente de
helpers — toda componente de ese tamaño incluye al menos una closure).
Detalle: `02-candidatos/enumeracion.md §1-2`.

## 6. Consumidores privados relevantes (src + tests separados)

```
frontera_entrante_src(K) = ∅ para los 63 miembros de V, sin excepción
  (único acoplamiento src/**->pcb.py: import de `register`, que no es
  miembro de V). Consecuencia: F-DT.4 no puede activarse en este archivo.

frontera_entrante_tests(K) (import/patch literal por path pcb.<k>)
  no vacía solo para _find_duplicate_refs (1 test, import directo).
  Limitación metodológica documentada (H-S47-05): la vía real de cobertura
  de los 19 @mcp.tool es invocación dinámica call_tool("<nombre>", ...),
  no import/patch de path — trazada por separado (raw/coverage.json),
  con evidencia offline+assert citada nominalmente por candidato.
```

## 7. Monkeypatches relevantes

```
run_drc, run_autoroute -- únicos símbolos parcheados sobre el namespace
  kicad_mcp.tools.pcb (4 archivos de test, ambos exclusivamente dentro de
  route_board). Ninguno de los 12 candidatos con ficha los referencia.
  N_marcados_monkeypatch = 0 (route_board ya excluido institucionalmente
  antes de llegar a la etapa de marcado F-DT.2 -- ver enumeracion.md §3).
```

## 8. Enumeración de candidatos con contadores del universo

```
N_universo_total           = 29
N_excluidos_institucional  = 8
N_excluidos_presup         = 0
N_marcados_monkeypatch     = 0
N_supervivientes           = 21
N_fichas_completas         = 12
N_evaluados                = 12
```

## 9. Matriz de candidatos con ficha completa

Ver `02-candidatos/README.md` tabla resumen (12 filas, LOC, S1, S7,
veredicto individual) y las 12 fichas individuales para M1-M4/S1-S8/R1-R14
completos.

## 10. Candidatos descartados institucional o presupuestariamente

8 excluidos institucionalmente (F-DT.1), 0 presupuestariamente. Detalle
nominal: `02-candidatos/descartados.md`.

## 11. Candidatos refutados por §11.5 con criterio activado

```
Fichas 1, 3, 8, 9, 10 (closure-bearing, satisfacen S7):
  NO_APTO por S1 (arista módulo nuevo -> pcb.py, vía _audit_error/
  _resolve_board/_similars/_segment_intersects_bbox) bajo el diseño de
  extracción natural, activando R12; o por S8 (d1 empeora) bajo la
  alternativa de inyección explícita de parámetro. Ambos gates no
  dispensables.

Fichas 2, 4, 5, 6*, 7, 11, 12 (helper-only, no satisfacen S7):
  NO_APTO por fallo de S7 (a/b/c cuantitativos) sin base demostrable
  para E1 (S7.d) -- funciones ya de responsabilidad única y estrecha,
  sin mezcla que eliminar. Activa R11 (beneficio marginal).

(*Ficha 6 falla ambos: S1 -- por _segment_intersects_bbox fuera del
  cluster -- Y S7.)
```

## 12. Candidatos `NO_CLASIFICABLE` por R-BL.3.a

Ninguno. R-BL.3.a nunca se activó (baseline sin drift, checkpoint exacto —
ver §2 arriba). Los 12 candidatos con ficha clasificaron limpiamente.

## 13. Mejor candidato, si existe

**No existe candidato `APTO` ni `APTO_CONDICIONAL`** entre los 12
materializados (`0/12`, ver `03-refutacion.md §1`). No aplica la
calificación "global" ni "dentro del presupuesto" de §15.4 punto 13 porque
no hay un candidato que calificar.

## 14. Alternativa secundaria, si existe

No aplica en el sentido de "segundo mejor APTO" (no hay ninguno APTO). Como
señal para H11 (reintento con presupuesto ampliado) o H5, se destacan dos
observaciones registradas en las fichas:

```
- Ficha 9 (add_track) es el candidato con mayor M1 (LOC) del universo
  materializado y el prior histórico "apto (alternativa)" de S40 -- el más
  atractivo por volumen si se resuelve el conflicto S1/S8 mediante un
  diseño que también reubique {_audit_error, _resolve_board, _similars}.
- Ficha 12 (_segment_intersects_bbox) y las fichas 2/4/5/7/11 son los
  únicos candidatos que satisfacen S1 con margen amplio (sin ninguna
  dependencia saliente hacia helpers compartidos) -- de menor riesgo
  contractual pero tamaño insuficiente para S7 sin una dispensa E1 que
  esta sesión no pudo fundamentar.
- Los 9 supervivientes SIN ficha (02-candidatos/enumeracion.md §6),
  en particular {_via_params, add_via} (110 LOC, del mismo orden que los
  5 candidatos evaluados), quedaron fuera solo por orden lexicográfico
  determinista -- no por ser menos prometedores.
```

## 15. Excepciones §11.7 propuestas por candidato `APTO_CONDICIONAL`

Ninguna — no hay candidatos `APTO_CONDICIONAL` (§11 arriba: en los 5
closure-bearing el gate que falla, S1 o S8, no es dispensable por E1/E2/E3;
en los 7 helper-only el gate que falla, S7, es dispensable en principio por
E1 pero sin evidencia mínima defendible en ninguno de los 7 casos — ver
`03-refutacion.md §2`).

## 16. Riesgos residuales

```
1. N_supervivientes(21) > UMBRAL_P_STOP_FICHAS(12): 9 candidatos nunca
   evaluados en Fase 3 (enumeracion.md §6). No se puede afirmar que
   NINGÚN candidato del universo total sea APTO -- solo que ninguno de
   los 12 evaluados lo es.
2. El patrón S1-vs-S8 encontrado en los 5 candidatos closure-bearing
   sugiere que CUALQUIER extracción de un solo tool desde register(),
   mientras _audit_error/_resolve_board/_similars permanezcan
   compartidos y no movidos, tropezará con el mismo obstáculo -- esto
   incluye, muy probablemente, a varios de los 9 supervivientes sin
   ficha que también son closures (get_tracks, reload_board_from_disk,
   save_board, set_footprint_ref, delete_track, delete_via, add_via).
   No verificado formalmente para esos 7 -- señal para H11, no
   afirmación.
3. Adyacencia temática con DT3 en 6 de los 12 candidatos (H-S47-03,
   04-hallazgos-fuera-de-scope.md) -- riesgo de secuencia de decisiones,
   no colisión técnica actual.
4. Divergencia de S47_TMP entre la nota firmada y el entorno real
   (H-S47-01), resuelta por ratificación de la Autoridad, con
   recomendación operativa para la próxima nota.
5. Ausencia de v5 en el paquete de invocación (H-S47-02), resuelta por
   localización y verificación de hash de una copia fuera del working
   tree, con recomendación operativa para el próximo contrato.
```

## 17. Prescripción de equivalencia futura (§12)

```
Ancla de equivalencia:
  SHA de referencia:            33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
  Baseline pre-cambio:          BASELINE_ACTUAL_OBSERVADO (§2 arriba)
  Tests focales por candidato:  citados nominalmente en cada ficha de
                                 02-candidatos/ (§S4 de cada una)
  Goldens ejercidos:            ninguno de los 12 candidatos toca código
                                 cubierto por golden (los goldens de
                                 pcb_encoders.py son de DT1 Slice 1, ya
                                 cerrada; sin relación con V de esta sesión)
  Monkeypatches vigentes:       run_drc/run_autoroute (pcb_module),
                                 ninguno afectado por los 12 candidatos

Como ningún candidato alcanzó APTO, no hay un "ganador" al que anclar una
prescripción S48 específica en este momento. Si el humano ejerce H11
(reintento con presupuesto ampliado) o decide llevar igualmente uno de los
NO_APTO a S48 bajo un diseño distinto al mínimo evaluado aquí (p. ej.
bundlear el trío de utilidades), la ancla de equivalencia arriba sigue
siendo válida como punto de partida; S48 deberá re-derivar
BASELINE_ACTUAL_OBSERVADO sobre su propio SHA de entrada.

Método de reversibilidad para S48 (si se autoriza): clones externos
(`git clone --local`) — NUNCA `git worktree add` sobre el repo autoritativo
— con manifiesto de tracked files SHA-256+modo e igualdad exacta tras
`git apply --reverse`, conforme a §12 de v6.
```

## 18. Veredicto (uno de los siete estados)

Aplicación formal de §11.3, en orden estricto:

```
1. Puerta 0 falló?                              NO -> continuar
2. R-BL.2 activada?                              NO -> continuar
3. R-BL.3.b activa insuficiencia global?         NO (no hubo R-BL.3 en
                                                  absoluto: checkpoint
                                                  exacto) -> continuar
4. Alguna V0.2-V0.7 no cumplida?                 NO (todas cumplidas,
                                                  contadores registrados
                                                  en §8 arriba) -> continuar
5. N_supervivientes(21) > UMBRAL_P_STOP_FICHAS(12)?
                                                  SÍ
                                                  -> EVIDENCIA_INSUFICIENTE
```

**La regla 5 se activa y es la primera regla aplicable de la secuencia
ordenada del §11.3.** Por diseño explícito del contrato ("Evaluar en orden;
retornar el primer estado aplicable"), la evaluación se detiene aquí — las
reglas 6-13 (incluida la constatación adicional, también verdadera, de que
los 12 candidatos evaluados son unánimemente `NO_APTO`) no determinan el
veredicto porque nunca se alcanzan en el orden de evaluación.

```
╔═══════════════════════════════════╗
║  VEREDICTO:  EVIDENCIA_INSUFICIENTE ║
╚═══════════════════════════════════╝
```

Conforme a la convención [B] de la nota de invocación y a la Regla 5 de la
fe de erratas: la investigación no afirma haber refutado un universo que no
evaluó exhaustivamente (9 de 21 supervivientes sin ficha). Este es un
resultado válido y honesto, no un fallo de S47 — S47 hizo su trabajo:
enumeró el universo completo (29 candidatos), aplicó los filtros
institucionales/presupuestarios correctamente, materializó fichas completas
hasta el presupuesto autorizado (12), y produjo evidencia de que **ninguno
de los 12 evaluados es un candidato limpio** — información directamente
accionable para H11.

## 19. Estado git final

Idéntico a Puerta 0 en las 5 dimensiones protegidas (HEAD, working tree,
CONFIG, REMOTES, REFS) más INDEX_HASH sin cambio. Ver `06-cierre.md` para
la comparación byte-a-byte completa. Ningún `INCUMPLIMIENTO`.

## 20. Referencia a `MANIFEST.sha256` y `CONTRACT.sha256`

```
CONTRACT.sha256 contiene el SHA-256 de CONTRATO-AUDITADO.md, que debe ser
  3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402
  (verificable: sha256sum -c CONTRACT.sha256, desde S47/).
MANIFEST.sha256 hashea todos los archivos del paquete, incluido
  CONTRACT.sha256 (verificable: sha256sum -c MANIFEST.sha256, desde S47/).
```

## 21. Siguiente unidad según §18

```
Veredicto = EVIDENCIA_INSUFICIENTE
  -> NO autoriza S48 (§18: S48 requiere GO o GO_DENTRO_DEL_PRESUPUESTO
     para H2, o GO_CONDICIONAL_PROPUESTO para H2-bis; ninguno de los dos
     se produjo).
  -> La vía de continuación disponible es H11 (§19): "Reintentar S47 tras
     EVIDENCIA_INSUFICIENTE... con presupuesto ampliado (UMBRAL_P_STOP_FICHAS
     > 12) o alcance restringido." Requiere nueva nota de invocación humana.
  -> DT1 Slice 2 permanece SIN CARACTERIZAR y SIN AUTORIZAR. Ningún
     resultado de esta sesión autoriza implementación (Regla 2 de la fe
     de erratas, respetada íntegramente).
```
