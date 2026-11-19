using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering.Universal;

/// <summary>
/// Utilidad: abre una escena vacia, instancia un modelo OBJ, le cambia los
/// materiales a URP Lit y renderiza una vista previa a /tmp/modelo.png.
/// Sirve para revisar escala, orientacion y materiales antes de usarlo.
/// </summary>
public static class PrevisualizarModelo
{
    private const string RutaModelo = "Assets/Prefabs/Tractor.prefab";

    [MenuItem("Herramientas/Campo 3D/Previsualizar modelo OBJ")]
    public static void Previsualizar()
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var modelo = AssetDatabase.LoadAssetAtPath<GameObject>(RutaModelo);

        if (modelo == null)
        {
            Debug.LogError("[PREVIEW] No se encontro " + RutaModelo);
            return;
        }

        var instancia = (GameObject)PrefabUtility.InstantiatePrefab(modelo);
        var renderers = instancia.GetComponentsInChildren<MeshRenderer>();

        Debug.Log("[PREVIEW] materiales del modelo: " +
            AssetDatabase.LoadAllAssetRepresentationsAtPath(RutaModelo).Length);

        var bounds = new Bounds(Vector3.zero, Vector3.zero);
        bool primero = true;
        int triangulos = 0;

        foreach (var renderer in renderers)
        {
            if (primero)
            {
                bounds = renderer.bounds;
                primero = false;
            }
            else
            {
                bounds.Encapsulate(renderer.bounds);
            }

            var malla = renderer.GetComponent<MeshFilter>()?.sharedMesh;

            if (malla != null)
            {
                triangulos += malla.triangles.Length / 3;
            }

            bool yaEsUrp = renderer.sharedMaterial != null &&
                renderer.sharedMaterial.shader != null &&
                renderer.sharedMaterial.shader.name.Contains("Universal");

            if (!yaEsUrp)
            {
                ConvertirAMaterialUrp(renderer);
            }
        }

        foreach (var renderer in renderers)
        {
            var mats = renderer.sharedMaterials;

            for (int i = 0; i < Mathf.Min(6, mats.Length); i++)
            {
                var m = mats[i];
                Debug.Log("[PREVIEW-MAT] " + i + " " +
                    (m == null ? "NULL" : m.name + " | " + m.shader.name +
                     " | color=" + m.color));
            }
        }

        Debug.Log(
            "[PREVIEW] renderers=" + renderers.Length +
            " | triangulos=" + triangulos +
            " | centro=" + bounds.center +
            " | tamano=" + bounds.size
        );

        // Orientar primero y despues centrar (si no, el pivote queda fuera)
        instancia.transform.rotation = Quaternion.Euler(0f, -90f, 0f);

        var boundsFinal = new Bounds(Vector3.zero, Vector3.zero);
        bool primeroFinal = true;

        foreach (var renderer in renderers)
        {
            if (primeroFinal)
            {
                boundsFinal = renderer.bounds;
                primeroFinal = false;
            }
            else
            {
                boundsFinal.Encapsulate(renderer.bounds);
            }
        }

        instancia.transform.position -= boundsFinal.center;

        CrearCamara(new Bounds(Vector3.zero, boundsFinal.size));
        CrearLuz();

        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.45f, 0.45f, 0.5f);
        RenderSettings.fog = false;

        Renderizar("/tmp/modelo.png");
        Debug.Log("[PREVIEW] listo en /tmp/modelo.png");
    }

    private static void ConvertirAMaterialUrp(MeshRenderer renderer)
    {
        var materiales = renderer.sharedMaterials;

        for (int i = 0; i < materiales.Length; i++)
        {
            var original = materiales[i];

            if (original == null)
            {
                continue;
            }

            var urp = new Material(Shader.Find("Universal Render Pipeline/Lit"))
            {
                name = original.name
            };

            Texture textura = null;

            if (original.HasProperty("_MainTex"))
            {
                textura = original.GetTexture("_MainTex");
            }
            else if (original.HasProperty("_BaseMap"))
            {
                textura = original.GetTexture("_BaseMap");
            }

            if (textura != null)
            {
                urp.SetTexture("_BaseMap", textura);
                urp.SetTextureScale("_BaseMap", original.mainTextureScale);
            }

            Color color = original.color;

            if (color == Color.white && original.HasProperty("_Color"))
            {
                color = original.GetColor("_Color");
            }

            urp.SetColor("_BaseColor", color);
            Debug.Log("[PREVIEW] mat=" + original.name +
                " color=" + color + " textura=" + (textura != null));
            urp.SetFloat("_Smoothness", 0.2f);
            materiales[i] = urp;
        }

        renderer.sharedMaterials = materiales;
    }

    private static void CrearCamara(Bounds bounds)
    {
        var go = new GameObject("Cam");
        var camara = go.AddComponent<Camera>();
        camara.clearFlags = CameraClearFlags.SolidColor;
        camara.backgroundColor = new Color(0.16f, 0.17f, 0.20f);
        camara.fieldOfView = 45f;
        camara.nearClipPlane = 0.01f;
        camara.farClipPlane = 10000f;

        // La camara usa el renderer 3D del pipeline
        camara.GetUniversalAdditionalCameraData().SetRenderer(1);

        float distancia = bounds.size.magnitude * 1.1f;
        Vector3 direccion = new Vector3(0.75f, 0.5f, -0.75f).normalized;

        go.transform.position = bounds.center + direccion * distancia;
        go.transform.LookAt(bounds.center);
    }

    private static void CrearLuz()
    {
        var go = new GameObject("Luz");
        var luz = go.AddComponent<Light>();
        luz.type = LightType.Directional;
        luz.intensity = 1.6f;
        luz.color = new Color(1f, 0.96f, 0.9f);
        luz.shadows = LightShadows.Soft;
        go.transform.rotation = Quaternion.Euler(50f, -35f, 0f);
        RenderSettings.sun = luz;
    }

    private static void Renderizar(string ruta)
    {
        var camara = Object.FindFirstObjectByType<Camera>();
        const int ancho = 1280;
        const int alto = 720;

        var destino = new RenderTexture(ancho, alto, 24, RenderTextureFormat.ARGB32);
        camara.targetTexture = destino;
        camara.Render();

        RenderTexture.active = destino;

        var textura = new Texture2D(ancho, alto, TextureFormat.RGB24, false);
        textura.ReadPixels(new Rect(0, 0, ancho, alto), 0, 0);
        textura.Apply();

        RenderTexture.active = null;
        camara.targetTexture = null;

        File.WriteAllBytes(ruta, textura.EncodeToPNG());

        Object.DestroyImmediate(textura);
        Object.DestroyImmediate(destino);
    }
}
