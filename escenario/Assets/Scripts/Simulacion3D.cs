using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Networking;
using Debug = UnityEngine.Debug;

// ---------------------------------------------------------------------------
// Estructuras del JSON que devuelve el servidor Python
// ---------------------------------------------------------------------------
[Serializable]
public class CeldaFrame3D
{
    public int x;
    public int y;
}

[Serializable]
public class AgenteFrame3D
{
    public int id;
    public int[] pos;
    public string state;
    public float fuel;
    public int seeds;
    public int planted_total;
}

[Serializable]
public class Frame3D
{
    public int tick;
    public CeldaFrame3D[] planted_cells;
    public AgenteFrame3D[] agents;
    public int remaining_cells;
}

[Serializable]
public class Metricas3D
{
    public int total_ticks;
    public int total_steps;
    public float total_fuel_consumed;
    public float driver_wage_cost;
    public float seed_cost;
    public int remaining_cells;
}

[Serializable]
public class Config3D
{
    public int[] grid_size;
}

[Serializable]
public class Respuesta3D
{
    public string status;
    public string message;
    public Metricas3D metrics;
    public Frame3D[] frames;
}

/// <summary>
/// Puente entre el simulador de Python y la escena 3D.
///
/// 1. Manda el payload JSON (generado por herramientas/generar_assets_3d.py)
///    al servidor Python con UnityWebRequest.
/// 2. Recibe todos los fotogramas de la corrida.
/// 3. Convierte la secuencia de celdas de cada agente en una curva
///    Catmull-Rom y reproduce la simulacion moviendo los tractores por esa
///    curva.
/// 4. Va marcando las celdas sembradas sobre el terreno.
///
/// La logica de la simulacion vive en Python; Unity solo la dibuja.
/// </summary>
public class Simulacion3D : MonoBehaviour
{
    [Header("SERVIDOR PYTHON")]
    public string serverUrl = "http://127.0.0.1:5000/simulate";
    public string archivoPayload = "payload_colinas.json";

    [Header("ESCENA")]
    public Terrain terreno;
    public GameObject prefabTractor;
    public GameObject prefabCelda;
    public Transform contenedorTractores;
    public Transform contenedorCeldas;

    [Header("CAMPO")]
    public float hectareasCampo = 100f;
    public float anchoSembradora = 9.12f;

    [Header("REPRODUCCION")]
    [Tooltip("Segundos reales que dura un tick de la simulacion")]
    public float duracionTick = 0.08f;
    public bool iniciarAlComenzar = true;

    [Header("VELOCIDAD (tecla T)")]
    [Tooltip("Multiplicadores de velocidad que se recorren con la tecla T")]
    public float[] velocidades = { 0.5f, 1f, 2f, 4f };

    private int indiceVelocidad = 1;

    // Estado interno
    private Respuesta3D respuesta;
    private readonly List<CatmullRomSpline> rutas = new List<CatmullRomSpline>();
    private readonly List<Transform> tractores = new List<Transform>();
    private readonly HashSet<int> celdasMarcadas = new HashSet<int>();
    private int tickVisible;
    private bool terminado;
    private bool conectando;
    private string estado = "Esperando...";
    private string mensajeError;
    private GUIStyle estiloPanel;
    private bool autotest;
    private bool capturas;
    private int grilla = 20;

    // Capa del terreno donde se pinta lo sembrado (0=pasto, 1=tierra, 2=sembrado)
    private const int CapaSembrado = 2;
    private float[,,] alfaTerreno;
    private float[,,] alfaBase;
    private float siguienteVolcado;
    private int minPintadoX = int.MaxValue;
    private int maxPintadoX = -1;
    private int minPintadoY = int.MaxValue;
    private int maxPintadoY = -1;

    // Estado de solo lectura, util para el HUD y para las pruebas
    public bool Terminada { get { return terminado; } }
    public int TickVisible { get { return tickVisible; } }
    public int CeldasSembradas { get { return celdasMarcadas.Count; } }
    public int TractoresCreados { get { return tractores.Count; } }
    public string Estado { get { return estado; } }
    public string MensajeError { get { return mensajeError; } }

    public float VelocidadActual
    {
        get
        {
            if (velocidades == null || velocidades.Length == 0)
            {
                return 1f;
            }

            return velocidades[Mathf.Clamp(indiceVelocidad, 0, velocidades.Length - 1)];
        }
    }
    public Respuesta3D Respuesta { get { return respuesta; } }

    // =====================================================================
    // CICLO DE VIDA
    // =====================================================================

