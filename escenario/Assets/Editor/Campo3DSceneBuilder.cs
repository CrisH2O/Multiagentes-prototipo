using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.ProBuilder;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

/// <summary>
/// Construye la escena 3D "Campo3D" desde cero, SIN tocar la escena 2D.
///
/// Piezas que crea:
///   - Un renderer 3D (UniversalRenderer) adicional en el pipeline URP.
///     La escena 2D sigue usando el Renderer2D por defecto; la camara 3D
///     apunta explicitamente al renderer nuevo, asi ambas escenas conviven.
///   - Un Terrain de Unity construido a partir del heightmap PNG que genera
///     herramientas/generar_assets_3d.py con la MISMA elevacion del modelo.
///   - Materiales URP Lit y TerrainLayers con texturas de pasto y tierra.
///   - Una bodega modelada con ProBuilder en el deposito.
///   - El tractor importado desde Assets/Modelos/Tractor.obj (malla importada),
///     guardado como prefab.
///   - Arboles y rocas como prefabs sobre el terreno.
///   - Camara en perspectiva con OrbitCamera y luz direccional con sombras.
///
/// Se puede ejecutar desde el menu:
///   Herramientas > Campo 3D > Crear escena Campo3D
/// o en batchmode:
///   Unity -batchmode -quit -projectPath escenario -executeMethod Campo3DSceneBuilder.CrearEscena
/// </summary>
public static class Campo3DSceneBuilder
{
    // ---------------------------------------------------------------------
    // Rutas
    // ---------------------------------------------------------------------
    private const string RutaEscena = "Assets/Scenes/Campo3D.unity";
    private const string RutaRenderer = "Assets/Settings/Renderer3D.asset";
    private const string RutaPipeline = "Assets/Settings/UniversalRP.asset";
    private const string RutaPostProceso =
        "Packages/com.unity.render-pipelines.universal/Runtime/Data/PostProcessData.asset";
    private const string RutaPaqueteUrp =
        "Packages/com.unity.render-pipelines.universal";

    private const string RutaHeightmap = "Assets/Texturas/heightmap_colinas.png";
    private const string RutaTexturaCesped = "Assets/Texturas/cesped.png";
    private const string RutaTexturaTierra = "Assets/Texturas/tierra.png";
    private const string RutaModeloTractor =
        "Assets/Modelos/JohnDeereR8/tractor_r8.obj";
    private const string RutaMtlTractor =
        "Assets/Modelos/JohnDeereR8/tractor_r8.mtl";

    private const string RutaDatosTerreno = "Assets/Terreno/TerrenoColinas.asset";
    private const string RutaCapaCesped = "Assets/Terreno/CapaCesped.terrainlayer";
    private const string RutaCapaTierra = "Assets/Terreno/CapaTierra.terrainlayer";
    private const string RutaCapaSembrado = "Assets/Terreno/CapaSembrado.terrainlayer";

    // ---------------------------------------------------------------------
    // Terreno
    // ---------------------------------------------------------------------
    private const float TamanoTerreno = 1000f;
    private const float AlturaTerreno = 8f;
    private static readonly Vector2 Deposito = new Vector2(-470f, -470f);

    // ---------------------------------------------------------------------
    // Materiales compartidos
    // ---------------------------------------------------------------------
    private static Material cesped;
    private static Material tierra;
    private static Material corteza;
    private static Material hoja;
    private static Material roca;
    private static Material verdeJohnDeere;
    private static Material amarilloRuedas;
    private static Material vidrioCabina;
    private static Material grisDetalle;
    private static Material paredBodega;
    private static Material techoBodega;
    private static Material cespedBase;
    private static Material celdaSembrada;
    private static Material sembrado;

    private static Terrain terreno;

    // =====================================================================
    // PUNTO DE ENTRADA
    // =====================================================================

    [MenuItem("Herramientas/Campo 3D/Crear escena Campo3D")]
    public static void CrearEscena()
    {
        CrearCarpetas();
        ConfigurarImportaciones();

        int indiceRenderer = AsegurarRenderer3D();
        CrearMateriales();

        Scene escena = EditorSceneManager.NewScene(
            NewSceneSetup.EmptyScene,
            NewSceneMode.Single
        );

        Transform escenario = new GameObject("ESCENARIO").transform;
        Transform objetos = new GameObject("OBJETOS").transform;
        Transform iluminacion = new GameObject("ILUMINACION").transform;
        Transform camaras = new GameObject("CAMARAS").transform;

        terreno = CrearTerreno(escenario);

        if (terreno == null)
        {
            Debug.LogError(
                "[Campo3D] Falta el heightmap. Corre antes: " +
                "python herramientas/generar_assets_3d.py"
            );
            return;
        }

        CrearCampoBase(escenario);
        CrearBodega(escenario);

        GameObject prefabArbol = CrearPrefabArbol(objetos);
        GameObject prefabRoca = CrearPrefabRoca(objetos);
        GameObject prefabTractor = CrearPrefabTractor(objetos);
        GameObject prefabCelda = CrearPrefabCelda(objetos);

        InstanciarSobreTerreno(
            prefabArbol, objetos, -180f, 140f, 25f, "Arbol_01", 3f
        );
        InstanciarSobreTerreno(
            prefabArbol, objetos, 210f, -120f, 130f, "Arbol_02", 3f
        );
        InstanciarSobreTerreno(
            prefabArbol, objetos, -60f, 330f, 65f, "Arbol_03", 3f
        );
        InstanciarSobreTerreno(
            prefabRoca, objetos, 120f, 190f, 40f, "Roca_01", 3f
        );
        InstanciarSobreTerreno(
            prefabRoca, objetos, -240f, -180f, 210f, "Roca_02", 3f
        );

        if (prefabTractor != null)
        {
            InstanciarSobreTerreno(
                prefabTractor, objetos, -430f, -380f, 0f, "Tractor_01"
            );
            InstanciarSobreTerreno(
                prefabTractor, objetos, -400f, -430f, 0f, "Tractor_02"
            );
            InstanciarSobreTerreno(
                prefabTractor, objetos, -360f, -470f, 0f, "Tractor_03"
            );
        }

        CrearSol(iluminacion);

        CrearCamara(camaras, indiceRenderer);

        ConfigurarAmbiente();
        CrearPostProceso();
        CrearSimulacion(
            escenario, objetos, terreno, prefabTractor, prefabCelda
        );

        EditorSceneManager.MarkSceneDirty(escena);
        EditorSceneManager.SaveScene(escena, RutaEscena);

        AgregarAEscenasDeBuild();

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        Debug.Log(
            "[Campo3D] Escena creada en " + RutaEscena +
            " | renderer 3D indice " + indiceRenderer +
            " | altura del terreno " + AlturaTerreno + " m" +
            ". La escena SampleScene (2D) quedo intacta."
        );
    }

