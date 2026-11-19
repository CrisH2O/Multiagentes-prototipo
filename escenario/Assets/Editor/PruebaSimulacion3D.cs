using System.IO;
using System.Net;
using System.Text;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Prueba sin entrar a Play: manda el payload al servidor Python, valida
/// que el JSON se pueda leer con JsonUtility y que las rutas de los
/// agentes generen curvas Catmull-Rom coherentes.
///
/// Requiere el servidor activo:
///   .venv/bin/python Agentes/agentesPrueba.py
/// </summary>
public static class PruebaSimulacion3D
{
    private const string Url = "http://127.0.0.1:5000/simulate";

    [MenuItem("Herramientas/Campo 3D/Probar API y curvas")]
    public static void Probar()
    {
        string ruta = Path.Combine(
            Application.dataPath, "StreamingAssets", "payload_colinas.json"
        );

        if (!File.Exists(ruta))
        {
            Debug.LogError("[PRUEBA3D] Falta " + ruta);
            return;
        }

        string payload = File.ReadAllText(ruta);
        string json = Enviar(payload);

        if (string.IsNullOrEmpty(json))
        {
            Debug.LogError("[PRUEBA3D] El servidor no respondio.");
            return;
        }

        var datos = JsonUtility.FromJson<Respuesta3D>(json);

        if (datos == null || datos.frames == null || datos.frames.Length == 0)
        {
            Debug.LogError("[PRUEBA3D] JSON invalido.");
            return;
        }

        Debug.Log(
            "[PRUEBA3D] frames=" + datos.frames.Length +
            " | total_ticks=" + datos.metrics.total_ticks +
            " | combustible=" + datos.metrics.total_fuel_consumed.ToString("F2") +
            " L | semilla=$" + datos.metrics.seed_cost.ToString("F0")
        );

        int agentes = datos.frames[0].agents != null
            ? datos.frames[0].agents.Length
            : 0;

        for (int i = 0; i < agentes; i++)
        {
            var puntos = Simulacion3D.RutaDeAgente(
                datos, i, null, 20
            );

            var curva = new CatmullRomSpline(puntos);

            Debug.Log(
                "[PRUEBA3D] agente " + i +
                " | puntos=" + puntos.Count +
                " | longitud=" + curva.Longitud.ToString("F1") +
                " | inicio=" + puntos[0] +
                " | fin=" + puntos[puntos.Count - 1]
            );

            float medio = (puntos.Count - 1) * 0.5f;
            Debug.Log(
                "[PRUEBA3D]   curva en el punto medio -> " +
                curva.Evaluar(medio) +
                " | tangente=" + curva.Tangente(medio)
            );
        }
    }

    private static string Enviar(string payload)
    {
        try
        {
            var peticion = (HttpWebRequest)WebRequest.Create(Url);
            peticion.Method = "POST";
            peticion.ContentType = "application/json";
            peticion.Timeout = 60000;

            byte[] cuerpo = Encoding.UTF8.GetBytes(payload);
            peticion.ContentLength = cuerpo.Length;

            using (var flujo = peticion.GetRequestStream())
            {
                flujo.Write(cuerpo, 0, cuerpo.Length);
            }

            using (var respuesta = (HttpWebResponse)peticion.GetResponse())
            using (var lector = new StreamReader(respuesta.GetResponseStream()))
            {
                return lector.ReadToEnd();
            }
        }
        catch (System.Exception excepcion)
        {
            Debug.LogError("[PRUEBA3D] " + excepcion.Message);
            return null;
        }
    }
}
