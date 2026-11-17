# Investigación agronómica: cuánta semilla y combustible se ocupa por hectárea

**Objetivo.** Traducir la simulación a las unidades con las que realmente se
trabaja en el campo mexicano: **hectáreas** y **costales de semilla**. El
modelo actual usa unidades abstractas (celdas, ticks), lo que impide decir
cuánto cuesta sembrar una hectárea.

> **Resumen en una línea:** un costal de semilla de maíz de 20 kg alcanza para
> **≈ 1 hectárea**, y sembrar esa hectárea consume **≈ 9–11 litros de diésel**
> (≈ $250–300 MXN). Para un campo de 3.24 ha: **~3.2 costales** y **~30 L**.

---

## 1. De qué tamaño es nuestro campo

### 1.1 La celda de 9 m está justificada

El código declara una celda de **9 m** (`Agentes/campo.py`, `tamano_celda_m =
9.0`). Ese número no es arbitrario: corresponde a una **sembradora de 12
surcos a 76 cm de separación** (30 pulgadas), el estándar de maíz en México y
Estados Unidos.

> 12 surcos × 0.76 m = **9.12 m** de ancho de trabajo

Confirmado en las especificaciones de la [John Deere 1775NT de 12 surcos a
30 in](https://www.deere.africa/en-afme/products-solutions/planters/drawn-planters/1775nt-12row30-drawn-planter-njixoeg)
y en la [sembradora DR12](https://www.deere.ca/fr/%c3%a9quipement-ensemencement/semoir-pr%c3%a9cision-dr12/).
Es decir: **una pasada de la sembradora = una celda de ancho**.

### 1.2 Área del terreno simulado

| Parámetro | Valor |
|---|---|
| Celdas | 20 × 20 = 400 |
| Lado de celda | 9 m |
| Área por celda | 9 × 9 = **81 m²** |
| Área total | 400 × 81 = 32,400 m² = **3.24 ha** |
| Celdas sembrables (364) | **2.95 ha** |

---

## 2. Semilla: cuántas semillas y cuántos costales por hectárea

### 2.1 Densidad de siembra

Para maíz de grano, los híbridos comerciales rondan **3,000 semillas por
kilogramo** y se siembran entre **15 y 25 kg por hectárea**, lo que equivale a
**45,000–75,000 semillas/ha** ([INEGI / INIFAP](https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/historicos/380/702825118259/702825118259.pdf#3#11#3)).
Los híbridos modernos de alto rendimiento se calibran cerca de **80,000
plantas/ha** ([MAS Seeds](https://www.masseeds.mx/buscador-de-productos/maiz/MAS_59K/)).

| Escenario | Semillas/ha | kg/ha |
|---|---:|---:|
| Baja densidad | 45,000 | 15 |
| **Típico** | **60,000** | **20** |
| Alta densidad | 75,000–80,000 | 25–27 |

### 2.2 El costal

El costal comercial estándar de semilla de maíz híbrido es de **20 kg**, y
contiene del orden de **60,000 semillas**.

- Confirmado por distribuidores: "el costal de 20 kilos de semilla, en promedio
  60 mil semillas" ([Panorama Agrario](https://panoramaagrario.com/2016/05/les-facilitan-semilla-maiz-agricultores/amp/))
- Precio 2026 en programa municipal de semilla a bajo costo: **$1,500 MXN el
  saco de 20 kg** ([Gobierno de Tuxpan, Jal.](https://www.tuxpan-jal.gob.mx/webok/?p=27860))
  — es precio subsidiado; el comercial suele estar por encima.

> **Regla práctica: 1 costal de 20 kg ≈ 1 hectárea.**

### 2.3 Cuántos costales para nuestro campo

| Campo | Área | Costales (60,000 sem/ha) |
|---|---:|---:|
| 1 celda | 0.0081 ha | 0.008 |
| 123 celdas | **1.0 ha** | **1 costal** |
| Campo completo (364 sembrables) | 2.95 ha | **≈ 3.2 costales** |
| Campo completo (400) | 3.24 ha | ≈ 3.5 costales |

**Conversión clave:** **1 celda ≈ 486 semillas ≈ 0.16 kg de semilla**.

---

## 3. Combustible: cuánto diésel por hectárea

### 3.1 Consumo medido en siembra de maíz

El estudio más cercano a nuestro caso —siembra de maíz con monitor SeedStar en
México— midió el rendimiento de combustible a distintas velocidades:

| Velocidad | Consumo |
|---|---:|
| 6 km/h | **8.6 L/ha** |
| 9 km/h | **10.77 L/ha** (+24%) |

Fuente: [Evaluación de parámetros de siembra de maíz a diferentes velocidades,
con monitor SeedStar (AGRIS/FAO)](https://agris.fao.org/search/en/records/669f609c00eb85b7d72c3501#1).

### 3.2 Precio del diésel en México (2026)

- El Gobierno de México y el sector gasolinero acordaron mantener un **precio
  máximo de $28 MXN por litro** ([PROFECO, abril 2026](https://www.gob.mx/profeco/prensa/gobierno-de-mexico-y-sector-gasolinero-acuerdan-mantener-el-precio-maximo-del-diesel-en-28-pesos-el-litro-424321)).
- Desde abril de 2026 el diésel se ha mantenido **por debajo de $27/L**, y
  **por debajo de $25.39/L** en zona fronteriza ([SENER, agosto 2026](https://www.gob.mx/sener/es/articulos/la-presidenta-de-mexico-y-el-sector-gasolinero-renuevan-la-estrategia-nacional-para-estabilizar-el-precio-de-la-gasolina-regular-y-el-diesel)).

**Valor adoptado: $27.00 MXN/L** (rango de sensibilidad: $25.39 – $28.00).

### 3.3 Costo de combustible por hectárea

| Consumo | Precio $25.39 | $27.00 | $28.00 |
|---|---:|---:|---:|
| 8.6 L/ha | $218 | **$232** | $241 |
| 10.77 L/ha | $273 | **$291** | $302 |

**Para nuestro campo de 3.24 ha:** 28–35 L de diésel, es decir **$753–$945 MXN**
solo de combustible.

---

## 4. Tiempo: de ticks a horas de trabajo

Con un ancho de trabajo de 9.12 m y una velocidad de 6 km/h:

> 9.12 m × 6,000 m/h = 54,720 m²/h = **5.47 ha/h teóricas**
> con 85 % de eficiencia de campo ≈ **4.65 ha/h**

Un campo de 3.24 ha se cubre en **≈ 42 minutos** de trabajo efectivo continuo
(una sola máquina, sin recargas).

Y como cada tick del modelo avanza una celda de 9 m:

> **1 tick ≈ 9 m ÷ (6,000 m/h) = 5.4 segundos**

Eso permite traducir los ticks del simulador a tiempo real.

---

## 5. Comparación: modelo vs. realidad

Aquí está el punto incómodo. El modelo **no está calibrado**: sus números son
consistentes entre sí, pero no corresponden a magnitudes reales.

| Concepto | Simulador | Realidad (maíz, 3.24 ha) | Factor |
|---|---:|---:|---:|
| Área | 400 celdas | 3.24 ha | — |
| Semilla total | 364 "semillas" | ~194,400 semillas (3.2 costales) | **~530×** |
| Capacidad de tanque | 35 "semillas" | 1 costal = 60,000 semillas = 123 celdas | — |
| Combustible | 792 L | 28–35 L | **~25×** |
| Tiempo (1 tractor) | 783 ticks | ≈ 42 min ≈ 467 ticks a 5.4 s | ~1.7× |
| Costo combustible | $19,008 (a $24/L) | $753–945 | **~22×** |
| Salario | $2.5/tick = $1,667/h | ≈ $45–70/h (operador) | **~25–35×** |

**Lectura correcta:** el simulador sirve para **comparar configuraciones entre
sí** (qué tan caro es un tanque de 10 vs 60 unidades), pero sus cifras
absolutas no representan pesos reales. Es la limitación **L8** del
[`ANALISIS.md`](ANALISIS.md).

---

## 6. Tabla de conversión (la que se usa en el proyecto)

| De | A | Factor |
|---|---|---|
| 1 celda | m² | 81 |
| 1 celda | hectáreas | 0.0081 |
| 123 celdas | hectáreas | 1.0 |
| 1 celda sembrada | semillas de maíz | ≈ 486 |
| 1 celda sembrada | kg de semilla | ≈ 0.16 |
| 1 costal (20 kg) | semillas | ≈ 60,000 |
| 1 costal | hectáreas | ≈ 1.0 |
| 1 costal | celdas | ≈ 123 |
| 1 ha sembrada | diésel | 8.6 – 10.77 L |
| 1 tick | segundos | ≈ 5.4 |
| 1 ha | tiempo de siembra | ≈ 0.215 h (4.65 ha/h) |

---

## 7. Cómo se aplica al proyecto

1. **Reportar en hectáreas.** `Agentes/unidades.py` convierte celdas a
   hectáreas y agrega costo y combustible por hectárea a los resultados.
2. **Reportar en costales.** El tanque del tractor se expresa como fracción de
   costal: 35 unidades ≈ **0.28 costal** (0.28 ha); 123 unidades ≈ 1 costal.
3. **Corregir el precio del diésel** de $24 a **$27 MXN/L** (valor investigado).
4. **Escala recomendada para un preset realista:** campo de 3.24 ha, tanque de
   **123–246 unidades** (1–2 costales), consumo de **8.6 L/ha**.

---

## 8. Fuentes

1. INEGI / INIFAP — *El maíz en México*: densidad de siembra, 3,000
   semillas/kg, 15–25 kg/ha.
   <https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/historicos/380/702825118259/702825118259.pdf>
2. Panorama Agrario — costal de 20 kg ≈ 60,000 semillas.
   <https://panoramaagrario.com/2016/05/les-facilitan-semilla-maiz-agricultores/amp/>
3. Gobierno de Tuxpan, Jalisco — Programa de semilla de maíz 2026, saco 20 kg
   $1,500.
   <https://www.tuxpan-jal.gob.mx/webok/?p=27860>
4. MAS Seeds México — densidad de 80,000 plantas/ha en híbridos de alto
   rendimiento.
   <https://www.masseeds.mx/buscador-de-productos/maiz/MAS_59K/>
5. AGRIS / FAO — *Evaluación de parámetros de siembra de maíz a diferentes
   velocidades de operación con monitor SeedStar*: 8.6 L/ha a 6 km/h y
   10.77 L/ha a 9 km/h.
   <https://agris.fao.org/search/en/records/669f609c00eb85b7d72c3501>
6. PROFECO — acuerdo de precio máximo de diésel a $28/L (abril 2026).
   <https://www.gob.mx/profeco/prensa/gobierno-de-mexico-y-sector-gasolinero-acuerdan-mantener-el-precio-maximo-del-diesel-en-28-pesos-el-litro-424321>
7. SENER — diésel por debajo de $27/L y $25.39/L en frontera (agosto 2026).
   <https://www.gob.mx/sener/es/articulos/la-presidenta-de-mexico-y-el-sector-gasolinero-renuevan-la-estrategia-nacional-para-estabilizar-el-precio-de-la-gasolina-regular-y-el-diesel>
8. John Deere — 1775NT, 12 surcos a 30 in (76 cm).
   <https://www.deere.africa/en-afme/products-solutions/planters/drawn-planters/1775nt-12row30-drawn-planter-njixoeg>
9. John Deere — sembradora de precisión DR12, 12 surcos.
   <https://www.deere.ca/fr/%c3%a9quipement-ensemencement/semoir-pr%c3%a9cision-dr12/>
10. INTA Argentina — consumo medio de semilla de maíz híbrido: 21.7 kg/ha.
    <https://repositorio.inta.gob.ar/xmlui/bitstream/handle/20.500.12123/7119/INTA_CRSantaFe_EEARafaela_Benzi_P_An%c3%a1lisis_integrado_del_consumo_de_bienes_y_servicios.pdf>

---

## 9. Limitaciones de esta investigación

- **Variedad y región.** Los rangos corresponden a maíz de grano; trigo, frijol
  y forrajes tienen densidades y costos distintos (el trigo, por ejemplo, se
  siembra en 100–150 kg/ha).
- **Precios.** El precio de semilla citado es de un programa subsidiado; el
  comercial es mayor. El diésel fluctúa y tiene tope regulatorio.
- **Combustible.** Los 8.6–10.77 L/ha corresponden a la labor de siembra sola,
  no a la preparación del terreno (que puede consumir 25–45 L/ha en labranza
  convencional).
- **Rendimiento de campo.** El 85 % de eficiencia es un supuesto estándar; en
  lotes pequeños o irregulares baja.