    // =====================================================================
    // IMPORTACION DE ASSETS
    // =====================================================================

    private static void ConfigurarImportaciones()
    {
        // Heightmap: es DATO, no color. Sin compresion para no deformar alturas.
        ConfigurarTextura(RutaHeightmap, sRGB: false, repetir: false, legible: true,
            sinCompresion: true);

        ConfigurarTextura(RutaTexturaCesped, sRGB: true, repetir: true, legible: false,
            sinCompresion: false);
        ConfigurarTextura(RutaTexturaTierra, sRGB: true, repetir: true, legible: false,
            sinCompresion: false);
        ConfigurarTextura("Assets/Texturas/sembrado.png", sRGB: true, repetir: true,
            legible: false, sinCompresion: false);
    }

    private static void ConfigurarTextura(
        string ruta, bool sRGB, bool repetir, bool legible, bool sinCompresion
    )
    {
        var importador = AssetImporter.GetAtPath(ruta) as TextureImporter;

        if (importador == null)
        {
            Debug.LogWarning("[Campo3D] No se pudo importar " + ruta);
            return;
        }

        bool cambio = false;

        if (importador.sRGBTexture != sRGB)
        {
            importador.sRGBTexture = sRGB;
            cambio = true;
        }

        if (importador.isReadable != legible)
        {
            importador.isReadable = legible;
            cambio = true;
        }

        var ajuste = repetir ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;

        if (importador.wrapMode != ajuste)
        {
            importador.wrapMode = ajuste;
            cambio = true;
        }

        if (importador.npotScale != TextureImporterNPOTScale.None)
        {
            importador.npotScale = TextureImporterNPOTScale.None;
            cambio = true;
        }

        var compresion = sinCompresion
            ? TextureImporterCompression.Uncompressed
            : TextureImporterCompression.Compressed;

        if (importador.textureCompression != compresion)
        {
            importador.textureCompression = compresion;
            cambio = true;
        }

        if (cambio)
        {
            importador.SaveAndReimport();
        }
    }

    // =====================================================================
    // RENDERER 3D
    // =====================================================================

    /// <summary>
    /// Crea (si hace falta) un UniversalRendererData y lo agrega a la lista
    /// del pipeline URP. Devuelve su indice para asignarselo a la camara 3D.
    /// El renderer por defecto sigue siendo el 2D, por lo que la escena 2D
    /// no cambia absolutamente nada.
    /// </summary>
    private static int AsegurarRenderer3D()
    {
        var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(
            RutaPipeline
        );

        if (pipeline == null)
        {
            throw new FileNotFoundException(
                "No se encontro el Render Pipeline Asset en " + RutaPipeline
            );
        }

        var renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(
            RutaRenderer
        );

        if (renderer == null)
        {
            renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
            renderer.postProcessData =
                AssetDatabase.LoadAssetAtPath<PostProcessData>(RutaPostProceso);

            AssetDatabase.CreateAsset(renderer, RutaRenderer);

            // Carga las referencias internas (shaders) que el renderer necesita.
            ResourceReloader.ReloadAllNullIn(renderer, RutaPaqueteUrp);
            EditorUtility.SetDirty(renderer);
        }

        var serializado = new SerializedObject(pipeline);
        SerializedProperty lista = serializado.FindProperty("m_RendererDataList");
        SerializedProperty distanciaSombra = serializado.FindProperty("m_ShadowDistance");

        if (distanciaSombra != null && distanciaSombra.floatValue < 600f)
        {
            distanciaSombra.floatValue = 600f;
            serializado.ApplyModifiedPropertiesWithoutUndo();
        }

        int indice = -1;

        for (int i = 0; i < lista.arraySize; i++)
        {
            if (lista.GetArrayElementAtIndex(i).objectReferenceValue == renderer)
            {
                indice = i;
                break;
            }
        }

        if (indice < 0)
        {
            indice = lista.arraySize;
            lista.arraySize += 1;
            lista.GetArrayElementAtIndex(indice).objectReferenceValue = renderer;

            serializado.ApplyModifiedPropertiesWithoutUndo();
            AssetDatabase.SaveAssets();
        }

        return indice;
    }

    // =====================================================================
    // MATERIALES
    // =====================================================================

