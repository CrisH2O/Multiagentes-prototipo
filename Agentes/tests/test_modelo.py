"""Tests de agentesPrueba.py: el modelo que usa Unity.

Cubre lo que antes no tenía ninguna prueba: calibración de unidades,
reproducibilidad, planificador zigzag y reglas de recarga.
"""
import pytest

import agentesPrueba
import escenarios
import unidades


def payload(**kwargs):
    base = dict(terreno="plano", n=10, n_agentes=2, obstaculos=5, semilla=1)
    base.update(kwargs)
    return escenarios.construir_payload(**base)


# --- Calibración ---------------------------------------------------------
def test_un_tanque_es_un_costal():
    p = payload(costales=1.0)
    assert p["max_seeds"] == 123          # 1 costal = 1 ha = 123 celdas


def test_medio_costal_es_la_mitad():
    # 0.5 x 123.46 = 61.7 -> 62 celdas
    assert payload(costales=0.5)["max_seeds"] == 62


def test_dos_costales_duplican_el_tanque():
    # 2 x 123.46 = 246.9 -> 247 celdas
    assert payload(costales=2.0)["max_seeds"] == 247


def test_el_combustible_esta_en_litros_por_celda():
    p = payload()
    assert p["fuel_por_paso"] == pytest.approx(unidades.LITROS_POR_CELDA)


def test_salario_es_por_hora_no_por_tick():
    p = payload()
    # $50/h con ticks de 5.4 s => ~$0.075 por tick
    assert p["wage_per_tick"] == pytest.approx(0.075, abs=0.001)


def test_costo_de_semilla_por_celda():
    p = payload()
    # $1,500 por costal de 123 celdas
    assert p["cost_per_seed"] == pytest.approx(12.15, abs=0.01)


def test_costales_invalidos_fallan():
    with pytest.raises(ValueError):
        payload(costales=0)
    with pytest.raises(ValueError):
        payload(estrategia="inventada")


# --- Reproducibilidad ----------------------------------------------------
def test_misma_semilla_misma_corrida():
    a = agentesPrueba.run_simulation(payload(semilla=3))
    b = agentesPrueba.run_simulation(payload(semilla=3))
    assert a["metrics"] == b["metrics"]
    assert a["frames"] == b["frames"]


def test_semilla_distinta_cambia_el_mapa():
    a = agentesPrueba.run_simulation(payload(semilla=1))
    b = agentesPrueba.run_simulation(payload(semilla=2))
    assert a["frames"] != b["frames"]


# --- Estrategias ---------------------------------------------------------
def test_el_plan_zigzag_cubre_cada_celda_una_vez():
    p = payload(n=8, n_agentes=1)
    modelo = agentesPrueba.FarmingModel({
        "grid_size": (8, 8),
        "difficulty": 1,
        "max_fuel": p["max_fuel"],
        "max_seeds": p["max_seeds"],
        "wage_per_tick": p["wage_per_tick"],
        "cost_per_seed": p["cost_per_seed"],
        "fuel_por_paso": p["fuel_por_paso"],
        "estrategia": "greedy",
        "elevation_map": p["elevation_map"],
        "obstacle_map": p["obstacle_map"],
        "depot_pos": (0, 0),
        "n_agents": 1,
    })
    plan = agentesPrueba.plan_zigzag(modelo)
    assert len(plan) == len(set(plan))              # sin repetir
    assert len(plan) == modelo.remaining_to_seed    # todas las sembrables


def test_el_plan_se_reparte_entre_los_tractores():
    planes = agentesPrueba.repartir_plan(list(range(10)), 3)
    assert sum(len(p) for p in planes) == 10
    assert len(planes) == 3


@pytest.mark.parametrize("estrategia", ["greedy", "zigzag"])
def test_ambas_estrategias_cubren_todo(estrategia):
    r = agentesPrueba.run_simulation(payload(estrategia=estrategia))
    assert r["metrics"]["remaining_cells"] == 0


def test_greedy_no_es_mas_lento_que_zigzag():
    """El planificador debe ganarle a la ruta base (20x20, 3 tractores)."""
    base = dict(terreno="colinas", n=20, n_agentes=3, obstaculos=35, semilla=1)
    t_greedy = agentesPrueba.run_simulation(payload(**base))["metrics"]["total_ticks"]
    t_zigzag = agentesPrueba.run_simulation(
        payload(estrategia="zigzag", **base)
    )["metrics"]["total_ticks"]
    assert t_greedy < t_zigzag


# --- Reglas del modelo ---------------------------------------------------
def test_sin_siembras_dobles():
    r = agentesPrueba.run_simulation(payload())
    sembradas = [
        (c["x"], c["y"])
        for f in r["frames"] for c in f["planted_cells"]
    ]
    assert len(sembradas) == len(set(sembradas))


def test_el_combustible_nunca_es_negativo():
    r = agentesPrueba.run_simulation(payload())
    assert all(a["fuel"] >= 0 for f in r["frames"] for a in f["agents"])


def test_los_agentes_terminan():
    r = agentesPrueba.run_simulation(payload())
    ultimo = r["frames"][-1]["agents"]
    assert all(a["state"] == "TERMINADO" for a in ultimo)


def test_consumo_por_hectarea_es_del_orden_real():
    """El modelo calibrado debe quedar en el orden de 8-18 L/ha."""
    r = agentesPrueba.run_simulation(
        payload(terreno="colinas", n=20, n_agentes=3, obstaculos=35, semilla=1)
    )
    hectareas = unidades.hectareas(400)
    litros_ha = r["metrics"]["total_fuel_consumed"] / hectareas
    assert 8.0 <= litros_ha <= 18.0, f"{litros_ha:.1f} L/ha fuera de rango"
