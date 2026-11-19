"""Q-Learning tabular medido sobre los mapas del simulador de siembra.

Responde con datos las preguntas 5, 7, 8 y 10 del cuestionario de Q-Learning:

* ¿cuántos episodios cuesta aprender a navegar en la rejilla 20x20 del proyecto?
* ¿la política aprendida iguala al BFS (que ya resuelve el problema)?
* ¿el aprendizaje transfiere a un mapa nuevo o hay que reentrenar?

Entorno: rejilla 20x20 con los obstáculos reales de ``escenarios``, acción =
moverse en 4 direcciones, recompensa = -1 por paso, -2 por choque, +10 por
llegar y -5 por agotar el límite. Es el mismo problema de navegación que el
``find_next_step`` del modelo resuelve con BFS.

Uso:
    .venv/bin/python experimentos_qlearning.py

Salidas:
    resultados/qlearning_episodios.csv
    resultados/qlearning_resumen.json
    resultados/figuras/qlearning_curva.png
"""
from __future__ import annotations

import csv
import json
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "Agentes"))

import escenarios  # noqa: E402

DIRECCIONES = ((-1, 0), (1, 0), (0, -1), (0, 1))
N = 20
DEPOT = (0, 0)
MAX_PASOS = 200
ACCIONES = 4


# ---------------------------------------------------------------------------
# Mapa y BFS de referencia (el "planificador" del proyecto)
# ---------------------------------------------------------------------------
def mapa(terreno="colinas", semilla=1, obstaculos=35):
    payload = escenarios.construir_payload(
        terreno, n=N, obstaculos=obstaculos, semilla=semilla
    )
    return np.asarray(payload["obstacle_map"], dtype=int)


def bfs(obs, inicio):
    dist = {inicio: 0}
    cola = deque([inicio])
    while cola:
        actual = cola.popleft()
        for dx, dy in DIRECCIONES:
            vecino = (actual[0] + dx, actual[1] + dy)
            if (0 <= vecino[0] < N and 0 <= vecino[1] < N
                    and obs[vecino] == 0 and vecino not in dist):
                dist[vecino] = dist[actual] + 1
                cola.append(vecino)
    return dist


def celdas_libres(obs):
    return [(x, y) for x in range(N) for y in range(N) if obs[x, y] == 0]


class Navegador:
    """Entorno mínimo compatible con el bucle de Q-Learning (reset/step)."""

    def __init__(self, obs, meta):
        self.obs = obs
        self.meta = meta
        self.libres = celdas_libres(obs)
        self.pos = DEPOT
        self.pasos = 0

    def reset(self, inicio=None):
        self.pos = inicio if inicio is not None else self.libres[0]
        self.pasos = 0
        return self.pos

    def step(self, accion):
        dx, dy = DIRECCIONES[accion]
        nx, ny = self.pos[0] + dx, self.pos[1] + dy
        choque = not (0 <= nx < N and 0 <= ny < N and self.obs[nx, ny] == 0)
        if not choque:
            self.pos = (nx, ny)
        self.pasos += 1
        if self.pos == self.meta:
            return self.pos, 10.0, True
        if self.pasos >= MAX_PASOS:
            return self.pos, -5.0, True
        return self.pos, -1.0 - (2.0 if choque else 0.0), False


# ---------------------------------------------------------------------------
# Q-Learning tabular
# ---------------------------------------------------------------------------
def entrenar(entorno, inicios, episodios=1000, alpha=0.1, gamma=0.99,
             eps_final=0.05, rng=None, eval_cada=25, eval_inicios=None):
    """Q-learning epsilon-greedy con función de acción-valor ``Q[x, y, a]``."""
    rng = np.random.default_rng(0) if rng is None else rng
    Q = np.zeros((N, N, ACCIONES))
    curva = []

    for episodio in range(1, episodios + 1):
        epsilon = max(eps_final, 1.0 - (1.0 - eps_final) * episodio / episodios)
        estado = entorno.reset(inicios[int(rng.integers(len(inicios)))])
        while True:
            if rng.random() < epsilon:
                accion = int(rng.integers(ACCIONES))
            else:
                accion = int(np.argmax(Q[estado]))
            siguiente, recompensa, fin = entorno.step(accion)
            objetivo = recompensa
            if not fin:
                objetivo += gamma * float(Q[siguiente].max())
            Q[estado][accion] += alpha * (objetivo - Q[estado][accion])
            estado = siguiente
            if fin:
                break

        if eval_cada and episodio % eval_cada == 0:
            exito, pasos = evaluar(entorno, Q, eval_inicios)
            curva.append({
                "episodio": episodio,
                "epsilon": round(epsilon, 4),
                "exito": exito,
                "pasos_medios": pasos,
            })

    return Q, curva