    private static void CrearMateriales()
    {
        cesped = CrearMaterial("Cesped", new Color(0.34f, 0.47f, 0.21f), 0.05f);
        tierra = CrearMaterial("Tierra", new Color(0.38f, 0.27f, 0.17f), 0.08f);
        corteza = CrearMaterial("Corteza", new Color(0.29f, 0.20f, 0.13f), 0.05f);
        hoja = CrearMaterial("Hoja", new Color(0.22f, 0.43f, 0.18f), 0.12f);
        roca = CrearMaterial("Roca", new Color(0.44f, 0.45f, 0.47f), 0.10f);

        verdeJohnDeere = CrearMaterial(
            "VerdeJohnDeere", new Color(0.13f, 0.36f, 0.16f), 0.35f, 0.15f
        );
        amarilloRuedas = CrearMaterial(
            "AmarilloRuedas", new Color(1.00f, 0.84f, 0.05f), 0.30f, 0.10f
        );
        vidrioCabina = CrearMaterial(
            "VidrioCabina", new Color(0.06f, 0.09f, 0.10f), 0.85f, 0.30f
        );
        grisDetalle = CrearMaterial(
            "GrisDetalle", new Color(0.20f, 0.21f, 0.22f), 0.45f, 0.60f
        );
        paredBodega = CrearMaterial(
            "ParedBodega", new Color(0.72f, 0.71f, 0.66f), 0.15f
        );
        techoBodega = CrearMaterial(
            "TechoBodega", new Color(0.28f, 0.30f, 0.32f), 0.35f, 0.30f
        );

        cespedBase = CrearMaterialTexturizado(
            "CespedBase", RutaTexturaCesped, new Vector2(60f, 60f)
        );

        celdaSembrada = CrearMaterialCelda();

        sembrado = CrearMaterialTexturizado(
            "Sembrado", "Assets/Texturas/sembrado.png", new Vector2(1f, 1f)
        );
    }

    private static Material CrearMaterial(
        string nombre, Color color, float suavidad, float metalico = 0f
    )
    {
        string ruta = "Assets/Materials/" + nombre + ".mat";
        var existente = AssetDatabase.LoadAssetAtPath<Material>(ruta);

        if (existente != null)
        {
            return existente;
        }

        var shader = Shader.Find("Universal Render Pipeline/Lit");

        if (shader == null)
        {
            throw new FileNotFoundException(
                "No se encontro el shader URP/Lit. Revisa el pipeline."
            );
        }

        var material = new Material(shader) { name = nombre };
        material.SetColor("_BaseColor", color);
        material.SetFloat("_Smoothness", suavidad);
        material.SetFloat("_Metallic", metalico);
        material.enableInstancing = true;

        AssetDatabase.CreateAsset(material, ruta);
        return material;
    }

    /// <summary>
    /// Material de las celdas sembradas: usa el shader propio
    /// Campo3D/CeldaSembrada (disco con pulso aditivo).
    /// </summary>
    private static Material CrearMaterialCelda()
    {
        const string ruta = "Assets/Materials/CeldaSembrada.mat";
        var existente = AssetDatabase.LoadAssetAtPath<Material>(ruta);

        if (existente != null && existente.shader != null &&
            existente.shader.name == "Campo3D/CeldaSembrada")
        {
            return existente;
        }

        if (existente != null)
        {
            AssetDatabase.DeleteAsset(ruta);
        }

        var shader = Shader.Find("Campo3D/CeldaSembrada");

        if (shader == null)
        {
            Debug.LogWarning(
                "[Campo3D] No se encontro Campo3D/CeldaSembrada; se usa Unlit."
            );

            return CrearMaterialUnlit(
                "CeldaSembradaRespaldo", new Color(0.35f, 1f, 0.45f)
            );
        }

        var material = new Material(shader) { name = "CeldaSembrada" };
        material.SetColor("_Color", new Color(0.35f, 1.00f, 0.45f));
        material.SetFloat("_Brillo", 1.9f);
        material.SetFloat("_Pulso", 2.2f);
        material.SetFloat("_Borde", 0.20f);

        AssetDatabase.CreateAsset(material, ruta);
        return material;
    }

    private static Material CrearMaterialUnlit(string nombre, Color color)
    {
        string ruta = "Assets/Materials/" + nombre + ".mat";
        var existente = AssetDatabase.LoadAssetAtPath<Material>(ruta);

        if (existente != null)
        {
            return existente;
        }

        var shader = Shader.Find("Universal Render Pipeline/Unlit");

        var material = new Material(shader) { name = nombre };
        material.SetColor("_BaseColor", color);
        material.SetColor("_Color", color);

        AssetDatabase.CreateAsset(material, ruta);
        return material;
    }

    private static Material CrearMaterialTexturizado(
        string nombre, string rutaTextura, Vector2 tiling
    )
    {
        string ruta = "Assets/Materials/" + nombre + ".mat";
        var existente = AssetDatabase.LoadAssetAtPath<Material>(ruta);

        if (existente != null)
        {
            return existente;
        }

        var shader = Shader.Find("Universal Render Pipeline/Lit");
        var textura = AssetDatabase.LoadAssetAtPath<Texture2D>(rutaTextura);

        var material = new Material(shader) { name = nombre };
        material.SetTexture("_BaseMap", textura);
        material.SetTextureScale("_BaseMap", tiling);
        material.SetColor("_BaseColor", new Color(0.95f, 0.95f, 0.95f));
        material.SetFloat("_Smoothness", 0.05f);

        AssetDatabase.CreateAsset(material, ruta);
        return material;
    }

    // =====================================================================
    // TERRENO
    // =====================================================================

