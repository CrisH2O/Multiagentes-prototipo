using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;
using Debug = UnityEngine.Debug;

[Serializable]
public class UnityAgentFrame
{
    public int id;
    public int[] pos;
    public string state;
}

[Serializable]
public class UnityPlantedCell
{
    public int x;
    public int y;
}

[Serializable]
public class UnitySimulationFrame
{
    public int tick;
    public UnityPlantedCell[] planted_cells;
    public UnityAgentFrame[] agents;
}

[Serializable]
public class UnitySimulationMetrics
{
    public int total_ticks;
    public int total_steps;
    public float total_fuel_consumed;
    public float driver_wage_cost;
    public float seed_cost;
    public int remaining_cells;
}

[Serializable]
public class UnitySimulationResponse
{
    public string status;
    public string message;
    public UnitySimulationMetrics metrics;
    public UnitySimulationFrame[] frames;
}

// Resumen de una corrida, para la tabla comparativa de la interfaz
public class ResultadoCorrida
{
    public string estrategia;
    public int ticks;
    public float litros;
    public float litrosPorHectarea;
    public float costoTotal;
    public float costoPorHectarea;
}

public class AgentSimulationBridge : MonoBehaviour
{
    [Header("CONEXION CON AGENTES PYTHON")]
    public string serverUrl = "http://127.0.0.1:5000/simulate";
    public float tickDuration = 0.14f;

    private PlantingGrid plantingGrid;
    private int agentCount;
    private int difficulty;
    private Coroutine simulation;
    private Process pythonServer;
    private GameObject motherShip;
    private string estrategia = "greedy";

    [Header("METRICAS")]
    [Tooltip("Precio del diesel en MXN por litro")]
    public float precioDiesel = 27f;
    [Tooltip("1 celda de 9x9 m = 0.0081 ha")]
    public float hectareasPorCelda = 0.0081f;

    public const int MAX_HISTORIAL = 8;
    private readonly List<ResultadoCorrida> historial =
        new List<ResultadoCorrida>();

    public IReadOnlyList<ResultadoCorrida> Historial { get { return historial; } }
    public UnitySimulationMetrics Metrics { get; private set; }
    public bool SimulacionTerminada { get; private set; }
    public int TickActual { get; private set; }
    public int TicksTotales { get; private set; }
    public string EstrategiaActual { get { return estrategia; } }
    public string MensajeError { get; private set; }

    private float hectareas
    {
        get
        {
            if (plantingGrid == null)
                return 1f;

            return plantingGrid.gridCells * plantingGrid.gridCells
                * hectareasPorCelda;
        }
    }

    public void StartSimulation(
        PlantingGrid grid,
        int numberOfAgents,
        int terrainDifficulty,
        string nuevaEstrategia)
    {
        plantingGrid = grid;
        agentCount = numberOfAgents;
        difficulty = terrainDifficulty;
        estrategia = string.IsNullOrEmpty(nuevaEstrategia)
            ? "greedy"
            : nuevaEstrategia;

        SimulacionTerminada = false;
        TickActual = 0;
        TicksTotales = 0;
        MensajeError = null;

        CreateMotherShip();

        if (simulation != null)
            StopCoroutine(simulation);

        simulation = StartCoroutine(RunSimulation());
    }

