
using System.Collections.Generic;
using UnityEngine;

public class GameSetupMenu : MonoBehaviour
{
    [Header("REFERENCIAS")]
    public TerrainGenerator terrain;
    public PlantingGrid plantingGrid;

    [Header("CONFIGURACION INICIAL")]
    public int agentCount = 3;
    public int obstacleCount = 35;

    private int selectedTerrain = 0;
    private bool simulationStarted = false;

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

    void Start()
    {
        // Ocultar el terreno hasta iniciar.
        terrain.gameObject.SetActive(false);
        plantingGrid.gameObject.SetActive(false);
    }

    void OnGUI()
    {
        if (simulationStarted)
            return;

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

    void StartSimulation()
    {
        // Configurar el terreno.
        terrain.generateOnStart = false;

        terrain.terrainType =
            (TerrainGenerator.TerrainType)selectedTerrain;

        terrain.gameObject.SetActive(true);

        terrain.GenerateTerrain();

        // Configurar cuadrícula y obstáculos.
        plantingGrid.generateOnStart = false;

        plantingGrid.terrain = terrain;
        plantingGrid.obstacleCount = obstacleCount;

        plantingGrid.gameObject.SetActive(true);

        plantingGrid.GenerateGrid();

        // Generar tractores.
        SpawnAgents();

        simulationStarted = true;
    }

    void SpawnAgents()
    {
        agentSprite = CreateAgentSprite();

        List<Vector2> positions = new List<Vector2>();

        for (int i = 0; i < agentCount; i++)
        {
            Vector2 position = Vector2.zero;
            bool found = false;

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

            GameObject agent = new GameObject(
                "Tractor_" + (i + 1)
            );

            agent.transform.position = new Vector3(
                position.x,
                position.y,
                -0.2f
            );

            agent.transform.localScale =
                new Vector3(0.30f, 0.23f, 1f);

            SpriteRenderer sr =
                agent.AddComponent<SpriteRenderer>();

            sr.sprite = agentSprite;
            sr.color = agentColors[i];
            sr.sortingOrder = 6;
        }

        Debug.Log("Tractores generados: " + positions.Count);
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

    GUIStyle CenterStyle()
    {
        return new GUIStyle(GUI.skin.label)
        {
            fontSize = 20,
            alignment = TextAnchor.MiddleCenter
        };
    }
}
