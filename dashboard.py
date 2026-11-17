"""Dashboard del simulador agrícola multiagente (Streamlit).

Ejecutar con:

    streamlit run dashboard.py

Lee los resultados de ``experimentos.py`` (``resultados/experimentos.csv`` y
``resultados/runs/*.json``) y ofrece:

* Comparación de métricas entre variantes de cada bloque experimental.
* Distribuciones por repetición (variabilidad ante el azar).
* Reproducción animada del mapa 2D de una corrida concreta.
* Tabla de datos crudos descargable.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent
RESULTADOS = RAIZ / "resultados"

# Un color por variante, consistente en todas las gráficas
PALETA = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
]

COLORES_AGENTE = [
    "#1f77b4", "#17becf", "#e377c2", "#ffffff",
    "#ff7f0e", "#ffff00", "#9467bd", "#2ca02c",
]

METRICAS = {
    "costo_total": "Costo total (MXN)",
    "ticks": "Ticks (tiempo)",
    "combustible_l": "Combustible (L)",
    "colisiones": "Colisiones entre tractores",
    "ratio_repeticion": "Fracción de pasos repetidos",
    "pasos": "Pasos totales",
    "cobertura": "Cobertura del terreno",
}

PREGUNTAS = {
    "terreno": "¿Cuánto encarece el relieve la misma tarea?",
    "flota": "¿Cuántos tractores conviene mandar antes de que se estorben?",
    "obstaculos": "¿Cuánto degrada un terreno más fragmentado el recorrido?",
    "semillas": "¿Cuánto cuesta reabastecerse muchas veces?",
}


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cargar_csv(ruta: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(ruta)


@st.cache_data(show_spinner=False)
def cargar_corrida(ruta: str, mtime: float) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def nombres_variantes(df: pd.DataFrame) -> list[str]:
    """Ordena las variantes por su valor numérico cuando lo hay."""
    variantes = list(dict.fromkeys(df["variante"]))

    def llave(nombre: str):
        valor = nombre.split("=")[-1]
        try:
            return (0, float(valor), nombre)
        except ValueError:
            return (1, 0.0, nombre)

    return sorted(variantes, key=llave)


# ---------------------------------------------------------------------------
# Gráficas
# ---------------------------------------------------------------------------
def grafica_barras(df: pd.DataFrame, metrica: str) -> plt.Figure:
    promedios = df.groupby("variante")[metrica].mean().reindex(nombres_variantes(df)).dropna()
    errores = df.groupby("variante")[metrica].std().reindex(promedios.index).fillna(0)

    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=130)
    colores = [PALETA[i % len(PALETA)] for i in range(len(promedios))]
    barras = ax.bar(promedios.index, promedios.values, yerr=errores.values,
                    capsize=4, color=colores, edgecolor="#222222", linewidth=0.6)
    ax.bar_label(barras, fmt="%.1f", fontsize=8, padding=3)
    ax.set_ylabel(METRICAS[metrica])
    ax.set_xlabel("Variante")
    ax.grid(axis="y", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    return fig


def grafica_caja(df: pd.DataFrame, metrica: str) -> plt.Figure:
    orden = nombres_variantes(df)
    datos = [df[df["variante"] == v][metrica].values for v in orden]

    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=130)
    caja = ax.boxplot(datos, tick_labels=orden, patch_artist=True, widths=0.55)
    for i, parche in enumerate(caja["boxes"]):
        parche.set_facecolor(PALETA[i % len(PALETA)])
        parche.set_alpha(0.75)
    for mediana in caja["medians"]:
        mediana.set_color("#111111")
    ax.set_ylabel(METRICAS[metrica])
    ax.set_xlabel("Variante")
    ax.grid(axis="y", alpha=0.25)
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    return fig


def grafica_compuesta(df: pd.DataFrame) -> plt.Figure:
    """Costo y colisiones por variante en un mismo panel (doble eje)."""
    orden = nombres_variantes(df)
    costo = df.groupby("variante")["costo_total"].mean().reindex(orden)
    colisiones = df.groupby("variante")["colisiones"].sum().reindex(orden)

    fig, ax1 = plt.subplots(figsize=(7.5, 3.6), dpi=130)
    ax1.bar(orden, costo.values, color=PALETA[0], alpha=0.85, label="Costo total")
    ax1.set_ylabel("Costo total (MXN)", color=PALETA[0])
    ax1.tick_params(axis="y", labelcolor=PALETA[0])

    ax2 = ax1.twinx()
    ax2.plot(orden, colisiones.values, color=PALETA[3], marker="o", linewidth=2,
             label="Colisiones")
    ax2.set_ylabel("Colisiones (suma)", color=PALETA[3])
    ax2.tick_params(axis="y", labelcolor=PALETA[3])

    ax1.grid(axis="y", alpha=0.25)
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Mapa 2D animado
# ---------------------------------------------------------------------------
def dibujar_mapa(corrida: dict, indice: int) -> plt.Figure:
    elevacion = np.array(corrida["elevation_map"], dtype=float)
    obstaculos = np.array(corrida["obstacle_map"], dtype=int)
    frames = corrida["frames"]
    frame = frames[min(indice, len(frames) - 1)]

    # Sembrado acumulado hasta el tick actual
    sembradas = np.zeros_like(obstaculos, dtype=float)
    for previo in frames[:min(indice, len(frames) - 1) + 1]:
        for celda in previo.get("planted_cells", []):
            sembradas[celda["x"], celda["y"]] = 1.0

    fig, ax = plt.subplots(figsize=(6.2, 6.2), dpi=130)
    # La matriz es [x][y]; para dibujar se transpone (filas = y)
    ax.imshow(elevacion.T, origin="lower", cmap="YlGn", alpha=0.85,
              extent=(-0.5, elevacion.shape[0] - 0.5, -0.5, elevacion.shape[1] - 0.5))

    ys, xs = np.nonzero(sembradas.T)
    ax.scatter(xs, ys, marker="s", s=90, color="#ffd400", edgecolor="#a07c00",
               linewidth=0.4, label="Sembrada", zorder=2)

    ys, xs = np.nonzero(obstaculos.T)
    ax.scatter(xs, ys, marker="X", s=90, color="#333333", label="Obstáculo", zorder=3)

    depot = (0, 0)
    ax.scatter([depot[0]], [depot[1]], marker="s", s=170, facecolor="none",
               edgecolor="#0044cc", linewidth=2.2, label="Depósito", zorder=4)

    for i, agente in enumerate(frame.get("agents", [])):
        x, y = agente["pos"]
        ax.scatter([x], [y], s=150, color=COLORES_AGENTE[i % len(COLORES_AGENTE)],
                   edgecolor="black", linewidth=1.1, zorder=5,
                   label=f"Tractor {agente['id']}")

    ax.set_xlim(-0.5, elevacion.shape[0] - 0.5)
    ax.set_ylim(-0.5, elevacion.shape[1] - 0.5)
    ax.set_xticks(range(0, elevacion.shape[0], max(1, elevacion.shape[0] // 10)))
    ax.set_yticks(range(0, elevacion.shape[1], max(1, elevacion.shape[1] // 10)))
    ax.set_xlabel("x  (celdas)")
    ax.set_ylabel("y  (celdas)")
    ax.set_title(
        f"Tick {frame['tick']} · sin sembrar: {frame.get('remaining_cells', '?')} "
        f"· {corrida['variante']} (semilla {corrida['semilla']})",
        fontsize=10,
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8,
              framealpha=0.95, borderaxespad=0.2)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Simulador agrícola multiagente", layout="wide")
    st.title("🌱 Simulador agrícola multiagente")
    st.caption(
        "John Deere · optimización de rutas de siembra · "
        "Python decide, Unity/Streamlit visualizan"
    )

    csv_ruta = RESULTADOS / "experimentos.csv"
    if not csv_ruta.exists():
        st.error(
            "No encuentro `resultados/experimentos.csv`.\n\n"
            "Ejecuta primero:  `python experimentos.py`"
        )
        return

    df = cargar_csv(str(csv_ruta), csv_ruta.stat().st_mtime)

    # -------------------- barra lateral --------------------
    with st.sidebar:
        st.header("Parámetros del experimento")
        escenarios = list(dict.fromkeys(df["escenario"]))
        escenario = st.selectbox("Bloque experimental", escenarios)
        sub = df[df["escenario"] == escenario]

        metrica = st.selectbox(
            "Métrica a comparar",
            list(METRICAS),
            format_func=lambda k: METRICAS[k],
        )

        st.divider()
        st.metric("Corridas en el bloque", len(sub))
        st.metric("Repeticiones por variante", sub["repeticion"].nunique())
        st.caption(f"Grid {int(df['grid'].iloc[0])}×{int(df['grid'].iloc[0])} celdas · "
                   f"{len(df)} corridas totales")

    st.info(f"**{escenario.capitalize()}** — {PREGUNTAS.get(escenario, '')}")

    # -------------------- KPIs --------------------
    mejor = sub.groupby("variante")["costo_total"].mean().idxmin()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Costo promedio", f"${sub['costo_total'].mean():,.0f}")
    c2.metric("Mejor variante", mejor, f"${sub['costo_total'].mean() - sub[sub['variante']==mejor]['costo_total'].mean():,.0f} vs media")
    c3.metric("Colisiones totales", int(sub["colisiones"].sum()))
    c4.metric("Pasos repetidos", f"{sub['ratio_repeticion'].mean()*100:.1f}%")

    # -------------------- pestañas --------------------
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Comparación", "🗺️ Mapa 2D animado", "📈 Distribuciones", "🗃️ Datos"]
    )

    with tab1:
        st.subheader(f"{METRICAS[metrica]} por variante")
        st.pyplot(grafica_barras(sub, metrica))
        st.subheader("Costo vs colisiones")
        st.caption(
            "Más tractores acelera la siembra, pero dispara las colisiones: "
            "el cuello de botella es la coordinación, no la máquina."
        )
        st.pyplot(grafica_compuesta(sub))

    with tab2:
        carpeta = RESULTADOS / "runs"
        disponibles = sorted(carpeta.glob(f"{escenario}_*.json")) if carpeta.exists() else []
        if not disponibles:
            st.warning(
                "No hay fotogramas guardados. Vuelve a correr "
                "`python experimentos.py` sin `--sin-frames`."
            )
        else:
            elegido = st.selectbox("Corrida a reproducir", disponibles,
                                   format_func=lambda p: p.stem)
            corrida = cargar_corrida(str(elegido), elegido.stat().st_mtime)
            total = len(corrida["frames"])
            indice = st.slider("Tick", 0, total - 1, total - 1)
            st.pyplot(dibujar_mapa(corrida, indice))

            m = corrida["metrics"]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Ticks", m["ticks"])
            k2.metric("Combustible", f"{m['combustible_l']:.0f} L")
            k3.metric("Costo total", f"${m['costo_total']:,.0f}")
            k4.metric("Colisiones", m["colisiones"])

    with tab3:
        st.subheader(f"Variabilidad de {METRICAS[metrica]} entre repeticiones")
        st.caption("Cada caja son las 5 repeticiones con semillas distintas del mismo escenario.")
        st.pyplot(grafica_caja(sub, metrica))

    with tab4:
        st.subheader("Datos crudos")
        st.dataframe(sub.sort_values(["variante", "repeticion"]),
                     use_container_width=True, height=380)
        st.download_button(
            "Descargar CSV completo",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="experimentos.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
