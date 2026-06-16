using UnityEngine;

/// <summary>
/// Attach to a helix particle system GameObject.
/// Set targetGesture to "updown_big" or "updown_small".
/// Set isRightArm to distinguish warm (right) from cold (left) colours,
/// mirrored helix direction, and X spawn side.
///
/// Spawn rules:
///   Left  arm → X = -8, rotation (0,  90, 0)
///   Right arm → X =  8, rotation (0, -90, 0)
///   Y is random within ScreenBounds each activation.
///
/// OSC mapping:
///   brush_size     → amplitude   (width of helix spiral)
///   particle_speed → zSpeed      (how fast particles travel along the helix)
///   line_curvature → frequency   (how many loops in the helix)
///   blur_amount    → startLifetime
///   confidence     → emissionRate
///   color_shift    → GetLeftArmColor() or GetRightArmColor()
/// </summary>
[RequireComponent(typeof(ParticleSystem))]
public class HelixParticleController : MonoBehaviour
{
    [Header("References")]
    [Tooltip("Auto-found if left empty")]
    public ParticleManager particleManager;
    [Tooltip("Auto-found if left empty")]
    public ScreenBounds screenBounds;

    [Header("Gesture")]
    [Tooltip("Set both to cover big and small variants e.g. updown_big_left / updown_small_left")]
    public string targetGestureBig = "updown_big_left";
    public string targetGestureSmall = "updown_small_left";

    [Tooltip("Off = left arm (cold, X = -8). On = right arm (warm, X = 8).")]
    public bool isRightArm = false;

    [Tooltip("Seconds without a packet before the gesture is considered inactive")]
    public float gestureTimeoutSeconds = 1f;

    [Header("Smoothing")]
    [Range(1f, 20f)]
    public float smoothSpeed = 4f;

    [Header("Helix Defaults")]
    public float defaultResolution = 20f;
    public float defaultFrequency = 1f;
    public float defaultAmplitude = 1f;
    public float defaultZSpeed = 5f;

    [Header("OSC Ranges")]
    public Vector2 amplitudeRange = new Vector2(0.5f, 3f);
    public Vector2 zSpeedRange = new Vector2(2f, 15f);
    public Vector2 frequencyRange = new Vector2(1f, 4f);
    public Vector2 lifetimeRange = new Vector2(2f, 8f);
    public Vector2 emissionRateRange = new Vector2(10f, 80f);

    [Header("Spawn X positions")]
    public float leftArmX = -8f;
    public float rightArmX = 8f;

    // ── Private state ─────────────────────────────────────────────────────
    private ParticleSystem _ps;
    private ParticleSystem.MainModule _main;
    private ParticleSystem.EmissionModule _emission;
    private ParticleSystem.VelocityOverLifetimeModule _vel;

    // Only emission and colour are smoothed continuously — all other values
    // are applied once at activation and not modulated mid-flight.
    private float _targetEmission;
    private float _targetColorT;

    private float _curEmission;
    private float _curColorT;

    private bool _hasData = false;
    private bool _gestureActive = false;
    private float _lastPacketTime = -999f;

    // ── Unity lifecycle ───────────────────────────────────────────────────
    void Awake()
    {
        _ps = GetComponent<ParticleSystem>();
        _main = _ps.main;
        _emission = _ps.emission;
        _vel = _ps.velocityOverLifetime;

        // Seed defaults
        _targetEmission = emissionRateRange.x;
        _targetColorT = 0f;
        _curEmission = _targetEmission;
        _curColorT = _targetColorT;

        _main.startSpeed = 0f;
        _vel.enabled = true;
        _vel.space = ParticleSystemSimulationSpace.Local;

        _ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        if (particleManager == null)
            particleManager = FindFirstObjectByType<ParticleManager>();
        if (screenBounds == null)
            screenBounds = FindFirstObjectByType<ScreenBounds>();
    }

    void Start()
    {
        // Build initial curves from defaults so the helix shape is ready before first activation
        RebuildHelixCurves(defaultAmplitude, defaultFrequency, defaultZSpeed);

        if (particleManager != null)
            particleManager.RegisterParticleSystem(_ps);
        else
            Debug.LogWarning("[HelixParticleController] No ParticleManager found.");
    }

