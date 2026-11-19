using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Camara orbital del escenario 3D.
///
/// MOUSE
///   Boton derecho  -> orbitar alrededor del centro de interes
///   Boton central  -> desplazar el centro sobre el plano del terreno
///   Rueda          -> acercar / alejar
///
/// TECLADO
///   Flechas        -> orbitar (izquierda/derecha gira, arriba/abajo inclina)
///   W A S D        -> desplazar el centro sobre el terreno
///   Q / E          -> alejar / acercar
///   F              -> volver al encuadre inicial
///   M              -> vista aerea (campo completo) / volver
///   H              -> mostrar u ocultar la ayuda en pantalla
///   Shift          -> mover mas rapido (mantener)
///
/// Todos los movimientos se interpolan con un suavizado exponencial,
/// de modo que la camara nunca "salta" de un fotograma a otro.
/// </summary>
public class OrbitCamera : MonoBehaviour
{
    [Header("CENTRO DE INTERES")]
    public Transform objetivo;

    [Header("ENCUADRE INICIAL")]
    public float distancia = 17f;
    public float yaw = 35f;
    public float pitch = 26f;

    [Header("SENSIBILIDAD MOUSE")]
    public float sensibilidadOrbita = 0.25f;
    public float sensibilidadDesplazamiento = 0.0025f;
    public float factorZoom = 0.9f;

    [Header("VELOCIDAD TECLADO")]
    public float velocidadOrbita = 55f;
    public float velocidadDesplazamiento = 7f;
    public float velocidadZoom = 14f;
    public float multiplicadorRapido = 2.5f;

    [Header("LIMITES")]
    public float pitchMinimo = 8f;
    public float pitchMaximo = 80f;
    public float distanciaMinima = 5f;
    public float distanciaMaxima = 45f;
    public float limiteDesplazamiento = 14f;

    [Header("SUAVIZADO")]
    public float suavizado = 8f;

    [Header("AYUDA EN PANTALLA")]
    public bool mostrarAyuda = true;

    // Estado deseado (lo que pide el usuario)
    private float yawObjetivo;
    private float pitchObjetivo;
    private float distanciaObjetivo;

    // Estado suavizado (lo que realmente se dibuja)
    private float yawActual;
    private float pitchActual;
    private float distanciaActual;
    private Vector3 centroActual;

    // Encuadre de arranque, para poder volver con la tecla F
    private Vector3 centroInicial;
    private GUIStyle estiloAyuda;
    private bool enVistaAerea;
    private float pitchAntes;
    private float distanciaAntes;
    private float yawInicial;
    private float pitchInicial;
    private float distanciaInicial;

    void Start()
    {
        if (objetivo == null)
        {
            // Sin centro asignado la camara orbita el origen.
            var centro = new GameObject("CentroEscena");
            objetivo = centro.transform;
        }

        yawInicial = yaw;
        pitchInicial = pitch;
        distanciaInicial = distancia;
        centroInicial = objetivo.position;

        yawObjetivo = yawActual = yaw;
        pitchObjetivo = pitchActual = pitch;
        distanciaObjetivo = distanciaActual = distancia;
        centroActual = centroInicial;

        AplicarTransformacion();

        // Para las pruebas automaticas: arrancar en vista aerea
        if (System.Array.IndexOf(
                System.Environment.GetCommandLineArgs(), "-aerea") >= 0)
        {
            AlternarVistaAerea();
        }
    }

    void LateUpdate()
    {
        LeerEntrada();

        // Suavizado independiente del framerate:
        // t tiende a 1 cuando suavizado*dt es grande.
        float t = 1f - Mathf.Exp(-suavizado * Time.deltaTime);

        yawActual = Mathf.LerpAngle(yawActual, yawObjetivo, t);
        pitchActual = Mathf.Lerp(pitchActual, pitchObjetivo, t);
        distanciaActual = Mathf.Lerp(distanciaActual, distanciaObjetivo, t);
        centroActual = Vector3.Lerp(centroActual, objetivo.position, t);

        AplicarTransformacion();
    }

    private void LeerEntrada()
    {
        LeerMouse();
        LeerTeclado();
    }

    private void LeerMouse()
    {
        var raton = Mouse.current;

        if (raton == null)
        {
            return;
        }

        Vector2 delta = raton.delta.ReadValue();

        if (raton.rightButton.isPressed && delta.sqrMagnitude > 0f)
        {
            yawObjetivo += delta.x * sensibilidadOrbita;
            pitchObjetivo = Mathf.Clamp(
                pitchObjetivo - delta.y * sensibilidadOrbita,
                pitchMinimo,
                pitchMaximo
            );
        }

        if (raton.middleButton.isPressed && delta.sqrMagnitude > 0f)
        {
            Vector3 derecha = transform.right;
            Vector3 adelante = Vector3.ProjectOnPlane(
                transform.forward,
                Vector3.up
            ).normalized;

            Vector3 desplazamiento =
                (derecha * -delta.x + adelante * -delta.y) *
                sensibilidadDesplazamiento *
                distanciaActual;

            DesplazarCentro(desplazamiento);
        }

        float rueda = raton.scroll.ReadValue().y;

        if (Mathf.Abs(rueda) > 0.01f)
        {
            distanciaObjetivo = Mathf.Clamp(
                distanciaObjetivo * Mathf.Pow(factorZoom, Mathf.Sign(rueda)),
                distanciaMinima,
                distanciaMaxima
            );
        }
    }

