"""Separa las 4 ruedas del tractor de la carroceria.

El modelo del John Deere viene como UNA sola malla, asi que las ruedas no se
pueden girar por separado. Este script parte la malla en:

    tractor_cuerpo.obj     carroceria (sin ruedas)
    rueda_0.obj .. 3.obj   cada rueda por separado (mismo material)

Las ruedas se identifican por el material que ocupa la parte baja y ancha
del modelo y luego se agrupan por cuadrante (delantera/trasera, izquierda/
derecha).

Uso:
    .venv/bin/python herramientas/separar_ruedas.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "escenario" / "Assets" / "Modelos" / "JohnDeereR8"
ENTRADA = CARPETA / "tractor_r8.obj"
MATERIAL_RUEDAS = "ID4836"


def leer_obj(ruta: Path):
    vertices = []
    caras = []
    material = None

    for linea in ruta.read_text().splitlines():
        if linea.startswith("v "):
            vertices.append([float(v) for v in linea.split()[1:4]])
        elif linea.startswith("usemtl "):
            material = linea[7:].strip()
        elif linea.startswith("f "):
            indices = [int(p.split("/")[0]) - 1 for p in linea.split()[1:]]
            caras.append((material, indices))

    return np.array(vertices), caras


def escribir_obj(ruta: Path, vertices: np.ndarray, caras, mtl: str) -> None:
    usados = sorted({i for _, indices in caras for i in indices})
    mapa = {viejo: nuevo + 1 for nuevo, viejo in enumerate(usados)}

    lineas = [f"mtllib {mtl}", f"# {len(caras)} caras"]

    for i in usados:
        x, y, z = vertices[i]
        lineas.append(f"v {x:.5f} {y:.5f} {z:.5f}")

    material_actual = None

    for material, indices in caras:
        if material != material_actual:
            lineas.append(f"usemtl {material}")
            material_actual = material

        lineas.append("f " + " ".join(str(mapa[i]) for i in indices))

    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> None:
    vertices, caras = leer_obj(ENTRADA)
    print(f"caras totales: {len(caras)}  vertices: {len(vertices)}")

    indices_rueda = [
        numero for numero, (material, _) in enumerate(caras)
        if material == MATERIAL_RUEDAS
    ]

    if not indices_rueda:
        raise SystemExit(f"No hay caras con el material {MATERIAL_RUEDAS}")

    print(f"caras de ruedas: {len(indices_rueda)}")

    # Centro de cada cara de rueda para agrupar por cuadrante
    centros = np.array([
        vertices[caras[numero][1]].mean(axis=0) for numero in indices_rueda
    ])

    corte_x = (centros[:, 0].min() + centros[:, 0].max()) / 2.0
    corte_z = (centros[:, 2].min() + centros[:, 2].max()) / 2.0

    grupos = {0: [], 1: [], 2: [], 3: []}

    for posicion, numero in enumerate(indices_rueda):
        x, _, z = centros[posicion]
        clave = (0 if x < corte_x else 1) + (0 if z < corte_z else 2)
        grupos[clave].append(caras[numero])

    for clave, caras_rueda in grupos.items():
        if not caras_rueda:
            continue

        puntos = np.array([
            vertices[indices].mean(axis=0) for _, indices in caras_rueda
        ])

        minimo = puntos.min(axis=0)
        maximo = puntos.max(axis=0)

        escribir_obj(
            CARPETA / f"rueda_{clave}.obj",
            vertices,
            caras_rueda,
            "tractor_r8.mtl",
        )

        print(
            f"rueda_{clave}.obj: {len(caras_rueda)} caras | centro aproximado "
            f"{((minimo + maximo) / 2).round(2)} | radio aprox "
            f"{((maximo - minimo) / 2).max().round(2)}"
        )

    cuerpo = [
        (material, indices)
        for material, indices in caras
        if material != MATERIAL_RUEDAS
    ]

    escribir_obj(CARPETA / "tractor_cuerpo.obj", vertices, cuerpo, "tractor_r8.mtl")
    print(f"tractor_cuerpo.obj: {len(cuerpo)} caras")


if __name__ == "__main__":
    main()
