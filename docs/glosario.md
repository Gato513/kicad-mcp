# Glosario EDA / KiCad

**Uso:** consultar ante CUALQUIER término dudoso antes de escribir código que
lo modele. La tercera columna existe porque es donde un no-experto (humano o
agente) se equivoca sistemáticamente.

| Término | Definición | Error típico del no-experto |
|---|---|---|
| **Símbolo (symbol)** | Representación lógica de un componente en el esquemático: pines, nombre, valor. Vive en `.kicad_sch`. | Confundirlo con el componente físico o con el footprint. Son tres cosas distintas unidas por campos. |
| **Footprint** | Huella física del componente en el PCB: pads, cortes, serigrafía. Vive en `.kicad_pcb`. | Asumir que símbolo y footprint se corresponden automáticamente: la asociación es un campo editable (y puede estar vacío o mal). |
| **lib_id** | Identificador `Libreria:Nombre` (p. ej. `Device:R`) que vincula una instancia con su definición de librería. | Tratarlo como string decorativo. Si la librería no está instalada, la instancia queda huérfana. |
| **Refdes / Reference** | Referencia única del componente: `R1`, `C3`, `U2`. Prefijo por tipo: R resistencia, C capacitor, L inductor, U circuito integrado, J conector, Q transistor, D diodo, SW switch, Y cristal. | Generar refs duplicadas o con prefijo incorrecto. La unicidad es responsabilidad de quien crea, KiCad no siempre lo impide en edición por archivo. |
| **Anotación** | Proceso de asignar refdes (`R?` → `R7`). Un esquemático sin anotar tiene refs con `?`. | Procesar un proyecto sin anotar como si `R?` fuera un ref válido. Detectar `?` y reportar. |
| **Pin** | Punto de conexión de un símbolo (esquemático). Tiene número, nombre y tipo eléctrico (input, output, power_in, passive…). | Ignorar el tipo eléctrico: el ERC lo usa (dos outputs unidos = violación). |
| **Pad** | Punto de conexión de un footprint (PCB). Se corresponde con un pin por número. | Asumir correspondencia 1:1 garantizada pin↔pad: componentes multi-unidad y pads mecánicos la rompen. |
| **Net** | Nodo eléctrico: conjunto de pines/pads conectados entre sí. Tiene nombre (asignado o autogenerado como `Net-(R1-Pad2)`). | Tratar nets autogeneradas como estables: cambian de nombre al reconectar. Solo los labels explícitos son estables. |
| **Wire** | Segmento gráfico de conexión en el esquemático. | **El error más caro del dominio:** creer que wire = conexión. Dos wires cruzados NO conectan sin junction; un wire que termina cerca de un pin NO conecta. La verdad de conectividad es la netlist, no la geometría. |
| **Junction** | Punto explícito que conecta wires que se cruzan. | Omitirlo al generar wires (v0.2+) y producir circuitos visualmente correctos pero eléctricamente rotos. |
| **Label** | Nombre de net asignado a un punto. Local (misma hoja), global (todo el proyecto), jerárquico (interfaz entre hojas). | Confundir alcances: dos labels locales iguales en hojas distintas NO son la misma net. |
| **Hoja jerárquica (sheet)** | Sub-esquemático anidado. Los proyectos reales son multi-hoja. | Procesar solo la hoja raíz e ignorar el resto en silencio (por eso existe `UNSUPPORTED_HIERARCHY`). |
| **Netlist** | Grafo bipartito componentes/pines ↔ nets, exportado por KiCad con su motor de conectividad real. | Reimplementar conectividad parseando wires del archivo en vez de usar la netlist. |
| **ERC** | Electrical Rules Check (esquemático): pines sin conectar, conflictos de tipos, entradas sin driver. | Creer que ERC limpio = circuito funcional. Solo verifica consistencia eléctrica formal. |
| **DRC** | Design Rules Check (PCB): clearances, anchos mínimos, cortocircuitos geométricos. | Ídem: DRC limpio = fabricable, no correcto. Y: exit code ≠ 0 de kicad-cli con violaciones no es un fallo del comando. |
| **Track** | Pista de cobre en el PCB (segmento, en una capa, con ancho, asignada a una net). | Crear tracks sin net asignada: DRC los marca y el ratsnest no se actualiza. |
| **Via** | Perforación conductora que une capas. | Olvidar que una via pertenece a una net y tiene reglas propias de tamaño/clearance. |
| **Zona (copper pour)** | Área de cobre rellena asignada a una net (típicamente GND). Requiere refill tras cambios. | Asumir refill automático: tras mutar tracks, la zona queda desactualizada hasta repour (limitación conocida del IPC). |
| **Ratsnest** | Líneas rectas que muestran conexiones pendientes de rutear en el PCB. | Confundirlas con tracks reales al leer el estado del board. |
| **Grilla (grid)** | Retícula de alineación. En esquemático, los pines viven en grilla de 1,27 mm (50 mil). | Colocar símbolos fuera de grilla (v0.2+): los pines no conectarán con wires aunque se vean tocándose. |
| **mil** | Milésima de pulgada (0,0254 mm). Unidad histórica de electrónica, común en datasheets. | Confundir mil con mm (factor ~39×) o con milímetro por el nombre. |
| **BOM** | Bill of Materials: lista de componentes para compra/ensamblado. | Asumir que la BOM incluye todo: los componentes con `in_bom=false` (mounting holes, fiduciales) se excluyen. |
| **Gerber** | Formato estándar de fabricación: un archivo por capa + drill files aparte. | Entregar Gerbers sin drill files: el fabricante no puede perforar. `export_manufacturing` genera ambos por eso. |
| **Netclass** | Grupo de nets con reglas compartidas (ancho de pista, clearance). | Ignorarlas al crear tracks: el ancho correcto depende de la netclass, no de un default global. |
| **Desacoplo (decoupling)** | Capacitor (típ. 100 nF) entre alimentación y GND, físicamente cerca de cada pin de poder de un IC. | Creer que la posición da igual porque "eléctricamente es lo mismo": la cercanía física ES el requisito de diseño. |
| **Pull-up / pull-down** | Resistencia a alimentación/GND que define el estado de reposo de una señal (típico en I2C: pull-ups en SDA/SCL). | Omitirlas en buses que las requieren, o duplicarlas cuando ya existen en otro módulo del bus. |
