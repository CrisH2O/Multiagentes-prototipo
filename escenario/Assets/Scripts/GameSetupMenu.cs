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
public class GridCoordData
{
    public int x;
    public int y;
}

[Serializable]
public class AgentFrameData
{
    public int id;
    public int[] pos;
    public float fuel;
    public int seeds;
    public string state;
    public int planted_total;
}

[Serializable]
public class SimulationFrameData
{
    public int tick;
    public int remaining_cells;
    public GridCoordData[] planted_cells;
    public AgentFrameData[] agents;
}

[Serializable]
public class SimulationMetricsData
{
    public int total_ticks;
    public int total_steps;
    public float total_fuel_consumed;
    public float driver_wage_cost;
    public float seed_cost;
    public int remaining_cells;
}

[Serializable]
public class SimulationResponseData
{
    public string status;
    public string message;
    public int[] depot_pos;
    public SimulationMetricsData metrics;
    public SimulationFrameData[] frames;
}

[Serializable]
public class PendingConfigData
{
    public bool has_config;
    public int difficulty;
    public int n_agents;
    public int obstacles;
}

public class GameSetupMenu : MonoBehaviour
{
    [Header("REFERENCIAS")]
    public TerrainGenerator terrain;
    public PlantingGrid plantingGrid;

    [Header("CONFIGURACION INICIAL")]
    public int agentCount = 3;
    public int obstacleCount = 35;

    [Header("CONEXION PYTHON (agentesPrueba.py)")]
    public string serverUrl = "http://127.0.0.1:5000/simulate";
    public float tickDuration = 0.14f;

    private int selectedTerrain = 0;
    private bool simulationStarted = false;
    private bool isPaused = false;
    private string statusMessage = "";

    private string[] terrainNames =
    {
        "Plano",
        "Medio",
        "Montanoso"
    };

    private Sprite agentSprite;

    private Color[] agentColors =
    {
        Color.blue,
        Color.cyan,
        Color.magenta,
        Color.white,
        new Color(1f, 0.5f, 0f),
        Color.yellow,
        new Color(0.5f, 0.2f, 1f),
        new Color(0.2f, 0.8f, 0.8f)
    };

    private readonly List<GameObject> spawnedAgents = new List<GameObject>();
    private SimulationFrameData currentFrame;
    private SimulationMetricsData finalMetrics;
    private int totalFrames = 0;
    private Coroutine simulationCoroutine;
    private Process pythonServerProcess;

    void Start()
    {
        if (terrain != null)
            terrain.gameObject.SetActive(false);

        if (plantingGrid != null)
            plantingGrid.gameObject.SetActive(false);

        StartCoroutine(PollPendingConfigFromPython());
    }

    IEnumerator PollPendingConfigFromPython()
    {
        while (true)
        {
            yield return new WaitForSeconds(1.0f);

            string baseUrl = serverUrl;
            int idx = baseUrl.LastIndexOf('/');
            string pollUrl = (idx > 7 ? baseUrl.Substring(0, idx) : baseUrl) + "/pending_config";

            using (UnityWebRequest req = UnityWebRequest.Get(pollUrl))
            {
                req.timeout = 2;
                yield return req.SendWebRequest();

                if (req.result == UnityWebRequest.Result.Success)
                {
                    PendingConfigData cfg = JsonUtility.FromJson<PendingConfigData>(req.downloadHandler.text);
                    if (cfg != null && cfg.has_config)
                    {
                        selectedTerrain = Mathf.Clamp(cfg.difficulty - 1, 0, terrainNames.Length - 1);
                        agentCount = Mathf.Clamp(cfg.n_agents, 1, 8);
                        obstacleCount = Mathf.Clamp(cfg.obstacles, 0, 150);
                        StartSimulation();
                    }
                }
            }
        }
    }

    void OnDestroy()
    {
        StopAutoStartedPythonServer();
    }

    void OnApplicationQuit()
    {
        StopAutoStartedPythonServer();
    }

    void OnGUI()
    {
        if (!simulationStarted)
        {
            DrawSetupMenu();
        }
        else
        {
            DrawSimulationHUD();
        }
    }

