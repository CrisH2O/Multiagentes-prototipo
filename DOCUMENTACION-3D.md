# Documentación del escenario 3D — rúbrica punto por punto

Este documento explica **cómo se usó cada técnica de la rúbrica** en el escenario 3D del
proyecto, **dónde está** en el repositorio y **cómo verlo** funcionando, tanto en Unity
como en el ejecutable.

- Proyecto Unity: `escenario/` (Unity **6000.6.8f1**, URP 17.6, ProBuilder 6.1.3).
- Escena 3D: `escenario/Assets/Scenes/Campo3D.unity`.
- Escena 2D original: `escenario/Assets/Scenes/SampleScene.unity` (intacta).
- Ejecutable: `escenario/Builds/Campo3D.app` (macOS, ~89 MB).
- Servidor Python: `Agentes/agentesPrueba.py`.

---

## 1. Cómo ejecutar el proyecto

### 1.1 En Unity (para revisar la escena)

1. Abrir `escenario/` con Unity **6000.6.8f1**.
2. Abrir `Assets/Scenes/Campo3D.unity`.
3. Verificar que el servidor Python esté corriendo (ver 1.2).
4. Presionar **Play**: aparece el **menú inicial** (terreno / tractores / estrategia) y al
   dar **INICIAR** se reproduce la simulación.

### 1.2 Servidor Python (obligatorio para simular)

```bash
cd Multiagentes-prototipo
.venv/bin/python Agentes/agentesPrueba.py
```

Queda escuchando en `http://127.0.0.1:5000` con dos rutas:

| Ruta | Método | Para qué |
|---|---|---|
| `/simulate` | POST | Recibe el payload y devuelve todos los fotogramas de la corrida |
| `/payload` | GET | Genera el payload según `terreno`, `agentes`, `estrategia`, `costales` |

### 1.3 Ejecutable

```bash
# Opción A: lanzador (arranca el servidor y abre el juego)
./iniciar_campo3d.command

# Opción B: abrir la app con el servidor ya corriendo
open escenario/Builds/Campo3D.app
```

### 1.4 Controles

| Tecla | Acción |
|---|---|
| Flechas | Orbitar la cámara |
| W A S D | Desplazar el centro de la cámara |
| Rueda / Q / E | Zoom |
| **C** | Cambiar cámara: órbita → Tractor_01 → 02 → 03 |
| **M** | Vista aérea del campo / volver |
| **T** | Cambiar escala de tiempo (1:600, 1:300, 1:150, 1:60, 1:30) |
| **Espacio** | Pausa / reanudar |
| F | Reiniciar encuadre |
| H | Ocultar la ayuda |

---

## 2. Uso de figuras primitivas

**Qué se hizo.** Varios elementos del escenario se construyeron con primitivas de Unity
(`GameObject.CreatePrimitive`), no con mallas importadas:

| Elemento | Primitivas | Detalle |
|---|---|---|
| `CampoBase` | `Plane` | Plano de 8,000 × 8,000 m que rodea al terreno para que el campo no parezca una isla flotante |
| Árbol (`Arbol.prefab`) | `Cylinder` + 2 `Sphere` | Tronco (cilindro) y dos copas (esferas) |
| Roca (`Roca.prefab`) | 2 `Sphere` | Dos esferas deformadas por escala |
| `HaloSembradora` (hijo del tractor) | `Quad` | Franja que representa el ancho de labor (9.12 m) |
| `CeldaSembrada.prefab` | `Plane` | Baldosa de 25 × 25 m (prefab de referencia) |

Las primitivas se crean desde el script de editor
`escenario/Assets/Editor/Campo3DSceneBuilder.cs` (método `Primitiva` y `CrearPrefabArbol`,
`CrearPrefabRoca`, `CrearCampoBase`, `CrearPrefabCelda`).

**Dónde verlo.**
- En Unity: jerarquía `ESCENARIO → CampoBase`, `OBJETOS → Arbol_01..03`, `Roca_01..02`.
  Seleccionar cualquiera y revisar `Mesh Filter` (mesh `Plane`, `Cylinder` o `Sphere`).
- En el ejecutable: los árboles y rocas se ven sobre el terreno; al hacer zoom se distinguen
  el cilindro y las esferas.