    /// <summary>
    /// Construye un Terrain de Unity leyendo el PNG de alturas como un
    /// heightmap. El PNG lo genera el script de Python con la misma
    /// elevacion que usa el modelo multiagente.
    /// </summary>
    private static Terrain CrearTerreno(Transform padre)
    {
        var textura = AssetDatabase.LoadAssetAtPath<Texture2D>(RutaHeightmap);

        if (textura == null)
        {
            Debug.LogError("[Campo3D] No existe " + RutaHeightmap);
            return null;
        }

        int resolucion = textura.width;

        if (resolucion != textura.height)
        {
            Debug.LogError("[Campo3D] El heightmap debe ser cuadrado.");
            return null;
        }

        var pixeles = textura.GetPixels();
        var alturas = new float[resolucion, resolucion];

        // El PNG se guarda volteado: la fila 0 es z = -10.
        for (int z = 0; z < resolucion; z++)
        {
            for (int x = 0; x < resolucion; x++)
            {
                alturas[z, x] = pixeles[z * resolucion + x].grayscale;
            }
        }

        var datos = new TerrainData();
        datos.heightmapResolution = resolucion;
        datos.size = new Vector3(TamanoTerreno, AlturaTerreno, TamanoTerreno);

        // El TerrainData debe ser un asset ANTES de asignar capas, si no
        // Unity pierde los mapas alfa (la capa de tierra no se veria).
        CrearCarpeta("Assets", "Terreno");
        AssetDatabase.CreateAsset(datos, RutaDatosTerreno);

        datos.SetHeights(0, 0, alturas);

        datos.terrainLayers = new[]
        {
            CrearCapaCesped(),
            CrearCapaTierra(),
            CrearCapaSembrado()
        };

        datos.alphamapResolution = 512;
        datos.SetAlphamaps(0, 0, CrearAlphamap(datos));

        EditorUtility.SetDirty(datos);
        AssetDatabase.SaveAssets();

        var terrenoGO = Terrain.CreateTerrainGameObject(datos);
        terrenoGO.name = "Terreno";
        terrenoGO.transform.SetParent(padre, false);

        // El Terrain se ancla en su esquina: se centra en el origen para que
        // las celdas (0,0)..(n,n) queden alrededor del centro del campo.
        terrenoGO.transform.localPosition = new Vector3(
            -TamanoTerreno / 2f, 0f, -TamanoTerreno / 2f
        );

        var componente = terrenoGO.GetComponent<Terrain>();
        componente.materialTemplate = CrearMaterialTerreno();

        return componente;
    }

    private static TerrainLayer CrearCapaCesped()
    {
        var capa = AssetDatabase.LoadAssetAtPath<TerrainLayer>(RutaCapaCesped);

        if (capa != null)
        {
            return capa;
        }

        capa = new TerrainLayer
        {
            name = "CapaCesped",
            diffuseTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(RutaTexturaCesped),
            tileSize = new Vector2(4f, 4f),
            smoothness = 0.05f
        };

        AssetDatabase.CreateAsset(capa, RutaCapaCesped);
        return capa;
    }

    private static TerrainLayer CrearCapaTierra()
    {
        var capa = AssetDatabase.LoadAssetAtPath<TerrainLayer>(RutaCapaTierra);

        if (capa != null)
        {
            return capa;
        }

        capa = new TerrainLayer
        {
            name = "CapaTierra",
            diffuseTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(RutaTexturaTierra),
            tileSize = new Vector2(3f, 3f),
            smoothness = 0.1f
        };

        AssetDatabase.CreateAsset(capa, RutaCapaTierra);
        return capa;
    }

    private static TerrainLayer CrearCapaSembrado()
    {
        var capa = AssetDatabase.LoadAssetAtPath<TerrainLayer>(RutaCapaSembrado);

        if (capa != null)
        {
            return capa;
        }

        capa = new TerrainLayer
        {
            name = "CapaSembrado",
            diffuseTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(
                "Assets/Texturas/sembrado.png"
            ),
            // La textura cubre 25 m: una celda = una repeticion
            tileSize = new Vector2(25f, 25f),
            smoothness = 0.05f
        };

        AssetDatabase.CreateAsset(capa, RutaCapaSembrado);
        return capa;
    }

    private static Material CrearMaterialTerreno()
    {
        const string ruta = "Assets/Materials/Terreno.mat";
        var material = AssetDatabase.LoadAssetAtPath<Material>(ruta);

        if (material != null)
        {
            return material;
        }

        var shader = Shader.Find("Universal Render Pipeline/Terrain/Lit");

        if (shader == null)
        {
            return null;
        }

        material = new Material(shader) { name = "Terreno" };
        AssetDatabase.CreateAsset(material, ruta);
        return material;
    }

    /// <summary>
    /// Capa de tierra alrededor del deposito (bodega y tractores), mezclada
    /// con pasto hacia afuera. Canal 0 = pasto, canal 1 = tierra.
    /// </summary>
    private static float[,,] CrearAlphamap(TerrainData datos)
    {
        int resolucion = datos.alphamapResolution;
        var alfa = new float[resolucion, resolucion, 3];

        for (int z = 0; z < resolucion; z++)
        {
            float mundoZ =
                (z / (float)(resolucion - 1)) * TamanoTerreno - TamanoTerreno / 2f;

            for (int x = 0; x < resolucion; x++)
            {
                float mundoX =
                    (x / (float)(resolucion - 1)) * TamanoTerreno - TamanoTerreno / 2f;

                float distancia = Vector2.Distance(
                    new Vector2(mundoX, mundoZ), Deposito
                );

                float mezcla = Mathf.Clamp01(
                    Mathf.InverseLerp(55f, 35f, distancia)
                );

                alfa[z, x, 0] = 1f - mezcla;   // pasto
                alfa[z, x, 1] = mezcla;        // tierra del deposito
                alfa[z, x, 2] = 0f;            // sembrado (lo pinta el simulador)
            }
        }

        return alfa;
    }

    private static float AlturaEn(float x, float z)
    {
        if (terreno == null)
        {
            return 0f;
        }

        return terreno.SampleHeight(new Vector3(x, 0f, z)) +
               terreno.transform.position.y;
    }

    // =====================================================================
    // ESCENARIO
    // =====================================================================

