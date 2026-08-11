# 04 — Hallazgos fuera de scope (extensión 13-21)

Conforme a v6 §14 y fe de erratas Regla 4/6: imprecisiones detectadas que no
producen `NO_GO_ENTRADA` se documentan aquí.

## H-S47EXT-01 — Divergencia LOC en `enumeracion.md §6` / contrato §2

**Severidad:** NOTE (no bloqueante, no altera ningún veredicto).

**Descripción:** `02-candidatos/enumeracion.md §6` del paquete S47 original
— y, por copia literal, el contrato `S47-H11-AMPLIACION-13-21_v1.md §2` —
anotan valores de LOC para 8 de los 9 candidatos pendientes que **no
coinciden** con `raw/inventory.json` (anclado, verificado byte-idéntico en
Puerta 0 §2.1) ni con el código fuente real de
`src/kicad_mcp/tools/pcb.py` en HEAD `33e32ef…`.

```
#   Candidato                    LOC en §2/§6   LOC real (inventory + fuente)
13  {_similars}                  13             3   (L95-97)
14  {_via_params, add_via}       110            110  ← única coincidencia
15  {delete_track}               51             18  (L1702-1719)
16  {delete_via}                 24             18  (L1726-1743)
17  {get_component_detail}       30             21  (L1975-1995)
18  {get_tracks}                 92             86  (L1749-1834)
19  {reload_board_from_disk}     59             57  (L1489-1545)
20  {save_board}                 44             35  (L1446-1480)
21  {set_footprint_ref}          116            114 (L1039-1152)
```

Los 12 candidatos de `enumeracion.md §5` (originales) **sí** coinciden
exactamente con `sum(V[m].loc)` de `inventory.json` — la anomalía está
confinada a §6. Método de verificación: `raw/02-m2-ext-input.py`+`tools/m2.py`
no computan LOC directamente; el LOC re-derivado en esta sesión sale de
`V[m]["loc"]` en `inventory-ext.json` (byte-idéntico al anclado, `cmp -s`
exit 0), sumado por miembro de cada cluster, y confirmado por lectura
directa de línea inicial/final contra `pcb.py`.

**Tratamiento:** no es `DRIFT_UNIVERSO_S47` — la comparación de identidad
exigida por contrato §2.1(3) es sobre el array `survivors` (nombres,
conjuntos, orden), no sobre las anotaciones de LOC; `01-comparacion-identidad.py`
verificó esa identidad con exit 0 (§00-preflight-ext.md §7), sin tocar LOC.
No es `NO_GO_ENTRADA` (fe de erratas Regla 6: solo 4 categorías la producen,
ninguna es esta). Se usó el LOC re-derivado (columna derecha) para M1/S7 en
cada una de las 9 fichas, con la divergencia declarada individualmente.

**Impacto en veredictos:** ninguno. Con el LOC del contrato o con el LOC
real, la clasificación S7 (cuantitativa) es idéntica para las 9: 14, 18, 21
satisfacen S7.a con ambos valores (todos ≥ `UMBRAL_S7_LOC=80` en ambas
columnas); 13, 15, 16, 17, 19, 20 fallan S7 con ambos valores (todos < 80 en
ambas columnas). Verificado explícitamente para el caso más ajustado (18,
`get_tracks`: 86 real vs. 92 anotado, ambos ≥ 80).

**Origen probable (no verificado, fuera de scope investigar):** el script
`tools/inventory.py` que generó `raw/inventory.json` no cambió (hash
verificado, §2.1 Puerta 0); es más probable que `enumeracion.md §6` se haya
redactado a mano o con una heurística distinta de conteo (p. ej. incluyendo
líneas de firma/decoradores de forma inconsistente) al momento de S47
original, sin re-verificar contra el propio `inventory.json` que la misma
sesión generó. No se investiga más a fondo: está fuera del alcance de esta
extensión (§10 del contrato prohíbe tocar candidatos 1-12 y el paquete
original es solo lectura).

**Corrección mínima recomendada para el humano:** ninguna acción requerida
sobre esta extensión. Si se reutiliza `enumeracion.md` como fuente de LOC en
un contrato futuro, preferir recomputar desde `inventory.json` en vez de
copiar los valores de §6 literalmente.

## H-S47EXT-02 — Archivo `.tmp` transitorio durante Puerta 0

**Severidad:** NOTE (no bloqueante, no reproducible).

Ver `00-preflight-ext.md §2` para el detalle completo. Un archivo vacío
`.tmp` apareció una vez en la raíz del repositorio durante la primera
verificación combinada de versiones de entorno; 7 intentos de reproducción
aislada y combinada posteriores no lo recrearon. Se eliminó (único comando
de escritura sobre el working tree autoritativo en toda la sesión) y se
reconfirmó árbol limpio. No corresponde a ningún comando exigido por el
contrato de forma determinista.

## Colisión con adyacencia DT3 (referencia, no nueva)

`get_component_detail` (17) y `get_tracks` (18) aparecen como consumidores
incidentales en tests GUI de flujos de zona (`test_pcb_session21_hole_clearance_gui.py`,
`test_zones_e2e_gui.py`) — igual que 6 de los 12 candidatos originales
(`H-S47-03` de `04-hallazgos-fuera-de-scope.md`, paquete original). Ninguno
de los dos implementa geometría de zona; se clasifican `REFERENCIA_EXISTENTE`
en S6 de sus fichas respectivas, consistente con el criterio ya aplicado en
S47 original. No es un hallazgo nuevo, se referencia por completitud.
