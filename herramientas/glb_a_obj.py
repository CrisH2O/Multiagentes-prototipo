"""Convierte un modelo .glb (glTF binario) a .obj + .mtl + texturas.

Unity no importa .glb de forma nativa, pero si importa .obj. Este script lee
el GLB directamente (sin dependencias externas) y escribe:

    <salida>/<nombre>.obj
    <salida>/<nombre>.mtl
    <salida>/texturas/*.png|jpg

Uso:
    .venv/bin/python herramientas/glb_a_obj.py modelo.glb [carpeta_salida]

Si no se indica carpeta, escribe junto al .glb.
"""
from __future__ import annotations

import base64
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

COMPONENTES = {
    5120: np.int8,
    5121: np.uint8,
    5122: np.int16,
    5123: np.uint16,
    5125: np.uint32,
    5126: np.float32,
}

TAMANO_TIPO = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


# ---------------------------------------------------------------------------
# Lectura del GLB
# ---------------------------------------------------------------------------
def leer_glb(ruta: Path):
    datos = ruta.read_bytes()

    if len(datos) < 12:
        raise ValueError("El archivo no es un GLB valido.")

    magia, version, largo_total = struct.unpack_from("<III", datos, 0)

    if magia != 0x46546C67:
        raise ValueError("Falta la firma glTF en el archivo.")

    if version != 2:
        raise ValueError(f"Version glTF no soportada: {version}")

    offset = 12
    gltf = None
    binario = b""

    while offset < largo_total:
        largo_bloque, tipo = struct.unpack_from("<II", datos, offset)
        offset += 8
        contenido = datos[offset:offset + largo_bloque]
        offset += largo_bloque

        if tipo == 0x4E4F534A:      # JSON
            gltf = json.loads(contenido.decode("utf-8"))
        elif tipo == 0x004E4942:    # BIN
            binario = contenido

    if gltf is None:
        raise ValueError("El GLB no trae bloque JSON.")

    return gltf, binario


def leer_accessor(gltf, binario, indice):
    acc = gltf["accessors"][indice]
    cantidad = acc["count"]
    tipo = acc["type"]
    dtype = np.dtype(COMPONENTES[acc["componentType"]])
    elementos = TAMANO_TIPO[tipo]

    if "bufferView" not in acc:
        # Accessor sin datos: todo ceros
        return np.zeros((cantidad, elementos), dtype=dtype)

    vista = gltf["bufferViews"][acc["bufferView"]]
    base = vista.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = vista.get("byteStride", 0)
    paso = elementos * dtype.itemsize

    if stride and stride != paso:
        crudo = np.frombuffer(binario, dtype=np.uint8,
                              count=stride * cantidad, offset=base)
        crudo = crudo.reshape(cantidad, stride)[:, :paso].copy()
        arreglo = crudo.view(dtype).reshape(cantidad, elementos)
    else:
        arreglo = np.frombuffer(binario, dtype=dtype,
                                count=cantidad * elementos,
                                offset=base).reshape(cantidad, elementos)

    return arreglo


# ---------------------------------------------------------------------------
# Transformaciones de nodos
# ---------------------------------------------------------------------------
def cuaternion_a_matriz(x, y, z, w):
    norma = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / norma, y / norma, z / norma, w / norma

    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def matriz_local(nodo):
    if "matrix" in nodo:
        # glTF guarda la matriz por columnas
        return np.array(nodo["matrix"], dtype=np.float64).reshape(4, 4).T

    traslacion = np.array(nodo.get("translation", [0, 0, 0]), dtype=np.float64)
    rotacion = nodo.get("rotation", [0, 0, 0, 1])
    escala = np.array(nodo.get("scale", [1, 1, 1]), dtype=np.float64)

    matriz = np.eye(4)
    matriz[:3, :3] = cuaternion_a_matriz(*rotacion) @ np.diag(escala)
    matriz[:3, 3] = traslacion
    return matriz


# ---------------------------------------------------------------------------
# Materiales y texturas
# ---------------------------------------------------------------------------
def nombre_material(gltf, indice):
    if indice is None or "materials" not in gltf:
        return "material"

    material = gltf["materials"][indice]
    return (material.get("name") or f"material_{indice}").strip().replace(" ", "_")


