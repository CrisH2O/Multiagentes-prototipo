"""Agentes: clase base Vehiculo y la Sembradora

Acciones del agente en cada paso:
1. Percibir: leer las celdas cercanas y actualizar su mapa
2. Decidir: si seguir la ruta establecida o alterarla
3. Actuar: avanzar por la ruta y marcar la celda como sembrada si llegó a su objetivo

Acciones de actuar: (campo.mover, campo.marcar_sembrada).
"""
from __future__ import annotations

from collections import deque

from campo import Campo, Celda, TipoCelda, generar_mapa


# Planeacion
# Recorrer en zigzag todas las celdas
def zigzag(mapa) -> list[Celda]:
    """Recorrer en zigzag todas las celdas como serpiente"""
    plan = []
    for y in range(mapa.alto):
        xs = range(mapa.ancho) if y % 2 == 1 else range(mapa.ancho - 1, -1, -1)
        plan += [(x, y) for x in xs if mapa.es_sembrable((x, y))]
    return plan


def ruta_bfs(mapa, inicio: Celda, meta: Celda) -> list[Celda] | None:
    """Recibe de entrada dos celdas y busca el camino mas corto entre ellas
    ignorando obstaculos"""
    if inicio == meta:
        return []
    if not mapa.es_transitable(meta):
        return None
    padre = {inicio: None} # ¿Que camino me lleva a cada celda?
    cola = deque([inicio])
    while cola:
        actual = cola.popleft()
        for vecino in mapa.vecinos(actual):
            if vecino in padre or not mapa.es_transitable(vecino):
                continue
            padre[vecino] = actual
            if vecino == meta: # Reconstruir el camino hacia atras
                ruta = [meta]
                while padre[ruta[-1]] != inicio:
                    ruta.append(padre[ruta[-1]])
                return ruta[::-1]
            cola.append(vecino)
    return None


# Agentes
class Vehiculo:
    """Todavia no se si agregaremos el seed tender, por si acaso hice una clase general de vehiculo"""

    def __init__(self, nombre: str, campo: Campo, posicion: Celda, radio_percepcion: int = 2):
        if radio_percepcion < 1:
            raise ValueError("radio_percepcion debe ser >= 1 (para ver la celda de enfrente)")
        self.nombre = nombre
        self.campo = campo
        self.posicion = posicion
        self.radio_percepcion = radio_percepcion
        self.mapa = campo.mapa.copia() #Realiza una copia del mapa inicial
        self.ruta: list[Celda] = [] # Celdas pendientes
        self.pasos = 0
        campo.colocar(nombre, posicion)

    def step(self) -> None:
        """Un tick: percibir -> decidir -> actuar."""
        self.percibir()
        self.decidir()
        self.actuar()

    def percibir(self) -> list[Celda]:
        """Mira alrededor y corrige su mapa. Devuelve las celdas que le sorprendieron."""
        sorpresas = []
        for celda, tipo in self.campo.sensar(self.posicion, self.radio_percepcion).items():
            if self.mapa.actualizar(celda, tipo):
                sorpresas.append(celda)
        return sorpresas

    def decidir(self) -> None:
        raise NotImplementedError("Cada vehículo define cómo decide")

    def actuar(self) -> None:
        raise NotImplementedError("Cada vehículo define cómo actúa")

    def avanzar(self) -> bool:
        """Da un paso por la ruta. Devuelve False si no pudo"""
        if not self.ruta:
            return False
        siguiente = self.ruta[0]
        if self.campo.ocupante(siguiente) is not None:
            return False                    # otro vehículo está ahí: esperar
        self.campo.mover(self.nombre, self.posicion, siguiente)
        self.posicion = siguiente
        self.ruta.pop(0)
        self.pasos += 1
        return True


class Sembradora(Vehiculo):
    SEMBRANDO = "SEMBRANDO"
    TERMINADA = "TERMINADA"

    def __init__(self, nombre: str, campo: Campo, posicion: Celda, plan: list[Celda], radio_percepcion: int = 2):
        super().__init__(nombre, campo, posicion, radio_percepcion)
        self.plan = list(plan) #celdas pendientes de sembrar, en orden
        self.estado = self.SEMBRANDO
        self.sembradas = 0
        self.descartadas: list[Celda] = []  # celdas que no pudo sembrar (bloqueadas o inalcanzables)

    # Decisiones
    def decidir(self) -> None:
        # Quitar la casilla bloqueada
        while self.plan and (not self.mapa.es_sembrable(self.plan[0]) or self.campo.esta_sembrada(self.plan[0])):
            self.descartadas.append(self.plan.pop(0))
            self.ruta = []

        if not self.plan:
            self.estado = self.TERMINADA
            self.ruta = []
            return

        # Usar BFS para encontrar la ruta hacia el siguiente objetivo
        objetivo = self.plan[0]
        ruta_invalida = bool(self.ruta) and (self.ruta[-1] != objetivo or not self.mapa.es_transitable(self.ruta[0]))
        if not self.ruta or ruta_invalida:
            self.ruta = ruta_bfs(self.mapa, self.posicion, objetivo) or []
            if not self.ruta:               # no hay camino: descartar este objetivo y seguir con el siguiente
                self.descartadas.append(self.plan.pop(0))

    # Acciones
    def actuar(self) -> None:
        if self.estado == self.TERMINADA:
            return
        if self.avanzar() and self.plan and self.posicion == self.plan[0]:
            self.campo.marcar_sembrada(self.posicion)
            self.plan.pop(0)
            self.sembradas += 1


# Demo
def correr(campo: Campo, agentes: list[Vehiculo], max_ticks: int = 5000, eventos: dict[int, callable] | None = None) -> int:
    """Avanza la simulación tick por tick. `eventos` = {tick: función} para imprevistos."""
    eventos = eventos or {}
    for tick in range(1, max_ticks + 1):
        if tick in eventos:
            eventos[tick]()
        for agente in agentes:
            agente.step()
        if all(getattr(a, "estado", None) == Sembradora.TERMINADA for a in agentes):
            return tick
    return max_ticks


if __name__ == "__main__":
    mapa = generar_mapa(ancho=14, alto=8, n_obstaculos=1, semilla=2)
    campo = Campo(mapa)
    sembradora = Sembradora("sembradora_1", campo, posicion=(0, 1), plan=zigzag(mapa))

    # Insertar obstaculo a media ejecucion
    ticks = correr(campo, [sembradora], eventos={15: lambda: campo.bloquear((8, 3))})

    print(campo)
    print(f"\nTicks: {ticks}   Pasos: {sembradora.pasos}   Sembradas: {sembradora.sembradas}")
    print(f"Cobertura: {campo.cobertura():.1%}   Doble siembra: {campo.celdas_doble_siembra()}")
    print(f"Celdas descartadas: {sembradora.descartadas}")
    print("(# = sembrada, X = obstáculo, S = sin sembrar)")
