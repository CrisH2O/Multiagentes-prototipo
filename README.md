# Plantación Óptima — Simulador multiagente de siembra

**Reto John Deere** · Simulación de una flota de tractores que debe sembrar un
terreno irregular al menor costo posible, con arquitectura de agentes y
comunicación explícita.

El sistema responde una pregunta concreta: **¿qué variables de diseño mueven
de verdad el costo de siembra?** La respuesta, medida en 80 corridas
controladas, está en [`ANALISIS.md`](ANALISIS.md): la capacidad de semillas
(2.74× el costo) pesa mucho más que el relieve (2%) o el tamaño de flota (14%).

---

## 1. El problema

Sembrar un campo irregular es un problema de **coordinación bajo
restricciones**, no de trayectoria: varios vehículos comparten terreno,
combustible, semillas y una estación de recarga, y cada decisión de uno altera
el costo de los demás.

**Entradas**

| Entrada | Descripción |
|---|---|
| `elevation_map` | Matriz `n×n` de elevaciones relativas en `[0,1]` |
| `obstacle_map` | Matriz `n×n` binaria (`1` = intransitable) |
| `grid_size` | Tamaño del terreno en celdas |
| `difficulty` | 1 plano · 2 colinas · 3 montañoso |
| `n_agents` | Número de tractores (1–8) |
| `max_fuel` | Capacidad del tanque |
| `max_seeds` | Semillas por carga |
| `wage_per_tick`, `cost_per_seed` | Costos unitarios |

**Salidas**

- `frames[]`: un fotograma por tick con posición, combustible, semillas,
  estado y celdas sembradas de cada tractor.
- `metrics`: ticks totales, pasos, combustible consumido, costo de salarios,
  costo de semillas y celdas restantes.

**Preguntas de experimentación**

1. ¿Cuánto encarece el relieve la misma tarea?
2. ¿Cuántos tractores conviene mandar antes de que se estorben?
3. ¿Cuánto degrada un terreno más fragmentado el recorrido?
4. ¿Cuánto cuesta reabastecerse muchas veces?

**Simplificaciones declaradas:** no se modela la física del suelo, el clima ni
sensores; el campo es una rejilla 2D; un tick equivale a un paso de celda.

---

## 2. Arquitectura y comunicación entre agentes

```
        ┌─────────────────────────────┐
        │  escenarios.py              │   genera terreno y obstáculos
        │  (semilla reproducible)     │
        └──────────────┬──────────────┘
                       │ payload JSON
                       ▼
        ┌─────────────────────────────┐
        │  agentesPrueba.py           │   FarmingModel + TractorAgent
        │  decisión y costos          │   (Python = única fuente de verdad)
        └──────────────┬──────────────┘
                       │ {frames[], metrics}
          ┌────────────┴────────────┐
          ▼                         ▼
  ┌───────────────┐         ┌──────────────────┐
  │  Unity 2D     │         │  dashboard.py    │
  │  (render)     │         │  (Streamlit)     │
  └───────────────┘         └──────────────────┘
```

**Principio central:** toda la lógica —pathfinding, costos, reglas físicas y
decisión— vive en Python. Unity y el dashboard **solo dibujan** el estado
recibido. Eso evita duplicar reglas y desincronizar visualización y cálculo.

**Cómo se comunican los agentes.** El modelo ejecuta los tractores en
**turnos secuenciales** dentro de cada tick. La comunicación es implícita y se
hace a través de dos estructuras compartidas:

| Estructura | Qué comparte | Quién escribe |
|---|---|---|
| `seeded_map` | celdas ya sembradas (evita doble siembra) | cualquiera, al sembrar |
| `target_pos` de cada agente | objetivo reclamado (evita converger) | cada agente, al planear |

Además, `occupied` (posiciones de todos los agentes) se consulta en cada BFS,
lo que impide moverse a una celda ocupada.

**Ciclo de decisión** (idéntico en `agents.py` y `agentesPrueba.py`):

