from __future__ import annotations

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading


PENDING_UNITY_CONFIG = None
CONFIG_LOCK = threading.Lock()
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


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
        return round(cost, 3)

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
        if self.state == "TERMINADO":
            return
        if self.model.remaining_to_seed <= 0:
            self.state = "TERMINADO"
            return

        distance = (
            abs(self.pos[0] - self.depot_pos[0]) +
            abs(self.pos[1] - self.depot_pos[1])
        )
        safe_return_fuel = (distance + 2) * (1.0 + 0.5 * self.model.difficulty)

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
            if self.remaining_to_seed <= 0 or idle_ticks >= 15:
                for agent in self.agents:
                    agent.state = "TERMINADO"
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
        "max_fuel": float(payload.get("max_fuel", 180.0)),
        "max_seeds": int(payload.get("max_seeds", 35)),
        "wage_per_tick": float(payload.get("wage_per_tick", 2.5)),
        "cost_per_seed": float(payload.get("cost_per_seed", 0.5)),
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
