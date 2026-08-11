# PACKAGE-METADATA — `S47-EXT-13-21`

```
Nombre de la unidad:   S47-H11-AMPLIACION-13-21
Ejecutor:              Claude Code
Autoridad:             Gato (proyecto MCP_AUDITOR_KICAD)
Fecha de ejecución:    2026-08-08
SHA_S47_ENTRADA:       33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
```

## Referencias por hash (no por copia, salvo donde el contrato exige copia)

```
Contrato de esta extensión:
  contrato_S47-H11-AMPLIACION-13-21_v1.md
  SHA-256: a2fbeee48e7304a9a957dd2b9b69d78eb290ee148cb5e66b0d90177d35ece6fc
  (copiado byte-a-byte en CONTRATO-AUDITADO.md, ver CONTRACT.sha256)

Nota de invocación de esta extensión:
  nota-invocacion-S47-H11-AMPLIACION-13-21.md
  SHA-256: 08e916d4dff2cb9827f3a222675a3c498dc9196599e0f9af5a0462a01cd95498

Contrato base S47 v6:
  contrato_S47-DT1-SLICE2-CARACTERIZACION_v6.md
  SHA-256: 3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402

Fe de erratas ejecutiva v6:
  fe-de-erratas-ejecutiva-contrato-S47-v6.md
  SHA-256: 63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4

Auditoría delta de erratas:
  auditoria-delta-fe-erratas-S47-v6.md
  SHA-256: 55850fdfb656468fe4758c3b782b7d853ec18d39cc8153ca1d6126ee653ee04a

Nota de invocación original S47:
  nota-invocacion-S47.md
  SHA-256: e746c33867bab1a626326522c5a94046e592e6c9835ecd8244b24237d7fb36b7

Paquete S47 original (solo lectura, no copiado dentro de esta unidad —
custodiado aparte, ver abajo):
  /tmp/tmp.ZedgZwIGVl.s47/S47/
  MANIFEST.sha256: cb3bfee2b25f1e34f3b46a3ead35be7b4525eb9efb24499d0a9dba0cf5fcf078
  CONTRACT.sha256: 7ee91544b55916c9e92afe216c271c0b742a0e5623f0f05c9373e4c761385456

Unidad reproducible corregida (fuente de tools/inventory.py, tools/cluster.py,
tools/m2.py, raw/*.json anclados):
  /tmp/tmp.ZedgZwIGVl.s47/S47-CORREGIDO-2/
  MANIFEST.sha256: 53992da2711279cbc9e0d27d48aa7c835a140acac74b5cf957015b001005c5d0
```

## Custodia (contrato §2.1.1, obligación cerrada por orden de invocación de Gato)

```
Copia byte-idéntica del paquete S47 original, creada en esta sesión:
  /home/astra/Desktop/agent_proyect/archivos_temporales_contrato/custodia/S47-ORIGINAL-H11/
  Verificada: sha256sum -c MANIFEST.sha256 (desde la copia) → exit 0, 25 entradas OK
  Verificada: diff -rq contra el original → vacío, exit 0
  Original NO movido ni modificado.
```

## Procedencia

Contrato preparado por Claude Chat (arquitecto), corregido por Codex
(escritor controlado), revisado independientemente (veredicto
`CONFORME_CON_OBSERVACIONES`, observación `H11-NX-01` aceptada como no
bloqueante por Gato), aceptado por Gato citando ambos SHA-256 finales,
invocado por Gato en turno separado posterior. Ejecutado por Claude Code
en esta sesión, siguiendo exclusivamente el alcance de §§1-11 del contrato.

## Limitaciones declaradas

1. `H-S47EXT-01` — divergencia LOC en `enumeracion.md §6`/contrato §2 para
   8 de los 9 candidatos (ver `04-hallazgos-fuera-de-scope-ext.md`). No
   altera ningún veredicto.
2. `H-S47EXT-02` — archivo `.tmp` transitorio, no reproducible, durante
   Puerta 0 (ver `00-preflight-ext.md §2`).
3. `delete_via` (16) tiene cobertura offline dedicada más delgada (1 test)
   que sus pares (ver `16-delete-via.md`).
4. Procedencia humana de H11 (autorización original que motivó esta
   extensión): la revisión independiente previa (`REVISION_INDEPENDIENTE_
   S47-H11-CORREGIDOS_v1.md`, `H11-CX-08`) la clasificó `NO_VERIFICABLE`
   con los artefactos locales disponibles — riesgo ya conocido y aceptado
   por Gato antes de emitir la orden de invocación; no es una limitación
   nueva de esta ejecución.

## Resultado

Ver `05-RECONCILIACION.md` para el veredicto único sobre el universo de 21
supervivientes. Requiere revisión independiente (contrato §11) antes de
cualquier decisión posterior.

## Linaje de corrección

```
Unidad origen:           S47-EXT-13-21/
MANIFEST.sha256 origen:  ea4aab540e1d8b7849baf5e3e4d8b4c89f7a3851c2f45845b9ada153b04a07d8
Revisor independiente:   Codex, read-only
Veredicto de revisión:   APROBAR_CON_CAMBIOS
Correcciones aplicadas:  C-EXT-01, C-EXT-02, C-EXT-03, C-EXT-04 (ver CORRECCIONES.md)
Productor de la corrección: Claude Code
Autorización de ejecución:  Gato, autoridad humana del proyecto MCP_AUDITOR_KICAD
Estado de esta unidad:   PENDIENTE_DE_REVISION_INDEPENDIENTE_R4
```

Ninguna corrección altera la cadena de veredictos: `NO_GO_POR_PRESUPUESTO`,
`ALCANCE_SUPERVIVIENTES_21`, 21/21 `NO_APTO` sin cambio. Detalle completo,
antes/después y evidencia por hallazgo en `CORRECCIONES.md`.