    void DrawSetupMenu()
    {
        GUI.Box(
            new Rect(
                Screen.width / 2f - 190,
                Screen.height / 2f - 220,
                380,
                440
            ),
            ""
        );

        GUILayout.BeginArea(new Rect(
            Screen.width / 2f - 165,
            Screen.height / 2f - 200,
            330,
            400
        ));

        GUILayout.Space(10);

        GUILayout.Label(
            "SIMULADOR AGRICOLA",
            TitleStyle()
        );

        GUILayout.Space(20);

        GUILayout.Label("SELECCIONAR TERRENO");

        for (int i = 0; i < terrainNames.Length; i++)
        {
            string label = selectedTerrain == i
                ? "> " + terrainNames[i] + " <"
                : terrainNames[i];

            if (GUILayout.Button(label, GUILayout.Height(35)))
            {
                selectedTerrain = i;
            }
        }

        GUILayout.Space(20);

        GUILayout.Label("CANTIDAD DE TRACTORES");

        GUILayout.BeginHorizontal();

        if (GUILayout.Button("-", GUILayout.Width(50)))
            agentCount = Mathf.Max(1, agentCount - 1);

        GUILayout.Label(
            agentCount.ToString(),
            CenterStyle()
        );

        if (GUILayout.Button("+", GUILayout.Width(50)))
            agentCount = Mathf.Min(8, agentCount + 1);

        GUILayout.EndHorizontal();

        GUILayout.Space(20);

        GUILayout.Label("CANTIDAD DE OBSTACULOS");

        GUILayout.BeginHorizontal();

        if (GUILayout.Button("-", GUILayout.Width(50)))
            obstacleCount = Mathf.Max(0, obstacleCount - 5);

        GUILayout.Label(
            obstacleCount.ToString(),
            CenterStyle()
        );

        if (GUILayout.Button("+", GUILayout.Width(50)))
            obstacleCount = Mathf.Min(150, obstacleCount + 5);

        GUILayout.EndHorizontal();

        GUILayout.Space(30);

        if (GUILayout.Button(
            "Comenzar",
            GUILayout.Height(45)))
        {
            StartSimulation();
        }

        GUILayout.EndArea();
    }

    void DrawSimulationHUD()
    {
        float panelWidth = 310f;
        float panelHeight = Mathf.Min(Screen.height - 20f, 620f);

        GUI.Box(new Rect(10f, 10f, panelWidth, panelHeight), "");

        GUILayout.BeginArea(new Rect(20f, 18f, panelWidth - 20f, panelHeight - 16f));

        GUILayout.Label("CONTROL DE SIMULACION", SubtitleStyle());
        GUILayout.Space(4);
        GUILayout.Label("Estado: " + statusMessage);

        int tick = currentFrame != null ? currentFrame.tick : 0;
        int remaining = currentFrame != null ? currentFrame.remaining_cells : 0;

        GUILayout.Label($"Tick: {tick} / {totalFrames}");
        GUILayout.Label($"Celdas por sembrar: {remaining}");

        GUILayout.Space(6);
        GUILayout.BeginHorizontal();
        if (GUILayout.Button(isPaused ? "Reanudar" : "Pausar", GUILayout.Height(26)))
        {
            isPaused = !isPaused;
        }
        if (GUILayout.Button("Vel -", GUILayout.Width(60), GUILayout.Height(26)))
        {
            tickDuration = Mathf.Min(0.60f, tickDuration + 0.04f);
        }
        if (GUILayout.Button("Vel +", GUILayout.Width(60), GUILayout.Height(26)))
        {
            tickDuration = Mathf.Max(0.02f, tickDuration - 0.04f);
        }
        GUILayout.EndHorizontal();

        if (currentFrame != null && currentFrame.agents != null)
        {
            GUILayout.Space(8);
            GUILayout.Label("TRACTORES EN CAMPO:", SubtitleStyle());

            for (int i = 0; i < currentFrame.agents.Length; i++)
            {
                AgentFrameData a = currentFrame.agents[i];
                int gx = (a.pos != null && a.pos.Length > 0) ? a.pos[0] : 0;
                int gy = (a.pos != null && a.pos.Length > 1) ? a.pos[1] : 0;

                GUILayout.Label(
                    $"T{i + 1} ({gx},{gy}) [{a.state}] | Gas:{a.fuel:F1} | Sem:{a.seeds} | Sembradas:{a.planted_total}"
                );
            }
        }

        if (finalMetrics != null)
        {
            GUILayout.Space(8);
            GUILayout.Label("METRICAS FINALES:", SubtitleStyle());
            GUILayout.Label($"Combustible usado: {finalMetrics.total_fuel_consumed:F2} L");
            GUILayout.Label($"Costo salarios: ${finalMetrics.driver_wage_cost:F2}");
            GUILayout.Label($"Costo semillas: ${finalMetrics.seed_cost:F2}");
        }

        GUILayout.Space(10);
        if (GUILayout.Button("Nueva Simulacion", GUILayout.Height(32)))
        {
            ResetToSetupMenu();
        }

        GUILayout.EndArea();
    }

