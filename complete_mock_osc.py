#!/usr/bin/env python3
"""
Complete mock OSC sender for all gestures with LEFT/RIGHT arm distinction.
NO DEPENDENCIES NEEDED - uses only Python built-in libraries
"""

import socket
import struct
import time
import random

# Unity OSC receiver settings
UNITY_IP = "127.0.0.1"
UNITY_PORT = 9000
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
# Arm gestures are duplicated with _left / _right suffix.
# Hip gestures have no side distinction.

GESTURES = {

    # ── CIRCLES ───────────────────────────────────────────────────────────────
    "circle_big_left": {
        "confidence":     (0.8,  0.95),
        "brush_size":     (0.6,  0.9),
        "particle_speed": (0.5,  0.8),
        "line_curvature": (0.7,  1.0),
        "blur_amount":    (0.6,  0.9),
        "color_shift":    (0.3,  0.7),
    },
    "circle_big_right": {
        "confidence":     (0.8,  0.95),
        "brush_size":     (0.6,  0.9),
        "particle_speed": (0.5,  0.8),
        "line_curvature": (0.7,  1.0),
        "blur_amount":    (0.6,  0.9),
        "color_shift":    (0.3,  0.7),
    },
    "circle_small_left": {
        "confidence":     (0.75, 0.9),
        "brush_size":     (0.2,  0.4),
        "particle_speed": (0.6,  0.9),
        "line_curvature": (0.7,  1.0),
        "blur_amount":    (0.7,  1.0),
        "color_shift":    (0.2,  0.8),
    },
    "circle_small_right": {
        "confidence":     (0.75, 0.9),
        "brush_size":     (0.2,  0.4),
        "particle_speed": (0.6,  0.9),
        "line_curvature": (0.7,  1.0),
        "blur_amount":    (0.7,  1.0),
        "color_shift":    (0.2,  0.8),
    },

    # ── PUNCHING ──────────────────────────────────────────────────────────────
    "punching_fast_left": {
        "confidence":     (0.85, 0.95),
        "brush_size":     (0.7,  0.95),
        "particle_speed": (0.8,  1.0),
        "line_curvature": (0.0,  0.2),
        "blur_amount":    (0.0,  0.2),
        "color_shift":    (0.1,  0.3),
    },
    "punching_fast_right": {
        "confidence":     (0.85, 0.95),
        "brush_size":     (0.7,  0.95),
        "particle_speed": (0.8,  1.0),
        "line_curvature": (0.0,  0.2),
        "blur_amount":    (0.0,  0.2),
        "color_shift":    (0.1,  0.3),
    },
    "punching_slow_left": {
        "confidence":     (0.8,  0.92),
        "brush_size":     (0.5,  0.8),
        "particle_speed": (0.2,  0.4),
        "line_curvature": (0.0,  0.15),
        "blur_amount":    (0.6,  0.9),
        "color_shift":    (0.2,  0.5),
    },
    "punching_slow_right": {
        "confidence":     (0.8,  0.92),
        "brush_size":     (0.5,  0.8),
        "particle_speed": (0.2,  0.4),
        "line_curvature": (0.0,  0.15),
        "blur_amount":    (0.6,  0.9),
        "color_shift":    (0.2,  0.5),
    },

    # ── UP / DOWN ─────────────────────────────────────────────────────────────
    "updown_big_left": {
        "confidence":     (0.75, 0.9),
        "brush_size":     (0.6,  0.9),
        "particle_speed": (0.4,  0.7),
        "line_curvature": (0.3,  0.6),
        "blur_amount":    (0.7,  1.0),
        "color_shift":    (0.3,  0.8),
    },
    "updown_big_right": {
        "confidence":     (0.75, 0.9),
        "brush_size":     (0.6,  0.9),
        "particle_speed": (0.4,  0.7),
        "line_curvature": (0.3,  0.6),
        "blur_amount":    (0.7,  1.0),
        "color_shift":    (0.3,  0.8),
    },
    "updown_small_left": {
        "confidence":     (0.7,  0.88),
        "brush_size":     (0.2,  0.4),
        "particle_speed": (0.5,  0.8),
        "line_curvature": (0.3,  0.6),
        "blur_amount":    (0.7,  0.95),
        "color_shift":    (0.2,  0.7),
    },
    "updown_small_right": {
        "confidence":     (0.7,  0.88),
        "brush_size":     (0.2,  0.4),
        "particle_speed": (0.5,  0.8),
        "line_curvature": (0.3,  0.6),
        "blur_amount":    (0.7,  0.95),
        "color_shift":    (0.2,  0.7),
    },

    # ── OPEN / CLOSE ──────────────────────────────────────────────────────────
    "openclose_big_left": {
        "confidence":     (0.75, 0.9),
        "brush_size":     (0.6,  0.95),
        "particle_speed": (0.4,  0.7),
        "line_curvature": (0.2,  0.5),
        "blur_amount":    (0.7,  1.0),
        "color_shift":    (0.3,  0.8),
    },
    "openclose_big_right": {
        "confidence":     (0.75, 0.9),
        "brush_size":     (0.6,  0.95),
        "particle_speed": (0.4,  0.7),
        "line_curvature": (0.2,  0.5),
        "blur_amount":    (0.7,  1.0),
        "color_shift":    (0.3,  0.8),
    },
    "openclose_small_left": {
        "confidence":     (0.7,  0.85),
        "brush_size":     (0.2,  0.4),
        "particle_speed": (0.5,  0.8),
        "line_curvature": (0.2,  0.5),
        "blur_amount":    (0.7,  0.95),
        "color_shift":    (0.2,  0.7),
    },
    "openclose_small_right": {
        "confidence":     (0.7,  0.85),
        "brush_size":     (0.2,  0.4),
        "particle_speed": (0.5,  0.8),
        "line_curvature": (0.2,  0.5),
        "blur_amount":    (0.7,  0.95),
        "color_shift":    (0.2,  0.7),
    },

    # ── WHIPPING (reset — no side needed, clears everything) ──────────────────
    "whipping": {
        "confidence":     (0.8,  0.92),
        "brush_size":     (0.5,  0.8),
        "particle_speed": (0.9,  1.0),
        "line_curvature": (0.1,  0.3),
        "blur_amount":    (0.0,  0.15),
        "color_shift":    (0.4,  0.9),
    },

    # ── HIP MOTIONS ───────────────────────────────────────────────────────────
    "hip_rotation_both": {
        "confidence":     (0.7,  0.88),
        "brush_size":     (0.4,  0.7),
        "particle_speed": (0.3,  0.6),
        "line_curvature": (0.8,  1.0),
        "blur_amount":    (0.8,  1.0),
        "color_shift":    (0.5,  1.0),
    },
    "hip_thrust": {
        "confidence":     (0.7,  0.85),
        "brush_size":     (0.5,  0.8),
        "particle_speed": (0.4,  0.7),
        "line_curvature": (0.2,  0.4),
        "blur_amount":    (0.7,  0.95),
        "color_shift":    (0.3,  0.7),
    },
    "side_to_side": {
        "confidence":     (0.7,  0.85),
        "brush_size":     (0.5,  0.8),
        "particle_speed": (0.4,  0.7),
        "line_curvature": (0.3,  0.5),
        "blur_amount":    (0.7,  0.95),
        "color_shift":    (0.3,  0.7),
    },
}