def extraer_textura(gltf, binario, indice_material, carpeta_texturas: Path):
    """Devuelve el nombre de archivo de la textura base, o None."""
    materiales = gltf.get("materials") or []

    if indice_material is None or indice_material >= len(materiales):
        return None

    material = materiales[indice_material]
    pbr = material.get("pbrMetallicRoughness", {})
    info = pbr.get("baseColorTexture")

    if not info:
        return None

    texturas = gltf.get("textures") or []
    imagenes = gltf.get("images") or []
    indice_textura = info.get("index", -1)

    if indice_textura < 0 or indice_textura >= len(texturas):
        return None

    fuente = texturas[indice_textura].get("source", -1)

    if fuente < 0 or fuente >= len(imagenes):
        return None

    imagen = imagenes[fuente]
    extension = ".png"

    if imagen.get("mimeType", "").endswith("jpeg"):
        extension = ".jpg"

    nombre = f"textura_{indice_material}{extension}"
    destino = carpeta_texturas / nombre

    if destino.exists():
        return nombre

    if "bufferView" in imagen:
        vista = gltf["bufferViews"][imagen["bufferView"]]
        base = vista.get("byteOffset", 0)
        datos = binario[base:base + vista["byteLength"]]
    elif "uri" in imagen:
        uri = imagen["uri"]

        if uri.startswith("data:"):
            datos = base64.b64decode(uri.split(",", 1)[1])
        else:
            return None
    else:
        return None

    destino.write_bytes(datos)
    return nombre


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------
def convertir(ruta_entrada: Path, carpeta_salida: Path,
              region=None, nombre_salida: str | None = None,
              max_tamano: float | None = None) -> None:
    gltf, binario = leer_glb(ruta_entrada)

    requeridos = gltf.get("extensionsRequired", [])

    if "KHR_draco_mesh_compression" in requeridos:
        raise ValueError(
            "El modelo usa Draco y no se puede convertir sin librerias extra."
        )

    carpeta_salida.mkdir(parents=True, exist_ok=True)
    carpeta_texturas = carpeta_salida / "texturas"
    carpeta_texturas.mkdir(exist_ok=True)

    nombre_base = nombre_salida or ruta_entrada.stem

    vertices = []
    normales = []
    uvs = []
    caras = []          # (material, [indices 1-based])
    materiales = {}     # indice -> nombre

    def visitar(indice, matriz_padre):
        nodo = gltf["nodes"][indice]
        matriz = matriz_padre @ matriz_local(nodo)

        if "mesh" in nodo:
            procesar_malla(nodo["mesh"], matriz)

        for hijo in nodo.get("children", []):
            visitar(hijo, matriz)

    def procesar_malla(indice_malla, matriz):
        malla = gltf["meshes"][indice_malla]

        for primitiva in malla.get("primitives", []):
            if "KHR_draco_mesh_compression" in primitiva.get("extensions", {}):
                raise ValueError("Primitiva comprimida con Draco: no soportada.")

            atributos = primitiva["attributes"]

            if "POSITION" not in atributos:
                continue

            posiciones = leer_accessor(gltf, binario, atributos["POSITION"]).astype(np.float64)

            # Filtro opcional por region (para sacar una pieza de una escena)
            if region is not None:
                centro_local = (posiciones.min(axis=0) + posiciones.max(axis=0)) / 2.0
                centro_mundo = (matriz @ np.array([
                    centro_local[0], centro_local[1], centro_local[2], 1.0
                ]))[:3]

                xmin, xmax, zmin, zmax = region

                if not (xmin <= centro_mundo[0] <= xmax and
                        zmin <= centro_mundo[2] <= zmax):
                    continue

            if max_tamano is not None:
                tamano_local = posiciones.max(axis=0) - posiciones.min(axis=0)

                if float(np.max(tamano_local)) > max_tamano:
                    continue

            # A mundo
            homogeneas = np.concatenate(
                [posiciones, np.ones((posiciones.shape[0], 1))], axis=1
            )
            mundo = (matriz @ homogeneas.T).T[:, :3]

            if "NORMAL" in atributos:
                normal = leer_accessor(gltf, binario, atributos["NORMAL"]).astype(np.float64)
                normal = normal @ np.linalg.inv(matriz[:3, :3]).T
            else:
                normal = np.zeros_like(mundo)

            uv = (leer_accessor(gltf, binario, atributos["TEXCOORD_0"]).astype(np.float64)
                  if "TEXCOORD_0" in atributos
                  else np.zeros((posiciones.shape[0], 2)))

            base = len(vertices) + 1

            vertices.extend(mundo.tolist())
            normales.extend(normal.tolist())
            uvs.extend(uv.tolist())

            if "indices" in primitiva:
                indices = leer_accessor(gltf, binario, primitiva["indices"]).reshape(-1).astype(np.int64)
            else:
                indices = np.arange(posiciones.shape[0], dtype=np.int64)

            indice_material = primitiva.get("material")
            clave = indice_material if indice_material is not None else -1

            if clave not in materiales:
                materiales[clave] = nombre_material(gltf, indice_material)

            for i in range(0, len(indices) - 2, 3):
                caras.append((
                    materiales[clave],
                    [base + int(indices[i]),
                     base + int(indices[i + 1]),
                     base + int(indices[i + 2])],
                ))

    escenas = gltf.get("scenes") or []
    indice_escena = gltf.get("scene", 0)

    if escenas:
        for raiz in escenas[indice_escena].get("nodes", []):
            visitar(raiz, np.eye(4))
    else:
        for indice in range(len(gltf.get("nodes", []))):
            visitar(indice, np.eye(4))

    if not vertices:
        raise ValueError("El modelo no tiene geometria.")

    # --- MTL ---
    lineas_mtl = []
    ruta_mtl = carpeta_salida / f"{nombre_base}.mtl"

    for clave, nombre in materiales.items():
        lineas_mtl.append(f"newmtl {nombre}")

        color = [0.7, 0.7, 0.7]
        alfa = 1.0

        if clave >= 0 and "materials" in gltf:
            material = gltf["materials"][clave]
            factor = material.get("pbrMetallicRoughness", {}).get("baseColorFactor")

            if factor:
                color = factor[:3]
                alfa = factor[3] if len(factor) > 3 else 1.0

        textura = extraer_textura(gltf, binario, clave if clave >= 0 else None,
                                  carpeta_texturas)

        lineas_mtl.append(f"Kd {color[0]:.4f} {color[1]:.4f} {color[2]:.4f}")

        if textura:
            lineas_mtl.append(f"map_Kd texturas/{textura}")

        lineas_mtl.append(f"d {alfa:.4f}")
        lineas_mtl.append("Ka 0.0 0.0 0.0")
        lineas_mtl.append("Ks 0.2 0.2 0.2")
        lineas_mtl.append("Ns 30.0")
        lineas_mtl.append("")

    ruta_mtl.write_text("\n".join(lineas_mtl), encoding="utf-8")

    # --- OBJ ---
    ruta_obj = carpeta_salida / f"{nombre_base}.obj"
    lineas = [
        f"# Convertido desde {ruta_entrada.name}",
        "# Ejes: glTF (Y arriba). Unity invierte X al importar OBJ.",
        f"mtllib {ruta_mtl.name}",
    ]

    for x, y, z in vertices:
        lineas.append(f"v {x:.5f} {y:.5f} {z:.5f}")

    for u, v in uvs:
        lineas.append(f"vt {u:.6f} {v:.6f}")

    for x, y, z in normales:
        lineas.append(f"vn {x:.5f} {y:.5f} {z:.5f}")

    material_actual = None

    for material, indices in caras:
        if material != material_actual:
            lineas.append(f"usemtl {material}")
            material_actual = material

        linea = "f " + " ".join(
            f"{i}/{i}/{i}" for i in indices
        )
        lineas.append(linea)

    ruta_obj.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    minimo = np.min(vertices, axis=0)
    maximo = np.max(vertices, axis=0)

    print(f"OK  {ruta_obj}")
    print(f"    vertices={len(vertices)}  triangulos={len(caras)}  "
          f"materiales={len(materiales)}")
    print(f"    caja: min={minimo.round(3).tolist()} max={maximo.round(3).tolist()}")
    print(f"    tamano={((maximo - minimo)).round(3).tolist()}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: glb_a_obj.py modelo.glb [carpeta_salida]")
        raise SystemExit(1)

    entrada = Path(sys.argv[1]).expanduser()

    if not entrada.exists():
        print(f"No existe: {entrada}")
        raise SystemExit(1)

    salida = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else entrada.parent

    region = None
    nombre = None
    resto = sys.argv[3:]

    if "--region" in resto:
        i = resto.index("--region")
        region = tuple(float(v) for v in resto[i + 1:i + 5])

    if "--nombre" in resto:
        i = resto.index("--nombre")
        nombre = resto[i + 1]

    max_tamano = None

    if "--max-tamano" in resto:
        i = resto.index("--max-tamano")
        max_tamano = float(resto[i + 1])

    convertir(entrada, salida, region=region, nombre_salida=nombre,
              max_tamano=max_tamano)


if __name__ == "__main__":
    main()