    private IEnumerator RunSimulation()
    {
        string payload = BuildPayload();
        string response = null;
        string error = null;

        yield return SendRequest(payload, (result, message) =>
        {
            response = result;
            error = message;
        });

        if (string.IsNullOrEmpty(response) && StartPythonServer())
        {
            for (int attempt = 0; attempt < 10; attempt++)
            {
                yield return new WaitForSeconds(0.5f);
                yield return SendRequest(payload, (result, message) =>
                {
                    response = result;
                    error = message;
                });

                if (!string.IsNullOrEmpty(response))
                    break;
            }
        }

        if (string.IsNullOrEmpty(response))
        {
            Debug.LogError(
                "No se pudo conectar con agentesPrueba.py: " + error);
            yield break;
        }

        UnitySimulationResponse simulationResponse =
            JsonUtility.FromJson<UnitySimulationResponse>(response);

        if (simulationResponse == null ||
            simulationResponse.frames == null)
        {
            Debug.LogError("Python devolvio una simulacion sin frames.");
            yield break;
        }

        TicksTotales = simulationResponse.frames.Length;

        for (int i = 0; i < simulationResponse.frames.Length; i++)
        {
            ApplyFrame(simulationResponse.frames[i]);
            TickActual = simulationResponse.frames[i].tick;
            yield return new WaitForSeconds(tickDuration);
        }

        Metrics = simulationResponse.metrics;
        SimulacionTerminada = true;
        RegistrarCorrida();

        simulation = null;
    }

    private void RegistrarCorrida()
    {
        if (Metrics == null)
            return;

        float area = hectareas;
        float litros = Metrics.total_fuel_consumed;
        float costo = litros * precioDiesel
            + Metrics.driver_wage_cost
            + Metrics.seed_cost;

        historial.Insert(0, new ResultadoCorrida
        {
            estrategia = estrategia,
            ticks = Metrics.total_ticks,
            litros = litros,
            litrosPorHectarea = area > 0f ? litros / area : 0f,
            costoTotal = costo,
            costoPorHectarea = area > 0f ? costo / area : 0f
        });

        while (historial.Count > MAX_HISTORIAL)
            historial.RemoveAt(historial.Count - 1);
    }

    public void DetenerSimulacion()
    {
        if (simulation != null)
        {
            StopCoroutine(simulation);
            simulation = null;
        }

        SimulacionTerminada = false;
    }

    private void ApplyFrame(UnitySimulationFrame frame)
    {
        if (frame.planted_cells != null)
        {
            for (int i = 0; i < frame.planted_cells.Length; i++)
            {
                UnityPlantedCell cell = frame.planted_cells[i];
                plantingGrid.MarkCellPlanted(cell.x, cell.y);
            }
        }

        if (frame.agents == null)
            return;

        for (int i = 0; i < frame.agents.Length; i++)
        {
            UnityAgentFrame agent = frame.agents[i];
            if (agent.pos == null || agent.pos.Length < 2)
                continue;

            GameObject tractor = GameObject.Find(
                "Tractor_" + (i + 1));
            if (tractor == null)
                continue;

            Vector2 position = plantingGrid.GetPlantingPosition(
                agent.pos[0],
                agent.pos[1]);
            tractor.transform.position =
                new Vector3(position.x, position.y, -0.2f);
        }
    }

    private void CreateMotherShip()
        {
            if (motherShip != null)
                return;

            Vector2 position = plantingGrid.GetPlantingPosition(0, 0);
            motherShip = new GameObject("NaveNodriza");
            motherShip.transform.position =
                new Vector3(position.x, position.y, -0.15f);
            motherShip.transform.localScale = Vector3.one * 0.6f;

            SpriteRenderer renderer =
                motherShip.AddComponent<SpriteRenderer>();
            renderer.sprite = CreateMotherShipSprite();
            renderer.sortingOrder = 5;
        }

    private Sprite CreateMotherShipSprite()
        {
            Texture2D texture = new Texture2D(
                32,
                32,
                TextureFormat.RGBA32,
                false);
            texture.filterMode = FilterMode.Point;

            for (int x = 0; x < 32; x++)
            {
                for (int y = 0; y < 32; y++)
                {
                    float dx = x - 15.5f;
                    float dy = y - 15.5f;
                    bool inside =
                        dx * dx / 190f + dy * dy / 80f <= 1f;
                    texture.SetPixel(
                        x,
                        y,
                        inside
                            ? new Color(0.15f, 0.38f, 0.7f)
                            : Color.clear);
                }
            }

            texture.Apply();
            return Sprite.Create(
                texture,
                new Rect(0, 0, 32, 32),
                new Vector2(0.5f, 0.5f),
                32);
    }