    void StartSimulation()
    {
        if (simulationCoroutine != null)
        {
            StopCoroutine(simulationCoroutine);
            simulationCoroutine = null;
        }

        currentFrame = null;
        finalMetrics = null;
        totalFrames = 0;
        isPaused = false;
        statusMessage = "Generando escenario...";

        // Configurar el terreno.
        terrain.generateOnStart = false;
        terrain.terrainType = (TerrainGenerator.TerrainType)selectedTerrain;
        terrain.gameObject.SetActive(true);
        terrain.GenerateTerrain();

        // Configurar cuadrícula y obstáculos.
        plantingGrid.generateOnStart = false;
        plantingGrid.terrain = terrain;
        plantingGrid.obstacleCount = obstacleCount;
        plantingGrid.gameObject.SetActive(true);
        plantingGrid.GenerateGrid();

        // Generar tractores en la estación base (0,0).
        SpawnAgentsAtDepot();

        simulationStarted = true;

        // Conectar con agentesPrueba.py y reproducir la simulación en tiempo real.
        simulationCoroutine = StartCoroutine(RunPythonSimulationCoroutine());
    }

    void ResetToSetupMenu()
    {
        if (simulationCoroutine != null)
        {
            StopCoroutine(simulationCoroutine);
            simulationCoroutine = null;
        }

        ClearSpawnedAgents();

        if (terrain != null)
            terrain.gameObject.SetActive(false);

        if (plantingGrid != null)
            plantingGrid.gameObject.SetActive(false);

        simulationStarted = false;
    }

    void ClearSpawnedAgents()
    {
        for (int i = 0; i < spawnedAgents.Count; i++)
        {
            if (spawnedAgents[i] != null)
            {
                Destroy(spawnedAgents[i]);
            }
        }
        spawnedAgents.Clear();
    }

    void SpawnAgentsAtDepot()
    {
        ClearSpawnedAgents();
        agentSprite = CreateAgentSprite();

        Vector2 depotWorldPos = plantingGrid.GetPlantingPosition(0, 0);

        for (int i = 0; i < agentCount; i++)
        {
            GameObject agent = new GameObject("Tractor_" + (i + 1));
            Vector2 offset = GetDepotOffset(i, agentCount);

            agent.transform.position = new Vector3(
                depotWorldPos.x + offset.x,
                depotWorldPos.y + offset.y,
                -0.2f
            );

            agent.transform.localScale = new Vector3(0.30f, 0.23f, 1f);

            SpriteRenderer sr = agent.AddComponent<SpriteRenderer>();
            sr.sprite = agentSprite;
            sr.color = agentColors[i % agentColors.Length];
            sr.sortingOrder = 6 + i;

            spawnedAgents.Add(agent);
        }

        Debug.Log("Tractores generados en la base (0,0): " + spawnedAgents.Count);
    }

    Vector2 GetDepotOffset(int index, int total)
    {
        if (total <= 1)
            return Vector2.zero;

        float angle = (2f * Mathf.PI * index) / total;
        return new Vector2(Mathf.Cos(angle), Mathf.Sin(angle)) * 0.08f;
    }