def evaluar(entorno, Q, inicios):
    """Política greedy sobre un conjunto fijo de inicios (sin exploración).

    Devuelve el éxito y los pasos medios, pero solo sobre los inicios en los
    que la política llega: comparar pasos con el BFS sin filtrar premiaría a
    una política que falla en los casos difíciles.
    """
    exitos = 0
    pasos_totales = 0
    for inicio in inicios:
        estado = entorno.reset(inicio)
        for _ in range(MAX_PASOS):
            accion = int(np.argmax(Q[estado]))
            estado, _, fin = entorno.step(accion)
            if fin:
                break
        if estado == entorno.meta:
            exitos += 1
            pasos_totales += entorno.pasos
    return (exitos / len(inicios) if inicios else 0.0,
            round(pasos_totales / exitos, 2) if exitos else None)


def inicios_lejanos(obs, meta, cantidad, minimo=12, semilla=0):
    """Inicios a al menos ``minimo`` pasos BFS de la meta (tarea no trivial)."""
    dist = bfs(obs, meta)
    candidatos = sorted(
        (c for c, d in dist.items() if d >= minimo),
        key=lambda c: (dist[c], c),
    )
    rng = np.random.default_rng(semilla)
    if len(candidatos) <= cantidad:
        return candidatos
    indices = rng.choice(len(candidatos), size=cantidad, replace=False)
    return [candidatos[int(i)] for i in indices]


def entrenar_meta(obs, meta, inicios, eval_inicios, episodios=6000, rng=None):
    entorno = Navegador(obs, meta)
    inicio = time.perf_counter()
    Q, curva = entrenar(entorno, inicios, episodios=episodios, rng=rng,
                        eval_inicios=eval_inicios)
    segundos = time.perf_counter() - inicio
    exito, pasos_q = evaluar(entorno, Q, eval_inicios)

    dist = bfs(obs, meta)
    distancias = [dist[c] for c in eval_inicios]
    pasos_bfs = round(float(np.mean(distancias)), 2)
    primero = next((p["episodio"] for p in curva if p["exito"] >= 0.95), None)
    return {
        "meta": list(meta),
        "pasos_bfs": pasos_bfs,
        "pasos_q": pasos_q,
        "exito_final": exito,
        "episodios_a_95": primero,
        "segundos": round(segundos, 2),
        "curva": curva,
        "Q": Q,
        "distancias_bfs": distancias,
    }


