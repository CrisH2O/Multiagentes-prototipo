using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Curva de Catmull-Rom (una spline parametrica que PASA por todos los
/// puntos de control, a diferencia de una Bezier).
///
/// Se usa para que los tractores se muevan de celda en celda de forma
/// fluida: el agente va exactamente por el centro de cada celda en cada
/// tick, pero entre tick y tick la trayectoria es una curva suave en vez
/// de una linea recta con esquinas.
///
/// El parametro de <see cref="Evaluar"/> es el INDICE del punto:
///   indice = 0        -> primer punto
///   indice = 1        -> segundo punto
///   indice = 1.5      -> mitad del tramo entre el punto 1 y el 2
///
/// Tambien incluye una tabla de longitud de arco (<see cref="Longitud"/>,
/// <see cref="PuntoEnDistancia"/>) para recorrer la curva a velocidad
/// constante, que es lo que se usa en los recorridos de camara.
/// </summary>
public class CatmullRomSpline
{
    private readonly Vector3[] puntos;
    private readonly bool cerrada;

    // Tabla de longitud de arco acumulada (se construye bajo demanda).
    private float[] longitudes;
    private const int MuestrasArco = 200;

    public int CantidadPuntos
    {
        get { return puntos != null ? puntos.Length : 0; }
    }

    public bool Valida
    {
        get { return puntos != null && puntos.Length >= 2; }
    }

    /// <summary>Longitud aproximada de la curva en unidades del mundo.</summary>
    public float Longitud
    {
        get
        {
            if (!Valida)
            {
                return 0f;
            }

            if (longitudes == null)
            {
                ConstruirTablaLongitud();
            }

            return longitudes[longitudes.Length - 1];
        }
    }

    public CatmullRomSpline(IList<Vector3> puntos, bool cerrada = false)
    {
        this.puntos = puntos != null
            ? new List<Vector3>(puntos).ToArray()
            : new Vector3[0];

        this.cerrada = cerrada;
    }

    // =====================================================================
    // EVALUACION POR INDICE
    // =====================================================================

    public Vector3 Evaluar(float indice)
    {
        if (!Valida)
        {
            return CantidadPuntos == 1 ? puntos[0] : Vector3.zero;
        }

        float ultimo = cerrada ? CantidadPuntos : CantidadPuntos - 1f;
        float recortado = Mathf.Clamp(indice, 0f, ultimo - 0.0001f);

        int segmento = Mathf.FloorToInt(recortado);
        float t = recortado - segmento;

        Vector3 p0 = Punto(segmento - 1);
        Vector3 p1 = Punto(segmento);
        Vector3 p2 = Punto(segmento + 1);
        Vector3 p3 = Punto(segmento + 2);

        return Interpolar(p0, p1, p2, p3, t);
    }

    /// <summary>
    /// Tangente (direccion de avance) en un indice. Se calcula por
    /// diferencias finitas sobre la misma curva.
    /// </summary>
    public Vector3 Tangente(float indice)
    {
        const float delta = 0.02f;

        Vector3 antes = Evaluar(indice - delta);
        Vector3 despues = Evaluar(indice + delta);
        Vector3 tangente = despues - antes;

        if (tangente.sqrMagnitude < 0.000001f)
        {
            return Vector3.forward;
        }

        return tangente.normalized;
    }

    // =====================================================================
    // EVALUACION POR LONGITUD DE ARCO
    // =====================================================================

    /// <summary>
    /// Devuelve el punto que esta a "distancia" unidades recorridas desde
    /// el inicio de la curva. Sirve para avanzar a velocidad constante.
    /// </summary>
    public Vector3 PuntoEnDistancia(float distancia)
    {
        if (!Valida)
        {
            return Vector3.zero;
        }

        if (longitudes == null)
        {
            ConstruirTablaLongitud();
        }

        float total = longitudes[longitudes.Length - 1];

        if (total <= 0f)
        {
            return puntos[0];
        }

        float objetivo = Mathf.Clamp(distancia, 0f, total);

        // Busqueda binaria en la tabla de longitudes
        int bajo = 0;
        int alto = longitudes.Length - 1;

        while (bajo < alto - 1)
        {
            int medio = (bajo + alto) / 2;

            if (longitudes[medio] < objetivo)
            {
                bajo = medio;
            }
            else
            {
                alto = medio;
            }
        }

        float largo = longitudes[alto] - longitudes[bajo];
        float fraccion = largo > 0f
            ? (objetivo - longitudes[bajo]) / largo
            : 0f;

        float ultimo = cerrada ? CantidadPuntos : CantidadPuntos - 1f;
        float inicio = (float)bajo / (longitudes.Length - 1) * ultimo;
        float fin = (float)alto / (longitudes.Length - 1) * ultimo;

        return Evaluar(Mathf.Lerp(inicio, fin, fraccion));
    }

    private void ConstruirTablaLongitud()
    {
        longitudes = new float[MuestrasArco + 1];

        float ultimo = cerrada ? CantidadPuntos : CantidadPuntos - 1f;
        Vector3 anterior = Evaluar(0f);
        longitudes[0] = 0f;

        for (int i = 1; i <= MuestrasArco; i++)
        {
            float indice = (float)i / MuestrasArco * ultimo;
            Vector3 actual = Evaluar(indice);

            longitudes[i] = longitudes[i - 1] +
                            Vector3.Distance(anterior, actual);

            anterior = actual;
        }
    }

    // =====================================================================
    // MATEMATICA
    // =====================================================================

    private Vector3 Punto(int indice)
    {
        int total = CantidadPuntos;

        if (cerrada)
        {
            int envuelto = ((indice % total) + total) % total;
            return puntos[envuelto];
        }

        return puntos[Mathf.Clamp(indice, 0, total - 1)];
    }

    /// <summary>
    /// Interpolacion cubica de Catmull-Rom entre p1 y p2.
    /// </summary>
    private static Vector3 Interpolar(
        Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, float t
    )
    {
        float t2 = t * t;
        float t3 = t2 * t;

        return 0.5f * (
            2f * p1 +
            (-p0 + p2) * t +
            (2f * p0 - 5f * p1 + 4f * p2 - p3) * t2 +
            (-p0 + 3f * p1 - 3f * p2 + p3) * t3
        );
    }
}
