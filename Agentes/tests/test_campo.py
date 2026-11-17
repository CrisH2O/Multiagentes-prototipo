"""Tests de campo.py.  Correr desde Agentes/ con:  pytest -q"""
import pytest

from campo import Campo, Mapa, TipoCelda, generar_mapa

MAPA_CHICO = """
CCCCCC
CSSSSC
CSXSSC
CCCCCC
"""


# Mapa
def test_mapa_desde_texto_y_de_regreso():
    mapa = Mapa.desde_texto(MAPA_CHICO)
    assert (mapa.ancho, mapa.alto) == (6, 4)
    assert str(mapa) == MAPA_CHICO.strip()


def test_tipos_de_celda():
    mapa = Mapa.desde_texto(MAPA_CHICO)
    assert mapa.tipo((0, 0)) == TipoCelda.CABECERA
    assert mapa.tipo((2, 2)) == TipoCelda.OBSTACULO
    assert mapa.es_sembrable((1, 1))
    assert not mapa.es_transitable((2, 2))     # obstáculo
    assert not mapa.es_transitable((10, 10))   # fuera del mapa


def test_vecinos_en_esquina_y_en_centro():
    mapa = Mapa.desde_texto(MAPA_CHICO)
    assert sorted(mapa.vecinos((0, 0))) == [(0, 1), (1, 0)]
    assert len(mapa.vecinos((2, 1))) == 4


def test_desde_texto_rechaza_errores():
    with pytest.raises(ValueError):
        Mapa.desde_texto("CCC\nCC")    # filas de distinto largo
    with pytest.raises(ValueError):
        Mapa.desde_texto("CCC\nCZC")   # símbolo desconocido


def test_copia_es_independiente():
    original = Mapa.desde_texto(MAPA_CHICO)
    copia = original.copia()
    copia.tipos[1, 1] = TipoCelda.OBSTACULO
    assert original.es_sembrable((1, 1))


# generar_mapa
def test_generar_mapa_es_reproducible():
    a = generar_mapa(semilla=3)
    b = generar_mapa(semilla=3)
    assert str(a) == str(b)


def test_generar_mapa_tiene_borde_de_cabecera_y_obstaculos():
    mapa = generar_mapa(ancho=20, alto=12, n_obstaculos=3, semilla=0)
    for x in range(mapa.ancho):
        assert mapa.es_cabecera((x, 0)) and mapa.es_cabecera((x, mapa.alto - 1))
    for y in range(mapa.alto):
        assert mapa.es_cabecera((0, y)) and mapa.es_cabecera((mapa.ancho - 1, y))
    assert mapa.contar(TipoCelda.OBSTACULO) >= 3


def test_obstaculos_no_tocan_la_cabecera():
    mapa = generar_mapa(n_obstaculos=4, semilla=7)
    for celda in mapa.celdas_de_tipo(TipoCelda.OBSTACULO):
        assert not any(mapa.es_cabecera(v) for v in mapa.vecinos(celda))


def test_generar_mapa_rechaza_campo_muy_chico():
    with pytest.raises(ValueError):
        generar_mapa(ancho=3, alto=3)


# Campo
def test_cobertura_y_doble_siembra():
    campo = Campo(Mapa.desde_texto(MAPA_CHICO))   # 7 celdas sembrables
    assert campo.cobertura() == 0.0
    campo.marcar_sembrada((1, 1))
    assert campo.cobertura() == pytest.approx(1 / 7)
    campo.marcar_sembrada((1, 1))
    assert campo.celdas_doble_siembra() == 1


def test_no_se_siembra_cabecera_ni_obstaculo():
    campo = Campo(Mapa.desde_texto(MAPA_CHICO))
    with pytest.raises(ValueError):
        campo.marcar_sembrada((0, 0))
    with pytest.raises(ValueError):
        campo.marcar_sembrada((2, 2))


def test_mover_respeta_reglas():
    campo = Campo(Mapa.desde_texto(MAPA_CHICO))
    campo.colocar("sembradora", (1, 1))
    campo.colocar("nodriza", (0, 1))
    campo.mover("sembradora", (1, 1), (2, 1))
    assert campo.ocupante((2, 1)) == "sembradora"
    with pytest.raises(ValueError):
        campo.mover("sembradora", (2, 1), (2, 2))   # obstáculo
    with pytest.raises(ValueError):
        campo.mover("sembradora", (2, 1), (4, 1))   # no es vecina
    campo.mover("sembradora", (2, 1), (1, 1))
    with pytest.raises(ValueError):
        campo.mover("sembradora", (1, 1), (0, 1))   # ocupada por la nodriza


def test_bloquear_cambia_la_verdad_pero_no_la_creencia():
    """La idea central: el mundo real cambia, el mapa del agente no."""
    mapa_inicial = Mapa.desde_texto(MAPA_CHICO)
    campo = Campo(mapa_inicial)
    mapa_de_la_sembradora = mapa_inicial.copia()

    campo.bloquear((3, 1))

    assert not campo.mapa.es_transitable((3, 1))       # en el mundo real hay un obstáculo
    assert mapa_de_la_sembradora.es_sembrable((3, 1))  # la sembradora todavía no lo sabe


def test_sensar_devuelve_el_rombo_de_celdas_y_el_tipo_real():
    campo = Campo(Mapa.desde_texto(MAPA_CHICO))
    vistas = campo.sensar((2, 1), radio=1)
    assert set(vistas) == {(2, 1), (1, 1), (3, 1), (2, 0), (2, 2)}   # centro + 4 vecinos
    assert vistas[(2, 2)] == TipoCelda.OBSTACULO
    assert (0, 0) in campo.sensar((0, 0), radio=2) and (-1, 0) not in campo.sensar((0, 0), radio=2)  # no sale del mapa


def test_actualizar_avisa_si_hubo_cambio():
    mapa = Mapa.desde_texto(MAPA_CHICO)
    assert mapa.actualizar((1, 1), TipoCelda.OBSTACULO) is True
    assert mapa.actualizar((1, 1), TipoCelda.OBSTACULO) is False     # ya lo sabía