    void Start()
    {
        string[] argumentos = System.Environment.GetCommandLineArgs();

        autotest = System.Array.IndexOf(argumentos, "-autotest") >= 0;
        capturas = System.Array.IndexOf(argumentos, "-capturas") >= 0;

        if (iniciarAlComenzar)
        {
            Iniciar();
        }
    }

    /// <summary>
    /// Deja constancia del error y, si el ejecutable se lanzo con
    /// -autotest, lo cierra con codigo 1.
    /// </summary>
    private void Fallar(string mensaje)
    {
        mensajeError = mensaje;
        estado = "Error";
        conectando = false;

        Debug.LogError("[Simulacion3D] " + mensaje);

        if (autotest)
        {
            Application.Quit(1);
        }
    }

    void Update()
    {
        var teclado = Keyboard.current;

        if (teclado != null && teclado.tKey.wasPressedThisFrame)
        {
            CiclarVelocidad();
        }
    }

    /// <summary>Avanza al siguiente multiplicador de velocidad.</summary>
    public void CiclarVelocidad()
    {
        if (velocidades == null || velocidades.Length == 0)
        {
            return;
        }

        indiceVelocidad = (indiceVelocidad + 1) % velocidades.Length;
    }

    public void Iniciar()
    {
        StopAllCoroutines();
        StartCoroutine(Ejecutar());
    }

    private IEnumerator Ejecutar()
    {
        mensajeError = null;
        terminado = false;
        tickVisible = 0;
        conectando = true;
        estado = "Leyendo configuracion...";

        string payload;

        try
        {
            payload = File.ReadAllText(RutaPayload());
        }
        catch (Exception excepcion)
        {
            Fallar("No se pudo leer el payload: " + excepcion.Message);
            yield break;
        }

        var configuracion = JsonUtility.FromJson<Config3D>(payload);

        if (configuracion != null && configuracion.grid_size != null &&
            configuracion.grid_size.Length > 0)
        {
            grilla = configuracion.grid_size[0];
        }

        estado = "Consultando al servidor Python...";

        string json = null;
        string error = null;

        yield return Enviar(payload, (resultado, fallo) =>
        {
            json = resultado;
            error = fallo;
        });

#if UNITY_EDITOR
        // En el editor, si el servidor no esta arriba, lo arrancamos solos.
        if (string.IsNullOrEmpty(json) && IntentarArrancarServidor())
        {
            for (int intento = 0; intento < 20 && string.IsNullOrEmpty(json); intento++)
            {
                yield return new WaitForSeconds(0.5f);
                yield return Enviar(payload, (resultado, fallo) =>
                {
                    json = resultado;
                    error = fallo;
                });
            }
        }
#endif

        conectando = false;

        if (string.IsNullOrEmpty(json))
        {
            Fallar(
                "No se pudo conectar con " + serverUrl + ". " +
                "Arranca el servidor con: .venv/bin/python Agentes/agentesPrueba.py" +
                (string.IsNullOrEmpty(error) ? "" : "\n" + error)
            );
            yield break;
        }

        respuesta = JsonUtility.FromJson<Respuesta3D>(json);

        if (respuesta == null || respuesta.frames == null ||
            respuesta.frames.Length == 0)
        {
            Fallar("Python devolvio una respuesta sin fotogramas.");
            yield break;
        }

        PrepararEscena();
        yield return Reproducir();

        if (autotest)
        {
            var metricas = respuesta.metrics;

            Debug.Log(
                "[AUTOTEST] OK" +
                " | ticks=" + (respuesta.frames.Length - 1) +
                " | celdas=" + celdasMarcadas.Count +
                " | tractores=" + tractores.Count +
                " | rutas=" + rutas.Count +
                " | combustible=" +
                (metricas != null
                    ? metricas.total_fuel_consumed.ToString("F2", CultureInfo.InvariantCulture)
                    : "?")
            );

            yield return new WaitForSeconds(0.5f);
            Application.Quit(0);
        }
    }

    // =====================================================================
    // PREPARACION
    // =====================================================================

    private void PrepararEscena()
    {
        rutas.Clear();
        tractores.Clear();
        celdasMarcadas.Clear();
        PrepararAlphamap();

        int agentes = respuesta.frames[0].agents != null
            ? respuesta.frames[0].agents.Length
            : 0;

        for (int i = 0; i < agentes; i++)
        {
            rutas.Add(new CatmullRomSpline(
                RutaDeAgente(respuesta, i, terreno, TamanoGrilla())
            ));

            tractores.Add(ObtenerTractor(i));
        }

        estado = "Reproduciendo " + respuesta.frames.Length + " ticks";
        tickVisible = 0;
        PosicionarTractores(0f);
        AplicarCeldas(0);
    }

