#!/usr/bin/env python3
"""
Complete mock OSC sender — UPDATED to match the live engine label space.

Live label space emitted here:
  circle_left/right, openclose_left/right, updown_left/right,
  punching_fast_left/right, punching_slow_left/right,
  whipping_left/right, hip_rotation_both, hip_thrust, side_to_side

OSC contract (unchanged): type tag ",sffffff"
  gestureName, confidence, brush_size, particle_speed,
  line_curvature, blur_amount, color_shift

NO DEPENDENCIES NEEDED - uses only Python built-in libraries
"""

import socket
import struct
import time
import math
import random

# Unity OSC receiver settings
UNITY_IP    = "127.0.0.1"
UNITY_PORT  = 9000
OSC_ADDRESS = "/motionsketch/prediction"

def osc_string(s):
    s = s.encode('utf-8') + b'\x00'
    return s + b'\x00' * (4 - len(s) % 4)

def osc_float(f):
    return struct.pack('>f', f)

def build_osc_message(address, values):
    msg = osc_string(address)
    types = ','
    for v in values:
        types += 's' if isinstance(v, str) else 'f'
    msg += osc_string(types)
    for v in values:
        msg += osc_string(v) if isinstance(v, str) else osc_float(v)
    return msg

# ── Gesture parameter ranges ───────────────────────────────────────────────────
# Names now match the LIVE engine (side reattached, no big/small).
# brush_size and particle_speed are deliberately given a WIDE range so the mock
# exercises Unity's size/speed lerps. Use the sweep modes to test them cleanly.

GESTURES = {

    # ── ARM: CIRCLES ───────────────────────────────────────────────────────────
    "circle_left": {
        "confidence":     (0.80, 0.95),
        "brush_size":     (0.25, 0.85),   # spans small -> big
        "particle_speed": (0.50, 0.80),
        "line_curvature": (0.70, 1.00),
        "blur_amount":    (0.60, 0.90),
        "color_shift":    (0.30, 0.70),
    },

    # ── ARM: OPEN / CLOSE ───────────────────────────────────────────────────────
    "openclose_left": {
        "confidence":     (0.70, 0.90),
        "brush_size":     (0.25, 0.90),
        "particle_speed": (0.40, 0.80),
        "line_curvature": (0.20, 0.50),
        "blur_amount":    (0.70, 1.00),
        "color_shift":    (0.20, 0.80),
    },

    # ── ARM: UP / DOWN ──────────────────────────────────────────────────────────
    "updown_left": {
        "confidence":     (0.70, 0.90),
        "brush_size":     (0.25, 0.90),
        "particle_speed": (0.40, 0.80),
        "line_curvature": (0.30, 0.60),
        "blur_amount":    (0.70, 1.00),
        "color_shift":    (0.20, 0.80),
    },

    # ── ARM: PUNCHING (speed kept as a class) ────────────────────────────────────
    "punching_fast_left": {
        "confidence":     (0.85, 0.95),
        "brush_size":     (0.70, 0.95),
        "particle_speed": (0.80, 1.00),
        "line_curvature": (0.00, 0.20),
        "blur_amount":    (0.00, 0.20),
        "color_shift":    (0.10, 0.30),
    },
    "punching_slow_left": {
        "confidence":     (0.80, 0.92),
        "brush_size":     (0.50, 0.80),
        "particle_speed": (0.20, 0.40),
        "line_curvature": (0.00, 0.15),
        "blur_amount":    (0.60, 0.90),
        "color_shift":    (0.20, 0.50),
    },

    # ── ARM: WHIPPING (reset — clears canvas; sided to match live) ───────────────
    "whipping_left": {
        "confidence":     (0.80, 0.92),
        "brush_size":     (0.50, 0.80),
        "particle_speed": (0.90, 1.00),
        "line_curvature": (0.10, 0.30),
        "blur_amount":    (0.00, 0.15),
        "color_shift":    (0.40, 0.90),
    },

    # ── HIP MOTIONS (no side) ────────────────────────────────────────────────────
    "hip_rotation_both": {
        "confidence":     (0.70, 0.88),
        "brush_size":     (0.40, 0.70),
        "particle_speed": (0.30, 0.60),
        "line_curvature": (0.80, 1.00),
        "blur_amount":    (0.80, 1.00),
        "color_shift":    (0.50, 1.00),
    },
    "hip_thrust": {
        "confidence":     (0.70, 0.85),
        "brush_size":     (0.50, 0.80),
        "particle_speed": (0.40, 0.70),
        "line_curvature": (0.20, 0.40),
        "blur_amount":    (0.70, 0.95),
        "color_shift":    (0.30, 0.70),
    },
    "side_to_side": {
        "confidence":     (0.70, 0.85),
        "brush_size":     (0.50, 0.80),
        "particle_speed": (0.40, 0.70),
        "line_curvature": (0.30, 0.50),
        "blur_amount":    (0.70, 0.95),
        "color_shift":    (0.30, 0.70),
    },
}

# Arm gestures get a _right twin generated automatically (same ranges).
def _add_right_twins(gestures):
    out = {}
    for name, params in gestures.items():
        out[name] = params
        if name.endswith("_left"):
            out[name[:-5] + "_right"] = params
    return out

