# Análisis crítico de resultados

Documento de interpretación del simulador multiagente agrícola. Todos los
números provienen de `resultados/experimentos.csv`, generado con
`python experimentos.py` (90 corridas: 18 variantes × 5 repeticiones).

El modelo está **calibrado en unidades de campo** (hectáreas, costales, litros
por hectárea) con base en [`INVESTIGACION-AGRICOLA.md`](INVESTIGACION-AGRICOLA.md)
y `Agentes/unidades.py`.

---

## 1. Metodología

**Diseño experimental.** Cinco bloques que aíslan **una variable a la vez**.
El resto de parámetros se mantiene en su valor base:

| Parámetro base | Valor | De dónde sale |
|---|---|---|
| Terreno | colinas (dificultad 2) | — |
| Tractores | 3 | — |
| Obstáculos | 35 | — |
| **Tanque de semilla** | **1 costal ≈ 1 ha ≈ 123 celdas** | costal de 20 kg = 60,000 semillas |
| **Diésel** | **0.0697 L por celda** (8.6 L/ha) | estudio con monitor SeedStar |
| Tanque de diésel | 300 L | tractor mediano |
| **Precio del diésel** | **$27 MXN/L** | PROFECO / SENER 2026 |
| **Mano de obra** | **$50 MXN/h** → $0.075 por tick | jornal del operador |
| Grid | 20 × 20 celdas = **3.24 ha** | celda de 9 m (12 surcos × 76 cm) |

**Reproducibilidad.** Cada corrida usa una semilla `1..5`, que fija a la vez el
terreno y los obstáculos. Cualquier fila del CSV se reconstruye exactamente.

**Dos métricas de costo por hectárea.** Distinguirlas importa:

- **$/ha del lote**: costo total ÷ 3.24 ha (incluye caminos y obstáculos).
- **$/ha sembrada**: costo total ÷ hectáreas realmente sembradas.

Los obstáculos reducen el área sembrable, así que el costo por hectárea del
lote baja sin que el sistema sea más eficiente. La métrica honesta es la
segunda.

---

## 2. Resultados

### 2.1 El resultado principal: el planificador le gana a la ruta base

| Estrategia | Ticks | **$/ha sembrada** | Combustible | Pasos repetidos |
|---|---:|---:|---:|---:|
| **Greedy (nuestro)** | **176 ± 5** | **$1,851** | 11.4 L/ha | 16% |
| Zigzag (línea base) | 211 ± 7 | $1,920 | 13.6 L/ha | 25% |

**Hallazgo:** el planificador es **17% más rápido** y **3.6% más barato** que la
ruta base en serpiente, con **menos pasos repetidos** (16% vs 25%).

Esto cierra la promesa central de la propuesta: ya existe una comparación
contra la ruta zigzag con las mismas métricas y los mismos mapas.

> El ahorro en dinero es modesto porque el 81% del costo es semilla, que no
> cambia con la ruta. **La ventaja real está en el tiempo y el combustible.**

### 2.2 Terreno — el relieve sigue sin importar

| Variante | Ticks | $/ha sembrada | Combustible |
|---|---:|---:|---:|
| Plano | 176 ± 5 | $1,849 | 11.3 L/ha |
| Colinas | 176 ± 5 | $1,851 | 11.4 L/ha |
| Montañoso | 176 ± 5 | $1,857 | 11.6 L/ha |

**Hallazgo:** de plano a montañoso la diferencia es **0.4%**, con los mismos
ticks.

**Por qué:** el costo de movimiento usa la *diferencia absoluta de elevación*
entre celdas contiguas, sin normalizar por pendiente ni distancia. Al subir y
bajar continuamente, los sobrecostos de subida se cancelan con los descuentos
de bajada. **El modelo no está midiendo lo que dice medir** (limitación L1).

### 2.3 Tamaño de flota — acelera sin encarecer