    private Transform ObtenerTractor(int indice)
    {
        string nombre = "Tractor_" + (indice + 1).ToString("D2");
        var existente = GameObject.Find(nombre);

        if (existente != null)
        {
            return existente.transform;
        }

        if (prefabTractor == null)
        {
            return null;
        }

        var instancia = Instantiate(prefabTractor, contenedorTractores);
        instancia.name = nombre;
        return instancia.transform;
    }

    // =====================================================================
    // REPRODUCCION
    // =====================================================================

    private IEnumerator Reproducir()
    {
        int total = respuesta.frames.Length;
        float progreso = 0f;

        // Capturas para revisar la simulacion sin estar frente a la pantalla
        // (porcentajes del total, para que sirvan con cualquier tamano de campo)
        int[] ticksCaptura =
        {
            Mathf.Max(1, total / 6),
            Mathf.Max(2, total * 3 / 6),
            Mathf.Max(3, total * 5 / 6)
        };
        int siguienteCaptura = 0;

        while (tickVisible < total - 1)
        {
            float duracion = Mathf.Max(
                duracionTick / Mathf.Max(VelocidadActual, 0.01f), 0.001f
            );

            progreso += Time.deltaTime / duracion;

            int objetivo = Mathf.Min(Mathf.FloorToInt(progreso), total - 1);

            while (tickVisible < objetivo)
            {
                tickVisible++;
                AplicarCeldas(tickVisible);
            }

            PosicionarTractores(progreso);

            if (Time.time >= siguienteVolcado)
            {
                VolcarAlphamap();
                siguienteVolcado = Time.time + 0.4f;
            }

            if (capturas && siguienteCaptura < ticksCaptura.Length &&
                tickVisible >= ticksCaptura[siguienteCaptura])
            {
                ScreenCapture.CaptureScreenshot(
                    "/tmp/campo3d_tick_" + ticksCaptura[siguienteCaptura] + ".png"
                );

                siguienteCaptura++;
            }

            yield return null;
        }

        VolcarAlphamap();

        if (capturas)
        {
            ScreenCapture.CaptureScreenshot("/tmp/campo3d_tick_final.png");
            yield return new WaitForSeconds(0.4f);
        }

        terminado = true;
        estado = "Simulacion terminada";
    }

    private void PosicionarTractores(float indice)
    {
        for (int i = 0; i < tractores.Count; i++)
        {
            if (tractores[i] == null || i >= rutas.Count || !rutas[i].Valida)
            {
                continue;
            }

            float recortado = Mathf.Min(indice, rutas[i].CantidadPuntos - 1f);
            Vector3 posicion = rutas[i].Evaluar(recortado);

            // Pegado al terreno (las alturas reales mandan sobre la curva)
            posicion.y = AlturaEn(posicion.x, posicion.z);

            Vector3 tangente = rutas[i].Tangente(recortado);
            tangente.y = 0f;

            if (tangente.sqrMagnitude > 0.0001f)
            {
                tractores[i].rotation = Quaternion.LookRotation(
                    tangente.normalized, Vector3.up
                );
            }

            tractores[i].position = posicion;
        }
    }

    private void AplicarCeldas(int indice)
    {
        if (indice < 0 || indice >= respuesta.frames.Length)
        {
            return;
        }

        Frame3D frame = respuesta.frames[indice];

        if (frame.planted_cells == null)
        {
            return;
        }

        int n = TamanoGrilla();

        foreach (CeldaFrame3D celda in frame.planted_cells)
        {
            int clave = celda.y * n + celda.x;

            if (!celdasMarcadas.Add(clave))
            {
                continue;
            }

            MarcarCelda(celda.x, celda.y);
        }
    }

    private void PrepararAlphamap()
    {
        alfaTerreno = null;

        if (terreno == null || terreno.terrainData == null)
        {
            return;
        }

        TerrainData datos = terreno.terrainData;

        if (datos.alphamapLayers <= CapaSembrado)
        {
            return;
        }

        if (alfaBase == null)
        {
            alfaBase = datos.GetAlphamaps(
                0, 0, datos.alphamapResolution, datos.alphamapResolution
            );
        }

        alfaTerreno = (float[,,])alfaBase.Clone();
        siguienteVolcado = 0f;

        minPintadoX = int.MaxValue;
        maxPintadoX = -1;
        minPintadoY = int.MaxValue;
        maxPintadoY = -1;

        Debug.Log(
            "[SIEMBRA] terreno=" + datos.size +
            " | alphamap=" + datos.alphamapResolution +
            " | capas=" + datos.alphamapLayers +
            " | grilla=" + grilla
        );
    }

