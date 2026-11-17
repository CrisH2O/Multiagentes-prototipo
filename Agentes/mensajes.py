"""
Todos los agentes se comunican mediante mensajes, no leyendo estados
"""
from __future__ import annotations

from dataclasses import dataclass, field

TIPOS = {"SOLICITUD", "ACEPTA", "LISTA", "COMPLETA"}


@dataclass(frozen=True)
class Mensaje:
    tick: int
    emisor: str
    receptor: str
    tipo: str
    contenido: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.tipo not in TIPOS:
            raise ValueError(f"Tipo de mensaje invalido")


class Correo:
    def __init__(self):
        self.tick = 0
        self.buzones: dict[str, list[Mensaje]] = {} # mensajes ya entregados, por receptor
        self.en_camino: list[Mensaje] = [] # enviados en este tick, se entregan en el siguiente
        self.historial: list[Mensaje] = [] # todo lo enviado

    def registrar(self, nombre: str) -> None:
        self.buzones.setdefault(nombre, [])

    def enviar(self, mensaje: Mensaje) -> None:
        if mensaje.receptor not in self.buzones:
            raise ValueError(f"Agente invalido")
        self.en_camino.append(mensaje)
        self.historial.append(mensaje)

    def entregar(self, tick: int) -> None:
        # Al inicio de un tick se entregan los mensajes enviados el pasado
        self.tick = tick
        for mensaje in self.en_camino:
            self.buzones[mensaje.receptor].append(mensaje)
        self.en_camino = []

    def recibir(self, nombre: str) -> list[Mensaje]:
        #Se vacia el buzon y recibe los mensajes
        mensajes = self.buzones[nombre]
        self.buzones[nombre] = []
        return mensajes
