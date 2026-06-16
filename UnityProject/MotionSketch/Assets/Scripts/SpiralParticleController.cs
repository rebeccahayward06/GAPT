using UnityEngine;

/// <summary>
/// Attach to a circle-gesture particle system GameObject.
/// isRightArm controls gesture names, colour palette, and arm side.
/// Big gesture → larger radius range. Small gesture → smaller radius range.
/// </summary>
[RequireComponent(typeof(ParticleSystem))]
public class SpiralParticleController : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private ParticleManager particleManager;
    [SerializeField] private ScreenBounds screenBounds;

    [Header("Arm Side")]
    [Tooltip("Off = left arm (cold). On = right arm (warm).")]
    [SerializeField] private bool isRightArm = false;

    [Header("Spiral Parameters")]
    [SerializeField] private float spiralSpeed = 50f;
    [SerializeField] private Vector2 emissionRateRange = new Vector2(50f, 500f);

    [Header("Big Gesture Size")]
    [SerializeField] private Vector2 bigParticleSizeRange = new Vector2(0.5f, 1.5f);
    [SerializeField] private Vector2 bigSpiralRadiusRange = new Vector2(2f, 4f);

    [Header("Small Gesture Size")]
    [SerializeField] private Vector2 smallParticleSizeRange = new Vector2(0.1f, 0.5f);
    [SerializeField] private Vector2 smallSpiralRadiusRange = new Vector2(0.3f, 1.2f);

    // ── Private state ─────────────────────────────────────────────────────
    private ParticleSystem _ps;
    private ParticleSystem.EmissionModule _emission;
    private ParticleSystem.MainModule _main;
    private ParticleSystem.VelocityOverLifetimeModule _velocity;
    private ParticleSystem.ShapeModule _shape;

    private string _gesture;

    private float _currentAngle = 0f;
    private float _currentEmissionRate = 0f;
    private float _currentRadius = 2f;

    private bool _isActive = false;
    private float _lastPacketTime = -999f;
    private const float GestureTimeout = 1f;

    // ── Unity lifecycle ───────────────────────────────────────────────────
    void Awake()
    {
        _ps = GetComponent<ParticleSystem>();
        _emission = _ps.emission;
        _main = _ps.main;
        _velocity = _ps.velocityOverLifetime;
        _shape = _ps.shape;

        if (particleManager == null)
            particleManager = FindFirstObjectByType<ParticleManager>();
        if (screenBounds == null)
            screenBounds = FindFirstObjectByType<ScreenBounds>();
    }

    void Start()
    {
        // Derived in Start so Inspector values are guaranteed applied
        string side = isRightArm ? "right" : "left";
        _gesture = $"circle_{side}";   // size is continuous now, not in the label

        _shape.enabled = true;
        _shape.shapeType = ParticleSystemShapeType.Circle;
        _shape.radius = 2f;
        _main.startLifetime = 10f;
        _main.playOnAwake = false;

        _ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        MoveToRandomPosition();

        if (particleManager != null)
            particleManager.RegisterParticleSystem(_ps);
        else
            Debug.LogWarning("[SpiralParticleController] No ParticleManager found.");
    }

    void OnEnable() => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName != _gesture)
        {
            _isActive = false;
            return;
        }

        bool wasInactive = !_isActive || (Time.time - _lastPacketTime > GestureTimeout);
        _lastPacketTime = Time.time;
        _isActive = true;

        if (wasInactive)
        {
            MoveToRandomPosition();
            _ps.Clear();
            _ps.Play();
        }

        // Size is continuous: brushSize 0 → small end, 1 → big end (spans both ranges)
        float sizeLo = smallParticleSizeRange.x;
        float sizeHi = bigParticleSizeRange.y;
        _main.startSize = Mathf.Lerp(sizeLo, sizeHi, p.brushSize);

        float radLo = smallSpiralRadiusRange.x;
        float radHi = bigSpiralRadiusRange.y;
        float targetRad = Mathf.Lerp(radLo, radHi, p.brushSize);
        _currentRadius = Mathf.Lerp(_currentRadius, targetRad, Time.deltaTime * 5f);

        float targetEmission = Mathf.Lerp(emissionRateRange.x, emissionRateRange.y, p.particleSpeed);
        _currentEmissionRate = Mathf.Lerp(_currentEmissionRate, targetEmission, Time.deltaTime * 5f);

        _main.startLifetime = Mathf.Lerp(3f, 10f, p.blurAmount);

        if (particleManager != null)
        {
            _main.startColor = isRightArm
                ? particleManager.GetRightArmColor(p.colorShift)
                : particleManager.GetLeftArmColor(p.colorShift);
        }
    }

    // ── Update ────────────────────────────────────────────────────────────
    void Update()
    {
        if (_isActive && Time.time - _lastPacketTime > GestureTimeout)
        {
            _isActive = false;
            _ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }

        if (!_isActive)
        {
            _emission.rateOverTime = 0f;
            return;
        }

        _emission.rateOverTime = _currentEmissionRate;
        _shape.radius = _currentRadius;

        _currentAngle += spiralSpeed * Time.deltaTime;
        if (_currentAngle > 360f) _currentAngle -= 360f;
        transform.rotation = Quaternion.Euler(0f, 0f, _currentAngle);

        _velocity.enabled = true;
        _velocity.space = ParticleSystemSimulationSpace.World;
        _velocity.orbitalX = new ParticleSystem.MinMaxCurve(_currentRadius * 2f);
    }

    // ── Helpers ───────────────────────────────────────────────────────────
    private void MoveToRandomPosition()
    {
        Vector3 pos = screenBounds != null
            ? screenBounds.GetRandomPosition()
            : new Vector3(Random.Range(-7f, 7f), Random.Range(-4f, 4f), 0f);
        pos.z = transform.position.z;
        transform.position = pos;
    }
}