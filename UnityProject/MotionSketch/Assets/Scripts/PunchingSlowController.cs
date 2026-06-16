using UnityEngine;

/// <summary>
/// Attach to "Punching_slow_left" or "Punching_slow_right".
///
/// Gesture names are auto-derived from isRightArm:
///   Left  arm → punching_slow_left  → cold colours
///   Right arm → punching_slow_right → warm colours
///
/// Emits continuously while the gesture is active (timeout pattern),
/// then stops emitting and lets trails die naturally with their particles.
///
/// OSC mapping:
///   brush_size     → startSize   (trail width via Size affects Width)
///   particle_speed → startSpeed  (how far particles travel before dying)
///   blur_amount    → startLifetime
///   confidence     → emissionRate
///   color_shift    → GetLeftArmColor() or GetRightArmColor()
/// </summary>
[RequireComponent(typeof(ParticleSystem))]
public class PunchingSlowController : MonoBehaviour
{
    [Header("References")]
    [Tooltip("Auto-found if left empty")]
    public ParticleManager particleManager;
    [Tooltip("Auto-found if left empty")]
    public ScreenBounds screenBounds;

    [Header("Arm Side")]
    [Tooltip("Off = left arm (cold). On = right arm (warm).")]
    public bool isRightArm = false;

    [Tooltip("Seconds without a packet before emission stops")]
    public float gestureTimeoutSeconds = 1f;

    [Header("Smoothing")]
    [Range(1f, 20f)]
    public float smoothSpeed = 5f;

    [Header("OSC Ranges")]
    public Vector2 emissionRateRange = new Vector2(50f, 300f);
    public Vector2 startSizeRange = new Vector2(0.02f, 0.15f);
    public Vector2 startSpeedRange = new Vector2(5f, 20f);
    public Vector2 lifetimeRange = new Vector2(0.1f, 0.5f);

    [Header("Colour Brightness")]
    [Tooltip("Multiplies the palette colour brightness — increase if the material appears dim")]
    public float colorBrightnessMultiplier = 1f;
    private ParticleSystem _ps;
    private ParticleSystem.MainModule _main;
    private ParticleSystem.EmissionModule _emission;

    private string _gestureName;

    // Smoothed targets
    private float _targetEmission;
    private float _targetSize;
    private float _targetSpeed;
    private float _targetLifetime;
    private float _targetColorT;

    // Current smoothed values
    private float _curEmission;
    private float _curSize;
    private float _curSpeed;
    private float _curLifetime;
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

        // Seed smoothed values from Inspector defaults
        _targetEmission = 200f;
        _targetSize = 0.05f;
        _targetSpeed = 10f;
        _targetLifetime = 0.25f;
        _targetColorT = 0f;

        _curEmission = _targetEmission;
        _curSize = _targetSize;
        _curSpeed = _targetSpeed;
        _curLifetime = _targetLifetime;
        _curColorT = _targetColorT;

        _main.playOnAwake = false;
        _ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        if (particleManager == null)
            particleManager = FindFirstObjectByType<ParticleManager>();
        if (screenBounds == null)
            screenBounds = FindFirstObjectByType<ScreenBounds>();
    }

    void Start()
    {
        // Derived here not in Awake — Inspector values are guaranteed applied by Start
        _gestureName = isRightArm ? "punching_slow_right" : "punching_slow_left";

        if (particleManager != null)
            particleManager.RegisterParticleSystem(_ps);
        else
            Debug.LogWarning("[PunchingSlowController] No ParticleManager found.");
    }

    void OnEnable() => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName != _gestureName) return;

        bool wasInactive = !_gestureActive ||
                           (Time.time - _lastPacketTime > gestureTimeoutSeconds);

        _lastPacketTime = Time.time;
        _gestureActive = true;
        _hasData = true;

        if (wasInactive)
        {
            MoveToRandomPosition();
            _ps.Clear();
            _ps.Play();
        }

        _targetEmission = Mathf.Lerp(emissionRateRange.x, emissionRateRange.y, p.confidence);
        _targetSize = Mathf.Lerp(startSizeRange.x, startSizeRange.y, p.brushSize);
        _targetSpeed = Mathf.Lerp(startSpeedRange.x, startSpeedRange.y, p.particleSpeed);
        _targetLifetime = Mathf.Lerp(lifetimeRange.x, lifetimeRange.y, p.blurAmount);
        _targetColorT = p.colorShift;
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
        _curSize = Mathf.Lerp(_curSize, _targetSize, dt);
        _curSpeed = Mathf.Lerp(_curSpeed, _targetSpeed, dt);
        _curLifetime = Mathf.Lerp(_curLifetime, _targetLifetime, dt);
        _curColorT = Mathf.Lerp(_curColorT, _targetColorT, dt);

        _emission.rateOverTime = _curEmission;
        _main.startSize = _curSize;
        _main.startSpeed = _curSpeed;
        _main.startLifetime = _curLifetime;

        if (particleManager != null)
        {
            Color baseColor = isRightArm
                ? particleManager.GetRightArmColor(_curColorT)
                : particleManager.GetLeftArmColor(_curColorT);

            _main.startColor = baseColor * colorBrightnessMultiplier;
        }
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