using System.Collections;
using UnityEngine;

/// <summary>
/// Attach to the "Hip_Thrust_Ripple" GameObject.
///
/// Each hip_thrust activation fires a fixed number of ripple rings
/// with a deliberate time gap between each one so they are clearly
/// visible as separate expanding rings.
///
/// OSC mapping:
///   brush_size     → startSize      (how large rings expand)
///   particle_speed → timeBetweenRings (faster punch = tighter gap)
///   blur_amount    → startLifetime  (how long each ring expands before fading)
///   confidence     → ring count     (3 to 5 rings)
///   color_shift    → GetHipColor()
/// </summary>
[RequireComponent(typeof(ParticleSystem))]
public class HipThrustRippleController : MonoBehaviour
{
    [Header("References")]
    [Tooltip("Auto-found if left empty")]
    public ParticleManager particleManager;
    [Tooltip("Auto-found if left empty")]
    public ScreenBounds screenBounds;

    [Header("Gesture")]
    public string targetGesture = "hip_thrust";

    [Header("Ring Settings")]
    [Tooltip("Minimum number of rings per activation")]
    public int minRings = 3;
    [Tooltip("Maximum number of rings per activation")]
    public int maxRings = 5;
    [Tooltip("Time gap range between each ring in seconds (maps from particle_speed)")]
    public Vector2 ringGapRange = new Vector2(0.4f, 1.2f);

    [Header("OSC Ranges")]
    public Vector2 startSizeRange = new Vector2(3f, 10f);
    public Vector2 lifetimeRange = new Vector2(6f, 12f);

    [Tooltip("Minimum seconds before the gesture can trigger again")]
    public float cooldownSeconds = 2f;

    // ── Private ───────────────────────────────────────────────────────────
    private ParticleSystem _ps;
    private ParticleSystem.MainModule _main;
    private ParticleSystem.EmissionModule _emission;

    private bool _isFiring = false;
    private float _lastTriggerTime = -999f;

    // ── Unity lifecycle ───────────────────────────────────────────────────
    void Awake()
    {
        _ps = GetComponent<ParticleSystem>();
        _main = _ps.main;
        _emission = _ps.emission;

        _main.loop = false;
        _main.playOnAwake = false;
        _emission.rateOverTime = 0f;
        _ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        if (particleManager == null)
            particleManager = FindFirstObjectByType<ParticleManager>();
        if (screenBounds == null)
            screenBounds = FindFirstObjectByType<ScreenBounds>();
    }

    void Start()
    {
        if (particleManager != null)
            particleManager.RegisterParticleSystem(_ps);
        else
            Debug.LogWarning("[HipThrustRippleController] No ParticleManager found.");
    }

    void OnEnable() => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName != targetGesture) return;
        if (_isFiring) return;
        if (Time.time - _lastTriggerTime < cooldownSeconds) return;

        _lastTriggerTime = Time.time;
        StartCoroutine(FireRings(p));
    }

    // ── Coroutine ─────────────────────────────────────────────────────────
    private IEnumerator FireRings(OSCReceiver.Prediction p)
    {
        _isFiring = true;

        MoveToRandomPosition();

        // Apply OSC values once for the whole activation
        float size = Mathf.Lerp(startSizeRange.x, startSizeRange.y, p.brushSize);
        float lifetime = Mathf.Lerp(lifetimeRange.x, lifetimeRange.y, p.blurAmount);
        float gap = Mathf.Lerp(ringGapRange.x, ringGapRange.y, 1f - p.particleSpeed);

        _main.startSize = size;
        _main.startLifetime = lifetime;

        if (particleManager != null)
            _main.startColor = particleManager.GetHipColor(p.colorShift);

        // How many rings — confidence 0.7–0.85 maps to 3–5
        int ringCount = Mathf.RoundToInt(Mathf.Lerp(minRings, maxRings, p.confidence));

        // Fire each ring as a single burst with a gap between them
        for (int i = 0; i < ringCount; i++)
        {
            // Emit exactly one particle (one ring) using a temporary burst
            var emission = _ps.emission;
            emission.rateOverTime = 0f;

            // Use ParticleSystem.Emit to fire exactly one particle per ring
            _ps.Play();
            _ps.Emit(1);
            _ps.Stop(false); // stop auto-play but keep existing particles alive

            if (i < ringCount - 1)
                yield return new WaitForSeconds(gap);
        }

        // Wait for the last ring to fully fade
        yield return new WaitForSeconds(lifetime);

        _ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        _isFiring = false;
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