"""Tests de agents.py"""
import pytest

from agents import Sembradora, Vehiculo, correr, ruta_bfs, zigzag
from campo import Campo, Mapa, TipoCelda, generar_mapa

MAPA_CHICO = """
CCCCCC
CSSSSC
CSXSSC
CSSSSC
CCCCCC
"""


def nueva_sembradora(texto=MAPA_CHICO, posicion=(0, 1), **kw):
    mapa = Mapa.desde_texto(texto)
    campo = Campo(mapa)
    return campo, Sembradora("s1", campo, posicion, zigzag(mapa), **kw)


# zigzag
def test_zigzag_es_serpentina_y_salta_obstaculos():
    plan = zigzag(Mapa.desde_texto(MAPA_CHICO))
    assert plan[:4] == [(1, 1), (2, 1), (3, 1), (4, 1)]      # fila 1: izquierda a derecha
    assert plan[4:7] == [(4, 2), (3, 2), (1, 2)]             # fila 2: derecha a izquierda, sin (2, 2)
    assert plan[7:] == [(1, 3), (2, 3), (3, 3), (4, 3)]      # fila 3: otra vez a la derecha


def test_zigzag_cubre_cada_celda_sembrable_una_vez():
    mapa = generar_mapa(semilla=4)
    plan = zigzag(mapa)
    assert len(plan) == len(set(plan)) == mapa.contar(TipoCelda.SEMBRABLE)


# ruta_bfs
def test_bfs_encuentra_el_camino_mas_corto_rodeando_el_obstaculo():
    mapa = Mapa.desde_texto("CCCCC\nCSXSC\nCSXSC\nCSSSC\nCCCCC")
    ruta = ruta_bfs(mapa, (1, 1), (3, 1))
    # Lo más corto es subir a la cabecera (fila 0), cruzar y bajar: 4 pasos
    assert ruta == [(1, 0), (2, 0), (3, 0), (3, 1)]


def test_bfs_rodea_por_dentro_si_la_cabecera_esta_cortada():
    mapa = Mapa.desde_texto("CCCCC\nCSXSC\nCSXSC\nCSSSC\nCCCCC")
    mapa.actualizar((2, 0), TipoCelda.OBSTACULO)             # se corta la cabecera de arriba
    ruta = ruta_bfs(mapa, (1, 1), (3, 1))
    assert len(ruta) == 6                                    # baja 2, cruza 2, sube 2
    assert all(mapa.es_transitable(c) for c in ruta)


def test_bfs_sin_camino_devuelve_none():
    mapa = Mapa.desde_texto("CCCCC\nCSXSC\nCCCCC")
    mapa.actualizar((2, 0), TipoCelda.OBSTACULO)
    mapa.actualizar((2, 2), TipoCelda.OBSTACULO)             # ahora (2, 1) separa izquierda de derecha
    assert ruta_bfs(mapa, (1, 1), (3, 1)) is None


def test_bfs_misma_celda_y_meta_no_transitable():
    mapa = Mapa.desde_texto(MAPA_CHICO)
    assert ruta_bfs(mapa, (1, 1), (1, 1)) == []
    assert ruta_bfs(mapa, (1, 1), (2, 2)) is None            # la meta es un obstáculo


# percepción
def test_percibe_solo_dentro_del_radio():
    campo, s = nueva_sembradora(posicion=(3, 1), radio_percepcion=2)
    campo.bloquear((4, 3))     # distancia 1 + 2 = 3: fuera del radio
    campo.bloquear((4, 2))     # distancia 1 + 1 = 2: dentro del radio
    assert s.percibir() == [(4, 2)]
    assert not s.mapa.es_transitable((4, 2))                 # ya lo sabe
    assert s.mapa.es_sembrable((4, 3))                       # de este otro no se ha enterado


def test_radio_invalido():
    campo = Campo(Mapa.desde_texto(MAPA_CHICO))
    with pytest.raises(ValueError):
        Vehiculo("v", campo, (0, 1), radio_percepcion=0)


# simulación completa
def test_cubre_todo_sin_doble_siembra_en_campo_generado():
    for semilla in range(10):
        mapa = generar_mapa(ancho=16, alto=10, n_obstaculos=3, semilla=semilla)
        campo = Campo(mapa)
        s = Sembradora("s1", campo, (0, 1), zigzag(mapa))
        correr(campo, [s])
        assert s.estado == Sembradora.TERMINADA
        assert campo.cobertura() == 1.0
        assert campo.celdas_doble_siembra() == 0
        assert s.sembradas == mapa.contar(TipoCelda.SEMBRABLE)


def test_obstaculo_imprevisto_se_descarta_y_se_sigue():
    mapa = generar_mapa(ancho=14, alto=8, n_obstaculos=1, semilla=2)
    campo = Campo(mapa)
    s = Sembradora("s1", campo, (0, 1), zigzag(mapa))
    correr(campo, [s], eventos={15: lambda: campo.bloquear((8, 3))})
    assert s.estado == Sembradora.TERMINADA
    assert (8, 3) in s.descartadas
    assert campo.celdas_doble_siembra() == 0
    assert campo.cobertura() == pytest.approx(1 - 1 / mapa.contar(TipoCelda.SEMBRABLE))


def test_obstaculo_en_la_ruta_obliga_a_replanear():
    # Objetivo lejano en línea recta; en el tick 2 aparece un obstáculo justo en medio del camino
    mapa = Mapa.desde_texto("CCCCCCCC\nCSSSSSSC\nCSSSSSSC\nCCCCCCCC")
    campo = Campo(mapa)
    s = Sembradora("s1", campo, (0, 1), plan=[(5, 1)])
    correr(campo, [s], eventos={2: lambda: campo.bloquear((3, 1))})
    assert s.estado == Sembradora.TERMINADA
    assert s.posicion == (5, 1) and campo.esta_sembrada((5, 1))   # llegó rodeando
    assert s.pasos > 5                                            # dio más pasos que en línea recta


def test_celda_inalcanzable_se_descarta_sin_trabarse():
    mapa = Mapa.desde_texto("CCCCCC\nCSSSSC\nCSSSSC\nCSSSSC\nCCCCCC")
    campo = Campo(mapa)
    s = Sembradora("s1", campo, (0, 1), zigzag(mapa))
    # Antes de empezar, se encierra la celda (3, 2) con obstáculos; sigue siendo "sembrable" en el mapa de la sembradora
    for celda in [(2, 2), (4, 2), (3, 1), (3, 3)]:
        campo.bloquear(celda)
    correr(campo, [s])
    assert s.estado == Sembradora.TERMINADA                 # no se quedó atorada
    assert (3, 2) in s.descartadas                          # la celda encerrada se descartó
    assert campo.celdas_doble_siembra() == 0


def test_espera_si_otro_vehiculo_bloquea_el_paso():
    campo, s = nueva_sembradora()
    campo.colocar("otro", (1, 1))                           # justo en la primera celda del plan
    s.step()
    assert s.posicion == (0, 1)                             # esperó, no se movió
    del campo.ocupacion[(1, 1)]                             # el otro se va
    s.step()
    assert s.posicion == (1, 1)


def test_cobertura_no_cuenta_como_hecha_una_celda_bloqueada():
    campo = Campo(Mapa.desde_texto(MAPA_CHICO))             # 11 sembrables
    campo.bloquear((4, 3))
    for celda in [(1, 1), (2, 1)]:
        campo.marcar_sembrada(celda)
    assert campo.cobertura() == pytest.approx(2 / 11)
