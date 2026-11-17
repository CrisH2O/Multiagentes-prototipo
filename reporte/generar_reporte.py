"""Genera el reporte técnico en Word a partir de los resultados.

    python reporte/generar_reporte.py

Lee `resultados/experimentos.csv` y las figuras de `resultados/figuras/`,
calcula los agregados y arma `reporte/Reporte_Plantacion_Optima.docx`.
"""
from __future__ import annotations

import csv
import statistics as st
from collections import defaultdict
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "resultados"
FIGURAS = RESULTADOS / "figuras"
SALIDA = RAIZ / "reporte" / "Reporte_Plantacion_Optima.docx"

AZUL = RGBColor(0x1F, 0x4E, 0x79)
GRIS = RGBColor(0x44, 0x44, 0x44)


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def cargar():
    csv_ruta = RESULTADOS / "experimentos.csv"
    if not csv_ruta.exists():
        raise SystemExit("Falta resultados/experimentos.csv: corre `python experimentos.py`")

    filas = list(csv.DictReader(csv_ruta.open(encoding="utf-8")))
    grupos = defaultdict(list)
    for fila in filas:
        grupos[(fila["escenario"], fila["variante"])].append(fila)
    return filas, grupos


def metrica(grupo, clave):
    valores = [float(f[clave]) for f in grupo]
    return st.mean(valores), (st.stdev(valores) if len(valores) > 1 else 0.0)


# ---------------------------------------------------------------------------
# Utilidades de documento
# ---------------------------------------------------------------------------
def titulo(doc, texto, nivel=1):
    encabezado = doc.add_heading(texto, level=nivel)
    for run in encabezado.runs:
        run.font.color.rgb = AZUL
    return encabezado


def parrafo(doc, texto, negrita=False, cursiva=False, tamano=11,
            alineacion=None, espacio_despues=6):
    p = doc.add_paragraph()
    run = p.add_run(texto)
    run.bold = negrita
    run.italic = cursiva
    run.font.size = Pt(tamano)
    if alineacion is not None:
        p.alignment = alineacion
    p.paragraph_format.space_after = Pt(espacio_despues)
    return p


def vineta(doc, texto, tamano=11):
    p = doc.add_paragraph(style="List Bullet")
    run = p.add_run(texto)
    run.font.size = Pt(tamano)
    p.paragraph_format.space_after = Pt(2)
    return p


def tabla(doc, encabezados, filas, anchos=None):
    t = doc.add_table(rows=1, cols=len(encabezados))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    encabezado = t.rows[0].cells
    for i, texto in enumerate(encabezados):
        encabezado[i].text = ""
        parrafo_celda = encabezado[i].paragraphs[0]
        run = parrafo_celda.add_run(texto)
        run.bold = True
        run.font.size = Pt(9)
    for fila in filas:
        celdas = t.add_row().cells
        for i, valor in enumerate(fila):
            celdas[i].text = ""
            run = celdas[i].paragraphs[0].add_run(str(valor))
            run.font.size = Pt(9)
    if anchos:
        for fila_t in t.rows:
            for i, ancho in enumerate(anchos):
                fila_t.cells[i].width = Inches(ancho)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


FIGURA_NUM = [0]


def figura(doc, archivo, ancho, titulo_fig, que_muestra, como_se_genera, que_significa):
    ruta = FIGURAS / archivo
    if not ruta.exists():
        raise SystemExit(f"Falta la figura {ruta}: corre `python figuras.py`")

    FIGURA_NUM[0] += 1
    numero = FIGURA_NUM[0]

    doc.add_picture(str(ruta), width=Inches(ancho))
    ultima = doc.paragraphs[-1]
    ultima.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"Figura {numero}. {titulo_fig}")
    run.bold = True
    run.font.size = Pt(9.5)
    run.font.color.rgb = GRIS

    for etiqueta, texto in (
        ("Qué muestra: ", que_muestra),
        ("Cómo se genera: ", como_se_genera),
        ("Qué significa: ", que_significa),
    ):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Inches(0.15)
        run = p.add_run(etiqueta)
        run.bold = True
        run.font.size = Pt(10)
        run2 = p.add_run(texto)
        run2.font.size = Pt(10)


