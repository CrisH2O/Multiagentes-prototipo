"""Planeación: el plan de siembra y las rutas.

- zigzag: en qué orden se siembran las celdas (antes de empezar).
- ruta_bfs: cómo llegar de una celda a otra (durante la siembra).
"""
from __future__ import annotations

from collections import deque

from campo import Celda


def manhattan(a: Celda, b: Celda) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# Recorrer en zigzag todas las celdas
def zigzag(mapa) -> list[Celda]:
    plan = []
    for y in range(mapa.alto):
        xs = range(mapa.ancho) if y % 2 == 1 else range(mapa.ancho - 1, -1, -1)
        plan += [(x, y) for x in xs if mapa.es_sembrable((x, y))]
    return plan

# Breadth-first search entre 2 celdas
def ruta_bfs(mapa, inicio: Celda, meta: Celda, evitar: set[Celda] | None = None,
             puede_pasar=None) -> list[Celda] | None:
    evitar = evitar or set()
    puede_pasar = puede_pasar or mapa.es_transitable
    if inicio == meta:
        return []
    if not puede_pasar(meta):
        return None
    padre = {inicio: None} # ¿Que camino me lleva a cada celda?
    cola = deque([inicio])
    while cola:
        actual = cola.popleft()
        for vecino in mapa.vecinos(actual):
            if vecino in padre or not puede_pasar(vecino):
                continue
            if vecino in evitar and vecino != meta:
                continue
            padre[vecino] = actual
            if vecino == meta: # Reconstruir el camino hacia atras
                ruta = [meta]
                while padre[ruta[-1]] != inicio:
                    ruta.append(padre[ruta[-1]])
                return ruta[::-1]
            cola.append(vecino)
    return None
