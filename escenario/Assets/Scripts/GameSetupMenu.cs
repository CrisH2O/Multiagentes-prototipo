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
    [Tooltip("Semilla del escenario: misma semilla = mismo mapa")]
    public int semilla = 1;

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

    // Tonalidades para distinguir los tractores
    private Color[] agentColors =
    {
        new Color(0.12f, 0.48f, 0.16f),
        new Color(0.30f, 0.60f, 0.18f),
        new Color(0.48f, 0.58f, 0.12f),
        new Color(0.10f, 0.38f, 0.28f),
        new Color(0.65f, 0.62f, 0.12f),
        new Color(0.18f, 0.55f, 0.38f),
        new Color(0.35f, 0.45f, 0.12f),
        new Color(0.15f, 0.42f, 0.45f)
    };

    // =====================================
    // INICIALIZACION
    // =====================================

    void Start()
    {
        terrain.gameObject.SetActive(false);
        plantingGrid.gameObject.SetActive(false);
    }

    // =====================================
    // MENU PRINCIPAL
    // =====================================

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

        // Dimensiones adaptables
        float panelWidth = Mathf.Min(420f, Screen.width - 30f);
        float panelHeight = Mathf.Min(500f, Screen.height - 30f);

        float x = (Screen.width - panelWidth) / 2f;
        float y = (Screen.height - panelHeight) / 2f;

        GUI.Box(
            new Rect(x, y, panelWidth, panelHeight),
            ""
        );

        GUILayout.BeginArea(
            new Rect(
                x + 25,
                y + 15,
                panelWidth - 50,
                panelHeight - 30
            )
        );

        // Scroll de seguridad para pantallas pequeñas
        GUILayout.BeginScrollView(
            Vector2.zero,
            false,
            false
        );

        GUILayout.Space(5);

        GUILayout.Label(
            "SIMULADOR AGRICOLA",
            TitleStyle(),
            GUILayout.Height(35)
        );

        GUILayout.Space(10);

        GUILayout.Label("SELECCIONAR TERRENO");

        GUILayout.Space(5);

        // Seleccion de terreno
        for (int i = 0; i < terrainNames.Length; i++)
        {
            string label = selectedTerrain == i
                ? "> " + terrainNames[i] + " <"
                : terrainNames[i];

            if (GUILayout.Button(
                label,
                GUILayout.Height(33)))
            {
                selectedTerrain = i;
            }
        }

        GUILayout.Space(15);

        // Cantidad de tractores
        GUILayout.Label("CANTIDAD DE TRACTORES");

        GUILayout.BeginHorizontal();

        if (GUILayout.Button("-", GUILayout.Width(55)))
        {
            agentCount = Mathf.Max(1, agentCount - 1);
        }

        GUILayout.Label(
            agentCount.ToString(),
            CenterStyle()
        );

        if (GUILayout.Button("+", GUILayout.Width(55)))
        {
            agentCount = Mathf.Min(8, agentCount + 1);
        }

        GUILayout.EndHorizontal();

        GUILayout.Space(15);

        // Cantidad de obstaculos
        GUILayout.Label("CANTIDAD DE OBSTACULOS");

        GUILayout.BeginHorizontal();

        if (GUILayout.Button("-", GUILayout.Width(55)))
        {
            obstacleCount = Mathf.Max(0, obstacleCount - 5);
        }

        GUILayout.Label(
            obstacleCount.ToString(),
            CenterStyle()
        );

        if (GUILayout.Button("+", GUILayout.Width(55)))
        {
            obstacleCount = Mathf.Min(150, obstacleCount + 5);
        }

        GUILayout.EndHorizontal();

        GUILayout.Space(22);

        // BOTON COMENZAR
        if (GUILayout.Button(
            "COMENZAR",
            GUILayout.Height(48),
            GUILayout.ExpandWidth(true)))
        {
            StartSimulation();
        }

        GUILayout.Space(5);

        GUILayout.Label(
            "Configura tu escenario agricola",
            SubtitleStyle()
        );

        GUILayout.EndScrollView();

        GUILayout.EndArea();
    }

    // =====================================
    // INICIAR SIMULACION
    // =====================================

    void StartSimulation()
    {
        if (terrain == null || plantingGrid == null)
        {
            Debug.LogError("Faltan referencias del terreno.");
            return;
        }

        // Configurar terreno
        terrain.generateOnStart = false;
        terrain.terrainType = (TerrainGenerator.TerrainType)selectedTerrain;
        terrain.gameObject.SetActive(true);
        terrain.GenerateTerrain();

        // Configurar cuadrícula y obstaculos
        plantingGrid.generateOnStart = false;
        plantingGrid.terrain = terrain;
        plantingGrid.obstacleCount = obstacleCount;
        plantingGrid.semilla = semilla;
        plantingGrid.gameObject.SetActive(true);
        plantingGrid.GenerateGrid();

        // Generar tractores
        SpawnAgents();

        simulationStarted = true;

        AgentSimulationBridge bridge =
            GetComponent<AgentSimulationBridge>();
        if (bridge == null)
            bridge = gameObject.AddComponent<AgentSimulationBridge>();

        bridge.StartSimulation(
            plantingGrid,
            agentCount,
            selectedTerrain + 1);
    }

    // =====================================
    // GENERAR TRACTORES
    // =====================================

    void SpawnAgents()
    {
        List<Vector2> positions = new List<Vector2>();

        for (int i = 0; i < agentCount; i++)
        {
            Vector2 position = Vector2.zero;
            bool found = false;

            // Buscar posicion libre
            for (int attempt = 0; attempt < 100; attempt++)
            {
                Vector2 candidate =
                    plantingGrid.GetRandomWalkablePosition();

                bool occupied = false;

                foreach (Vector2 existing in positions)
                {
                    if (Vector2.Distance(candidate, existing) < 0.3f)
                    {
                        occupied = true;
                        break;
                    }
                }

                if (!occupied)
                {
                    position = candidate;
                    found = true;
                    break;
                }
            }

            if (!found)
            {
                Debug.LogWarning(
                    "No hay suficientes posiciones para todos los tractores."
                );

                break;
            }

            positions.Add(position);

            // Crear tractor
            GameObject agent = new GameObject(
                "Tractor_" + (i + 1)
            );

            agent.transform.position = new Vector3(
                depotWorldPos.x + offset.x,
                depotWorldPos.y + offset.y,
                -0.2f
            );

            // Tamaño del tractor
            agent.transform.localScale =
                new Vector3(0.42f, 0.42f, 1f);

            // Crear sprite personalizado
            SpriteRenderer sr =
                agent.AddComponent<SpriteRenderer>();

            sr.sprite = CreateAgentSprite(agentColors[i]);
            sr.sortingOrder = 6;
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

    // =====================================
    // CREAR TRACTOR CLASICO DESDE ARRIBA
    // =====================================

    Sprite CreateAgentSprite(Color bodyColor)
    {
        int size = 64;

        Texture2D texture = new Texture2D(
            size,
            size,
            TextureFormat.RGBA32,
            false
        );

        texture.filterMode = FilterMode.Point;
        texture.wrapMode = TextureWrapMode.Clamp;

        // Fondo transparente
        Color clear = new Color(0, 0, 0, 0);

        for (int x = 0; x < size; x++)
        {
            for (int y = 0; y < size; y++)
            {
                texture.SetPixel(x, y, clear);
            }
        }

        Color dark = new Color(0.08f, 0.10f, 0.08f);
        Color wheel = new Color(0.12f, 0.13f, 0.12f);
        Color wheelCenter = new Color(0.38f, 0.40f, 0.35f);
        Color glass = new Color(0.30f, 0.72f, 0.85f);
        Color glassLight = new Color(0.65f, 0.88f, 0.94f);
        Color bodyLight = Color.Lerp(bodyColor, Color.white, 0.25f);
        Color bodyDark = Color.Lerp(bodyColor, Color.black, 0.30f);
        Color headlight = new Color(1f, 0.90f, 0.45f);

        // ---------------------------------
        // RUEDAS TRASERAS
        // ---------------------------------

        FillRect(texture, 5, 10, 17, 31, dark);
        FillRect(texture, 47, 10, 59, 31, dark);

        FillRect(texture, 7, 12, 15, 29, wheel);
        FillRect(texture, 49, 12, 57, 29, wheel);

        FillRect(texture, 9, 16, 13, 25, wheelCenter);
        FillRect(texture, 51, 16, 55, 25, wheelCenter);

        // ---------------------------------
        // RUEDAS DELANTERAS
        // ---------------------------------

        FillRect(texture, 9, 39, 19, 57, dark);
        FillRect(texture, 45, 39, 55, 57, dark);

        FillRect(texture, 11, 41, 17, 55, wheel);
        FillRect(texture, 47, 41, 53, 55, wheel);

        FillRect(texture, 13, 45, 15, 52, wheelCenter);
        FillRect(texture, 49, 45, 51, 52, wheelCenter);

        // ---------------------------------
        // CHASIS CENTRAL
        // ---------------------------------

        FillRect(texture, 19, 7, 45, 47, dark);
        FillRect(texture, 21, 8, 43, 46, bodyDark);
        FillRect(texture, 23, 10, 41, 44, bodyColor);

        // ---------------------------------
        // CARROCERIA TRASERA
        // ---------------------------------

        FillRect(texture, 19, 8, 45, 24, bodyColor);
        FillRect(texture, 21, 10, 43, 22, bodyLight);

        // ---------------------------------
        // CAPO DELANTERO
        // ---------------------------------

        FillRect(texture, 22, 40, 42, 57, bodyDark);
        FillRect(texture, 24, 41, 40, 55, bodyColor);

        FillRect(texture, 26, 43, 38, 53, bodyLight);

        // Parte frontal
        FillRect(texture, 25, 54, 39, 57, dark);
        FillRect(texture, 27, 54, 37, 55, wheelCenter);

        // ---------------------------------
        // CABINA
        // ---------------------------------

        FillRect(texture, 18, 23, 46, 41, dark);
        FillRect(texture, 20, 25, 44, 39, bodyColor);

        // Cristal trasero
        FillRect(texture, 23, 26, 41, 30, glass);

        // Cristal delantero
        FillRect(texture, 23, 34, 41, 38, glass);

        // Reflejos
        FillRect(texture, 24, 35, 27, 37, glassLight);
        FillRect(texture, 24, 27, 27, 29, glassLight);

        // Marcos laterales
        FillRect(texture, 20, 31, 22, 33, dark);
        FillRect(texture, 42, 31, 44, 33, dark);

        // ---------------------------------
        // DETALLES DEL TRACTOR
        // ---------------------------------

        // Luces delanteras
        FillRect(texture, 22, 55, 25, 59, headlight);
        FillRect(texture, 39, 55, 42, 59, headlight);

        // Escape
        FillRect(texture, 29, 47, 35, 50, dark);
        FillRect(texture, 31, 48, 33, 49, wheelCenter);

        // Detalle trasero
        FillRect(texture, 28, 7, 36, 10, dark);

        texture.Apply();

        return Sprite.Create(
            texture,
            new Rect(0, 0, size, size),
            new Vector2(0.5f, 0.5f),
            size
        );
    }

    // =====================================
    // DIBUJAR RECTANGULOS EN LA TEXTURA
    // =====================================

    void FillRect(
        Texture2D texture,
        int xMin,
        int yMin,
        int xMax,
        int yMax,
        Color color)
    {
        for (int x = xMin; x <= xMax; x++)
        {
            for (int y = yMin; y <= yMax; y++)
            {
                texture.SetPixel(x, y, color);
            }
        }
    }

    // =====================================
    // ESTILOS DEL MENU
    // =====================================

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

    GUIStyle SubtitleStyle()
    {
        return new GUIStyle(GUI.skin.label)
        {
            fontSize = 11,
            alignment = TextAnchor.MiddleCenter,
            normal =
            {
                textColor = Color.gray
            }
        };
    }
}
