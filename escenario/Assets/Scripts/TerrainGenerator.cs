
using UnityEngine;

[RequireComponent(typeof(SpriteRenderer))]
public class TerrainGenerator : MonoBehaviour
{
    public enum TerrainType
    {
        Plano,
        Colinas,
        Montanoso
    }

    [Header("ESCENARIO")]
    public TerrainType terrainType = TerrainType.Plano;

    [Header("DIMENSIONES")]
    public int resolution = 256;
    public int gridCells = 20;
    public float worldSize = 10f;
    public float heightScale = 5f;

    [Header("VISUALIZACION")]
    public bool showGrid = true;
    public bool showContours = true;

    [Header("INICIALIZACION")]
    public bool generateOnStart = true;

    private float[,] heights;
    private Texture2D terrainTexture;
    private SpriteRenderer spriteRenderer;

    void Start()
    {
        if (generateOnStart)
        {
            GenerateTerrain();
        }
    }

    [ContextMenu("Generar terreno")]
    public void GenerateTerrain()
    {
        resolution = Mathf.Max(32, resolution);
        gridCells = Mathf.Max(1, gridCells);

        spriteRenderer = GetComponent<SpriteRenderer>();

        heights = new float[resolution, resolution];

        // Crear textura
        terrainTexture = new Texture2D(
            resolution,
            resolution,
            TextureFormat.RGBA32,
            false
        );

        terrainTexture.filterMode = FilterMode.Bilinear;
        terrainTexture.wrapMode = TextureWrapMode.Clamp;

        // PRIMERA FASE: calcular elevaciones
        for (int y = 0; y < resolution; y++)
        {
            for (int x = 0; x < resolution; x++)
            {
                float u = (float)x / (resolution - 1);
                float v = (float)y / (resolution - 1);

                heights[x, y] = CalculateHeight(u, v);
            }
        }

        // SEGUNDA FASE: generar representacion visual
        int cellSize = Mathf.Max(
            1,
            resolution / gridCells
        );

        for (int y = 0; y < resolution; y++)
        {
            for (int x = 0; x < resolution; x++)
            {
                float h = heights[x, y];

                Color color = GetTerrainColor(h);

                // Curvas topograficas
                if (showContours)
                {
                    float level = h * 12f;

                    if (Mathf.Abs(
                        level - Mathf.Round(level)
                    ) < 0.045f)
                    {
                        color *= 0.75f;
                    }
                }

                // Cuadricula visual
                if (showGrid &&
                    (x % cellSize == 0 ||
                     y % cellSize == 0))
                {
                    color = Color.Lerp(
                        color,
                        Color.black,
                        0.12f
                    );
                }

                terrainTexture.SetPixel(x, y, color);
            }
        }

        terrainTexture.Apply();

        // Crear sprite
        Sprite terrainSprite = Sprite.Create(
            terrainTexture,
            new Rect(0, 0, resolution, resolution),
            new Vector2(0.5f, 0.5f),
            resolution / worldSize
        );

        spriteRenderer.sprite = terrainSprite;
        spriteRenderer.sortingOrder = 0;

        Debug.Log(
            "Terreno generado: " + terrainType
        );
    }

    // =====================================
    // GENERACION DE ELEVACIONES
    // =====================================

    private float CalculateHeight(float x, float y)
    {
        float noise = Mathf.PerlinNoise(
            x * 4f + 10f,
            y * 4f + 10f
        );

        float height = 0.3f;

        switch (terrainType)
        {
            case TerrainType.Plano:

                height = 0.38f +
                    (noise - 0.5f) * 0.08f;

                break;

            case TerrainType.Colinas:

                height = 0.22f
                    + 0.38f * Hill(
                        x, y, 0.30f, 0.35f, 0.14f
                    )
                    + 0.35f * Hill(
                        x, y, 0.72f, 0.65f, 0.18f
                    )
                    + (noise - 0.5f) * 0.12f;

                break;

            case TerrainType.Montanoso:

                height = 0.12f
                    + 0.62f * Hill(
                        x, y, 0.28f, 0.68f, 0.16f
                    )
                    + 0.72f * Hill(
                        x, y, 0.72f, 0.30f, 0.13f
                    )
                    + 0.25f * Hill(
                        x, y, 0.53f, 0.52f, 0.10f
                    )
                    + (noise - 0.5f) * 0.10f;

                break;
        }

        return Mathf.Clamp01(height);
    }

    // Crear monticulos
    private float Hill(
        float x,
        float y,
        float centerX,
        float centerY,
        float radius)
    {
        float dx = x - centerX;
        float dy = y - centerY;

        float distance = dx * dx + dy * dy;

        return Mathf.Exp(
            -distance / (2f * radius * radius)
        );
    }

    // =====================================
    // COLORES SEGUN ELEVACION
    // =====================================

    private Color GetTerrainColor(float h)
    {
        if (h < 0.30f)
        {
            return Color.Lerp(
                new Color(0.12f, 0.30f, 0.12f),
                new Color(0.20f, 0.65f, 0.20f),
                h / 0.30f
            );
        }

        if (h < 0.60f)
        {
            return Color.Lerp(
                new Color(0.20f, 0.65f, 0.20f),
                Color.yellow,
                (h - 0.30f) / 0.30f
            );
        }

        if (h < 0.80f)
        {
            return Color.Lerp(
                Color.yellow,
                new Color(1f, 0.45f, 0f),
                (h - 0.60f) / 0.20f
            );
        }

        return Color.Lerp(
            new Color(1f, 0.45f, 0f),
            new Color(0.65f, 0.10f, 0.08f),
            (h - 0.80f) / 0.20f
        );
    }

    // =====================================
    // CONSULTAR ALTURA
    // =====================================

    public float GetHeight(float x, float y)
    {
        if (heights == null)
            return 0f;

        int px = Mathf.Clamp(
            Mathf.RoundToInt(x * (resolution - 1)),
            0,
            resolution - 1
        );

        int py = Mathf.Clamp(
            Mathf.RoundToInt(y * (resolution - 1)),
            0,
            resolution - 1
        );

        return heights[px, py] * heightScale;
    }

    // =====================================
    // CONSULTAR PENDIENTE EN GRADOS
    // =====================================

    public float GetSlope(float x, float y)
    {
        if (heights == null)
            return 0f;

        float step = 1f / (resolution - 1);

        float left = GetHeight(x - step, y);
        float right = GetHeight(x + step, y);

        float down = GetHeight(x, y - step);
        float up = GetHeight(x, y + step);

        float distance = 2f * step * worldSize;

        float dx = (right - left) / distance;
        float dy = (up - down) / distance;

        float gradient = Mathf.Sqrt(
            dx * dx + dy * dy
        );

        return Mathf.Atan(gradient) * Mathf.Rad2Deg;
    }

    // =====================================
    // CONSULTAR DATOS DESDE UNITY
    // =====================================

    public bool GetTerrainData(
        Vector2 worldPosition,
        out float elevation,
        out float slopeDegrees)
    {
        Vector2 local =
            worldPosition - (Vector2)transform.position;

        float x = local.x / worldSize + 0.5f;
        float y = local.y / worldSize + 0.5f;

        if (x < 0 || x > 1 || y < 0 || y > 1)
        {
            elevation = 0f;
            slopeDegrees = 0f;

            return false;
        }

        elevation = GetHeight(x, y);
        slopeDegrees = GetSlope(x, y);

        return true;
    }
}
