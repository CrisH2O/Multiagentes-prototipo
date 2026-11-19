# Q-Learning en la flota de siembra: respuestas y decisión técnica

> Respuesta al cuestionario **«Qlearning Premier»** aplicada al simulador de este
> repositorio (Reto John Deere). Cada punto se contesta con las cifras, el código
> y las unidades del proyecto, no con ejemplos genéricos. Al final están el MDP
> que sí conviene, un plan de tres semanas y la evidencia medida con
> `experimentos_qlearning.py`.

---

## 0. Veredicto en una página

**No reemplacen el planificador por Q-Learning tabular. Sí usen Q-Learning como
módulo acotado, y solo si el problema lo justifica.**

El proyecto ya resolvió el problema de decisión con un planificador BFS que
gana **17% en tiempo y 3.6% en costo** frente a la ruta base, con cobertura
100% y cero siembras dobles. Q-Learning tabular, en su mejor caso (rejilla
determinista, totalmente observable, sin otros tractores), **iguala al
BFS (ratio 1.001) pero cuesta ~1,710 episodios por meta y no transfiere a un mapa nuevo**
(12% de éxito). El BFS cuesta cero episodios y generaliza a cualquier mapa.

La razón de fondo: **Q-Learning sirve cuando no se conoce el modelo del
entorno**. Aquí el entorno está modelado y es determinista
(`FarmingModel`), así que buscar (BFS) es más barato, óptimo y explicable que
aprender por prueba y error.

| # | Pregunta del cuestionario | Respuesta corta para este proyecto |
|---|---|---|
| 1 | ¿Qué es el agente: tractor o sistema central? | El **tractor** es el agente; el planificador central es el **entorno/coordinador**, no otro agente que aprende. |
| 2 | ¿Qué ve el tractor? | Posición, orientación, combustible (L), semilla (costales), depósito, celdas restantes y metas reclamadas. Discretizado completo son **~59.8 M estados**: no cabe. |
| 3 | ¿Qué acciones? | 4 movimientos + sembrar + recargar + esperar = **7**; sembrar y recargar ya son reglas deterministas, así que la acción aprendible es **a dónde ir** o **recargar sí/no**. |
| 4 | ¿Cómo se premia? | En **pesos del proyecto** (tick = $0.075, litro = $27) y **sin la semilla**: el 81% del costo es fijo por hectárea y meterlo premia no sembrar. |
| 5 | ¿Cuánto mide la tabla Q? | 365 celdas × 4 acciones = **1,460 valores (11.4 KiB)**; con el estado realista, **418.6 M pares (3.1 GiB)**. Con 3 tractores, 1.7×10¹⁰ pares. |
| 6 | ¿Qué pasa con α y γ? | α = 0.1 con decaimiento; γ = 0.99 (horizonte ≈ 100 pasos ≈ 9 min de campo). α = 1 oscila, α = 0.01 tarda ~100 visitas por par. |
| 7 | ¿Explorar o explotar? | ε-greedy de 1.0 a 0.05 lineal; ε = 0 al evaluar. Explorar **solo en simulación**. |
| 8 | ¿Cuántos episodios? | **1,710 de media** (rango 1,450–2,125) para 95% de éxito en **una** meta; cubrir 365 metas ≈ **624 mil episodios** ≈ 2 días de cómputo. |
| 9 | ¿Seguridad? | Política congelada, sombra, geocerca, paro de emergencia y operador; nunca ε > 0 en campo. |
| 10 | ¿Es la herramienta correcta? | Para la tarea completa, **no**. Es correcta como módulo para decisiones pequeñas con incertidumbre (reabastecimiento/despacho). |

**La evidencia, en una tabla** (5 metas del mapa real del proyecto, 15 inicios
lejanos por meta, 6,000 episodios por meta; detalle en la sección 11):

