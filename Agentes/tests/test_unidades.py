"""Tests de unidades.py: equivalencias entre el modelo y el campo."""
import pytest

import unidades


# Geometría
def test_area_de_celda_corresponde_al_ancho_de_la_sembradora():
    # 12 surcos x 0.76 m = 9.12 m ~ 9 m
    assert unidades.LADO_CELDA_M == pytest.approx(9.0)
    assert unidades.AREA_CELDA_M2 == pytest.approx(81.0)


def test_una_hectarea_son_aproximadamente_123_celdas():
    assert unidades.CELDAS_POR_HECTAREA == pytest.approx(123.456, abs=0.01)


def test_hectareas_de_un_campo_20x20():
    assert unidades.hectareas(400) == pytest.approx(3.24)


def test_hectareas_de_una_celda():
    assert unidades.hectareas(1) == pytest.approx(0.0081)


def test_123_celdas_son_una_hectarea():
    assert unidades.hectareas(123) == pytest.approx(1.0, abs=0.01)


# Semilla
def test_un_costal_cubre_una_hectarea():
    """60,000 semillas por costal y 60,000 semillas/ha."""
    assert unidades.costales_por_hectarea() == pytest.approx(1.0)


def test_semillas_por_celda_en_maiz():
    assert unidades.semillas_por_celda() == pytest.approx(486, abs=1)


def test_mas_densidad_implica_mas_costales():
    pocos = unidades.costales_por_hectarea(45_000)
    muchos = unidades.costales_por_hectarea(80_000)
    assert pocos < muchos


def test_costales_de_un_campo_completo():
    # 364 celdas sembrables ~ 2.95 ha ~ 2.95 costales
    assert unidades.costales_de_celdas(364) == pytest.approx(2.95, abs=0.02)


# Combustible
def test_consumo_a_6_km_h_es_el_menor():
    assert unidades.litros_por_hectarea(6.0) == pytest.approx(8.6)


def test_consumo_a_9_km_h_es_el_mayor():
    assert unidades.litros_por_hectarea(9.0) == pytest.approx(10.77)


def test_consumo_interpola_entre_velocidades():
    medio = unidades.litros_por_hectarea(7.5)
    assert 8.6 < medio < 10.77


def test_costo_de_combustible_por_hectarea():
    # 8.6 L/ha * 27 MXN/L
    assert unidades.costo_combustible_por_hectarea() == pytest.approx(232.2, abs=0.1)


def test_precio_mas_alto_encarece():
    caro = unidades.costo_combustible_por_hectarea(precio_litro=28.0)
    barato = unidades.costo_combustible_por_hectarea(precio_litro=25.39)
    assert caro > barato


# Tiempo
def test_un_tick_equivale_a_5_4_segundos():
    assert unidades.segundos_por_tick(6.0) == pytest.approx(5.4, abs=0.01)


def test_horas_de_ticks():
    assert unidades.horas_de_ticks(3600 / 5.4) == pytest.approx(1.0, abs=0.01)


def test_rendimiento_de_campo_cerca_de_4_6_ha_por_hora():
    assert unidades.hectareas_por_hora() == pytest.approx(4.59, abs=0.05)


# Preset
def test_preset_realista_del_campo_20x20():
    preset = unidades.preset_realista(20)
    assert preset["hectareas"] == pytest.approx(3.24)
    assert preset["max_seeds_por_costal"] == 123
    assert 25 < preset["litros_totales"] < 40
    assert 600 < preset["costo_combustible"] < 1000
