# Especificación TOON v1 (Token-Oriented Object Notation)

**Estado:** CONTRATO — frontera F1. Cambios requieren bump de versión (v2) y
aprobación humana. Los golden files en `tests/golden/` son la definición
ejecutable de esta spec: ante discrepancia entre este texto y un golden, el
golden manda y la discrepancia se reporta.

**Propósito:** serializar el estado de un proyecto KiCad para consumo de un
LLM con el mínimo de tokens posible sin pérdida de información eléctrica.
**No-objetivos:** no es un formato de intercambio (nunca se parsea de vuelta),
no es generado por el LLM (solo lo lee), no preserva información visual
(strokes, colores, tamaños de texto).

---

## 1. Entrada del encoder (estado normalizado)

El encoder recibe el estado normalizado que produce el bridge, en este schema
JSON (definición ejecutable: `src/kicad_mcp/toon/schema.py`):

```json
{
  "kind": "sch",
  "snap": 7,
  "components": [
    {
      "ref": "U1",
      "value": "STM32F103C8Tx",
      "lib": "MCU_ST_STM32F1:STM32F103C8Tx",
      "x": 100.0,
      "y": 50.0,
      "pins": [
        {"p": "1", "name": "VBAT", "net": "3V3"},
        {"p": "8", "name": "GND",  "net": "GND"}
      ]
    }
  ]
}
```

Coordenadas siempre en **mm** (la conversión desde nanómetros del IPC ocurre
en el bridge, nunca aquí). La sección `[N]` se **deriva** de los pines: el
encoder construye el mapa net → pines; la entrada no lleva lista de nets.

## 2. Gramática del documento completo

```
documento   := cabecera "\n" seccion_C "\n" seccion_N
cabecera    := ("SCH"|"PCB") "|v1|" INT "c|" INT "n|snap:" INT
seccion_C   := "[C]" "\n" linea_comp*
linea_comp  := REF "  " VALUE "  " POS "  " pines "\n"
POS         := "x" NUM " y" NUM
pines       := pin (" " pin)*
pin         := PIN_ID ">" NET | PIN_ID ">-"        ; ">-" = sin conectar
seccion_N   := "[N]" "\n" linea_net*
linea_net   := NET ": " miembro (" " miembro)* "\n"
miembro     := REF "." PIN_ID
```

Reglas de formato:
- `NUM`: mm con **1 decimal**, sin ceros a la izquierda (`100.0`, `7.5`).
- `PIN_ID`: número de pin si existe; nombre de pin solo si el símbolo no
  numera (raro). Nunca ambos.
- Alineación en columnas con dobles espacios; no se exige ancho fijo (la
  alineación perfecta cuesta tokens y no aporta comprensión medida).
- Componentes ordenados por ref natural (`C1, C2, C10`, no `C1, C10, C2`);
  nets ordenadas: nets de poder primero (ver §4), resto alfabético.
- El campo `lib` de la entrada **no se emite** en la línea de componente
  (recuperable vía `get_component_detail`); el valor sí, siempre.

### Ejemplo mínimo normativo (= golden 001)

```
SCH|v1|3c|3n|snap:1
[C]
C1  100nF  x105.0 y80.0  1>3V3 2>GND
R1  10k  x120.0 y80.0  1>3V3 2>SDA
U1  STM32F103C8Tx  x100.0 y50.0  1>3V3 8>GND 10>SDA
[N]
3V3: C1.1 R1.1 U1.1
GND: C1.2 U1.8
SDA: R1.2 U1.10
```

## 3. Gramática del delta (ΔTOON)

```
delta      := cabecera_d "\n" cambio* seccion_area?
cabecera_d := "DTOON|v1|snap:" INT "|base:" INT "|area:r" INT "@" REF
cambio     := ("[+] " linea_comp)            ; componente añadido
            | ("[-] " REF "\n")              ; componente eliminado
            | ("[~C] " linea_comp)           ; componente modificado (línea completa nueva)
            | ("[~N] " linea_net)            ; net modificada (línea completa nueva)
seccion_area := "[AREA]" "\n" (REF " ok\n")*  ; refs en el área SIN cambios
```

Decisiones deliberadas:
- `[~C]`/`[~N]` emiten la **línea completa nueva**, no un diff de campos. Un
  LLM reconstruye estado desde una línea completa con más fiabilidad que
  aplicando parches de campos; el costo extra es de ~5 tokens por cambio.