| Métrica | Q-Learning tabular | BFS del proyecto |
|---|---:|---:|
| Éxito al llegar (inicios a ≥12 pasos) | **100%** | 100% |
| Pasos medios / pasos óptimos | **1.001** | 1.0 |
| Episodios para 95% de éxito (por meta) | **1,710** | **0** |
| Transferencia a mapa con otros obstáculos | **12%** | **100%** |
| Tiempo de cómputo por meta | 0.93 s (juguete) | milisegundos |

Conclusión operativa: **el aprendizaje no aporta precisión, solo costo**. Donde
sí puede aportar es donde el planificador no decide: cuándo reabastecerse, qué
meta tomar cuando hay incertidumbre, o cómo reaccionar a fallas. Ese MDP es
pequeño y se puede resolver; la ruta completa, no.

---

## 1. El problema: ¿qué es el agente y cuál es el objetivo?

**Respuesta.** Hay que separar dos niveles:

- **Agente de decisión:** cada tractor (`TractorAgent`). Tiene su propia
  política y su propio estado (posición, combustible, semilla).
- **Coordinador:** el planificador central que asigna metas y resuelve
  conflictos. En el proyecto esto ya existe de forma implícita: `FarmingModel`
  ejecuta los tractores en turnos y comparte `seeded_map`, `target_pos` y
  `occupied`.

**En este proyecto.** El agente es el tractor, no el sistema central. Un
"agente central que controla varios" obligaría a un espacio de acciones
conjuntas de 4⁸ = 65,536 combinaciones por tick con 8 tractores, y a un estado
conjunto de 365⁸ ≈ 3.2×10²⁰ configuraciones. Es intratable en tabular y ni
siquiera es un buen encuadre: la coordinación explícita (reclamar meta, evitar
celdas ocupadas) ya funciona y es auditable.

**El objetivo** no es "recorrer el campo", es:

> Cubrir el 100% de las celdas sembrables, sin doble siembra, minimizando
> **tiempo y combustible**, no el costo total.

Esto último importa y es contraintuitivo: la semilla es el **81% del costo**
($1,500 de $1,851 por hectárea) y es una **identidad por hectárea**, no un
resultado del modelo (limitación L8 de `ANALISIS.md`). Si el agente optimiza
"costo total" tal cual, aprende a **no sembrar**. El objetivo correcto es
`J = ticks × $0.075 + litros × $27`, sujeto a cobertura 100% y cero doble
siembra.

**Multiagente.** Sí hay varios tractores y sí se estorban: con 8 tractores
aparecen hasta **21 colisiones por corrida** (L2). Pero eso no se arregla con
Q-Learning: se arregla con una regla de reserva del depósito y una cola de
recarga. Aprender la coordinación exigiría estado y acción conjuntos; el
enfoque correcto en la literatura es *centralized training, decentralized
execution* (CTDE) con redes, no una tabla.

**Decisión.** Agente = tractor; coordinador = planificador determinista. No
aprender lo que una regla ya resuelve.

---

## 2. Estados: qué "ve" el tractor

**Respuesta.** El estado debe contener **solo lo necesario para la decisión que
se aprende**. Meter todo lo que el simulador conoce es el error más común y el
que hace explotar la tabla.

**Lo que el modelo ya expone** (en `frames` y en las estructuras del modelo):

| Variable | Rango real |
|---|---|
| Posición | 365 celdas libres (20×20 con 35 obstáculos) |
| Orientación | 4 direcciones |
| Combustible | 0–300 L |
| Semilla | 0–123 celdas (1 costal) |
| Distancia al depósito | 0–38 pasos |
| Celdas restantes | 0–365 |
| Pendiente | Δelevación ≈ 0.01–0.10 por paso |
| Metas reclamadas / ocupadas | hasta 8 posiciones |

**El problema de discretizar todo.** Si se toman 10 bins de combustible, 4 de
semilla, 8 de distancia al depósito, 8 de distancia a la meta y 16 patrones
locales de obstáculos:

```
365 posiciones × 4 orientaciones × 10 × 4 × 8 × 8 × 16 = 59,801,600 estados
× 7 acciones = 418,611,200 pares (s, a) ≈ 3.1 GiB en float64
```

y eso **sin** la meta explícita ni los otros tractores. Con la meta como parte
del estado, la tabla pasa a 365² × 4 ≈ 533 mil pares solo para navegación; con
3 tractores, 365³ × 7³ ≈ 1.7×10¹⁰.

**La alternativa viable.** El estado mínimo depende de la decisión:

- **Navegar a una meta conocida:** `(x, y)` → 365 estados × 4 acciones =
  **1,460 valores**. Es lo que se midió en la sección 11.
- **Decidir si recargar:** `(combustible_bin, semilla_bin, distancia_depósito,
  restante_bin)` = 10 × 4 × 8 × 5 = **1,600 estados × 2 acciones = 3,200
  pares** ≈ 25 KiB. Este sí es un MDP honesto.

**Decisión.** Empezar por el estado pequeño de la decisión concreta. La
posición exacta y el mapa ya los usa el planificador; el RL no debe duplicar
esa información.

---

## 3. Acciones: qué puede hacer

**Respuesta.** En la rejilla del proyecto el repertorio natural es:

| Acción | ¿Aprenderla? | Por qué |
|---|---|---|
| Mover norte/sur/este/oeste | **Sí** | Es la decisión de navegación. |
| Sembrar al llegar | No | Regla determinista: si la celda está libre, se siembra. |
| Recargar en el depósito | No (regla) / **Sí** (cuándo) | Recargar es automático al llegar; **decidir ir** sí es una decisión. |
| Esperar | No | El modelo corta a los 15 ticks de inactividad; sería un atajo. |
| Girar en ángulos de 5° | No aplica | La rejilla es de 4 vecinos y 9 m por celda. Eso es control continuo → PID/MPC. |

**Granularidad.** Pasar de 4 acciones a 8 (diagonales) duplica la tabla y
cambia el costo por celda; el proyecto ya calibró una celda de 9 m (12 surcos
× 76 cm), así que 4 acciones es la granularidad correcta.

**Decisión.** 4 acciones de movimiento y, aparte, una acción binaria
"recargar sí/no" si se aprende esa política. No aprender siembra ni recarga
como acciones primitivas: son reglas.

---

## 4. Recompensas: qué es bueno y qué es malo

**Respuesta.** La recompensa debe estar en las **unidades del negocio** y debe
premiar el resultado (cobertura) sin pagar por atajos.

**Diseño recomendado** (por paso, en pesos):

```
r_t = −(0.075 · Δt + 27 · L_t) − 5 · [choque] + Φ(s_{t+1}) − Φ(s_t)
Φ(s) = −2 · celdas_restantes
```

- `0.075` = salario por tick (3 tractores, $50/h, tick de 5.4 s).
- `27` = precio del diésel por litro.
- `Φ` es *reward shaping* basado en potencial: acelera el aprendizaje y
  **conserva la política óptima** (Ng, Harada y Russell, 1999).
- **La semilla no entra.** Es el 81% del costo y es constante por hectárea;
  incluirla hace que el agente prefiera no sembrar.

**Atajos que el agente aprendería (y cómo se bloquean):**

| Atajo | Cómo se manifiesta | Bloqueo |
|---|---|---|
| No sembrar | Recorre todo, siembra poco, "ahorra" semilla | Semilla fuera de la recompensa + bono terminal por cobertura |
| Quedarse quieto | Evita combustible y choques | Penalización por tick + Φ por celdas restantes |
| Circular cuesta abajo | Aprovecha que el modelo cobra poco bajar (L1) | Normalizar pendiente por distancia, o excluir la pendiente del reward |
| Sembrar solo lo fácil | Deja esquinas y obstáculos | Cobertura obligatoria al terminar; sin bono parcial |
| Chocar para "recolectar" | Si el choque no cuesta, no hay incentivo a coordinarse | −5 por choque y reserva de meta |

