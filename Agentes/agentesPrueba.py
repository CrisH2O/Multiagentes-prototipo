import agentpy as ap
import numpy as np
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading

PENDING_UNITY_CONFIG = None
CONFIG_LOCK = threading.Lock()


class TractorAgent(ap.Agent):
    def setup(self):
        self.grid = self.model.grid
        self.max_fuel = float(self.p.max_fuel)
        self.fuel = self.max_fuel
        self.max_seeds = int(self.p.max_seeds)
        self.seeds = self.max_seeds
        
        self.total_fuel_used = 0.0
        self.seeds_planted = 0
        self.steps_taken = 0
        
        # Estados: 'SEMBRANDO', 'RECARGANDO', 'TERMINADO'
        self.state = 'SEMBRANDO'
        self.depot_pos = tuple(self.p.depot_pos)
        self.target_pos = None

    @property
    def pos(self):
        return self.grid.positions[self]

    def get_move_cost(self, u, v):
        """Calcula el gasto de gasolina basado en la pendiente (curvas de nivel) y dificultad."""
        z_u = self.model.elevation_map[u]
        z_v = self.model.elevation_map[v]
        diff = z_v - z_u
        
        # Factor de penalización según la dificultad (1: Baja, 2: Media, 3: Alta)
        slope_factor = 0.5 * self.p.difficulty
        
        if diff > 0:
            # Subir cuesta más combustible
            cost = 1.0 + (diff * slope_factor)
        else:
            # Bajar o ir plano cuesta menos, con un mínimo de consumo base
            cost = max(0.5, 1.0 + (diff * 0.2))
        return round(float(cost), 3)

    def find_next_step(self, target_condition_fn):
        """
        BFS para encontrar el primer paso hacia la celda más cercana que cumpla target_condition_fn.
        Evita obstáculos, bordes del mapa y posiciones ocupadas por otros tractores.
        """
        start = self.pos
        queue = deque([(start, [])])
        visited = {start}
        
        # Posiciones ocupadas por otros agentes activos (excepto la base para permitir recargas)
        occupied = {
            a.pos for a in self.model.agents
            if a != self and a.pos != self.depot_pos and a.state != 'TERMINADO'
        }

        grid_w, grid_h = self.model.grid_size

        while queue:
            curr, path = queue.popleft()
            if curr != start and target_condition_fn(curr):
                self.target_pos = curr
                return path[0]

            # Vecinos ortogonales (Arriba, Abajo, Izquierda, Derecha)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = curr[0] + dx, curr[1] + dy
                next_pos = (nx, ny)

                # 1. No salirse del área delimitada
                if 0 <= nx < grid_w and 0 <= ny < grid_h:
                    if next_pos not in visited:
                        # 2. Evitar obstáculos y colisiones con otros tractores
                        if self.model.obstacle_map[next_pos] == 0 and next_pos not in occupied:
                            visited.add(next_pos)
                            queue.append((next_pos, path + [next_pos]))
        self.target_pos = None
        return None

    def step(self):
        if self.state == 'TERMINADO':
            return

        # Verificar si ya se sembró todo el terreno disponible
        if self.model.remaining_to_seed <= 0:
            self.state = 'TERMINADO'
            return

        # Distancia Manhattan aproximada a la base para estimar combustible de retorno seguro
        dist_to_depot = abs(self.pos[0] - self.depot_pos[0]) + abs(self.pos[1] - self.depot_pos[1])
        safe_return_fuel = (dist_to_depot + 2) * (1.0 + 0.5 * self.p.difficulty)

        # Evaluar si necesita ir a recargar semillas o combustible
        if self.seeds <= 0 or self.fuel <= safe_return_fuel:
            self.state = 'RECARGANDO'

        # --- LÓGICA DE RECARGA ---
        if self.state == 'RECARGANDO':
            if self.pos == self.depot_pos:
                # Llegó a la base: recarga completa
                self.fuel = self.max_fuel
                self.seeds = self.max_seeds
                self.state = 'SEMBRANDO'
                return
            else:
                # Buscar paso hacia la base
                next_pos = self.find_next_step(lambda pos: pos == self.depot_pos)
                if next_pos is None:
                    next_pos = self.find_free_neighbor()
                if next_pos:
                    self.execute_move(next_pos)
                return

        # --- LÓGICA DE SIEMBRA ---
        if self.state == 'SEMBRANDO':
            # Si la celda actual no está sembrada y no es obstáculo, la sembramos
            if self.model.seeded_map[self.pos] == 0 and self.model.obstacle_map[self.pos] == 0:
                self.plant_seed(self.pos)
                if self.model.remaining_to_seed <= 0:
                    self.state = 'TERMINADO'
                    return

            # Si aún tiene semillas tras sembrar la celda actual, se mueve a la siguiente no sembrada
            if self.seeds > 0 and self.fuel > safe_return_fuel:
                claimed = {
                    a.target_pos for a in self.model.agents
                    if a != self and a.state == 'SEMBRANDO' and a.target_pos is not None
                }
                next_pos = self.find_next_step(
                    lambda pos: (
                        self.model.seeded_map[pos] == 0
                        and self.model.obstacle_map[pos] == 0
                        and pos not in claimed
                    )
                )
                if next_pos is None:
                    next_pos = self.find_next_step(
                        lambda pos: self.model.seeded_map[pos] == 0 and self.model.obstacle_map[pos] == 0
                    )
                if next_pos is None and self.pos != self.depot_pos:
                    # Si otros tractores bloquean temporalmente el paso, regresar hacia la base o ceder paso
                    next_pos = self.find_next_step(lambda pos: pos == self.depot_pos) or self.find_free_neighbor()
                if next_pos:
                    self.execute_move(next_pos)
                    # Sembrar al llegar si la celda está virgen
                    if self.model.seeded_map[self.pos] == 0 and self.seeds > 0:
                        self.plant_seed(self.pos)
                        if self.model.remaining_to_seed <= 0:
                            self.state = 'TERMINADO'

    def find_free_neighbor(self):
        """Busca un vecino ortogonal libre para ceder el paso y evitar bloqueos mutuos."""
        occupied = {
            a.pos for a in self.model.agents
            if a != self and a.pos != self.depot_pos and a.state != 'TERMINADO'
        }
        grid_w, grid_h = self.model.grid_size
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = self.pos[0] + dx, self.pos[1] + dy
            next_pos = (nx, ny)
            if 0 <= nx < grid_w and 0 <= ny < grid_h:
                if self.model.obstacle_map[next_pos] == 0 and next_pos not in occupied:
                    return next_pos
        return None

    def execute_move(self, next_pos):
        """Mueve el agente en la cuadrícula y descuenta gasolina."""
        cost = self.get_move_cost(self.pos, next_pos)
        self.fuel = round(self.fuel - cost, 3)
        self.total_fuel_used = round(self.total_fuel_used + cost, 3)
        self.steps_taken += 1
        self.grid.move_to(self, next_pos)

    def plant_seed(self, pos):
        """Marca la celda como sembrada (nunca se vuelve a sembrar)."""
        self.model.seeded_map[pos] = 1
        self.seeds -= 1
        self.seeds_planted += 1
        self.model.remaining_to_seed -= 1
        self.model.current_tick_planted.append({"x": int(pos[0]), "y": int(pos[1])})