1. **Percibir** — la celda actual y su entorno (`sensar` con radio Manhattan).
2. **Decidir** — ¿tengo semillas y combustible para el retorno? Si no,
   `RECARGANDO`. Si sí, BFS a la celda sembrable más cercana **no reclamada**
   por otro tractor.
3. **Actuar** — avanzar una celda, descontar combustible según pendiente y
   sembrar si llegó a un objetivo válido.

**Modo de integración:** JSON precalculado. Python simula la corrida completa y
devuelve todos los fotogramas de una vez; Unity los reproduce a
`tickDuration = 0.14 s`. Se eligió sobre WebSocket por ser determinista,
reproducible y sin latencia de red.

---

## 3. Estructura del repositorio

```
Agentes/
  campo.py            Dominio del terreno: Celda, Mapa, Campo, sensor, siembra
  agents.py           Prototipo limpio: Vehiculo, Sembradora, zigzag, BFS
  agentesPrueba.py    Modelo multiagente + servidor HTTP (lo que usa Unity)
  escenarios.py       Generación reproducible de terreno y obstáculos
  metricas.py         Colisiones, revisitas, cobertura y costo monetizado
  unidades.py         Conversión a hectáreas, costales y litros/ha
  tests/              73 tests: dominio, agentes, escenarios, métricas y unidades
  requirements.txt    Dependencias del modelo
experimentos.py       Diseño experimental -> resultados/experimentos.csv
figuras.py            Exporta las gráficas del análisis a resultados/figuras/
dashboard.py          Dashboard Streamlit (comparativas + mapa 2D animado)
resultados/           CSV de corridas, fotogramas JSON y figuras PNG
escenario/            Proyecto Unity 6 (URP 2D): render del modelo
ANALISIS.md           Interpretación de resultados, limitaciones y mejoras
INVESTIGACION-AGRICOLA.md  Cuánta semilla y diésel se ocupa por hectárea (con fuentes)
resources/            Enunciado y rúbrica del reto
```

---

## 4. Instalación y ejecución

Requiere Python ≥ 3.11 y `uv` (recomendado) o `pip`.

```bash
# Entorno
uv sync

# Tests (73)
cd Agentes && ../.venv/bin/python -m pytest -q

# Simulación rápida en terminal
../.venv/bin/python agentesPrueba.py        # levanta el servidor en :5000
```

### Experimentos (genera los datos del análisis)

```bash
.venv/bin/python experimentos.py              # 80 corridas, ≈25 s
.venv/bin/python experimentos.py --repeticiones 3 --solo flota
```

Salidas: `resultados/experimentos.csv` (una fila por corrida) y
`resultados/runs/*.json` (fotogramas para animar el mapa).

### Figuras para el informe

```bash
.venv/bin/python figuras.py
```

Genera en `resultados/figuras/` una gráfica costo-vs-colisiones por bloque y
una comparativa de eficiencia (costo por celda sembrada).

### Dashboard

```bash
.venv/bin/python -m streamlit run dashboard.py
```

Incluye comparación de métricas por variante, distribuciones por repetición,
mapa 2D animado tick a tick y descarga del CSV.

### Visualización en Unity

1. Abrir la carpeta `escenario/` con Unity **6000.6.8f1**.
2. Abrir `Assets/Scenes/SampleScene.unity`.
3. Levantar el servidor: `.venv/bin/python Agentes/agentesPrueba.py`
4. **Play** → elegir terreno, tractores y obstáculos → **Comenzar**.

El proyecto está en `2D` porque la rúbrica lo permite explícitamente.

---

## 5. Métricas

| Métrica | Definición | Por qué importa |
|---|---|---|
| Cobertura | celdas sembradas / sembrables | garantía básica del servicio |
| Siembras dobles | celdas sembradas ≥2 veces | desperdicio de semilla |
| Colisiones | fotogramas con 2+ tractores en una celda | fallo de coordinación |
| Pasos repetidos | entradas a celdas ya recorridas / pasos | ineficiencia de ruta |
| Combustible | litros consumidos | principal componente del costo |
| Costo total | combustible + salarios + semillas | objetivo de optimización |
| Costo por hectárea | costo total / área del campo | permite hablar en unidades de campo |