**Decisión.** Recompensa monetaria, semilla fuera, potencial por celdas
restantes y bono terminal solo con cobertura 100%. Nada de recompensas
"por celda nueva" a secas.

---

## 5. La tabla Q: qué significa y cuánto mide

**Respuesta.** `Q(s, a)` es la recompensa futura descontada que espero si estoy
en `s`, hago `a` y luego actúo óptimamente. Es una tabla de números, uno por
par `(s, a)`.

| Variante de estado | Estados | Acciones | Pares | Memoria (float64) |
|---|---:|---:|---:|---:|
| Navegación pura `(x, y)` | 365 | 4 | **1,460** | **11.4 KiB** |
| Navegación + sembrar/recargar | 365 | 7 | 2,555 | 20 KiB |
| Estado local realista (sección 2) | 59,801,600 | 7 | **418,611,200** | **3.1 GiB** |
| 3 tractores, estado conjunto | 365³ ≈ 4.9×10⁷ | 7³ = 343 | **1.7×10¹⁰** | 127 GiB |
| 8 tractores, estado conjunto | 365⁸ ≈ 3.2×10²⁰ | 7⁸ ≈ 5.8×10⁶ | **1.8×10²⁷** | imposible |

Nota práctica: en Python un `dict` cuesta ~100 bytes por entrada, no 8. La
tabla realista en `dict` serían ~40 GiB; con `numpy` y `float32`, la mitad.
Aun así, el problema no es la memoria: es que **no hay datos suficientes para
visitar cada par**.

**Decisión.** Tabla pequeña y explícita (`numpy` de `[x, y, acción]`) solo para
la decisión acotada. Si el estado necesita más de ~10⁵ pares, es señal de que
el problema no es para tabular.

---

## 6. La regla de actualización

**Respuesta.** La regla estándar (Watkins y Dayan, 1992):

```
Q(s, a) ← Q(s, a) + α · [ r + γ · max_a' Q(s', a') − Q(s, a) ]
```

**α (tasa de aprendizaje).**

- α = 1: la tabla copia la última muestra; con recompensas ruidosas **oscila y
  no promedia**. En el experimento se ve: la curva de la meta 1 retrocede
  después de cruzar el 95%.
- α = 0.1: promedia las últimas ~10 visitas. Es lo que se usó y bastó en
  6,000 episodios.
- α = 0.01: necesita ~100 visitas por par para converger; con 1,460 pares son
  ~146 mil actualizaciones mínimas, y en la práctica muchas más.
- Recomendado: α = 0.1 con decaimiento a 0.01, o *learning rate* por visita
  `α = 1/n(s,a)`.

**γ (descuento).**

- γ = 0: solo importa el paso actual; el agente no planifica.
- γ = 0.99: horizonte efectivo ≈ 1/(1−γ) = 100 pasos ≈ **9 minutos** de campo
  (tick de 5.4 s). Es razonable para un episodio de ~176 ticks (16 min).
- γ = 1: válido en episodios finitos, pero los valores Q crecen y la escala de
  la recompensa importa; no lo recomiendo aquí.
- γ = 0.9: horizonte de 10 pasos ≈ 54 s; demasiado corto para decidir una
  recarga.

**Estabilidad.** Q-Learning tabular con α constante y política greedy puede
oscilar; la curva medida no es monótona. Si se reporta una curva, hay que
mostrarla tal cual, no suavizada.

**Decisión.** α = 0.1 → 0.01, γ = 0.99, y evaluar con ε = 0.

---

## 7. Exploración vs. explotación