    /// <summary>
    /// Plano grande de pasto alrededor del terreno, para que el campo no
    /// parezca una isla flotante. Queda a la altura del borde del heightmap.
    /// </summary>
    private static void CrearCampoBase(Transform padre)
    {
        var plano = GameObject.CreatePrimitive(PrimitiveType.Plane);
        plano.name = "CampoBase";
        plano.transform.SetParent(padre, false);
        plano.transform.localPosition =
            new Vector3(0f, 0.12f * AlturaTerreno - 0.01f, 0f);
        plano.transform.localScale = new Vector3(800f, 1f, 800f);
        plano.GetComponent<MeshRenderer>().sharedMaterial = cespedBase;

        // El terreno ya tiene su propio collider: el plano no debe estorbar.
        UnityEngine.Object.DestroyImmediate(plano.GetComponent<Collider>());
    }

    /// <summary>
    /// Bodega del deposito modelada con ProBuilder: dos cajas (cuerpo y techo)
    /// cuyos vertices se deforman al tamano final.
    /// </summary>
    private static void CrearBodega(Transform padre)
    {
        float altura = AlturaEn(Deposito.x, Deposito.y);
        var centro = new Vector3(Deposito.x, altura, Deposito.y);

        var cuerpo = ShapeGenerator.CreateShape(ShapeType.Cube);
        cuerpo.name = "Bodega";
        cuerpo.transform.SetParent(padre, false);
        cuerpo.transform.position = centro + Vector3.up * 6f;

        DeformarCaja(cuerpo.GetComponent<ProBuilderMesh>(), new Vector3(40f, 12f, 25f));
        cuerpo.GetComponent<MeshRenderer>().sharedMaterial = paredBodega;

        var techo = ShapeGenerator.CreateShape(ShapeType.Cube);
        techo.name = "TechoBodega";
        techo.transform.SetParent(padre, false);
        techo.transform.position = centro + Vector3.up * 12.4f;

        DeformarCaja(techo.GetComponent<ProBuilderMesh>(), new Vector3(44f, 1f, 29f));
        techo.GetComponent<MeshRenderer>().sharedMaterial = techoBodega;
    }

    /// <summary>
    /// Lleva una caja de ProBuilder (1x1x1) al tamano pedido deformando sus
    /// vertices, sin usar la escala del Transform.
    /// </summary>
    private static void DeformarCaja(ProBuilderMesh malla, Vector3 tamano)
    {
        IList<Vector3> originales = malla.positions;
        var posiciones = new Vector3[originales.Count];

        for (int i = 0; i < originales.Count; i++)
        {
            posiciones[i] = new Vector3(
                originales[i].x * tamano.x,
                originales[i].y * tamano.y,
                originales[i].z * tamano.z
            );
        }

        malla.positions = posiciones;
        malla.ToMesh();
        malla.Refresh();
    }

    private static GameObject CrearPrefabArbol(Transform padre)
    {
        var raiz = new GameObject("Arbol");
        raiz.transform.SetParent(padre, false);

        Primitiva(
            PrimitiveType.Cylinder, "Tronco", raiz.transform,
            new Vector3(0f, 1.05f, 0f),
            new Vector3(0.26f, 1.05f, 0.26f),
            corteza
        );
        Primitiva(
            PrimitiveType.Sphere, "Copa_A", raiz.transform,
            new Vector3(0f, 2.5f, 0f),
            new Vector3(1.75f, 1.55f, 1.75f),
            hoja
        );
        Primitiva(
            PrimitiveType.Sphere, "Copa_B", raiz.transform,
            new Vector3(0.45f, 2.0f, 0.3f),
            new Vector3(1.15f, 1.0f, 1.15f),
            hoja
        );

        return GuardarPrefab(raiz, "Assets/Prefabs/Arbol.prefab");
    }

    private static GameObject CrearPrefabRoca(Transform padre)
    {
        var raiz = new GameObject("Roca");
        raiz.transform.SetParent(padre, false);

        Primitiva(
            PrimitiveType.Sphere, "Cuerpo", raiz.transform,
            new Vector3(0f, 0.35f, 0f),
            new Vector3(1.1f, 0.75f, 0.95f),
            roca
        );
        Primitiva(
            PrimitiveType.Sphere, "Pico", raiz.transform,
            new Vector3(0.42f, 0.55f, 0.2f),
            new Vector3(0.5f, 0.45f, 0.5f),
            roca
        );

        return GuardarPrefab(raiz, "Assets/Prefabs/Roca.prefab");
    }

