"""Generación reproducible de escenarios (terreno + obstáculos).

Este módulo reproduce en Python la misma lógica que el escenario de Unity
(`TerrainGenerator.cs` y `PlantingGrid.cs`), pero con **semilla explícita**,
de modo que cualquier experimento se puede repetir bit a bit.

Convención de indexación: las matrices se guardan como ``[x][y]`` (columna,
fila), igual que las consume ``agentesPrueba.run_simulation``.
"""
from __future__ import annotations

import numpy as np

import unidades

# Los tres tipos de terreno que ofrece el menú de Unity
TERRENOS = {
    "plano": 1,      # dificultad 1
    "colinas": 2,    # dificultad 2
    "montanoso": 3,  # dificultad 3
}

# Parámetros por defecto, alineados con los valores del inspector de Unity
GRID_POR_DEFECTO = 20
OBSTACULOS_POR_DEFECTO = 35


# ---------------------------------------------------------------------------
# Ruido suave determinista (sustituto reproducible de Mathf.PerlinNoise)
# ---------------------------------------------------------------------------
def _ruido_suave(rng: np.random.Generator, n: int, celdas: int = 6) -> np.ndarray:
    """Ruido suave en rejilla ``n x n`` con valores en [0, 1].

    Se genera una malla gruesa aleatoria y se interpola bilinealmente. El
    resultado tiene la misma "textura" que el ruido Perlin de Unity, pero es
    totalmente reproducible a partir de la semilla de ``rng``.
    """
    grueso = rng.random((celdas + 1, celdas + 1))

    xs = np.linspace(0.0, celdas, n)
    i = np.clip(xs.astype(int), 0, celdas - 1)
    f = (xs - i).reshape(-1, 1)

    # Interpolación horizontal de cada fila
    filas = grueso[i, :] * (1 - f) + grueso[i + 1, :] * f  # (n, celdas+1)

    # Interpolación vertical
    g = f.reshape(1, -1)
    return filas[:, i] * (1 - g) + filas[:, i + 1] * g


def _colina(x: np.ndarray, y: np.ndarray, cx: float, cy: float, radio: float) -> np.ndarray:
    """Campana gaussiana centrada en (cx, cy), igual que ``TerrainGenerator.Hill``."""
    return np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2.0 * radio ** 2))


