using UnityEngine;

/// <summary>
/// Attach to "Punching_fast_left" or "Punching_fast_right".
///
/// Gesture names are auto-derived from isRightArm in Start():
///   Left  arm → punching_fast_left  → X = -8, rotation (0,  90, 0), cold colours
///   Right arm → punching_fast_right → X =  8, rotation (0, -90, 0), warm colours
///   Y is random within ScreenBounds each activation.
///
/// Emits continuously while the gesture is active (timeout pattern),
/// then stops and lets trails die naturally with their particles.
///
/// OSC mapping:
///   brush_size     → startSize
///   particle_speed → startSpeed
///   blur_amount    → startLifetime
///   confidence     → emissionRate
///   color_shift    → GetLeftArmColor() or GetRightArmColor()
/// </summary>
[RequireComponent(typeof(ParticleSystem))]
public class PunchingFastController : MonoBehaviour
{
    [Header("References")]
    [Tooltip("Auto-found if left empty")]
    public ParticleManager particleManager;
    [Tooltip("Auto-found if left empty")]
    public ScreenBounds    screenBounds;

    [Header("Arm Side")]
    [Tooltip("Off = left arm (cold, X = -8, rotation 0,90,0).\nOn = right arm (warm, X = 8, rotation 0,-90,0).")]
    public bool isRightArm = false;

    [Header("Spawn")]
    public float leftArmX  = -8f;
    public float rightArmX =  8f;

    [Tooltip("Seconds without a packet before emission stops")]
    public float gestureTimeoutSeconds = 1f;

    [Header("Smoothing")]
    [Range(1f, 20f)]
    public float smoothSpeed = 5f;

    [Header("OSC Ranges")]
    public Vector2 emissionRateRange      = new Vector2(10f,  60f);
    [Tooltip("Overrides emission range for right arm to compensate for dimmer warm material")]
    public Vector2 emissionRateRangeRight = new Vector2(200f, 600f);
    public Vector2 startSizeRange         = new Vector2(0.03f, 0.15f);
    public Vector2 startSpeedRange        = new Vector2(8f,    25f);
    public Vector2 lifetimeRange          = new Vector2(0.4f,  0.9f);

    [Header("Colour Brightness")]
    [Tooltip("Multiplies palette colour — increase on right arm if material appears dim")]
    public float colorBrightnessMultiplier = 1f;

    // ── Private ───────────────────────────────────────────────────────────
    private ParticleSystem                _ps;
    private ParticleSystem.MainModule     _main;
    private ParticleSystem.EmissionModule _emission;

    private string _gestureName;

    private float _targetEmission;
    private float _targetSize;
    private float _targetSpeed;
    private float _targetLifetime;
    private float _targetColorT;

    private float _curEmission;
    private float _curSize;
    private float _curSpeed;
    private float _curLifetime;
    private float _curColorT;

    private bool  _hasData        = false;
    private bool  _gestureActive  = false;
    private float _lastPacketTime = -999f;

    // ── Unity lifecycle ───────────────────────────────────────────────────
    void Awake()
    {
        _ps       = GetComponent<ParticleSystem>();
        _main     = _ps.main;
        _emission = _ps.emission;

        _targetEmission = 20f;
        _targetSize     = 0.05f;
        _targetSpeed    = 15f;
        _targetLifetime = 0.65f;
        _targetColorT   = 0f;

        _curEmission = _targetEmission;
        _curSize     = _targetSize;
        _curSpeed    = _targetSpeed;
        _curLifetime = _targetLifetime;
        _curColorT   = _targetColorT;

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
        _gestureName = isRightArm ? "punching_fast_right" : "punching_fast_left";

        if (particleManager != null)
            particleManager.RegisterParticleSystem(_ps);
        else
            Debug.LogWarning("[PunchingFastController] No ParticleManager found.");
    }

    void OnEnable()  => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName != _gestureName) return;

        bool wasInactive = !_gestureActive ||
                           (Time.time - _lastPacketTime > gestureTimeoutSeconds);

        _lastPacketTime = Time.time;
        _gestureActive  = true;
        _hasData        = true;

        if (wasInactive)
        {
            MoveToSpawnPosition();
            ApplyRotation();
            _ps.Clear();
            _ps.Play();
        }

        Vector2 activeEmissionRange = isRightArm ? emissionRateRangeRight : emissionRateRange;
        _targetEmission = Mathf.Lerp(activeEmissionRange.x, activeEmissionRange.y, p.confidence);
        _targetSize     = Mathf.Lerp(startSizeRange.x,      startSizeRange.y,      p.brushSize);
        _targetSpeed    = Mathf.Lerp(startSpeedRange.x,     startSpeedRange.y,     p.particleSpeed);
        _targetLifetime = Mathf.Lerp(lifetimeRange.x,       lifetimeRange.y,       p.blurAmount);
        _targetColorT   = p.colorShift;
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
        _curSize     = Mathf.Lerp(_curSize,     _targetSize,     dt);
        _curSpeed    = Mathf.Lerp(_curSpeed,    _targetSpeed,    dt);
        _curLifetime = Mathf.Lerp(_curLifetime, _targetLifetime, dt);
        _curColorT   = Mathf.Lerp(_curColorT,   _targetColorT,   dt);

        _emission.rateOverTime = _curEmission;
        _main.startSize        = _curSize;
        _main.startSpeed       = _curSpeed;
        _main.startLifetime    = _curLifetime;

        if (particleManager != null)
        {
            Color baseColor = isRightArm
                ? particleManager.GetRightArmColor(_curColorT)
                : particleManager.GetLeftArmColor(_curColorT);
            _main.startColor = baseColor * colorBrightnessMultiplier;
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────
    private void MoveToSpawnPosition()
    {
        float spawnX = isRightArm ? rightArmX : leftArmX;
        float spawnY = screenBounds != null
            ? screenBounds.GetRandomPosition().y
            : Random.Range(-4f, 4f);
        transform.position = new Vector3(spawnX, spawnY, transform.position.z);
    }

    private void ApplyRotation()
    {
        transform.rotation = isRightArm
            ? Quaternion.Euler(0f, -90f, 0f)
            : Quaternion.Euler(0f,  90f, 0f);
    }
}
