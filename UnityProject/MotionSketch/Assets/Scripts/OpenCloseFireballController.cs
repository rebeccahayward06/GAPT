using System.Collections;
using UnityEngine;

/// <summary>
/// Attach to "OpenClose_left" or "OpenClose_right" parent GameObject.
///
/// Instead of relying on particle startSpeed (which trails can't follow),
/// the entire GameObject moves across the screen each activation.
/// Child trail systems move with it automatically.
///
/// Gesture names are derived automatically from isRightArm:
///   Left  arm → openclose_big_left  / openclose_small_left  → X = -8, moves right
///   Right arm → openclose_big_right / openclose_small_right → X =  8, moves left
///
/// OSC mapping:
///   brush_size     → particle size + HDR intensity
///   particle_speed → travel speed across screen
///   blur_amount    → how long it travels (lifetime)
///   confidence     → HDR bloom intensity
///   color_shift    → GetLeftArmColor() or GetRightArmColor()
/// </summary>
[RequireComponent(typeof(ParticleSystem))]
public class OpenCloseFireballController : MonoBehaviour
{
    [Header("References")]
    [Tooltip("Auto-found if left empty")]
    public ParticleManager particleManager;
    [Tooltip("Auto-found if left empty")]
    public ScreenBounds screenBounds;

    [Header("Arm Side")]
    [Tooltip("Off = left arm (cold, spawns at X = -8, moves right).\nOn = right arm (warm, spawns at X = 8, moves left).")]
    public bool isRightArm = false;

    [Header("Spawn")]
    public float leftArmX = -8f;
    public float rightArmX = 8f;

    [Header("OSC Ranges")]
    public Vector2 speedRange = new Vector2(2f, 8f);
    public Vector2 sizeRange = new Vector2(0.5f, 3f);
    public Vector2 lifetimeRange = new Vector2(3f, 8f);

    [Header("Shader Colour")]
    [Tooltip("HDR colour property name in the fireball shader")]
    public string shaderColorProperty = "_Color";
    [Tooltip("HDR intensity multiplier range driven by confidence")]
    public Vector2 hdrIntensityRange = new Vector2(1f, 4f);

    [Tooltip("Minimum seconds before the gesture can re-trigger")]
    public float cooldownSeconds = 1f;

    // ── Private ───────────────────────────────────────────────────────────
    private ParticleSystem[] _allSystems;
    private ParticleSystem.MainModule _main;
    private Renderer[] _renderers;
    private TrailRenderer[] _trails;
    private MaterialPropertyBlock _mpb;

    // Gesture names derived from isRightArm so no manual Inspector entry needed
    private string _gesture;

    private float _lastTriggerTime = -999f;
    private bool _isFiring = false;

    // ── Unity lifecycle ───────────────────────────────────────────────────
    void Awake()
    {
        _allSystems = GetComponentsInChildren<ParticleSystem>(includeInactive: true);
        _main = GetComponent<ParticleSystem>().main;
        _renderers = GetComponentsInChildren<Renderer>(includeInactive: true);
        _trails = GetComponentsInChildren<TrailRenderer>(includeInactive: true);
        _mpb = new MaterialPropertyBlock();

        foreach (var ps in _allSystems)
        {
            var m = ps.main;
            m.loop = false;
            m.startSpeed = 0f;
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        }
        foreach (var tr in _trails)
        {
            tr.emitting = false;
            tr.Clear();
        }

        if (particleManager == null)
            particleManager = FindFirstObjectByType<ParticleManager>();
        if (screenBounds == null)
            screenBounds = FindFirstObjectByType<ScreenBounds>();
    }

    void Start()
    {
        // Derived here not in Awake — Inspector values are guaranteed applied by Start
        
        string side = isRightArm ? "right" : "left";
        _gesture = $"openclose_{side}";   // size is continuous now, not in the label

        if (particleManager != null)
            foreach (var ps in _allSystems)
                particleManager.RegisterParticleSystem(ps);
        else
            Debug.LogWarning("[OpenCloseFireballController] No ParticleManager found.");
    }

    void OnEnable() => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName != _gesture) return;
        if (_isFiring) return;
        if (Time.time - _lastTriggerTime < cooldownSeconds) return;

        _lastTriggerTime = Time.time;
        StartCoroutine(FireProjectile(p));
    }

    // ── Coroutine ─────────────────────────────────────────────────────────
    private IEnumerator FireProjectile(OSCReceiver.Prediction p)
    {
        _isFiring = true;

        // ── Map OSC values ────────────────────────────────────────────────
        float speed = Mathf.Lerp(speedRange.x, speedRange.y, p.particleSpeed);
        float size = Mathf.Lerp(sizeRange.x, sizeRange.y, p.brushSize);
        float lifetime = Mathf.Lerp(lifetimeRange.x, lifetimeRange.y, p.blurAmount);

        // ── Clear first and disable trails before teleporting ─────────────
        foreach (var ps in _allSystems)
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        foreach (var tr in _trails)
        {
            tr.emitting = false;
            tr.Clear();
        }

        yield return null; // flush before moving

        // ── Spawn position ────────────────────────────────────────────────
        float spawnX = isRightArm ? rightArmX : leftArmX;
        float spawnY = screenBounds != null
            ? screenBounds.GetRandomPosition().y
            : Random.Range(-4f, 4f);
        transform.position = new Vector3(spawnX, spawnY, transform.position.z);

        yield return null; // settle at new position before trails re-enable

        foreach (var tr in _trails)
            tr.emitting = true;

        // ── Rotation — face inward ────────────────────────────────────────
        // Left fires rightward (0, 90, 0), right fires leftward (0, -90, 0)
        transform.rotation = isRightArm
            ? Quaternion.Euler(0f, -90f, 0f)
            : Quaternion.Euler(0f, 90f, 0f);

        // ── Particle size ─────────────────────────────────────────────────
        _main.startSize = size;

        // ── Shader colour via MaterialPropertyBlock ───────────────────────
        Color baseColor = particleManager != null
            ? (isRightArm
                ? particleManager.GetRightArmColor(p.colorShift)
                : particleManager.GetLeftArmColor(p.colorShift))
            : (isRightArm ? Color.red : Color.cyan);

        float intensity = Mathf.Lerp(hdrIntensityRange.x, hdrIntensityRange.y, p.confidence);
        Color hdrColor = baseColor * intensity;

        foreach (var r in _renderers)
        {
            r.GetPropertyBlock(_mpb);
            _mpb.SetColor(shaderColorProperty, hdrColor);
            r.SetPropertyBlock(_mpb);
        }
        _main.startColor = baseColor;

        // ── Play all systems from spawn position ──────────────────────────
        foreach (var ps in _allSystems)
            ps.Play();

        // ── Move the entire GameObject across the screen ──────────────────
        // Direction: left arm moves right (+X), right arm moves left (-X)
        float direction = isRightArm ? -1f : 1f;
        float elapsed = 0f;

        while (elapsed < lifetime)
        {
            transform.position += new Vector3(direction * speed * Time.deltaTime, 0f, 0f);
            elapsed += Time.deltaTime;
            yield return null;
        }

        // ── Stop and clear ────────────────────────────────────────────────
        foreach (var ps in _allSystems)
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        foreach (var tr in _trails)
        {
            tr.emitting = false;
            tr.Clear();
        }

        _isFiring = false;
    }
}