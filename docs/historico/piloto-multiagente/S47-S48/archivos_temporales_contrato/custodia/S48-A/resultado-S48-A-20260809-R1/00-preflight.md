# 00 — Preflight S48-A

Contrato aprobado, SHA-256 exacto (§13 del contrato):

```text
f2ca64b6c7be33095b174c35b335e88667f7fc4782174dd69ac365b8cd3383b1
```

Nota de invocación (mensaje de Gato, turno de aprobación de ejecución):

```text
S47_ORIGINAL_DIR=/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/custodia/S47-ORIGINAL-H11
S47_EXT_CORREGIDO_DIR=/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/custodia/S47-EXT-13-21-CORREGIDO
REPO_DIR=NO_DISPONIBLE
MODO=SOLO_PAQUETES
```

Fecha de ejecución: 2026-08-09T17:27:35-03:00. Ejecutor: Claude Code. Aprobación: Gato.
Techo de ejecución: 3 horas (valor por defecto §11, sin valor explícito distinto en la nota).

**Observación de forma (no bloqueante):** la nota de invocación no repite palabra por
palabra el rótulo `Contrato aprobado SHA-256:` de la plantilla §3, pero el hash exacto
del contrato fue citado textualmente por Gato en el mismo mensaje de autorización de
ejecución y verificado en el paso 2 de abajo. Se considera satisfecho el requisito
sustantivo de §4.1 ("nota identifica a Gato y contiene el hash exacto del contrato
aprobado").

## Verificaciones (§4), en orden

### 1. Nota existe, identifica a Gato, hash exacto del contrato

Verificado — ver arriba. Autor: Gato ("Yo, Gato, autorizo ejecutar S48-A…").

### 2. `realpath` de ambas rutas de paquetes

```text
$ realpath "$S47_ORIGINAL_DIR"
/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/custodia/S47-ORIGINAL-H11

$ realpath "$S47_EXT_CORREGIDO_DIR"
/home/astra/Desktop/agent_proyect/archivos_temporales_contrato/custodia/S47-EXT-13-21-CORREGIDO
```

Ambas rutas existen y son accesibles en modo lectura.

### 3. Ambas rutas fuera del working tree del repo (si existe)

Repo local presente en `/home/astra/Desktop/agent_proyect/kicad-mcp` (ver §7 sobre
`REPO_DIR` abajo). Ninguna de las dos rutas de paquetes es un prefijo del repo ni
viceversa:

```text
realpath(S47_ORIGINAL_DIR)      -> fuera del repo — OK
realpath(S47_EXT_CORREGIDO_DIR) -> fuera del repo — OK
```

### 4. `sha256sum MANIFEST.sha256` vs §2.1 / §2.2 del contrato

```text
cb3bfee2b25f1e34f3b46a3ead35be7b4525eb9efb24499d0a9dba0cf5fcf078  S47-ORIGINAL-H11/MANIFEST.sha256
d564029b1eea5e6bd3da648cbdb615c3b6cec6f5195fdbf73ea12d2261f65074  S47-EXT-13-21-CORREGIDO/MANIFEST.sha256
```

Coinciden byte a byte con §2.1 (`cb3bfee2…f078`) y §2.2 (`d564029b…5074`) del contrato.
`MATCH`.

### 5. `sha256sum -c MANIFEST.sha256` dentro de cada paquete

**Paquete original (25 entradas):** 25/25 `OK`, exit 0.
**Paquete extensión corregida (29 entradas):** 29/29 `OK`, exit 0.

Ningún archivo listado en ningún manifiesto difiere del disco. Sin alteración
post-firma detectable.

### 6. Directorio de salida

```text
$S48A_TMP = /tmp/tmp.6xIOIIfcqR.s48a
```

Creado con `mktemp -d --suffix=.s48a`, fuera del repositorio y de ambos paquetes S47.
Subdirectorio de trabajo: `$S48A_TMP/S48-A/`.

### 7. `REPO_DIR`

La nota de invocación declara `REPO_DIR=NO_DISPONIBLE` y `MODO=SOLO_PAQUETES`
explícitamente — no es una ausencia detectada por el ejecutor sino una decisión
operativa de la Autoridad tomada al firmar la nota. Se honra tal como fue declarada:
no se usa el repositorio local como fuente de evidencia para responder Q1–Q7 ni para
localizar referencias de código citadas en las fichas.

**Nota de transparencia (no consultada como insumo, solo registrada por disponibilidad
física de la máquina):** el repositorio existe en
`/home/astra/Desktop/agent_proyect/kicad-mcp`, `git rev-parse HEAD` =
`33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b` (coincide exactamente con el checkpoint
histórico citado en contrato §2.3), `git status --porcelain=v1 --untracked-files=all`
reporta un único archivo modificado, `M docs/BACKLOG.md`, preexistente a esta sesión y
no relacionado con S48-A. Esta observación no cambia `MODO_SOLO_PAQUETES`, que queda
determinado por la declaración explícita de la nota, no por esta atestación.

## Resultado del preflight

Ningún disparador de `NO_GO_ENTRADA` de §4 está presente:

- nota ausente/mal formada/hash distinto → no aplica (hash coincide, autoría clara);
- paquete no localizable → no aplica (ambos resueltos por `realpath`);
- hash de manifiesto distinto → no aplica (coincidencia exacta en ambos);
- fallo de `sha256sum -c` → no aplica (54/54 entradas `OK` combinadas);
- imposibilidad de crear salida fuera de repo/paquetes → no aplica (`$S48A_TMP` creado);
- instrucción sobrevenida fuera de scope → no aplica.

**Veredicto de preflight: `GO`.** Modo de ejecución: `MODO_SOLO_PAQUETES`. Se procede a
Fase 2 (matriz).

---

## 8. Preflight de la ronda de corrección R1 (§10.2 del contrato)

Esta unidad (`resultado-S48-A-20260809-R1`) es la **única ronda de
corrección material** autorizada por §10.2 del contrato, sobre 6 defectos
puntuales señalados por la Autoridad en Q3, Q4, Q5, Q6 y Q7. No reabre el
preflight de Fase 2 arriba (§1–§7): el universo, los paquetes S47 y sus
hashes de manifiesto permanecen exactamente los mismos.

### 8.1 Fuente adicional autorizada para esta ronda

```text
Fe de erratas ejecutiva, contrato S47 v6
SHA-256 esperado (dado por la Autoridad):
63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4
```

Verificación:

```text
$ sha256sum custodia/S48-A-FUENTES-AUTORIZADAS/04-fe-de-erratas-ejecutiva-contrato-S47-v6.md
63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4
```

`MATCH` exacto. Nota de ruta: el archivo custodiado dentro de `S48-A-FUENTES-
AUTORIZADAS/` lleva el prefijo `04-` que no aparece en la ruta citada por la
Autoridad (`.../S48-A-FUENTES-AUTORIZADAS/fe-de-erratas-ejecutiva-contrato-
S47-v6.md`); el contenido es idéntico byte a byte (mismo hash) al de la
copia sin prefijo en `archivos_temporales_contrato/fe-de-erratas-ejecutiva-
contrato-S47-v6.md`. No es una divergencia de contenido, solo de nombre de
archivo dentro de custodia.

Usada exclusivamente como fuente **READ-ONLY**: no se copió dentro de
ningún paquete S48-A, no se modificó, no se referencia por ruta absoluta en
ningún producto salvo esta nota de preflight.

### 8.2 Re-verificación de integridad de la unidad original y de S47

```text
$ sha256sum -c resultado-S48-A-20260809/MANIFEST.sha256
8/8 OK, exit 0

$ sha256sum -c S47-ORIGINAL-H11/MANIFEST.sha256
25/25 OK, exit 0
```

Ninguna de las dos unidades fue alterada por esta ronda. `resultado-S48-A-
20260809/` permanece exactamente como cerró Codex; toda escritura de R1
ocurre únicamente dentro de `resultado-S48-A-20260809-R1/`.

### 8.3 Estado del repositorio (transparencia, no consultado como insumo)

```text
$ git -C /home/astra/Desktop/agent_proyect/kicad-mcp status --porcelain
 M docs/BACKLOG.md

$ git -C /home/astra/Desktop/agent_proyect/kicad-mcp rev-parse HEAD
33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
```

Sin cambios desde el preflight original (§7 arriba): el único archivo
modificado es preexistente y ajeno a S48-A. `MODO_SOLO_PAQUETES` se
mantiene.

### 8.4 Alcance de la corrección

Autorizado por la Autoridad, 6 puntos:

1. Reanálisis de Q7 bajo la Regla 3 de la fe de erratas — ver
   `01a-ontologia-y-derivaciones.md` y `04-interpretacion.md` §Q7.
2. Actualización de `convencion_a` en la matriz y reconciliación de
   `04-interpretacion.md`, `05-hallazgos-meta.md`, `06-cierre.md`.
3. Corrección de la cobertura declarada en Q5 (20/21, ficha 6 excepción).
4. Corrección de Q6: separación de señales evaluadas-sin-fallo vs. sin
   declaración.
5. Corrección de Q4: 7 firmas exactas vs. 5 conjuntos de señales activas;
   eliminación de la afirmación no demostrada sobre clustering.
6. Corrección de Q3: trío no nulo `{S1, S8_R11, R12}=1`.

Ninguna ampliación adicional: no se agregan preguntas, productos ni
recálculos de M1–M4. Ningún archivo de `S47-ORIGINAL-H11/`,
`S47-EXT-13-21-CORREGIDO/`, el contrato ni el repositorio se modifica.

**Veredicto de preflight de ronda R1: `GO`.**