class FarmingModel(ap.Model):
    def setup(self):
        self.grid_size = tuple(self.p.grid_size)
        depot = tuple(self.p.depot_pos)

        # Asegurar que max_fuel permita llegar a la esquina más lejana y regresar a la base
        max_dist = self.grid_size[0] + self.grid_size[1]
        min_required_fuel = (max_dist + 10) * (1.0 + 0.5 * self.p.difficulty) * 2.5
        if self.p.max_fuel < min_required_fuel:
            self.p.max_fuel = round(min_required_fuel, 1)

        # Recibir matrices desde el diccionario de parámetros (enviado por Unity)
        self.elevation_map = np.array(self.p.elevation_map, dtype=float)
        self.obstacle_map = np.array(self.p.obstacle_map, dtype=int)
        
        # Matriz de control de siembra: 0 = No sembrado, 1 = Sembrado
        self.seeded_map = np.zeros(self.grid_size, dtype=int)
        
        # La estación base no se siembra ni debe tener obstáculo
        self.obstacle_map[depot] = 0
        self.seeded_map[depot] = 1

        # Verificar celdas alcanzables desde la base (por si los obstáculos encierran alguna celda)
        reachable = self._find_reachable_cells(depot)
        for x in range(self.grid_size[0]):
            for y in range(self.grid_size[1]):
                if (x, y) not in reachable and self.obstacle_map[x, y] == 0:
                    self.seeded_map[x, y] = 1

        # Total de celdas cultivables meta (alcanzables y sin obstáculo, excluyendo la base)
        self.remaining_to_seed = int(np.sum(self.seeded_map == 0) - np.sum((self.obstacle_map == 1) & (self.seeded_map == 0)))
        for x in range(self.grid_size[0]):
            for y in range(self.grid_size[1]):
                if self.obstacle_map[x, y] == 1:
                    self.seeded_map[x, y] = 1
        self.remaining_to_seed = int(np.sum(self.seeded_map == 0))

        # Crear entorno Grid y Agentes
        self.grid = ap.Grid(self, self.grid_size, track_empty=True)
        self.agents = ap.AgentList(self, self.p.n_agents, TractorAgent)
        
        # Iniciar todos los tractores en la base (0,0)
        self.grid.add_agents(self.agents, positions=[depot] * self.p.n_agents)

        # Historial para exportar a Unity
        self.unity_log = []
        self.current_tick_planted = []
        self.idle_ticks = 0

    def _find_reachable_cells(self, start):
        queue = deque([start])
        visited = {start}
        w, h = self.grid_size
        while queue:
            cx, cy = queue.popleft()
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                    if self.obstacle_map[nx, ny] == 0:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
        return visited

    def step(self):
        self.current_tick_planted = []
        prev_positions = [a.pos for a in self.agents]

        # Ejecutar un turno agente por agente (secuencial para evitar que dos elijan la misma celda en el mismo tick)
        for agent in self.agents:
            agent.step()

        curr_positions = [a.pos for a in self.agents]
        if prev_positions == curr_positions and len(self.current_tick_planted) == 0:
            self.idle_ticks += 1
        else:
            self.idle_ticks = 0

        # Guardar el fotograma actual para que Unity lo reproduzca
        frame_data = {
            "tick": int(self.t),
            "remaining_cells": int(self.remaining_to_seed),
            "planted_cells": self.current_tick_planted,
            "agents": [
                {
                    "id": int(a.id),
                    "pos": [int(a.pos[0]), int(a.pos[1])],
                    "fuel": float(a.fuel),
                    "seeds": int(a.seeds),
                    "state": a.state,
                    "planted_total": int(a.seeds_planted)
                }
                for a in self.agents
            ]
        }
        self.unity_log.append(frame_data)

        # Condición de paro: todo el terreno sembrado, agentes terminados o bloqueo prolongado
        if (
            self.remaining_to_seed <= 0
            or all(a.state == 'TERMINADO' for a in self.agents)
            or self.idle_ticks >= 15
        ):
            for a in self.agents:
                a.state = 'TERMINADO'
            self.stop()

    def end(self):
        # Resumen de métricas finales (costos operativos)
        total_fuel = sum(a.total_fuel_used for a in self.agents)
        total_steps = sum(a.steps_taken for a in self.agents)
        self.report("total_ticks", int(self.t))
        self.report("total_steps", int(total_steps))
        self.report("total_fuel_consumed", round(float(total_fuel), 2))
        self.report("driver_wage_cost", round(float(self.t * self.p.wage_per_tick * self.p.n_agents), 2))
        self.report("seed_cost", round(float(sum(a.seeds_planted for a in self.agents) * self.p.cost_per_seed), 2))


