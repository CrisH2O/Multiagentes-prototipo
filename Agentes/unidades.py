"""Conversión entre las unidades del simulador y las unidades del campo.

El modelo trabaja con **celdas** y **ticks**; en el campo se trabaja con
**hectáreas** y **costales de semilla**. Este módulo fija esa equivalencia con
los valores investigados en ``INVESTIGACION-AGRICOLA.md`` (con sus fuentes).

Nada aquí altera la simulación: son conversiones para *reportar* resultados.
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Geometría: la celda es el ancho de trabajo de la sembradora
# ---------------------------------------------------------------------------
# 12 surcos x 0.76 m = 9.12 m  (John Deere 1775NT / DR12)
LADO_CELDA_M = 9.0
AREA_CELDA_M2 = LADO_CELDA_M ** 2          # 81 m²
M2_POR_HECTAREA = 10_000.0
CELDAS_POR_HECTAREA = M2_POR_HECTAREA / AREA_CELDA_M2   # ≈ 123.46

# Ancho real de trabajo de la sembradora (12 surcos x 0.76 m).
# Una pasada cubre 9.12 m; en una hectarea (100 x 100 m) caben
# 100 / 9.12 ≈ 11 pasadas de 100 m.
ANCHO_SEMBRADORA_M = 9.12
PASADAS_POR_HECTAREA = math.ceil(100.0 / ANCHO_SEMBRADORA_M)   # 11


def pasadas_por_celda(lado_celda_m: float = LADO_CELDA_M,
                      ancho_sembradora_m: float = ANCHO_SEMBRADORA_M) -> int:
    """Cuantas pasadas de la sembradora necesita una celda cuadrada."""
    return math.ceil(lado_celda_m / ancho_sembradora_m)

# ---------------------------------------------------------------------------
# Semilla de maíz
# ---------------------------------------------------------------------------
DENSIDAD_SEMILLAS_HA = 60_000       # típico (rango 45,000 - 80,000)
DENSIDAD_MIN_HA = 45_000
DENSIDAD_MAX_HA = 80_000
SEMILLAS_POR_KG = 3_000             # híbridos comerciales
KG_POR_COSTAL = 20.0
SEMILLAS_POR_COSTAL = 60_000
COSTO_COSTAL_MXN = 1_500.0          # programa subsidiado 2026

# ---------------------------------------------------------------------------
# Combustible y tiempo
# ---------------------------------------------------------------------------
LITROS_POR_HA = 8.6                 # siembra a 6 km/h (rango 8.6 - 10.77)
LITROS_POR_HA_MAX = 10.77           # siembra a 9 km/h
PRECIO_DIESEL_MXN_L = 27.0          # rango 25.39 - 28.00 (2026)
VELOCIDAD_KMH = 6.0
EFICIENCIA_CAMPO = 0.85             # fracción del tiempo teórico que es efectivo

# ---------------------------------------------------------------------------
# Conversiones
# ---------------------------------------------------------------------------
def hectareas(celdas: int | float,
              lado_celda_m: float = LADO_CELDA_M) -> float:
    """Hectáreas que ocupan N celdas del lado indicado."""
    return celdas * (lado_celda_m ** 2) / M2_POR_HECTAREA


def celdas_por_hectarea() -> float:
    return CELDAS_POR_HECTAREA


def semillas_por_hectarea(densidad: float = DENSIDAD_SEMILLAS_HA) -> float:
    """Semillas necesarias para sembrar una hectárea a la densidad dada."""
    return densidad


def semillas_por_celda(densidad: float = DENSIDAD_SEMILLAS_HA) -> float:
    """Semillas reales que van en una celda de 81 m²."""
    return densidad / CELDAS_POR_HECTAREA


def costales_por_hectarea(densidad: float = DENSIDAD_SEMILLAS_HA) -> float:
    """Costales de 20 kg necesarios por hectárea."""
    return densidad / SEMILLAS_POR_COSTAL


def costales_de_celdas(celdas: int | float,
                       densidad: float = DENSIDAD_SEMILLAS_HA) -> float:
    """Costales equivalentes a sembrar N celdas."""
    return hectareas(celdas) * costales_por_hectarea(densidad)


def litros_por_hectarea(velocidad_kmh: float = VELOCIDAD_KMH) -> float:
    """Consumo de diésel interpolado entre las dos velocidades medidas."""
    if velocidad_kmh <= VELOCIDAD_KMH:
        return LITROS_POR_HA
    if velocidad_kmh >= 9.0:
        return LITROS_POR_HA_MAX
    # Interpolación lineal entre 6 y 9 km/h
    avance = (velocidad_kmh - VELOCIDAD_KMH) / (9.0 - VELOCIDAD_KMH)
    return LITROS_POR_HA + avance * (LITROS_POR_HA_MAX - LITROS_POR_HA)


def costo_combustible_por_hectarea(velocidad_kmh: float = VELOCIDAD_KMH,
                                   precio_litro: float = PRECIO_DIESEL_MXN_L) -> float:
    """Pesos de diésel por hectárea sembrada."""
    return litros_por_hectarea(velocidad_kmh) * precio_litro


def segundos_por_tick(velocidad_kmh: float = VELOCIDAD_KMH,
                      lado_celda_m: float = LADO_CELDA_M) -> float:
    """Tiempo real que representa avanzar una celda en un tick."""
    metros_por_segundo = velocidad_kmh * 1000.0 / 3600.0
    return lado_celda_m / metros_por_segundo


def horas_de_ticks(ticks: float, velocidad_kmh: float = VELOCIDAD_KMH) -> float:
    """Horas de trabajo efectivo equivalentes a N ticks."""
    return ticks * segundos_por_tick(velocidad_kmh) / 3600.0


def hectareas_por_hora(velocidad_kmh: float = VELOCIDAD_KMH,
                       eficiencia: float = EFICIENCIA_CAMPO) -> float:
    """Rendimiento de campo teórico corregido por eficiencia."""
    ancho_m = LADO_CELDA_M
    m2_por_hora = ancho_m * velocidad_kmh * 1000.0 * eficiencia
    return m2_por_hora / M2_POR_HECTAREA


# ---------------------------------------------------------------------------
# Preset calibrado para experimentos "realistas"
# ---------------------------------------------------------------------------
def preset_realista(n_celdas: int = 20,
                    lado_celda_m: float = LADO_CELDA_M) -> dict:
    """Parámetros del modelo expresados en magnitudes de campo.

    Devuelve el tanque y el consumo equivalentes a un costal real de semilla,
    para usarlos en ``escenarios.construir_payload``.
    """
    area = hectareas(n_celdas * n_celdas, lado_celda_m)
    return {
        "hectareas": round(area, 3),
        "costales_equivalentes": round(area * costales_por_hectarea(), 2),
        # 1 "semilla" del modelo = 1 celda sembrada => 123 celdas por costal
        "max_seeds_por_costal": round(CELDAS_POR_HECTAREA),
        "litros_totales": round(area * LITROS_POR_HA, 1),
        "costo_combustible": round(area * costo_combustible_por_hectarea(), 2),
        "horas_estimadas": round(area / hectareas_por_hora(), 2),
    }


if __name__ == "__main__":
    print(f"Celda: {LADO_CELDA_M} m -> {AREA_CELDA_M2:.0f} m²")
    print(f"Celdas por hectárea: {CELDAS_POR_HECTAREA:.1f}")
    print(f"Semillas por celda: {semillas_por_celda():.0f}")
    print(f"1 costal = {SEMILLAS_POR_COSTAL / DENSIDAD_SEMILLAS_HA:.2f} ha")
    print(f"1 tick = {segundos_por_tick():.2f} s")
    print(f"Rendimiento: {hectareas_por_hora():.2f} ha/h")
    print()
    print("Campo 20x20 (3.24 ha):")
    for clave, valor in preset_realista(20).items():
        print(f"  {clave:22s} {valor}")


# ---------------------------------------------------------------------------
# Calibración del modelo a magnitudes reales
# ---------------------------------------------------------------------------
# Un tanque = un costal = una hectárea. Así se piensa en el campo.
COSTALES_POR_TANQUE = 1.0

# Un tractor mediano lleva ~300 L de diésel: no recarga en un lote de 3 ha,
# así que el reabastecimiento lo dispara la semilla, como en la realidad.
TANQUE_DIESEL_L = 300.0

# Jornal del operador: ~$50 MXN por hora (8 h ≈ $400/día).
SALARIO_HORA_MXN = 50.0

# Derivados
LITROS_POR_CELDA = LITROS_POR_HA / CELDAS_POR_HECTAREA        # ≈ 0.0697 L
COSTO_SEMILLA_POR_CELDA = COSTO_COSTAL_MXN / CELDAS_POR_HECTAREA  # ≈ $12.15


def salario_por_tick(salario_hora: float = SALARIO_HORA_MXN,
                     velocidad_kmh: float = VELOCIDAD_KMH,
                     lado_celda_m: float = LADO_CELDA_M) -> float:
    """Costo de mano de obra que corresponde a un tick."""
    horas_por_tick = segundos_por_tick(velocidad_kmh, lado_celda_m) / 3600.0
    return salario_hora * horas_por_tick


def parametros_calibrados(costales_por_tanque: float = COSTALES_POR_TANQUE,
                          tanque_litros: float = TANQUE_DIESEL_L,
                          salario_hora: float = SALARIO_HORA_MXN,
                          precio_litro: float = PRECIO_DIESEL_MXN_L,
                          lado_celda_m: float = LADO_CELDA_M) -> dict:
    """Parámetros del modelo expresados en magnitudes de campo.

    1 unidad de semilla del modelo = 1 celda sembrada. El tamaño de la celda
    se puede cambiar (por ejemplo 25 m para un campo de 100 ha) sin romper
    la calibración: todo se deriva del área de la celda.
    """
    celdas_por_ha = M2_POR_HECTAREA / (lado_celda_m ** 2)

    return {
        "max_seeds": int(round(costales_por_tanque * celdas_por_ha)),
        "max_fuel": float(tanque_litros),
        "fuel_por_paso": LITROS_POR_HA / celdas_por_ha,
        "cost_per_seed": round(costales_por_tanque * COSTO_COSTAL_MXN
                               / (costales_por_tanque * celdas_por_ha), 4),
        "wage_per_tick": round(
            salario_por_tick(salario_hora, lado_celda_m=lado_celda_m), 5),
        "precio_litro": float(precio_litro),
        "costales_por_tanque": costales_por_tanque,
    }
