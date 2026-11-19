"""Separa las 4 ruedas del tractor directo desde el GLB.

El modelo de Sketchfab tiene miles de nodos; las ruedas son los nodos bajos
y anchos de la zona de ejes. Este script los agrupa en 4 ruedas y escribe:

    tractor_cuerpo.obj
    rueda_0.obj .. rueda_3.obj

Uso:
    .venv/bin/python herramientas/separar_ruedas_glb.py ~/Downloads/john_deere_r8.glb
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import glb_a_obj as g

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "escenario" / "Assets" / "Modelos" / "JohnDeereR8"


def main() -> None:
    entrada = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else (
        Path.home() / "Downloads" / "john_deere_r8.glb"
    )

    gltf, binario = g.leer_glb(entrada)

    piezas = []

    def visitar(indice, matriz_padre):
        nodo = gltf["nodes"][indice]
        matriz = matriz_padre @ g.matriz_local(nodo)

        if "mesh" in nodo:
            for prim in gltf["meshes"][nodo["mesh"]].get("primitives", []):
                acc = gltf["accessors"][prim["attributes"]["POSITION"]]

                if "min" not in acc:
                    continue

                minimo = np.array(acc["min"])
                maximo = np.array(acc["max"])
                esquinas = np.array([
                    [x, y, z, 1]
                    for x in (minimo[0], maximo[0])
                    for y in (minimo[1], maximo[1])
                    for z in (minimo[2], maximo[2])
                ])
                mundo = (matriz @ esquinas.T).T[:, :3]
                piezas.append((indice, mundo.min(0), mundo.max(0)))

        for hijo in nodo.get("children", []):
            visitar(hijo, matriz)

    for raiz in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        visitar(raiz, np.eye(4))

    candidatos = []

    for indice, minimo, maximo in piezas:
        centro = (minimo + maximo) / 2
        tam = maximo - minimo

        if (18 < centro[0] < 26 and centro[1] < 5.8
                and -14 < centro[2] < -9.4 and max(tam) < 2.2):
            candidatos.append((indice, centro[0], centro[2]))

    print(f"nodos de rueda: {len(candidatos)}")

    puntos = np.array([[c[1], c[2]] for c in candidatos])
    centros = np.array([
        [puntos[:, 0].min(), puntos[:, 1].min()],
        [puntos[:, 0].max(), puntos[:, 1].min()],
        [puntos[:, 0].min(), puntos[:, 1].max()],
        [puntos[:, 0].max(), puntos[:, 1].max()],
    ])

    for _ in range(40):
        distancias = ((puntos[:, None, :] - centros[None, :, :]) ** 2).sum(2)
        etiquetas = distancias.argmin(1)

        for k in range(4):
            if (etiquetas == k).any():
                centros[k] = puntos[etiquetas == k].mean(0)

    grupos = {
        k: {indice for (indice, _, _), e in zip(candidatos, etiquetas) if e == k}
        for k in range(4)
    }

    todos = {indice for indice, _, _ in piezas}
    ruedas = set().union(*grupos.values())

    for k, nodos in grupos.items():
        g.convertir(entrada, CARPETA, nombre_salida=f"rueda_{k}",
                    nodos_incluidos=nodos)

    g.convertir(entrada, CARPETA, nombre_salida="tractor_cuerpo",
                nodos_excluidos=ruedas)


if __name__ == "__main__":
    main()
