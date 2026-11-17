"""
Nodriza / Seed tender
Se encuentra con la sembradora y la recarga a orden de esta
Por ahora se asume semilla ilimitada
"""
from __future__ import annotations

from campo import Campo, Celda
from planeacion import manhattan
from vehiculo import Vehiculo


class Nodriza(Vehiculo):
    # Estados
    ESPERANDO = "ESPERANDO"
    YENDO_AL_PUNTO = "YENDO_AL_PUNTO"
    EN_PUNTO = "EN_PUNTO"
    DESCARGANDO = "DESCARGANDO"

    def __init__(self, nombre: str, campo: Campo, posicion: Celda, descarga_kg_por_tick: float = 10.0,
                 radio_percepcion: int = 1, combustible_por_paso_L: float = 0.3):
        if descarga_kg_por_tick <= 0:
            raise ValueError("descarga_kg_por_tick debe ser > 0")
        super().__init__(nombre, campo, posicion, radio_percepcion, combustible_por_paso_L)
        self.descarga_kg_por_tick = descarga_kg_por_tick
        self.estado = self.ESPERANDO
        self.pedido: dict | None = None
        self.kg_entregados = 0.0

    # Solo puede ir por los bordes
    def puede_pasar(self, celda: Celda) -> bool:
        return self.mapa.es_cabecera(celda)

    def elegir_punto(self, cerca_de: Celda) -> Celda:
        junto = [c for c in self.mapa.vecinos(cerca_de) if self.mapa.es_cabecera(c)]
        return min(junto, key=lambda c: (manhattan(c, self.posicion), c))

    # Decisiones
    def leer_mensajes(self) -> None:
        for m in self.buzon:
            # Se puede sobreescribir una solicitud
            if m.tipo == "SOLICITUD" and (self.pedido is None or self.pedido["cliente"] == m.emisor):
                punto = self.elegir_punto(tuple(m.contenido["cerca_de"]))
                self.pedido = {"id": m.contenido["id"], "cliente": m.emisor, "punto": punto, "cliente_listo": None}
                self.enviar(m.emisor, "ACEPTA", id=m.contenido["id"], punto=punto)
                self.estado = self.YENDO_AL_PUNTO
                self.ruta = []
            elif m.tipo == "LISTA" and self.pedido is not None and m.contenido["id"] == self.pedido["id"]:
                self.pedido["cliente_listo"] = tuple(m.contenido["pos"])

    def decidir(self) -> None:
        self.leer_mensajes()
        if self.estado == self.YENDO_AL_PUNTO:
            punto = self.pedido["punto"]
            if self.posicion == punto:
                self.estado = self.EN_PUNTO
                self.ruta = []
            elif not self.ruta_vigente(punto):
                self.ruta = self.ruta_hacia(punto) or []
        if self.estado == self.EN_PUNTO:
            listo = self.pedido["cliente_listo"]
            if listo is not None and manhattan(listo, self.posicion) == 1:
                self.estado = self.DESCARGANDO

    # Acciones
    def actuar(self) -> None:
        if self.estado == self.YENDO_AL_PUNTO:
            self.avanzar()
        elif self.estado == self.DESCARGANDO:
            cliente = self.campo.vehiculos[self.pedido["cliente"]]
            aceptado = cliente.recibir_semilla(self.descarga_kg_por_tick)
            self.kg_entregados += aceptado
            if aceptado < self.descarga_kg_por_tick: # Se terminó la recarga
                self.enviar(self.pedido["cliente"], "COMPLETA", id=self.pedido["id"])
                self.pedido = None
                self.estado = self.ESPERANDO
