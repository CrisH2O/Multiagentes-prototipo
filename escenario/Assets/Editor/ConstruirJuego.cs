using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>
/// Construye el ejecutable de macOS con SOLO la escena 3D.
///
/// El .app queda en Builds/Campo3D.app (la escena 2D no se toca).
/// </summary>
public static class ConstruirJuego
{
    private const string RutaEscena = "Assets/Scenes/Campo3D.unity";
    private const string CarpetaBuild = "Builds";
    private const string RutaApp = "Builds/Campo3D.app";

    [MenuItem("Herramientas/Campo 3D/Construir macOS")]
    public static void ConstruirMac()
    {
        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene(RutaEscena, true)
        };

        Directory.CreateDirectory(CarpetaBuild);

        var opciones = new BuildPlayerOptions
        {
            scenes = new[] { RutaEscena },
            locationPathName = RutaApp,
            target = BuildTarget.StandaloneOSX,
            options = BuildOptions.None
        };

        BuildReport reporte = BuildPipeline.BuildPlayer(opciones);
        BuildSummary resumen = reporte.summary;

        Debug.Log(
            "[BUILD] resultado=" + resumen.result +
            " | tamano=" + (resumen.totalSize / (1024f * 1024f)).ToString("F1") + " MB" +
            " | errores=" + resumen.totalErrors +
            " | ruta=" + RutaApp
        );

        if (resumen.result != BuildResult.Succeeded)
        {
            throw new IOException("El build fallo: " + resumen.result);
        }
    }
}
