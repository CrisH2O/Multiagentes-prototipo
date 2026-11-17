"""
Modelo de AgentPy

Uso rápido:
    modelo = ModeloSiembra({"ancho": 20, "alto": 12, "seed": 1})
    resultados = modelo.run()
    resultados.reporters            # tabla con las métricas finales
"""
from __future__ import annotations

import agentpy as ap

from agents import Nodriza, Sembradora, zigzag
from campo import Campo, TipoCelda, generar_mapa

# Valores por defecto
PARAMETROS_BASE = {
    # Campo
    "ancho": 20,
    "alto": 12,
    "n_obstaculos": 2,
    "semilla_mapa": 0, # semilla aleatoria, no confundir con grano
    # Sembradora
    "ticks_por_vuelta": 3,
    "radio_percepcion": 2,
    "capacidad_tolva_kg": 50.0,
    "semilla_por_celda_kg": 2.0,
    "combustible_por_paso_L": 0.5,
    # Nodriza
    "aviso_anticipado": True,
    "descarga_kg_por_tick": 10.0,
    "combustible_nodriza_por_paso_L": 0.3,
    # Obstaculos
    "n_imprevistos": 0,
    "tick_max_imprevisto": 100, # aparecen en un tick al azar entre 1 y este valor
    # Simulación
    "steps": 5000, #Tope de seguridad
}


class ModeloSiembra(ap.Model):

    def param(self, nombre):
        # Devolver parametro o parametro base
        return self.p.get(nombre, PARAMETROS_BASE[nombre])

    def setup(self):
        mapa = generar_mapa(self.param("ancho"), self.param("alto"), self.param("n_obstaculos"),
                            semilla=self.param("semilla_mapa"))
        self.campo = Campo(mapa)

        self.sembradora = Sembradora(
            "sembradora_1", self.campo, (1, 1), zigzag(mapa),
            radio_percepcion=self.param("radio_percepcion"),
            capacidad_tolva_kg=self.param("capacidad_tolva_kg"),
            semilla_por_celda_kg=self.param("semilla_por_celda_kg"),
            ticks_por_vuelta=self.param("ticks_por_vuelta"),
            aviso_anticipado=self.param("aviso_anticipado"),
            combustible_por_paso_L=self.param("combustible_por_paso_L"),
        )

        # La nodriza empieza en la cabecera, junto a la sembradora
        self.nodriza = Nodriza(
            "nodriza_1", self.campo, (0, 1),
            descarga_kg_por_tick=self.param("descarga_kg_por_tick"),
            combustible_por_paso_L=self.param("combustible_nodriza_por_paso_L"),
        )
        self.agentes = [self.sembradora, self.nodriza]

        # Segun el valor dado spawnea obstaculos aleatorios imprevistos
        sembrables = mapa.celdas_de_tipo(TipoCelda.SEMBRABLE)
        n = min(self.param("n_imprevistos"), len(sembrables))
        celdas = self.random.sample(sembrables, n)
        self.imprevistos = {}                       # {tick: [celdas]}
        for celda in celdas:
            tick = self.random.randint(1, self.param("tick_max_imprevisto"))
            self.imprevistos.setdefault(tick, []).append(celda)
        self.imprevistos_ocurridos = 0

    def step(self):
        # Llegan los mensajes enviados en el tick anterior
        self.campo.correo.entregar(self.t)

        # Eventos imprevistos de este tick
        for celda in self.imprevistos.get(self.t, []):
            if self.campo.ocupante(celda) is None:
                self.campo.bloquear(celda)
                self.imprevistos_ocurridos += 1

        # Paso de cada agente
        for agente in self.agentes:
            agente.step()

        # La sembradora concluye la simulación
        if self.sembradora.estado == Sembradora.TERMINADA:
            self.stop()

    def update(self):
        # Datos para graficas
        s = self.sembradora
        self.record("cobertura", self.campo.cobertura())
        self.record("semilla_kg", s.semilla_kg)
        self.record("kg_entregados_nodriza", self.nodriza.kg_entregados)
        self.record("combustible_usado_L", s.combustible_usado_L + self.nodriza.combustible_usado_L)
        self.record("estado", s.estado)
        self.record("estado_nodriza", self.nodriza.estado)

    def end(self):
        s = self.sembradora
        self.report("motivo_fin", s.motivo_fin or "tope_de_ticks")
        self.report("ticks", self.t)
        self.report("cobertura", self.campo.cobertura())
        self.report("sembradas", s.sembradas)
        self.report("descartadas", len(s.descartadas))
        self.report("doble_siembra", self.campo.celdas_doble_siembra())
        self.report("pasos", s.pasos)
        self.report("pasos_sobre_sembrado", s.pasos_sobre_sembrado)
        self.report("vueltas", s.vueltas)
        self.report("ticks_en_vueltas", s.ticks_en_vueltas)
        self.report("recargas", s.recargas)
        self.report("avisos_anticipados", s.avisos_anticipados)
        self.report("ticks_recargando", s.ticks_recargando)
        self.report("ticks_esperando_nodriza", s.ticks_esperando)
        self.report("semilla_usada_kg", s.semilla_usada_kg)
        self.report("combustible_sembradora_L", s.combustible_usado_L)
        self.report("combustible_nodriza_L", self.nodriza.combustible_usado_L)
        self.report("pasos_nodriza", self.nodriza.pasos)
        self.report("mensajes", len(self.campo.correo.historial))
        self.report("imprevistos", self.imprevistos_ocurridos)
