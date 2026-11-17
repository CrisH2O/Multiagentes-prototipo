# Análisis crítico de resultados

Documento de interpretación del simulador multiagente agrícola. Todos los
números provienen de `resultados/experimentos.csv`, generado con
`python experimentos.py` (80 corridas: 16 variantes × 5 repeticiones).

---

## 1. Metodología

**Diseño experimental.** Cuatro bloques que aíslan **una variable a la vez**.
El resto de parámetros se mantiene en su valor base:

| Parámetro base | Valor |
|---|---|
| Terreno | colinas (dificultad 2) |
| Tractores | 3 |
| Obstáculos | 35 |
| Semillas por tanque | 35 |
| Grid | 20 × 20 celdas |
| Precio del combustible | $24 MXN/L (supuesto, ver §5) |
| Salario | $2.5 por tick por tractor |
| Costo por semilla | $0.5 |

**Reproducibilidad.** Cada corrida usa una semilla `1..5`. La semilla fija a la
vez la elevación del terreno y la posición de los obstáculos
(`Agentes/escenarios.py`), así que cualquier fila del CSV se puede reconstruir
exactamente. Los 5 valores por variante permiten reportar desviación estándar
en lugar de un solo número.

**Garantía de conectividad.** Los obstáculos se colocan de uno en uno y se
descarta cualquier celda que parta el terreno en islas o encierre el depósito.
Sin esto aparecían corridas degeneradas (0 celdas alcanzables, 1 tick) que
sesgaban los promedios en ~4%.

---

## 2. Resultados

### 2.1 Terreno — el relieve casi no importa

| Variante | Ticks | Costo total | Combustible |
|---|---:|---:|---:|
| Plano | 265 ± 7 | $21,005 ± 605 | 785 L |
| Colinas | 265 ± 7 | $21,173 ± 607 | 792 L |
| Montañoso | 265 ± 7 | $21,429 ± 612 | 802 L |

**Hallazgo:** pasar de plano a montañoso encarece la operación solo **2.0%**,
con los **mismos ticks** en las tres variantes.

**Por qué:** el costo de movimiento usa la *diferencia absoluta de elevación*
entre celdas contiguas (`agentesPrueba.TractorAgent.move_cost`), sin
normalizar por pendiente ni por distancia. Al subir y bajar continuamente, los
sobrecostos de subida se cancelan con los descuentos de bajada. El resultado es
que la topografía casi no discrimina: **el modelo no está midiendo lo que dice
medir** (§5, limitación L1).

*Consecuencia práctica:* el terreno no sirve para elegir ruta; solo aporta
realismo visual. Es la diferencia entre "mostrar el terreno" y "optimizar según
el terreno".

### 2.2 Tamaño de flota — más tractores saturan la coordinación

| Tractores | Ticks | Costo total | Combustible | Colisiones |
|---:|---:|---:|---:|---:|
| 1 | 783 ± 23 | $20,870 | 780 L | 0 |
| 2 | 405 ± 9 | $21,587 | 807 L | 2 |
| 3 | 265 ± 7 | $21,173 | 792 L | 0 |
| 5 | 180 ± 11 | $23,791 | 890 L | **8** |
| 8 | 117 ± 5 | $24,210 | 904 L | **27** |

**Hallazgo:** de 1 a 3 tractores el tiempo cae **2.95×** sin subir el costo.
De 3 a 8 el tiempo cae otra **2.26×**, pero el costo sube **14%** y las
colisiones pasan de 0 a 27.

**Por qué:** el algoritmo es *greedy* — cada tractor va a la celda pendiente más
cercana sin reservarla de forma definitiva. Con pocos tractores casi no
compiten; con 5+ convergen a la misma zona, a la misma vuelta al depósito y a
la misma celda de recarga. El depósito se convierte en un cuello de botella.

**Conclusión:** para este terreno, **3 tractores es el punto de equilibrio**.
Añadir máquinas acelera la siembra pero destruye la ventaja en costo.

### 2.3 Obstáculos — más fragmentos, más vuelta

| Obstáculos | Ticks | Costo total | Pasos repetidos |
|---:|---:|---:|---:|
| 0 | 243 ± 0 | $19,441 | 23% |
| 20 | 260 ± 14 | $20,750 | 30% |
| 50 | 270 ± 10 | $21,261 | 32% |
| 100 | 293 ± 52 | $22,273 | 44% |

**Hallazgo:** con 100 obstáculos el costo sube **15%** y los pasos repetidos
crecen de **23% a 44%**, casi el doble. La desviación estándar también explota
(±$3,458): el rendimiento se vuelve muy dependiente de la forma del terreno.

**Por qué:** el modelo no penaliza volver a cruzar una celda recorrida. Es la
degradación silenciosa: la cobertura sigue siendo 100%, así que el sistema
"parece" igual de eficiente, pero recorre más terreno por la misma tarea.

### 2.4 Capacidad de semillas — el factor dominante

| Semillas/tanque | Ticks | Costo total | Combustible | Colisiones |
|---:|---:|---:|---:|---:|
| 10 | 610 ± 13 | **$48,074** | 1,805 L | 6 |
| 20 | 417 ± 83 | $33,100 | 1,241 L | 5 |
| 35 | 265 ± 7 | $21,173 | 792 L | 0 |
| 60 | 219 ± 6 | **$17,520** | 654 L | 0 |

