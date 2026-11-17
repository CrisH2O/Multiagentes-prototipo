# Rúbrica de Evaluación del Reto John Deere

**Valor total:** 100 puntos

## Objetivo General

Desarrollar una solución computacional que represente, analice y permita
experimentar con un problema relacionado con el contexto agrícola e industrial
de John Deere. Se deben demostrar competencias en modelado, programación,
experimentación, análisis de datos, visualización y pensamiento crítico,
enfocándose en la **arquitectura del (los) agente(s) y los mecanismos de
comunicación entre ellos**.

*Nota importante:* **No es obligatorio utilizar AgentPy**. Se pueden usar
Python, NumPy, SciPy, OpenCV, Matplotlib, Plotly, Streamlit, Dash, Mesa,
Pygame, etc. Las **visualizaciones 2D son suficientes** (no se requiere 3D),
pero es **obligatorio contar con un dashboard** para el análisis.

---

## Criterios de Evaluación

### 1. Formulación del problema y objetivos (10 puntos)

Explicar el problema a resolver, su importancia en John Deere y los resultados
esperados, estableciendo la relación entre el problema real, el modelo
computacional, la arquitectura de agentes y su comunicación.

- Explicar el fenómeno/comportamiento a estudiar.
- Identificar entradas, salidas y parámetros principales.
- Establecer objetivos medibles y definir preguntas de experimentación.
- Explicar simplificaciones y definir claramente la arquitectura/comunicación
  de agentes.

### 2. Modelado del entorno y de sus componentes (15 puntos)

Construir una representación computacional coherente (agentes, vehículos,
cultivos, obstáculos, etc.) y las reglas que determinan su comportamiento.

- Representar espacialmente el entorno (mapa, plano 2D).
- Diferenciar visualmente los elementos.
- Explicar la evolución de los estados del sistema y las relaciones
  entrada-decisión-resultado.

### 3. Implementación computacional y funcionamiento (15 puntos)

La solución debe ser ejecutable, organizada y demostrar el comportamiento
esperado.

- Separar configuración, lógica, ejecución, recolección de datos y
  visualización.
- Organizar el código en funciones/clases referentes a la arquitectura y
  comunicación de agentes.
- Evitar valores fijos, incluir validaciones y documentar dependencias.

### 4. Diseño experimental y exploración de escenarios (15 puntos)

Demostrar que la solución permite la experimentación sobre la arquitectura y
comunicación de los agentes.

- Ejecutar al menos **tres escenarios distintos y justificados**.
- Modificar parámetros relevantes y comparar resultados.
- Repetir pruebas ante aleatoriedad (usar semillas reproducibles).
- Identificar en qué condiciones el sistema funciona mejor o peor.

### 5. Métricas, indicadores y evaluación cuantitativa (15 puntos)

Definir y calcular indicadores objetivos de desempeño relacionados al problema
y a los agentes.

- Ejemplos de métricas: exactitud/precisión, errores, cobertura, tiempos,
  eficiencia, colisiones, variabilidad.
- Utilizar gráficas (barras, series temporales, histogramas, mapas de calor).
- Respaldar las conclusiones con resultados numéricos, no solo visuales.

### 6. Visualización 2D, animaciones y dashboards (10 puntos)

- **Visualización del entorno:** representación 2D del sistema (parcelas,
  vehículos, obstáculos) y sus cambios de estado. Se recomiendan animaciones
  si hay evolución temporal.
- **Dashboard de resultados:** debe incluir la representación 2D, indicadores
  cuantitativos, gráficas comparativas y los parámetros del experimento.
  Puede ser web (Streamlit, Dash) o estático bien organizado (Jupyter
  Notebook).
- **Calidad visual:** se valora la claridad sobre la complejidad. Usar títulos,
  etiquetas, leyendas y consistencia en colores.

### 7. Análisis crítico, sensibilidad y limitaciones (10 puntos)

Interpretar los resultados más allá de la simple descripción de las gráficas.

- Explicar el porqué de los resultados en ciertos escenarios.
- Identificar parámetros sensibles, fallos y limitaciones del modelo.
- Proponer mejoras justificadas técnicamente.

### 8. Reproducibilidad, documentación y presentación (10 puntos)

El proyecto debe poder ser comprendido y ejecutado por un tercero.

- **Entregables:** código fuente, notebooks/scripts, instrucciones de
  instalación/ejecución (README), datos de prueba, dashboard, resultados y
  video de demostración (si se solicita).
- Presentar con claridad qué se construyó, cómo funciona y las conclusiones.

---

## Escala de Evaluación

| Nivel de Desempeño | Rango | Descripción |
| :--- | :---: | :--- |
| **Excelente** | 90–100% | Solución completa, reproducible, con experimentación rigurosa, visualizaciones claras y análisis profundo de los agentes. |
| **Competente** | 81–89% | Solución funcional y documentada, con experimentación adecuada, aunque con oportunidades menores de mejora. |
| **En desarrollo** | 61–80% | Solución parcialmente funcional o con deficiencias relevantes en experimentación, visualización o documentación. |
| **Insuficiente** | 0–60% | Faltan componentes esenciales o evidencia verificable para evaluar la solución. |

---

## Consideraciones Finales (Checklist de Expectativas)

Se espera que cada equipo demuestre que su solución:

1. Representa un problema claramente definido usando la arquitectura y
   comunicación de agentes.
2. Ejecuta un modelo computacional funcional.
3. Permite experimentar con distintas condiciones.
4. Genera datos y resultados medibles.
5. Presenta visualizaciones 2D y dashboards comprensibles.
6. Facilita reproducir los experimentos.
7. Permite obtener conclusiones fundamentadas sobre los parámetros de diseño
   del sistema.
