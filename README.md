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
  tests/              55 tests: dominio, agentes, escenarios y métricas
  requirements.txt    Dependencias del modelo
experimentos.py       Diseño experimental -> resultados/experimentos.csv
figuras.py            Exporta las gráficas del análisis a resultados/figuras/
dashboard.py          Dashboard Streamlit (comparativas + mapa 2D animado)
resultados/           CSV de corridas, fotogramas JSON y figuras PNG
escenario/            Proyecto Unity 6 (URP 2D): render del modelo
ANALISIS.md           Interpretación de resultados, limitaciones y mejoras
resources/            Enunciado y rúbrica del reto
```

---

## 4. Instalación y ejecución

Requiere Python ≥ 3.11 y `uv` (recomendado) o `pip`.

```bash
# Entorno
uv sync

# Tests (55)
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

El combustible se monetiza en `metricas.costo_total` con un precio por litro
explícito (supuesto declarado en el análisis).

---

## 6. Reproducibilidad

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

## 7. Resultados y limitaciones

Los resultados completos, con tablas, interpretación, limitaciones y mejoras
justificadas, están en **[`ANALISIS.md`](ANALISIS.md)**. Resumen:

- **Cobertura 100% y 0 siembras dobles** en las 80 corridas.
- **La capacidad de semillas domina el costo** (2.74× de 10 a 60 semillas).
- **3 tractores es el punto de equilibrio**: 8 tractores tardan 2.26× menos
  pero cuestan 14% más y generan hasta 27 colisiones por corrida.
- **El terreno casi no discrimina** (2.0% de diferencia): el costo por pendiente
  no está normalizado por distancia.
- **34.2% de los pasos repiten tramo**, la ineficiencia sistemática del
  algoritmo greedy.

---

## 8. Equipo

Ana Paula García Valverde · Pablo Velázquez Bremont · Cristhian Zahid Huezo
García · Kevin Xiao Huang · Alejandro Vila Casahonda · Juan David Silva Camacho

Socio formador: **John Deere**.