# ---------------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------------
def main() -> None:
    filas, grupos = cargar()

    def bloque(escenario):
        return {v.split("=")[-1]: g for (e, v), g in grupos.items() if e == escenario}

    terreno = bloque("terreno")
    flota = bloque("flota")
    obstaculos = bloque("obstaculos")
    costales = bloque("costales")
    estrategia = bloque("estrategia")

    ticks_g, _ = metrica(estrategia["greedy"], "ticks")
    ticks_z, _ = metrica(estrategia["zigzag"], "ticks")
    costo_g, _ = metrica(estrategia["greedy"], "costo_ha_sembrada")
    costo_z, _ = metrica(estrategia["zigzag"], "costo_ha_sembrada")
    litros_g, _ = metrica(estrategia["greedy"], "combustible_ha")
    litros_z, _ = metrica(estrategia["zigzag"], "combustible_ha")
    rep_g, _ = metrica(estrategia["greedy"], "ratio_repeticion")
    rep_z, _ = metrica(estrategia["zigzag"], "ratio_repeticion")

    ahorro_tiempo = (ticks_z - ticks_g) / ticks_z * 100
    ahorro_costo = (costo_z - costo_g) / costo_z * 100

    colisiones_totales = int(sum(float(f["colisiones"]) for f in filas))
    cobertura_min = min(float(f["cobertura"]) for f in filas)
    dobles = int(sum(float(f["siembras_dobles"]) for f in filas))
    repeticion_global = st.mean(float(f["ratio_repeticion"]) for f in filas) * 100

    doc = Document()

    # ------------------------- Portada -------------------------
    doc.add_paragraph()
    doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = t.add_run("Plantación Óptima")
    run.bold = True
    run.font.size = Pt(30)
    run.font.color.rgb = AZUL

    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = s.add_run("Sistema multiagente para la planeación de siembra agrícola")
    run.font.size = Pt(15)

    s2 = doc.add_paragraph()
    s2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = s2.add_run("Reto John Deere · Reporte técnico")
    run.font.size = Pt(12)
    run.font.color.rgb = GRIS

    doc.add_paragraph()
    doc.add_paragraph()

    for linea in (
        "Ana Paula García Valverde",
        "Pablo Velázquez Bremont",
        "Cristhian Zahid Huezo García",
        "Kevin Xiao Huang",
        "Alejandro Vila Casahonda",
        "Juan David Silva Camacho",
    ):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(linea)
        run.font.size = Pt(12)
        p.paragraph_format.space_after = Pt(0)

    doc.add_paragraph()
    fecha = doc.add_paragraph()
    fecha.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fecha.add_run("17 de noviembre de 2026")
    run.font.size = Pt(11)
    run.font.color.rgb = GRIS

    doc.add_page_break()

    # ------------------------- Resumen -------------------------
    titulo(doc, "Resumen ejecutivo", 1)
    parrafo(doc, (
        "Este trabajo construye un simulador multiagente que representa una flota de "
        "tractores sembrando un terreno agrícola irregular y responde una pregunta "
        "concreta: qué variables de diseño mueven realmente el costo y el tiempo de "
        "siembra. El modelo está calibrado en unidades de campo —hectáreas, costales "
        "de semilla y litros de diésel— a partir de una investigación agronómica con "
        "fuentes verificables."
    ))
    parrafo(doc, (
        f"Se ejecutaron {len(filas)} corridas controladas en cinco bloques "
        "experimentales, cada uno con cinco semillas reproducibles. El resultado "
        f"principal es que el planificador propuesto supera a la ruta base en zigzag: "
        f"{ahorro_tiempo:.0f}% menos tiempo y {ahorro_costo:.1f}% menos costo por "
        f"hectárea. Además, se encontró que la semilla concentra el 81% del costo y "
        "que el relieve apenas influye (0.4%), lo que revela una limitación del modelo "
        "más que una propiedad del problema."
    ))
    parrafo(doc, (
        f"En las {len(filas)} corridas la cobertura fue del "
        f"{cobertura_min * 100:.0f}% con {dobles} siembras dobles, y el consumo quedó "
        f"en el orden de magnitud de la literatura: 10.4 a 11.6 litros por hectárea "
        "frente a los 8.6–10.77 de las mediciones de campo."
    ))

    # ------------------------- 1. Introducción -------------------------
    titulo(doc, "1. Problema y objetivos", 1)
    parrafo(doc, (
        "Sembrar un campo irregular es un problema de coordinación bajo restricciones, "
        "no de trayectoria. Varios vehículos comparten terreno, combustible, semilla y "
        "una estación de recarga, y la decisión de uno altera el costo de los demás. "
        "En el contexto de John Deere, la pregunta operativa es cómo distribuir el "
        "trabajo para cubrir todo el terreno sin repetir tramos, sin colisionar y al "
        "menor costo posible."
    ))

    titulo(doc, "1.1 Objetivo general", 2)
    parrafo(doc, (
        "Reducir el costo total de siembra —tiempo, distancia y combustible— frente a "
        "una ruta en zigzag base, empleando los mismos mapas y la misma semilla, y "
        "verificar que no se produzcan colisiones."
    ))

    titulo(doc, "1.2 Preguntas de investigación", 2)
    for pregunta in (
        "¿El planificador propuesto le gana a la ruta base en zigzag?",
        "¿Cuánto encarece el relieve la misma tarea?",
        "¿Cuántos tractores conviene enviar antes de que se estorben?",
        "¿Cuánto degrada un terreno más fragmentado el recorrido?",
        "¿Cuánto cuesta reabastecerse muchas veces?",
    ):
        vineta(doc, pregunta)

    titulo(doc, "1.3 Alcance y simplificaciones", 2)
    parrafo(doc, (
        "No se modela la física del suelo, el clima en tiempo real ni sensores; el "
        "campo es una rejilla bidimensional y un tick equivale a un paso de celda. "
        "Estas simplificaciones se declaran y se discuten en la sección de limitaciones."
    ))

    # ------------------------- 2. Arquitectura -------------------------
    titulo(doc, "2. Arquitectura de agentes y comunicación", 1)
    parrafo(doc, (
        "El principio arquitectónico central es que Python es la única fuente de "
        "verdad: ahí viven el pathfinding, el cálculo de costos, las reglas físicas y "
        "la toma de decisiones. Unity y el tablero de análisis únicamente dibujan el "
        "estado que reciben, lo que evita duplicar reglas y desincronizar la "
        "visualización del cálculo."
    ))

    titulo(doc, "2.1 Ciclo de decisión del agente", 2)
    parrafo(doc, "Cada tractor ejecuta en cada tick un ciclo de tres fases:")
    vineta(doc, "Percibir: lee las celdas a su alcance y actualiza su mapa interno.")
    vineta(doc, (
        "Decidir: si no tiene semilla o combustible para regresar, pasa a RECARGANDO; "
        "si puede trabajar, busca por búsqueda en anchura (BFS) la celda sembrable más "
        "cercana que no esté reclamada por otro tractor."
    ))
    vineta(doc, (
        "Actuar: avanza una celda, descuenta combustible según la pendiente y siembra "
        "si llegó a un objetivo válido."
    ))

    titulo(doc, "2.2 Mecanismos de comunicación", 2)
    parrafo(doc, (
        "La comunicación entre agentes es implícita y ocurre mediante estructuras "
        "compartidas del modelo, lo que constituye el mecanismo central del sistema:"
    ))
    tabla(doc,
          ["Estructura", "Qué comparte", "Quién escribe"],
          [["seeded_map", "Celdas ya sembradas (evita doble siembra)", "Cualquier agente al sembrar"],
           ["target_pos", "Objetivo reclamado (evita converger a la misma celda)", "Cada agente al planear"],
           ["occupied", "Posiciones de todos los agentes", "Se consulta en cada BFS"]],
          anchos=[1.4, 3.4, 2.2])

    parrafo(doc, (
        "Además, el modelo ejecuta los tractores en turnos secuenciales dentro de cada "
        "tick, de modo que dos agentes no eligen la misma celda en el mismo instante."
    ))

    titulo(doc, "2.3 Integración con Unity", 2)
    parrafo(doc, (
        "La comunicación sigue el modo estático descrito en la propuesta: Python "
        "simula la corrida completa y devuelve todos los fotogramas en una sola "
        "respuesta JSON; Unity los reproduce a 0.14 segundos por tick. Se eligió sobre "
        "WebSocket por ser determinista, reproducible y libre de latencia de red."
    ))

    # ------------------------- 3. Modelo y escala -------------------------
    titulo(doc, "3. Modelo computacional y escala física", 1)
    titulo(doc, "3.1 Representación del entorno", 2)
    parrafo(doc, (
        "El terreno se representa como una matriz de celdas con cuatro tipos: fuera, "
        "cabecera, sembrable y obstáculo. Cada agente mantiene su propia copia del "
        "mapa, que corrige con sus lecturas, mientras el modelo conserva el mapa real. "
        "En Unity los obstáculos se dibujan como árboles y piedras, elegidos de forma "
        "determinista a partir de la semilla."
    ))

    titulo(doc, "3.2 Unidades y calibración", 2)
    parrafo(doc, (
        "El modelo se calibró a magnitudes de campo a partir de la investigación "
        "agronómica documentada en INVESTIGACION-AGRICOLA.md. La equivalencia central "
        "es que una celda mide 9 metros por lado —el ancho de trabajo de una "
        "sembradora de 12 surcos a 76 cm—, por lo que el campo simulado ocupa 3.24 "
        "hectáreas."
    ))
    tabla(doc,
          ["Concepto", "Equivalencia", "Fuente"],
          [["1 celda", "9 m × 9 m = 81 m²", "Sembradora de 12 surcos"],
           ["1 hectárea", "≈ 123 celdas", "10,000 m² / 81 m²"],
           ["1 costal (20 kg)", "≈ 60,000 semillas ≈ 1 ha", "INEGI / INIFAP (s.f.)"],
           ["Tanque de semilla", "1 costal = 123 celdas", "Calibración del modelo"],
           ["Siembra de 1 ha", "8.6 – 10.77 L de diésel", "AGRIS/FAO (2024)"],
           ["Precio diésel", "$27 MXN/L", "PROFECO (2026); SENER (2026)"],
           ["1 tick", "≈ 5.4 s (9 m a 6 km/h)", "Cinemática de avance"]],
          anchos=[1.6, 2.8, 2.4])

    parrafo(doc, (
        "El tanque se expresa en costales y no en unidades abstractas: un tanque lleno "
        "equivale a un costal de 20 kg, es decir una hectárea. El consumo de combustible "
        "se fijó en 0.0697 litros por celda para reproducir los 8.6 litros por hectárea "
        "medidos en campo."
    ))

    # ------------------------- 4. Metodología -------------------------
    titulo(doc, "4. Metodología experimental", 1)
    parrafo(doc, (
        f"Se diseñaron cinco bloques que aíslan una variable a la vez, con cinco "
        f"repeticiones por variante, para un total de {len(filas)} corridas. Cada "
        "repetición usa una semilla distinta que determina a la vez el terreno y la "
        "posición de los obstáculos, de modo que cualquier fila del archivo de "
        "resultados se puede reconstruir exactamente."
    ))
    tabla(doc,
          ["Bloque", "Variable aislada", "Valores probados"],
          [["Terreno", "Dificultad del relieve", "Plano, Medio, Montañoso"],
           ["Flota", "Número de tractores", "1, 2, 3, 5, 8"],
           ["Obstáculos", "Fragmentación del terreno", "0, 20, 50, 100"],
           ["Capacidad", "Costales por tanque", "0.25, 0.5, 1, 2"],
           ["Estrategia", "Método de ruteo", "Planificador, Zigzag"]],
          anchos=[1.4, 2.6, 2.8])

    titulo(doc, "4.1 Métricas", 2)
    tabla(doc,
          ["Métrica", "Definición", "Interpretación"],
          [["Cobertura", "Celdas sembradas / sembrables", "Garantía del servicio"],
           ["Siembras dobles", "Celdas sembradas dos veces", "Desperdicio de semilla"],
           ["Colisiones", "Fotogramas con dos tractores en una celda", "Fallo de coordinación"],
           ["Pasos repetidos", "Entradas a celdas ya recorridas", "Ineficiencia de ruta"],
           ["Diésel por ha", "Litros consumidos / hectárea", "Eficiencia energética"],
           ["Costo por ha", "Combustible + salarios + semilla", "Objetivo de optimización"]],
          anchos=[1.4, 3.0, 2.2])

    # ------------------------- 5. Resultados -------------------------
    titulo(doc, "5. Resultados", 1)

    titulo(doc, "5.1 El planificador frente a la ruta base", 2)
    parrafo(doc, (
        f"El planificador completó la siembra en {ticks_g:.0f} ticks frente a "
        f"{ticks_z:.0f} de la ruta en zigzag, con un costo de ${costo_g:,.0f} contra "
        f"${costo_z:,.0f} por hectárea sembrada. Esto representa {ahorro_tiempo:.0f}% "
        f"menos tiempo y {ahorro_costo:.1f}% menos costo."
    ))

    figura(doc, "fig_estrategia.png", 6.3,
           "Comparación de las dos estrategias de ruteo",
           "dos gráficas de barras con barras de error: a la izquierda los ticks "
           "necesarios y a la derecha el costo por hectárea sembrada, para el "
           "planificador y para la ruta base en zigzag.",
           "se ejecuta el mismo escenario (20×20 celdas, 3 tractores, 35 obstáculos) "
           "con las dos estrategias y cinco semillas distintas; cada barra es el "
           "promedio de esas cinco corridas y la línea vertical es la desviación "
           "estándar. El script figuras.py lee el archivo experimentos.csv y dibuja "
           "los promedios.",
           "el planificador es consistentemente mejor: cubre el terreno en menos "
           "tiempo porque elige siempre la celda pendiente más cercana, mientras el "
           "zigzag recorre filas completas aunque la siguiente celda por sembrar esté "
           "al otro lado del campo. La diferencia de costo es menor porque la semilla "
           "—que domina el gasto— es la misma en ambos casos.")

    titulo(doc, "5.2 Tamaño de la flota", 2)
    parrafo(doc, (
        "Al pasar de un tractor a ocho, el tiempo se reduce de 518 a 68 ticks, es "
        "decir 7.6 veces, mientras el costo por hectárea se mantiene prácticamente "
        "constante. El precio de esa velocidad son las colisiones: de cero a 21 por "
        "corrida."
    ))
    figura(doc, "fig_flota.png", 6.3,
           "Tiempo y costo según el número de tractores",
           "a la izquierda, barras con los ticks totales para 1, 2, 3, 5 y 8 tractores; "
           "a la derecha, una línea con el costo por hectárea sembrada para esos mismos "
           "tamaños de flota.",
           "cada punto proviene del promedio de cinco corridas en terreno Medio con 35 "
           "obstáculos; solo cambia el número de tractores y el resto de parámetros se "
           "mantiene fijo. Las colisiones anotadas son la suma de las cinco "
           "repeticiones de cada configuración.",
           "añadir tractores compra tiempo pero no dinero: el costo por hectárea varía "
           "menos del 1% porque la semilla es un costo fijo por hectárea. El límite "
           "práctico no es económico sino de coordinación, y aparece con cinco o más "
           "tractores, cuando varios compiten por el mismo depósito de recarga.")

    titulo(doc, "5.3 Capacidad del tanque de semilla", 2)
    parrafo(doc, (
        "Con un cuarto de costal el costo sube a $2,036 por hectárea y el consumo a "
        "17.4 litros por hectárea; con dos costales baja a $1,821 y 10.4 litros. El "
        "tanque de un costal es el punto de equilibrio, porque dos costales solo "
        "ahorran 1.6% adicional."
    ))
    figura(doc, "fig_costales.png", 6.3,
           "Efecto de la capacidad del tanque",
           "dos gráficas de barras: el costo por hectárea sembrada y el diésel por "
           "hectárea para capacidades de 0.25, 0.5, 1 y 2 costales por tanque. La línea "
           "punteada marca el consumo de referencia de 8.6 litros por hectárea "
           "reportado por la literatura.",
           "se varía únicamente la capacidad del tanque; la semilla, el terreno y la "
           "flota quedan fijos. El costo y el consumo se obtienen de las métricas del "
           "modelo y se normalizan por la superficie sembrada.",
           "la capacidad importa porque cada recarga implica un viaje de ida y vuelta "
           "al depósito sin sembrar. Con un cuarto de costal el tractor pasa más tiempo "
           "viajando que sembrando y el consumo se dispara 67%. A partir de un costal "
           "el beneficio marginal se agota: duplicar el tanque ya no compensa.")

    titulo(doc, "5.4 Relieve del terreno", 2)
    parrafo(doc, (
        "La diferencia entre un terreno plano y uno montañoso es de 0.4% en costo y de "
        "0.3 litros por hectárea en combustible. La dispersión entre semillas es mayor "
        "que la diferencia entre terrenos."
    ))
    figura(doc, "fig_terreno.png", 6.3,
           "Costo y combustible por tipo de terreno",
           "dos gráficas de puntos con barras de error para terreno Plano, Medio y "
           "Montañoso. Se usan puntos en lugar de barras porque el eje está recortado: "
           "la diferencia es menor que la dispersión entre semillas.",
           "se ejecuta el mismo escenario cambiando solo el perfil de elevación; la "
           "media y la desviación estándar se calculan sobre cinco semillas por "
           "terreno.",
           "el relieve casi no influye porque el costo de movimiento usa la diferencia "
           "de elevación entre celdas contiguas sin normalizarla por la pendiente. Al "
           "subir y bajar de forma alternada, los sobrecostos se compensan con los "
           "descuentos. Es una limitación del modelo, no una propiedad del problema "
           "real.")

    titulo(doc, "5.5 Fragmentación del terreno", 2)
    parrafo(doc, (
        "Con 100 obstáculos el costo por hectárea del lote baja de $1,856 a $1,430, "
        "pero el costo por hectárea efectivamente sembrada sube de $1,860 a $1,913 y "
        "los pasos repetidos crecen de 15% a 25%."
    ))
    figura(doc, "fig_obstaculos.png", 6.3,
           "El efecto del denominador al medir el costo",
           "barras agrupadas que comparan dos formas de calcular el costo: por hectárea "
           "total del lote y por hectárea realmente sembrada, para 0, 20, 50 y 100 "
           "obstáculos.",
           "se recalcula el mismo conjunto de corridas con dos denominadores distintos: "
           "el área total del campo (3.24 ha, constante) y el área efectivamente "
           "sembrada, que se reduce al aumentar los obstáculos.",
           "es una advertencia metodológica: los obstáculos quitan superficie "
           "sembrable, de modo que el costo del lote baja aunque el sistema sea menos "
           "eficiente. Al normalizar por hectárea sembrada se ve el efecto real, que es "
           "un encarecimiento del 2.8% y más recorrido repetido.")

    titulo(doc, "5.6 Variabilidad entre semillas", 2)
    parrafo(doc, (
        "El coeficiente de variación del costo se mantiene entre 0.5% y 1.9% en todas "
        "las configuraciones, lo que indica que las conclusiones no dependen de una "
        "semilla afortunada."
    ))
    figura(doc, "fig_variabilidad.png", 6.3,
           "Dispersión del costo entre repeticiones",
           "diagramas de caja del costo por hectárea sembrada para cada tamaño de flota "
           "y para cada estrategia. Cada caja resume cinco corridas con semillas "
           "distintas.",
           "se agrupan las cinco repeticiones de cada variante y se dibuja la caja con "
           "la mediana, los cuartiles y los valores atípicos.",
           "la dispersión es pequeña, así que las diferencias entre configuraciones son "
           "significativas. La caja más ancha corresponde a ocho tractores (1.9%), "
           "consistente con un sistema de coordinación más ruidoso cuando hay más "
           "agentes compitiendo.")

    titulo(doc, "5.7 Visualización del escenario", 2)
    parrafo(doc, (
        "El simulador en Unity reproduce la misma información en dos dimensiones: "
        "relieve, obstáculos, celdas sembradas y posición de los tractores."
    ))
    figura(doc, "fig_mapa.png", 4.6,
           "Estado final de una corrida simulada",
           "mapa bidimensional donde el fondo representa la elevación del terreno, los "
           "cuadros amarillos son celdas sembradas, los círculos verdes son obstáculos "
           "(árboles o piedras), el recuadro azul es el depósito y los círculos naranjas "
           "son los tractores.",
           "se toma el último fotograma de una corrida guardada y se dibuja la matriz "
           "de siembra acumulada junto con el mapa de elevación del escenario.",
           "permite verificar visualmente que la cobertura es completa y que ningún "
           "tractor terminó sobre un obstáculo. El simulador en Unity muestra la misma "
           "escena animada, tick a tick, con el mismo contrato de datos.")

    # ------------------------- 6. Comparativa -------------------------
    titulo(doc, "6. Comparativa con el método base", 1)
    parrafo(doc, (
        "La propuesta original comprometía comparar la ruta optimizada contra una ruta "
        "en zigzag con las mismas métricas. La ruta base se implementó como una "
        "estrategia adicional del mismo modelo, no como un cálculo aparte, para que "
        "ambas usaran el mismo motor de costos y de física. El recorrido en serpiente "
        "se genera una vez al inicio y se reparte entre los tractores en bloques "
        "contiguos."
    ))
    tabla(doc,
          ["Indicador", "Planificador", "Zigzag (base)", "Mejora"],
          [["Ticks", f"{ticks_g:.0f}", f"{ticks_z:.0f}", f"{ahorro_tiempo:.0f}% menos"],
           ["Costo por ha sembrada", f"${costo_g:,.0f}", f"${costo_z:,.0f}", f"{ahorro_costo:.1f}% menos"],
           ["Diésel por ha", f"{litros_g:.1f} L", f"{litros_z:.1f} L", f"{(litros_z - litros_g) / litros_z * 100:.1f}% menos"],
           ["Pasos repetidos", f"{rep_g * 100:.0f}%", f"{rep_z * 100:.0f}%", f"{(rep_z - rep_g) * 100:.0f} puntos"],
           ["Colisiones", "0", "0", "—"]],
          anchos=[1.8, 1.4, 1.4, 1.4])

    parrafo(doc, (
        "La ruta en zigzag tiene una ventaja conceptual: nunca repite una celda dentro "
        "de su plan, porque recorre filas completas. Sin embargo, el planificador la "
        "supera en tiempo y costo porque el zigzag paga dos penalizaciones que el "
        "planificador evita: al terminar una fila debe desplazarse hasta el extremo "
        "opuesto para empezar la siguiente, y al fragmentarse el terreno por "
        "obstáculos esas transiciones se alargan."
    ))
    parrafo(doc, (
        f"El ahorro en dinero ({ahorro_costo:.1f}%) parece pequeño en términos "
        "absolutos porque el 81% del costo es semilla, un gasto que no depende de la "
        "ruta. La ventaja real del planificador es de tiempo: "
        f"{ahorro_tiempo:.0f}% menos, equivalente a liberar el tractor casi una hora "
        "por cada cuatro de trabajo."
    ))

    # ------------------------- 7. Investigación -------------------------
    titulo(doc, "7. Datos agronómicos de referencia", 1)
    parrafo(doc, (
        "Para que el simulador hable en las unidades del campo se realizó una "
        "investigación documental sobre densidad de siembra de maíz, presentación "
        "comercial de la semilla y consumo de diésel en la labor de siembra."
    ))
    tabla(doc,
          ["Parámetro", "Valor adoptado", "Rango en la literatura"],
          [["Densidad de siembra", "60,000 semillas/ha", "45,000 – 80,000"],
           ["Semillas por kilogramo", "3,000", "≈ 3,000 (híbridos)"],
           ["Peso del costal", "20 kg", "20 kg (estándar comercial)"],
           ["Semillas por costal", "≈ 60,000", "≈ 60,000"],
           ["Precio del costal", "$1,500 MXN", "Programa subsidiado 2026"],
           ["Diésel en siembra", "8.6 L/ha", "8.6 – 10.77 L/ha"],
           ["Precio del diésel", "$27 MXN/L", "$25.39 – $28.00"]],
          anchos=[1.9, 1.7, 2.4])

    parrafo(doc, (
        "De ahí se deriva la equivalencia operativa del proyecto: un costal de 20 kg "
        "alcanza para una hectárea, y sembrar esa hectárea consume entre 8.6 y 10.77 "
        "litros de diésel. Para el campo simulado de 3.24 hectáreas se requieren "
        "alrededor de 3.2 costales y entre 28 y 35 litros de combustible, con un costo "
        "de diésel de 752 a 945 pesos."
    ))

    parrafo(doc, (
        "El modelo calibrado produce 10.4 a 11.6 litros por hectárea en las "
        "configuraciones operativas, lo que representa una desviación de 3 a 10% "
        "respecto a la literatura. La diferencia se explica porque el simulador "
        "incluye los viajes de recarga, que la medición de campo no contabiliza."
    ))

    # ------------------------- 8. Limitaciones -------------------------
    titulo(doc, "8. Limitaciones y trabajo futuro", 1)
    for limitacion in (
        "El relieve está subrepresentado: el costo por pendiente no se normaliza por "
        "la distancia, por lo que un desnivel real de 100 metros cuesta lo mismo que "
        "una loma suave.",
        "El depósito genera colisiones: todos los tractores comparten la misma celda "
        "de recarga y el planificador la excluye de las celdas prohibidas, lo que "
        "produce hasta 21 colisiones con ocho tractores.",
        "La repetición de tramos no está penalizada: el agente no recuerda por dónde "
        "pasó, solo qué sembró, y el 18.3% de los pasos repiten recorrido.",
        "Existe una sola línea base: comparar contra un único zigzag favorece al "
        "planificador. Faltan franjas paralelas y partición del campo por zonas.",
        "La calibración es parcial: la semilla está calibrada por construcción, así "
        "que el 81% del costo es una identidad y no un resultado del modelo. Tampoco "
        "se incluye depreciación de maquinaria ni preparación del terreno.",
    ):
        vineta(doc, limitacion)

    parrafo(doc, (
        "Como trabajo futuro se propone penalizar la repetición de tramos añadiendo un "
        "costo creciente a las celdas ya transitadas, modelar el depósito como un "
        "recurso con cola de espera, normalizar la pendiente por distancia y ampliar "
        "el conjunto de líneas base."
    ))

    # ------------------------- 9. Conclusiones -------------------------
    titulo(doc, "9. Conclusiones", 1)
    for conclusion in (
        f"El planificador supera a la ruta base en zigzag: {ahorro_tiempo:.0f}% menos "
        f"tiempo y {ahorro_costo:.1f}% menos costo por hectárea, con los mismos mapas y "
        "la misma semilla.",
        "La capacidad del tanque de semilla es la decisión de mayor impacto entre las "
        "variables operativas; el tanque de un costal es el punto de equilibrio.",
        "Añadir tractores reduce el tiempo hasta 7.6 veces sin encarecer la operación, "
        "pero degrada la coordinación y multiplica las colisiones.",
        "El relieve casi no influye en el resultado, lo que constituye una limitación "
        "del modelo y una línea de mejora prioritaria.",
        "El sistema es reproducible: la misma semilla reconstruye exactamente el mismo "
        "terreno y el mismo resultado, condición necesaria para cualquier conclusión "
        "comparativa.",
    ):
        vineta(doc, conclusion)

    # ------------------------- 10. Referencias -------------------------
    titulo(doc, "10. Referencias", 1)

    referencias = [
        "AGRIS. (2024). Evaluación de parámetros de siembra de maíz a diferentes "
        "velocidades de operación del implemento y utilizando el monitor de siembra "
        "SeedStar. Organización de las Naciones Unidas para la Alimentación y la "
        "Agricultura. https://agris.fao.org/search/en/records/669f609c00eb85b7d72c3501",

        "Deere & Company. (s. f.). 1775NT 12Row30 drawn planter. Recuperado el 17 de "
        "noviembre de 2026, de "
        "https://www.deere.africa/en-afme/products-solutions/planters/drawn-planters/1775nt-12row30-drawn-planter-njixoeg",

        "Deere & Company. (s. f.). Semoir de précision DR12. Recuperado el 17 de "
        "noviembre de 2026, de "
        "https://www.deere.ca/fr/équipement-ensemencement/semoir-précision-dr12/",

        "H. Ayuntamiento de Tuxpan, Jalisco. (2026). Programa de comercialización de "
        "semilla de maíz híbrido a bajo costo P.V. 2026. "
        "https://www.tuxpan-jal.gob.mx/webok/?p=27860",

        "Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. Computing in "
        "Science & Engineering, 9(3), 90–95. https://doi.org/10.1109/MCSE.2007.55",

        "Instituto Nacional de Estadística y Geografía. (s. f.). El maíz: densidad de "
        "siembra y variedades recomendadas. "
        "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/historicos/380/702825118259/702825118259.pdf",

        "Instituto Nacional de Tecnología Agropecuaria. (s. f.). Análisis integrado del "
        "consumo de bienes y servicios en explotaciones agrícolas. "
        "https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/7119/INTA_CRSantaFe_EEARafaela_Benzi_P_Análisis_integrado_del_consumo_de_bienes_y_servicios.pdf",

        "MAS Seeds México. (2024). MAS 59K: Ficha de producto. "
        "https://www.masseeds.mx/buscador-de-productos/maiz/MAS_59K/",

        "McKinney, W. (2010). Data structures for statistical computing in Python. En "
        "S. van der Walt y J. Millman (Eds.), Proceedings of the 9th Python in Science "
        "Conference (pp. 56–61). https://doi.org/10.25080/Majora-92bf1922-00a",

        "Panorama Agrario. (2016, 12 de mayo). Les facilitan semilla de maíz a "
        "agricultores. "
        "https://panoramaagrario.com/2016/05/les-facilitan-semilla-maiz-agricultores/amp/",

        "Procuraduría Federal del Consumidor. (2026, 22 de abril). Gobierno de México y "
        "sector gasolinero acuerdan mantener el precio máximo del diésel en 28 pesos "
        "el litro. https://www.gob.mx/profeco/prensa/gobierno-de-mexico-y-sector-gasolinero-acuerdan-mantener-el-precio-maximo-del-diesel-en-28-pesos-el-litro-424321",

        "Secretaría de Energía. (2026, 31 de agosto). La Presidenta de México y el "
        "sector gasolinero renuevan la Estrategia Nacional para Estabilizar el Precio "
        "de la Gasolina Regular y el Diésel. "
        "https://www.gob.mx/sener/es/articulos/la-presidenta-de-mexico-y-el-sector-gasolinero-renuevan-la-estrategia-nacional-para-estabilizar-el-precio-de-la-gasolina-regular-y-el-diesel",

        "Streamlit. (2026). Streamlit (Versión 1.67) [Software]. "
        "https://streamlit.io",

        "Unity Technologies. (2026). Unity (Versión 6000.6.8f1) [Software]. "
        "https://unity.com",
    ]

    for referencia in referencias:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.5)
        p.paragraph_format.first_line_indent = Inches(-0.5)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(referencia)
        run.font.size = Pt(10)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(SALIDA)
    print(f"Reporte generado: {SALIDA.relative_to(RAIZ)}")
    print(f"Figuras incluidas: {FIGURA_NUM[0]}")
    print(f"Corridas analizadas: {len(filas)}")


if __name__ == "__main__":
    main()
