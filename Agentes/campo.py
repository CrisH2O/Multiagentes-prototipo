"""
Celda: una posición (x, y).

Mapa: Es lo que cada agente cree que hay en una celda

Campo: Es el mapa real que se puede consultar con los sensores
"""
from __future__ import annotations

import random
from enum import IntEnum

import numpy as np

from mensajes import Correo

# Cada celda es una tupla
Celda = tuple[int, int]
DIRECCIONES = [(1, 0), (-1, 0), (0, 1), (0, -1)]


class TipoCelda(IntEnum):
    FUERA = 0 # Celdas invalidas
    CABECERA = 1 # Orillas transitables
    SEMBRABLE = 2 # Se puede sembrar
    OBSTACULO = 3 # No se puede pasar ni sembrar


# Símbolo de cada tipo para dibujar el mapa como texto
SIMBOLOS = {
    TipoCelda.FUERA: ".",
    TipoCelda.CABECERA: "C",
    TipoCelda.SEMBRABLE: "S",
    TipoCelda.OBSTACULO: "X",
}


class Mapa:
    """Qué tipo es cada celda. Es la información que conoce un agente."""

    def __init__(self, tipos, tamano_celda_m: float = 9.0):
        # Copia los tipos del campo
        self.tipos = np.array(tipos, dtype=np.int8)
        self.tamano_celda_m = tamano_celda_m

    @property
    def alto(self) -> int:
        return self.tipos.shape[0]   # número de filas

    @property
    def ancho(self) -> int:
        return self.tipos.shape[1]   # número de columnas

    # Consultas
    def en_limites(self, celda: Celda) -> bool:
        x, y = celda
        return 0 <= x < self.ancho and 0 <= y < self.alto

    def tipo(self, celda: Celda) -> TipoCelda:
        x, y = celda
        return TipoCelda(self.tipos[y, x])   # ojo: la matriz se indexa [fila, columna]

    def es_transitable(self, celda: Celda) -> bool:
        return self.en_limites(celda) and self.tipo(celda) in (TipoCelda.CABECERA, TipoCelda.SEMBRABLE)

    def es_sembrable(self, celda: Celda) -> bool:
        return self.en_limites(celda) and self.tipo(celda) == TipoCelda.SEMBRABLE

    def es_cabecera(self, celda: Celda) -> bool:
        return self.en_limites(celda) and self.tipo(celda) == TipoCelda.CABECERA

    def vecinos(self, celda: Celda) -> list[Celda]:
        """Celdas adyacentes que están dentro del mapa."""
        x, y = celda
        candidatos = [(x + dx, y + dy) for dx, dy in DIRECCIONES]
        return [c for c in candidatos if self.en_limites(c)]

    def celdas_de_tipo(self, tipo: TipoCelda) -> list[Celda]:
        filas, columnas = np.nonzero(self.tipos == tipo)
        return [(int(x), int(y)) for y, x in zip(filas, columnas)]

    def contar(self, tipo: TipoCelda) -> int:
        return int(np.count_nonzero(self.tipos == tipo))

    def actualizar(self, celda: Celda, tipo: TipoCelda) -> bool:
        # Actualiza alguna celda y devuelve True si cambió de tipo
        x, y = celda
        if self.tipos[y, x] == tipo:
            return False
        self.tipos[y, x] = tipo
        return True

    # Utilidades
    def copia(self) -> "Mapa":
        return Mapa(self.tipos, self.tamano_celda_m)

    def __str__(self) -> str:
        filas = []
        for y in range(self.alto):
            filas.append("".join(SIMBOLOS[self.tipo((x, y))] for x in range(self.ancho)))
        return "\n".join(filas)

    @classmethod
    def desde_texto(cls, texto: str, tamano_celda_m: float = 9.0) -> "Mapa":
        # Crea un mapa de texto para visualizar el terreno
        simbolo_a_tipo = {s: t for t, s in SIMBOLOS.items()}
        lineas = [linea.strip() for linea in texto.strip().splitlines()]
        if len({len(linea) for linea in lineas}) != 1:
            raise ValueError("Todas las filas del mapa deben tener el mismo largo")
        tipos = []
        for linea in lineas:
            fila = []
            for s in linea:
                if s not in simbolo_a_tipo:
                    raise ValueError(f"Símbolo desconocido en el mapa: '{s}'")
                fila.append(simbolo_a_tipo[s])
            tipos.append(fila)
        return cls(tipos, tamano_celda_m)


