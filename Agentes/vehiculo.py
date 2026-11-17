"""
Clase base de vehiculos

Acciones en cada paso:
1. Percibir: leer sus mensajes y las celdas cercanas, y actualizar su mapa
2. Decidir: si seguir la ruta establecida o alterarla
3. Actuar: avanzar por la ruta y marcar la celda como sembrada si llegó a su objetivo

Acciones de actuar: (campo.mover, campo.marcar_sembrada, pasar semilla).

Reglas:
- Ningun agente se mete en el carril del otro,
- Se comunican mediante mensajes
"""
from __future__ import annotations

from campo import Campo, Celda
from mensajes import Mensaje
from planeacion import ruta_bfs


class Vehiculo:

    def __init__(self, nombre: str, campo: Campo, posicion: Celda, radio_percepcion: int = 2,
                 combustible_por_paso_L: float = 0.5):
        if radio_percepcion < 1:
            raise ValueError("radio invalido")
        self.nombre = nombre
        self.campo = campo
        self.posicion = posicion
        self.radio_percepcion = radio_percepcion
        self.mapa = campo.mapa.copia() #Realiza una copia del mapa inicial
        if not self.puede_pasar(posicion):
            raise ValueError(f"{nombre} no puede empezar en {posicion}: está fuera de su carril")
        self.ruta: list[Celda] = [] # Celdas pendientes
        self.pasos = 0
        self.buzon: list[Mensaje] = [] # mensajes recibidos en este tick
        #Por ahora el combustible es ilimitado
        self.combustible_por_paso_L = combustible_por_paso_L
        self.combustible_usado_L = 0.0
        self.pasos_sobre_sembrado = 0 #Para metricas
        campo.colocar(nombre, posicion)
        campo.vehiculos[nombre] = self
        campo.correo.registrar(nombre)

    def step(self) -> None:
        self.percibir()
        self.decidir()
        self.actuar()

    def percibir(self) -> list[Celda]:
        """Lee sus mensajes, mira alrededor y corrige su mapa. Devuelve las celdas que le sorprendieron."""
        self.buzon = self.campo.correo.recibir(self.nombre)
        sorpresas = []
        for celda, tipo in self.campo.sensar(self.posicion, self.radio_percepcion).items():
            if self.mapa.actualizar(celda, tipo):
                sorpresas.append(celda)
        return sorpresas

    def decidir(self) -> None:
        raise NotImplementedError("No definida para la clase base")

    def actuar(self) -> None:
        raise NotImplementedError("No definida para la clase base")

    def enviar(self, receptor: str, tipo: str, **contenido) -> None:
        self.campo.correo.enviar(Mensaje(self.campo.correo.tick, self.nombre, receptor, tipo, contenido))

    # Rutas
    def puede_pasar(self, celda: Celda) -> bool:
        raise NotImplementedError("No definida para la clase base")

    def celdas_a_evitar(self) -> set[Celda]:
        return set()

    def ruta_hacia(self, meta: Celda) -> list[Celda] | None:
        # Intentar evitar las celdas invalidas
        for evitar in (self.celdas_a_evitar(), set()):
            ruta = ruta_bfs(self.mapa, self.posicion, meta, evitar=evitar, puede_pasar=self.puede_pasar)
            if ruta is not None:
                return ruta
        return None

    def ruta_vigente(self, meta: Celda) -> bool:
        return bool(self.ruta) and self.ruta[-1] == meta and self.puede_pasar(self.ruta[0])

    def avanzar(self) -> bool:
        if not self.ruta:
            return False
        siguiente = self.ruta[0]
        if self.campo.ocupante(siguiente) is not None:
            return False
        if self.campo.esta_sembrada(siguiente):
            self.pasos_sobre_sembrado += 1
        self.campo.mover(self.nombre, self.posicion, siguiente)
        self.posicion = siguiente
        self.ruta.pop(0)
        self.pasos += 1
        self.combustible_usado_L += self.combustible_por_paso_L
        return True
