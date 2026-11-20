# Guion de presentación — Simulador 3D de siembra (100 ha)

Duración objetivo: **10 minutos** (hay versión corta de 5 min al final).
Todo lo que se muestra está en `escenario/Builds/Campo3D.app` y en la escena
`escenario/Assets/Scenes/Campo3D.unity`.

---

## 0. Antes de empezar (checklist de 2 minutos)

1. Abrir una terminal y levantar el servidor:
   ```bash
   cd Multiagentes-prototipo
   .venv/bin/python Agentes/agentesPrueba.py
   ```
   Debe decir: `Servidor Python activo en http://127.0.0.1:5000/simulate`.
2. Abrir el ejecutable: `open escenario/Builds/Campo3D.app` (o doble clic en
   `iniciar_campo3d.command`, que hace las dos cosas).
3. Verificar que aparece el **menú** y que el juego responde (probar una vez con
   "Sin obstáculos" y detenerlo con "Volver al menú").
4. Tener a mano las capturas de `escenario/Previews/` por si falla el proyector o
   el servidor.
5. Subir el volumen del sistema **no** hace falta: el proyecto no usa audio.

---

## 1. Introducción (30 s) — qué es y por qué

> "Este es un simulador de siembra de maíz para **100 hectáreas**. La decisión de
> qué sembrar y por dónde va **toda en Python**: un modelo multiagente con tres
> tractores que se reparten el campo. Unity **solo dibuja** ese resultado en 3D.
> El campo es de **1,000 × 1,000 metros**, dividido en **1,600 celdas de 25 × 25 m**,
> y la sembradora tiene **9.12 m de ancho de labor** (12 surcos a 0.76 m)."

**Números para repetir durante la demo:**
- 100 ha = 1,600 celdas de 0.0625 ha.
- 1 pasada de la sembradora cubre el **36.5 %** del ancho de una celda.
- 3 pasadas por celda → **11 pasadas por hectárea** → **110 km** de recorrido total.
- Corrida típica: **710 ticks**, **91.2 ha sembradas**, **1,148 L** de diésel.
- Tiempo real de campo: **8 h 05 min**.

---

## 2. Arquitectura (1 min) — cómo se comunican

> "Unity no simula: le pide a Python. Son dos llamadas por HTTP:
> 1) `GET /payload` con lo que elegí en el menú (terreno, tractores, estrategia,
>    obstáculos y semilla), y Python me devuelve la configuración en **JSON**;
> 2) `POST /simulate` con ese JSON, y Python corre el modelo y me devuelve **todos
>    los fotogramas** de la corrida, también en JSON. Unity los reproduce.
>
> Es **REST + JSON** con la librería estándar de Python, sin FastAPI ni WebSocket,
> porque el modelo ya calcula todo de una vez y así la reproducción es
> determinista: puedo pausar, cambiar la velocidad o volver a empezar sin tocar a
> Python."

Si preguntan por qué no WebSocket: "Porque no necesito streaming; el modelo tarda
~5 s y devuelve 710 frames; WebSocket tendría sentido para simulación en vivo."

---

## 3. Demo (5 min) — el recorrido que hay que hacer

### 3.1 El menú (40 s)

Mostrar la ventana del menú y leer las opciones:

> "Como en la versión 2D, elijo **terreno** (plano, colinas, montañoso),
> **cantidad de tractores** (1 a 4), **estrategia** (planificador o zigzag),
> **obstáculos** (0 a 300, se escriben directo) y **semilla** de generación
> (0 a 999 o aleatoria). Le doy **INICIAR**."

**Qué resaltar:** el campo cambia de relieve al elegir otro terreno (hay 3 terrenos
de 100 ha en la escena).

### 3.2 Vista general (40 s)

- Presionar **M** (vista aérea) y mostrar el campo completo.
- Presionar **M** otra vez para volver.

> "Esto son 100 hectáreas reales. El terreno tiene un **heightmap** hecho en Python
> con la misma elevación que usa el modelo, y la siembra se pinta sobre el terreno,
> celda por celda, con las tres pasadas de la sembradora y los surcos."

**Decir:** el HUD arriba a la derecha muestra `Sembrado: X ha (%)`, `Faltan: Y ha`,
`Celda: 25×25 m = 0.0625 ha` y `Sembradora: 9.12 m = 36 % del ancho por pasada`.

### 3.3 Seguir un tractor (1 min 30 s)

- Presionar **C** una o dos veces para seguir un tractor.
- Señalar el panel inferior izquierdo: `Tractor_01 [SEMBRANDO]`, barra de **semilla**
  con su **porcentaje**, **combustible** en litros y **hectáreas sembradas**.
- Señalar el **halo verde pulsante** bajo el tractor: es el **ancho real de la
  sembradora (9.12 m)** y usa un **shader propio** (`CeldaSembrada.shader`).