GESTURES = _add_right_twins(GESTURES)

# ── Grouped menu (left/right both listed) ────────────────────────────────────────
MENU = [
    ("CIRCLES",      ["circle_left", "circle_right"]),
    ("OPEN / CLOSE", ["openclose_left", "openclose_right"]),
    ("UP / DOWN",    ["updown_left", "updown_right"]),
    ("PUNCHING",     ["punching_fast_left", "punching_fast_right",
                      "punching_slow_left", "punching_slow_right"]),
    ("RESET",        ["whipping_left", "whipping_right"]),
    ("HIP MOTIONS",  ["hip_rotation_both", "hip_thrust", "side_to_side"]),
]

def generate_values(gesture_name, brush_override=None, speed_override=None):
    """Build the 7-value OSC payload. Optional overrides let the sweep modes
    drive brush_size / particle_speed smoothly instead of randomly."""
    p = GESTURES[gesture_name]
    brush = brush_override if brush_override is not None else random.uniform(*p["brush_size"])
    speed = speed_override if speed_override is not None else random.uniform(*p["particle_speed"])
    return [
        gesture_name,
        random.uniform(*p["confidence"]),
        float(brush),
        float(speed),
        random.uniform(*p["line_curvature"]),
        random.uniform(*p["blur_amount"]),
        random.uniform(*p["color_shift"]),
    ]

def send_prediction(sock, values):
    msg = build_osc_message(OSC_ADDRESS, values)
    sock.sendto(msg, (UNITY_IP, UNITY_PORT))
    print(f"Sent: {values[0]:22s} | conf:{values[1]:.2f} | "
          f"brush:{values[2]:.2f} | speed:{values[3]:.2f}")

def print_menu():
    print("=" * 70)
    print("Motion Sketch Mock OSC Sender  (live-label compatible)")
    print("=" * 70)
    print(f"Sending to {UNITY_IP}:{UNITY_PORT}{OSC_ADDRESS}")
    print("Rate: every 0.5 s\n")

    index   = 1
    ordered = []
    for group_name, gestures in MENU:
        print(f"{group_name}:")
        for g in gestures:
            print(f"  {index:2d}. {g}")
            ordered.append(g)
            index += 1
        print()

    print("SPECIAL:")
    print(f"  {index}. Cycle through ALL gestures")
    print(f"  {index+1}. Random gestures")
    print(f"  {index+2}. SIZE sweep  (hold one gesture, brush_size ramps 0->1->0)")
    print(f"  {index+3}. SPEED sweep (hold one gesture, particle_speed ramps 0->1->0)")
    return ordered

def _pick_gesture(ordered):
    g = input("Which gesture number? ")
    try:
        n = int(g)
        if 1 <= n <= len(ordered):
            return ordered[n - 1]
    except ValueError:
        pass
    print("Invalid, defaulting to circle_left.")
    return "circle_left"

def _sweep_value(period=4.0):
    """Smooth 0->1->0 oscillation, one full cycle every `period` seconds."""
    return 0.5 * (1 - math.cos(2 * math.pi * (time.time() % period) / period))

def main():
    ordered = print_menu()
    total   = len(ordered)

    choice = input("\nSelect number: ")
    try:
        choice_num = int(choice)
    except ValueError:
        print("Invalid choice.")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        if 1 <= choice_num <= total:
            gesture = ordered[choice_num - 1]
            print(f"\nSending '{gesture}' continuously...  (Ctrl+C to stop)\n")
            while True:
                send_prediction(sock, generate_values(gesture))
                time.sleep(0.5)

        elif choice_num == total + 1:
            print("\nCycling through all gestures (5 s each)...  (Ctrl+C to stop)\n")
            while True:
                for gesture in ordered:
                    print(f"\n>>> Now sending: {gesture}")
                    for _ in range(10):
                        send_prediction(sock, generate_values(gesture))
                        time.sleep(0.5)

        elif choice_num == total + 2:
            secs_in = input("Seconds per gesture? (e.g. 5): ")
            try:
                secs = float(secs_in)
            except ValueError:
                secs = 5.0
            print(f"\nRandom gestures ({secs}s each)...  (Ctrl+C to stop)\n")
            while True:
                gesture = random.choice(ordered)
                print(f"\n>>> Now sending: {gesture}")
                end = time.time() + secs
                while time.time() < end:
                    send_prediction(sock, generate_values(gesture))
                    time.sleep(0.5)

        elif choice_num == total + 3:
            gesture = _pick_gesture(ordered)
            print(f"\nSIZE sweep on '{gesture}' — watch the brush size in Unity.  (Ctrl+C to stop)\n")
            while True:
                send_prediction(sock, generate_values(gesture, brush_override=_sweep_value()))
                time.sleep(0.1)   # faster rate so the sweep looks smooth

        elif choice_num == total + 4:
            gesture = _pick_gesture(ordered)
            print(f"\nSPEED sweep on '{gesture}' — watch the particle speed in Unity.  (Ctrl+C to stop)\n")
            while True:
                send_prediction(sock, generate_values(gesture, speed_override=_sweep_value()))
                time.sleep(0.1)

        else:
            print("Invalid choice.")

    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()