"""Genera los assets 3D del escenario Campo3D.

Produce, a partir de la MISMA elevación que usa el modelo multiagente
(`Agentes/escenarios.py`), los archivos que Unity importa como assets:

  escenario/Assets/Texturas/heightmap_colinas.png    Mapa de alturas (513x513)
  escenario/Assets/Texturas/cesped.png               Textura de pasto (tileable)
  escenario/Assets/Texturas/tierra.png               Textura de tierra (tileable)
  escenario/Assets/Modelos/Tractor.obj + .mtl        Malla importable del tractor
  escenario/Assets/StreamingAssets/payload_colinas.json  Payload que Unity manda a Python

Uso:
    .venv/bin/python herramientas/generar_assets_3d.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ASSETS = RAIZ / "escenario" / "Assets"
TEXTURAS = ASSETS / "Texturas"
MODELOS = ASSETS / "Modelos"
STREAMING = ASSETS / "StreamingAssets"

sys.path.insert(0, str(RAIZ / "Agentes"))
import escenarios  # noqa: E402

# ---------------------------------------------------------------------------
# Parametros del terreno (deben coincidir con Campo3DSceneBuilder.cs)
# ---------------------------------------------------------------------------
RESOLUCION = 513          # 2^n + 1, requerido por Unity Terrain
TAMANO_MUNDO = 1000.0     # metros de lado (1000 x 1000 m = 100 ha)
ALTURA_MAXIMA = 8.0       # metros entre el punto mas bajo y el mas alto
TERRENO = "colinas"
SEMILLA = 3
CUADRICULA = 40           # 40 x 40 celdas de 25 m = 100 ha
LADO_CELDA_M = 25.0
DEPOSITO = (-470.0, -470.0)   # esquina donde vive la bodega
ALTURA_PLATEAU = 0.12     # altura normalizada del area plana del deposito


# ---------------------------------------------------------------------------
# Ruido
# ---------------------------------------------------------------------------
def _ruido_tileable(n: int, celdas: int, rng: np.random.Generator) -> np.ndarray:
    """Ruido de valor en [0, 1] que se repite sin costuras."""
    rejilla = rng.random((celdas, celdas))

    xs = np.arange(n) * celdas / n
    i0 = np.floor(xs).astype(int) % celdas
    i1 = (i0 + 1) % celdas
    f = xs - np.floor(xs)
    f = f * f * (3.0 - 2.0 * f)

    fila0 = rejilla[i0][:, i0] * (1.0 - f) + rejilla[i0][:, i1] * f
    fila1 = rejilla[i1][:, i0] * (1.0 - f) + rejilla[i1][:, i1] * f

    return fila0 * (1.0 - f)[:, None] + fila1 * f[:, None]


def _ruido_fractal(n: int, rng: np.random.Generator, octavas=(4, 8, 16, 32)) -> np.ndarray:
    total = np.zeros((n, n))
    amplitud = 1.0
    suma = 0.0
    for celdas in octavas:
        total += _ruido_tileable(n, celdas, rng) * amplitud
        suma += amplitud
        amplitud *= 0.5
    return total / suma


# ---------------------------------------------------------------------------
# Mapa de alturas
# ---------------------------------------------------------------------------
def _remuestrear_bilineal(matriz: np.ndarray, n: int) -> np.ndarray:
    origen = matriz.shape[0]

    xs = np.linspace(0.0, origen - 1.0, n)
    i = np.clip(np.floor(xs).astype(int), 0, origen - 2)
    f = xs - i

    filas = matriz[i, :] * (1.0 - f)[:, None] + matriz[i + 1, :] * f[:, None]

    j = np.clip(np.floor(xs).astype(int), 0, origen - 2)
    g = xs - j

    return filas[:, j] * (1.0 - g)[None, :] + filas[:, j + 1] * g[None, :]


def _suavizar(matriz: np.ndarray, pasadas: int = 3) -> np.ndarray:
    """Desenfoque 3x3 repetido: quita el aspecto de bloques del muestreo."""
    salida = matriz.copy()

    for _ in range(pasadas):
        salida = (
            salida * 4.0
            + np.roll(salida, 1, axis=0) + np.roll(salida, -1, axis=0)
            + np.roll(salida, 1, axis=1) + np.roll(salida, -1, axis=1)
            + np.roll(np.roll(salida, 1, axis=0), 1, axis=1)
            + np.roll(np.roll(salida, 1, axis=0), -1, axis=1)
            + np.roll(np.roll(salida, -1, axis=0), 1, axis=1)
            + np.roll(np.roll(salida, -1, axis=0), -1, axis=1)
        ) / 12.0

    return salida


def generar_mapa_alturas(terreno: str = TERRENO) -> np.ndarray:
    elevacion = escenarios.generar_elevacion(terreno, CUADRICULA, SEMILLA)
    base = _suavizar(_remuestrear_bilineal(elevacion, RESOLUCION), pasadas=2)

    rng = np.random.default_rng(SEMILLA + 100)
    detalle = (_ruido_fractal(RESOLUCION, rng) - 0.5) * 0.035

    alturas = np.clip(base + detalle, 0.0, 1.0)

    # Area plana alrededor del deposito para la bodega y los tractores
    coordenadas = np.linspace(-TAMANO_MUNDO / 2.0, TAMANO_MUNDO / 2.0, RESOLUCION)
    xx, zz = np.meshgrid(coordenadas, coordenadas, indexing="xy")
    distancia = np.hypot(xx - DEPOSITO[0], zz - DEPOSITO[1])

    # 1 dentro de 35 m, 0 fuera de 55 m (cabe la bodega y los tractores)
    t = np.clip((distancia - 35.0) / 20.0, 0.0, 1.0)
    mascara = 1.0 - (t * t * (3.0 - 2.0 * t))

    alturas = alturas * (1.0 - mascara) + ALTURA_PLATEAU * mascara

    # Borde exterior plano: el terreno se une con el plano base del campo
    distancia_borde = np.minimum.reduce([
        xx + TAMANO_MUNDO / 2.0,
        TAMANO_MUNDO / 2.0 - xx,
        zz + TAMANO_MUNDO / 2.0,
        TAMANO_MUNDO / 2.0 - zz,
    ])
    borde = np.clip((distancia_borde - 20.0) / 40.0, 0.0, 1.0)
    borde = borde * borde * (3.0 - 2.0 * borde)

    return np.clip(alturas * borde + ALTURA_PLATEAU * (1.0 - borde), 0.0, 1.0)


# ---------------------------------------------------------------------------
# Texturas
# ---------------------------------------------------------------------------
def textura_cesped(n: int = 256) -> np.ndarray:
    rng = np.random.default_rng(11)
    fino = _ruido_fractal(n, rng, octavas=(32, 64, 96))
    medio = _ruido_tileable(n, 6, rng)

    base = np.array([0.30, 0.42, 0.17])
    variacion = (fino - 0.5) * 0.16 + (medio - 0.5) * 0.10

    imagen = base[None, None, :] + variacion[:, :, None]

    # Manchas amarillentas (pasto seco)
    seco = np.clip((_ruido_tileable(n, 4, rng) - 0.55) * 3.0, 0.0, 1.0)
    imagen = imagen * (1.0 - seco[:, :, None] * 0.45) + (
        np.array([0.52, 0.50, 0.24])[None, None, :] * seco[:, :, None] * 0.45
    )

    return np.clip(imagen, 0.0, 1.0)


def textura_tierra(n: int = 256) -> np.ndarray:
    rng = np.random.default_rng(23)
    fino = _ruido_fractal(n, rng, octavas=(16, 32, 64))
    medio = _ruido_tileable(n, 5, rng)

    base = np.array([0.36, 0.26, 0.16])
    variacion = (fino - 0.5) * 0.18 + (medio - 0.5) * 0.12

    imagen = base[None, None, :] + variacion[:, :, None]

    # Piedritas
    piedras = np.clip((_ruido_tileable(n, 96, rng) - 0.72) * 6.0, 0.0, 1.0)
    imagen = imagen * (1.0 - piedras[:, :, None] * 0.6) + (
        np.array([0.22, 0.21, 0.20])[None, None, :] * piedras[:, :, None] * 0.6
    )

    return np.clip(imagen, 0.0, 1.0)


def textura_sembrado(n: int = 512) -> np.ndarray:
    """Textura de una celda sembrada de 25 x 25 m (20.5 px por metro).

    Dibuja las 3 pasadas de la sembradora (9.12 m), 12 surcos por pasada
    (0.76 m), la cresta iluminada y las semillas brotando sobre ella.
    """
    rng = np.random.default_rng(41)
    ruido = _ruido_fractal(n, rng, octavas=(16, 32, 64))

    base = np.array([0.28, 0.21, 0.14])
    imagen = base[None, None, :] + (ruido - 0.5)[:, :, None] * 0.07

    metros_por_pixel = 25.0 / n
    xs = np.arange(n) * metros_por_pixel
    ys = np.arange(n) * metros_por_pixel

    fase = (xs % 0.76) / 0.76          # 0 = fondo del surco, 0.5 = cresta

    # Surco oscuro
    surco = np.exp(-((fase - 0.0) ** 2) / (2.0 * 0.11 ** 2))
    imagen = imagen * (1.0 - 0.42 * surco)[:, None, None]

    # Cresta iluminada
    cresta = np.exp(-((fase - 0.5) ** 2) / (2.0 * 0.16 ** 2))
    imagen = imagen + (cresta * 0.055)[:, None, None]

    # Juntas entre las 3 pasadas (cada 9.12 m)
    junta = np.exp(-((xs % 9.12) ** 2) / (2.0 * 0.16 ** 2))
    imagen = imagen * (1.0 - 0.40 * junta)[:, None, None]

    # Semillas brotando: puntos verdes sobre la cresta cada ~0.18 m
    paso_v = 0.18
    fila = np.floor(ys / paso_v)
    fase_v = (ys / paso_v) % 1.0
    desplazamiento = ((fila * 0.618) % 1.0) * 0.5

    en_fila = (np.abs(fase_v - (0.25 + desplazamiento)) < 0.13)
    en_cresta = np.abs(fase - (0.52 + 0.02 * np.sin(fila))) < 0.10

    brote = en_fila[None, :] & en_cresta[:, None]
    verde = np.array([0.30, 0.55, 0.17])

    imagen = np.where(brote[:, :, None],
                      imagen * 0.35 + verde[None, None, :] * 0.65,
                      imagen)

    # Paja suelta
    paja = np.clip((_ruido_tileable(n, 90, rng) - 0.76) * 4.0, 0.0, 1.0)
    imagen = imagen + paja[:, :, None] * np.array([0.09, 0.07, 0.02])

    return np.clip(imagen, 0.0, 1.0)


def guardar_textura(rgb: np.ndarray, ruta: Path) -> None:
    Image.fromarray((rgb * 255.0).round().astype(np.uint8), "RGB").save(ruta)


def guardar_alturas(alturas: np.ndarray, ruta: Path) -> None:
    # PIL guarda la fila 0 arriba; Unity lee la fila 0 abajo.
    # Se voltea para que la altura del pixel (fila, columna) coincida con
    # (z, x) del terreno de Unity.
    gris = (np.clip(alturas, 0.0, 1.0) * 255.0).round().astype(np.uint8)
    Image.fromarray(np.flipud(gris), "L").save(ruta)


# ---------------------------------------------------------------------------
# Malla del tractor
# ---------------------------------------------------------------------------
class Malla:
    def __init__(self) -> None:
        self.vertices: list[tuple[float, float, float]] = []
        self.caras: list[tuple[str, list[int]]] = []

    def _vertice(self, p) -> int:
        self.vertices.append((float(p[0]), float(p[1]), float(p[2])))
        return len(self.vertices)  # indices 1-based para el OBJ

    def caja(self, centro, tamano, material: str) -> None:
        cx, cy, cz = centro
        sx, sy, sz = tamano
        x0, x1 = cx - sx / 2.0, cx + sx / 2.0
        y0, y1 = cy - sy / 2.0, cy + sy / 2.0
        z0, z1 = cz - sz / 2.0, cz + sz / 2.0

        v = [
            self._vertice((x0, y0, z0)),
            self._vertice((x1, y0, z0)),
            self._vertice((x1, y1, z0)),
            self._vertice((x0, y1, z0)),
            self._vertice((x0, y0, z1)),
            self._vertice((x1, y0, z1)),
            self._vertice((x1, y1, z1)),
            self._vertice((x0, y1, z1)),
        ]

        caras = [
            (v[4], v[5], v[6], v[7]),  # +Z
            (v[1], v[0], v[3], v[2]),  # -Z
            (v[5], v[1], v[2], v[6]),  # +X
            (v[0], v[4], v[7], v[3]),  # -X
            (v[3], v[7], v[6], v[2]),  # +Y
            (v[0], v[1], v[5], v[4]),  # -Y
        ]

        for cara in caras:
            self.caras.append((material, list(cara)))

    def cilindro(self, centro, radio: float, largo: float, eje: str,
                 material: str, segmentos: int = 14) -> None:
        cx, cy, cz = centro

        if eje == "x":
            u, v, w = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)
        elif eje == "y":
            u, v, w = (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        else:
            u, v, w = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)

        u = np.array(u)
        v = np.array(v)
        w = np.array(w)
        centro = np.array([cx, cy, cz])
        mitad = largo / 2.0

        anillo_bajo = []
        anillo_alto = []

        for k in range(segmentos):
            angulo = 2.0 * np.pi * k / segmentos
            radial = np.cos(angulo) * u + np.sin(angulo) * v

            anillo_bajo.append(
                self._vertice(centro + radial * radio - w * mitad)
            )
            anillo_alto.append(
                self._vertice(centro + radial * radio + w * mitad)
            )

        for k in range(segmentos):
            siguiente = (k + 1) % segmentos
            self.caras.append((
                material,
                [
                    anillo_bajo[k],
                    anillo_bajo[siguiente],
                    anillo_alto[siguiente],
                    anillo_alto[k],
                ],
            ))

        # Tapas
        centro_bajo = self._vertice(centro - w * mitad)
        centro_alto = self._vertice(centro + w * mitad)

        for k in range(segmentos):
            siguiente = (k + 1) % segmentos
            self.caras.append((material, [centro_alto, anillo_alto[k], anillo_alto[siguiente]]))
            self.caras.append((material, [centro_bajo, anillo_bajo[siguiente], anillo_bajo[k]]))

    def guardar(self, ruta_obj: Path, ruta_mtl: Path, colores: dict[str, tuple]) -> None:
        lineas_mtl = []
        for nombre, (r, g, b) in colores.items():
            lineas_mtl.extend([
                f"newmtl {nombre}",
                "Ka 0.000 0.000 0.000",
                f"Kd {r:.4f} {g:.4f} {b:.4f}",
                "Ks 0.150 0.150 0.150",
                "Ns 24.0",
                "d 1.0",
                "illum 2",
                "",
            ])
        ruta_mtl.write_text("\n".join(lineas_mtl), encoding="utf-8")

        lineas_obj = [
            "# Tractor low-poly generado por herramientas/generar_assets_3d.py",
            f"mtllib {ruta_mtl.name}",
        ]

        for x, y, z in self.vertices:
            lineas_obj.append(f"v {x:.4f} {y:.4f} {z:.4f}")

        material_actual = None
        for material, indices in self.caras:
            if material != material_actual:
                lineas_obj.append(f"usemtl {material}")
                material_actual = material
            lineas_obj.append("f " + " ".join(str(i) for i in indices))

        ruta_obj.write_text("\n".join(lineas_obj) + "\n", encoding="utf-8")


def generar_tractor() -> None:
    malla = Malla()

    # Chasis
    malla.caja((0.0, 0.78, 0.0), (1.75, 0.62, 3.60), "cuerpo")

    # Capo del motor (delante, +Z)
    malla.caja((0.0, 1.12, 1.15), (1.55, 0.72, 1.50), "cuerpo")

    # Cabina
    malla.caja((0.0, 1.72, -0.55), (1.45, 1.15, 1.70), "cuerpo")

    # Vidrios de la cabina
    malla.caja((0.0, 1.78, 0.32), (1.20, 0.70, 0.06), "cabina")
    malla.caja((0.74, 1.78, -0.55), (0.06, 0.70, 1.30), "cabina")
    malla.caja((-0.74, 1.78, -0.55), (0.06, 0.70, 1.30), "cabina")

    # Techo
    malla.caja((0.0, 2.38, -0.55), (1.60, 0.12, 1.90), "detalle")

    # Ruedas traseras (grandes)
    for lado in (-1.0, 1.0):
        malla.cilindro((1.02 * lado, 0.82, -1.05), 0.82, 0.52, "x", "llantas")

    # Ruedas delanteras (pequenas)
    for lado in (-1.0, 1.0):
        malla.cilindro((0.92 * lado, 0.55, 1.45), 0.55, 0.36, "x", "llantas")

    # Tubo de escape
    malla.cilindro((0.45, 1.85, 1.55), 0.07, 1.00, "y", "detalle")

    # Faros delanteros
    for lado in (-1.0, 1.0):
        malla.caja((0.45 * lado, 1.18, 1.92), (0.18, 0.16, 0.06), "detalle")

    malla.guardar(
        MODELOS / "Tractor.obj",
        MODELOS / "Tractor.mtl",
        {
            "cuerpo": (34 / 255, 124 / 255, 43 / 255),   # verde John Deere
            "llantas": (1.0, 0.86, 0.05),                # amarillo
            "cabina": (0.07, 0.09, 0.10),                # vidrio oscuro
            "detalle": (0.18, 0.19, 0.20),               # gris
        },
    )


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def guardar_payload() -> None:
    """Payload exacto que Unity enviara al servidor Python.

    Se genera con el mismo modulo que usa el modelo, para que la elevacion
    del terreno de Unity y la del modelo sean identicas.
    """
    import json

    payload = escenarios.construir_payload(
        terreno=TERRENO,
        n=CUADRICULA,
        n_agentes=3,
        obstaculos=140,
        semilla=SEMILLA,
        costales=16,
        estrategia="greedy",
        steps=6000,
        lado_celda_m=LADO_CELDA_M,
    )

    STREAMING.mkdir(parents=True, exist_ok=True)
    ruta = STREAMING / "payload_colinas.json"
    ruta.write_text(json.dumps(payload), encoding="utf-8")
    print(f"payload: {ruta.name} ({ruta.stat().st_size} bytes)")


def main() -> None:
    TEXTURAS.mkdir(parents=True, exist_ok=True)
    MODELOS.mkdir(parents=True, exist_ok=True)
    STREAMING.mkdir(parents=True, exist_ok=True)

    for nombre_terreno in ("plano", "colinas", "montanoso"):
        alturas = generar_mapa_alturas(nombre_terreno)
        guardar_alturas(alturas, TEXTURAS / f"heightmap_{nombre_terreno}.png")

    alturas = generar_mapa_alturas()
    print(f"heightmap: {RESOLUCION}x{RESOLUCION}  "
          f"min={alturas.min():.3f} max={alturas.max():.3f}")

    guardar_textura(textura_cesped(), TEXTURAS / "cesped.png")
    guardar_textura(textura_tierra(), TEXTURAS / "tierra.png")
    guardar_textura(textura_sembrado(), TEXTURAS / "sembrado.png")
    print("texturas: cesped.png, tierra.png, sembrado.png (256x256)")

    generar_tractor()
    print("malla: Tractor.obj + Tractor.mtl")

    guardar_payload()


if __name__ == "__main__":
    main()