> "Con C cambio de cámara: órbita, tractor 1, 2 o 3. La cámara va pegada al tractor
> y el tractor se mueve por una **curva de Catmull-Rom**, no a saltos de celda."

### 3.4 Velocidad y tiempo real (40 s)

- Presionar **T** una o dos veces para bajar la velocidad.
- Presionar **Espacio** para pausar y reanudar.

> "Puedo ir a 1:600 (50 segundos la corrida) o a 1:30 (16 minutos, para verlo de
> cerca). El HUD siempre muestra el **tiempo de campo real**: por ejemplo
> '4 h 02 min de 8 h 05 min'. La corrida completa son 8 horas de trabajo real."

### 3.5 Obstáculos y reinicio limpio (1 min)

- Volver al menú (**"Volver al menú"**), poner `OBSTÁCULOS = 140`, semilla 7 y dar
  INICIAR.
- En la vista aérea (**M**), señalar los **árboles y rocas** en las celdas verdes.

> "Las celdas que no se siembran son los obstáculos, y ahora se dibujan como árboles
> o rocas para que se entienda. El modelo **nunca** siembra ni pasa sobre ellos; lo
> verifiqué con un contador: `marcadas = pintadas` y **0 celdas sembradas sobre
> obstáculos**."

- Volver al menú y lanzar otra corrida (con 0 obstáculos): el campo se **limpia** y
  vuelve a empezar de cero.

> "Al reiniciar se borra la siembra anterior y el contador vuelve a cero."

---

## 4. Recorrido por la rúbrica (2 min 30 s) — en Unity o con capturas

Abrir Unity con `escenario/Assets/Scenes/Campo3D.unity` y ir mostrando, en este orden:

| # | Criterio | Qué muestro | Frase para decir |
|---|---|---|---|
| 1 | **Figuras primitivas** | Jerarquía `OBJETOS → Arbol_01` (cilindro + esferas), `Roca_01`, `CampoBase` (Plane) | "Los árboles y rocas son primitivas escaladas; el campo base es un plano." |
| 2 | **ProBuilder y Prefabs** | Seleccionar `ESCENARIO → Bodega` (componente **ProBuilder Mesh**), abrir `Tools → ProBuilder`; luego `Assets/Prefabs` | "La bodega está modelada con ProBuilder y es editable; el tractor, árboles y rocas son prefabs." |
| 3 | **Heightmaps** | `Terreno_Colinas` → Terrain Settings (Heightmap 513, 1000 × 1000 m); abrir `Assets/Texturas/heightmap_colinas.png` | "El terreno sale de un PNG de alturas generado en Python con la misma elevación del modelo." |
| 4 | **Mallas importadas** | `Assets/Modelos/JohnDeereR8/tractor_r8.obj` (150,948 triángulos) y `Tractor.prefab` | "El tractor John Deere se importó de un GLB de Sketchfab, convertido a OBJ; mide 7.25 m." |
| 5 | **Cámaras** | `Camara Principal` (Camera + OrbitCamera + CamaraSeguimiento) | "Una cámara con tres modos: órbita, seguimiento y aérea." |
| 6 | **Movimiento de cámara** | En Play: botón derecho para orbitar, rueda, C y M | "Los movimientos van suavizados y con límites; el seguimiento va pegado al tractor." |
| 7 | **API con Python** | `Simulacion3D.cs` (`Ejecutar`, `Enviar`, `EnviarGet`) y `Agentes/agentesPrueba.py` (`do_GET`, `do_POST`) | "Dos endpoints REST: /payload y /simulate." |
| 8 | **JSON** | `Assets/StreamingAssets/payload_colinas.json` y las clases `Respuesta3D`, `Frame3D` | "El payload y los frames viajan como JSON; se deserializan con JsonUtility." |
| 9 | **Ejecutable** | `escenario/Builds/Campo3D.app` | "Está compilado para macOS; no necesita Unity para abrirse." |
| 10 | **Curvas paramétricas** | `CatmullRomSpline.cs` (Evaluar, Tangente, tabla de longitud de arco) | "La trayectoria es una spline de Catmull-Rom; el tractor no salta de celda en celda." |
| 11 | **Materiales y texturas** | `Assets/Materials`, `Assets/Texturas/sembrado.png`, Terrain Layers | "Texturas generadas por script: pasto, tierra y siembra con surcos y brotes." |
| 12 | **Iluminación** | `Sol` (direccional con sombras, 600 m) y `PostProceso` (Volume con bloom, ACES, viñeta) | "Sol con sombras suaves, ambiente, niebla y post-proceso." |
| 13 | **Shaders** | `Assets/Shaders/CieloGradiente.shader` (cielo) y `CeldaSembrada.shader` (halo del tractor) | "Dos shaders HLSL propios: el degradado del cielo y el halo pulsante de la sembradora." |

Si el tiempo aprieta, mostrar solo 2, 3, 4, 10 y 13 (los más visuales) y decir
"el resto está documentado en `DOCUMENTACION-3D.md`".