class Campo:
    """Mapa verdadero"""

    def __init__(self, mapa: Mapa):
        self.mapa = mapa.copia() # Para asegurar inmutabilidad
        self.sembrables_iniciales = mapa.contar(TipoCelda.SEMBRABLE)
        # Cuantas veces se sembro
        self.sembradas = np.zeros((self.mapa.alto, self.mapa.ancho), dtype=int)
        # Qué agente está en cada celda: {(x, y): "sembradora_1"}
        self.ocupacion: dict[Celda, str] = {}
        # Vehículos en el campo por nombre
        self.vehiculos: dict = {}
        # Canal de comunicación entre los agentes
        self.correo = Correo()

    # Siembra
    def marcar_sembrada(self, celda: Celda) -> None:
        if not self.mapa.es_sembrable(celda):
            raise ValueError(f"La celda {celda} no es sembrable")
        x, y = celda
        self.sembradas[y, x] += 1

    def esta_sembrada(self, celda: Celda) -> bool:
        x, y = celda
        return self.sembradas[y, x] > 0

    def cobertura(self) -> float:
        # Fraccion de celdas sembrables que han sido sembradas al menos una vez
        hechas = np.count_nonzero(self.sembradas > 0)
        return hechas / self.sembrables_iniciales if self.sembrables_iniciales else 1.0

    def celdas_doble_siembra(self) -> int:
        return int(np.count_nonzero(self.sembradas > 1))

    # Ocupacion
    def ocupante(self, celda: Celda) -> str | None:
        return self.ocupacion.get(celda)

    def colocar(self, agente: str, celda: Celda) -> None:
        # Pone a un agente en su celda inicial.
        if not self.mapa.es_transitable(celda):
            raise ValueError(f"{agente} no puede colocarse en {celda}: no es transitable")
        if self.ocupante(celda) is not None:
            raise ValueError(f"{agente} no puede colocarse en {celda}: ocupada por {self.ocupante(celda)}")
        self.ocupacion[celda] = agente

    def mover(self, agente: str, desde: Celda, hacia: Celda) -> None:
        """Mueve a un agente a una celda vecina. Falla si el movimiento es inválido."""
        if self.ocupante(desde) != agente:
            raise ValueError(f"{agente} no está en {desde}")
        if hacia not in self.mapa.vecinos(desde):
            raise ValueError(f"{hacia} no es vecina de {desde}")
        if not self.mapa.es_transitable(hacia):
            raise ValueError(f"{hacia} no es transitable")
        if self.ocupante(hacia) is not None:
            raise ValueError(f"{hacia} está ocupada por {self.ocupante(hacia)}")
        del self.ocupacion[desde]
        self.ocupacion[hacia] = agente

    # Sensor
    def sensar(self, centro: Celda, radio: int) -> dict[Celda, TipoCelda]:
        """Lo que puede ver un sensor"""
        cx, cy = centro
        vistas = {}
        for y in range(cy - radio, cy + radio + 1):
            for x in range(cx - radio, cx + radio + 1):
                if abs(x - cx) + abs(y - cy) <= radio and self.mapa.en_limites((x, y)):
                    vistas[(x, y)] = self.mapa.tipo((x, y))
        return vistas

    # Eventos
    def bloquear(self, celda: Celda) -> None:
        if self.ocupante(celda) is not None:
            raise ValueError(f"No se puede bloquear {celda}: hay un agente ahí")
        x, y = celda
        self.mapa.tipos[y, x] = TipoCelda.OBSTACULO

    def __str__(self) -> str:
        """Mapa real con '#' en celdas sembradas y '@' donde hay un agente."""
        filas = []
        for y in range(self.mapa.alto):
            fila = ""
            for x in range(self.mapa.ancho):
                if (x, y) in self.ocupacion:
                    fila += "@"
                elif self.sembradas[y, x] > 0:
                    fila += "#"
                else:
                    fila += SIMBOLOS[self.mapa.tipo((x, y))]
            filas.append(fila)
        return "\n".join(filas)


def generar_mapa(ancho: int = 20, alto: int = 12, n_obstaculos: int = 2, tam_max_obstaculo: int = 2,
                 semilla: int | None = None, tamano_celda_m: float = 9.0) -> Mapa:
    """Genera un campo rectangular: borde de cabecera, interior sembrable y obstáculos."""
    if ancho < 5 or alto < 5:
        raise ValueError("El campo debe medir al menos 5x5 celdas")
    rng = random.Random(semilla)

    # 1. Todo sembrable, con un anillo de cabecera en el borde
    tipos = np.full((alto, ancho), TipoCelda.SEMBRABLE, dtype=np.int8)
    tipos[0, :] = tipos[-1, :] = TipoCelda.CABECERA
    tipos[:, 0] = tipos[:, -1] = TipoCelda.CABECERA

    # 2. Obstáculos rectangulares en el interior
    colocados, intentos = 0, 0
    while colocados < n_obstaculos and intentos < 500:
        intentos += 1
        w = rng.randint(1, tam_max_obstaculo)
        h = rng.randint(1, tam_max_obstaculo)
        # Columnas 0 y ancho-1 son cabecera; 1 y ancho-2 quedan como margen sembrable
        x_max, y_max = ancho - 2 - w, alto - 2 - h
        if x_max < 2 or y_max < 2:
            continue                         # este tamaño no cabe; probar otro
        x0 = rng.randint(2, x_max)
        y0 = rng.randint(2, y_max)
        # El rectángulo y una celda de margen alrededor deben estar libres (sembrables)
        zona = tipos[y0 - 1:y0 + h + 1, x0 - 1:x0 + w + 1]
        if np.all(zona == TipoCelda.SEMBRABLE):
            tipos[y0:y0 + h, x0:x0 + w] = TipoCelda.OBSTACULO
            colocados += 1

    if colocados < n_obstaculos:
        raise ValueError(f"Solo cupieron {colocados} de {n_obstaculos} obstáculos; use un campo más grande")
    return Mapa(tipos, tamano_celda_m)