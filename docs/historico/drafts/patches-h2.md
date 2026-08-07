# Parches condicionales — resultado de H2 (auditoría R8)

**Sólo aplicar tras ejecutar el criterio de refutación de H2 sobre la rama base.**

## Criterio de refutación (recordatorio, del prompt)

```bash
# Sobre la rama base, con la working tree limpia:
uv run pytest -m "not integration" --collect-only 2>&1 | tail -3
# ── anotar el número de tests recolectados: N_estrecho

uv run pytest -m "not integration and not integration_gui and not integration_gui_slow" --collect-only 2>&1 | tail -3
# ── anotar el número de tests recolectados: N_amplio
```

- **Si `N_estrecho == N_amplio` → H2 refutada.** El filtro actual ya excluye
  `integration_gui_slow` por otro camino. La auditoría §R8 es incorrecta o
  desactualizada. **No aplicar los parches.** Documentar el hallazgo en el
  reporte de cierre en §H2.
- **Si `N_estrecho > N_amplio` → H2 confirmada.** El filtro actual deja pasar
  `N_estrecho - N_amplio` tests `integration_gui_slow`. **Aplicar los parches
  A y B.**

---

## Parche A — `pyproject.toml`  (sólo si H2 confirmada)

Ubicación: la sección `[tool.pytest.ini_options]`, campo `addopts`.

**Antes** (según auditoría §R8):
```toml
[tool.pytest.ini_options]
addopts = "-m 'not integration and not integration_gui'"
```

**Después:**
```toml
[tool.pytest.ini_options]
addopts = "-m 'not integration and not integration_gui and not integration_gui_slow'"
```

**Verificación post-parche:**
```bash
uv run pytest --collect-only 2>&1 | tail -3
# Debe coincidir con N_amplio del criterio de refutación.
```

Si el `addopts` real de la rama base no coincide con el "Antes" mostrado
arriba, escalá — la premisa del parche es falsa.

---

## Parche B — `CLAUDE.md`  (sólo si H2 confirmada, y el parche A aplicó)

Ubicación: cualquier bloque de comandos que hoy documente
`pytest -m "not integration"`. Según el contexto operativo §7 los comandos
canónicos son:

```bash
uv run pytest -m "not integration and not integration_gui and not integration_gui_slow"
```

El §7 del contexto ya usa la forma completa; probablemente `CLAUDE.md` está
desincronizado con eso mismo. Buscar en `CLAUDE.md` toda ocurrencia de
`-m "not integration"` (sin los otros dos filtros) y reemplazarla por la forma
completa. `grep -n 'not integration' CLAUDE.md` sirve para el inventario.

Sin cambiar nada más de `CLAUDE.md` en esta sesión: el resto del drift
documental (P1-4 del contexto operativo — `CONTEXT.md` en raíz, hoja de ruta
archivada, snapshots con "índice espacial") es sesión aparte por §Fuera del
prompt.

---

## Si H2 fue refutada — qué documentar

En el reporte de cierre, sección §H2:

- El comando exacto que se corrió.
- El valor de `N_estrecho` y `N_amplio` y que son iguales.
- Una hipótesis sobre por qué el filtro actual funciona (¿los tests `slow`
  también tienen la marca `integration_gui`? ¿el `addopts` real es distinto
  al que la auditoría reportó?).
- Un ADR o decisión informal cerrando R8 como "no aplica" con evidencia.

R8 pasa a estar cerrado — no como un "no lo miramos", sino como refutado con
evidencia. Es exactamente el patrón D-33.1 del manual §7 aplicado.