---

## 5. Resultados y cierre (30 s)

> "Con 3 tractores, la corrida sembró **91.2 ha** (1,459 celdas) usando **1,148 L**
> de diésel, con un costo de semilla de unos **$136,800** y un jornal de ~$1,000.
> La sembradora hace **11 pasadas por hectárea**, o sea **110 km** de recorrido.
> El proyecto está en GitHub con la documentación punto por punto de la rúbrica."

**Limitaciones (decirlas con naturalidad, suma puntos):**
- Las ruedas del tractor no giran: el modelo de Sketchfab viene con toda la
  geometría fusionada en una malla; separarla rompía el modelo.
- El bloom del post-proceso se queda fuera en el build (URP lo elimina); en el
  editor sí se ve.
- El ejecutable necesita el servidor de Python corriendo.

---

## 6. Preguntas probables y respuestas cortas

**¿Por qué 25 m por celda y no 9 m?**
"El planificador hace búsqueda en anchura por cada paso; con 12,000 celdas de 9 m
tardaba minutos. Con 25 m son 1,600 celdas, corre en segundos, y cada celda se
modela como las 3 pasadas de la sembradora (25 / 9.12 ≈ 2.74)."

**¿Cómo se calcula el combustible?**
"8.6 L/ha calibrado, multiplicado por el área de cada paso, más el costo extra por
pendiente. El total incluye los viajes al depósito."

**¿Los tractores se chocan?**
"El modelo evita celdas ocupadas por otros agentes y les da un pequeño margen de
separación; en la vista general se ve cómo se reparten."

**¿Qué pasa si se cae el servidor?**
"La app muestra el error y no simula; por eso el lanzador `iniciar_campo3d.command`
arranca el servidor y el juego juntos."

**¿Por qué no usan FastAPI o WebSocket?**
"REST + JSON con la librería estándar cubre las dos llamadas; el modelo precalcula
los 710 fotogramas y Unity los reproduce con control de velocidad. WebSocket
sobraría salvo que quisiéramos simulación en vivo."

**¿De dónde salió el tractor?**
"De Sketchfab (John Deere R8 de *yarifmx*, licencia CC Attribution). El GLB era una
escena completa de 2,145 piezas; la filtré por región y tamaño para quedarme con el
tractor, la convertí a OBJ y le asigné materiales URP."

**¿Cómo se pintan las celdas sembradas?**
"En el **alphamap** del terreno (capa de siembra): cada celda que el modelo marca
se pinta en el terreno, así se adapta a la pendiente. La textura tiene 3 pasadas,
12 surcos y brotes."

**¿Por qué el campo se ve con franjas?**
"Es la textura de siembra: 3 pasadas de 9.12 m por celda, con sus juntas y surcos."

**¿El 100 % de efectividad?**
"Sí: verifiqué con un contador que `marcadas = pintadas` y que **0 celdas
sembradas son obstáculo**. Con 0 obstáculos se siembran 1,599 de 1,600; la única
restante es la celda del depósito, donde arrancan y recargan los tractores."

---

## 7. Plan B si algo falla

- **No arranca el servidor**: revisar que el puerto 5000 esté libre
  (`lsof -iTCP:5000 -sTCP:LISTEN`); a veces macOS lo ocupa con AirPlay.
- **La app no simula**: ejecutar `iniciar_campo3d.command` (levanta servidor + app).
- **Falla el proyector**: usar las capturas de `escenario/Previews/`
  (`menu_3d.png`, `siembra_100ha_aerea.png`, `siembra_surcos.png`,
  `obstaculos_3d.png`, `tractor_john_deere.png`).
- **Se complica la demo en vivo**: abrir Unity con `Campo3D.unity` y dar Play; el
  menú y los controles son los mismos.

---

## 8. Versión corta (5 minutos)

1. **30 s** — qué es: 100 ha, Python decide, Unity dibuja.
2. **2 min** — demo: menú → INICIAR → **M** (vista aérea) → **C** (seguir tractor,
   mostrar HUD y halo) → **T** (velocidad) → "Volver al menú" y cambiar semilla.
3. **1 min 30 s** — rúbrica exprés: ProBuilder (bodega), heightmap (Terrain),
   malla importada (tractor), curva (script) y shaders (2 archivos).
4. **1 min** — resultados (91.2 ha, 1,148 L, 11 pasadas/ha, 8 h de campo) y
   limitaciones; mencionar `DOCUMENTACION-3D.md`.

---

## 9. Frases de una línea para memorizar

- "Python decide, Unity dibuja."
- "100 hectáreas reales: 1,600 celdas de 25 m y una sembradora de 9.12 m."
- "11 pasadas por hectárea, 110 km de recorrido."
- "8 horas de campo en 3 minutos de demo, y el HUD muestra el tiempo real."
- "Cada celda sembrada está pintada en el terreno; cero siembra sobre obstáculos."