# ---------------------------------------------------------------------------
# Elevación
# ---------------------------------------------------------------------------
def generar_elevacion(terreno: str, n: int = GRID_POR_DEFECTO,
                      semilla: int = 0) -> np.ndarray:
    """Devuelve una matriz ``n x n`` de elevaciones normalizadas en [0, 1].

    Los valores no son metros: son alturas relativas, tal como las usa el
    modelo para penalizar el consumo de combustible al subir pendientes.
    """
    if terreno not in TERRENOS:
        raise ValueError(f"Terreno desconocido: {terreno!r}. Usa {list(TERRENOS)}")

    rng = np.random.default_rng(semilla)
    ruido = _ruido_suave(rng, n)

    u, v = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n), indexing="ij")

    if terreno == "plano":
        altura = 0.38 + (ruido - 0.5) * 0.08

    elif terreno == "colinas":
        altura = (
            0.22
            + 0.38 * _colina(u, v, 0.30, 0.35, 0.14)
            + 0.35 * _colina(u, v, 0.72, 0.65, 0.18)
            + (ruido - 0.5) * 0.12
        )

    else:  # montanoso
        altura = (
            0.12
            + 0.62 * _colina(u, v, 0.28, 0.68, 0.16)
            + 0.72 * _colina(u, v, 0.72, 0.30, 0.13)
            + 0.25 * _colina(u, v, 0.53, 0.52, 0.10)
            + (ruido - 0.5) * 0.10
        )

    return np.clip(altura, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Obstáculos
# ---------------------------------------------------------------------------
def _celdas_alcanzables(obstaculos: np.ndarray, inicio: tuple[int, int]) -> int:
    """Cuenta celdas libres conectadas al depósito (BFS de 4 vecinos)."""
    n = obstaculos.shape[0]
    vistos = {inicio}
    cola = [inicio]
    while cola:
        x, y = cola.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < n and 0 <= ny < n and (nx, ny) not in vistos:
                if obstaculos[nx, ny] == 0:
                    vistos.add((nx, ny))
                    cola.append((nx, ny))
    return len(vistos)


def _conectado(obstaculos: np.ndarray, depot: tuple[int, int]) -> bool:
    """¿Todas las celdas libres siguen conectadas al depósito?"""
    n = obstaculos.shape[0]
    libres = n * n - int(obstaculos.sum())
    return _celdas_alcanzables(obstaculos, depot) == libres


def generar_obstaculos(n: int, cantidad: int, semilla: int,
                       depot: tuple[int, int] = (0, 0)) -> np.ndarray:
    """Matriz binaria ``n x n`` con 1 donde hay obstáculo.

    La base (``depot``) nunca puede ser obstáculo y **el campo siempre queda
    conectado**. Los obstáculos se colocan de uno en uno sobre un orden
    aleatorio (derivado de la semilla) y se descarta cualquier celda que
    parta el terreno en islas o encierre el depósito.

    Sin esta garantía aparecían corridas degeneradas (0 celdas alcanzables,
    1 tick) que sesgaban los promedios del experimento.
    """
    if cantidad < 0:
        raise ValueError("La cantidad de obstáculos no puede ser negativa")

    n_celdas_libres = n * n - 1
    if cantidad > n_celdas_libres:
        raise ValueError("Hay más obstáculos que celdas disponibles")

    rng = np.random.default_rng(semilla)
    candidatas = [(x, y) for x in range(n) for y in range(n)
                  if (x, y) != tuple(depot)]
    orden = rng.permutation(len(candidatas))

    obstaculos = np.zeros((n, n), dtype=int)
    colocados = 0

    for indice in orden:
        if colocados == cantidad:
            break
        x, y = candidatas[int(indice)]
        obstaculos[x, y] = 1
        if _conectado(obstaculos, tuple(depot)):
            colocados += 1
        else:
            obstaculos[x, y] = 0  # desconectaría el campo: se descarta

    if colocados < cantidad:
        raise ValueError(
            f"No se pueden colocar {cantidad} obstáculos en una rejilla {n}x{n} "
            f"manteniendo el terreno conectado (máximo alcanzado: {colocados})"
        )

    return obstaculos


# ---------------------------------------------------------------------------
# Atajo: escenario completo listo para `run_simulation`
# ---------------------------------------------------------------------------
def construir_payload(terreno: str = "plano", n: int = GRID_POR_DEFECTO,
                      n_agentes: int = 3, obstaculos: int = OBSTACULOS_POR_DEFECTO,
                      semilla: int = 0, costales: float = 1.0,
                      estrategia: str = "greedy",
                      tanque_litros: float = unidades.TANQUE_DIESEL_L,
                      salario_hora: float = unidades.SALARIO_HORA_MXN,
                      steps: int = 2000,
                      depot: tuple[int, int] = (0, 0),
                      lado_celda_m: float | None = None) -> dict:
    """Payload del servidor con parámetros en magnitudes de campo.

    ``costales`` es la capacidad del tanque expresada en costales de 20 kg:
    1 costal ≈ 1 ha ≈ 123 celdas. Todo lo demás se deriva de ahí
    (``unidades.parametros_calibrados``).
    """
    if costales <= 0:
        raise ValueError("costales debe ser mayor que cero")
    if estrategia not in ("greedy", "zigzag"):
        raise ValueError(f"Estrategia desconocida: {estrategia!r}")

    elevacion = generar_elevacion(terreno, n, semilla)
    mapa_obs = generar_obstaculos(n, obstaculos, semilla + 1, depot)
    calibrado = unidades.parametros_calibrados(
        costales_por_tanque=costales,
        tanque_litros=tanque_litros,
        salario_hora=salario_hora,
        **({"lado_celda_m": lado_celda_m} if lado_celda_m else {}),
    )

    return {
        "grid_size": [n, n],
        "difficulty": TERRENOS[terreno],
        "n_agents": int(n_agentes),
        "depot_pos": [int(depot[0]), int(depot[1])],
        "elevation_map": elevacion.tolist(),
        "obstacle_map": mapa_obs.tolist(),
        "estrategia": estrategia,
        "steps": int(steps),
        **calibrado,
    }


if __name__ == "__main__":
    # Demostración rápida de los tres terrenos
    for nombre in TERRENOS:
        elev = generar_elevacion(nombre, 8, semilla=1)
        print(f"{nombre:10s} min={elev.min():.3f} max={elev.max():.3f} "
              f"desnivel={elev.max() - elev.min():.3f}")