    private void LeerTeclado()
    {
        var teclado = Keyboard.current;

        if (teclado == null)
        {
            return;
        }

        if (teclado.hKey.wasPressedThisFrame)
        {
            mostrarAyuda = !mostrarAyuda;
        }

        if (teclado.fKey.wasPressedThisFrame)
        {
            ReiniciarEncuadre();
        }

        if (teclado.mKey.wasPressedThisFrame)
        {
            AlternarVistaAerea();
        }

        // dt limita el efecto al paso real entre fotogramas
        float dt = Mathf.Min(Time.deltaTime, 0.1f);
        float rapido =
            teclado.leftShiftKey.isPressed || teclado.rightShiftKey.isPressed
                ? multiplicadorRapido
                : 1f;

        // ---- Orbitar con flechas ----
        float giro = velocidadOrbita * dt * rapido;

        if (teclado.leftArrowKey.isPressed)
        {
            yawObjetivo -= giro;
        }

        if (teclado.rightArrowKey.isPressed)
        {
            yawObjetivo += giro;
        }

        if (teclado.upArrowKey.isPressed)
        {
            pitchObjetivo = Mathf.Clamp(
                pitchObjetivo - giro, pitchMinimo, pitchMaximo
            );
        }

        if (teclado.downArrowKey.isPressed)
        {
            pitchObjetivo = Mathf.Clamp(
                pitchObjetivo + giro, pitchMinimo, pitchMaximo
            );
        }

        // ---- Desplazar con WASD ----
        Vector3 derecha = Vector3.ProjectOnPlane(
            transform.right, Vector3.up
        ).normalized;
        Vector3 adelante = Vector3.ProjectOnPlane(
            transform.forward, Vector3.up
        ).normalized;

        Vector3 movimiento = Vector3.zero;

        if (teclado.wKey.isPressed)
        {
            movimiento += adelante;
        }

        if (teclado.sKey.isPressed)
        {
            movimiento -= adelante;
        }

        if (teclado.aKey.isPressed)
        {
            movimiento -= derecha;
        }

        if (teclado.dKey.isPressed)
        {
            movimiento += derecha;
        }

        if (movimiento.sqrMagnitude > 0f)
        {
            float velocidad = velocidadDesplazamiento * rapido;

            // Mas lejos = desplazamiento proporcional, para que se sienta igual
            velocidad *= Mathf.Clamp(distanciaActual / 17f, 0.6f, 2.5f);

            DesplazarCentro(
                movimiento.normalized * velocidad * dt
            );
        }

        // ---- Zoom con Q / E ----
        if (teclado.qKey.isPressed)
        {
            distanciaObjetivo = Mathf.Clamp(
                distanciaObjetivo + velocidadZoom * dt,
                distanciaMinima,
                distanciaMaxima
            );
        }

        if (teclado.eKey.isPressed)
        {
            distanciaObjetivo = Mathf.Clamp(
                distanciaObjetivo - velocidadZoom * dt,
                distanciaMinima,
                distanciaMaxima
            );
        }
    }

    private void DesplazarCentro(Vector3 desplazamiento)
    {
        Vector3 destino = objetivo.position + desplazamiento;

        // No dejar que el centro se pierda fuera del terreno
        destino.x = Mathf.Clamp(
            destino.x, -limiteDesplazamiento, limiteDesplazamiento
        );
        destino.z = Mathf.Clamp(
            destino.z, -limiteDesplazamiento, limiteDesplazamiento
        );

        objetivo.position = destino;
    }

    /// <summary>
    /// Pasa a una vista cenital que abarca todo el campo (100 ha) y vuelve
    /// al encuadre anterior con la misma tecla.
    /// </summary>
    public void AlternarVistaAerea()
    {
        if (!enVistaAerea)
        {
            pitchAntes = pitchObjetivo;
            distanciaAntes = distanciaObjetivo;

            pitchObjetivo = 82f;
            distanciaObjetivo = 760f;
            enVistaAerea = true;
        }
        else
        {
            pitchObjetivo = pitchAntes;
            distanciaObjetivo = distanciaAntes;
            enVistaAerea = false;
        }
    }

    private void ReiniciarEncuadre()
    {
        objetivo.position = centroInicial;
        yawObjetivo = yawInicial;
        pitchObjetivo = pitchInicial;
        distanciaObjetivo = distanciaInicial;
    }

    private void AplicarTransformacion()
    {
        Quaternion rotacion = Quaternion.Euler(pitchActual, yawActual, 0f);

        transform.SetPositionAndRotation(
            centroActual - rotacion * Vector3.forward * distanciaActual,
            rotacion
        );
    }

    private void OnGUI()
    {
        if (!mostrarAyuda)
        {
            return;
        }

        if (estiloAyuda == null)
        {
            estiloAyuda = new GUIStyle(GUI.skin.box)
            {
                alignment = TextAnchor.UpperLeft,
                fontSize = 13,
                padding = new RectOffset(10, 10, 8, 8)
            };
        }

        GUI.Box(
            new Rect(12f, 12f, 300f, 132f),
            "Camara\n" +
            "Flechas: orbitar\n" +
            "W A S D: desplazar\n" +
            "Rueda o Q/E: zoom\n" +
            "Shift: mas rapido\n" +
            "F: reiniciar   M: vista aerea   H: ayuda",
            estiloAyuda
        );
    }
}
