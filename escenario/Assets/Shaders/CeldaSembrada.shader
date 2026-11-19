// Shader de las celdas sembradas.
//
// Efecto: cada celda es un disco con brillo aditivo que "respira" (pulso
// senoidal). El degrade radial se calcula desde las UV del disco, asi que
// no necesita ninguna textura.
Shader "Campo3D/CeldaSembrada"
{
    Properties
    {
        _Color ("Color", Color) = (0.35, 1.0, 0.45, 1)
        _Brillo ("Brillo", Range(0.5, 4)) = 1.8
        _Pulso ("Velocidad del pulso", Range(0, 8)) = 2.2
        _Borde ("Suavidad del borde", Range(0.01, 0.6)) = 0.18
    }

    SubShader
    {
        Tags
        {
            "RenderType" = "Transparent"
            "Queue" = "Transparent"
            "RenderPipeline" = "UniversalPipeline"
            "IgnoreProjector" = "True"
            "PreviewType" = "Plane"
        }

        Blend One One
        ZWrite Off
        Cull Off

        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _Color;
                float _Brillo;
                float _Pulso;
                float _Borde;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            Varyings vert(Attributes entrada)
            {
                Varyings salida;
                salida.positionCS = TransformObjectToHClip(entrada.positionOS.xyz);
                salida.uv = entrada.uv;
                return salida;
            }

            half4 frag(Varyings entrada) : SV_Target
            {
                // Distancia al centro del disco (0 centro, 1 borde)
                float2 desdeCentro = entrada.uv - 0.5;
                float distancia = length(desdeCentro) * 2.0;

                float disco = 1.0 - smoothstep(1.0 - _Borde, 1.0, distancia);
                float pulso = 0.78 + 0.30 * sin(_Time.y * _Pulso + entrada.uv.x * 6.28);

                float alpha = disco * pulso;
                half3 color = _Color.rgb * _Brillo * pulso;

                return half4(color * alpha, alpha);
            }
            ENDHLSL
        }
    }

    Fallback Off
}
