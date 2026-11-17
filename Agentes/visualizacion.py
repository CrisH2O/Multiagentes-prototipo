
from __future__ import annotations

import agentpy as ap
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Patch

from agents import Sembradora
from campo import TipoCelda

# Un código por cada cosa que se dibuja en el campo
(FUERA, CABECERA, SEMBRABLE, OBSTACULO, SEMBRADA, RUTA, IMPREVISTO,
 ENCUENTRO, NODRIZA, SEMBRADORA) = range(10)

COLORES = {
    FUERA: "#ffffff",
    CABECERA: "#c9b79c",
    SEMBRABLE: "#efe6cf",
    OBSTACULO: "#555555",
    SEMBRADA: "#6aaa4f",
    RUTA: "#9ecae1",
    IMPREVISTO: "#d62728",
    ENCUENTRO: "#ffd60a",
    NODRIZA: "#e85d04",
    SEMBRADORA: "#1f3a93",
}

ETIQUETAS = {
    CABECERA: "Cabecera",
    SEMBRABLE: "Por sembrar",
    SEMBRADA: "Sembrada",
    OBSTACULO: "Obstáculo conocido",
    IMPREVISTO: "Obstáculo no detectado",
    RUTA: "Ruta planeada",
    ENCUENTRO: "Punto de encuentro",
    NODRIZA: "Nodriza",
    SEMBRADORA: "Sembradora",
}


def cuadricula_de_colores(modelo) -> np.ndarray:
    """Convierte el estado del modelo en una matriz de códigos (uno por celda)."""
    campo, s = modelo.campo, modelo.sembradora
    real = campo.mapa.tipos
    grid = np.array(real, dtype=float)    # FUERA, CABECERA, SEMBRABLE, OBSTACULO ya coinciden con 0..3

    grid[campo.sembradas > 0] = SEMBRADA
    # Obstáculo en el mundo real que NO está en el mapa de la sembradora
    no_detectado = (real == TipoCelda.OBSTACULO) & (s.mapa.tipos != TipoCelda.OBSTACULO)
    grid[no_detectado] = IMPREVISTO
    for x, y in s.ruta:
        grid[y, x] = RUTA
    n = modelo.nodriza
    if n.pedido is not None:
        x, y = n.pedido["punto"]
        grid[y, x] = ENCUENTRO
    x, y = n.posicion
    grid[y, x] = NODRIZA
    x, y = s.posicion
    grid[y, x] = SEMBRADORA
    return grid


def dibujar_campo(modelo, ax) -> None:
    s, n = modelo.sembradora, modelo.nodriza
    ap.gridplot(cuadricula_de_colores(modelo), ax=ax, color_dict=COLORES, convert=True)
    ax.set_title(f"Tick {modelo.t} — Cobertura: {modelo.campo.cobertura():.0%}   Recargas: {s.recargas}\n"
                 f"Sembradora: {s.estado} ({s.semilla_kg:.0f}/{s.capacidad_tolva_kg:.0f} kg)   "
                 f"Nodriza: {n.estado} ({n.kg_entregados:.0f} kg entregados)", fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.legend(handles=[Patch(color=COLORES[k], label=v) for k, v in ETIQUETAS.items()],
              loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=4, fontsize=8, frameon=False)


def animacion_plot(modelo, ax) -> None:
    """Función para ap.animate: dibuja solo el campo (la simulación)."""
    dibujar_campo(modelo, ax)


def periodos(ticks, estados, buscados) -> list[tuple[int, int]]:
    """Intervalos [inicio, fin) en los que el estado estuvo dentro de `buscados`."""
    intervalos, inicio = [], None
    for t, estado in zip(ticks, estados):
        if estado in buscados and inicio is None:
            inicio = t
        elif estado not in buscados and inicio is not None:
            intervalos.append((inicio, t))
            inicio = None
    if inicio is not None:
        intervalos.append((inicio, ticks[-1] + 1))
    return intervalos