**Cómo verificarlo.** En el Inspector de un árbol: `Mesh Filter → Mesh: Cylinder/Sphere` y
`Transform → Scale` distinto de 1. Son primitivas escaladas, no modelos importados.

---

## 3. Uso de ProBuilder y Prefabs

### 3.1 ProBuilder

**Qué se hizo.** Se instaló **ProBuilder 6.1.3** (viene incluido en el editor) y se modeló
con su API la **bodega del depósito**:

- `Bodega`: cubo de ProBuilder deformado a **40 × 12 × 25 m** (paredes).
- `TechoBodega`: cubo de ProBuilder deformado a **44 × 1 × 29 m** (techo con voladizo).

No son cubos escalados: los vértices se deforman con `ProBuilderMesh.positions` y luego
`ToMesh()` + `Refresh()`, por lo que la geometría queda a escala real y el objeto conserva
el componente **ProBuilderMesh** (editable con la herramienta).

Código: `Campo3DSceneBuilder.CrearBodega()` y `DeformarCaja()`.

**Dónde verlo.**
- Unity: `ESCENARIO → Bodega` y `ESCENARIO → TechoBodega`. En el Inspector aparece el
  componente **ProBuilder Mesh**.
- Para editarla: `Tools → ProBuilder → ProBuilder Window`, seleccionar `Bodega` y usar los
  modos de cara/arista/vértice.
- El paquete instalado: `Packages/manifest.json` → `"com.unity.probuilder": "6.1.3"`.

### 3.2 Prefabs

Se guardaron cuatro prefabs en `escenario/Assets/Prefabs/`:

| Prefab | Contenido |
|---|---|
| `Tractor.prefab` | Tractor John Deere (malla importada) + materiales URP + `BoxCollider` + `HaloSembradora` |
| `Arbol.prefab` | Tronco + dos copas |
| `Roca.prefab` | Dos esferas |
| `CeldaSembrada.prefab` | Baldosa de 25 m (referencia) |

La escena instancia los prefabs (3 tractores, 3 árboles, 2 rocas). En el ejecutable se
crean instancias adicionales si el menú pide 4 tractores.

**Cómo verificarlo.** En Unity, seleccionar `OBJETOS → Tractor_01` y ver en el Inspector que
es una **instancia de prefab** (encabezado con el nombre del prefab y flecha de override).
Doble clic en `Assets/Prefabs/Tractor.prefab` para abrirlo en modo prefab.

---

## 4. Uso de Heightmaps

**Qué se hizo.** El terreno NO es un plano: es un **Terrain** de Unity construido a partir
de un **mapa de alturas PNG** generado en Python con la **misma elevación** que usa el
modelo multiagente.

- Script: `herramientas/generar_assets_3d.py` (función `generar_mapa_alturas`).
- Salidas: `escenario/Assets/Texturas/heightmap_plano.png`,
  `heightmap_colinas.png`, `heightmap_montanoso.png` (513 × 513 px, 8 bits).
- Tamaño del terreno: **1,000 × 1,000 m = 100 ha**, altura máxima **8 m**
  (513 px sobre 1,000 m ≈ 2 m por texel).
- En Unity se leen los píxeles con `Texture2D.GetPixels()`, se cargan en un `TerrainData`
  con `SetHeights()` y se crean **tres terrenos** (uno por altura) que el menú activa.

Además del heightmap, el terreno usa un **alphamap** (512 × 512) con tres capas:
césped, tierra (alrededor del depósito) y **sembrado** (la que pinta el simulador).

**Dónde verlo.**
- Unity: `ESCENARIO → Terreno_Colinas` (o `Terreno_Plano` / `Terreno_Montañoso`).
  Inspector del Terrain → botón **Terrain Settings**: `Heightmap Resolution: 513`,
  `Width/Height: 1000`, y en *Paint Terrain* las tres capas.
- Activar/desactivar los tres terrenos en la jerarquía para ver el relieve distinto.
- En el ejecutable: menú → elegir **Plano / Colinas / Montañoso** y notar el cambio de
  relieve del campo.
- El PNG original: abrir `Assets/Texturas/heightmap_colinas.png` (se ve el mapa de alturas).

---

## 5. Uso de mallas importadas

