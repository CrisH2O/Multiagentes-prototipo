# Análisis crítico de resultados

Documento de interpretación del simulador multiagente agrícola. Todos los
números provienen de `resultados/experimentos.csv`, generado con
`python experimentos.py` (80 corridas: 16 variantes × 5 repeticiones).

Las equivalencias con el campo (hectáreas, costales, litros por hectárea)
están fundamentadas en [`INVESTIGACION-AGRICOLA.md`](INVESTIGACION-AGRICOLA.md)
y se aplican con `Agentes/unidades.py`.

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
| Grid | 20 × 20 celdas = **3.24 ha** |
| Precio del combustible | **$27 MXN/L** (investigado, ver §2.5) |
| Salario | $2.5 por tick por tractor |
| Costo por semilla | $0.5 |

**Reproducibilidad.** Cada corrida usa una semilla `1..5`. La semilla fija a la
vez la elevación del terreno y la posición de los obstáculos
(`Agentes/escenarios.py`), así que cualquier fila del CSV se puede reconstruir
exactamente. Los 5 valores por variante permiten reportar desviación estándar.

**Garantía de conectividad.** Los obstáculos se colocan de uno en uno y se
descarta cualquier celda que parta el terreno en islas o encierre el depósito.

**Escala física.** Una celda equivale a 9 m × 9 m = 81 m², el ancho de trabajo
de una sembradora de 12 surcos a 76 cm. El campo completo son **3.24 ha**.

---

## 2. Resultados

### 2.1 Terreno — el relieve casi no importa

| Variante | Ticks | Costo total | **Por hectárea** | Combustible |
|---|---:|---:|---:|---:|
| Plano | 265 ± 7 | $23,360 ± 674 | **$7,210/ha** | 785 L |
| Colinas | 265 ± 7 | $23,548 ± 676 | $7,268/ha | 792 L |
| Montañoso | 265 ± 7 | $23,836 ± 682 | $7,357/ha | 802 L |

**Hallazgo:** pasar de plano a montañoso encarece la operación solo **2.0%**,
con los **mismos ticks** en las tres variantes.

**Por qué:** el costo de movimiento usa la *diferencia absoluta de elevación*
entre celdas contiguas (`agentesPrueba.TractorAgent.move_cost`), sin normalizar
por pendiente ni por distancia. Al subir y bajar continuamente, los sobrecostos
de subida se cancelan con los descuentos de bajada. **El modelo no está
midiendo lo que dice medir** (§5, limitación L1).

### 2.2 Tamaño de flota — más tractores saturan la coordinación

| Tractores | Ticks | Costo total | **Por hectárea** | Combustible | Colisiones |
|---:|---:|---:|---:|---:|---:|
| 1 | 783 ± 23 | $23,211 | $7,164/ha | 780 L | 0 |
| 2 | 405 ± 9 | $24,009 | $7,410/ha | 807 L | 2 |
| 3 | 265 ± 7 | $23,548 | $7,268/ha | 792 L | 0 |
| 5 | 180 ± 11 | $26,460 | $8,167/ha | 890 L | **8** |
| 8 | 117 ± 5 | $26,921 | **$8,309/ha** | 904 L | **27** |

**Hallazgo:** de 1 a 3 tractores el tiempo cae **2.95×** sin subir el costo. De
3 a 8 el tiempo cae otra **2.26×**, pero el costo por hectárea sube **14%** y
las colisiones pasan de 0 a 27.

**Por qué:** el algoritmo es *greedy* — cada tractor va a la celda pendiente más
cercana sin reservarla de forma definitiva. Con 5+ tractores convergen a la
misma zona, a la misma vuelta al depósito y a la misma celda de recarga.

**Conclusión:** **3 tractores es el punto de equilibrio**. Añadir máquinas
acelera la siembra pero destruye la ventaja en costo.

### 2.3 Obstáculos — más fragmentos, más vuelta

| Obstáculos | Ticks | Costo total | **Por hectárea** | Pasos repetidos |
|---:|---:|---:|---:|---:|
| 0 | 243 ± 0 | $21,618 | $6,672/ha | 23% |
| 20 | 260 ± 14 | $23,077 | $7,122/ha | 30% |
| 50 | 270 ± 10 | $23,644 | $7,298/ha | 32% |
| 100 | 293 ± 52 | $24,764 | **$7,643/ha** | **44%** |

**Hallazgo:** con 100 obstáculos el costo sube **15%** y los pasos repetidos
crecen de **23% a 44%**, casi el doble. La desviación estándar también explota
(±$3,842): el rendimiento se vuelve muy dependiente de la forma del terreno.

### 2.4 Capacidad de semillas — el factor dominante

| Tanque | Ticks | Costo total | **Por hectárea** | Combustible | Cobertura por carga |
|---:|---:|---:|---:|---:|---:|
| 10 | 610 ± 13 | **$53,488** | **$16,509/ha** | 1,805 L | 0.08 ha |
| 20 | 417 ± 83 | $36,823 | $11,365/ha | 1,241 L | 0.16 ha |
| 35 | 265 ± 7 | $23,548 | $7,268/ha | 792 L | **0.28 ha** |
| 60 | 219 ± 6 | **$19,482** | **$6,013/ha** | 654 L | **0.49 ha** |

**Hallazgo:** pasar de 10 a 60 unidades de tanque reduce el costo **2.74×**
($16,509 → $6,013 por hectárea).

**Por qué:** cada recarga implica un viaje de ida y vuelta al depósito *sin
sembrar*. Con 10 unidades, 364 celdas exigen ~36 viajes; con 60, solo 6. El
combustible de esos viajes muertos es lo que dispara el costo: 1,805 L contra
654 L.

