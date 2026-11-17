import agentpy as ap
import numpy as np
from collections import deque
import json

class TractorAgent(ap.Agent):
    def setup(self):
        self.grid = self.model.grid
        self.max_fuel = self.p.max_fuel
        self.fuel = self.max_fuel
        self.max_seeds = self.p.max_seeds
        self.seeds = self.max_seeds
        
        self.total_fuel_used = 0.0
        self.seeds_planted = 0
        self.steps_taken = 0
        
        # Estados: 'SEMBRANDO', 'RECARGANDO', 'TERMINADO'
        self.state = 'SEMBRANDO'
        self.depot_pos = self.p.depot_pos

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
        return round(cost, 3)

    def find_next_step(self, target_condition_fn):
        """
        BFS para encontrar el primer paso hacia la celda más cercana que cumpla target_condition_fn.
        Evita obstáculos, bordes del mapa y posiciones ocupadas por otros tractores.
        """
        start = self.pos
        queue = deque([(start, [])])
        visited = {start}
        
        # Posiciones ocupadas por otros agentes (excepto la base para permitir recargas)
        occupied = {a.pos for a in self.model.agents if a != self and a.pos != self.depot_pos}

        while queue:
            curr, path = queue.popleft()
            if curr != start and target_condition_fn(curr):
                return path[0]

            # Vecinos ortogonales (Arriba, Abajo, Izquierda, Derecha)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = curr[0] + dx, curr[1] + dy
                next_pos = (nx, ny)

                # 1. No salirse del área delimitada
                if 0 <= nx < self.p.grid_size[0] and 0 <= ny < self.p.grid_size[1]:
                    if next_pos not in visited:
                        # 2. Evitar obstáculos y colisiones con otros tractores
                        if self.model.obstacle_map[next_pos] == 0 and next_pos not in occupied:
                            visited.add(next_pos)
                            queue.append((next_pos, path + [next_pos]))
        return None

    def step(self):
        if self.state == 'TERMINADO':
            return

        # Verificar si ya se sembró todo el terreno disponible
        if self.model.remaining_to_seed <= 0:
            self.state = 'TERMINADO'
            return

        # Distancia Manhattan aproximada a la base para estimar combustible de retorno Seguro
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
                next_pos = self.find_next_step(
                    lambda pos: self.model.seeded_map[pos] == 0 and self.model.obstacle_map[pos] == 0
                )
                if next_pos:
                    self.execute_move(next_pos)
                    # Sembrar al llegar si la celda está virgen
                    if self.model.seeded_map[self.pos] == 0 and self.seeds > 0:
                        self.plant_seed(self.pos)

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


class FarmingModel(ap.Model):
    def setup(self):
        # Recibir matrices desde el diccionario de parámetros (enviado por Unity)
        self.elevation_map = np.array(self.p.elevation_map)
        self.obstacle_map = np.array(self.p.obstacle_map)
        
        # Matriz de control de siembra: 0 = No sembrado, 1 = Sembrado
        self.seeded_map = np.zeros(self.p.grid_size, dtype=int)
        
        # La estación base no se siembra ni debe tener obstáculo
        depot = self.p.depot_pos
        self.obstacle_map[depot] = 0
        self.seeded_map[depot] = 1 

        # Total de celdas cultivables meta
        total_cells = self.p.grid_size[0] * self.p.grid_size[1]
        obstacles_count = int(np.sum(self.obstacle_map))
        self.remaining_to_seed = total_cells - obstacles_count - 1 # -1 por la base

        # Crear entorno Grid y Agentes
        self.grid = ap.Grid(self, self.p.grid_size, track_empty=True)
        self.agents = ap.AgentList(self, self.p.n_agents, TractorAgent)
        
        # Iniciar todos los tractores en la base (0,0) o distribuirlos alrededor
        self.grid.add_agents(self.agents, positions=[depot] * self.p.n_agents)

        # Historial para exportar a Unity
        self.unity_log = []

    def step(self):
        # Ejecutar un turno agente por agente (secuencial para evitar que dos elijan la misma celda en el mismo tick)
        for agent in self.agents:
            agent.step()

        # Guardar el fotograma actual para que Unity lo reproduzca
        frame_data = {
            "tick": self.t,
            "remaining_cells": int(self.remaining_to_seed),
            "agents": [
                {
                    "id": a.id,
                    "pos": [int(a.pos[0]), int(a.pos[1])],
                    "fuel": a.fuel,
                    "seeds": int(a.seeds),
                    "state": a.state,
                    "planted_total": int(a.seeds_planted)
                }
                for a in self.agents
            ]
        }
        self.unity_log.append(frame_data)

        # Condición de paro: todo el terreno sembrado o límite de seguridad de pasos alcanzado
        if self.remaining_to_seed <= 0 or all(a.state == 'TERMINADO' for a in self.agents):
            self.stop()

    def end(self):
        # Resumen de métricas finales (costos operativos)
        total_fuel = sum(a.total_fuel_used for a in self.agents)
        total_steps = sum(a.steps_taken for a in self.agents)
        self.report("total_ticks", self.t)
        self.report("total_fuel_consumed", round(total_fuel, 2))
        self.report("driver_wage_cost", round(self.t * self.p.wage_per_tick * self.p.n_agents, 2))
        self.report("seed_cost", sum(a.seeds_planted for a in self.agents) * self.p.cost_per_seed)


