using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Segunda forma de mover la camara: seguir a un tractor.
///
/// Con la tecla C se alterna entre:
///   0 -> camara orbital (OrbitCamera)
///   1 -> seguir Tractor_01
///   2 -> seguir Tractor_02
///   3 -> seguir Tractor_03
///
/// Mientras sigue a un tractor, desactiva OrbitCamera para que no compitan
/// por la misma camara.
/// </summary>
public class CamaraSeguimiento : MonoBehaviour
{
    [Header("ENCUADRE")]
    public float distancia = 9f;
    public float altura = 5f;
    public float alturaMirada = 1.2f;

    [Header("SUAVIZADO")]
    public float suavizadoPosicion = 4f;
    public float suavizadoRotacion = 6f;

    private OrbitCamera orbita;
    private Simulacion3D simulacion;
    private Transform objetivo;
    private int modo;
    private GUIStyle estilo;
    private static Texture2D blanco;

    public int Modo { get { return modo; } }
    public string NombreObjetivo
    {
        get { return objetivo != null ? objetivo.name : "orbita"; }
    }

    void Start()
    {
        orbita = GetComponent<OrbitCamera>();
        simulacion = Object.FindFirstObjectByType<Simulacion3D>();

        // Para las pruebas automaticas: arrancar siguiendo el tractor N
        string[] argumentos = System.Environment.GetCommandLineArgs();
        int posicion = System.Array.IndexOf(argumentos, "-seguir");

        if (posicion >= 0 && posicion + 1 < argumentos.Length &&
            int.TryParse(argumentos[posicion + 1], out int numero))
        {
            modo = Mathf.Clamp(numero, 0, 3);
            AplicarModo();
        }
    }

    void Update()
    {
        var teclado = Keyboard.current;

        if (teclado != null && teclado.cKey.wasPressedThisFrame)
        {
            CiclarModo();
        }
    }

    void LateUpdate()
    {
        if (objetivo == null)
        {
            return;
        }

        Vector3 atras = -objetivo.forward;
        Vector3 destino = objetivo.position +
                          atras * distancia +
                          Vector3.up * altura;

        float t = 1f - Mathf.Exp(-suavizadoPosicion * Time.deltaTime);

        transform.position = Vector3.Lerp(transform.position, destino, t);

        Vector3 mirar = objetivo.position + Vector3.up * alturaMirada;
        Quaternion rotacion = Quaternion.LookRotation(
            mirar - transform.position, Vector3.up
        );

        transform.rotation = Quaternion.Slerp(
            transform.rotation, rotacion,
            1f - Mathf.Exp(-suavizadoRotacion * Time.deltaTime)
        );
    }

    /// <summary>Avanza al siguiente modo (orbita -> tractor 1 -> 2 -> 3).</summary>
    public void CiclarModo()
    {
        modo = (modo + 1) % 4;
        AplicarModo();
    }

    private void AplicarModo()
    {
        if (modo == 0)
        {
            objetivo = null;

            if (orbita != null)
            {
                orbita.enabled = true;
            }

            return;
        }

        var tractor = GameObject.Find("Tractor_" + modo.ToString("D2"));

        if (tractor == null)
        {
            objetivo = null;

            if (orbita != null)
            {
                orbita.enabled = true;
            }

            return;
        }

        objetivo = tractor.transform;

        if (orbita != null)
        {
            orbita.enabled = false;
        }

        // Colocarse ya detras del tractor para no "viajar" desde el origen.
        transform.position = objetivo.position -
                            objetivo.forward * distancia +
                            Vector3.up * altura;

        transform.rotation = Quaternion.LookRotation(
            objetivo.position + Vector3.up * alturaMirada - transform.position,
            Vector3.up
        );
    }

    private void OnGUI()
    {
        if (estilo == null)
        {
            estilo = new GUIStyle(GUI.skin.box)
            {
                alignment = TextAnchor.UpperLeft,
                fontSize = 12,
                padding = new RectOffset(8, 8, 6, 6)
            };
        }

        GUI.Box(
            new Rect(12f, 152f, 300f, 44f),
            "Camara: " + NombreObjetivo + "\nC: cambiar camara",
            estilo
        );

        if (modo > 0)
        {
            DibujarStats();
        }
    }

    /// <summary>Panel con semilla, combustible y celdas del tractor seguido.</summary>
    private void DibujarStats()
    {
        if (simulacion == null)
        {
            return;
        }

        AgenteFrame3D agente = simulacion.AgenteActual(modo - 1);

        if (agente == null)
        {
            return;
        }

        var rect = new Rect(12f, Screen.height - 168f, 316f, 156f);
        GUI.Box(rect, GUIContent.none, estilo);

        float x = rect.x + 10f;
        float y = rect.y + 8f;

        GUI.Label(
            new Rect(x, y, 300f, 20f),
            "Tractor_" + modo.ToString("D2") + "   [" +
            (agente.state ?? "?") + "]"
        );

        y += 24f;

        Barra(
            new Rect(x, y, 216f, 14f),
            agente.seeds / (float)simulacion.MaxSemillas,
            new Color(0.45f, 0.82f, 0.35f)
        );

        GUI.Label(
            new Rect(x + 222f, y - 3f, 90f, 20f),
            agente.seeds + " sem"
        );

        y += 24f;

        Barra(
            new Rect(x, y, 216f, 14f),
            agente.fuel / simulacion.MaxCombustible,
            new Color(0.95f, 0.70f, 0.20f)
        );

        GUI.Label(
            new Rect(x + 222f, y - 3f, 90f, 20f),
            agente.fuel.ToString("F0") + " L"
        );

        y += 24f;

        GUI.Label(
            new Rect(x, y, 300f, 20f),
            "Sembradas: " + agente.planted_total + " celdas"
        );

        y += 22f;

        GUI.Label(
            new Rect(x, y, 300f, 20f),
            "C: cambiar tractor   M: vista aerea"
        );
    }

    private void Barra(Rect rect, float fraccion, Color color)
    {
        if (blanco == null)
        {
            blanco = Texture2D.whiteTexture;
        }

        GUI.color = new Color(0.12f, 0.12f, 0.12f, 0.9f);
        GUI.DrawTexture(rect, blanco);

        GUI.color = color;
        GUI.DrawTexture(
            new Rect(rect.x, rect.y, rect.width * Mathf.Clamp01(fraccion), rect.height),
            blanco
        );

        GUI.color = Color.white;
    }
}
