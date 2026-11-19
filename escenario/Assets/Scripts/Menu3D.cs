using UnityEngine;

/// <summary>
/// Menu inicial de la escena 3D, equivalente al de la version 2D:
/// elegir terreno, cantidad de tractores y estrategia antes de simular.
///
/// Mientras el menu esta visible, la simulacion no corre. Al presionar
/// "Iniciar" se activa el terreno elegido y se pide a Python el payload
/// correspondiente.
/// </summary>
public class Menu3D : MonoBehaviour
{
    public Simulacion3D simulacion;
    public Terrain[] terrenos;

    private readonly string[] etiquetasTerreno = { "Plano", "Colinas", "Montañoso" };
    private readonly string[] clavesTerreno = { "plano", "colinas", "montanoso" };
    private readonly string[] etiquetasEstrategia = { "Planificador", "Zigzag" };
    private readonly string[] clavesEstrategia = { "greedy", "zigzag" };

    private int terrenoElegido = 1;
    private int agentes = 3;
    private int estrategiaElegida;
    private int obstaculos;

    private bool visible = true;
    private GUIStyle estilo;
    private GUIStyle boton;
    private GUIStyle titulo;

    void Start()
    {
        ActivarTerreno();

        string[] argumentos = System.Environment.GetCommandLineArgs();

        // Para pruebas automaticas: arrancar con los valores por defecto
        if (System.Array.IndexOf(argumentos, "-conobstaculos") >= 0)
        {
            obstaculos = 140;
        }

        if (System.Array.IndexOf(argumentos, "-autoiniciar") >= 0)
        {
            Iniciar();
        }
        else if (System.Array.IndexOf(argumentos, "-capturas") >= 0)
        {
            StartCoroutine(CapturarMenu());
        }
    }

    private System.Collections.IEnumerator CapturarMenu()
    {
        yield return new WaitForSeconds(1.5f);
        ScreenCapture.CaptureScreenshot("/tmp/menu_campo3d.png");
        yield return new WaitForSeconds(0.5f);
        Application.Quit(0);
    }

    private void ActivarTerreno()
    {
        if (terrenos == null)
        {
            return;
        }

        for (int i = 0; i < terrenos.Length; i++)
        {
            if (terrenos[i] != null)
            {
                terrenos[i].gameObject.SetActive(i == terrenoElegido);
            }
        }
    }

    private void Iniciar()
    {
        visible = false;
        ActivarTerreno();

        if (simulacion == null)
        {
            return;
        }

        simulacion.terreno = terrenos != null && terrenoElegido < terrenos.Length
            ? terrenos[terrenoElegido]
            : null;

        simulacion.IniciarCon(
            clavesTerreno[terrenoElegido],
            agentes,
            clavesEstrategia[estrategiaElegida],
            obstaculos
        );
    }

    /// <summary>Vuelve a abrir el menu (por ejemplo desde el HUD).</summary>
    public void Mostrar()
    {
        visible = true;
    }

    private void OnGUI()
    {
        CrearEstilos();

        if (!visible)
        {
            if (GUI.Button(
                    new Rect(Screen.width - 128f, Screen.height - 44f, 116f, 30f),
                    "Menú", boton))
            {
                visible = true;
            }

            return;
        }

        float ancho = 420f;
        float alto = 470f;
        var panel = new Rect(
            (Screen.width - ancho) / 2f, (Screen.height - alto) / 2f, ancho, alto
        );

        GUI.Box(panel, GUIContent.none, estilo);

        float x = panel.x + 24f;
        float y = panel.y + 18f;

        GUI.Label(new Rect(x, y, ancho - 48f, 34f), "SIMULACIÓN 3D", titulo);
        y += 44f;

        GUI.Label(new Rect(x, y, ancho - 48f, 22f), "SELECCIONAR TERRENO");
        y += 24f;

        for (int i = 0; i < etiquetasTerreno.Length; i++)
        {
            var rect = new Rect(x + i * 124f, y, 116f, 32f);
            string etiqueta = terrenoElegido == i
                ? "> " + etiquetasTerreno[i] + " <"
                : etiquetasTerreno[i];

            if (GUI.Button(rect, etiqueta, boton))
            {
                terrenoElegido = i;
                ActivarTerreno();
            }
        }

        y += 48f;

        GUI.Label(new Rect(x, y, ancho - 48f, 22f), "TRACTORES: " + agentes);
        y += 24f;

        if (GUI.Button(new Rect(x, y, 56f, 30f), "-", boton))
        {
            agentes = Mathf.Max(1, agentes - 1);
        }

        if (GUI.Button(new Rect(x + 64f, y, 56f, 30f), "+", boton))
        {
            agentes = Mathf.Min(4, agentes + 1);
        }

        y += 48f;

        GUI.Label(new Rect(x, y, ancho - 48f, 22f), "ESTRATEGIA");
        y += 24f;

        for (int i = 0; i < etiquetasEstrategia.Length; i++)
        {
            var rect = new Rect(x + i * 184f, y, 176f, 32f);
            string etiqueta = estrategiaElegida == i
                ? "> " + etiquetasEstrategia[i] + " <"
                : etiquetasEstrategia[i];

            if (GUI.Button(rect, etiqueta, boton))
            {
                estrategiaElegida = i;
            }
        }

        y += 56f;

        GUI.Label(new Rect(x, y, ancho - 48f, 22f), "OBSTÁCULOS (árboles y rocas)");
        y += 24f;

        if (GUI.Button(new Rect(x, y, 176f, 32f), obstaculos == 0 ? "> Sin (100 %) <" : "Sin (100 %)", boton))
        {
            obstaculos = 0;
        }

        if (GUI.Button(new Rect(x + 184f, y, 176f, 32f), obstaculos > 0 ? "> Con (140) <" : "Con (140)", boton))
        {
            obstaculos = 140;
        }

        y += 56f;

        if (GUI.Button(new Rect(x, y, ancho - 48f, 44f), "INICIAR", boton))
        {
            Iniciar();
        }
    }

    private void CrearEstilos()
    {
        if (estilo != null)
        {
            return;
        }

        estilo = new GUIStyle(GUI.skin.box)
        {
            padding = new RectOffset(12, 12, 12, 12)
        };

        boton = new GUIStyle(GUI.skin.button)
        {
            fontSize = 14
        };

        titulo = new GUIStyle(GUI.skin.label)
        {
            fontSize = 20,
            fontStyle = FontStyle.Bold,
            alignment = TextAnchor.MiddleCenter
        };
    }
}
