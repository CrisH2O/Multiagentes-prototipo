from __future__ import annotations

from campo import Campo, Celda, TipoCelda
from planeacion import manhattan
from vehiculo import Vehiculo

"""
Define su ruta y la sigue si es posible sembrando en el camino
Si detecta que al final de una linea no tendra suficente grano para la siguiente, llama a la nodriza
"""
class Sembradora(Vehiculo):
    #Estados
    SEMBRANDO = "SEMBRANDO"
    ESPERANDO_NODRIZA = "ESPERANDO_NODRIZA"
    RECARGANDO = "RECARGANDO"
    TERMINADA = "TERMINADA"

    def __init__(self, nombre: str, campo: Campo, posicion: Celda, plan: list[Celda], radio_percepcion: int = 2,
                 capacidad_tolva_kg: float = 50.0, semilla_por_celda_kg: float = 2.0,
                 ticks_por_vuelta: int = 0, nodriza: str = "nodriza_1",
                 aviso_anticipado: bool = True, combustible_por_paso_L: float = 0.5):
        super().__init__(nombre, campo, posicion, radio_percepcion, combustible_por_paso_L)
        if semilla_por_celda_kg <= 0:
            raise ValueError("semilla_por_celda_kg debe ser > 0")
        if ticks_por_vuelta < 0:
            raise ValueError("ticks_por_vuelta no puede ser negativo")

        self.plan = list(plan) #celdas pendientes de sembrar, en orden
        self.estado = self.SEMBRANDO
        self.sembradas = 0
        self.descartadas: list[Celda] = [] # celdas que no pudo sembrar
        self.motivo_fin: str | None = None

        # Pasadas
        self.pasada_actual: int | None = None
        self.ticks_por_vuelta = ticks_por_vuelta
        self.espera_vuelta = 0
        self.vueltas = 0
        self.ticks_en_vueltas = 0

        # Semilla
        self.capacidad_tolva_kg = capacidad_tolva_kg
        self.semilla_por_celda_kg = semilla_por_celda_kg
        self.semilla_kg = capacidad_tolva_kg # empieza con la tolva llena
        self.semilla_usada_kg = 0.0
        self.celdas_sembradas: set[Celda] = set()
        mas_larga = self.pasada_mas_larga()
        if mas_larga * semilla_por_celda_kg > capacidad_tolva_kg:
            raise ValueError(f"La tolva ({capacidad_tolva_kg} kg) no alcanza para la pasada más larga "
                             f"({mas_larga} celdas = {mas_larga * semilla_por_celda_kg} kg)")

        # Recarga con la nodriza
        self.nodriza = nodriza
        self.id_solicitud = 0
        self.lugar_espera: Celda | None = None # Donde se pondra la sembradora
        self.punto_encuentro: Celda | None = None # Donde se pondra la nodriza
        self.lista_enviada = False
        self.aviso_anticipado = aviso_anticipado
        self.recarga_pendiente = False
        self.recargar_al_terminar: int | None = None
        self.avisos_anticipados = 0
        self.recargas = 0
        self.ticks_recargando = 0
        self.ticks_esperando = 0

    # Carril: solo el área de siembra (sembrada o no)
    def puede_pasar(self, celda: Celda) -> bool:
        return self.mapa.es_sembrable(celda)

    def celdas_a_evitar(self) -> set[Celda]:
        return self.celdas_sembradas

    # Pasadas
    def pasada(self, celda: Celda) -> int:
        return celda[1]   # la fila

    def celdas_de_pasada(self, desde: int = 0) -> int:
        """Cuántas celdas seguidas del plan, a partir de la posición `desde`, están en la misma pasada."""
        if desde >= len(self.plan):
            return 0
        p = self.pasada(self.plan[desde])
        n = 0
        for celda in self.plan[desde:]:
            if self.pasada(celda) != p:
                break
            n += 1
        return n

    def pasada_mas_larga(self) -> int:
        mas_larga, actual, anterior = 0, 0, None
        for celda in self.plan:
            actual = actual + 1 if self.pasada(celda) == anterior else 1
            anterior = self.pasada(celda)
            mas_larga = max(mas_larga, actual)
        return mas_larga

    def inicio_de_pasada(self) -> bool:
        return bool(self.plan) and self.pasada(self.plan[0]) != self.pasada_actual

    # Reglas de recarga
    def necesita_recargar(self) -> bool:
        return self.inicio_de_pasada() and self.semilla_kg + 1e-9 < self.celdas_de_pasada() * self.semilla_por_celda_kg

    def no_alcanzara_para_la_siguiente(self) -> bool:
        #Cuando empieza una pasada se pregunta si alcanzará para la siguiente
        n = self.celdas_de_pasada()
        siguiente = self.celdas_de_pasada(desde=n)
        if siguiente == 0:
            return False
        sobrante = self.semilla_kg - n * self.semilla_por_celda_kg
        return sobrante + 1e-9 < siguiente * self.semilla_por_celda_kg

    def elegir_lugar_de_espera(self, cerca_de: Celda) -> Celda | None:
        candidatas = sorted((c for c in self.mapa.celdas_de_tipo(TipoCelda.SEMBRABLE)
                             if any(self.mapa.es_cabecera(v) for v in self.mapa.vecinos(c))),
                            key=lambda c: (manhattan(cerca_de, c), c))
        for c in candidatas:
            if c == self.posicion or self.ruta_hacia(c) is not None:
                return c
        return None

    def pedir_recarga(self, cerca_de: Celda, semilla_al_llegar: float | None = None) -> None:
        self.id_solicitud += 1
        self.recarga_pendiente = True
        self.lugar_espera = self.elegir_lugar_de_espera(cerca_de)
        self.punto_encuentro = None
        self.lista_enviada = False
        if self.lugar_espera is None:
            self.terminar("recarga_inalcanzable")
            return
        if semilla_al_llegar is None:
            semilla_al_llegar = self.semilla_kg
        self.enviar(self.nodriza, "SOLICITUD", id=self.id_solicitud, cerca_de=self.lugar_espera,
                    kg=self.capacidad_tolva_kg - semilla_al_llegar)

    def recibir_semilla(self, kg: float) -> float:
        aceptado = max(0.0, min(kg, self.capacidad_tolva_kg - self.semilla_kg))
        self.semilla_kg += aceptado
        if self.estado == self.ESPERANDO_NODRIZA:
            self.estado = self.RECARGANDO
        return aceptado

    # Decisiones
    def leer_mensajes(self) -> None:
        for m in self.buzon:
            if m.contenido.get("id") != self.id_solicitud:
                continue
            if m.tipo == "ACEPTA":
                self.punto_encuentro = m.contenido["punto"]
            elif m.tipo == "COMPLETA":
                self.recargas += 1
                self.recarga_pendiente = False
                self.recargar_al_terminar = None
                self.estado = self.SEMBRANDO
                self.ruta = []

    def decidir(self) -> None:
        self.leer_mensajes()
        if self.estado in (self.TERMINADA, self.RECARGANDO):
            return
        if self.estado == self.ESPERANDO_NODRIZA:
            self.acercarse_a_la_nodriza()
            return

        # SEMBRANDO
        # Quitar la casilla bloqueada
        while self.plan and (not self.mapa.es_sembrable(self.plan[0]) or self.campo.esta_sembrada(self.plan[0])):
            self.descartadas.append(self.plan.pop(0))
            self.ruta = []

        if not self.plan:
            self.terminar("completado")
            return

        if self.inicio_de_pasada():
            termino_la_pasada_acordada = (self.recargar_al_terminar is not None
                                          and self.pasada_actual == self.recargar_al_terminar)
            if termino_la_pasada_acordada or self.necesita_recargar():
                # Toca recargar
                self.estado = self.ESPERANDO_NODRIZA
                self.ruta = []
                if not self.recarga_pendiente:
                    self.pedir_recarga(cerca_de=self.posicion)
                return
            if self.aviso_anticipado and not self.recarga_pendiente and self.no_alcanzara_para_la_siguiente():
                # Llama a la nodriza antes de terminar la pasada
                n = self.celdas_de_pasada()
                fin_de_pasada = self.plan[n - 1]
                self.pedir_recarga(cerca_de=fin_de_pasada,
                                   semilla_al_llegar=self.semilla_kg - n * self.semilla_por_celda_kg)
                self.recargar_al_terminar = self.pasada(self.plan[0])
                self.avisos_anticipados += 1

        # Usar BFS para encontrar la ruta hacia el siguiente objetivo
        objetivo = self.plan[0]
        if not self.ruta_vigente(objetivo):
            ruta = self.ruta_hacia(objetivo)
            if ruta is None: #Descartarlo si no hay camino
                self.descartadas.append(self.plan.pop(0))
                self.ruta = []
            else:
                self.ruta = ruta

    def acercarse_a_la_nodriza(self) -> None:
        # Ir al lugar de espera
        punto = self.punto_encuentro
        if punto is not None and manhattan(self.posicion, punto) == 1:
            if not self.lista_enviada:
                self.enviar(self.nodriza, "LISTA", id=self.id_solicitud, pos=self.posicion)
                self.lista_enviada = True
            self.ruta = []
            return
        destino = self.lugar_espera
        if not self.puede_pasar(destino):
            # Si el lugar esta bloqueado reubicarlo
            self.pedir_recarga(cerca_de=self.posicion)
            return
        if self.posicion != destino and not self.ruta_vigente(destino):
            self.ruta = self.ruta_hacia(destino) or []
            if not self.ruta:
                self.terminar("recarga_inalcanzable")

    def terminar(self, motivo: str) -> None:
        self.estado = self.TERMINADA
        self.motivo_fin = motivo
        self.ruta = []

    # Acciones
    def actuar(self) -> None:
        if self.estado == self.TERMINADA:
            return
        if self.espera_vuelta > 0:
            self.espera_vuelta -= 1
            self.ticks_en_vueltas += 1
            return
        if self.estado == self.RECARGANDO:
            self.ticks_recargando += 1
            return
        if self.estado == self.ESPERANDO_NODRIZA:
            self.ticks_esperando += 1
            self.avanzar()
            return

        # Solo se siembra si esta activo el estado de sembrar.
        # Se siembra al llegar a la celda objetivo, o sin moverse si ya estaba parada en ella.
        self.avanzar()
        if self.plan and self.posicion == self.plan[0]:
            self.campo.marcar_sembrada(self.posicion)
            self.celdas_sembradas.add(self.posicion)
            pasada = self.pasada(self.posicion)
            if self.pasada_actual is not None and pasada != self.pasada_actual:
                self.vueltas += 1
                self.espera_vuelta = self.ticks_por_vuelta
            self.pasada_actual = pasada
            self.semilla_kg -= self.semilla_por_celda_kg
            self.semilla_usada_kg += self.semilla_por_celda_kg
            self.plan.pop(0)
            self.sembradas += 1
