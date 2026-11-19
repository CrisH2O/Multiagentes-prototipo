using UnityEngine;

/// <summary>
/// Menu inicial de la escena 3D, equivalente al de la version 2D:
/// elegir terreno, cantidad de tractores, estrategia, cantidad de obstaculos
/// y semilla de generacion antes de simular.
///
/// Mientras el menu esta visible, la simulacion no corre. Al presionar
/// "Iniciar" se activa el terreno elegido y se pide a Python el payload
/// correspondiente (incluidos los obstaculos y la semilla).
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
    private string textoObstaculos = "0";
    private string textoSemilla = "3";
    private float ultimoInicio = -10f;
    private string aviso;
    private float avisoHasta;

    private bool visible = true;
    private GUIStyle estilo;
    private GUIStyle boton;
    private GUIStyle titulo;
    private GUIStyle centrado;

    void Start()
    {
        ActivarTerreno();

        string[] argumentos = System.Environment.GetCommandLineArgs();

        // Para pruebas automaticas
        if (System.Array.IndexOf(argumentos, "-conobstaculos") >= 0)
        {
            textoObstaculos = "140";
        }

        int posObstaculos = System.Array.IndexOf(argumentos, "-obstaculos");

        if (posObstaculos >= 0 && posObstaculos + 1 < argumentos.Length &&
            int.TryParse(argumentos[posObstaculos + 1], out int numObstaculos))
        {
            textoObstaculos = Mathf.Clamp(numObstaculos, 0, 300).ToString();
        }

        int posSemilla = System.Array.IndexOf(argumentos, "-semilla");

        if (posSemilla >= 0 && posSemilla + 1 < argumentos.Length &&
            int.TryParse(argumentos[posSemilla + 1], out int numSemilla))
        {
            textoSemilla = Mathf.Clamp(numSemilla, 0, 999).ToString();
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
        // Rate limit: no permitir lanzar corridas mas rapido que 1 cada 1.5 s
        if (Time.unscaledTime - ultimoInicio < 1.5f)
        {
            aviso = "Espera un momento antes de iniciar otra corrida.";
            avisoHasta = Time.unscaledTime + 2f;
            return;
        }

        ultimoInicio = Time.unscaledTime;

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
            Obstaculos(),
            Semilla()
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

        float ancho = 440f;
        float alto = 580f;
        var panel = new Rect(
            (Screen.width - ancho) / 2f, (Screen.height - alto) / 2f, ancho, alto
        );

        GUI.Box(panel, GUIContent.none, estilo);

        float x = panel.x + 24f;
        float y = panel.y + 16f;

        GUI.Label(new Rect(x, y, ancho - 48f, 34f), "SIMULACIÓN 3D", titulo);
        y += 44f;

        // --- Terreno ---
        GUI.Label(new Rect(x, y, ancho - 48f, 22f), "SELECCIONAR TERRENO");
        y += 24f;

        for (int i = 0; i < etiquetasTerreno.Length; i++)
        {
            var rect = new Rect(x + i * 126f, y, 118f, 32f);
            string etiqueta = terrenoElegido == i
                ? "> " + etiquetasTerreno[i] + " <"
                : etiquetasTerreno[i];

            if (GUI.Button(rect, etiqueta, boton))
            {
                terrenoElegido = i;
                ActivarTerreno();
            }
        }

        y += 42f;

        // --- Tractores ---
        GUI.Label(
            new Rect(x, y, ancho - 48f, 22f),
            "TRACTORES: " + agentes
        );

        y += 24f;

        if (GUI.Button(new Rect(x, y, 56f, 30f), "-", boton))
        {
            agentes = Mathf.Max(1, agentes - 1);
        }

        if (GUI.Button(new Rect(x + 64f, y, 56f, 30f), "+", boton))
        {
            agentes = Mathf.Min(4, agentes + 1);
        }

        y += 40f;

        // --- Estrategia ---
        GUI.Label(new Rect(x, y, ancho - 48f, 22f), "ESTRATEGIA");
        y += 24f;

        for (int i = 0; i < etiquetasEstrategia.Length; i++)
        {
            var rect = new Rect(x + i * 194f, y, 186f, 32f);
            string etiqueta = estrategiaElegida == i
                ? "> " + etiquetasEstrategia[i] + " <"
                : etiquetasEstrategia[i];

            if (GUI.Button(rect, etiqueta, boton))
            {
                estrategiaElegida = i;
            }
        }

        y += 42f;

        // --- Obstaculos ---
        GUI.Label(
            new Rect(x, y, ancho - 48f, 22f),
            "OBSTÁCULOS (0 a 300)"
        );

        y += 24f;

        textoObstaculos = CampoNumero(
            new Rect(x, y, 120f, 30f), textoObstaculos, 3
        );

        GUI.Label(
            new Rect(x + 130f, y, ancho - 178f, 30f),
            Obstaculos() == 0 ? "campo completo" : "árboles y rocas"
        );

        y += 40f;

        // --- Semilla de generacion ---
        GUI.Label(
            new Rect(x, y, ancho - 48f, 22f),
            "SEMILLA DE OBSTÁCULOS (0 a 999)"
        );

        y += 24f;

        textoSemilla = CampoNumero(
            new Rect(x, y, 120f, 30f), textoSemilla, 3
        );

        if (GUI.Button(new Rect(x + 130f, y, 140f, 30f), "Aleatoria", boton))
        {
            textoSemilla = Random.Range(0, 1000).ToString();
        }

        y += 44f;

        // --- Iniciar ---
        if (GUI.Button(new Rect(x, y, ancho - 48f, 44f), "INICIAR", boton))
        {
            Iniciar();
        }

        if (!string.IsNullOrEmpty(aviso) && Time.unscaledTime < avisoHasta)
        {
            GUI.Label(new Rect(x, y + 50f, ancho - 48f, 24f), aviso, centrado);
        }
    }

    /// <summary>Campo de texto que solo acepta digitos.</summary>
    private string CampoNumero(Rect rect, string texto, int maximoDigitos)
    {
        string escrito = GUI.TextField(rect, texto ?? string.Empty, maximoDigitos, boton);
        string soloDigitos = string.Empty;

        foreach (char caracter in escrito)
        {
            if (char.IsDigit(caracter))
            {
                soloDigitos += caracter;
            }
        }

        return soloDigitos;
    }

    private int Obstaculos()
    {
        return int.TryParse(textoObstaculos, out int valor)
            ? Mathf.Clamp(valor, 0, 300)
            : 0;
    }

    private int Semilla()
    {
        return int.TryParse(textoSemilla, out int valor)
            ? Mathf.Clamp(valor, 0, 999)
            : 3;
    }

    /// <summary>Selector [-] valor [+] que modifica una variable.</summary>
    private void Paso(float x, float y, ref int valor, int paso, int minimo, int maximo)
    {
        if (GUI.Button(new Rect(x, y, 48f, 30f), "-", boton))
        {
            valor = Mathf.Max(minimo, valor - paso);
        }

        GUI.Label(new Rect(x + 54f, y, 50f, 30f), valor.ToString(), centrado);

        if (GUI.Button(new Rect(x + 110f, y, 48f, 30f), "+", boton))
        {
            valor = Mathf.Min(maximo, valor + paso);
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

        centrado = new GUIStyle(GUI.skin.label)
        {
            alignment = TextAnchor.MiddleCenter,
            fontSize = 14
        };
    }
}