    private string BuildPayload()
    {
        int size = plantingGrid.gridCells;
        float[,] elevations = plantingGrid.GetElevationMatrix();
        int[,] obstacles = plantingGrid.GetObstacleMatrix();
        StringBuilder json = new StringBuilder(8192);

        json.Append("{");
        json.AppendFormat(
            CultureInfo.InvariantCulture,
            "\"grid_size\":[{0},{1}],",
            size,
            size);
        json.AppendFormat(
            CultureInfo.InvariantCulture,
            "\"difficulty\":{0},\"n_agents\":{1},",
            difficulty,
            agentCount);
        json.AppendFormat(
            CultureInfo.InvariantCulture,
            "\"estrategia\":\"{0}\",",
            estrategia);
        json.Append("\"depot_pos\":[0,0],\"elevation_map\":[");
        AppendFloatMatrix(json, elevations, size);
        json.Append("],\"obstacle_map\":[");
        AppendIntMatrix(json, obstacles, size);
        json.Append("]}");
        return json.ToString();
    }

    private void AppendFloatMatrix(
        StringBuilder json,
        float[,] matrix,
        int size)
    {
        for (int x = 0; x < size; x++)
        {
            if (x > 0)
                json.Append(",");
            json.Append("[");
            for (int y = 0; y < size; y++)
            {
                if (y > 0)
                    json.Append(",");
                json.Append(matrix[x, y].ToString(
                    "F4",
                    CultureInfo.InvariantCulture));
            }
            json.Append("]");
        }
    }

    private void AppendIntMatrix(
        StringBuilder json,
        int[,] matrix,
        int size)
    {
        for (int x = 0; x < size; x++)
        {
            if (x > 0)
                json.Append(",");
            json.Append("[");
            for (int y = 0; y < size; y++)
            {
                if (y > 0)
                    json.Append(",");
                json.Append(matrix[x, y]);
            }
            json.Append("]");
        }
    }

    private IEnumerator SendRequest(
        string payload,
        Action<string, string> callback)
    {
        byte[] body = Encoding.UTF8.GetBytes(payload);
        using (UnityWebRequest request =
            new UnityWebRequest(serverUrl, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(body);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = 30;
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
                callback(request.downloadHandler.text, null);
            else
                callback(null, request.error);
        }
    }

    private bool StartPythonServer()
    {
        try
        {
            if (pythonServer != null && !pythonServer.HasExited)
                return true;

            DirectoryInfo assets =
                new DirectoryInfo(Application.dataPath);
            DirectoryInfo projectRoot = assets.Parent != null
                ? assets.Parent.Parent
                : null;

            if (projectRoot == null)
                return false;

            string scriptPath = Path.Combine(
                projectRoot.FullName,
                "Agentes",
                "agentesPrueba.py");
            if (!File.Exists(scriptPath))
            {
                Debug.LogError(
                    "No se encontro el servidor Python en " + scriptPath);
                return false;
            }

            string python = "python";
            string venvPython = Path.Combine(
                projectRoot.FullName,
                ".venv",
                "Scripts",
                "python.exe");
            if (File.Exists(venvPython))
                python = venvPython;

            ProcessStartInfo info = new ProcessStartInfo
            {
                FileName = python,
                Arguments = "\"" + scriptPath + "\" --no-input",
                WorkingDirectory = projectRoot.FullName,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            pythonServer = Process.Start(info);
            return pythonServer != null;
        }
        catch (InvalidOperationException exception)
        {
            Debug.LogError(
                "No se pudo iniciar el servidor Python: " +
                exception.Message);
            return false;
        }
    }

    private void OnDestroy()
    {
        if (simulation != null)
            StopCoroutine(simulation);

        if (pythonServer != null && !pythonServer.HasExited)
            pythonServer.Kill();
    }
}
