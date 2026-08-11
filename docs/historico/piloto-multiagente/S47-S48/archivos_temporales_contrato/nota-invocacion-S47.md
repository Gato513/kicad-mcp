# NOTA DE INVOCACIÓN S47 — §11.9

**Estado:** borrador firmable. La firma efectiva ocurre al invocar Claude Code sobre esta nota.
**Emisión del instrumento:** Arquitecto principal (Claude Chat), 2026-08-08.
**Aprobación operativa:** pendiente de confirmación expresa de la Autoridad (Gato) al invocar Claude Code, tras sustituir `S47_TMP`.

---

```
NOTA DE INVOCACIÓN S47
=====================

Fecha:                 2026-08-08

Contrato aprobado:
    Versión:           S47 v6
    SHA-256:           3b16079cd67357b17ff2d23064c6397454b8a06e4830684c0fa60c2eaac91402

Anexos vinculantes:
    Fe de erratas:
        SHA-256:       63fe27be8ca2fa852d2f5dfef3996549edcced710b2b67275b970c19a36dcdd4
        Archivo:       fe-de-erratas-ejecutiva-contrato-S47-v6.md
    Auditoría delta:
        SHA-256:       55850fdfb656468fe4758c3b782b7d853ec18d39cc8153ca1d6126ee653ee04a
        Archivo:       auditoria-delta-fe-erratas-S47-v6.md

Convenciones interpretativas aceptadas:
    [A] Precedencia condicional de Regla 3 sobre S8/R11.
        La Regla 3 (M2 cualitativo) de la fe de erratas prevalece
        sobre §§10, 11.4-S8, 11.5-R11 y 11.7 de v6 solo cuando la
        comparación homogénea de M2 no sea limpia sobre un candidato
        concreto. En caso contrario, v6 aplica literalmente.
    [B] Precedencia conservadora sobre candidato sin clasificar.
        Un candidato relevante sin clasificar que no esté contabilizado
        como N_excluidos_presup ni N_excluidos_institucional conduce
        a EVIDENCIA_INSUFICIENTE, nunca a GO_DENTRO_DEL_PRESUPUESTO
        ni a NO_GO_POR_PRESUPUESTO.
    [C] Ámbito completo de "preflight fallido".
        "Preflight fallido" en Regla 6 de la fe de erratas incluye
        todas las reglas R-P0.1 a R-P0.15 sin exclusiones. En
        particular R-P0.15 (GIT_OPTIONAL_LOCKS != 0 o PYTEST_ADDOPTS
        != '') activa NO_GO_ENTRADA.

Ancla de sesión SHA:   33e32efbdc8e2fc4fbb544cb569b0c5b9f0f028b
                       (checkpoint conocido; SUJETO A REVERIFICACIÓN
                        AL INICIAR PUERTA 0. Si HEAD local difiere de
                        este SHA y la divergencia no está explicable
                        por merges posteriores documentados en
                        git log, aplicar R-P0.9 → NO_GO_ENTRADA.)

Umbrales autorizados (defaults íntegros del contrato):
    UMBRAL_S7_LOC          = 80
    UMBRAL_S7_CLOSURES     = 3
    UMBRAL_S7_PCB_LOC      = 100
    UMBRAL_R7_REEXPORTS    = 3
    UMBRAL_F_DT3_LOC       = 400
    UMBRAL_F_DT4_MODS      = 3
    UMBRAL_P_STOP_FICHAS   = 12

Categorías §11.7 preautorizadas como evaluables:
    [E1, E2, E3]
    (Preautorización categorial. NO autoriza ninguna instancia
    específica. La aprobación de la instancia concreta ocurre
    post-S47 vía H2-bis.)

S47_TMP:               /tmp/tmp.xOUY807dLa.s47
    Método de generación:  mktemp -d --suffix=.s47
    Reglas:
      - ruta absoluta canónica (verificable con realpath);
      - fuera del working tree del repo (verificable en Puerta 0);
      - registrar aquí LITERALMENTE la ruta resultante antes de
        invocar Claude Code.
    Ejemplo de comando previo a la invocación:
      export S47_TMP=$(mktemp -d --suffix=.s47) && echo "$S47_TMP"
    Pegar la ruta resultante en esta línea, sustituyendo el
    marcador /tmp/tmp.xOUY807dLa.s47.

Aprobación:            Gato
    La invocación efectiva de Claude Code con esta nota constituye
    la confirmación expresa de la Autoridad.
```

---

## Instrucciones de uso de esta nota

1. Ejecutar en la máquina que hospedará S47:
   ```bash
   export S47_TMP=$(mktemp -d --suffix=.s47)
   echo "S47_TMP=$S47_TMP"
   ```
2. Sustituir en la nota `<SUSTITUIR ANTES DE FIRMAR>` por el valor exacto de `$S47_TMP` obtenido.
3. Sustituir `<sustituir por ISO 8601 al firmar>` en el campo `Fecha` por la fecha real de invocación.
4. Sustituir `<confirmar al invocar>` en el campo `Aprobación` por la confirmación explícita (por ejemplo, "aprobado").
5. Configurar en el shell de la sesión, antes de invocar Claude Code:
   ```bash
   export GIT_OPTIONAL_LOCKS=0
   export PYTEST_ADDOPTS=''
   export PYTHONPYCACHEPREFIX="$S47_TMP/pycache"
   export MYPY_CACHE_DIR="$S47_TMP/mypy-cache"
   export RUFF_CACHE_DIR="$S47_TMP/ruff-cache"
   export UV_CACHE_DIR="$S47_TMP/uv-cache"
   ```
6. Verificar manualmente antes de invocar Claude Code:
   - rama `master` activa,
   - HEAD == origin/master,
   - working tree limpio (`git status --porcelain` vacío),
   - entorno sincronizado (`uv sync --frozen` ejecutado previamente),
   - `pcb_encoders.py` presente.
7. Invocar Claude Code con la nota firmada como insumo, indicando:
   - hash de v6 y de los anexos,
   - contenido literal de la nota firmada,
   - referencia a las convenciones A/B/C.

Claude Code ejecutará Puerta 0 verificando todo lo anterior. Si algo falla, producirá `PAQUETE_ENTRADA_FALLIDA` con `NO_GO_ENTRADA`. Si Puerta 0 pasa, la caracterización READ-ONLY comienza.

---

## Fin del rol del Arquitecto principal en este ciclo

Con esta nota emitida, mi trabajo como Arquitecto principal para el ciclo S47 está concluido. Las siguientes autoridades son:

```
Autoridad (Gato)
→ firma la nota (sustituye S47_TMP, fecha y confirmación)
→ invoca Claude Code con la nota como insumo

Claude Code
→ ejecuta S47 READ-ONLY
→ produce el paquete S47 conforme a §15 de v6

Codex
→ revisión independiente del paquete producido

ChatGPT
→ reconciliación de discrepancias materiales

Autoridad (Gato)
→ decide sobre S48 (H2 o H2-bis según veredicto)
```

Yo permanezco disponible como Arquitecto principal para futuras sesiones (por ejemplo, diseñar el contrato de S48 si el veredicto lo habilita y la Autoridad lo decide), pero no interfiero en la ejecución de S47 ni en su revisión.

---

**Fin de la nota.** Instrumento firmable listo. La ejecución READ-ONLY de S47 depende ahora de que la Autoridad firme e invoque.