**Respuesta.** ε-greedy con decaimiento lineal de **1.0 a 0.05** durante el
entrenamiento y **ε = 0** en evaluación. Con 4 acciones, ε = 0.05 explora una
de cada 20 decisiones, suficiente para detectar que una acción dejó de ser
buena, y no tanto como para destruir la política.

**Alternativas** y cuándo usarlas:

- **Softmax/Boltzmann:** útil si hay acciones casi equivalentes; aquí no.
- **UCB / conteo de visitas:** mejor con recompensas dispersas; añade estado
  auxiliar (conteos) y complejidad.
- **Inicialización optimista:** con recompensas negativas por paso, `Q = 0` ya
  es optimista; no hace falta.

**En este proyecto** el costo de explorar es tiempo de cómputo, no diésel:
nunca se explora en campo. Y como el entorno es determinista, la exploración
solo sirve para descubrir la topología; una vez conocida, el BFS la resuelve
mejor.

**Decisión.** ε 1.0 → 0.05; ε = 0 al evaluar y en producción.

---

## 8. Entrenamiento y evaluación

**Respuesta.** Entrenar **solo en el simulador** (el proyecto ya lo tiene,
determinista y con semilla) y evaluar con las métricas que ya existen.

**Lo medido** (sección 11): para **una** meta, 95% de éxito requiere
**1,450–2,125 episodios** (media 1,710), con 6,000 episodios de presupuesto por
meta. Ese número es el **mejor caso**: rejilla determinista, sin otros
tractores, totalmente observable. Con coordinación multiagente, la muestra
necesaria es mayor, no menor.

**Extrapolación honesta.** Cubrir el campo con una política por meta:

```
365 metas × 1,710 episodios ≈ 624,000 episodios
```

A 0.28 s por corrida del modelo completo (90 corridas en ~25 s), son **~2 días
de cómputo por configuración**, frente a **milisegundos** del BFS para las 365
metas. La alternativa de meter la meta en el estado no reduce el costo: lo
reparte en 533 mil pares que con el mismo presupuesto se visitan menos de una
vez.

**Protocolo recomendado** (coherente con `experimentos.py`):

1. Semillas 1–3 para entrenar, 4 para ajustar, 5 para probar. Nunca la misma
   semilla en train y test.
2. Métricas: cobertura, siembras dobles, colisiones, pasos repetidos, L/ha y
   $/ha **sembrada** (no $/ha del lote; ver la trampa de la sección 2.4 de
   `ANALISIS.md`).
3. 30 episodios de evaluación con ε = 0; reportar media ± desviación.
4. **Criterio de adopción:** mejorar ≥5% en L/ha o ticks, mantener cobertura
   100% y no aumentar colisiones. Si no se cumple, se documenta el resultado
   negativo; no se ajusta el umbral después de ver los datos.
5. Línea base: `greedy` (176 ticks), no `zigzag` (211). Ganarle al zigzag no
   demuestra nada; hay que ganarle al planificador.

**¿Cómo sé que aprendió?** Con tres pruebas: éxito alto en inicios no vistos,
pasos iguales o mejores que el BFS, y transferencia a un mapa nuevo. En el
experimento aprobó las dos primeras y **falló la tercera** (12% de éxito):
aprendió el mapa, no la tarea.

**Decisión.** Simulador, semillas separadas, mismas métricas y criterio de
adopción escrito antes de entrenar.

---

## 9. Seguridad

**Respuesta.** Un tractor real no es un entorno de exploración. Reglas mínimas:

- **Entrenamiento solo en simulación.** La política sale congelada; en campo
  no se actualiza Q.
- **Modo sombra:** la política propone, el operador o el planificador decide,
  durante un periodo de validación.
- **Geocerca y límites físicos:** el tractor no puede salir del lote ni
  exceder velocidad/giro, independientemente de lo que diga la política.
- **Paro de emergencia** y hombre muerto; el operador puede tomar el control
  en cualquier momento.
- **Auditoría:** la tabla Q es interpretable (una ventaja real frente a DQN);
  se puede revisar qué acción elige en cada estado.