**Qué se hizo.** El tractor es una **malla importada** de Sketchfab (John Deere R8):

- GLB original: `~/Downloads/john_deere_r8.glb` (no se versiona).
- Conversión GLB → OBJ: `herramientas/glb_a_obj.py` (lee el glTF binario, aplica las
  transformaciones de nodos, extrae texturas y escribe OBJ + MTL).
- Extracción del tractor de la escena de Sketchfab: filtro por región y tamaño
  (`--region` y `--max-tamano`), porque el GLB era una escena completa (2,145 piezas,
  72 × 71 m) y no solo el tractor.
- Resultado: `escenario/Assets/Modelos/JohnDeereR8/tractor_r8.obj` +
  `tractor_r8.mtl` + `texturas/`.
- Medidas reales: **7.25 × 4.14 × 3.56 m**, **150,948 triángulos**, 64 materiales.
- En Unity se importa como modelo, se le asignan materiales URP (con sus texturas) y se
  guarda como `Assets/Prefabs/Tractor.prefab`, con el pivote en el suelo y mirando a +Z.

**Dónde verlo.**
- Unity: `Assets/Modelos/JohnDeereR8/tractor_r8.obj` (seleccionar y ver el preview en el
  Inspector) y `Assets/Prefabs/Tractor.prefab`.
- En el ejecutable: tecla **C** para seguir a un tractor y ver el modelo en detalle.
- El OBJ está en **Git LFS** (`.gitattributes`: `*.obj lfs`), por eso el repo no pesa 150 MB.

**Cómo verificarlo.** En el Inspector del OBJ: `Meshes → tractor_r8` con 150,948
triángulos y 64 sub-mallas; `Materials` importados.

---

## 6. Uso de cámaras

**Qué se hizo.** Hay una **cámara principal** en perspectiva (`CAMARAS → Camara Principal`)
con tres modos de uso, más el HUD que muestra el estado de cada tractor:

| Modo | Cómo se activa | Qué hace |
|---|---|---|
| Órbita | por defecto | Cámara orbital alrededor del campo, con zoom y desplazamiento |
| Seguimiento | tecla **C** | Se pega detrás del tractor elegido y lo sigue |
| Vista aérea | tecla **M** | Sube a una vista cenital de todo el campo (100 ha) |

La cámara usa el **renderer 3D** del pipeline (`UniversalRendererData` en
`Assets/Settings/Renderer3D.asset`), separado del renderer 2D que usa la escena original.

**Dónde verlo.**
- Unity: seleccionar `Camara Principal` → componentes `Camera` (FOV 50, perspectiva),
  `Universal Additional Camera Data` (renderer 3D, post-proceso activado),
  `OrbitCamera` y `CamaraSeguimiento`.
- En el ejecutable: mantener **C** para recorrer órbita → Tractor_01 → 02 → 03, y **M**
  para la vista aérea.

---

## 7. Movimiento de la cámara

**Qué se hizo.** Dos scripts con suavizado, sin saltos:

- `OrbitCamera.cs`:
  - Órbita con **botón derecho**, desplazamiento con **botón central**, zoom con **rueda**.
  - Teclado: flechas (orbitar), WASD (desplazar), Q/E (zoom), Shift (más rápido).
  - Suavizado exponencial: `t = 1 - exp(-suavizado * dt)`, independiente de los FPS.
  - Límites de inclinación (8°–80°), distancia (25–1,200 m) y desplazamiento (±480 m).
  - **M**: vista aérea (82° de inclinación, 760 m).
- `CamaraSeguimiento.cs`:
  - Se coloca a 15 m detrás y 7 m arriba del tractor, mirándolo.
  - Posición y rotación **exactas** (sin retardo) para que a escala 1:600 el tractor no se
    salga de cuadro.

**Dónde verlo.**
- En Unity Play: arrastrar con el botón derecho para orbitar y notar el amortiguamiento.
- En el ejecutable: probar los controles de la tabla de la sección 1.4.

---

## 8. Comunicación con nodo de Python usando API

**Qué se hizo.** La lógica de la simulación vive en Python; Unity **solo dibuja**. La
comunicación es por **HTTP local**:

1. Unity pide a Python el payload según el menú:
   `GET http://127.0.0.1:5000/payload?terreno=colinas&agentes=3&estrategia=greedy`