- `[AREA]` lista refs sin cambios dentro del radio, como `ok`. Da al modelo la
  confirmación de que su modelo mental del área sigue válido, a ~3 tokens por
  ref. Se omite si el área tiene más de 20 refs sin cambios (se sustituye por
  `[AREA] 34 refs sin cambios`).
- La cabecera usa `DTOON` (ASCII puro), no `ΔTOON`: el carácter Δ tokeniza mal
  en varios vocabularios.

## 4. Degradación por presupuesto de tokens

El encoder recibe `max_tokens` (default 800). Estimación: `len(texto)/3.5`
(calibrar contra el tokenizador real en Eval A; es presupuesto, no factura).
Si el documento completo excede el presupuesto, se degrada en este orden,
parando en cuanto se cumple:

1. **Colapso de nets de poder** en `[N]`: una net cuyo nombre matchea
   `^(GND|VSS|AGND|DGND|PGND|VCC|VDD|VBUS|[0-9]+V[0-9]*|3V3|5V|12V|-?[0-9]+V)$`
   (case-insensitive) y tiene >8 miembros se emite como
   `GND: 47 pines (colapsada)`. Los pines individuales siguen visibles en
   `[C]`, no hay pérdida eléctrica.
2. **Resumen de componentes lejanos**: si hay un foco activo (área local),
   los componentes fuera del área se agrupan:
   `[FUERA_DE_AREA] 23 comp: R12-R34(resistencias) C8-C19(caps) J2,J3(conectores)`.
3. **Omisión de posiciones**: se elimina `POS` de las líneas de `[C]` (la
   conectividad se preserva; la geometría se recupera bajo demanda).
4. Si aún excede: el encoder **falla** con `CONTEXT_BUDGET_IMPOSSIBLE` y el
   hint de subir el presupuesto o reducir el radio. Jamás trunca en silencio.

Toda degradación aplicada se declara en una línea final:
`[DEGRADADO] poder_colapsado fuera_de_area`.

## 5. Sanitización de texto no confiable

Todo string proveniente del proyecto (`ref`, `value`, nombres de net y de
pin) es entrada no confiable (prompt injection vía archivo, arquitectura §7):

1. Eliminar caracteres de control y saltos de línea (reemplazo por `_`).
2. Longitud máxima 40 chars por campo; exceso se trunca con `…`.
3. Los caracteres estructurales del formato (`>`, `|`, `:`) dentro de un valor
   se reemplazan por `_`.
4. Si tras sanitizar el campo matchea heurísticas de instrucción
   (`(?i)(ignore|system|instruction|prompt|you are)`) se emite igualmente pero
   el documento añade la línea final
   `[AVISO] campos con texto sospechoso: R7.value` — la decisión la toma el
   humano/agente, el encoder solo marca. No censurar en silencio: un value
   legítimo podría contener esas palabras.

## 6. Golden files

Estructura: `tests/golden/NNN_nombre/` con `input.json` (+ `base.json` y
`params.json` para deltas) y `expected.toon`. El test es igualdad de string
**exacta** (byte a byte, `\n` final único). Regla F1: los golden no se editan
para hacer pasar tests. Añadir un golden nuevo está permitido; modificar uno
existente requiere bump a v2.

Set inicial (borradores a validar por el humano contra esta spec):
- `001_minimo` — 3 componentes, sin degradación (§2, ejemplo normativo).
- `002_degradacion` — 12 componentes con GND de 14 miembros y presupuesto
  forzado: verifica colapso de poder + línea `[DEGRADADO]`.
- `003_delta` — base de 4 componentes, se añade C3 y se modifica una net:
  verifica `[+]`, `[~N]`, `[AREA]` y cabecera `DTOON`.

## 7. Compatibilidad y evolución

- El consumidor (prompt del agente) declara: "el contexto llega en formato
  TOON v1". La cabecera lleva la versión precisamente para que un mismatch
  sea detectable.
- Cambios aditivos que un lector v1 ignora sin daño (nuevas líneas `[X]` al
  final) son v1.x y se documentan aquí. Cualquier cambio a líneas existentes
  es v2.
- Pendiente de Eval A (arquitectura §5.8): esta sintaxis compite contra CSV y
  JSON compacto. Si pierde, esta spec se archiva y se reemplaza — el resto del
  sistema no depende de la sintaxis, solo del contrato encoder(estado,
  presupuesto) → string.
