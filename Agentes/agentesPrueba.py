from __future__ import annotations

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
from urllib.parse import parse_qs, urlparse

import escenarios
import unidades


PENDING_UNITY_CONFIG = None
CONFIG_LOCK = threading.Lock()
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def plan_zigzag(model):
    """Recorrido en serpiente de todas las celdas sembrables.

    Es la ruta base contra la que se compara la planificación: cubre cada celda
    una sola vez, fila por fila, alternando el sentido.
    """
    plan = []
    for y in range(model.height):
        columnas = range(model.width) if y % 2 else range(model.width - 1, -1, -1)
        for x in columnas:
            if model.seeded[x][y] == 0:
                plan.append((x, y))
    return plan


def repartir_plan(plan, n_agentes):
    """Divide el recorrido en bloques contiguos, uno por tractor."""
    if n_agentes < 1:
        raise ValueError("Se requiere al menos un tractor")
    tamano = -(-len(plan) // n_agentes)  # división hacia arriba
    return [plan[i * tamano:(i + 1) * tamano] for i in range(n_agentes)]


class TractorAgent:
    def __init__(self, model, identifier, depot):
        self.model = model
        self.id = identifier
        self.position = depot
        self.depot_pos = depot
        self.max_fuel = model.max_fuel
        self.fuel = model.max_fuel
        self.max_seeds = model.max_seeds
        self.seeds = model.max_seeds
        self.total_fuel_used = 0.0
        self.seeds_planted = 0
        self.steps_taken = 0
        self.state = "SEMBRANDO"
        self.target_pos = None
        # Solo se usa con estrategia "zigzag"
        planes = getattr(model, "planes_zigzag", None)
        self.plan = planes[identifier] if planes and identifier < len(planes) else []
        self.plan_idx = 0

    @property
    def pos(self):
        return self.position

    def move_cost(self, origin, destination):
        difference = (
            self.model.elevation[destination[0]][destination[1]]
            - self.model.elevation[origin[0]][origin[1]]
        )
        if difference > 0:
            cost = 1.0 + difference * 0.5 * self.model.difficulty
        else:
            cost = max(0.5, 1.0 + difference * 0.2)
        # Convierte el costo abstracto a litros reales por paso
        return round(cost * self.model.fuel_por_paso, 4)

    def find_next_step(self, condition):
        occupied = {
            agent.pos
            for agent in self.model.agents
            if agent is not self
            and agent.pos != self.depot_pos
            and agent.state != "TERMINADO"
        }
        queue = deque([(self.pos, [])])
        visited = {self.pos}
        candidates = []

        while queue:
            current, path = queue.popleft()
            if current != self.pos and condition(current):
                candidates.append((current, path))

            for dx, dy in DIRECTIONS:
                neighbor = (current[0] + dx, current[1] + dy)
                if not self.model.inside(neighbor) or neighbor in visited:
                    continue
                if self.model.is_obstacle(neighbor) or neighbor in occupied:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

        if not candidates:
            self.target_pos = None
            return None

        other_positions = [
            agent.pos
            for agent in self.model.agents
            if agent is not self and agent.state != "TERMINADO"
        ]

        def score(candidate):
            position, path = candidate
            spacing = min(
                (
                    abs(position[0] - other[0]) +
                    abs(position[1] - other[1])
                    for other in other_positions
                ),
                default=8,
            )
            return len(path) - min(spacing, 8) * 0.25

        self.target_pos, path = min(candidates, key=score)
        return path[0] if path else None

    def step(self):
        if self.model.estrategia == "zigzag":
            self._step_zigzag()
        else:
            self._step_greedy()

    def _step_zigzag(self):
        """Sigue el recorrido en serpiente asignado."""
        if self.state == "TERMINADO":
            return
        if self.model.remaining_to_seed <= 0:
            self.state = "TERMINADO"
            return

        distance = (
            abs(self.pos[0] - self.depot_pos[0]) +
            abs(self.pos[1] - self.depot_pos[1])
        )
        safe_return_fuel = (
            (distance + 2) * (1.0 + 0.5 * self.model.difficulty)
            * self.model.fuel_por_paso
        )

        if self.seeds <= 0 or self.fuel <= safe_return_fuel:
            self.state = "RECARGANDO"

        if self.state == "RECARGANDO":
            if self.pos == self.depot_pos:
                self.fuel = self.max_fuel
                self.seeds = self.max_seeds
                self.state = "SEMBRANDO"
                return
            next_pos = self.find_next_step(lambda p: p == self.depot_pos)
            if next_pos is not None:
                self.execute_move(next_pos)
            return

        # Sembrar donde está parado, si toca
        if self.model.seeded[self.pos[0]][self.pos[1]] == 0:
            self.plant(self.pos)
            if self.model.remaining_to_seed <= 0:
                self.state = "TERMINADO"
                return

        # Saltar celdas ya resueltas
        while (self.plan_idx < len(self.plan)
               and self.model.seeded[self.plan[self.plan_idx][0]][self.plan[self.plan_idx][1]]):
            self.plan_idx += 1

        if self.plan_idx >= len(self.plan):
            # Se acabó el plan pero faltan celdas: terminar con el greedy
            if self.model.remaining_to_seed > 0:
                self._step_greedy()
                return
            self.state = "TERMINADO"
            return

        objetivo = self.plan[self.plan_idx]
        self.target_pos = objetivo
        next_pos = self.find_next_step(lambda p: p == objetivo)
        if next_pos is None:
            self.plan_idx += 1          # inalcanzable: descartar y seguir
            self.target_pos = None
            return
        self.execute_move(next_pos)

    def _step_greedy(self):
        if self.state == "TERMINADO":
            return
        if self.model.remaining_to_seed <= 0:
            self.state = "TERMINADO"
            return

        distance = (
            abs(self.pos[0] - self.depot_pos[0]) +
            abs(self.pos[1] - self.depot_pos[1])
        )
        safe_return_fuel = (
            (distance + 2) * (1.0 + 0.5 * self.model.difficulty)
            * self.model.fuel_por_paso
        )

        if self.seeds <= 0 or self.fuel <= safe_return_fuel:
            self.state = "RECARGANDO"

        if self.state == "RECARGANDO":
            if self.pos == self.depot_pos:
                self.fuel = self.max_fuel
                self.seeds = self.max_seeds
                self.state = "SEMBRANDO"
                return
            next_pos = self.find_next_step(lambda position: position == self.depot_pos)
            if next_pos is not None:
                self.execute_move(next_pos)
            return

        if self.model.seeded[self.pos[0]][self.pos[1]] == 0:
            self.plant(self.pos)
            if self.model.remaining_to_seed <= 0:
                self.state = "TERMINADO"
                return

        if self.seeds <= 0 or self.fuel <= safe_return_fuel:
            return

        claimed = {
            agent.target_pos
            for agent in self.model.agents
            if agent is not self
            and agent.state == "SEMBRANDO"
            and agent.target_pos is not None
        }
        next_pos = self.find_next_step(
            lambda position: (
                self.model.seeded[position[0]][position[1]] == 0
                and position not in claimed
            )
        )
        if next_pos is None:
            next_pos = self.find_next_step(
                lambda position: self.model.seeded[position[0]][position[1]] == 0
            )
        if next_pos is not None:
            self.execute_move(next_pos)
            if self.model.seeded[self.pos[0]][self.pos[1]] == 0:
                self.plant(self.pos)
                if self.model.remaining_to_seed <= 0:
                    self.state = "TERMINADO"

    def execute_move(self, destination):
        cost = self.move_cost(self.pos, destination)
        self.fuel = round(self.fuel - cost, 3)
        self.total_fuel_used = round(self.total_fuel_used + cost, 3)
        self.steps_taken += 1
        self.position = destination

    def plant(self, position):
        if self.model.seeded[position[0]][position[1]]:
            return
        self.model.seeded[position[0]][position[1]] = 1
        self.seeds -= 1
        self.seeds_planted += 1
        self.model.remaining_to_seed -= 1
        self.model.current_tick_planted.append(
            {"x": position[0], "y": position[1]}
        )


class FarmingModel:
    def __init__(self, parameters):
        self.width, self.height = parameters["grid_size"]
        self.grid_size = (self.width, self.height)
        self.difficulty = parameters["difficulty"]
        self.max_fuel = float(parameters["max_fuel"])
        self.max_seeds = int(parameters["max_seeds"])
        self.wage_per_tick = float(parameters["wage_per_tick"])
        self.cost_per_seed = float(parameters["cost_per_seed"])
        # Litros que consume avanzar una celda (calibrado: 8.6 L/ha / 123 celdas)
        self.fuel_por_paso = float(parameters.get("fuel_por_paso", 1.0))
        self.estrategia = parameters.get("estrategia", "greedy")
        self.elevation = parameters["elevation_map"]
        self.obstacles = parameters["obstacle_map"]
        self.depot = tuple(parameters["depot_pos"])
        self.obstacles[self.depot[0]][self.depot[1]] = 0
        self.seeded = [
            [1 if self.is_obstacle((x, y)) else 0 for y in range(self.height)]
            for x in range(self.width)
        ]
        self.seeded[self.depot[0]][self.depot[1]] = 1
        reachable = self.reachable(self.depot)
        for x in range(self.width):
            for y in range(self.height):
                if (x, y) not in reachable:
                    self.seeded[x][y] = 1
        self.remaining_to_seed = sum(
            self.seeded[x][y] == 0
            for x in range(self.width)
            for y in range(self.height)
        )
        # La ruta base en serpiente se calcula una vez, antes de que nadie siembre
        self.planes_zigzag = []
        if self.estrategia == "zigzag":
            self.planes_zigzag = repartir_plan(
                plan_zigzag(self), parameters["n_agents"]
            )

        self.agents = [
            TractorAgent(self, index, self.depot)
            for index in range(parameters["n_agents"])
        ]
        self.current_tick_planted = []
        self.frames = []
        self.tick = 0

    def inside(self, position):
        return (
            0 <= position[0] < self.width
            and 0 <= position[1] < self.height
        )

    def is_obstacle(self, position):
        return bool(self.obstacles[position[0]][position[1]])

    def reachable(self, start):
        queue = deque([start])
        visited = {start}
        while queue:
            current = queue.popleft()
            for dx, dy in DIRECTIONS:
                neighbor = (current[0] + dx, current[1] + dy)
                if (
                    self.inside(neighbor)
                    and neighbor not in visited
                    and not self.is_obstacle(neighbor)
                ):
                    visited.add(neighbor)
                    queue.append(neighbor)
        return visited

    def run(self, max_ticks):
        idle_ticks = 0
        for self.tick in range(1, max_ticks + 1):
            self.current_tick_planted = []
            previous = [agent.pos for agent in self.agents]
            for agent in self.agents:
                agent.step()
            current = [agent.pos for agent in self.agents]
            idle_ticks = idle_ticks + 1 if (
                previous == current and not self.current_tick_planted
            ) else 0
            # El fin de la simulación se decide antes de grabar el fotograma,
            # para que el último frame ya muestre a todos en TERMINADO.
            terminado = self.remaining_to_seed <= 0 or idle_ticks >= 15
            if terminado:
                for agent in self.agents:
                    agent.state = "TERMINADO"
            self.frames.append({
                "tick": self.tick,
                "remaining_cells": self.remaining_to_seed,
                "planted_cells": self.current_tick_planted,
                "agents": [
                    {
                        "id": agent.id,
                        "pos": [agent.pos[0], agent.pos[1]],
                        "fuel": agent.fuel,
                        "seeds": agent.seeds,
                        "state": agent.state,
                        "planted_total": agent.seeds_planted,
                    }
                    for agent in self.agents
                ],
            })
            if terminado:
                break


def run_simulation(payload):
    elevation = payload.get("elevation_map")
    obstacles = payload.get("obstacle_map")
    if elevation is None or obstacles is None:
        raise ValueError("El payload debe incluir elevation_map y obstacle_map.")

    parameters = {
        "grid_size": tuple(payload.get("grid_size", [20, 20])),
        "difficulty": int(payload.get("difficulty", 2)),
        "n_agents": int(payload.get("n_agents", 3)),
        "depot_pos": tuple(payload.get("depot_pos", [0, 0])),
        "elevation_map": elevation,
        "obstacle_map": obstacles,
        # Valores calibrados por defecto (ver INVESTIGACION-AGRICOLA.md):
        # un tanque = un costal = 1 ha, diésel en litros reales.
        "max_fuel": float(payload.get("max_fuel", unidades.TANQUE_DIESEL_L)),
        "max_seeds": int(payload.get("max_seeds", 123)),
        "wage_per_tick": float(payload.get("wage_per_tick",
                                          unidades.salario_por_tick())),
        "cost_per_seed": float(payload.get("cost_per_seed",
                                           unidades.COSTO_SEMILLA_POR_CELDA)),
        "fuel_por_paso": float(payload.get("fuel_por_paso",
                                           unidades.LITROS_POR_CELDA)),
        "estrategia": str(payload.get("estrategia", "greedy")),
    }
    model = FarmingModel(parameters)
    model.run(int(payload.get("steps", 2000)))
    total_fuel = sum(agent.total_fuel_used for agent in model.agents)
    total_steps = sum(agent.steps_taken for agent in model.agents)
    metrics = {
        "total_ticks": model.tick,
        "total_steps": total_steps,
        "total_fuel_consumed": round(total_fuel, 2),
        "driver_wage_cost": round(
            model.tick * model.wage_per_tick * len(model.agents), 2
        ),
        "seed_cost": round(
            sum(agent.seeds_planted for agent in model.agents)
            * model.cost_per_seed,
            2,
        ),
        "remaining_cells": model.remaining_to_seed,
    }
    return {
        "status": "success",
        "depot_pos": list(model.depot),
        "metrics": metrics,
        "frames": model.frames,
    }


class SimulationHTTPRequestHandler(BaseHTTPRequestHandler):
    def respond(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.respond(200, {})

    def do_GET(self):
        ruta = urlparse(self.path)

        if ruta.path == "/payload":
            try:
                consulta = parse_qs(ruta.query)
                terreno = consulta.get("terreno", ["colinas"])[0]
                agentes = int(consulta.get("agentes", ["3"])[0])
                estrategia = consulta.get("estrategia", ["greedy"])[0]
                costales = float(consulta.get("costales", ["16"])[0])

                payload = escenarios.construir_payload(
                    terreno=terreno,
                    n=40,
                    n_agentes=agentes,
                    obstaculos=140,
                    semilla=3,
                    costales=costales,
                    estrategia=estrategia,
                    steps=6000,
                    lado_celda_m=25.0,
                )
                self.respond(200, payload)
            except (ValueError, KeyError) as error:
                self.respond(400, {"status": "error", "message": str(error)})
            return

        if self.path.startswith("/pending_config"):
            with CONFIG_LOCK:
                config = PENDING_UNITY_CONFIG
                globals()["PENDING_UNITY_CONFIG"] = None
            self.respond(200, {"has_config": config is not None, **(config or {})})
            return
        self.respond(200, {"status": "ok", "message": "Servidor activo"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self.respond(200, run_simulation(payload))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            self.respond(400, {"status": "error", "message": str(error)})

    def log_message(self, format_string, *args):
        if "/pending_config" not in (args[0] if args else ""):
            super().log_message(format_string, *args)


def start_server(host="127.0.0.1", port=5000):
    server = ThreadingHTTPServer((host, port), SimulationHTTPRequestHandler)
    print(f"Servidor Python activo en http://{host}:{port}/simulate")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    start_server()
