// Cielo en gradiente para el escenario 3D.
// Se usa como material de Skybox: tres colores (arriba, horizonte, abajo)
// mezclados segun la direccion de la mirada. No depende de texturas.
Shader "Campo3D/CieloGradiente"
{
    Properties
    {
        _ColorArriba ("Color arriba", Color) = (0.18, 0.34, 0.62, 1)
        _ColorHorizonte ("Color horizonte", Color) = (0.72, 0.82, 0.92, 1)
        _ColorAbajo ("Color abajo", Color) = (0.42, 0.44, 0.38, 1)
        _Potencia ("Potencia del degradado", Range(0.3, 6)) = 1.6
    }

    SubShader
    {
        Tags
        {
            "Queue" = "Background"
            "RenderType" = "Background"
            "PreviewType" = "Skybox"
            "IgnoreProjector" = "True"
            "RenderPipeline" = "UniversalPipeline"
        }

        Cull Off
        ZWrite Off
        ZTest LEqual

        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _ColorArriba;
                float4 _ColorHorizonte;
                float4 _ColorAbajo;
                float _Potencia;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 direccion : TEXCOORD0;
            };

            Varyings vert(Attributes entrada)
            {
                Varyings salida;
                salida.positionCS = TransformObjectToHClip(entrada.positionOS.xyz);
                salida.direccion = entrada.positionOS.xyz;
                return salida;
            }

            half4 frag(Varyings entrada) : SV_Target
            {
                float3 direccion = normalize(entrada.direccion);
                float haciaArriba = saturate(direccion.y);
                float haciaAbajo = saturate(-direccion.y);

                float3 color = lerp(
                    _ColorHorizonte.rgb,
                    _ColorArriba.rgb,
                    pow(haciaArriba, 1.0 / max(_Potencia, 0.01))
                );

                color = lerp(
                    color,
                    _ColorAbajo.rgb,
                    pow(haciaAbajo, 1.0 / max(_Potencia, 0.01))
                );

                return half4(color, 1.0);
            }
            ENDHLSL
        }
    }

    Fallback Off
}
