# GIT — Antes / Después

## Antes (Puerta 0, `00-preflight-ext.md §1`)

```
branch:  master
HEAD:    33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
origin/master: 33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b (alineado)
status --porcelain=v1 -uall:  (vacío)
worktree list --porcelain:
  worktree /home/astra/Desktop/agent_proyect/kicad-mcp
  HEAD 33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
  branch refs/heads/master
```

(Excepción documentada: aparición transitoria y no reproducible de `.tmp`
entre la primera y la segunda observación — ver `00-preflight-ext.md §2` y
`04-hallazgos-fuera-de-scope-ext.md` H-S47EXT-02. Eliminado antes de
continuar; reconfirmado limpio antes de Fase 3.)

## Después (cierre de esta sesión)

```
branch:  master
HEAD:    33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b   (idéntico)
status --porcelain=v1 -uall:  (vacío)
worktree list --porcelain:
  worktree /home/astra/Desktop/agent_proyect/kicad-mcp
  HEAD 33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
  branch refs/heads/master
```

## Comparación

```
HEAD antes  == HEAD después                    : SÍ (33e32ef…f028b)
working tree antes == working tree después      : SÍ (ambos vacíos)
commits nuevos                                   : 0
archivos modificados en el repositorio            : 0
```

**Ningún `INCUMPLIMIENTO`.** Todos los artefactos de esta sesión (custodia,
unidad `S47-EXT-13-21/`, comparaciones, fichas) se escribieron fuera del
working tree autoritativo: la custodia en
`archivos_temporales_contrato/custodia/S47-ORIGINAL-H11/` (sibling del
repositorio, no dentro de él) y la unidad de evidencia en `$S47_TMP/S47-EXT-13-21/`
(bajo `/tmp`, fuera del repositorio). El único comando de escritura dentro
del working tree autoritativo en toda la sesión fue `rm -f .tmp`, que
restauró el estado previo verificado (no una mutación neta).
