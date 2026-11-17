"""Métricas derivadas de una corrida de simulación.

El modelo (`agentesPrueba.FarmingModel`) ya reporta cobertura, ticks,
combustible y costos. Aquí se calculan las métricas que la rúbrica pide y
que el modelo no expone directamente:

* **Colisiones**: fotogramas en los que dos o más tractores ocupan la misma celda.
* **Revisitas**: cuántas veces un tractor vuelve a entrar a una celda que ya
  había recorrido (equivale a "pasar más de una vez por el mismo tramo").
* **Eficiencia**: cobertura, siembras dobles y costo total monetizado.

Todas las funciones trabajan sobre la lista ``frames`` que devuelve
``run_simulation``, así que no tocan la lógica de los agentes.
"""
from __future__ import annotations

from collections import Counter


def _trayectorias(frames: list[dict]) -> dict[int, list[tuple[int, int]]]:
    """Agrupa la secuencia de posiciones de cada agente."""
    recorridos: dict[int, list[tuple[int, int]]] = {}
    for frame in frames:
        for agente in frame.get("agents", []):
            recorridos.setdefault(agente["id"], []).append(tuple(agente["pos"]))
    return recorridos


def _entradas(camino: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Quita las repeticiones consecutivas: quedarse quieto no es "entrar"."""
    if not camino:
        return []
    entradas = [camino[0]]
    for anterior, actual in zip(camino, camino[1:]):
        if actual != anterior:
            entradas.append(actual)
    return entradas


def colisiones(frames: list[dict], ignorar_primer_frame: bool = True) -> int:
    """Fotogramas con dos o más tractores en la misma celda.

    El primer fotograma se ignora por defecto porque todos los tractores
    arrancan apilados en el depósito: es una decisión de diseño, no un choque.
    """
    inicio = 1 if ignorar_primer_frame else 0
    total = 0
    for frame in frames[inicio:]:
        posiciones = [tuple(a["pos"]) for a in frame.get("agents", [])]
        if len(posiciones) != len(set(posiciones)):
            total += 1
    return total


def revisitas(frames: list[dict]) -> dict[str, float]:
    """Cuánto se repite el recorrido de cada tractor.

    Devuelve ``pasos_repetidos`` (entradas a celdas ya visitadas), el total de
    celdas distintas y el ratio de repetición sobre los pasos efectivos.
    """
    total_entradas = 0
    total_repetidas = 0
    max_visitas = 0

    for camino in _trayectorias(frames).values():
        entradas = _entradas(camino)
        conteo = Counter(entradas)
        total_entradas += len(entradas)
        total_repetidas += sum(v - 1 for v in conteo.values() if v > 1)
        if conteo:
            max_visitas = max(max_visitas, max(conteo.values()))

    ratio = (total_repetidas / total_entradas) if total_entradas else 0.0
    return {
        "pasos_repetidos": total_repetidas,
        "pasos_efectivos": total_entradas,
        "ratio_repeticion": round(ratio, 4),
        "max_visitas_celda": max_visitas,
    }


def siembra(frames: list[dict]) -> dict[str, int]:
    """Celdas sembradas distintas y siembras dobles (deben ser 0)."""
    sembradas: set[tuple[int, int]] = set()
    dobles = 0
    for frame in frames:
        for celda in frame.get("planted_cells", []):
            posicion = (celda["x"], celda["y"])
            if posicion in sembradas:
                dobles += 1
            sembradas.add(posicion)
    return {"celdas_sembradas": len(sembradas), "siembras_dobles": dobles}


def costo_total(metricas: dict, precio_litro: float = 24.0) -> float:
    """Costo monetizado completo: combustible + salarios + semillas.

    El modelo reporta litros de combustible pero no los monetiza, así que el
    precio por litro entra como parámetro del análisis.
    """
    return round(
        metricas.get("total_fuel_consumed", 0.0) * precio_litro
        + metricas.get("driver_wage_cost", 0.0)
        + metricas.get("seed_cost", 0.0),
        2,
    )


def resumir_corrida(frames: list[dict], metricas_modelo: dict,
                    precio_litro: float = 24.0) -> dict:
    """Junta las métricas del modelo con las derivadas en un solo diccionario."""
    if not frames:
        raise ValueError("La corrida no produjo fotogramas")

    resumen = {
        "ticks": int(metricas_modelo["total_ticks"]),
        "pasos": int(metricas_modelo["total_steps"]),
        "combustible_l": float(metricas_modelo["total_fuel_consumed"]),
        "costo_salarios": float(metricas_modelo["driver_wage_cost"]),
        "costo_semillas": float(metricas_modelo["seed_cost"]),
        "celdas_restantes": int(metricas_modelo["remaining_cells"]),
        "colisiones": colisiones(frames),
    }
    resumen.update(revisitas(frames))
    resumen.update(siembra(frames))
    resumen["costo_total"] = costo_total(metricas_modelo, precio_litro)
    resumen["precio_litro"] = precio_litro

    total_sembrable = resumen["celdas_sembradas"] + resumen["celdas_restantes"]
    resumen["cobertura"] = round(
        resumen["celdas_sembradas"] / total_sembrable if total_sembrable else 1.0, 4
    )
    return resumen


if __name__ == "__main__":
    # Autoprueba con una corrida real
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import escenarios
    import agentesPrueba

    payload = escenarios.construir_payload("colinas", n=12, n_agentes=3, semilla=1)
    respuesta = agentesPrueba.run_simulation(payload)
    print(resumir_corrida(respuesta["frames"], respuesta["metrics"]))
