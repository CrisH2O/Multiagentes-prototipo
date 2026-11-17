"""Genera las figuras del reporte.

Cada figura está pensada para imprimirse en el documento: etiquetas legibles,
barras de error, métricas por hectárea sembrada y un solo mensaje por gráfica.

    python figuras.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parent
RESULTADOS = RAIZ / "resultados"
SALIDA = RESULTADOS / "figuras"

AZUL = "#1f4e79"
NARANJA = "#d9822b"
VERDE = "#2e7d32"
GRIS = "#7a7a7a"

# Nombres que se muestran en el reporte
ETIQUETAS = {
    "greedy": "Planificador",
    "zigzag": "Zigzag (base)",
    "plano": "Plano",
    "colinas": "Medio",
    "montanoso": "Montañoso",
}


def cargar() -> pd.DataFrame:
    csv = RESULTADOS / "experimentos.csv"
    if not csv.exists():
        raise SystemExit("Falta resultados/experimentos.csv: corre `python experimentos.py`")
    return pd.read_csv(csv)


def valor(variante: str) -> str:
    """'n_agentes=5' -> '5'; 'greedy' -> 'Planificador'."""
    bruto = variante.split("=")[-1]
    return ETIQUETAS.get(bruto, bruto)


def orden(bloque: pd.DataFrame) -> list[str]:
    variantes = list(dict.fromkeys(bloque["variante"]))

    def llave(nombre: str):
        valor_bruto = nombre.split("=")[-1]
        try:
            return (0, float(valor_bruto), nombre)
        except ValueError:
            orden_manual = {"greedy": 0, "zigzag": 1}
            return (1, orden_manual.get(valor_bruto, 99), nombre)

    return sorted(variantes, key=llave)


def estilo(ax):
    ax.grid(axis="y", color="#dddddd", linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.spines["left"].set_color("#888888")
    ax.spines["bottom"].set_color("#888888")


def media_error(bloque: pd.DataFrame, metrica: str, ordenados: list[str]):
    medias = bloque.groupby("variante")[metrica].mean().reindex(ordenados)
    errores = bloque.groupby("variante")[metrica].std().reindex(ordenados).fillna(0)
    return medias.values, errores.values


# ---------------------------------------------------------------------------
# 1. Estrategia: planificador vs zigzag
# ---------------------------------------------------------------------------
def fig_estrategia(df: pd.DataFrame) -> Path:
    bloque = df[df["escenario"] == "estrategia"]
    ordenados = orden(bloque)
    nombres = [valor(v) for v in ordenados]

    ticks, err_ticks = media_error(bloque, "ticks", ordenados)
    costo, err_costo = media_error(bloque, "costo_ha_sembrada", ordenados)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4), dpi=160)
    colores = [AZUL, NARANJA]

    barras = ax1.bar(nombres, ticks, yerr=err_ticks, capsize=5,
                     color=colores, edgecolor="#333333", linewidth=0.7)
    ax1.bar_label(barras, fmt="%.0f", fontsize=10, padding=4)
    ax1.set_ylabel("Ticks (1 tick ≈ 5.4 s)")
    ax1.set_title("Tiempo de siembra", fontsize=11)
    ax1.set_ylim(0, max(ticks) * 1.25)
    estilo(ax1)

    barras = ax2.bar(nombres, costo, yerr=err_costo, capsize=5,
                     color=colores, edgecolor="#333333", linewidth=0.7)
    ax2.bar_label(barras, fmt="$%.0f", fontsize=10, padding=4)
    ax2.set_ylabel("Costo por hectárea sembrada (MXN)")
    ax2.set_title("Costo", fontsize=11)
    ax2.set_ylim(0, max(costo) * 1.25)
    estilo(ax2)

    ahorro_t = (ticks[1] - ticks[0]) / ticks[1] * 100
    ahorro_c = (costo[1] - costo[0]) / costo[1] * 100
    fig.suptitle(
        f"Planificador vs ruta base: {ahorro_t:.0f}% menos tiempo y "
        f"{ahorro_c:.1f}% menos costo",
        fontsize=11, y=1.00)
    fig.tight_layout()
    destino = SALIDA / "fig_estrategia.png"
    fig.savefig(destino, bbox_inches="tight")
    plt.close(fig)
    return destino


# ---------------------------------------------------------------------------
# 2. Tamaño de flota
# ---------------------------------------------------------------------------
def fig_flota(df: pd.DataFrame) -> Path:
    bloque = df[df["escenario"] == "flota"]
    ordenados = orden(bloque)
    nombres = [valor(v) for v in ordenados]

    ticks, err_ticks = media_error(bloque, "ticks", ordenados)
    costo, err_costo = media_error(bloque, "costo_ha_sembrada", ordenados)
    colisiones = bloque.groupby("variante")["colisiones"].sum().reindex(ordenados).values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4), dpi=160)

    barras = ax1.bar(nombres, ticks, yerr=err_ticks, capsize=5,
                     color=AZUL, edgecolor="#333333", linewidth=0.7)
    ax1.bar_label(barras, fmt="%.0f", fontsize=9, padding=4)
    ax1.set_xlabel("Tractores")
    ax1.set_ylabel("Ticks")
    ax1.set_title("Tiempo total", fontsize=11)
    ax1.set_ylim(0, max(ticks) * 1.25)
    estilo(ax1)

    ax2.plot(nombres, costo, marker="o", linewidth=2.2, color=VERDE,
             markersize=8, label="Costo por ha")
    ax2.set_xlabel("Tractores")
    ax2.set_ylabel("Costo por hectárea sembrada (MXN)")
    ax2.set_title("Costo (casi constante)", fontsize=11)
    ax2.set_ylim(min(costo) * 0.97, max(costo) * 1.02)
    ax2.set_xlim(-0.4, len(nombres) - 0.6)
    estilo(ax2)

    for i, total in enumerate(colisiones):
        if total > 0:
            ax2.annotate(f"{int(total)} colisiones", (i, costo[i]),
                         textcoords="offset points", xytext=(0, -18),
                         ha="center", fontsize=8, color="#b03030")

    ax1.set_xticks(range(len(nombres)))
    ax1.set_xticklabels(nombres)
    fig.suptitle("Más tractores compran tiempo, no dinero", fontsize=11, y=1.00)
    fig.tight_layout()
    destino = SALIDA / "fig_flota.png"
    fig.savefig(destino, bbox_inches="tight")
    plt.close(fig)
    return destino


# ---------------------------------------------------------------------------
# 3. Capacidad del tanque (costales)
# ---------------------------------------------------------------------------
def fig_costales(df: pd.DataFrame) -> Path:
    bloque = df[df["escenario"] == "costales"]
    ordenados = orden(bloque)
    nombres = [valor(v) for v in ordenados]

    costo, err_costo = media_error(bloque, "costo_ha_sembrada", ordenados)
    litros, err_litros = media_error(bloque, "combustible_ha", ordenados)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4), dpi=160)

    barras = ax1.bar(nombres, costo, yerr=err_costo, capsize=5,
                     color=AZUL, edgecolor="#333333", linewidth=0.7)
    ax1.bar_label(barras, fmt="$%.0f", fontsize=9, padding=4)
    ax1.set_xlabel("Costales por tanque (1 = 1 ha)")
    ax1.set_ylabel("Costo por hectárea sembrada (MXN)")
    ax1.set_title("Costo", fontsize=11)
    ax1.set_ylim(0, max(costo) * 1.22)
    estilo(ax1)

    barras = ax2.bar(nombres, litros, yerr=err_litros, capsize=5,
                     color=NARANJA, edgecolor="#333333", linewidth=0.7)
    ax2.bar_label(barras, fmt="%.1f", fontsize=9, padding=4)
    ax2.axhline(8.6, color="#b03030", linestyle="--", linewidth=1.2)
    ax2.text(-0.35, 8.6, "8.6 L/ha (literatura)", va="bottom", ha="left",
             fontsize=8, color="#b03030",
             bbox=dict(facecolor="white", alpha=0.85, edgecolor="none",
                       pad=1.5))
    ax2.set_xlabel("Costales por tanque (1 = 1 ha)")
    ax2.set_ylabel("Diésel por hectárea (L/ha)")
    ax2.set_title("Combustible", fontsize=11)
    ax2.set_ylim(0, max(litros) * 1.25)
    estilo(ax2)

    fig.suptitle("El tanque de un costal es el punto de equilibrio",
                 fontsize=11, y=1.00)
    fig.tight_layout()
    destino = SALIDA / "fig_costales.png"
    fig.savefig(destino, bbox_inches="tight")
    plt.close(fig)
    return destino


# ---------------------------------------------------------------------------
# 4. Terreno
# ---------------------------------------------------------------------------
def fig_terreno(df: pd.DataFrame) -> Path:
    bloque = df[df["escenario"] == "terreno"]
    ordenados = ["terreno=plano", "terreno=colinas", "terreno=montanoso"]
    nombres = [valor(v) for v in ordenados]

    costo, err_costo = media_error(bloque, "costo_ha_sembrada", ordenados)
    litros, err_litros = media_error(bloque, "combustible_ha", ordenados)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4), dpi=160)

    # Puntos con barra de error: el eje está recortado porque la diferencia
    # es menor que la dispersión entre semillas.
    ax1.errorbar(nombres, costo, yerr=err_costo, fmt="o", color=AZUL,
                 markersize=10, capsize=6, linewidth=1.8, elinewidth=1.8)
    for i, c in enumerate(costo):
        ax1.annotate(f"${c:.0f}", (i, c), textcoords="offset points",
                     xytext=(0, 14), ha="center", fontsize=9,
                     bbox=dict(facecolor="white", alpha=0.85,
                               edgecolor="none", pad=1.5))
    ax1.set_ylabel("Costo por hectárea sembrada (MXN)")
    ax1.set_title("Costo", fontsize=11)
    ax1.set_ylim(min(costo) * 0.985, max(costo) * 1.012)
    ax1.set_xlim(-0.55, len(nombres) - 0.45)
    estilo(ax1)

    ax2.errorbar(nombres, litros, yerr=err_litros, fmt="o", color=NARANJA,
                 markersize=10, capsize=6, linewidth=1.8, elinewidth=1.8)
    for i, l in enumerate(litros):
        ax2.annotate(f"{l:.1f}", (i, l), textcoords="offset points",
                     xytext=(0, 14), ha="center", fontsize=9,
                     bbox=dict(facecolor="white", alpha=0.85,
                               edgecolor="none", pad=1.5))
    ax2.set_ylabel("Diésel por hectárea (L/ha)")
    ax2.set_title("Combustible", fontsize=11)
    ax2.set_ylim(min(litros) * 0.97, max(litros) * 1.06)
    ax2.set_xlim(-0.55, len(nombres) - 0.45)
    estilo(ax2)

    diferencia = (costo[2] - costo[0]) / costo[0] * 100
    fig.suptitle(
        f"El relieve casi no cambia el costo: {diferencia:.1f}% de plano a montañoso",
        fontsize=11, y=1.00)
    fig.tight_layout()
    destino = SALIDA / "fig_terreno.png"
    fig.savefig(destino, bbox_inches="tight")
    plt.close(fig)
    return destino


# ---------------------------------------------------------------------------
# 5. Obstáculos: la trampa del denominador
# ---------------------------------------------------------------------------
def fig_obstaculos(df: pd.DataFrame) -> Path:
    bloque = df[df["escenario"] == "obstaculos"]
    ordenados = orden(bloque)
    nombres = [valor(v) for v in ordenados]

    por_lote = bloque.groupby("variante")["costo_ha"].mean().reindex(ordenados).values
    por_sembrada = (bloque.groupby("variante")["costo_ha_sembrada"]
                    .mean().reindex(ordenados).values)

    x = np.arange(len(nombres))
    ancho = 0.38

    fig, ax = plt.subplots(figsize=(9, 4), dpi=160)
    b1 = ax.bar(x - ancho / 2, por_lote, ancho, label="Por hectárea del lote",
                color=GRIS, edgecolor="#333333", linewidth=0.7)
    b2 = ax.bar(x + ancho / 2, por_sembrada, ancho,
                label="Por hectárea sembrada", color=AZUL,
                edgecolor="#333333", linewidth=0.7)

    ax.bar_label(b1, fmt="$%.0f", fontsize=8, padding=3)
    ax.bar_label(b2, fmt="$%.0f", fontsize=8, padding=3)

    ax.set_xticks(x)
    ax.set_xticklabels(nombres)
    ax.set_xlabel("Obstáculos en el terreno")
    ax.set_ylabel("Costo (MXN por hectárea)")
    ax.set_ylim(0, max(por_lote.max(), por_sembrada.max()) * 1.2)
    ax.legend(fontsize=9, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.16), ncol=2)
    estilo(ax)
    ax.set_title(
        "Con más obstáculos el costo del lote baja, pero el costo "
        "por hectárea sembrada sube",
        fontsize=10)
    fig.tight_layout()
    destino = SALIDA / "fig_obstaculos.png"
    fig.savefig(destino, bbox_inches="tight")
    plt.close(fig)
    return destino


# ---------------------------------------------------------------------------
# 6. Variabilidad entre semillas
# ---------------------------------------------------------------------------
def fig_variabilidad(df: pd.DataFrame) -> Path:
    bloque = df[df["escenario"].isin(["flota", "estrategia"])]
    grupos, etiquetas = [], []
    colores = []

    for escenario in ("flota", "estrategia"):
        sub = bloque[bloque["escenario"] == escenario]
        for variante in orden(sub):
            grupos.append(sub[sub["variante"] == variante]["costo_ha_sembrada"].values)
            etiquetas.append(valor(variante))
            colores.append(AZUL if escenario == "flota" else NARANJA)

    fig, ax = plt.subplots(figsize=(9, 3.8), dpi=160)
    caja = ax.boxplot(grupos, patch_artist=True, widths=0.6)
    for parche, color in zip(caja["boxes"], colores):
        parche.set_facecolor(color)
        parche.set_alpha(0.7)
    for mediana in caja["medians"]:
        mediana.set_color("#111111")

    ax.set_xticklabels(etiquetas, rotation=20, ha="right")
    ax.set_ylabel("Costo por hectárea sembrada (MXN)")
    estilo(ax)
    ax.set_title(
        "Cada caja son 5 semillas distintas: la dispersión del costo "
        "es menor al 2%",
        fontsize=10)
    fig.tight_layout()
    destino = SALIDA / "fig_variabilidad.png"
    fig.savefig(destino, bbox_inches="tight")
    plt.close(fig)
    return destino


# ---------------------------------------------------------------------------
# 7. Mapa 2D de una corrida
# ---------------------------------------------------------------------------
def fig_mapa() -> Path:
    corridas = sorted((RESULTADOS / "runs").glob("estrategia_*.json"))
    if not corridas:
        raise SystemExit("No hay fotogramas: corre `python experimentos.py`")

    datos = json.loads(corridas[0].read_text(encoding="utf-8"))
    elevacion = np.array(datos["elevation_map"], dtype=float)
    obstaculos = np.array(datos["obstacle_map"], dtype=int)
    frames = datos["frames"]

    sembradas = np.zeros_like(obstaculos, dtype=float)
    for frame in frames:
        for celda in frame.get("planted_cells", []):
            sembradas[celda["x"], celda["y"]] = 1.0

    ultimo = frames[-1]

    fig, ax = plt.subplots(figsize=(6.4, 6.0), dpi=160)
    ax.imshow(elevacion.T, origin="lower", cmap="YlGn", alpha=0.8,
              extent=(-0.5, elevacion.shape[0] - 0.5,
                      -0.5, elevacion.shape[1] - 0.5))

    ys, xs = np.nonzero(sembradas.T)
    ax.scatter(xs, ys, marker="s", s=70, color="#ffd400",
               edgecolor="#9c7a00", linewidth=0.4, label="Sembrada", zorder=2)

    ys, xs = np.nonzero(obstaculos.T)
    ax.scatter(xs, ys, marker="o", s=70, color="#2e5d34",
               edgecolor="#1b3a20", linewidth=0.6, label="Obstáculo (árbol/piedra)",
               zorder=3)

    ax.scatter([0], [0], marker="s", s=180, facecolor="none",
               edgecolor="#0044cc", linewidth=2.2, label="Depósito", zorder=4)

    for i, agente in enumerate(ultimo["agents"]):
        x, y = agente["pos"]
        ax.scatter([x], [y], s=140, color="#d9822b", edgecolor="black",
                   linewidth=1.1, zorder=5, label="Tractor" if i == 0 else None)

    ax.set_xlim(-0.5, elevacion.shape[0] - 0.5)
    ax.set_ylim(-0.5, elevacion.shape[1] - 0.5)
    paso = max(1, elevacion.shape[0] // 8)
    ax.set_xticks(range(0, elevacion.shape[0], paso))
    ax.set_yticks(range(0, elevacion.shape[1], paso))
    ax.set_xlabel("x (celdas)")
    ax.set_ylabel("y (celdas)")
    ax.set_title(
        f"Corrida terminada en {ultimo['tick']} ticks · "
        f"{datos['variante']} · semilla {datos['semilla']}",
        fontsize=10)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8,
              framealpha=0.95, borderaxespad=0.2)
    fig.tight_layout()
    destino = SALIDA / "fig_mapa.png"
    fig.savefig(destino, bbox_inches="tight")
    plt.close(fig)
    return destino


def main() -> None:
    df = cargar()
    SALIDA.mkdir(parents=True, exist_ok=True)

    generadas = [
        fig_estrategia(df),
        fig_flota(df),
        fig_costales(df),
        fig_terreno(df),
        fig_obstaculos(df),
        fig_variabilidad(df),
        fig_mapa(),
    ]

    # Las figuras del esquema anterior ya no se usan
    for vieja in SALIDA.glob("*_costo_colisiones.png"):
        vieja.unlink()
    if (SALIDA / "eficiencia_costo_por_celda.png").exists():
        (SALIDA / "eficiencia_costo_por_celda.png").unlink()

    for ruta in generadas:
        print("figura:", ruta.relative_to(RAIZ))


if __name__ == "__main__":
    main()
