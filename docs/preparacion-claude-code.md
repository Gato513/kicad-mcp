# Preparación del proyecto para desarrollo con Claude Code

**Versión:** 1.0 · Julio 2026
**Proyecto:** kicad-mcp (agente EDA sobre KiCad vía MCP, arquitectura v0.2)
**Propósito:** inventario exacto de lo que debe existir antes de que Claude Code escriba la primera línea, qué puede generarse durante el desarrollo, y evaluación de preparación.

---

## ⚠ Ambigüedad detectada (resolver antes de continuar)

Tu punto 4 menciona **"Funding Rate Arbitrage"** como dominio del proyecto. Eso es un dominio financiero (arbitraje de tasas de financiamiento en derivados cripto) y **no tiene ninguna relación con lo que hemos diseñado**, que es un sistema EDA sobre KiCad. Asumo que es un residuo de una plantilla de prompt reutilizada de otro proyecto, y respondo para el dominio real (EDA/KiCad). **Si efectivamente existe un segundo proyecto de arbitraje financiero, nada de este documento aplica a él y necesita su propia preparación desde cero.** Esta clase de contaminación entre proyectos es exactamente el tipo de error que también comete un agente si el contexto persistente mezcla dominios — razón adicional para mantener un repositorio y un CLAUDE.md por proyecto, sin excepciones.

---

## 1. Contexto del proyecto: documentación necesaria

El principio rector: **Claude Code no lee tu mente, lee tu repositorio.** Todo conocimiento que no esté en un archivo versionado no existe para el agente. La documentación se divide en tres niveles según frecuencia de consulta:

| Nivel | Documento | Estado actual | Imprescindible pre-desarrollo |
|---|---|---|---|
| Núcleo (siempre en contexto) | `CLAUDE.md` — memoria del proyecto | **No existe** | **Sí — es el artefacto #1** |
| Referencia (bajo demanda) | `docs/arquitectura.md` (v0.2) | Existe | Sí (ya está) |
| Referencia | `docs/specs/toon-v1.md` — especificación formal del formato | **No existe** | **Sí** |
| Referencia | `docs/specs/tool-catalog.md` — catálogo de tools + códigos de error | **No existe** | **Sí** |
| Referencia | `docs/specs/bridge-protocol.md` — contrato JSON-RPC Rust↔Python | No existe | No (MVP es Python puro; se escribe en v0.4) |
| Referencia | `docs/glosario.md` — dominio EDA/KiCad | **No existe** | **Sí** |
| Referencia | `docs/adr/` — decisiones D1–D6 como ADRs individuales | Parcial (están en la arquitectura) | Recomendado (1 h de trabajo) |
| Humano | `README.md` — instalación y uso | No existe | No (generable durante) |

**Qué debe mantenerse siempre actualizado** (y quién): `CLAUDE.md` (tú, tras cada sesión que cambie reglas), `tool-catalog.md` (el agente, como parte del Definition of Done de cada tool nueva), `toon-v1.md` (solo con bump de versión del formato — es un contrato, no documentación). Todo lo demás tolera desactualización sin romper al agente.

---

## 2. Arquitectura: qué consulta el agente

Ya tienes el documento de arquitectura v0.2, que es el insumo principal. Lo que falta es **traducirlo a artefactos operativos para el agente**:

**ADRs individuales** (`docs/adr/0001-mono-usuario.md` … `0006-sin-bd.md`): un agente que encuentra una decisión en un archivo dedicado con formato "Contexto / Decisión / Consecuencias" la respeta; una decisión enterrada en la sección 11 de un documento de 400 líneas se le escapa cuando el contexto se compacta. Convertir D1–D6 es una hora de trabajo y puede hacerlo el propio Claude Code como primera tarea supervisada.

**Documento de fronteras** (`docs/adr/0000-fronteras-inviolables.md`) — el más importante y el que no existe en ningún proyecto típico. Lista explícita de lo que el agente **no puede modificar sin aprobación humana**:
1. La especificación TOON y sus golden files (son contrato).
2. El sistema de gates (§D3 de la arquitectura) — ni lógica ni umbrales.
3. Los códigos de error del catálogo (los consume otro LLM en runtime; renombrarlos rompe el sistema en producción).
4. La regla "ninguna dependencia de KiCad 11/nightlies" (D2).
5. La taxonomía de directorios del repositorio.