    void OnEnable() => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName != targetGestureBig && p.gestureName != targetGestureSmall) return;

        bool wasInactive = !_gestureActive ||
                           (Time.time - _lastPacketTime > gestureTimeoutSeconds);

        _lastPacketTime = Time.time;
        _gestureActive = true;
        _hasData = true;

        if (wasInactive)
        {
            MoveToSpawnPosition();
            ApplyRotation();
            _ps.Clear();
            _ps.Play();
        }

        // Emission rate and colour are safe to modulate continuously
        _targetEmission = Mathf.Lerp(emissionRateRange.x, emissionRateRange.y, p.confidence);
        _targetColorT = p.colorShift;

        // Shape-defining values only on fresh activation — changing lifetime or
        // curves while particles are alive shifts their curve sample position
        // and breaks the helical structure.
        if (wasInactive)
        {
            float amplitude = Mathf.Lerp(amplitudeRange.x, amplitudeRange.y, p.brushSize);
            float zSpeed = Mathf.Lerp(zSpeedRange.x, zSpeedRange.y, p.particleSpeed);
            float frequency = Mathf.Lerp(frequencyRange.x, frequencyRange.y, p.lineCurvature);
            float lifetime = Mathf.Lerp(lifetimeRange.x, lifetimeRange.y, p.blurAmount);

            _main.startLifetime = lifetime;
            RebuildHelixCurves(amplitude, frequency, zSpeed);
        }

    }

    // ── Update ────────────────────────────────────────────────────────────
    void Update()
    {
        if (_gestureActive && Time.time - _lastPacketTime > gestureTimeoutSeconds)
        {
            _gestureActive = false;
            _ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }

        if (!_hasData) return;

        float dt = Time.deltaTime * smoothSpeed;
        _curEmission = Mathf.Lerp(_curEmission, _targetEmission, dt);
        _curColorT = Mathf.Lerp(_curColorT, _targetColorT, dt);

        _emission.rateOverTime = _curEmission;

        // Colour from ParticleManager palette
        if (particleManager != null)
        {
            _main.startColor = isRightArm
                ? particleManager.GetRightArmColor(_curColorT)
                : particleManager.GetLeftArmColor(_curColorT);
        }
    }

    // ── Helix curve builder ───────────────────────────────────────────────
    private void RebuildHelixCurves(float amplitude, float frequency, float zSpeed)
    {
        // Right arm mirrors the X axis (negative amplitude flips the spiral)
        float xAmplitude = isRightArm ? -amplitude : amplitude;

        AnimationCurve curveX = new AnimationCurve();
        AnimationCurve curveY = new AnimationCurve();

        for (int i = 0; i < (int)defaultResolution; i++)
        {
            float t = i / (defaultResolution - 1f);
            curveX.AddKey(t, Mathf.Sin(t * 2f * Mathf.PI * frequency) * xAmplitude);
            curveY.AddKey(t, Mathf.Cos(t * 2f * Mathf.PI * frequency) * amplitude);
        }

        AnimationCurve curveZ = AnimationCurve.Linear(0f, zSpeed, 1f, zSpeed);

        _vel.x = new ParticleSystem.MinMaxCurve(2f, curveX);
        _vel.y = new ParticleSystem.MinMaxCurve(2f, curveY);
        _vel.z = new ParticleSystem.MinMaxCurve(2f, curveZ);
    }

    // ── Helpers ───────────────────────────────────────────────────────────
    private void MoveToSpawnPosition()
    {
        float spawnX = isRightArm ? rightArmX : leftArmX;

        // Random Y within screen bounds, fixed X side, preserve Z
        float spawnY = screenBounds != null
            ? Random.Range(screenBounds.GetRandomPosition().y,
                           screenBounds.GetRandomPosition().y)
            : Random.Range(-4f, 4f);

        // Use ScreenBounds for a proper random Y
        if (screenBounds != null)
        {
            Vector3 randomPos = screenBounds.GetRandomPosition();
            spawnY = randomPos.y;
        }

        transform.position = new Vector3(spawnX, spawnY, transform.position.z);
    }

    private void ApplyRotation()
    {
        transform.rotation = isRightArm
            ? Quaternion.Euler(0f, -90f, 0f)
            : Quaternion.Euler(0f, 90f, 0f);
    }
}