    IEnumerator RunPythonSimulationCoroutine()
    {
        statusMessage = "Conectando con agentesPrueba.py...";
        string jsonPayload = BuildSimulationRequestJson();

        string responseJson = null;
        string errorMsg = null;

        yield return SendSimulationRequest(jsonPayload, (res, err) =>
        {
            responseJson = res;
            errorMsg = err;
        });

        // Si el servidor Python no estaba encendido aún, iniciarlo automáticamente y reintentar
        if (string.IsNullOrEmpty(responseJson))
        {
            statusMessage = "Iniciando servidor agentesPrueba.py...";
            bool started = TryStartPythonServer();

            if (started)
            {
                for (int retry = 0; retry < 10; retry++)
                {
                    yield return new WaitForSeconds(0.5f);
                    yield return SendSimulationRequest(jsonPayload, (res, err) =>
                    {
                        responseJson = res;
                        errorMsg = err;
                    });

                    if (!string.IsNullOrEmpty(responseJson))
                        break;
                }
            }
        }

        if (string.IsNullOrEmpty(responseJson))
        {
            statusMessage = "Error de conexion con Python: " + errorMsg;
            Debug.LogError(
                "No se pudo conectar con agentesPrueba.py en " + serverUrl +
                ". Detalle: " + errorMsg
            );
            yield break;
        }

        SimulationResponseData simResponse =
            JsonUtility.FromJson<SimulationResponseData>(responseJson);

        if (simResponse == null || simResponse.status != "success" || simResponse.frames == null)
        {
            statusMessage = "Error en respuesta de simulacion.";
            Debug.LogError("Respuesta invalida de agentesPrueba.py: " + responseJson);
            yield break;
        }

        finalMetrics = simResponse.metrics;
        totalFrames = simResponse.frames.Length;
        statusMessage = "Simulando en tiempo real...";

        Vector3[] startPositions = new Vector3[spawnedAgents.Count];
        Vector3[] targetPositions = new Vector3[spawnedAgents.Count];
        int[] prevPlantedTotals = new int[spawnedAgents.Count];

        for (int f = 0; f < simResponse.frames.Length; f++)
        {
            while (isPaused)
            {
                yield return null;
            }

            SimulationFrameData frame = simResponse.frames[f];
            currentFrame = frame;

            // Calcular posiciones destino para cada tractor en este tick
            for (int i = 0; i < spawnedAgents.Count; i++)
            {
                if (spawnedAgents[i] == null)
                    continue;

                startPositions[i] = spawnedAgents[i].transform.position;

                if (frame.agents != null && i < frame.agents.Length)
                {
                    AgentFrameData agentData = frame.agents[i];
                    int gx = (agentData.pos != null && agentData.pos.Length > 0) ? agentData.pos[0] : 0;
                    int gy = (agentData.pos != null && agentData.pos.Length > 1) ? agentData.pos[1] : 0;

                    Vector2 cellWorld = plantingGrid.GetPlantingPosition(gx, gy);
                    Vector2 offset = (gx == 0 && gy == 0)
                        ? GetDepotOffset(i, spawnedAgents.Count)
                        : Vector2.zero;

                    targetPositions[i] = new Vector3(
                        cellWorld.x + offset.x,
                        cellWorld.y + offset.y,
                        -0.2f
                    );
                }
                else
                {
                    targetPositions[i] = startPositions[i];
                }
            }

            // Interpolar suavemente el movimiento de todos los tractores durante el tick
            float duration = Mathf.Max(0.01f, tickDuration);
            float elapsed = 0f;

            while (elapsed < duration)
            {
                while (isPaused)
                {
                    yield return null;
                }

                elapsed += Time.deltaTime;
                float t = Mathf.Clamp01(elapsed / duration);

                for (int i = 0; i < spawnedAgents.Count; i++)
                {
                    if (spawnedAgents[i] != null)
                    {
                        spawnedAgents[i].transform.position = Vector3.Lerp(
                            startPositions[i],
                            targetPositions[i],
                            t
                        );
                    }
                }

                yield return null;
            }

            for (int i = 0; i < spawnedAgents.Count; i++)
            {
                if (spawnedAgents[i] != null)
                {
                    spawnedAgents[i].transform.position = targetPositions[i];
                }
            }

            // Marcar las celdas sembradas en este tick
            if (frame.planted_cells != null)
            {
                for (int c = 0; c < frame.planted_cells.Length; c++)
                {
                    plantingGrid.MarkCellPlanted(
                        frame.planted_cells[c].x,
                        frame.planted_cells[c].y
                    );
                }
            }

            if (frame.agents != null)
            {
                for (int i = 0; i < frame.agents.Length && i < prevPlantedTotals.Length; i++)
                {
                    AgentFrameData a = frame.agents[i];
                    if (a.planted_total > prevPlantedTotals[i] && a.pos != null && a.pos.Length >= 2)
                    {
                        plantingGrid.MarkCellPlanted(a.pos[0], a.pos[1]);
                    }
                    prevPlantedTotals[i] = a.planted_total;
                }
            }
        }

        statusMessage = "Simulacion completada";
        Debug.Log(
            $"Simulacion finalizada en {totalFrames} ticks. " +
            $"Combustible: {finalMetrics.total_fuel_consumed:F2} L"
        );
    }

    IEnumerator SendSimulationRequest(string jsonPayload, Action<string, string> callback)
    {
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonPayload);

