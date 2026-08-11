# 04 — Hallazgos fuera de scope (§14)

No corregidos en S47 (READ-ONLY). Elevados al humano vía `05-veredicto.md`.

---

```
ID:         H-S47-01
Categoría:  DRIFT_DOC
Prioridad:  P1
Ubicación:  nota-invocacion-S47.md, campo S47_TMP
Evidencia:  la nota firmada registra literalmente
              S47_TMP: /tmp/tmp.xOUY807dLa.s47
            (directorio vacío, `ls -la` confirma creado 10:54, sin
            contenido). El shell de la sesión exportó y usó
              S47_TMP=/tmp/tmp.ZedgZwIGVl.s47
            (creado 11:07, receptor real de PYTHONPYCACHEPREFIX,
            MYPY_CACHE_DIR, RUFF_CACHE_DIR, UV_CACHE_DIR). Ambas rutas
            verificadas fuera del working tree con realpath.
Impacto:    la nota §11.9, tal como quedó firmada, no describe con
            precisión el entorno de ejecución real. La Autoridad ratificó
            expresamente la ruta del entorno como la correcta durante esta
            sesión (ver 00-preflight.md §2) antes de que Puerta 0
            avanzara — no bloqueó la ejecución (Regla 6 de la fe de
            erratas: la divergencia de un campo operativo secundario,
            resuelta por ratificación humana explícita, no es ninguna de
            las 4 causas de NO_GO_ENTRADA).
Acción tomada: ninguna corrección de la nota (fuera de alcance, F1-style
            para documentos de invocación). Se registra para que quien
            firme la próxima nota (S48) copie la ruta real de $S47_TMP
            DESPUÉS de exportarla, no antes.
```

```
ID:         H-S47-02
Categoría:  DRIFT_DOC
Prioridad:  P2
Ubicación:  archivos_temporales_contrato/ (paquete de invocación entregado)
Evidencia:  v6 delega explícitamente en v5 para §§7.1.3-7.1.5, 7.2, 7.3,
            11.2 (V0.1-V0.6), 11.4 (S1-S8), 11.5 (R1-R14), 11.7.bis, 11.8,
            13.1/13.2 ("Igual a v5", "Idéntico a v5"). El archivo
            contrato_S47-DT1-SLICE2-CARACTERIZACION_v5.md NO estaba
            presente en archivos_temporales_contrato/. Se localizó una
            copia en ~/.local/share/Trash/files/ (papelera del sistema,
            fuera del working tree), SHA-256
            3fc56ce82ae5c7a396bd667e55228785e2073ea556373846cf0696ed6c75b7a2,
            que coincide exactamente con el hash "3fc56ce8…" que el propio
            encabezado de v6 (línea 4) cita como la v5 que auditó ChatGPT.
Impacto:    sin la localización manual de esta copia, S47 habría tenido
            que detenerse en EVIDENCIA_INSUFICIENTE ya en Fase 2/3 por
            falta de las reglas S1-S8/R1-R14 operativas. La Autoridad
            aprobó expresamente usar esta copia verificada por hash antes
            de iniciar Puerta 0 (ver 00-preflight.md §6).
Acción tomada: ninguna corrección del paquete de invocación (fuera de
            alcance). Se recomienda que el próximo contrato READ-ONLY
            (S48, si se autoriza) incluya v5 explícitamente en el paquete
            de archivos_temporales_contrato/, o que v6 deje de delegar y
            copie las secciones necesarias in extenso — consistente con el
            compromiso de la fe de erratas §3 ("plantilla mínima... sin
            repetir sobrecontrol").
```

```
ID:         H-S47-03
Categoría:  RIESGO_NUEVO / DRIFT_AFECTA_CANDIDATO
Prioridad:  P2
Ubicación:  6 de los 12 candidatos materializados (fichas 3, 4, 5, 6, 9, 12
            — ver 04-colisiones.md)
Evidencia:  docs/BACKLOG.md:519-529 (DT3, "Geometría de dominio dentro de
            bridge/... Próximo paso: caracterización independiente. No
            mezclar con el siguiente slice de DT1 sin decisión humana.").
            6 de los 12 candidatos de esta sesión son clusters de
            geometría de coordenadas (distancia punto-bbox,
            intersección de segmentos, SDF de rectángulo redondeado,
            colisión pad-track) que viven en tools/pcb.py, NO en bridge/
            — DT3 está acotada textualmente a bridge/, así que no hay
            colisión de ubicación ni de código con DT3 tal como está
            definida hoy.
Impacto:    si una futura sesión (S48/S49, u otra) decide extraer alguno
            de estos 6 candidatos SIN haber resuelto primero dónde debe
            vivir arquitectónicamente la geometría de dominio (la pregunta
            que DT3 deja abierta), podría fijar la deuda en un TERCER
            lugar (un nuevo módulo en tools/) antes de que DT3 responda
            "¿debería toda la geometría de dominio vivir junta, y dónde?".
            Esto no es una colisión técnica hoy, es un riesgo de secuencia
            de decisiones.
Acción tomada: ninguna (S47 es READ-ONLY, no decide secuencia de sesiones).
            Elevado explícitamente para que el humano considere resolver
            DT3 antes de autorizar S48 sobre cualquiera de estos 6
            candidatos, o documente conscientemente que se acepta el
            riesgo de una tercera ubicación.
```

```
ID:         H-S47-04
Categoría:  PRIOR_HISTORICO_NO_REPRODUCIDO (parcial)
Prioridad:  P3
Ubicación:  docs/analisis/40-dt1-caracterizacion.md §9
Evidencia:  el prior "Zonas (validación)" (apto, al límite del criterio
            "una familia funcional" de contrato v2) no se puede
            re-evaluar como candidato apto bajo v6 — F-DT.1 lo excluye
            institucionalmente antes de llegar a Fase 3 (ver
            01-inventario-actual.md §9, 02-candidatos/descartados.md #2).
Impacto:    ninguno operativo — es un cambio de contrato (v2 → v6
            endureció el criterio de exclusión de zonas), no una
            regresión ni un hallazgo de código. Se registra por
            completitud de §7.2 (contraste con priors históricos).
Acción tomada: ninguna — documentado como evolución de contrato en
            01-inventario-actual.md §9 y 03-refutacion.md CR1.
```

```
ID:         H-S47-05
Categoría:  LIMITACION_METODOLOGICA
Prioridad:  P3
Ubicación:  01-inventario-actual.md §8
Evidencia:  frontera_entrante_tests(K), definida literalmente en §7.1.2
            como "importa o patcha por path pcb.<k>", no captura el
            mecanismo real por el que la suite ejerce los 19 @mcp.tool de
            pcb.py: invocación dinámica del registro FastMCP
            (client.call_tool("<nombre>", {...})), despacho por string, no
            import/patch de path Python.
Impacto:    bajo la definición literal, frontera_entrante_tests reporta
            0 para 18 de los 19 mcp_tools, lo que podría leerse
            erróneamente como "sin cobertura de tests". Se mitigó
            construyendo un trazador complementario
            ($S47_TMP/tools/coverage.py) que sí captura la invocación
            call_tool con evidencia de assert sobre el resultado, citado
            nominalmente en cada ficha de candidato con closure (§10-M4).
Acción tomada: ninguna corrección de código; documentado como limitación
            metodológica explícita y mitigado con evidencia complementaria
            dentro de esta misma sesión, conforme a Regla 4 de la fe de
            erratas.
```
