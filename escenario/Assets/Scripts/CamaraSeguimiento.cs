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
    private Transform objetivo;
    private int modo;
    private GUIStyle estilo;

    public int Modo { get { return modo; } }
    public string NombreObjetivo
    {
        get { return objetivo != null ? objetivo.name : "orbita"; }
    }

    void Start()
    {
        orbita = GetComponent<OrbitCamera>();
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
    }
}