    /// <summary>Pinta una celda sembrada en la capa de terreno.</summary>
    private void MarcarCelda(int celdaX, int celdaY)
    {
        if (alfaTerreno == null)
        {
            return;
        }

        int resolucion = terreno.terrainData.alphamapResolution;
        float porCelda = (float)resolucion / grilla;

        int desdeX = Mathf.FloorToInt(celdaX * porCelda);
        int hastaX = Mathf.CeilToInt((celdaX + 1) * porCelda);
        int desdeY = Mathf.FloorToInt(celdaY * porCelda);
        int hastaY = Mathf.CeilToInt((celdaY + 1) * porCelda);

        for (int y = desdeY; y < hastaY; y++)
        {
            if (y < 0 || y >= resolucion)
            {
                continue;
            }

            for (int x = desdeX; x < hastaX; x++)
            {
                if (x < 0 || x >= resolucion)
                {
                    continue;
                }

                minPintadoX = Mathf.Min(minPintadoX, x);
                maxPintadoX = Mathf.Max(maxPintadoX, x);
                minPintadoY = Mathf.Min(minPintadoY, y);
                maxPintadoY = Mathf.Max(maxPintadoY, y);

                alfaTerreno[y, x, 0] = 0f;
                alfaTerreno[y, x, 1] = 0f;
                alfaTerreno[y, x, 2] = 1f;
            }
        }
    }

    private void VolcarAlphamap()
    {
        if (alfaTerreno == null || terreno == null)
        {
            return;
        }

        terreno.terrainData.SetAlphamaps(0, 0, alfaTerreno);
    }

    private void LimpiarCeldas()
    {
        if (contenedorCeldas == null)
        {
            return;
        }

        for (int i = contenedorCeldas.childCount - 1; i >= 0; i--)
        {
            Destroy(contenedorCeldas.GetChild(i).gameObject);
        }
    }

    // =====================================================================
    // UTILIDADES PUBLICAS (las usa tambien la prueba del editor)
    // =====================================================================

    public string RutaPayload()
    {
        return Path.Combine(Application.streamingAssetsPath, archivoPayload);
    }

    public int TamanoGrilla()
    {
        return grilla;
    }

    public float AlturaEn(float x, float z)
    {
        if (terreno == null)
        {
            return 0f;
        }

        return terreno.SampleHeight(new Vector3(x, 0f, z)) +
               terreno.transform.position.y;
    }

    /// <summary>
    /// Convierte una celda de la rejilla (x, y) a una posicion del mundo
    /// sobre el terreno.
    /// </summary>
    public static Vector3 CeldaAMundo(
        Terrain terreno, int tamanoGrilla, int celdaX, int celdaY
    )
    {
        if (terreno == null)
        {
            return new Vector3(celdaX, 0f, celdaY);
        }

        Vector3 origen = terreno.transform.position;
        Vector3 tamano = terreno.terrainData.size;

        float x = origen.x +
                  (celdaX + 0.5f) * tamano.x / tamanoGrilla;

        float z = origen.z +
                  (celdaY + 0.5f) * tamano.z / tamanoGrilla;

        float y = terreno.SampleHeight(new Vector3(x, 0f, z)) + origen.y;

        return new Vector3(x, y, z);
    }

    /// <summary>
    /// Ruta completa (en coordenadas del mundo) de un agente, tomando su
    /// celda en cada fotograma.
    /// </summary>
    public static List<Vector3> RutaDeAgente(
        Respuesta3D respuesta, int agente, Terrain terreno, int tamanoGrilla
    )
    {
        var puntos = new List<Vector3>();

        foreach (Frame3D frame in respuesta.frames)
        {
            if (frame.agents == null || agente >= frame.agents.Length)
            {
                continue;
            }

            AgenteFrame3D datos = frame.agents[agente];

            if (datos.pos == null || datos.pos.Length < 2)
            {
                continue;
            }

            puntos.Add(CeldaAMundo(terreno, tamanoGrilla, datos.pos[0], datos.pos[1]));
        }

        return puntos;
    }

    // =====================================================================
    // RED
    // =====================================================================

