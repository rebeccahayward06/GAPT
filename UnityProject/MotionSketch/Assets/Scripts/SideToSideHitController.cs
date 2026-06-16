using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Attach to the "Side_to_side_hit" parent GameObject.
/// Fires all child particle systems twice per gesture activation.
///
/// Original size/speed/burst values are cached at startup so that
/// OSC scaling always works from a fixed baseline — never compounds.
/// </summary>
public class SideToSideHitController : MonoBehaviour
{
    [Header("References")]
    [Tooltip("Auto-found if left empty")]
    public ParticleManager particleManager;
    [Tooltip("Auto-found if left empty")]
    public ScreenBounds    screenBounds;

    [Header("Gesture")]
    public string targetGesture       = "side_to_side";

    [Tooltip("Gap in seconds between the two hits")]
    public float timeBetweenHits      = 0.4f;

    [Tooltip("Move to a second random position for the second hit")]
    public bool  moveOnSecondHit      = true;

    [Tooltip("Minimum seconds before the gesture can trigger again")]
    public float cooldownSeconds      = 1.5f;

    // ── Cached original values per system ────────────────────────────────
    private struct SystemDefaults
    {
        public float sizeMin;
        public float sizeMax;
        public float speedMin;
        public float speedMax;
        public int   burstCount;   // -1 if no burst slot exists
    }

    private ParticleSystem[]    _allSystems;
    private SystemDefaults[]    _defaults;
    private Light               _pointLight;   // the Point Light child

    private float _lastTriggerTime = -999f;
    private bool  _isFiring        = false;

    // ── Unity lifecycle ───────────────────────────────────────────────────
    void Awake()
    {
        _allSystems = GetComponentsInChildren<ParticleSystem>(includeInactive: true);
        _defaults   = new SystemDefaults[_allSystems.Length];

        for (int i = 0; i < _allSystems.Length; i++)
        {
            var ps   = _allSystems[i];
            var main = ps.main;

            // Disable looping so each Play() fires exactly one burst cycle
            main.loop = false;

            // Cache the Inspector-set values BEFORE any runtime changes
            _defaults[i] = new SystemDefaults
            {
                sizeMin    = main.startSize.constantMin,
                sizeMax    = main.startSize.constantMax,
                speedMin   = main.startSpeed.constantMin,
                speedMax   = main.startSpeed.constantMax,
                burstCount = ps.emission.burstCount > 0
                    ? (int)ps.emission.GetBurst(0).count.constant
                    : -1
            };

            // Stop any auto-play
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        }

        // Find the Point Light child and disable it until a burst fires
        _pointLight = GetComponentInChildren<Light>(includeInactive: true);
        if (_pointLight != null)
            _pointLight.enabled = false;
        else
            Debug.LogWarning("[SideToSideHitController] No Point Light found in children.");

        if (particleManager == null)
            particleManager = FindFirstObjectByType<ParticleManager>();
        if (screenBounds == null)
            screenBounds = FindFirstObjectByType<ScreenBounds>();
    }

    void Start()
    {
        if (particleManager != null)
        {
            foreach (var ps in _allSystems)
                particleManager.RegisterParticleSystem(ps);
        }
        else
        {
            Debug.LogWarning("[SideToSideHitController] No ParticleManager found.");
        }
    }

    void OnEnable()  => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName != targetGesture) return;
        if (_isFiring) return;
        if (Time.time - _lastTriggerTime < cooldownSeconds) return;

        _lastTriggerTime = Time.time;
        StartCoroutine(FireDoubleHit(p));
    }

    // ── Double-hit coroutine ──────────────────────────────────────────────
    private IEnumerator FireDoubleHit(OSCReceiver.Prediction p)
    {
        _isFiring = true;

        // Hit 1
        MoveToRandomPosition();
        ApplyOSCData(p);
        if (_pointLight != null) _pointLight.enabled = true;
        PlayAll();

        yield return new WaitForSeconds(timeBetweenHits);

        // Disable light briefly between the two hits so the glow clears
        if (_pointLight != null) _pointLight.enabled = false;
        ClearAll();

        // Hit 2
        if (moveOnSecondHit)
            MoveToRandomPosition();

        ApplyOSCData(p);
        if (_pointLight != null) _pointLight.enabled = true;
        PlayAll();

        // Wait for particles to die (max lifetime ~0.7s + buffer)
        yield return new WaitForSeconds(1f);

        // Clean up — disable light and clear any lingering particles
        if (_pointLight != null) _pointLight.enabled = false;
        ClearAll();

        _isFiring = false;
    }

    // ── Helpers ───────────────────────────────────────────────────────────
    private void PlayAll()
    {
        foreach (var ps in _allSystems)
            ps.Play(withChildren: false);
    }

    private void ClearAll()
    {
        foreach (var ps in _allSystems)
            ps.Clear();
    }

    /// <summary>
    /// Scales particle properties from CACHED originals — never from current
    /// runtime values, so repeated calls cannot compound.
    /// </summary>
    private void ApplyOSCData(OSCReceiver.Prediction p)
    {
        float sizeScale  = Mathf.Lerp(0.5f, 2f,  p.brushSize);
        float speedScale = Mathf.Lerp(0.5f, 2f,  p.particleSpeed);
        float burstScale = Mathf.Lerp(0.3f, 1f,  p.confidence);

        for (int i = 0; i < _allSystems.Length; i++)
        {
            var ps   = _allSystems[i];
            var main = ps.main;
            var d    = _defaults[i];

            // Scale from the cached Inspector values, not the current runtime values
            main.startSize = new ParticleSystem.MinMaxCurve(
                d.sizeMin * sizeScale,
                d.sizeMax * sizeScale);

            main.startSpeed = new ParticleSystem.MinMaxCurve(
                d.speedMin * speedScale,
                d.speedMax * speedScale);

            // Only touch burst count on systems that actually have a burst
            if (d.burstCount > 0)
            {
                var emission = ps.emission;
                var burst    = emission.GetBurst(0);
                burst.count  = new ParticleSystem.MinMaxCurve(
                    Mathf.Max(1f, d.burstCount * burstScale));
                emission.SetBurst(0, burst);
            }
        }
    }

    private void MoveToRandomPosition()
    {
        Vector3 pos = screenBounds != null
            ? screenBounds.GetRandomPosition()
            : new Vector3(Random.Range(-7f, 7f), Random.Range(-4f, 4f), 0f);

        pos.z = transform.position.z;
        transform.position = pos;
    }
}
