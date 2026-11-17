"""
Para importar todos los codigos simultaneamente
Probablemnte sea eliminado
"""
from __future__ import annotations

from campo import Campo, generar_mapa
from nodriza import Nodriza
from planeacion import manhattan, ruta_bfs, zigzag
from sembradora import Sembradora
from vehiculo import Vehiculo

__all__ = ["Vehiculo", "Sembradora", "Nodriza", "zigzag", "ruta_bfs", "manhattan", "correr"]


def correr(campo: Campo, agentes: list[Vehiculo], max_ticks: int = 5000, eventos: dict[int, callable] | None = None) -> int:
    eventos = eventos or {}
    sembradoras = [a for a in agentes if isinstance(a, Sembradora)]
    for tick in range(1, max_ticks + 1):
        campo.correo.entregar(tick)
        if tick in eventos:
            eventos[tick]()
        for agente in agentes:
            agente.step()
        if all(s.estado == Sembradora.TERMINADA for s in sembradoras):
            return tick
    return max_ticks


if __name__ == "__main__":
    mapa = generar_mapa(ancho=14, alto=8, n_obstaculos=1, semilla=2)
    campo = Campo(mapa)
    # La sembradora empieza dentro del área de siembra; la nodriza, en la cabecera
    sembradora = Sembradora("sembradora_1", campo, posicion=(1, 1), plan=zigzag(mapa), ticks_por_vuelta=2)
    nodriza = Nodriza("nodriza_1", campo, posicion=(0, 1))

    # Insertar obstaculo a media ejecucion
    ticks = correr(campo, [sembradora, nodriza], eventos={15: lambda: campo.bloquear((8, 3))})

    s, n = sembradora, nodriza
    print(campo)
    print(f"\nTicks: {ticks}   Pasos: {s.pasos}   Sembradas: {s.sembradas}   Fin: {s.motivo_fin}")
    print(f"Cobertura: {campo.cobertura():.1%}   Doble siembra: {campo.celdas_doble_siembra()}")
    print(f"Recargas: {s.recargas}   Ticks recargando: {s.ticks_recargando}   Ticks esperando a la nodriza: {s.ticks_esperando}")
    print(f"Semilla usada: {s.semilla_usada_kg:.0f} kg   Combustible sembradora: {s.combustible_usado_L:.1f} L")
    print(f"Nodriza: {n.pasos} pasos, {n.kg_entregados:.0f} kg entregados")
    print(f"Mensajes enviados: {len(campo.correo.historial)}   Pasos sobre sembrado: {s.pasos_sobre_sembrado}")
    print(f"Celdas descartadas: {s.descartadas}")
    print("(# = sembrada, X = obstáculo, S = sin sembrar, @ = vehículo)")