**Diagramas útiles:** los dos Mermaid de la arquitectura (componentes y secuencia) son suficientes. No inviertas en más diagramas pre-desarrollo: los diagramas desactualizados son peores que su ausencia, porque el agente los toma como verdad.

---

## 3. Especificaciones técnicas: el trabajo real pendiente

Esto es lo que separa "tener una arquitectura" de "estar listo para un agente". Un agente con especificaciones ambiguas no se detiene: **inventa**, y lo inventado compila.

### 3.1 Especificación TOON v1 (imprescindible)
Documento formal con: gramática completa (cabecera, secciones `[C]`/`[N]`, delta `[+]/[-]/[~]`), reglas de escape de texto proveniente del proyecto (mitigación de prompt injection del §7 de la arquitectura), reglas de degradación por presupuesto en orden exacto, y **al menos 5 golden files**: pares `estado_entrada.json → salida_esperada.toon` que se convierten en tests inmutables. Sin golden files, el agente "mejorará" el formato silenciosamente en el refactor #3 y romperá la compatibilidad con los prompts.

### 3.2 Catálogo de tools (imprescindible)
Por cada tool del MVP: nombre, categoría, descripción ≤ 15 palabras (regla del §4.1), schema de parámetros, códigos de error posibles, nivel de refresh que devuelve, y gate que la afecta si aplica. Más la **taxonomía completa de errores** (`NET_NOT_FOUND`, `SNAPSHOT_STALE`, `GATE_DENIED`, `BUDGET_EXCEEDED`, `KICAD_TIMEOUT`, `KICAD_RESTARTED`, `EXTERNAL_EDIT_DETECTED`…) con el formato `{code, message, hint}`. Para el MVP (solo lectura + validación + exports) son ~10 tools: es una tarde de trabajo tuya, y es la tarde mejor invertida de toda la preparación.