def main():
    t0 = time.perf_counter()
    obs_a = mapa("colinas", semilla=1)
    obs_b = mapa("colinas", semilla=2)

    dist = bfs(obs_a, DEPOT)
    libres = celdas_libres(obs_a)
    candidatas = sorted((c for c in libres if dist.get(c, 0) >= 12),
                        key=lambda c: dist[c], reverse=True)
    metas = [candidatas[0]] + [candidatas[i] for i in (3, 7, 11, 15)]

    resultados = []
    for meta in metas:
        inicios = inicios_lejanos(obs_a, meta, 15, minimo=12, semilla=7)
        r = entrenar_meta(obs_a, meta, inicios, inicios,
                          episodios=6000, rng=np.random.default_rng(0))

        # Transferencia: misma Q, misma meta (o la libre más cercana) y otros
        # obstáculos. Así se mide generalización al mapa, no a otra tarea.
        dist_b = bfs(obs_b, DEPOT)
        if obs_b[meta] == 0 and meta in dist_b:
            meta_b = meta
        else:
            meta_b = min(celdas_libres(obs_b),
                         key=lambda c: abs(c[0] - meta[0]) + abs(c[1] - meta[1]))
        entorno_b = Navegador(obs_b, meta_b)
        inicios_b = inicios_lejanos(obs_b, meta_b, 15, minimo=12, semilla=7)
        exito_transfer, pasos_transfer = evaluar(entorno_b, r["Q"], inicios_b)
        r["transfer_exito"] = exito_transfer
        r["transfer_pasos"] = pasos_transfer
        r["meta_b"] = list(meta_b)
        resultados.append(r)

    resumen = {
        "mapa": "colinas 20x20, 35 obstáculos, semilla 1",
        "celdas_libres": len(libres),
        "episodios_por_meta": 6000,
        "alpha": 0.1,
        "gamma": 0.99,
        "epsilon": "1.0 -> 0.05 lineal",
        "metas": [],
        "segundos_totales": None,
    }
    for r in resultados:
        resumen["metas"].append({
            "meta": r["meta"],
            "pasos_bfs": r["pasos_bfs"],
            "pasos_q": r["pasos_q"],
            "exito_final": round(r["exito_final"], 3),
            "episodios_a_95": r["episodios_a_95"],
            "transfer_exito": round(r["transfer_exito"], 3),
            "transfer_pasos": r["transfer_pasos"],
            "meta_b": r["meta_b"],
        })

    con_exito = [r for r in resultados if r["pasos_q"] and r["pasos_bfs"]]
    resumen.update({
        "exito_final_medio": round(float(np.mean([r["exito_final"] for r in resultados])), 3),
        "ratio_pasos_q_vs_bfs": round(float(np.mean([
            r["pasos_q"] / r["pasos_bfs"] for r in con_exito
        ])), 3) if con_exito else None,
        "episodios_a_95_medio": round(float(np.mean([
            r["episodios_a_95"] for r in resultados if r["episodios_a_95"]
        ])), 1),
        "transfer_exito_medio": round(float(np.mean([
            r["transfer_exito"] for r in resultados
        ])), 3),
        "segundos_por_meta": round(float(np.mean([
            r["segundos"] for r in resultados
        ])), 2),
    })
    resumen["segundos_totales"] = round(time.perf_counter() - t0, 2)

    salida = RAIZ / "resultados"
    salida.mkdir(exist_ok=True)
    with (salida / "qlearning_resumen.json").open("w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    with (salida / "qlearning_episodios.csv").open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["meta_x", "meta_y", "pasos_bfs", "pasos_q",
                           "exito_final", "episodios_a_95", "transfer_exito",
                           "transfer_pasos"])
        for r in resultados:
            escritor.writerow([r["meta"][0], r["meta"][1], r["pasos_bfs"],
                               r["pasos_q"], round(r["exito_final"], 3),
                               r["episodios_a_95"], round(r["transfer_exito"], 3),
                               r["transfer_pasos"]])

    _figura(resultados, salida / "figuras" / "qlearning_curva.png")

    print(json.dumps(resumen, ensure_ascii=False, indent=2))


def _figura(resultados, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig, (izq, der) = plt.subplots(1, 2, figsize=(11, 4.2))

    for i, r in enumerate(resultados):
        xs = [p["episodio"] for p in r["curva"]]
        ys = [p["exito"] * 100 for p in r["curva"]]
        izq.plot(xs, ys, label=f"meta {i + 1} ({r['pasos_bfs']} pasos BFS)")
    izq.set_xlabel("episodios de entrenamiento")
    izq.set_ylabel("éxito en evaluación greedy (%)")
    izq.set_title("Q-Learning: curva de aprendizaje")
    izq.axhline(95, color="gray", linestyle="--", linewidth=1, label="umbral 95%")
    izq.set_ylim(-5, 105)
    izq.grid(alpha=0.3)
    izq.legend(fontsize=7)

    x = np.arange(len(resultados))
    ancho = 0.35
    der.bar(x - ancho / 2, [r["pasos_bfs"] for r in resultados], ancho,
            label="BFS (óptimo)")
    der.bar(x + ancho / 2, [r["pasos_q"] or 0 for r in resultados], ancho,
            label="Q-Learning")
    der.set_xticks(x)
    der.set_xticklabels([f"meta {i + 1}" for i in range(len(resultados))])
    der.set_ylabel("pasos hasta la meta")
    der.set_title("Pasos: Q-Learning vs BFS")
    der.legend()
    der.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(destino, dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