| Tractores | Ticks | $/ha sembrada | Combustible | Colisiones |
|---:|---:|---:|---:|---:|
| 1 | 518 ± 15 | $1,846 | 11.2 L/ha | 0 |
| 2 | 271 ± 8 | $1,861 | 11.7 L/ha | 0 |
| 3 | 176 ± 5 | $1,851 | 11.4 L/ha | 0 |
| 5 | 104 ± 7 | $1,842 | 11.1 L/ha | 6 |
| 8 | 68 ± 6 | $1,848 | 11.3 L/ha | **21** |

**Hallazgo:** de 1 a 8 tractores el tiempo cae **7.6×** con el costo
prácticamente **plano** (variación < 1%). El precio a pagar son las
**colisiones**: de 0 a 21 por corrida.

**Por qué:** en unidades reales, la semilla domina el costo y es la misma sin
importar cuántos tractores haya. El combustible y el jornal por hectárea son
casi constantes. Por eso **añadir máquinas compra tiempo, no dinero**.

**Conclusión:** con 8 tractores el sistema se coordina mal (21 colisiones) pero
el costo no se degrada. El límite práctico lo pone la coordinación, no la
economía.

### 2.4 Obstáculos — el costo baja, la eficiencia no mejora

| Obstáculos | Ticks | $/ha del lote | **$/ha sembrada** | Pasos repetidos |
|---:|---:|---:|---:|---:|
| 0 | 198 ± 0 | $1,856 | $1,860 | 15% |
| 20 | 202 ± 12 | $1,787 | $1,886 | 17% |
| 50 | 164 ± 12 | $1,605 | $1,839 | 17% |
| 100 | 173 ± 13 | **$1,430** | **$1,913** | **25%** |

**Hallazgo:** el costo por hectárea *del lote* cae 23% con 100 obstáculos… pero
es un espejismo: hay **menos hectáreas que sembrar**. Al normalizar por
hectárea **sembrada**, el costo en realidad **sube** ($1,860 → $1,913) y los
pasos repetidos pasan de 15% a 25%.

**Lección metodológica:** cambiar el denominador cambia la conclusión. Es el
tipo de trampa que hay que evitar al reportar "costo por hectárea".

### 2.5 Capacidad del tanque — importa, pero menos de lo esperado

| Costales por tanque | Ticks | $/ha sembrada | Combustible | Pasos repetidos |
|---:|---:|---:|---:|---:|
| 0.25 (≈ 0.25 ha) | 271 ± 9 | **$2,036** | 17.4 L/ha | 31% |
| 0.5 | 210 ± 9 | $1,917 | 13.5 L/ha | 21% |
| **1.0** | 176 ± 5 | $1,851 | 11.4 L/ha | 16% |
| 2.0 | 161 ± 8 | **$1,821** | 10.4 L/ha | 13% |

**Hallazgo:** con un cuarto de costal por tanque el costo sube **11.8%**
respecto a un tanque lleno, y el combustible **67%** (17.4 vs 10.4 L/ha).

**Por qué:** cada recarga es un viaje al depósito sin sembrar. Con 0.25 costales
caben 31 celdas, así que el tractor pasa más tiempo viajando que sembrando.

**Conclusión:** el tanque de **un costal completo** es el punto de equilibrio:
duplicarlo a dos costales solo ahorra 1.6% más de costo.

---

## 3. Métricas globales (90 corridas)

| Métrica | Valor |
|---|---|
| Cobertura | **100% en las 90 corridas** |
| Siembras dobles | **0** |
| Colisiones | 39 (19 corridas con al menos una) |
| Pasos repetidos | **18.3%** de media |
| Máximo de visitas a una misma celda | **7** |
| Combustible | **9.4 – 18.4 L/ha** (media 11.9) |
| Costo | **$1,803 – $2,067 por hectárea sembrada** |