- **Sim-to-real:** el modelo no tiene física de suelo, clima ni sensores
  (limitaciones L1 y L8). Una política óptima en el simulador puede ser mala
  en campo; validar en parcela pequeña antes de escalar.
- **Normas de referencia:** ISO 18497 (maquinaria agrícola altamente
  automatizada) e ISO 25119 (seguridad funcional de sistemas de control en
  tractores).

**Decisión.** Nada de ε > 0 en campo; sombra, geocerca, paro y operador.

---

## 10. ¿Es la herramienta correcta?

**Respuesta.** Para el problema completo, **no**. Para un subproblema acotado,
**sí, con condiciones**.

| Subproblema | Herramienta correcta | Por qué | Evidencia del proyecto |
|---|---|---|---|
| Cobertura y ruteo | **BFS/A\* + franjas** | Óptimo, determinista, explicable, sin entrenamiento | 176 vs 211 ticks; 3.6% menos costo |
| Asignación entre tractores | Subasta/despacho o reclamo de meta | El espacio conjunto no escala | 21 colisiones con 8 tractores → falta regla, no aprendizaje |
| Reabastecimiento | Regla de umbral, DP o RL tabular | Estado pequeño (1,600), decisión secuencial real | Con 0.25 costales el costo sube 11.8%: la decisión importa |
| Seguimiento de trayectoria continuo | **PID/MPC** | Garantías de estabilidad y esfuerzo de control | En rejilla no aplica; en tractor real sí |
| Obstáculos no estructurados | Percepción + RL profundo | Requiere simulación masiva y sensores | Fuera del alcance del reto |

**Por qué Q-Learning tabular no escala aquí:**

1. El estado conjunto crece exponencialmente con los tractores.
2. La recompensa es principalmente fija (semilla, 81%), así que el espacio de
   mejora real es pequeño: tiempo y combustible.
3. El entorno es conocido y determinista; buscar es más barato que aprender.
4. La política aprendida no es más precisa que el BFS (ratio 1.001) y no
   transfiere (12%).

**Cuándo sí valdría la pena:** si el tractor operara con incertidumbre real
(fallas, clima, sensores ruidosos) y no se pudiera modelar; o si la tarea
exigiera adaptarse a un terreno desconocido en línea. Ese no es el caso de este
reto.

**Decisión.** Q-Learning como módulo de decisión acotada, nunca como sustituto
del planificador.

---

## 11. El MDP que sí recomiendo (y su límite)

Si la rúbrica exige un componente de aprendizaje, el candidato honesto es la
**decisión de reabastecimiento**, no la ruta:

- **Estado:** `(combustible_bin, semilla_bin, distancia_depósito_bin,
  restante_bin)` → 1,600 estados.
- **Acciones:** `SEGUIR` / `VOLVER_AL_DEPÓSITO`.
- **Recompensa:** `−(0.075 + 27·L)` por paso, con Φ por celdas restantes.
- **Horizonte:** 176 ticks; γ = 0.99.
- **Tabla:** 3,200 pares → 25 KiB; entrenable en minutos.
- **Línea base:** la regla actual (`seeds <= 0 or fuel <= safe_return_fuel`).

![Curvas de aprendizaje y comparación de pasos](resultados/figuras/qlearning_curva.png)

**Figura 1.** Izquierda: éxito en evaluación greedy por episodio para las cinco
metas (la curva no es monótona: con α constante la política puede retroceder).
Derecha: pasos medios hasta la meta; Q-Learning iguala al BFS en las cinco.

**Limitación del experimento:** una sola semilla de entrenamiento por meta y
una rejilla sin combustible ni pendientes; aun así, la diferencia con el BFS
(1,710 episodios frente a cero) es de órdenes de magnitud, no de matices.