El combustible se monetiza en `metricas.costo_total` con **$27 MXN/L**, precio
investigado en [`INVESTIGACION-AGRICOLA.md`](INVESTIGACION-AGRICOLA.md)
(rango de sensibilidad: $25.39 – $28.00 por litro).

---

## 6. Escala física: hectáreas y costales

El modelo trabaja en celdas, pero los resultados se reportan en las unidades
del campo. La equivalencia está fundamentada en
[`INVESTIGACION-AGRICOLA.md`](INVESTIGACION-AGRICOLA.md) y se aplica con
`Agentes/unidades.py`.

| Concepto | Equivalencia | Fuente |
|---|---|---|
| 1 celda | 9 m × 9 m = **81 m²** | ancho de una sembradora de 12 surcos a 76 cm |
| 1 hectárea | **≈ 123 celdas** | 10,000 m² ÷ 81 m² |
| Campo 20 × 20 | **3.24 ha** | 400 × 81 m² |
| 1 celda sembrada | **≈ 486 semillas** de maíz | 60,000 semillas/ha |
| 1 costal (20 kg) | **≈ 60,000 semillas ≈ 1 ha** | INEGI/INIFAP |
| Siembra de 1 ha | **8.6 – 10.77 L de diésel** | estudio con monitor SeedStar |
| 1 tick | **≈ 5.4 s** | avance de 9 m a 6 km/h |
| Rendimiento | **≈ 4.6 ha/h** | 9 m de ancho × 6 km/h × 85% |

Con eso, un tanque de 35 unidades cubre **0.28 ha** y uno de 60 cubre **0.49 ha**;
un costal rinde una hectárea completa.

⚠️ El modelo **no está calibrado**: consume ~240 L/ha frente a los 8.6–10.77 L/ha
reales. Sus cifras sirven para **comparar configuraciones**, no como costo real
por hectárea. Es la limitación L8 del análisis.

## 7. Reproducibilidad

Cada corrida queda identificada por su **semilla**, que determina a la vez el
terreno y los obstáculos:

```python
import escenarios
payload = escenarios.construir_payload("colinas", n=20, semilla=3)
```

La misma semilla produce exactamente el mismo mapa y la misma corrida. La
conectividad del terreno está garantizada: el generador descarta
disposiciones que encierren el depósito.

**Limitación conocida:** la generación visual de Unity (`PlantingGrid`,
`TerrainGenerator`) todavía usa `Random.Range` sin sembrar, así que la corrida
del editor no coincide bit a bit con el CSV. Los experimentos del análisis son
los reproducibles.

---

## 8. Resultados y limitaciones

Los resultados completos, con tablas, interpretación, limitaciones y mejoras
justificadas, están en **[`ANALISIS.md`](ANALISIS.md)**. Resumen:

- **Cobertura 100% y 0 siembras dobles** en las 80 corridas.
- **La capacidad de semillas domina el costo** (2.74× de 10 a 60 semillas):
  de **$16,509/ha a $6,013/ha** según el tanque.
- **3 tractores es el punto de equilibrio**: 8 tractores tardan 2.26× menos
  pero cuestan 14% más y generan hasta 27 colisiones por corrida.
- **El terreno casi no discrimina** (2.0% de diferencia): el costo por pendiente
  no está normalizado por distancia.
- **34.2% de los pasos repiten tramo**, la ineficiencia sistemática del
  algoritmo greedy.

---

## 9. Equipo

Ana Paula García Valverde · Pablo Velázquez Bremont · Cristhian Zahid Huezo
García · Kevin Xiao Huang · Alejandro Vila Casahonda · Juan David Silva Camacho

Socio formador: **John Deere**.
