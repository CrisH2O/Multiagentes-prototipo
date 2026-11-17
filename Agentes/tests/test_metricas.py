"""Tests de metricas.py: colisiones, revisitas y costos."""
import pytest

from metricas import (
    colisiones,
    costo_total,
    resumir_corrida,
    revisitas,
    siembra,
)


def frame(tick, posiciones, sembradas=()):
    """Construye un fotograma mínimo con la forma que usa metricas."""
    return {
        "tick": tick,
        "remaining_cells": 0,
        "planted_cells": [{"x": x, "y": y} for x, y in sembradas],
        "agents": [{"id": i, "pos": list(pos)} for i, pos in enumerate(posiciones)],
    }


# Colisiones
def test_una_celda_por_agente_no_es_colision():
    frames = [frame(1, [(0, 0), (0, 1)]), frame(2, [(1, 0), (0, 2)])]
    assert colisiones(frames) == 0


def test_dos_agentes_en_la_misma_celda_es_colision():
    frames = [frame(1, [(0, 0), (0, 1)]), frame(2, [(3, 3), (3, 3)])]
    assert colisiones(frames) == 1


def test_el_primer_frame_se_ignora_por_el_deposito_compartido():
    """Todos arrancan apilados en el depósito: no es un choque."""
    frames = [frame(1, [(0, 0), (0, 0)]), frame(2, [(1, 0), (0, 1)])]
    assert colisiones(frames) == 0
    assert colisiones(frames, ignorar_primer_frame=False) == 1


def test_varias_colisiones_se_acumulan():
    frames = [
        frame(1, [(0, 0), (0, 1)]),
        frame(2, [(2, 2), (2, 2)]),
        frame(3, [(2, 2), (2, 2)]),
    ]
    assert colisiones(frames) == 2


# Revisitas
def test_ida_y_vuelta_cuenta_como_revisita():
    frames = [
        frame(1, [(0, 0)]),
        frame(2, [(1, 0)]),
        frame(3, [(2, 0)]),
        frame(4, [(1, 0)]),   # vuelve
        frame(5, [(0, 0)]),   # vuelve otra vez
    ]
    r = revisitas(frames)
    assert r["pasos_efectivos"] == 5
    assert r["pasos_repetidos"] == 2


def test_quedarse_quieto_no_cuenta_como_paso():
    frames = [frame(1, [(0, 0)]), frame(2, [(0, 0)]), frame(3, [(0, 0)])]
    r = revisitas(frames)
    assert r["pasos_efectivos"] == 1
    assert r["pasos_repetidos"] == 0
    assert r["ratio_repeticion"] == 0.0


def test_camino_sin_repetir_no_pierde_pasos():
    frames = [frame(i, [(i, 0)]) for i in range(5)]
    r = revisitas(frames)
    assert r["pasos_repetidos"] == 0
    assert r["ratio_repeticion"] == 0.0


def test_max_visitas_a_una_celda():
    frames = [frame(1, [(0, 0)]), frame(2, [(1, 0)]), frame(3, [(1, 0)]),
              frame(4, [(0, 0)]), frame(5, [(1, 0)])]
    assert revisitas(frames)["max_visitas_celda"] >= 2


# Siembra
def test_siembra_detecta_celdas_distintas():
    frames = [frame(1, [(0, 0)], [(1, 1)]), frame(2, [(0, 0)], [(2, 2)])]
    r = siembra(frames)
    assert r["celdas_sembradas"] == 2
    assert r["siembras_dobles"] == 0


def test_siembra_doble_se_detecta():
    frames = [frame(1, [(0, 0)], [(1, 1)]), frame(2, [(0, 0)], [(1, 1)])]
    assert siembra(frames)["siembras_dobles"] == 1


# Costos
def test_costo_total_suma_combustible_salarios_y_semillas():
    modelo = {
        "total_fuel_consumed": 10.0,
        "driver_wage_cost": 100.0,
        "seed_cost": 50.0,
    }
    # 10 L * 24 + 100 + 50 = 390
    assert costo_total(modelo, precio_litro=24.0) == 390.0


def test_costo_total_usa_precio_por_litro():
    modelo = {"total_fuel_consumed": 10.0, "driver_wage_cost": 0, "seed_cost": 0}
    assert costo_total(modelo, precio_litro=20.0) == 200.0
    assert costo_total(modelo, precio_litro=40.0) == 400.0


# Resumen integrado
def test_resumir_corrida_mezcla_modelo_y_derivadas():
    frames = [frame(1, [(0, 0)], [(1, 1)]), frame(2, [(1, 0)], [(2, 2)])]
    modelo = {
        "total_ticks": 2,
        "total_steps": 3,
        "total_fuel_consumed": 2.0,
        "driver_wage_cost": 5.0,
        "seed_cost": 1.0,
        "remaining_cells": 0,
    }
    r = resumir_corrida(frames, modelo, precio_litro=10.0)
    assert r["ticks"] == 2
    assert r["colisiones"] == 0
    assert r["cobertura"] == 1.0
    assert r["costo_total"] == 2.0 * 10 + 5.0 + 1.0


def test_resumir_corrida_sin_fotogramas_falla():
    with pytest.raises(ValueError):
        resumir_corrida([], {"total_ticks": 0})


def test_cobertura_parcial_se_calcula_bien():
    frames = [frame(1, [(0, 0)], [(1, 1), (2, 2)])]
    modelo = {"total_ticks": 1, "total_steps": 1, "total_fuel_consumed": 0,
              "driver_wage_cost": 0, "seed_cost": 0, "remaining_cells": 2}
    r = resumir_corrida(frames, modelo)
    assert r["cobertura"] == 0.5
