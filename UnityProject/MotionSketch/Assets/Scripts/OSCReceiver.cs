using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Parses the hand-rolled OSC messages sent by complete_mock_osc.py
/// Format: /motionsketch/prediction  ,sffffff
///         gesture_name, confidence, brush_size, particle_speed,
///         line_curvature, blur_amount, color_shift
///
/// Attach to any persistent GameObject (e.g. a GameManager).
/// Other scripts subscribe via OSCReceiver.OnPrediction.
/// </summary>
public class OSCReceiver : MonoBehaviour
{
    [Header("Network")]
    [Tooltip("Must match UNITY_PORT in the Python script")]
    public int listenPort = 9000;

    // ── Public event ────────────────────────────────────────────────────────
    public struct Prediction
    {
        public string gestureName;
        public float  confidence;
        public float  brushSize;
        public float  particleSpeed;
        public float  lineCurvature;
        public float  blurAmount;
        public float  colorShift;
    }

    public static event Action<Prediction> OnPrediction;

    // ── Private ──────────────────────────────────────────────────────────────
    private UdpClient       _udp;
    private Thread          _thread;
    private volatile bool   _running;

    // Thread-safe queue so we dispatch events on the main thread
    private readonly Queue<Prediction> _queue = new Queue<Prediction>();
    private readonly object            _lock  = new object();

    // ── Unity lifecycle ──────────────────────────────────────────────────────
    void Start()
    {
        _udp     = new UdpClient(listenPort);
        _running = true;
        _thread  = new Thread(ReceiveLoop) { IsBackground = true };
        _thread.Start();
        Debug.Log($"[OSCReceiver] Listening on UDP port {listenPort}");
    }

    void Update()
    {
        // Drain the queue on the main thread so Unity API calls are safe
        lock (_lock)
        {
            while (_queue.Count > 0)
            {
                var p = _queue.Dequeue();
                OnPrediction?.Invoke(p);
            }
        }
    }

    void OnDestroy()
    {
        _running = false;
        _udp?.Close();
        _thread?.Join(500);
    }

    // ── Background receive loop ──────────────────────────────────────────────
    private void ReceiveLoop()
    {
        var remote = new IPEndPoint(IPAddress.Any, 0);
        while (_running)
        {
            try
            {
                byte[] data = _udp.Receive(ref remote);
                if (TryParse(data, out Prediction p))
                {
                    lock (_lock) { _queue.Enqueue(p); }
                }
            }
            catch (SocketException) { /* socket closed on shutdown */ }
            catch (Exception e)     { Debug.LogWarning($"[OSCReceiver] {e.Message}"); }
        }
    }

    // ── OSC parser ───────────────────────────────────────────────────────────
    // Matches the hand-rolled format in complete_mock_osc.py:
    //   osc_string(address) + osc_string(",sfffff") + osc_string(gesture) + 6 × osc_float
    private static bool TryParse(byte[] data, out Prediction result)
    {
        result = default;
        int pos = 0;

        // 1. Address string (we don't validate it here)
        if (!ReadOscString(data, ref pos, out _)) return false;

        // 2. Type-tag string  → should be ",sfffff"
        if (!ReadOscString(data, ref pos, out string typetag)) return false;
        if (typetag != ",sffffff")
        {
            Debug.LogWarning($"[OSCReceiver] Unexpected type-tag: '{typetag}' (expected ',sffffff')");
            return false;
        }

        // 3. Gesture name (string argument)
        if (!ReadOscString(data, ref pos, out string gestureName)) return false;

        // 4. Six floats (big-endian)
        if (!ReadOscFloat(data, ref pos, out float confidence))    return false;
        if (!ReadOscFloat(data, ref pos, out float brushSize))     return false;
        if (!ReadOscFloat(data, ref pos, out float particleSpeed)) return false;
        if (!ReadOscFloat(data, ref pos, out float lineCurvature)) return false;
        if (!ReadOscFloat(data, ref pos, out float blurAmount))    return false;
        if (!ReadOscFloat(data, ref pos, out float colorShift))    return false;

        result = new Prediction
        {
            gestureName   = gestureName,
            confidence    = confidence,
            brushSize     = brushSize,
            particleSpeed = particleSpeed,
            lineCurvature = lineCurvature,
            blurAmount    = blurAmount,
            colorShift    = colorShift
        };
        return true;
    }

    /// <summary>Read a null-terminated, 4-byte-padded OSC string.</summary>
    private static bool ReadOscString(byte[] data, ref int pos, out string value)
    {
        value = null;
        if (pos >= data.Length) return false;

        int start = pos;
        while (pos < data.Length && data[pos] != 0) pos++;
        value = Encoding.UTF8.GetString(data, start, pos - start);

        // Skip null terminator + padding to next 4-byte boundary
        pos++;                              // past the null
        int rem = pos % 4;
        if (rem != 0) pos += 4 - rem;      // pad

        return true;
    }

    /// <summary>Read a big-endian IEEE 754 float.</summary>
    private static bool ReadOscFloat(byte[] data, ref int pos, out float value)
    {
        value = 0f;
        if (pos + 4 > data.Length) return false;

        // Reverse bytes for little-endian CPU
        byte[] b = { data[pos+3], data[pos+2], data[pos+1], data[pos] };
        value = BitConverter.ToSingle(b, 0);
        pos += 4;
        return true;
    }
}