**Hallazgo:** pasar de 10 a 60 semillas por tanque reduce el costo **2.74×**
($48,074 → $17,520). Es el efecto más grande de todos los bloques, muy por
encima del terreno (2.0%) o de la flota (14%).

**Por qué:** cada recarga implica un viaje de ida y vuelta al depósito *sin
sembrar*. Con 10 semillas, 364 celdas exigen ~36 viajes; con 60, solo 6. El
combustible de esos viajes muertos es lo que dispara el costo: 1,805 L contra
654 L (2.76× más).

**Conclusión:** la decisión con mayor retorno no es la ruta ni el terreno, sino
**la capacidad de carga**. Optimizar la logística de reabastecimiento importa
más que optimizar el pathfinding.

---

## 3. Métricas globales (80 corridas)

| Métrica | Valor |
|---|---|
| Cobertura | **100% en las 80 corridas** |
| Siembras dobles | **0** |
| Colisiones | 59 (22 corridas con al menos una) |
| Pasos repetidos | **34.2%** de media |
| Máximo de visitas a una misma celda | **95** |

**Lectura:** el sistema cumple de forma robusta dos garantías (cubrir todo, no
sembrar dos veces) y falla sistemáticamente en una (no repetir tramo). El
máximo de **95 visitas a una sola celda** es la evidencia más cruda de que el
pathfinding puede entrar en ciclo cuando el objetivo está bloqueado.

---

## 4. Comparación con la propuesta original

| Compromiso | Estado |
|---|---|
| Cubrir todo el terreno | ✅ 100% |
| No sembrar dos veces | ✅ 0 casos |
| No chocar con obstáculos | ✅ el BFS evita obstáculos |
| No chocar entre agentes | ⚠️ 59 colisiones en 80 corridas |
| No pasar más de una vez por el mismo tramo | ❌ 34.2% de los pasos |
| Reducir costo frente a zigzag base | ❌ no implementado |

Las dos últimas no son requisitos de la rúbrica, pero sí son la promesa central
del proyecto, y aquí se declaran explícitamente como deuda.

---

## 5. Limitaciones del modelo

**L1 — El relieve está subrepresentado.** El costo por pendiente usa
`1 + Δelevación × 0.5 × dificultad` con Δelevación ≈ 0.01–0.10 por paso. Un
desnivel real de 100 m en 9 m de avance (pendiente > 1000%) cuesta lo mismo
que una loma suave. El terreno debería entrar como *pendiente normalizada por
distancia* (desnivel / separación entre celdas).

**L2 — El depósito genera colisiones.** Todos los tractores comparten `(0,0)`.
El BFS excluye las celdas ocupadas *excepto* el depósito, así que dos tractores
pueden terminar en la misma celda. Se concentra en configuraciones con muchas
recargas y con flotas grandes (8 tractores → 27 colisiones).

**L3 — Repetición de tramos no penalizada.** No hay memoria de celdas ya
transitadas, solo de celdas sembradas. El pathfinding no puede evitar pasar por
tramos repetidos porque no los conoce.

**L4 — No hay línea base zigzag.** Sin un benchmark, la afirmación "ruta
óptima" no se puede sostener. Los números actuales son *absolutos*, no
*relativos* a una alternativa.

**L5 — El precio del combustible es un supuesto.** $24 MXN/L es una
estimación. El ranking no cambia con el precio porque el combustible domina
~89% del costo, pero el valor absoluto del ahorro sí escala con él.

**L6 — La aleatoriedad de Unity no está sembrada.** `PlantingGrid` y
`TerrainGenerator` usan `Random.Range` sin `InitState`, así que la corrida
visual del editor **no es reproducible**. Los experimentos sí lo son porque se
generan en Python.

**L7 — Cobertura siempre 100%.** El modelo marca como resueltas las celdas
inalcanzables, así que "cobertura" no distingue un terreno bien sembrado de uno
con zonas vedadas. Es una métrica que no puede fallar.

---

## 6. Mejoras propuestas (justificadas)

1. **Penalizar la repetición de tramos** (L3). Añadir al costo una celda ya
   transitada: `costo × (1 + α × visitas_previas)`. Afecta al 34% de los pasos,
   el mayor desperdicio medido.
2. **Modelar el depósito como recurso** (L2). Cola de recarga con una sola
   posición, o varios puntos de recarga. Elimina hasta 27 colisiones por corrida.
3. **Normalizar pendiente por distancia** (L1). Convertiría el terreno en una
   variable con efecto real y justificaría el módulo de elevación.
4. **Implementar la línea base zigzag** (L4). Es el benchmark que el proyecto
   promete; sin él no hay "optimización" demostrable.
5. **Sembrar el RNG de Unity** (L6). `Random.InitState(payload.semilla)` para
   que la demo visual coincida con el CSV.
6. **Reemplazar greedy por asignación global.** Subasta o vecino más cercano
   con reserva de objetivo: atacaría de raíz las colisiones y la repetición.

---

## 7. Cómo reproducir todo

```bash
# 1. Entorno
uv sync                      # o: pip install -r Agentes/requirements.txt

# 2. Tests (55)
cd Agentes && ../.venv/bin/python -m pytest -q && cd ..

# 3. Experimentos (≈25 s, genera CSV + fotogramas)
.venv/bin/python experimentos.py

# 4. Dashboard
.venv/bin/python -m streamlit run dashboard.py
```

Los resultados de este documento corresponden a la corrida registrada en
`resultados/experimentos.csv` (80 filas).