    /// <summary>
    /// Toma la malla importada del tractor (John Deere R8, extraido de la
    /// escena de Sketchfab), le asigna materiales URP con sus texturas y la
    /// guarda como prefab con el pivote en el suelo y mirando a +Z.
    /// </summary>
    private static GameObject CrearPrefabTractor(Transform padre)
    {
        var modelo = AssetDatabase.LoadAssetAtPath<GameObject>(RutaModeloTractor);

        if (modelo == null)
        {
            Debug.LogWarning(
                "[Campo3D] No existe " + RutaModeloTractor +
                ". Corre herramientas/glb_a_obj.py"
            );
            return null;
        }

        var mapaTexturas = LeerTexturasMtl(RutaMtlTractor);

        CrearCarpeta("Assets/Materials", "Tractor");

        var instancia = (GameObject)PrefabUtility.InstantiatePrefab(modelo, padre);
        instancia.name = "Modelo";
        instancia.transform.localRotation = Quaternion.Euler(0f, -90f, 0f);

        foreach (var renderer in instancia.GetComponentsInChildren<MeshRenderer>())
        {
            var materiales = renderer.sharedMaterials;

            for (int i = 0; i < materiales.Length; i++)
            {
                var original = materiales[i];
                string nombre = original != null ? original.name : "tractor";
                string rutaMaterial = "Assets/Materials/Tractor/" +
                    SanearNombre(nombre) + ".mat";

                Color color = original != null ? original.color : Color.gray;
                color = TinteJohnDeere(color);

                string textura = BuscarTextura(mapaTexturas, nombre);
                var imagen = string.IsNullOrEmpty(textura)
                    ? null
                    : AssetDatabase.LoadAssetAtPath<Texture2D>(textura);

                var yaExiste = AssetDatabase.LoadAssetAtPath<Material>(rutaMaterial);

                if (yaExiste != null)
                {
                    yaExiste.SetColor("_BaseColor",
                        imagen != null ? Color.white : color);

                    if (imagen != null)
                    {
                        yaExiste.SetTexture("_BaseMap", imagen);
                    }

                    EditorUtility.SetDirty(yaExiste);
                    materiales[i] = yaExiste;
                    continue;
                }

                var urp = new Material(
                    Shader.Find("Universal Render Pipeline/Lit")
                );

                urp.name = nombre;
                urp.SetFloat("_Smoothness", 0.35f);
                urp.SetFloat("_Metallic", 0.1f);
                urp.SetColor("_BaseColor", color);

                if (imagen != null)
                {
                    urp.SetTexture("_BaseMap", imagen);
                    urp.SetColor("_BaseColor", Color.white);
                }

                AssetDatabase.CreateAsset(urp, rutaMaterial);
                materiales[i] = urp;
            }

            renderer.sharedMaterials = materiales;
        }

        // Centrar en XZ y apoyar las ruedas en y = 0
        Bounds caja = CalcularBounds(instancia);
        instancia.transform.localPosition -= new Vector3(
            caja.center.x, caja.min.y, caja.center.z
        );

        var raiz = new GameObject("Tractor");
        raiz.transform.SetParent(padre, false);
        instancia.transform.SetParent(raiz.transform, true);

        var colisionador = raiz.AddComponent<BoxCollider>();
        colisionador.center = new Vector3(0f, 2.1f, 0f);
        colisionador.size = new Vector3(3.6f, 4.2f, 7.4f);

        return GuardarPrefab(raiz, "Assets/Prefabs/Tractor.prefab");
    }

    /// <summary>
    /// El modelo de Sketchfab trae los paneles en gris. Los grises medios se
    /// pintan con el verde de John Deere; las ruedas amarillas, el vidrio
    /// azul y las llantas oscuras se respetan.
    /// </summary>
    private static Color TinteJohnDeere(Color original)
    {
        float r = original.r;
        float g = original.g;
        float b = original.b;

        bool gris = Mathf.Abs(r - g) < 0.06f && Mathf.Abs(g - b) < 0.06f;
        float luminancia = (r + g + b) / 3f;

        if (gris && luminancia > 0.09f && luminancia < 0.97f)
        {
            return new Color(0.09f, 0.33f, 0.13f);
        }

        return original;
    }

    private static string SanearNombre(string nombre)
    {
        foreach (char caracter in Path.GetInvalidFileNameChars())
        {
            nombre = nombre.Replace(caracter, '_');
        }

        return string.IsNullOrEmpty(nombre) ? "material" : nombre;
    }

    private static Bounds CalcularBounds(GameObject objeto)
    {
        var renderers = objeto.GetComponentsInChildren<MeshRenderer>();
        var bounds = new Bounds(objeto.transform.position, Vector3.zero);

        foreach (var renderer in renderers)
        {
            bounds.Encapsulate(renderer.bounds);
        }

        return bounds;
    }

    private static Dictionary<string, string> LeerTexturasMtl(string rutaMtl)
    {
        var mapa = new Dictionary<string, string>();

        if (!File.Exists(rutaMtl))
        {
            return mapa;
        }

        string actual = null;

        foreach (string linea in File.ReadAllLines(rutaMtl))
        {
            string limpia = linea.Trim();

            if (limpia.StartsWith("newmtl "))
            {
                actual = limpia.Substring(7).Trim();
            }
            else if (limpia.StartsWith("map_Kd ") && actual != null)
            {
                string archivo = limpia.Substring(7).Trim();
                string carpeta = Path.GetDirectoryName(rutaMtl) ?? string.Empty;
                mapa[actual] = (carpeta + "/" + archivo).Replace("\\", "/");
            }
        }

        return mapa;
    }

    private static string BuscarTextura(
        Dictionary<string, string> mapa, string nombreMaterial
    )
    {
        if (mapa.Count == 0 || string.IsNullOrEmpty(nombreMaterial))
        {
            return null;
        }

        if (mapa.TryGetValue(nombreMaterial, out string exacta))
        {
            return exacta;
        }

        foreach (var par in mapa)
        {
            if (nombreMaterial.Contains(par.Key))
            {
                return par.Value;
            }
        }

        return null;
    }

    /// <summary>
    /// Marcador de celda sembrada (se conserva como prefab de referencia).
    /// </summary>
    private static GameObject CrearPrefabCelda(Transform padre)
    {
        var celda = GameObject.CreatePrimitive(PrimitiveType.Plane);
        celda.name = "CeldaSembrada";
        celda.transform.SetParent(padre, false);

        // Un Plane mide 10x10: con escala 2.5 queda una celda de 25x25 m.
        celda.transform.localScale = new Vector3(2.5f, 1f, 2.5f);

        UnityEngine.Object.DestroyImmediate(celda.GetComponent<Collider>());

        var renderer = celda.GetComponent<MeshRenderer>();

        if (renderer != null)
        {
            renderer.sharedMaterial = sembrado;
        }

        return GuardarPrefab(celda, "Assets/Prefabs/CeldaSembrada.prefab");
    }