### 3.3 Restricciones técnicas (documento corto, crítico)
`docs/specs/restricciones-kicad.md` — las verdades no negociables que el agente no puede descubrir por sí mismo sin perder días: IPC es request-reply sin notificaciones; todo se procesa en el hilo de UI (timeout 2 s obligatorio, cola de profundidad 1); `KICAD_API_TOKEN` cambia por instancia (detección de reinicios); socket en `/tmp/kicad/api.sock`; kicad-cli para todo export/ERC/DRC; kicad-python 0.7.x con pin de versión exacto; **unidades internas del IPC en nanómetros** (la fuente #1 de bugs off-by-10⁶ previsibles); grilla de esquemático de 1,27 mm (50 mil) — pines fuera de grilla no conectan.

### 3.4 Requisitos
Ya existen (RF1–RF12, RNF1–RNF7 en la arquitectura). Acción pendiente: convertirlos en issues/tareas rastreables con criterios de aceptación verificables por test — eso puede hacerlo Claude Code en la primera sesión.

---

## 4. Conocimiento del dominio (EDA/KiCad)

Lo que el agente **no puede asumir** y debe estar en `docs/glosario.md` + `restricciones-kicad.md`:

- **Símbolo ≠ footprint ≠ componente físico**: la tripleta symbol (esquemático) / footprint (PCB) / lib_id, y que la asociación es un campo, no una identidad.
- **Net, pin, pad, junction**: qué constituye conexión eléctrica en cada editor. En esquemático, dos wires que se cruzan **no** están conectados sin junction; un wire que termina a 0,1 mm de un pin **no** conecta. Esta semántica es la causa raíz de los fracasos de escritura de esquemáticos en los proyectos MCP existentes.
- **ERC vs DRC**: qué verifica cada uno, severidades, y que "pasa ERC" no significa "el circuito funciona" — solo que es eléctricamente consistente.
- **Unidades y coordenadas**: mm en archivos, nanómetros en IPC, mils en el folclore de electrónica; eje Y y rotaciones según editor.
- **Referencias (refdes)**: convenciones R/C/L/U/J/Q, unicidad, anotación.
- **Netlist como grafo**: el modelo mental correcto es bipartito (componentes-pines ↔ nets), no una lista.
- **Jerarquía de hojas**: los esquemáticos reales son multi-hoja con labels jerárquicos; el MVP puede limitarse a hoja única, pero debe declararlo y fallar explícitamente ante jerarquía, no ignorarla.

Formato recomendado del glosario: término → definición de 2-3 líneas → *error típico de un no-experto* (esa tercera columna es la que realmente previene bugs del agente).

---

## 5. Normas de desarrollo

Para el MVP (Python): `uv` como gestor, `ruff` (lint+format), `mypy --strict`, `pytest` con marcas `unit` / `golden` / `integration` (integration requiere KiCad corriendo y se excluye por defecto), `pydantic` para todo dato que cruce una frontera de proceso. Layout `src/kicad_mcp/` con módulos que espejan los componentes de la arquitectura (`toon/`, `snapshots/`, `tools/`, `bridge/`, `gates/`, `audit/`). Commits convencionales. Cobertura exigida solo donde es barata y valiosa: motor TOON y delta > 90 % (lógica pura), resto sin objetivo numérico.

Reglas que van en CLAUDE.md porque el agente las viola por defecto si no se le dice: (1) ningún `except Exception: pass` — todo error se mapea a la taxonomía o se propaga; (2) logging estructurado (JSON) con `tool_name`, `snap_id`, `tokens_est`, `latency_ms` en cada tool call — es el instrumento del RNF2, no decoración; (3) prohibido llamar a la red en tests; (4) prohibido editar golden files para "arreglar" un test — un golden que falla es una conversación con el humano; (5) toda ruta de archivo pasa por el canonicalizador contra la raíz del proyecto (§7 de la arquitectura).

---

## 6. Contexto persistente para Claude Code

**`CLAUDE.md` (raíz del repo, siempre cargado)** — máximo ~200 líneas o deja de leerse con atención. Contenido: qué es el proyecto (3 líneas), comandos (`uv run pytest -m "not integration"`, `uv run ruff check`, cómo lanzar el server contra el MCP Inspector), las 5 fronteras inviolables (§2), las 5 reglas de código (§5), los errores de dominio más caros (nanómetros, grilla 1,27 mm, junctions), y **punteros** a los docs de referencia — nunca su contenido copiado, porque las copias divergen.

**Bajo demanda** (el agente los abre cuando la tarea lo requiere): arquitectura v0.2, specs, ADRs, glosario. **Nunca en contexto**: fixtures de proyectos KiCad (miles de líneas de S-expressions que envenenan la ventana — el agente los procesa con código, no leyéndolos).

Opcional pero rentable: `.claude/commands/` con slash commands para rituales repetidos (`/nueva-tool` que recuerda el checklist: schema + catálogo + errores + test + golden si toca TOON).

---

## 7. Herramientas y permisos

**Necesita:** KiCad 10 instalado con API server habilitado (Preferences → Plugins) — *verificado por ti manualmente antes de empezar*; `kicad-cli` en PATH; kicad-python 0.7.x pineado; **MCP Inspector** (`npx @modelcontextprotocol/inspector`) para probar el server sin gastar tokens de agente; 3 proyectos KiCad de fixture (5, ~30 y ~150 componentes — el de 30 puede ser un proyecto open source real, p. ej. una placa de desarrollo publicada con licencia libre); acceso web para documentación oficial de KiCad.

**Servidores MCP para Claude Code:** ninguno es imprescindible. El propio proyecto se prueba con Inspector, no conectándolo a Claude Code hasta que sea estable (evita el bucle "el agente desarrolla el server que el agente usa", que contamina el debugging).

**Permisos (`.claude/settings.json`):** permitir `uv run pytest/ruff/mypy`, git add/commit en ramas de trabajo, edición dentro del repo. **Denegar o requerir aprobación:** `git push`, cualquier `rm -rf`, edición de `docs/specs/**` y `tests/golden/**`, instalación de dependencias nuevas (cada dependencia la apruebas tú — la deriva de dependencias es el error silencioso más común del desarrollo agéntico), y ejecución contra cualquier proyecto KiCad fuera de `tests/fixtures/`. Esta última es la crítica: **el agente jamás opera sobre un proyecto tuyo real durante el desarrollo.**

---

## 8. Checklist de preparación ordenado

**Imprescindible antes de empezar (estimado: 2–3 días de tu tiempo):**
1. ☐ Confirmar la ambigüedad del dominio (¿"Funding Rate Arbitrage" fue un error de plantilla?)
2. ☐ Verificar entorno: KiCad 10 + API server activo + `kicad-cli --version` + `pip show kicad-python` en tu Linux
3. ☐ Crear repo con estructura de directorios + `CLAUDE.md` (§6)
4. ☐ Escribir `docs/specs/toon-v1.md` + 5 golden files a mano (los golden se escriben a mano *una vez*, por ti, con calma)
5. ☐ Escribir `docs/specs/tool-catalog.md` con las ~10 tools del MVP + taxonomía de errores
6. ☐ Escribir `docs/specs/restricciones-kicad.md` (§3.3 — puedes extraerlo casi todo de la arquitectura v0.2)
7. ☐ Escribir `docs/glosario.md` (§4)
8. ☐ Conseguir/crear los 3 fixtures y verificar que kicad-cli los procesa sin error
9. ☐ Configurar `.claude/settings.json` con los permisos del §7

**Generable durante el desarrollo (primeras tareas del agente, supervisadas):**
10. ☐ ADRs 0000–0006 a partir de la arquitectura
11. ☐ README, CI (GitHub Actions: lint + unit + golden), issues desde RF1–RF12
12. ☐ Esqueleto del proyecto con FastMCP + primer tool trivial (`ping`) verificado en Inspector

**Opcional (no bloquea nada):**
13. ☐ Slash commands, pre-commit hooks, matriz de CI contra KiCad 9

---

## 9. Evaluación final: ¿está listo?

**No. Preparación actual: ~40 %.** Lo que existe es excelente base (arquitectura v0.2 con decisiones cerradas, riesgos identificados, roadmap) — es más de lo que tiene el 90 % de los proyectos que se lanzan a desarrollo agéntico. Pero falta exactamente la capa que convierte una arquitectura en instrucciones ejecutables por un agente:

| Falta | Por qué bloquea | Ítem |
|---|---|---|
| CLAUDE.md | Sin él, cada sesión de Claude Code redescubre el proyecto desde cero y toma decisiones inconsistentes entre sesiones | #3 |
| Spec TOON + golden files | El formato es el contrato central; sin spec formal el agente lo implementará "razonablemente" y cada refactor lo mutará | #4 |
| Catálogo de tools + errores | Los nombres y códigos son API pública consumida por otro LLM; improvisarlos genera deuda inmediata | #5 |
| Restricciones KiCad + glosario | Es el conocimiento que el agente no tiene y no puede inferir; sin él, los primeros días se pierden en bugs de unidades y semántica de conexión | #6, #7 |
| Fixtures + entorno verificado | Sin fixtures el agente no puede probar nada real; sin verificación del entorno, el primer error será de instalación y lo debuggeará a ciegas | #2, #8 |
| Permisos configurados | El default de un agente autónomo sin restricciones sobre un proyecto EDA es inaceptable dado el §7 de la arquitectura | #9 |

**Siguiente paso concreto:** los ítems 1–2 hoy (30 minutos), y luego los ítems 3–7 en orden — con la observación de que los ítems 4–7 puede redactarlos Claude (este Claude, en esta conversación o la siguiente) a partir de la arquitectura v0.2, dejándote a ti solo la revisión y los golden files. Eso comprime los 2–3 días a aproximadamente uno.

---

*Regla final, la más importante de todo el documento: durante las primeras dos semanas, revisa cada PR del agente como revisarías el de un ingeniero nuevo brillante pero sin contexto — porque eso es exactamente lo que es. La autonomía se gana con historial, no se otorga por adelantado.*
