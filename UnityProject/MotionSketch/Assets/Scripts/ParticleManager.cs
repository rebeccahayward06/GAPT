using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Central manager for all particle systems.
///   - Whipping gesture  → instant clear of all particles
///   - 10 s max lifetime → enforced on every registered system
///   - Colour palettes   → left arm = cold, right arm = warm, hip = separate
///
/// Attach to any persistent GameObject (e.g. GameManager).
/// No Inspector wiring to OSC needed — uses the static OSCReceiver.OnPrediction event.
/// </summary>
public class ParticleManager : MonoBehaviour
{
    [Header("Particle System References")]
    [SerializeField] private List<ParticleSystem> allParticleSystems = new List<ParticleSystem>();

    [Header("Lifetime Settings")]
    [SerializeField] private float maxParticleLifetime = 10f;

    [Header("Color Palettes")]
    [Tooltip("Left arm gestures  — blues, purples, cyans")]
    [SerializeField] private Gradient leftArmColdColors;
    [Tooltip("Right arm gestures — reds, oranges, yellows")]
    [SerializeField] private Gradient rightArmWarmColors;
    [Tooltip("Hip gestures       — greens, teals")]
    [SerializeField] private Gradient hipColors;

    private bool _isClearing = false;

    // ── Unity lifecycle ───────────────────────────────────────────────────
    void Start()
    {
        EnforceMaxLifetimeOnAll();
        Debug.Log($"[ParticleManager] Managing {allParticleSystems.Count} particle systems");
    }

    void OnEnable()  => OSCReceiver.OnPrediction += HandlePrediction;
    void OnDisable() => OSCReceiver.OnPrediction -= HandlePrediction;

    // ── OSC handler ───────────────────────────────────────────────────────
    private void HandlePrediction(OSCReceiver.Prediction p)
    {
        if (p.gestureName.StartsWith("whipping"))   // catches whipping_left AND whipping_right
            ClearAllParticles();
    }

    // ── Public API ────────────────────────────────────────────────────────
    public void ClearAllParticles()
    {
        if (_isClearing) return;
        _isClearing = true;

        foreach (var ps in allParticleSystems)
            if (ps != null) ps.Clear();

        Debug.Log("[ParticleManager] Whipping — all particles cleared!");
        Invoke(nameof(ResetClearingFlag), 0.1f);
    }

    /// <summary>Left arm: cold colours (blue / cyan / purple)</summary>
    public Color GetLeftArmColor(float t) =>
        leftArmColdColors != null ? leftArmColdColors.Evaluate(t) : Color.cyan;

    /// <summary>Right arm: warm colours (red / orange / yellow)</summary>
    public Color GetRightArmColor(float t) =>
        rightArmWarmColors != null ? rightArmWarmColors.Evaluate(t) : Color.red;

    /// <summary>Hip: separate palette (green / teal)</summary>
    public Color GetHipColor(float t) =>
        hipColors != null ? hipColors.Evaluate(t) : Color.green;

    /// <summary>
    /// Called by each particle controller on Start so dynamically-placed
    /// systems are still covered by whipping and lifetime enforcement.
    /// </summary>
    public void RegisterParticleSystem(ParticleSystem ps)
    {
        if (ps == null || allParticleSystems.Contains(ps)) return;

        allParticleSystems.Add(ps);
        var main = ps.main;
        main.startLifetime = maxParticleLifetime;
    }

    // ── Private helpers ───────────────────────────────────────────────────
    private void EnforceMaxLifetimeOnAll()
    {
        foreach (var ps in allParticleSystems)
        {
            if (ps == null) continue;
            var main = ps.main;
            main.startLifetime = maxParticleLifetime;
        }
    }

    private void ResetClearingFlag() => _isClearing = false;
}