    /// <summary>
    /// Objeto con el componente que se conecta al servidor Python y
    /// reproduce la simulacion sobre el terreno.
    /// </summary>
    private static void CrearSimulacion(
        Transform escenario,
        Transform objetos,
        Terrain terreno,
        GameObject prefabTractor,
        GameObject prefabCelda
    )
    {
        var contenedorCeldas = new GameObject("CeldasSembradas");
        contenedorCeldas.transform.SetParent(escenario, false);

        var go = new GameObject("SIMULACION");
        go.transform.SetParent(escenario, false);

        var simulacion = go.AddComponent<Simulacion3D>();
        simulacion.terreno = terreno;
        simulacion.prefabTractor = prefabTractor;
        simulacion.prefabCelda = prefabCelda;
        simulacion.contenedorTractores = objetos;
        simulacion.contenedorCeldas = contenedorCeldas.transform;
        simulacion.hectareasCampo = 100f;
        simulacion.anchoSembradora = 9.12f;
        simulacion.duracionTick = 0.08f;
        simulacion.iniciarAlComenzar = true;
    }

    /// <summary>
    /// Volumen global de post-proceso: bloom para el brillo, tonemapping ACES,
    /// vineta y un ajuste suave de color.
    /// </summary>
    private static void CrearPostProceso()
    {
        const string ruta = "Assets/Settings/PerfilCampo3D.asset";
        var perfil = AssetDatabase.LoadAssetAtPath<VolumeProfile>(ruta);

        if (perfil == null)
        {
            perfil = ScriptableObject.CreateInstance<VolumeProfile>();
            AssetDatabase.CreateAsset(perfil, ruta);

            var bloom = perfil.Add<Bloom>(true);
            bloom.intensity.Override(0.55f);
            bloom.threshold.Override(0.85f);
            bloom.scatter.Override(0.65f);

            var tonemapping = perfil.Add<Tonemapping>(true);
            tonemapping.mode.Override(TonemappingMode.ACES);

            var vignette = perfil.Add<Vignette>(true);
            vignette.intensity.Override(0.22f);
            vignette.smoothness.Override(0.45f);

            var ajustes = perfil.Add<ColorAdjustments>(true);
            ajustes.postExposure.Override(0.15f);
            ajustes.contrast.Override(10f);
            ajustes.saturation.Override(8f);

            EditorUtility.SetDirty(perfil);
            AssetDatabase.SaveAssets();
        }

        var go = new GameObject("PostProceso");
        var volumen = go.AddComponent<Volume>();
        volumen.isGlobal = true;
        volumen.priority = 1f;
        volumen.sharedProfile = perfil;
    }

    // =====================================================================
    // ILUMINACION Y CAMARA
    // =====================================================================

    private static void CrearSol(Transform padre)
    {
        var sol = new GameObject("Sol");
        sol.transform.SetParent(padre, false);
        sol.transform.rotation = Quaternion.Euler(48f, -32f, 0f);

        var luz = sol.AddComponent<Light>();
        luz.type = LightType.Directional;
        luz.color = new Color(1f, 0.95f, 0.86f);
        luz.intensity = 1.35f;
        luz.shadows = LightShadows.Soft;
        luz.shadowStrength = 0.9f;

        RenderSettings.sun = luz;
    }

    private static Camera CrearCamara(Transform padre, int indiceRenderer)
    {
        var centro = new GameObject("CentroEscena");
        centro.transform.position = new Vector3(0f, 0.6f, 0f);

        var camaraGO = new GameObject("Camara Principal");
        camaraGO.tag = "MainCamera";
        camaraGO.transform.SetParent(padre, false);

        var camara = camaraGO.AddComponent<Camera>();
        camara.fieldOfView = 50f;
        camara.nearClipPlane = 0.1f;
        camara.farClipPlane = 3000f;
        camara.clearFlags = CameraClearFlags.Skybox;

        camaraGO.AddComponent<AudioListener>();

        // La camara 3D usa el renderer 3D; el resto de camaras (escena 2D)
        // siguen usando el renderer 2D por defecto.
        var datosCamara = camara.GetUniversalAdditionalCameraData();
        datosCamara.SetRenderer(indiceRenderer);
        datosCamara.renderPostProcessing = true;

        var orbita = camaraGO.AddComponent<OrbitCamera>();
        camaraGO.AddComponent<CamaraSeguimiento>();
        orbita.objetivo = centro.transform;
        orbita.distancia = 850f;
        orbita.yaw = 215f;
        orbita.pitch = 50f;
        orbita.distanciaMinima = 25f;
        orbita.distanciaMaxima = 1200f;
        orbita.limiteDesplazamiento = 480f;
        orbita.velocidadDesplazamiento = 60f;
        orbita.velocidadZoom = 250f;

        // Dejar el encuadre ya puesto en el editor (sin necesidad de Play).
        Quaternion rotacion = Quaternion.Euler(orbita.pitch, orbita.yaw, 0f);
        camaraGO.transform.SetPositionAndRotation(
            centro.transform.position - rotacion * Vector3.forward * orbita.distancia,
            rotacion
        );

        return camara;
    }

    private static void ConfigurarAmbiente()
    {
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.58f, 0.63f, 0.72f);
        RenderSettings.ambientEquatorColor = new Color(0.40f, 0.42f, 0.36f);
        RenderSettings.ambientGroundColor = new Color(0.20f, 0.18f, 0.15f);
        RenderSettings.ambientIntensity = 1f;

        RenderSettings.fog = true;
        RenderSettings.fogMode = FogMode.ExponentialSquared;
        RenderSettings.fogDensity = 0.00045f;
        RenderSettings.fogColor = new Color(0.74f, 0.80f, 0.84f);