**Validación contra la realidad:** la literatura indica 8.6–10.77 L/ha para
siembra de maíz. El simulador queda en 10.4–11.6 L/ha en las configuraciones
razonables (hasta 18.4 L/ha cuando el tanque es de un cuarto de costal). Es una
**desviación de 3–10%** en el rango operativo normal, y se explica porque el
modelo incluye los viajes de recarga, que el estudio de campo no mide.

---

## 4. Comparación con la propuesta original

| Compromiso | Estado |
|---|---|
| Cubrir todo el terreno | ✅ 100% |
| No sembrar dos veces | ✅ 0 casos |
| No chocar con obstáculos | ✅ el BFS evita obstáculos |
| No chocar entre agentes | ⚠️ 39 colisiones en 90 corridas |
| No pasar más de una vez por el mismo tramo | ⚠️ 18.3% de los pasos |
| **Reducir costo/tiempo frente al zigzag base** | ✅ **17% más rápido, 3.6% más barato** |

---

## 5. Limitaciones del modelo

**L1 — El relieve está subrepresentado.** El costo por pendiente usa
`1 + Δelevación × 0.5 × dificultad` con Δelevación ≈ 0.01–0.10 por paso. Un
desnivel real de 100 m en 9 m de avance cuesta lo mismo que una loma suave.
Debería usarse pendiente normalizada por distancia.

**L2 — El depósito genera colisiones.** Todos los tractores comparten `(0,0)` y
el BFS excluye las celdas ocupadas *excepto* el depósito. 21 colisiones con 8
tractores.

**L3 — Repetición de tramos no penalizada.** No hay memoria de celdas ya
transitadas, solo de celdas sembradas. Sigue en 18.3%.

**L4 — La línea base zigzag es única.** Existen rutas base mejores (boustrophedon
con división por bloques, franjas paralelas); comparar contra una sola favorece
al planificador.

**L5 — Precio del diésel supuesto.** $27/L con rango $25.39–$28.00. Como el
combustible pesa ~17% del costo, un cambio de precio no altera el ranking.

**L6 — La aleatoriedad de Unity no está sembrada.** `PlantingGrid` y
`TerrainGenerator` usan `Random.Range` sin `InitState`, así que la corrida
visual del editor no es reproducible. Los experimentos sí lo son.

**L7 — Cobertura siempre 100%.** El modelo marca como resueltas las celdas
inalcanzables, así que "cobertura" no distingue un terreno bien sembrado de uno
con zonas vedadas.

**L8 — Calibración parcial.** La semilla está calibrada por construcción
(1 costal = 1 ha), pero **ese 81% del costo no es un resultado del modelo, es
una identidad**. El combustible sí es un resultado y queda 3–10% arriba de la
literatura. El modelo **no** captura depreciación de maquinaria, tiempo de
traslado al lote ni costo de preparación del terreno.

---

## 6. Mejoras propuestas (justificadas)

1. **Penalizar la repetición de tramos** (L3). Añadir `costo × (1 + α ×
   visitas_previas)`. Afecta al 18.3% de los pasos.
2. **Modelar el depósito como recurso** (L2). Cola de recarga o varios puntos.
   Elimina hasta 21 colisiones por corrida.
3. **Normalizar pendiente por distancia** (L1). Convertiría el terreno en una
   variable con efecto real.
4. **Ampliar la línea base** (L4). Comparar contra franjas paralelas y contra
   división del campo por zonas.
5. **Sembrar el RNG de Unity** (L6). `Random.InitState(payload.semilla)`.
6. **Incorporar costos fijos** (L8). Depreciación y preparación del terreno
   harían que el costo por hectárea se acerque al valor completo de la labor.

---

## 7. Cómo reproducir todo

```bash
uv sync
cd Agentes && ../.venv/bin/python -m pytest -q && cd ..
.venv/bin/python experimentos.py
.venv/bin/python figuras.py
.venv/bin/python -m streamlit run dashboard.py
```

Resultados: `resultados/experimentos.csv` (90 filas, reproducible byte a byte).
