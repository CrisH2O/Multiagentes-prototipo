
using UnityEngine;

public class PlantingGrid : MonoBehaviour
{
    [Header("REFERENCIA DEL TERRENO")]
    public TerrainGenerator terrain;

    [Header("CONFIGURACION")]
    public int gridCells = 20;

    public float maxSlope = 25f;

    public float markerSize = 0.13f;

    [Header("OBSTACULOS")]
    public int obstacleCount = 35;

    [Header("INICIALIZACION")]
    public bool generateOnStart = true;

    private bool[,] plantable;
    private bool[,] blocked;

    private Sprite circleSprite;
    private Sprite squareSprite;

    void Start()
    {
        if (generateOnStart)
        {
            GenerateGrid();
        }
    }

    // =====================================
    // GENERAR CUADRICULA
    // =====================================

    [ContextMenu("Generar cuadrícula")]
    public void GenerateGrid()
    {
        if (terrain == null)
        {
            Debug.LogError(
                "No has asignado TerrainGenerator."
            );

            return;
        }

        if (gridCells < 1)
            gridCells = 1;

        // Eliminar elementos anteriores
        for (int i = transform.childCount - 1; i >= 0; i--)
        {
            Destroy(transform.GetChild(i).gameObject);
        }

        plantable = new bool[gridCells, gridCells];
        blocked = new bool[gridCells, gridCells];

        circleSprite = CreateSprite(true);
        squareSprite = CreateSprite(false);

        // Generar obstaculos aleatorios
        GenerateObstacles();

        float cellSize = terrain.worldSize / gridCells;

        Vector3 origin = terrain.transform.position;

        // Recorrer las celdas
        for (int x = 0; x < gridCells; x++)
        {
            for (int y = 0; y < gridCells; y++)
            {
                float worldX = origin.x
                    - terrain.worldSize / 2f
                    + (x + 0.5f) * cellSize;

                float worldY = origin.y
                    - terrain.worldSize / 2f
                    + (y + 0.5f) * cellSize;

                Vector2 position = new Vector2(
                    worldX,
                    worldY
                );

                float elevation;
                float slope;

                bool valid = terrain.GetTerrainData(
                    position,
                    out elevation,
                    out slope
                );

                if (!valid)
                    continue;

                // Determinar si se puede plantar
                plantable[x, y] = slope <= maxSlope;

                // Crear objeto visual
                GameObject point = new GameObject(
                    "Cell_" + x + "_" + y
                );

                point.transform.SetParent(transform);

                point.transform.position = new Vector3(
                    worldX,
                    worldY,
                    -0.1f
                );

                SpriteRenderer sr =
                    point.AddComponent<SpriteRenderer>();

                if (blocked[x, y])
                {
                    // Obstaculo oscuro
                    sr.sprite = squareSprite;

                    sr.color = new Color(
                        0.12f,
                        0.12f,
                        0.12f
                    );

                    point.transform.localScale =
                        Vector3.one * cellSize * 0.72f;

                    point.name =
                        "Obstacle_" + x + "_" + y;

                    sr.sortingOrder = 4;
                }
                else
                {
                    // Punto de plantacion
                    sr.sprite = circleSprite;

                    sr.color = plantable[x, y]
                        ? Color.green
                        : Color.red;

                    point.transform.localScale =
                        Vector3.one * markerSize;

                    sr.sortingOrder = 2;
                }
            }
        }

        Debug.Log(
            "Cuadricula generada. Obstaculos: "
            + obstacleCount
        );
    }

    // =====================================
    // GENERAR OBSTACULOS
    // =====================================

    private void GenerateObstacles()
    {
        int created = 0;
        int attempts = 0;

        while (
            created < obstacleCount &&
            attempts < gridCells * gridCells * 5
        )
        {
            attempts++;

            int x = Random.Range(0, gridCells);
            int y = Random.Range(0, gridCells);

            if (!blocked[x, y])
            {
                blocked[x, y] = true;
                created++;
            }
        }

        if (created < obstacleCount)
        {
            Debug.LogWarning(
                "No fue posible generar todos los obstaculos."
            );
        }
    }

    // =====================================
    // CONSULTAR SI SE PUEDE PLANTAR
    // =====================================

    public bool IsPlantable(int x, int y)
    {
        if (!InsideGrid(x, y))
            return false;

        return plantable[x, y] && !blocked[x, y];
    }

    // =====================================
    // CONSULTAR SI SE PUEDE TRANSITAR
    // =====================================

    public bool IsWalkable(int x, int y)
    {
        if (!InsideGrid(x, y))
            return false;

        // El tractor puede atravesar pendientes.
        // Los obstaculos son los que bloquean el paso.
        return !blocked[x, y];
    }

    // =====================================
    // CONSULTAR OBSTACULOS
    // =====================================

    public bool IsBlocked(int x, int y)
    {
        if (!InsideGrid(x, y))
            return true;

        return blocked[x, y];
    }

    // =====================================
    // VALIDAR COORDENADAS
    // =====================================

    private bool InsideGrid(int x, int y)
    {
        return plantable != null &&
            x >= 0 &&
            x < gridCells &&
            y >= 0 &&
            y < gridCells;
    }

    // =====================================
    // OBTENER POSICION DE UNA CELDA
    // =====================================

    public Vector2 GetPlantingPosition(int x, int y)
    {
        float cellSize = terrain.worldSize / gridCells;

        Vector3 origin = terrain.transform.position;

        return new Vector2(
            origin.x - terrain.worldSize / 2f
                + (x + 0.5f) * cellSize,

            origin.y - terrain.worldSize / 2f
                + (y + 0.5f) * cellSize
        );
    }

    // =====================================
    // BUSCAR POSICION TRANSITABLE ALEATORIA
    // =====================================

    public Vector2 GetRandomWalkablePosition()
    {
        for (int i = 0; i < 1000; i++)
        {
            int x = Random.Range(0, gridCells);
            int y = Random.Range(0, gridCells);

            if (IsWalkable(x, y))
            {
                return GetPlantingPosition(x, y);
            }
        }

        Debug.LogWarning(
            "No se encontro una posicion transitable."
        );

        return terrain.transform.position;
    }

    // =====================================
    // CREAR SPRITES
    // =====================================

    private Sprite CreateSprite(bool circle)
    {
        int size = 32;

        Texture2D texture = new Texture2D(
            size,
            size,
            TextureFormat.RGBA32,
            false
        );

        texture.filterMode = FilterMode.Bilinear;

        for (int x = 0; x < size; x++)
        {
            for (int y = 0; y < size; y++)
            {
                float dx = x - size / 2f;
                float dy = y - size / 2f;

                bool inside = circle
                    ? dx * dx + dy * dy < 150f
                    : true;

                texture.SetPixel(
                    x,
                    y,
                    inside ? Color.white : Color.clear
                );
            }
        }

        texture.Apply();

        return Sprite.Create(
            texture,
            new Rect(0, 0, size, size),
            new Vector2(0.5f, 0.5f),
            size
        );
    }
}