2. Unity envía ese payload a:
   `POST http://127.0.0.1:5000/simulate` (con `UnityWebRequest` y `Content-Type: application/json`).
3. Python responde **todos los fotogramas** de la corrida (710 en el escenario por defecto).
4. Unity los reproduce.

Si el servidor no está arriba en el editor, `Simulacion3D` intenta **arrancarlo solo**
(`Agentes/agentesPrueba.py`). En el ejecutable hay que tenerlo corriendo (o usar
`iniciar_campo3d.command`).

**Dónde verlo.**
- Código: `escenario/Assets/Scripts/Simulacion3D.cs` (`Ejecutar`, `Enviar`, `EnviarGet`).
- Servidor: `Agentes/agentesPrueba.py` (`do_GET` con `/payload`, `do_POST` con `/simulate`).
- Prueba rápida sin Unity:

```bash
curl "http://127.0.0.1:5000/payload?terreno=colinas&agentes=3&estrategia=greedy"
curl -X POST http://127.0.0.1:5000/simulate -H "Content-Type: application/json" \
     -d @escenario/Assets/StreamingAssets/payload_colinas.json
```

- En el ejecutable: el HUD muestra `Tick`, `Sembrado: X ha`, y los tractores se mueven;
  si se cae el servidor aparece el mensaje de error.

---

## 9. Uso de JSON

**Qué se hizo.** Todo el intercambio es JSON, en ambos sentidos:

| Archivo / clase | Contenido |
|---|---|
| `escenario/Assets/StreamingAssets/payload_colinas.json` | Payload completo: `grid_size`, `elevation_map` 40×40, `obstacle_map`, `n_agents`, `max_seeds`, `max_fuel`, `fuel_por_paso`, `cost_per_seed`, etc. |
| `Respuesta3D` (C#) | `status`, `metrics`, `frames[]` |
| `Frame3D` | `tick`, `planted_cells[]`, `agents[]`, `remaining_cells` |
| `AgenteFrame3D` | `id`, `pos[2]`, `state`, `fuel`, `seeds`, `planted_total` |
| `Metricas3D` | `total_ticks`, `total_steps`, `total_fuel_consumed`, `driver_wage_cost`, `seed_cost`, `remaining_cells` |

La deserialización usa `JsonUtility.FromJson<Respuesta3D>(json)` y el payload de configuración
se lee con `JsonUtility.FromJson<Config3D>(payload)` (para conocer la rejilla y los máximos
de semilla y combustible que muestra el HUD).

**Dónde verlo.**
- Abrir `escenario/Assets/StreamingAssets/payload_colinas.json` (JSON del payload).
- Ver los frames: ejecutar el `curl` de la sección 8 y guardar la respuesta.
- En el código: las clases `[Serializable]` al inicio de `Simulacion3D.cs`.

---

## 10. Proyecto en ejecutable

**Qué se hizo.** Se compila un **.app de macOS** con solo la escena 3D:

- Script: `escenario/Assets/Editor/ConstruirJuego.cs` (`ConstruirMac`), menú
  `Herramientas → Campo 3D → Construir macOS`.
- Salida: `escenario/Builds/Campo3D.app` (**89.5 MB**).
- El ejecutable NO va en Git (`.gitignore`); se regenera con el menú de Unity.

Incluye un modo de **prueba automática** (`-autotest`) que corre la simulación completa sin
ventana y sale con código 0:

```bash
./Builds/Campo3D.app/Contents/MacOS/escenario -batchmode -autotest
# [AUTOTEST] OK | ticks=710 | celdas=1459 | tractores=3 | rutas=3 | combustible=1148.40
```

**Dónde verlo.** Abrir `escenario/Builds/Campo3D.app` (o `./iniciar_campo3d.command`).
Si macOS lo bloquea por no estar firmado: clic derecho → **Abrir**.

---

## 11. Movimiento fluido con curvas paramétricas

**Qué se hizo.** Los tractores **no saltan** de celda en celda: su trayectoria es una
**spline de Catmull-Rom** que pasa por el centro de cada celda que visitan.

- Script: `escenario/Assets/Scripts/CatmullRomSpline.cs`.
  - `Evaluar(float indice)` interpola cúbicamente entre puntos (el índice es el número de
    punto; 1.5 = mitad del tramo entre el punto 1 y el 2).
  - `Tangente(indice)` por diferencias finitas (para orientar el tractor).
  - `PuntoEnDistancia(distancia)` con **tabla de longitud de arco** (200 muestras), para
    recorridos a velocidad constante (se usa para el movimiento).
- `Simulacion3D.PrepararEscena()` construye una ruta por agente con **todas** las posiciones
  de sus fotogramas y luego `PosicionarTractores(progreso)` evalúa la curva en el progreso
  continuo (no entero), de modo que el avance es suave aunque el modelo avance por ticks.
- El tractor se **inclina con la pendiente** del terreno (`GetInterpolatedNormal`) y su base
  queda apoyada en el suelo (se corrigió el pivote del modelo).

**Dónde verlo.** En el ejecutable: seguir un tractor con **C** y observar que gira en curva
en las esquinas y no “teleporta”. En Unity: el script `CatmullRomSpline.cs` documenta la
matemática; en Play, seleccionar `Tractor_01` y ver el movimiento continuo en la escena.

---

## 12. Uso de materiales y texturas

**Qué se hizo.** Materiales URP Lit para todo, con texturas generadas por Python:

- Materiales en `escenario/Assets/Materials/`: `Cesped`, `Tierra`, `Corteza`, `Hoja`,
  `Roca`, `CespedBase`, `Sembrado`, `Terreno`, `Cielo`, `VerdeJohnDeere`,
  `AmarilloRuedas`, `VidrioCabina`, `GrisDetalle`, `ParedBodega`, `TechoBodega`,
  `CeldaSembrada`, más los 64 materiales del tractor en `Assets/Materials/Tractor/`.
- Texturas en `escenario/Assets/Texturas/` (generadas con `herramientas/generar_assets_3d.py`):
  - `cesped.png` (256², tileable, con manchas de pasto seco)
  - `tierra.png` (256², con piedritas)
  - `sembrado.png` (**512²**: 3 pasadas de 9.12 m, 12 surcos por pasada de 0.76 m,
    semillas brotando sobre la cresta y juntas entre pasadas)
  - `heightmap_*.png` (mapas de alturas)
- El terreno usa **Terrain Layers** (`Assets/Terreno/CapaCesped`, `CapaTierra`,
  `CapaSembrado`) con tiling en metros: la capa de siembra repite la textura cada 25 m
  (una celda).
- Los materiales del tractor se asignan por nombre desde el MTL, con su textura cuando
  existe.

**Dónde verlo.**
- Unity: `Assets/Materials` (cada material con su `_BaseMap`), `Assets/Terreno` (Terrain
  Layers con su textura y `Tile Size`), y el Terrain en `Paint Terrain`.
- En el ejecutable: hacer zoom al suelo sembrado (se ven los surcos y los brotes) y a la
  bodega (paredes y techo con materiales distintos).

---

## 13. Uso de iluminación

**Qué se hizo.**

- **Sol**: luz direccional `ILUMINACION → Sol`, rotación (48°, −32°), color cálido
  (1, 0.95, 0.86), intensidad 1.35, **sombras suaves** (`LightShadows.Soft`), distancia de
  sombras ampliada a **600 m** para cubrir el campo de 1 km.
- **Ambiente**: `AmbientMode.Trilight` con colores de cielo, ecuador y suelo.
- **Niebla**: exponencial cuadrática, densidad 0.00045 (da profundidad al campo de 1 km).
- **Cielo**: material con **shader propio** (ver sección 14), asignado a
  `RenderSettings.skybox`.
- **Post-proceso**: objeto `PostProceso` con un `Volume` global y el perfil
  `Assets/Settings/PerfilCampo3D.asset` (Bloom, Tonemapping ACES, Vignette, Color
  Adjustments). La cámara principal tiene `renderPostProcessing = true`.

**Dónde verlo.**
- Unity: seleccionar `Sol` (Light), `ESCENARIO/PostProceso` (Volume + perfil) y
  `Camara Principal` (post-proceso activado).
- En el ejecutable: el sol proyecta sombras de los tractores y árboles; el horizonte tiene
  la niebla y el cielo del shader.

*Limitación conocida:* en el build, URP elimina algunas variantes del shader de **Bloom**
(el log del jugador avisa “Shader 'Hidden/Universal Render Pipeline/Bloom' … stripped”).
El tonemapping, la viñeta y el color sí se aplican. En el editor el bloom sí se ve.

---

## 14. Uso de shaders para efectos especiales

Se escribieron **dos shaders HLSL propios** en `escenario/Assets/Shaders/`:

### 14.1 `CieloGradiente.shader` (aplicado)

- Shader de **skybox** con degradado de tres colores (arriba, horizonte, abajo) en función
  de la dirección de la mirada.
- Se usa en el material `Assets/Materials/Cielo.mat`, asignado a
  `RenderSettings.skybox` de la escena.
- **Cómo verlo:** en el ejecutable, mirar el cielo (degradado azul); en Unity, abrir
  `Cielo.mat` y ver el shader `Campo3D/CieloGradiente`, o cambiar `_ColorArriba` y ver el
  cielo cambiar en Play.

### 14.2 `CeldaSembrada.shader` (aplicado al halo de la sembradora)

- Shader **aditivo** con degradado radial calculado desde las UV y **pulso senoidal**
  (`_Time.y`), sin texturas.
- Se usa en el material `Assets/Materials/CeldaSembrada.mat`, que está en el hijo
  **`HaloSembradora`** del prefab `Tractor.prefab`: un quad de **9.12 m de ancho**
  (el ancho real de labor) que brilla bajo cada tractor y “respira”.
- **Cómo verlo:** en el ejecutable, seguir un tractor con **C** y ver el halo verde pulsante
  bajo la sembradora; su ancho es el de la sembradora real.
- En Unity: abrir `Assets/Shaders/CeldaSembrada.shader` y su material; en Play, el halo
  aparece bajo los tractores.

### 14.3 Shaders de post-proceso

Además, el pipeline usa los shaders de post-proceso de URP (Bloom, Tonemapping, UberPost,
FinalPost), agregados a **Always Included Shaders** en `ProjectSettings/GraphicsSettings.asset`
para que el build no los elimine (ver limitación del bloom en la sección 13).

---

## 15. El escenario en números (para el reporte)

| Dato | Valor |
|---|---|
| Superficie | **100 ha** (1,000 × 1,000 m) |
| Celdas de simulación | **40 × 40 = 1,600** celdas de 25 × 25 m |
| Área de una celda | 625 m² = **0.0625 ha** |
| Celdas por hectárea | **16** |
| Ancho de la sembradora | **9.12 m** (12 surcos × 0.76 m) |
| Una pasada cubre | 9.12 × 25 = 228 m² = 0.0228 ha = **36.5 %** del ancho de la celda |
| Pasadas por celda | **2.74 → 3** |
| Pasadas por hectárea | **11** (1,100 m lineales) |
| Recorrido total del campo | ≈ **110 km** de pasadas |
| Corrida por defecto (sin obstáculos) | **741 ticks**, **1,599 celdas** sembradas (99.9 ha), 1,199 L de diésel |
| Corrida con obstáculos | **710 ticks**, **1,459 celdas** sembradas (91.2 ha), 1,148 L de diésel |
| Tiempo de campo simulado | **8 h 05 min** |
| Escalas de reproducción | 1:600 (50 s) … 1:30 (16 min); por defecto **1:150** (~3.2 min) |

El HUD muestra en todo momento `Sembrado: X ha (%)`, `Faltan: Y ha`,
`Celda: 25x25 m = 0.0625 ha` y `Sembradora: 9.12 m = 36 % del ancho de una celda por pasada`,
además del tiempo de campo transcurrido.

---

## 16. Cómo se generan los assets (reproducibilidad)

```bash
# 1) Texturas, heightmaps, malla del tractor y payload
.venv/bin/python herramientas/generar_assets_3d.py

# 2) (Opcional) Convertir el GLB del tractor a OBJ
.venv/bin/python herramientas/glb_a_obj.py ~/Downloads/john_deere_r8.glb \
    escenario/Assets/Modelos/JohnDeereR8 --region 14 32 -20 -4 --max-tamano 6 --nombre tractor_r8

# 3) Reconstruir la escena 3D en Unity (batch)
Unity -batchmode -quit -projectPath escenario \
      -executeMethod Campo3DSceneBuilder.CrearEscena

# 4) Compilar el ejecutable
Unity -batchmode -quit -projectPath escenario \
      -executeMethod ConstruirJuego.ConstruirMac
```

En el editor también están en el menú **Herramientas → Campo 3D**:
*Crear escena Campo3D*, *Renderizar vista previa*, *Construir macOS*,
*Probar API y curvas*.

---

## 17. Limitaciones conocidas

1. **Ruedas estáticas.** El GLB del John Deere viene con toda la geometría fusionada en una
   sola malla; no fue posible separar las 4 ruedas sin romper el modelo (se intentó por
   material y por nodos del glTF). Para que giren haría falta un modelo con las ruedas como
   piezas aparte.
2. **Bloom en el build.** URP elimina las variantes del shader de Bloom en la compilación
   (aviso en el log). Tonemapping, viñeta y color sí funcionan.
3. **Servidor Python externo.** El `.app` no arranca el servidor por sí solo; hay que
   ejecutarlo (o usar `iniciar_campo3d.command`).
4. **App sin firmar.** macOS puede pedir confirmación la primera vez (clic derecho → Abrir).
5. **Cambio de terreno.** La bodega y los adornos se colocan con la altura del terreno de
   colinas; al cambiar a plano/montañoso la altura del depósito es la misma (meseta), pero
   árboles y rocas pueden quedar ligeramente hundidos o flotando.
6. **Celdas que no se siembran.** No son un fallo de dibujo: el modelo marca como no
   sembrables las celdas con obstáculo y la celda del depósito. El simulador pinta
   exactamente las celdas que marca (comprobado con un contador: `marcadas = pintadas`,
   0 celdas marcadas sin pintar). El menú permite elegir **"Sin obstáculos (100 %)"**, que
   deja 1,599 de 1,600 celdas sembradas (la única restante es el depósito, donde arrancan y
   recargan los tractores).

---

## 18. Resumen de la rúbrica

| Criterio | Dónde está | Cómo verlo |
|---|---|---|
| Figuras primitivas | `CampoBase`, `Arbol.prefab`, `Roca.prefab`, `HaloSembradora` | Jerarquía/Inspector; árboles y rocas en el juego |
| ProBuilder y Prefabs | `Bodega`, `TechoBodega` (ProBuilderMesh); `Assets/Prefabs` | Inspector con ProBuilder; instancias de prefab |
| Heightmaps | `Assets/Texturas/heightmap_*.png` → Terrain 513² | Terrain Settings; menú de terrenos |
| Mallas importadas | `Assets/Modelos/JohnDeereR8/tractor_r8.obj` | Inspector del OBJ; tecla C en el juego |
| Cámaras | `Camara Principal` (órbita/seguimiento/aérea) | Componentes Camera + scripts; teclas C y M |
| Movimiento de cámara | `OrbitCamera.cs`, `CamaraSeguimiento.cs` | Botón derecho, WASD, rueda, C, M |
| API con Python | `Simulacion3D.cs` ↔ `agentesPrueba.py` | `curl /payload` y `/simulate` |
| JSON | `payload_colinas.json`, `Respuesta3D`/`Frame3D` | Abrir el JSON; frames en la respuesta |
| Ejecutable | `Builds/Campo3D.app` | Abrir la app / `iniciar_campo3d.command` |
| Curvas paramétricas | `CatmullRomSpline.cs` | Seguir un tractor (C) y ver los giros suaves |
| Materiales y texturas | `Assets/Materials`, `Assets/Texturas`, Terrain Layers | Zoom al suelo sembrado y a la bodega |
| Iluminación | `Sol`, `PostProceso`, cielo | Sombras, niebla y cielo en el juego |
| Shaders | `Assets/Shaders/CieloGradiente.shader`, `CeldaSembrada.shader` | Cielo degradado y halo pulsante bajo el tractor |

---

## 19. Créditos

- **John Deere R8** — *yarifmx* (Sketchfab), licencia **CC Attribution**.
- **ProBuilder**, **URP** y **Unity 6** — Unity Technologies.
- El resto de texturas y mallas (pasto, tierra, siembra, bodega, árboles, rocas) se generan
  por script en `herramientas/generar_assets_3d.py`.
