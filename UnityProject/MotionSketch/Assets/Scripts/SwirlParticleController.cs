using UnityEngine;

/// <summary>
/// Attach this to the "Swirl" GameObject (hip_rotation_both gesture).
/// Registers with ParticleManager so whipping clears it along with everything else,
/// and uses GetHipColor() for colour consistency across all systems.
/// </summary>
[RequireComponent(typeof(ParticleSystem))]
public class SwirlParticleController : MonoBehaviour
{
    [Header("References")]
    [Tooltip("Auto-found if left empty")]
    public ParticleManager particleManager;
    [Tooltip("Auto-found if left empty")]
    public ScreenBounds    screenBounds;

    [Header("Gesture filter")]
    public string targetGesture = "hip_rotation_both";

    [Tooltip("Seconds without a packet before the gesture is considered inactive")]
    public float gestureTimeoutSeconds = 1f;

    [Header("Smoothing")]
    [Range(1f, 20f)]
    public float smoothSpeed = 5f;

    [Header("Emission")]
    public float emissionMin = 10f;
    public float emissionMax = 70f;

    [Header("Start Size")]
    public float sizeMin = 2f;
    public float sizeMax = 12f;

    [Header("Rotation over Lifetime (degrees/sec)")]
    public float rotationMin = 90f;
    public float rotationMax = 540f;

    // ── Private state ─────────────────────────────────────────────────────
    private ParticleSystem                            _ps;
    private ParticleSystem.MainModule                 _main;
    private ParticleSystem.EmissionModule             _emission;
    private ParticleSystem.RotationOverLifetimeModule _rotation;
    private ParticleSystem.ColorOverLifetimeModule    _color;

    private float _targetEmission  = 50f;
    private float _targetSize      = 7f;
    private float _targetRotation  = 270f;
    private float _targetAlpha     = 1f;
    private float _targetColorT    = 0f;    // drives GetHipColor() instead of raw hue

    private float _curEmission;
    private float _curSize;
    private float _curRotation;
    private float _curAlpha;
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
        _rotation = _ps.rotationOverLifetime;
        _color    = _ps.colorOverLifetime;

        _curEmission  = _targetEmission;
        _curSize      = _targetSize;
        _curRotation  = _targetRotation;
        _curAlpha     = _targetAlpha;
        _curColorT    = _targetColorT;

        if (particleManager == null)
            particleManager = FindFirstObjectByType<ParticleManager>();
        if (screenBounds == null)
            screenBounds = FindFirstObjectByType<ScreenBounds>();
    }

    void Start()
    {
        // Stop immediately — system only plays when OSC data arrives,
        // regardless of the "Play On Awake" setting in the Inspector.
        _ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        if (particleManager != null)
            particleManager.RegisterParticleSystem(_ps);
        else
            Debug.LogWarning("[SwirlParticleController] No ParticleManager found.");
    }

    void OnEnable()  => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    void Update()
    {
        if (_gestureActive && Time.time - _lastPacketTime > gestureTimeoutSeconds)
        {
            _gestureActive = false;
            _ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }

        if (!_hasData) return;

        float dt = Time.deltaTime * smoothSpeed;
        _curEmission  = Mathf.Lerp(_curEmission,  _targetEmission,  dt);
        _curSize      = Mathf.Lerp(_curSize,       _targetSize,      dt);
        _curRotation  = Mathf.Lerp(_curRotation,   _targetRotation,  dt);
        _curAlpha     = Mathf.Lerp(_curAlpha,       _targetAlpha,     dt);
        _curColorT    = Mathf.Lerp(_curColorT,      _targetColorT,    dt);

        ApplyToParticleSystem();
    }

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName != targetGesture) return;

        bool wasInactive = !_gestureActive ||
                           (Time.time - _lastPacketTime > gestureTimeoutSeconds);

        _lastPacketTime = Time.time;
        _gestureActive  = true;
        _hasData        = true;

        if (wasInactive)
        {
            MoveToRandomPosition();
            _ps.Clear();
            _ps.Play();
        }

        _targetEmission  = Mathf.Lerp(emissionMin, emissionMax, p.confidence);
        _targetSize      = Mathf.Lerp(sizeMin,      sizeMax,     p.brushSize);
        _targetRotation  = Mathf.Lerp(rotationMin,  rotationMax, p.lineCurvature);
        _targetAlpha     = p.blurAmount;
        _targetColorT    = p.colorShift;   // passed to GetHipColor()
    }

    // ── Apply to particle system ──────────────────────────────────────────
    private void ApplyToParticleSystem()
    {
        _emission.rateOverTime = _curEmission;
        _main.startSize        = _curSize;

        _rotation.z = new ParticleSystem.MinMaxCurve(
            _curRotation * 0.5f * Mathf.Deg2Rad,
            _curRotation * Mathf.Deg2Rad);

        // Colour from ParticleManager hip palette, with alpha fade over lifetime
        Color baseColor = particleManager != null
            ? particleManager.GetHipColor(_curColorT)
            : Color.green;

        var gradient = new Gradient();
        gradient.SetKeys(
            new GradientColorKey[]
            {
                new GradientColorKey(baseColor, 0f),
                new GradientColorKey(baseColor, 1f)
            },
            new GradientAlphaKey[]
            {
                new GradientAlphaKey(_curAlpha, 0f),
                new GradientAlphaKey(0f,         1f)
            }
        );
        _color.color = new ParticleSystem.MinMaxGradient(gradient);
    }

    // ── Helpers ───────────────────────────────────────────────────────────
    private void MoveToRandomPosition()
    {
        if (screenBounds == null) return;
        Vector3 pos = screenBounds.GetRandomPosition();
        pos.z = transform.position.z;
        transform.position = pos;
    }
}
