"""Tests de escenarios.py: reproducibilidad, conectividad y validaciones."""
import numpy as np
import pytest

from escenarios import (
    TERRENOS,
    construir_payload,
    generar_elevacion,
    generar_obstaculos,
)


# Reproducibilidad
def test_elevacion_es_reproducible_con_la_misma_semilla():
    a = generar_elevacion("colinas", 12, semilla=7)
    b = generar_elevacion("colinas", 12, semilla=7)
    assert np.array_equal(a, b)


def test_elevacion_cambia_con_otra_semilla():
    a = generar_elevacion("colinas", 12, semilla=1)
    b = generar_elevacion("colinas", 12, semilla=2)
    assert not np.array_equal(a, b)


def test_elevacion_esta_normalizada():
    for terreno in TERRENOS:
        elev = generar_elevacion(terreno, 10, semilla=3)
        assert elev.shape == (10, 10)
        assert elev.min() >= 0.0 and elev.max() <= 1.0


def test_montanoso_tiene_mas_desnivel_que_plano():
    plano = generar_elevacion("plano", 20, semilla=1)
    montanoso = generar_elevacion("montanoso", 20, semilla=1)
    assert (montanoso.max() - montanoso.min()) > (plano.max() - plano.min())


def test_terreno_desconocido_falla():
    with pytest.raises(ValueError, match="Terreno desconocido"):
        generar_elevacion("volcanico", 10)


# Obstáculos
def test_obstaculos_respetan_la_cantidad_y_el_deposito():
    mapa = generar_obstaculos(15, 20, semilla=4)
    assert mapa.sum() == 20
    assert mapa[0, 0] == 0


def test_obstaculos_son_reproducibles():
    a = generar_obstaculos(15, 20, semilla=9)
    b = generar_obstaculos(15, 20, semilla=9)
    assert np.array_equal(a, b)


def test_el_terreno_siempre_queda_conectado():
    """Ninguna disposición puede encerrar el depósito ni formar islas."""
    from escenarios import _celdas_alcanzables

    for cantidad in (0, 10, 40, 80):
        for semilla in range(1, 8):
            mapa = generar_obstaculos(16, cantidad, semilla=semilla)
            libres = 16 * 16 - 1 - cantidad
            # +1 porque el conteo incluye la celda del depósito
            assert _celdas_alcanzables(mapa, (0, 0)) == libres + 1


def test_obstaculos_negativos_o_excesivos_fallan():
    with pytest.raises(ValueError):
        generar_obstaculos(10, -1, semilla=1)
    with pytest.raises(ValueError):
        generar_obstaculos(10, 100, semilla=1)


# Payload
def test_payload_tiene_las_claves_que_espera_el_modelo():
    payload = construir_payload("colinas", n=8, n_agentes=2, obstaculos=5, semilla=1)
    assert payload["grid_size"] == [8, 8]
    assert payload["difficulty"] == 2
    assert payload["n_agents"] == 2
    assert len(payload["elevation_map"]) == 8
    assert len(payload["obstacle_map"]) == 8
    assert payload["depot_pos"] == [0, 0]


def test_payload_es_reproducible():
    a = construir_payload("montanoso", n=10, semilla=5)
    b = construir_payload("montanoso", n=10, semilla=5)
    assert a["elevation_map"] == b["elevation_map"]
    assert a["obstacle_map"] == b["obstacle_map"]
