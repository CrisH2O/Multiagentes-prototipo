"""Exporta las figuras del análisis a PNG (para informe o presentación).

Lee ``resultados/experimentos.csv`` y escribe ``resultados/figuras/*.png``.

    python figuras.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd

RAIZ = Path(__file__).resolve().parent
RESULTADOS = RAIZ / "resultados"

PALETA = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

ETIQUETAS = {
    "terreno": "Terreno",
    "flota": "Número de tractores",
    "obstaculos": "Obstáculos",
    "costales": "Costales por tanque",
    "estrategia": "Estrategia de ruteo",
}


def ordenar(df: pd.DataFrame) -> list[str]:
    variantes = list(dict.fromkeys(df["variante"]))

    def llave(nombre: str):
        valor = nombre.split("=")[-1]
        try:
            return (0, float(valor), nombre)
        except ValueError:
            return (1, 0.0, nombre)

    return sorted(variantes, key=llave)


def figura_bloque(df: pd.DataFrame, escenario: str, salida: Path) -> Path:
    """Barras de costo + línea de colisiones para un bloque experimental."""
    sub = df[df["escenario"] == escenario]
    orden = ordenar(sub)
    costo = sub.groupby("variante")["costo_total"].mean().reindex(orden)
    error = sub.groupby("variante")["costo_total"].std().reindex(orden).fillna(0)
    colisiones = sub.groupby("variante")["colisiones"].sum().reindex(orden)

    fig, ax1 = plt.subplots(figsize=(8, 4.2), dpi=150)
    barras = ax1.bar(orden, costo.values, yerr=error.values, capsize=4,
                     color=PALETA[0], alpha=0.88, edgecolor="#222", linewidth=0.6)
    ax1.bar_label(barras, fmt="$%.0f", fontsize=8, padding=3,
                  bbox=dict(facecolor="white", alpha=0.8, edgecolor="none", pad=0.6))
    ax1.set_ylabel("Costo total (MXN)", color=PALETA[0])
    ax1.tick_params(axis="y", labelcolor=PALETA[0])
    ax1.set_xlabel(ETIQUETAS.get(escenario, escenario))
    ax1.grid(axis="y", alpha=0.25)
    ax1.spines[["top"]].set_visible(False)

    ax2 = ax1.twinx()
    ax2.plot(orden, colisiones.values, color=PALETA[3], marker="o", linewidth=2,
             label="Colisiones")
    ax2.set_ylabel("Colisiones (suma de 5 repeticiones)", color=PALETA[3])
    ax2.tick_params(axis="y", labelcolor=PALETA[3])
    ax2.spines[["top"]].set_visible(False)

    plt.xticks(rotation=15, ha="right")
    fig.tight_layout()
    destino = salida / f"{escenario}_costo_colisiones.png"
    fig.savefig(destino)
    plt.close(fig)
    return destino


def figura_eficiencia(df: pd.DataFrame, salida: Path) -> Path:
    """Costo por celda sembrada en los 4 bloques: qué variable pesa más."""
    filas = []
    for escenario in df["escenario"].unique():
        sub = df[df["escenario"] == escenario]
        for variante, grupo in sub.groupby("variante"):
            eficiencia = (grupo["costo_total"] / grupo["celdas_sembradas"]).mean()
            filas.append({"escenario": escenario, "variante": variante,
                          "costo_por_celda": eficiencia})

    tabla = pd.DataFrame(filas)
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    for i, (escenario, grupo) in enumerate(tabla.groupby("escenario")):
        grupo = grupo.set_index("variante").reindex(ordenar(df[df["escenario"] == escenario]))
        ax.plot(range(len(grupo)), grupo["costo_por_celda"].values, marker="o",
                linewidth=2, color=PALETA[i % len(PALETA)],
                label=ETIQUETAS.get(escenario, escenario))
        ax.set_xticks(range(len(grupo)))
        ax.set_xticklabels(grupo.index, rotation=20, ha="right", fontsize=8)

    ax.set_ylabel("Costo por celda sembrada (MXN)")
    ax.set_xlabel("Variante (cada bloque con su propia escala)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    destino = salida / "eficiencia_costo_por_celda.png"
    fig.savefig(destino)
    plt.close(fig)
    return destino


def main() -> None:
    csv_ruta = RESULTADOS / "experimentos.csv"
    if not csv_ruta.exists():
        raise SystemExit("Falta resultados/experimentos.csv: corre `python experimentos.py`")

    df = pd.read_csv(csv_ruta)
    salida = RESULTADOS / "figuras"
    salida.mkdir(parents=True, exist_ok=True)

    generadas = [figura_eficiencia(df, salida)]
    for escenario in ("terreno", "flota", "obstaculos", "costales", "estrategia"):
        generadas.append(figura_bloque(df, escenario, salida))

    for ruta in generadas:
        print("figura:", ruta.relative_to(RAIZ))


if __name__ == "__main__":
    main()