        RenderSettings.skybox = CrearCielo();
    }

    private static Material CrearCielo()
    {
        const string ruta = "Assets/Materials/Cielo.mat";
        var cielo = AssetDatabase.LoadAssetAtPath<Material>(ruta);

        if (cielo != null)
        {
            return cielo;
        }

        var shader = Shader.Find("Campo3D/CieloGradiente");

        if (shader == null)
        {
            Debug.LogWarning(
                "[Campo3D] No se encontro el shader del cielo; se usa el de Unity."
            );

            return AssetDatabase.GetBuiltinExtraResource<Material>(
                "Default-Skybox.mat"
            );
        }

        cielo = new Material(shader) { name = "Cielo" };
        cielo.SetColor("_ColorArriba", new Color(0.16f, 0.32f, 0.60f, 1f));
        cielo.SetColor("_ColorHorizonte", new Color(0.78f, 0.86f, 0.94f, 1f));
        cielo.SetColor("_ColorAbajo", new Color(0.45f, 0.46f, 0.40f, 1f));
        cielo.SetFloat("_Potencia", 1.8f);

        AssetDatabase.CreateAsset(cielo, ruta);
        return cielo;
    }

    // =====================================================================
    // VISTA PREVIA
    // =====================================================================

    /// <summary>
    /// Renderiza un PNG de la escena sin abrir la ventana del editor.
    /// Sirve para revisar el resultado desde fuera de Unity.
    /// </summary>
    [MenuItem("Herramientas/Campo 3D/Renderizar vista previa")]
    public static void RenderizarVistaPrevia()
    {
        EditorSceneManager.OpenScene(RutaEscena, OpenSceneMode.Single);

        var camara = UnityEngine.Object.FindFirstObjectByType<Camera>();

        if (camara == null)
        {
            Debug.LogError("[Campo3D] La escena no tiene camara.");
            return;
        }

        // En batchmode, Camera.Render() con el SRP Batcher activo liga el
        // material del primer objeto a todos los demas. Se apaga solo
        // durante la captura y se restaura al terminar.
        var pipeline = GraphicsSettings.currentRenderPipeline
            as UniversalRenderPipelineAsset;
        bool srpBatcherOriginal = pipeline != null && pipeline.useSRPBatcher;

        if (pipeline != null)
        {
            pipeline.useSRPBatcher = false;
        }

        const int ancho = 1600;
        const int alto = 900;

        var destino = new RenderTexture(ancho, alto, 24, RenderTextureFormat.ARGB32)
        {
            antiAliasing = 4
        };

        camara.targetTexture = destino;
        camara.Render();

        RenderTexture.active = destino;

        var textura = new Texture2D(ancho, alto, TextureFormat.RGB24, false);
        textura.ReadPixels(new Rect(0, 0, ancho, alto), 0, 0);
        textura.Apply();

        RenderTexture.active = null;
        camara.targetTexture = null;

        string carpeta = Path.Combine(Directory.GetCurrentDirectory(), "Previews");
        Directory.CreateDirectory(carpeta);

        string ruta = Path.Combine(carpeta, "Campo3D.png");
        File.WriteAllBytes(ruta, textura.EncodeToPNG());

        UnityEngine.Object.DestroyImmediate(textura);
        UnityEngine.Object.DestroyImmediate(destino);

        if (pipeline != null)
        {
            pipeline.useSRPBatcher = srpBatcherOriginal;
        }

        Debug.Log("[Campo3D] Vista previa guardada en " + ruta);
    }

    // =====================================================================
    // UTILIDADES
    // =====================================================================

    private static GameObject Primitiva(
        PrimitiveType tipo,
        string nombre,
        Transform padre,
        Vector3 posicionLocal,
        Vector3 escalaLocal,
        Material material
    )
    {
        var go = GameObject.CreatePrimitive(tipo);
        go.name = nombre;
        go.transform.SetParent(padre, false);
        go.transform.localPosition = posicionLocal;
        go.transform.localScale = escalaLocal;

        var renderer = go.GetComponent<MeshRenderer>();

        if (renderer != null)
        {
            renderer.sharedMaterial = material;
        }

        return go;
    }

    private static GameObject GuardarPrefab(GameObject go, string ruta)
    {
        return PrefabUtility.SaveAsPrefabAssetAndConnect(
            go, ruta, InteractionMode.AutomatedAction
        );
    }

    private static void InstanciarSobreTerreno(
        GameObject prefab,
        Transform padre,
        float x,
        float z,
        float rotacionY,
        string nombre,
        float escala = 1f
    )
    {
        if (prefab == null)
        {
            return;
        }

        var instancia = (GameObject)PrefabUtility.InstantiatePrefab(prefab, padre);
        instancia.name = nombre;
        instancia.transform.localPosition = new Vector3(x, AlturaEn(x, z), z);
        instancia.transform.localRotation = Quaternion.Euler(0f, rotacionY, 0f);
        instancia.transform.localScale = Vector3.one * escala;
    }

    private static void CrearCarpetas()
    {
        CrearCarpeta("Assets", "Materials");
        CrearCarpeta("Assets", "Prefabs");
        CrearCarpeta("Assets", "Scenes");
        CrearCarpeta("Assets", "Terreno");
    }

    private static void CrearCarpeta(string padre, string nombre)
    {
        if (!AssetDatabase.IsValidFolder(padre + "/" + nombre))
        {
            AssetDatabase.CreateFolder(padre, nombre);
        }
    }

    private static void AgregarAEscenasDeBuild()
    {
        var escenas = new List<EditorBuildSettingsScene>(
            EditorBuildSettings.scenes
        );

        foreach (var escena in escenas)
        {
            if (escena.path == RutaEscena)
            {
                return;
            }
        }

        escenas.Add(new EditorBuildSettingsScene(RutaEscena, true));
        EditorBuildSettings.scenes = escenas.ToArray();
    }
}