# =====================================================================
# BLOQUE DE PRUEBA (SIMULANDO EL INPUT QUE MANDARÍA UNITY AL BACKEND)
# =====================================================================
if __name__ == "__main__":
    # 1. Parámetros elegidos por el usuario en la UI de Unity
    GRID_W, GRID_H = 12, 12
    DIFFICULTY = 2        # 1: Fácil, 2: Media, 3: Difícil
    N_TRACTORS = 3        # Cantidad de agentes

    # 2. Simulación de mapas ya generados por Unity (Curvas de nivel y Obstáculos)
    np.random.seed(42)
    # Mapa de elevación con dos colinas suaves (como tu imagen de Unity)
    x, y = np.meshgrid(np.linspace(-2, 2, GRID_W), np.linspace(-2, 2, GRID_H))
    mock_elevation = np.exp(-((x - 0.8)**2 + (y - 0.8)**2)) * 5 + np.exp(-((x + 0.8)**2 + (y + 0.8)**2)) * 4
    
    # Obstáculos aleatorios según la dificultad (ej. 10% del mapa bloqueado)
    mock_obstacles = np.random.choice([0, 1], size=(GRID_W, GRID_H), p=[0.90, 0.10])
    mock_obstacles[0, 0] = 0 # Asegurar que la base esté libre

    # 3. Diccionario de configuración para AgentPy
    parameters = {
        "grid_size": (GRID_W, GRID_H),
        "difficulty": DIFFICULTY,
        "n_agents": N_TRACTORS,
        "elevation_map": mock_elevation.tolist(),
        "obstacle_map": mock_obstacles.tolist(),
        "depot_pos": (0, 0),       # Esquina donde recargan gasolina y semillas
        "max_fuel": 45.0,          # Capacidad del tanque de gasolina
        "max_seeds": 30,           # Capacidad de la tolva de semillas
        "wage_per_tick": 2.5,      # Salario por unidad de tiempo
        "cost_per_seed": 0.5,      # Costo unitario por semilla
        "steps": 500               # Tope máximo de ticks por seguridad
    }

    # 4. Ejecutar el modelo
    model = FarmingModel(parameters)
    results = model.run()

    # 5. Imprimir resumen y muestra del JSON que le devolverías a Unity
    print("\n--- RESUMEN DE LA SIMULACIÓN ---")
    print(f"Terreno restante sin sembrar: {model.remaining_to_seed} celdas")
    print(f"Ticks totales (Tiempo): {results.reporters['total_ticks'].iloc[0]}")
    print(f"Combustible total usado: {results.reporters['total_fuel_consumed'].iloc[0]} L")
    print(f"Costo total de salarios: ${results.reporters['driver_wage_cost'].iloc[0]}")
    print(f"Costo total de semillas: ${results.reporters['seed_cost'].iloc[0]}")

    # Convertir el DataFrame de reporters a un diccionario plano de Python
    metrics_dict = results.reporters.iloc[0].to_dict() if hasattr(results.reporters, "iloc") else dict(results.reporters)

    # Exportar los primeros 2 ticks a formato JSON (lo que consumiría Unity)
    unity_response = {
        "status": "success",
        "metrics": metrics_dict,  # <-- Usamos el diccionario limpio en lugar del DataFrame
        "frames": model.unity_log[:2] 
    }
    
    print("\n--- EJEMPLO DE PAYLOAD JSON PARA UNITY (Primeros 2 Ticks) ---")
    json_string = json.dumps(unity_response, indent=2)
    print(json_string)