**Límite esperado:** como el combustible del tanque de 300 L rara vez limita
(4300 celdas de autonomía en un campo de 365), la decisión real la dispara la
semilla (123 celdas por costal) y el viaje de regreso es obligatorio. La regla
actual ya es casi óptima; el margen de mejora está en **ordenar las metas para
terminar cerca del depósito**, que es un problema de ruteo, no de RL. Por eso
el resultado más probable de este MDP es "no mejora significativamente": hay
que medirlo antes de prometerlo.

---

## 12. Plan de tres semanas (si hay que entregar RL)

| Semana | Entregable | Criterio de avance |
|---|---|---|
| 1 | Envoltorio `reset/step` sobre `FarmingModel`; FrozenLake resuelto en ~50 líneas; línea base `greedy` medida | El entorno corre los 176 ticks y reproduce el CSV |
| 2 | Q-Learning tabular del reabastecimiento (o de la selección de meta); entrenamiento semillas 1–3, ajuste 4 | Curva de aprendizaje y tabla Q guardada |
| 3 | Evaluación con semilla 5, mismas métricas, comparación contra la regla actual y el planificador | Decisión escrita: adoptar (≥5% mejor) o documentar resultado negativo |

Entregables ya disponibles en el repositorio:

- `experimentos_qlearning.py` — navegador Q vs BFS, reproducible.
- `resultados/qlearning_resumen.json` y `resultados/qlearning_episodios.csv`.
- `resultados/figuras/qlearning_curva.png` — curvas de aprendizaje y
  comparación de pasos.

---

## 13. Cómo contestar en la presentación (cinco frases)

1. "El agente es el tractor; el planificador central es el entorno, no un
   agente que aprende."
2. "Modelamos el estado mínimo para la decisión; el estado completo son 59.8
   millones, y el conjunto con 3 tractores es 1.7×10¹⁰ pares."
3. "La recompensa está en pesos y excluye la semilla, porque el 81% del costo
   es fijo por hectárea y premiarla enseña a no sembrar."
4. "Medimos Q-Learning contra el BFS: empata en pasos, pero cuesta 1,710
   episodios por meta y transfiere 12% a un mapa nuevo; el BFS cuesta cero y
   generaliza."
5. "Por eso lo usamos como módulo acotado —reabastecimiento— y no como
   reemplazo del planificador; si no mejora 5%, lo reportamos como resultado
   negativo."

---

## 14. Reproducir

```bash
# Entorno y tests (91)
uv sync
cd Agentes && ../.venv/bin/python -m pytest -q && cd ..

# Experimento de Q-Learning (≈5 s; escribe resultados/qlearning_*)
.venv/bin/python experimentos_qlearning.py

# Resultados del proyecto (90 corridas) y figuras
.venv/bin/python experimentos.py
.venv/bin/python figuras.py
```

El experimento es determinista: usa los mapas de `escenarios.construir_payload`
y `numpy.random.default_rng(0)` para el entrenamiento.

---

## Referencias

- Sutton, R. S., & Barto, A. G. (2018). *Reinforcement learning: An
  introduction* (2nd ed.). MIT Press.
- Watkins, C. J. C. H., & Dayan, P. (1992). Q-learning. *Machine Learning,
  8*, 279–292.
- Ng, A. Y., Harada, D., & Russell, S. (1999). Policy invariance under reward
  transformations: Theory and application to reward shaping. *Proceedings of
  ICML 1999*.
- Mnih, V., et al. (2015). Human-level control through deep reinforcement
  learning. *Nature, 518*, 529–533.
- Kaelbling, L. P., Littman, M. L., & Cassandra, A. R. (1998). Planning and
  acting in partially observable stochastic domains. *Artificial Intelligence,
  101*, 99–134.
- ISO 18497:2018. *Agricultural machinery and tractors — Safety of highly
  automated machinery*.
- ISO 25119:2018. *Tractors and machinery for agriculture and forestry —
  Safety-related parts of control systems*.
