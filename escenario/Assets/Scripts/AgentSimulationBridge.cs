using System;
using System.Collections;
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
public class UnitySimulationResponse
{
    public string status;
    public string message;
    public UnitySimulationFrame[] frames;
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

    public void StartSimulation(
        PlantingGrid grid,
        int numberOfAgents,
        int terrainDifficulty)
    {
        plantingGrid = grid;
        agentCount = numberOfAgents;
        difficulty = terrainDifficulty;
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

        for (int i = 0; i < simulationResponse.frames.Length; i++)
        {
            ApplyFrame(simulationResponse.frames[i]);
            yield return new WaitForSeconds(tickDuration);
        }
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