**Conclusión:** la decisión con mayor retorno no es la ruta ni el terreno, sino
**la capacidad de carga**.

En unidades de campo, un costal de 20 kg rinde ≈ 1 ha ≈ 123 celdas, así que
**un tanque de 60 unidades cubre 0.49 ha**: medio costal por carga. El tanque
actual (35) cubre apenas **0.28 ha**, y es la razón por la que el tractor pasa
la mayor parte del tiempo viajando al depósito.

### 2.5 El resultado, en unidades de campo

El campo simulado son **3.24 ha**, que en maíz equivalen a **≈ 3.2 costales de
semilla de 20 kg** (un costal ≈ 1 ha ≈ 123 celdas). Con eso, el orden de
magnitud real sería:

| Concepto | Valor real esperado (3.24 ha) |
|---|---:|
| Semilla | ≈ 3.2 costales (≈ $4,800 si el costal está a $1,500) |
| Diésel de siembra | 28 – 35 L (8.6 – 10.77 L/ha) |
| Costo de diésel | $752 – $945 |
| Tiempo de siembra | ≈ 0.7 h (4.6 ha/h) |
| **Costo de combustible por ha** | **$232 – $291** |

Compárese con lo que reporta el simulador: **$7,268/ha** y **240 L/ha** de
combustible. La diferencia no es un error de cálculo, es **falta de
calibración** (§5, L8).

---

## 3. Métricas globales (80 corridas)

| Métrica | Valor |
|---|---|
| Cobertura | **100% en las 80 corridas** |
| Siembras dobles | **0** |
| Colisiones | 59 (22 corridas con al menos una) |
| Pasos repetidos | **34.2%** de media |
| Máximo de visitas a una misma celda | **95** |
| Costo medio por hectárea | **$8,128/ha** |

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

---

## 5. Limitaciones del modelo

**L1 — El relieve está subrepresentado.** El costo por pendiente usa
`1 + Δelevación × 0.5 × dificultad` con Δelevación ≈ 0.01–0.10 por paso. Un
desnivel real de 100 m en 9 m de avance cuesta lo mismo que una loma suave.
Debería usarse pendiente normalizada por distancia.

**L2 — El depósito genera colisiones.** Todos los tractores comparten `(0,0)` y
el BFS excluye las celdas ocupadas *excepto* el depósito. Se concentra en
configuraciones con muchas recargas y flotas grandes (8 tractores → 27).

**L3 — Repetición de tramos no penalizada.** No hay memoria de celdas ya
transitadas, solo de celdas sembradas.

**L4 — No hay línea base zigzag.** Sin benchmark, la afirmación "ruta óptima"
no se puede sostener.

**L5 — El precio del combustible es un supuesto.** Ahora vale **$27/L**, con
rango de sensibilidad $25.39–$28.00 (ver investigación). Como el combustible es
~89% del costo, el ranking no cambia, pero el monto absoluto escala con él.

**L6 — La aleatoriedad de Unity no está sembrada.** `PlantingGrid` y
`TerrainGenerator` usan `Random.Range` sin `InitState`, así que la corrida
visual del editor no es reproducible. Los experimentos sí lo son.

**L7 — Cobertura siempre 100%.** El modelo marca como resueltas las celdas
inalcanzables, así que "cobertura" no distingue un terreno bien sembrado de uno
con zonas vedadas.

**L8 — El modelo no está calibrado contra la realidad.** Sus magnitudes son
internas y coherentes, pero no representan el campo:

| Concepto | Simulador | Realidad | Factor |
|---|---:|---:|---:|
| Combustible | 240 L/ha | 8.6 – 10.77 L/ha | **~25×** |
| Semilla | 364 "unidades" | ~194,400 semillas (3.2 costales) | **~530×** |
| Salario | $2.5/tick ≈ $1,667/h | ≈ $45–70/h | **~25–35×** |
| Tiempo (1 tractor) | 783 ticks | ≈ 42 min (467 ticks) | ~1.7× |

Por eso los resultados son válidos **en comparación relativa**, no en pesos
absolutos por hectárea.

---

## 6. Mejoras propuestas (justificadas)

1. **Penalizar la repetición de tramos** (L3). Añadir `costo × (1 + α ×
   visitas_previas)`. Afecta al 34% de los pasos.
2. **Modelar el depósito como recurso** (L2). Cola de recarga o varios puntos.
   Elimina hasta 27 colisiones por corrida.
3. **Normalizar pendiente por distancia** (L1). Convertiría el terreno en una
   variable con efecto real.
4. **Implementar la línea base zigzag** (L4). Es el benchmark prometido.
5. **Sembrar el RNG de Unity** (L6). `Random.InitState(payload.semilla)`.
6. **Reemplazar greedy por asignación global** (subasta o reserva de objetivo).
7. **Calibrar el modelo con el preset realista** (L8). Tanque de 123 unidades
   (1 costal), 8.6 L/ha y salario por hora real; así las cifras absolutas
   pasarían a ser defendibles.

---

## 7. Cómo reproducir todo

```bash
# 1. Entorno
uv sync

# 2. Tests (55)
cd Agentes && ../.venv/bin/python -m pytest -q && cd ..

# 3. Experimentos (≈25 s, genera CSV + fotogramas)
.venv/bin/python experimentos.py

# 4. Figuras y dashboard
.venv/bin/python figuras.py
.venv/bin/python -m streamlit run dashboard.py
```

Los resultados corresponden a `resultados/experimentos.csv` (80 filas, 27
columnas, reproducible byte a byte).