# ── Grouped menu ──────────────────────────────────────────────────────────────
MENU = [
    ("CIRCLES",       ["circle_big_left",      "circle_big_right",
                       "circle_small_left",    "circle_small_right"]),
    ("PUNCHING",      ["punching_fast_left",   "punching_fast_right",
                       "punching_slow_left",   "punching_slow_right"]),
    ("UP / DOWN",     ["updown_big_left",      "updown_big_right",
                       "updown_small_left",    "updown_small_right"]),
    ("OPEN / CLOSE",  ["openclose_big_left",   "openclose_big_right",
                       "openclose_small_left", "openclose_small_right"]),
    ("RESET",         ["whipping"]),
    ("HIP MOTIONS",   ["hip_rotation_both", "hip_thrust", "side_to_side"]),
]

def generate_values(gesture_name):
    params = GESTURES[gesture_name]
    return [
        gesture_name,
        random.uniform(*params["confidence"]),
        random.uniform(*params["brush_size"]),
        random.uniform(*params["particle_speed"]),
        random.uniform(*params["line_curvature"]),
        random.uniform(*params["blur_amount"]),
        random.uniform(*params["color_shift"]),
    ]

def send_prediction(sock, values):
    msg = build_osc_message(OSC_ADDRESS, values)
    sock.sendto(msg, (UNITY_IP, UNITY_PORT))
    print(f"Sent: {values[0]:25s} | conf:{values[1]:.2f} | "
          f"brush:{values[2]:.2f} | speed:{values[3]:.2f}")

def print_menu():
    print("=" * 70)
    print("Motion Sketch Mock OSC Sender")
    print("=" * 70)
    print(f"Sending to {UNITY_IP}:{UNITY_PORT}{OSC_ADDRESS}")
    print(f"Rate: Every 0.5 seconds\n")

    index = 1
    ordered = []
    for group_name, gestures in MENU:
        print(f"{group_name}:")
        for g in gestures:
            print(f"  {index:2d}. {g}")
            ordered.append(g)
            index += 1
        print()

    print(f"  {index}. Cycle through ALL gestures")
    print(f"  {index+1}. Random gestures")
    return ordered

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
            print(f"\nSending '{gesture}' continuously...")
            print("Press Ctrl+C to stop\n")
            while True:
                send_prediction(sock, generate_values(gesture))
                time.sleep(0.5)

        elif choice_num == total + 1:
            print("\nCycling through all gestures (5 seconds each)...")
            print("Press Ctrl+C to stop\n")
            while True:
                for gesture in ordered:
                    print(f"\n>>> Now sending: {gesture}")
                    for _ in range(10):
                        send_prediction(sock, generate_values(gesture))
                        time.sleep(0.5)

        elif choice_num == total + 2:
            duration = input("Seconds per gesture? (e.g. 5): ")
            try:
                secs = float(duration)
            except ValueError:
                secs = 5.0
            print(f"\nRandom gestures ({secs}s each)... Press Ctrl+C to stop\n")
            while True:
                gesture = random.choice(ordered)
                print(f"\n>>> Now sending: {gesture}")
                end = time.time() + secs
                while time.time() < end:
                    send_prediction(sock, generate_values(gesture))
                    time.sleep(0.5)
        else:
            print("Invalid choice.")

    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()