def run_simulation(payload: dict) -> dict:
    """
    Construye los parámetros del modelo a partir del payload recibido de Unity,
    ejecuta la simulación completa y devuelve el diccionario listo para serializar a JSON.
    """
    grid_size = tuple(payload.get("grid_size", [20, 20]))
    difficulty = int(payload.get("difficulty", 2))
    n_agents = int(payload.get("n_agents", 3))
    depot_pos = tuple(payload.get("depot_pos", [0, 0]))

    elevation_map = payload.get("elevation_map")
    obstacle_map = payload.get("obstacle_map")

    if elevation_map is None or obstacle_map is None:
        raise ValueError("El payload debe incluir 'elevation_map' y 'obstacle_map'.")

    parameters = {
        "grid_size": grid_size,
        "difficulty": difficulty,
        "n_agents": n_agents,
        "elevation_map": elevation_map,
        "obstacle_map": obstacle_map,
        "depot_pos": depot_pos,
        "max_fuel": float(payload.get("max_fuel", 180.0)),
        "max_seeds": int(payload.get("max_seeds", 35)),
        "wage_per_tick": float(payload.get("wage_per_tick", 2.5)),
        "cost_per_seed": float(payload.get("cost_per_seed", 0.5)),
        "steps": int(payload.get("steps", 2000)),
    }

    model = FarmingModel(parameters)
    results = model.run(display=False)

    raw_metrics = (
        results.reporters.iloc[0].to_dict()
        if hasattr(results.reporters, "iloc")
        else dict(results.reporters)
    )
    metrics_dict = {
        "total_ticks": int(raw_metrics.get("total_ticks", model.t)),
        "total_steps": int(raw_metrics.get("total_steps", 0)),
        "total_fuel_consumed": float(raw_metrics.get("total_fuel_consumed", 0.0)),
        "driver_wage_cost": float(raw_metrics.get("driver_wage_cost", 0.0)),
        "seed_cost": float(raw_metrics.get("seed_cost", 0.0)),
        "remaining_cells": int(model.remaining_to_seed),
    }

    print("\n--- RESUMEN DE LA SIMULACIÓN ---")
    print(f"Cuadrícula: {grid_size[0]}x{grid_size[1]} | Dificultad: {difficulty} | Tractores: {n_agents}")
    print(f"Terreno restante sin sembrar: {model.remaining_to_seed} celdas")
    print(f"Ticks totales (Tiempo): {metrics_dict['total_ticks']}")
    print(f"Combustible total usado: {metrics_dict['total_fuel_consumed']} L")
    print(f"Costo total de salarios: ${metrics_dict['driver_wage_cost']}")
    print(f"Costo total de semillas: ${metrics_dict['seed_cost']}")

    return {
        "status": "success",
        "depot_pos": [int(depot_pos[0]), int(depot_pos[1])],
        "metrics": metrics_dict,
        "frames": model.unity_log,
    }


class SimulationHTTPRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        global PENDING_UNITY_CONFIG
        if self.path.startswith("/pending_config"):
            self._set_headers(200)
            with CONFIG_LOCK:
                if PENDING_UNITY_CONFIG is not None:
                    data = {"has_config": True, **PENDING_UNITY_CONFIG}
                    PENDING_UNITY_CONFIG = None
                else:
                    data = {"has_config": False}
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        self._set_headers(200)
        response = {"status": "ok", "message": "Servidor de simulacion activo"}
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)

            response_data = run_simulation(payload)
            self._set_headers(200)
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        except Exception as exc:
            error_response = {
                "status": "error",
                "message": str(exc),
            }
            self._set_headers(400)
            self.wfile.write(json.dumps(error_response).encode("utf-8"))

    def log_message(self, format, *args):
        if "/pending_config" not in (args[0] if args else ""):
            print(f"[Servidor Unity <-> Python] {self.address_string()} - {format % args}")


def prompt_console_input_loop():
    """Permite al usuario ingresar parámetros desde la terminal de Python para disparar la simulación en Unity."""
    global PENDING_UNITY_CONFIG
    while True:
        try:
            print("\n---------------------------------------------------------------------")
            print("Ingresa parámetros para enviar a Unity (o usa el menú dentro de Unity):")
            diff_str = input("  Dificultad / Terreno (1: Plano, 2: Medio, 3: Montañoso) [2]: ").strip()
            difficulty = int(diff_str) if diff_str else 2
            difficulty = max(1, min(3, difficulty))

            tractors_str = input("  Cantidad de tractores (1-8) [3]: ").strip()
            n_agents = int(tractors_str) if tractors_str else 3
            n_agents = max(1, min(8, n_agents))

            obs_str = input("  Cantidad de obstáculos (0-150) [35]: ").strip()
            obstacles = int(obs_str) if obs_str else 35
            obstacles = max(0, min(150, obstacles))

            with CONFIG_LOCK:
                PENDING_UNITY_CONFIG = {
                    "difficulty": difficulty,
                    "n_agents": n_agents,
                    "obstacles": obstacles,
                }
            print(
                f"-> Configuración lista ({n_agents} tractores, dificultad {difficulty}, "
                f"{obstacles} obstáculos). Esperando a Unity en modo Play..."
            )
        except ValueError:
            print("Entrada inválida. Por favor ingresa números enteros.")
        except (EOFError, KeyboardInterrupt):
            break


