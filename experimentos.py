"""Diseño experimental: corre escenarios, repite con semillas y exporta CSV.

Uso típico:

    python experimentos.py                     # corrida completa (≈80 simulaciones)
    python experimentos.py --repeticiones 3    # menos repeticiones, más rápido
    python experimentos.py --solo terreno      # un solo bloque experimental

Cada fila del CSV es una corrida independiente y reproducible: la columna
``semilla`` reconstruye exactamente el mapa y el azar del modelo.

Salidas:

* ``resultados/experimentos.csv``  -> una fila por corrida (para el dashboard)
* ``resultados/runs/*.json``       -> fotogramas de corridas representativas
                                     (para animar el mapa 2D en el dashboard)
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CODIGO = RAIZ / "Agentes"
sys.path.insert(0, str(CODIGO))

import agentesPrueba  # noqa: E402
import escenarios  # noqa: E402
import metricas  # noqa: E402

# ---------------------------------------------------------------------------
# Bloques experimentales
# ---------------------------------------------------------------------------
# Cada bloque aísla UNA variable y deja el resto en su valor base:
# 3 tractores, terreno "colinas", 35 obstáculos, 35 semillas por tanque.

BASE = {
    "terreno": "colinas",
    "n_agentes": 3,
    "obstaculos": 35,
    "max_seeds": 35,
}

BLOQUES = {
    "terreno": {
        "variable": "terreno",
        "pregunta": "¿Cuánto encarece el relieve la misma tarea?",
        "variantes": [{"terreno": t} for t in ("plano", "colinas", "montanoso")],
    },
    "flota": {
        "variable": "n_agentes",
        "pregunta": "¿Cuántos tractores conviene mandar antes de que se estorben?",
        "variantes": [{"n_agentes": k} for k in (1, 2, 3, 5, 8)],
    },
    "obstaculos": {
        "variable": "obstaculos",
        "pregunta": "¿Cuánto degrada un terreno más fragmentado el recorrido?",
        "variantes": [{"obstaculos": k} for k in (0, 20, 50, 100)],
    },
    "semillas": {
        "variable": "max_seeds",
        "pregunta": "¿Cuánto cuesta reabastecerse muchas veces?",
        "variantes": [{"max_seeds": k} for k in (10, 20, 35, 60)],
    },
}

COLUMNAS = [
    "escenario", "variante", "repeticion", "semilla",
    "grid", "terreno", "n_agentes", "obstaculos", "max_seeds",
    "ticks", "pasos", "combustible_l", "costo_salarios", "costo_semillas",
    "costo_total", "cobertura", "colisiones", "pasos_repetidos",
    "ratio_repeticion", "max_visitas_celda", "celdas_sembradas",
    "siembras_dobles", "celdas_restantes", "segundos",
]


def corrida(config: dict, semilla: int, grid: int, precio_litro: float,
            verbose: bool = False) -> tuple[dict, dict, dict]:
    """Ejecuta una simulación y devuelve (métricas, respuesta, payload)."""
    payload = escenarios.construir_payload(
        terreno=config["terreno"],
        n=grid,
        n_agentes=config["n_agentes"],
        obstaculos=config["obstaculos"],
        semilla=semilla,
        max_seeds=config["max_seeds"],
    )

    inicio = time.perf_counter()
    if verbose:
        respuesta = agentesPrueba.run_simulation(payload)
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            respuesta = agentesPrueba.run_simulation(payload)
    segundos = time.perf_counter() - inicio

    resumen = metricas.resumir_corrida(
        respuesta["frames"], respuesta["metrics"], precio_litro=precio_litro
    )
    resumen["segundos"] = round(segundos, 3)
    return resumen, respuesta, payload


def nombre_variante(config: dict, variable: str) -> str:
    """Etiqueta legible: la variable que aisla el bloque."""
    return f"{variable}={config[variable]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimentos del simulador agrícola")
    parser.add_argument("--repeticiones", type=int, default=5,
                        help="repeticiones por variante (semillas 1..N)")
    parser.add_argument("--grid", type=int, default=20, help="tamaño del terreno")
    parser.add_argument("--precio-litro", type=float, default=24.0,
                        help="precio del combustible en MXN por litro")
    parser.add_argument("--solo", default=None,
                        help=f"ejecutar solo un bloque: {', '.join(BLOQUES)}")
    parser.add_argument("--salida", default=str(RAIZ / "resultados"))
    parser.add_argument("--sin-frames", action="store_true",
                        help="no guardar JSON de fotogramas (CSV más rápido)")
    parser.add_argument("--verbose", action="store_true",
                        help="mostrar la salida de cada simulación")
    args = parser.parse_args()

    if args.repeticiones < 1:
        print("--repeticiones debe ser >= 1", file=sys.stderr)
        return 2

    bloques = BLOQUES if args.solo is None else {args.solo: BLOQUES[args.solo]}
    if args.solo and args.solo not in BLOQUES:
        print(f"Bloque desconocido: {args.solo}", file=sys.stderr)
        return 2

    salida = Path(args.salida)
    carpeta_runs = salida / "runs"
    salida.mkdir(parents=True, exist_ok=True)
    if not args.sin_frames:
        carpeta_runs.mkdir(parents=True, exist_ok=True)

    total = sum(len(b["variantes"]) for b in bloques.values()) * args.repeticiones
    print(f"Experimentos: {total} simulaciones · grid {args.grid}x{args.grid} "
          f"· {args.repeticiones} repeticiones por variante")

    filas: list[dict] = []
    hechas = 0
    inicio = time.perf_counter()

    for nombre, bloque in bloques.items():
        print(f"\n[{nombre}] {bloque['pregunta']}")
        for variante in bloque["variantes"]:
            config = {**BASE, **variante}
            etiqueta = nombre_variante(config, bloque["variable"])

            for repeticion in range(1, args.repeticiones + 1):
                semilla = repeticion  # semillas 1..N => mapas reconstruibles
                resumen, respuesta, _payload = corrida(
                    config, semilla, args.grid, args.precio_litro, args.verbose
                )
                hechas += 1

                filas.append({
                    "escenario": nombre,
                    "variante": etiqueta,
                    "repeticion": repeticion,
                    "semilla": semilla,
                    "grid": args.grid,
                    "terreno": config["terreno"],
                    "n_agentes": config["n_agentes"],
                    "obstaculos": config["obstaculos"],
                    "max_seeds": config["max_seeds"],
                    **resumen,
                })

                # Se guardan los fotogramas de la primera repetición de cada
                # variante: suficiente para animar el mapa sin inflar el repo.
                if repeticion == 1 and not args.sin_frames:
                    valor = etiqueta.split("=")[-1]
                    archivo = carpeta_runs / f"{nombre}_{valor}_s{semilla}.json"
                    archivo.write_text(json.dumps({
                        "escenario": nombre,
                        "variante": etiqueta,
                        "semilla": semilla,
                        "config": config,
                        "elevation_map": _payload["elevation_map"],
                        "obstacle_map": _payload["obstacle_map"],
                        "metrics": resumen,
                        "frames": respuesta["frames"],
                    }), encoding="utf-8")

                print(f"  {etiqueta:16s} rep {repeticion}  "
                      f"ticks={resumen['ticks']:4d}  "
                      f"costo=${resumen['costo_total']:9.2f}  "
                      f"colisiones={resumen['colisiones']}  "
                      f"({hechas}/{total})")

    csv_destino = salida / "experimentos.csv"
    with csv_destino.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.DictWriter(fh, fieldnames=COLUMNAS)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({k: fila.get(k, "") for k in COLUMNAS})

    duracion = time.perf_counter() - inicio
    print(f"\nListo: {len(filas)} corridas en {duracion:.1f} s")
    print(f"CSV: {csv_destino}")
    if not args.sin_frames:
        print(f"Fotogramas: {carpeta_runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