    private IEnumerator Enviar(string payload, Action<string, string> callback)
    {
        byte[] cuerpo = Encoding.UTF8.GetBytes(payload);

        using (UnityWebRequest peticion = new UnityWebRequest(serverUrl, "POST"))
        {
            peticion.uploadHandler = new UploadHandlerRaw(cuerpo);
            peticion.downloadHandler = new DownloadHandlerBuffer();
            peticion.SetRequestHeader("Content-Type", "application/json");
            peticion.timeout = 60;

            yield return peticion.SendWebRequest();

            if (peticion.result == UnityWebRequest.Result.Success)
            {
                callback(peticion.downloadHandler.text, null);
            }
            else
            {
                callback(null, peticion.error + " // " +
                              peticion.downloadHandler.text);
            }
        }
    }

#if UNITY_EDITOR
    private static Process servidor;

    /// <summary>
    /// Solo en el editor: arranca Agentes/agentesPrueba.py si no esta activo.
    /// En el ejecutable hay que arrancar el servidor a mano.
    /// </summary>
    private static bool IntentarArrancarServidor()
    {
        try
        {
            if (servidor != null && !servidor.HasExited)
            {
                return true;
            }

            var assets = new DirectoryInfo(Application.dataPath);
            DirectoryInfo proyecto = assets.Parent;              // escenario/
            DirectoryInfo raiz = proyecto != null ? proyecto.Parent : null; // repo

            if (raiz == null)
            {
                return false;
            }

            string python = Path.Combine(raiz.FullName, ".venv", "bin", "python");
            string script = Path.Combine(
                raiz.FullName, "Agentes", "agentesPrueba.py"
            );

            if (!File.Exists(python) || !File.Exists(script))
            {
                return false;
            }

            var info = new ProcessStartInfo
            {
                FileName = python,
                Arguments = "\"" + script + "\"",
                WorkingDirectory = raiz.FullName,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            servidor = Process.Start(info);

            Debug.Log("[Simulacion3D] Servidor Python iniciado.");
            return true;
        }
        catch (Exception excepcion)
        {
            Debug.LogWarning(
                "[Simulacion3D] No se pudo iniciar el servidor: " +
                excepcion.Message
            );

            return false;
        }
    }
#endif

    // =====================================================================
    // INTERFAZ
    // =====================================================================

    private void OnGUI()
    {
        if (estiloPanel == null)
        {
            estiloPanel = new GUIStyle(GUI.skin.box)
            {
                alignment = TextAnchor.UpperLeft,
                fontSize = 13,
                padding = new RectOffset(10, 10, 8, 8)
            };
        }

        var rect = new Rect(Screen.width - 300f, 12f, 288f, 150f);

        var texto = new StringBuilder();
        texto.AppendLine("SIMULACION 3D");
        texto.AppendLine(estado ?? "");

        if (respuesta != null && respuesta.frames != null)
        {
            int total = respuesta.frames.Length;
            int sembradas = celdasMarcadas.Count;
            int restantes = respuesta.frames[
                Mathf.Clamp(tickVisible, 0, total - 1)
            ].remaining_cells;

            texto.AppendLine("Tick: " + tickVisible + " / " + (total - 1));
            texto.AppendLine("Celdas sembradas: " + sembradas);
            texto.AppendLine("Celdas restantes: " + restantes);
            texto.AppendLine("Agentes: " + tractores.Count);
            texto.AppendLine(
                "Velocidad: " + VelocidadActual.ToString("0.##") + "x  (T)"
            );
            texto.AppendLine("Campo: " + hectareasCampo.ToString("F0") + " ha");
            texto.AppendLine(
                "Sembradora: " + anchoSembradora.ToString("F2") + " m" +
                " | " + Mathf.CeilToInt(100f / anchoSembradora) + " pasadas/ha"
            );
        }

        if (terminado && respuesta != null && respuesta.metrics != null)
        {
            Metricas3D m = respuesta.metrics;
            texto.AppendLine("---");
            texto.AppendLine("Combustible: " +
                m.total_fuel_consumed.ToString("F2", CultureInfo.InvariantCulture) + " L");
            texto.AppendLine("Costo semilla: $" +
                m.seed_cost.ToString("F0", CultureInfo.InvariantCulture));
        }

        GUI.Box(rect, texto.ToString(), estiloPanel);

        if (!string.IsNullOrEmpty(mensajeError))
        {
            var rectError = new Rect(12f, Screen.height - 96f, Screen.width - 24f, 84f);
            GUI.Box(rectError, mensajeError, estiloPanel);
        }

        if ((terminado || !string.IsNullOrEmpty(mensajeError) || !conectando) &&
            GUI.Button(new Rect(Screen.width - 300f, 168f, 288f, 26f),
                "Volver a simular"))
        {
            Iniciar();
        }
    }
}