def start_server(host="127.0.0.1", port=5000, interactive=True):
    server = ThreadingHTTPServer((host, port), SimulationHTTPRequestHandler)
    print("=====================================================================")
    print(f"SERVIDOR MULTIAGENTES ACTIVO EN http://{host}:{port}/simulate")
    print("Esperando parámetros del usuario y mapa desde Unity...")
    print("(Presiona Ctrl+C para detener el servidor)")
    print("=====================================================================")

    if interactive and sys.stdin is not None and sys.stdin.isatty():
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            prompt_console_input_loop()
        except KeyboardInterrupt:
            pass
        finally:
            print("\nServidor detenido.")
            server.shutdown()
            server.server_close()
    else:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")
        finally:
            server.server_close()


# =====================================================================
# BLOQUE PRINCIPAL (SERVIDOR PARA UNITY O PRUEBA LOCAL CON --test)
# =====================================================================
if __name__ == "__main__":
    if "--test" in sys.argv:
        # 1. Parámetros elegidos por el usuario en la UI de Unity
        GRID_W, GRID_H = 12, 12
        DIFFICULTY = 2        # 1: Fácil, 2: Media, 3: Difícil
        N_TRACTORS = 3        # Cantidad de agentes

        # 2. Simulación de mapas ya generados por Unity (Curvas de nivel y Obstáculos)
        np.random.seed(42)
        x, y = np.meshgrid(np.linspace(-2, 2, GRID_W), np.linspace(-2, 2, GRID_H))
        mock_elevation = np.exp(-((x - 0.8)**2 + (y - 0.8)**2)) * 5 + np.exp(-((x + 0.8)**2 + (y + 0.8)**2)) * 4
        mock_obstacles = np.random.choice([0, 1], size=(GRID_W, GRID_H), p=[0.90, 0.10])
        mock_obstacles[0, 0] = 0

        test_payload = {
            "grid_size": [GRID_W, GRID_H],
            "difficulty": DIFFICULTY,
            "n_agents": N_TRACTORS,
            "elevation_map": mock_elevation.tolist(),
            "obstacle_map": mock_obstacles.tolist(),
            "depot_pos": [0, 0],
        }

        unity_response = run_simulation(test_payload)
        sample_response = {
            "status": unity_response["status"],
            "metrics": unity_response["metrics"],
            "frames": unity_response["frames"][:2],
        }
        print("\n--- EJEMPLO DE PAYLOAD JSON PARA UNITY (Primeros 2 Ticks) ---")
        print(json.dumps(sample_response, indent=2))
    else:
        port = 5000
        interactive = "--no-input" not in sys.argv
        for arg in sys.argv[1:]:
            if arg.isdigit():
                port = int(arg)
        start_server(port=port, interactive=interactive)