        using (UnityWebRequest request = new UnityWebRequest(serverUrl, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = 30;

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                callback(request.downloadHandler.text, null);
            }
            else
            {
                callback(null, request.error);
            }
        }
    }

    string BuildSimulationRequestJson()
    {
        int n = plantingGrid.gridCells;
        int difficulty = selectedTerrain + 1;
        float[,] elevations = plantingGrid.GetElevationMatrix();
        int[,] obstacles = plantingGrid.GetObstacleMatrix();

        StringBuilder sb = new StringBuilder(8192);
        sb.Append("{");
        sb.AppendFormat(CultureInfo.InvariantCulture, "\"grid_size\":[{0},{1}],", n, n);
        sb.AppendFormat(CultureInfo.InvariantCulture, "\"difficulty\":{0},", difficulty);
        sb.AppendFormat(CultureInfo.InvariantCulture, "\"n_agents\":{0},", agentCount);
        sb.Append("\"depot_pos\":[0,0],");

        sb.Append("\"elevation_map\":[");
        for (int x = 0; x < n; x++)
        {
            if (x > 0) sb.Append(",");
            sb.Append("[");
            for (int y = 0; y < n; y++)
            {
                if (y > 0) sb.Append(",");
                sb.Append(elevations[x, y].ToString("F4", CultureInfo.InvariantCulture));
            }
            sb.Append("]");
        }
        sb.Append("],");

        sb.Append("\"obstacle_map\":[");
        for (int x = 0; x < n; x++)
        {
            if (x > 0) sb.Append(",");
            sb.Append("[");
            for (int y = 0; y < n; y++)
            {
                if (y > 0) sb.Append(",");
                sb.Append(obstacles[x, y]);
            }
            sb.Append("]");
        }
        sb.Append("]");

        sb.Append("}");
        return sb.ToString();
    }

    bool TryStartPythonServer()
    {
        try
        {
            if (pythonServerProcess != null && !pythonServerProcess.HasExited)
                return true;

            // Application.dataPath apunta a .../Multiagentes-prototipo/escenario/Assets
            DirectoryInfo assetsDir = new DirectoryInfo(Application.dataPath);
            DirectoryInfo projectRoot = assetsDir.Parent != null && assetsDir.Parent.Parent != null
                ? assetsDir.Parent.Parent
                : assetsDir.Parent;

            if (projectRoot == null)
                return false;

            string scriptPath = Path.Combine(projectRoot.FullName, "agentes", "agentesPrueba.py");
            if (!File.Exists(scriptPath))
            {
                scriptPath = Path.Combine(projectRoot.FullName, "Agentes", "agentesPrueba.py");
            }
            if (!File.Exists(scriptPath))
            {
                Debug.LogWarning("No se encontro agentesPrueba.py en: " + scriptPath);
                return false;
            }

            string venvPythonWin = Path.Combine(projectRoot.FullName, ".venv", "Scripts", "python.exe");
            string venvPythonUnix = Path.Combine(projectRoot.FullName, ".venv", "bin", "python");

            string pythonExe = "python";
            if (File.Exists(venvPythonWin))
                pythonExe = venvPythonWin;
            else if (File.Exists(venvPythonUnix))
                pythonExe = venvPythonUnix;

            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = $"\"{scriptPath}\" --no-input",
                WorkingDirectory = projectRoot.FullName,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            pythonServerProcess = Process.Start(startInfo);
            Debug.Log("Servidor Python iniciado automaticamente con: " + pythonExe);
            return pythonServerProcess != null;
        }
        catch (Exception ex)
        {
            Debug.LogWarning("No se pudo iniciar automaticamente agentesPrueba.py: " + ex.Message);
            return false;
        }
    }

    void StopAutoStartedPythonServer()
    {
        try
        {
            if (pythonServerProcess != null && !pythonServerProcess.HasExited)
            {
                pythonServerProcess.Kill();
                pythonServerProcess.Dispose();
                pythonServerProcess = null;
            }
        }
        catch
        {
            // Ignorar errores al cerrar el proceso secundario
        }
    }

    Sprite CreateAgentSprite()
    {
        Texture2D texture = new Texture2D(16, 16);

        for (int x = 0; x < 16; x++)
        {
            for (int y = 0; y < 16; y++)
            {
                texture.SetPixel(x, y, Color.white);
            }
        }

        texture.Apply();

        return Sprite.Create(
            texture,
            new Rect(0, 0, 16, 16),
            new Vector2(0.5f, 0.5f),
            16
        );
    }

    GUIStyle TitleStyle()
    {
        return new GUIStyle(GUI.skin.label)
        {
            fontSize = 24,
            fontStyle = FontStyle.Bold,
            alignment = TextAnchor.MiddleCenter
        };
    }

    GUIStyle SubtitleStyle()
    {
        return new GUIStyle(GUI.skin.label)
        {
            fontSize = 14,
            fontStyle = FontStyle.Bold
        };
    }

    GUIStyle CenterStyle()
    {
        return new GUIStyle(GUI.skin.label)
        {
            fontSize = 20,
            alignment = TextAnchor.MiddleCenter
        };
    }
}
