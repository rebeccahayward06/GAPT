using UnityEngine;

public class CreatingHelix : MonoBehaviour
{
    public float frequency = 1f; // repeat rate of circle (360 degrees)
    public float resolution = 20f; // amount of keys on curve (smooth->increase)
    public float amplitude = 1.0f; // height of curve
    public float zSpeed = 0f; // speed

    void Start()
    {
        CreateHelix();
    }

    void CreateHelix()
    {
        ParticleSystem PS = GetComponent<ParticleSystem>();

        var vel = PS.velocityOverLifetime;
        var main = PS.main;

        main.startSpeed = 0f;
        vel.enabled = true; // enable velocity over lifetime
        vel.space = ParticleSystemSimulationSpace.Local;

        // X axis — sine wave curve
        AnimationCurve curveX = new AnimationCurve();
        for (int i = 0; i < resolution; i++)
        {
            float t = i / (resolution - 1);
            float value = Mathf.Sin(t * 2 * Mathf.PI * frequency) * amplitude;
            curveX.AddKey(t, value);
        }

        // Y axis — cosine wave curve (90° offset from X gives the circular cross-section)
        AnimationCurve curveY = new AnimationCurve();
        for (int i = 0; i < resolution; i++)
        {
            float t = i / (resolution - 1);
            float value = Mathf.Cos(t * 2 * Mathf.PI * frequency) * amplitude;
            curveY.AddKey(t, value);
        }

        // Z axis — flat curve (constant speed), same mode as X and Y
        AnimationCurve curveZ = AnimationCurve.Linear(0f, zSpeed, 1f, zSpeed);

        // All three axes must use the same MinMaxCurve mode — curve mode here
        vel.x = new ParticleSystem.MinMaxCurve(2f, curveX);
        vel.y = new ParticleSystem.MinMaxCurve(2f, curveY);
        vel.z = new ParticleSystem.MinMaxCurve(2f, curveZ);
    }
}
