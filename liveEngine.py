"""
liveEngine.py  -  3-sensor live inference for MotionSketch.

Three Movella DOT sensors stream simultaneously:
  - left wrist  -> wrist_model, output gesture gets "_left"
  - right wrist -> wrist_model, output gesture gets "_right"
  - hips        -> hip_model,   output gesture as-is

Side is assigned from WHICH sensor reports (not classified).
Size and speed are sent as continuous values (not classified).

Run train_regions.py first to produce models/wrist_model.joblib and
models/hip_model.joblib. Make sure THIS folder's Features.py is identical
to the one train_regions.py used.
"""

import asyncio
import struct
import collections
from collections import Counter

import numpy as np
import joblib
from bleak import BleakClient
from pythonosc import udp_client

from Features import extract_features, WINDOW_SIZE, STEP_SIZE

# ============================================================
# CONFIG  -  FILL IN the two missing addresses (use scanner.py)
# ============================================================
SENSORS = {
    "left":  "D4:22:CD:00:61:3A",
    "right": "D4:22:CD:00:60:F0",
    "hip":   "D4:22:CD:00:61:4B",
}
# which model each sensor uses
ROLE = {"left": "wrist", "right": "wrist", "hip": "hip"}

UNITY_IP = "127.0.0.1"
UNITY_PORT = 9000
OSC_PATH = "/motionsketch/prediction"

CONTROL_UUID = "15172001-4947-11e9-8646-d663bd873d93"
UUID_MEDIUM = "15172003-4947-11e9-8646-d663bd873d93"
PAYLOAD_CUSTOM_MODE_1 = 0x16        # verified earlier for your firmware

CONF_THRESHOLD = 0.50
VOTE_WINDOW = 5
VOTE_AGREE = 3

IDLE_MOTION = 5   # TUNE THIS. Below it = "not moving".

# ---- load both models once, shared across sensors ----
MODELS = {
    "wrist": (joblib.load("models/wrist_model.joblib"),
              joblib.load("models/wrist_encoder.joblib")),
    "hip":   (joblib.load("models/hip_model.joblib"),
              joblib.load("models/hip_encoder.joblib")),
}
print(f"[Engine] wrist classes: {list(MODELS['wrist'][1].classes_)}")
print(f"[Engine] hip classes:   {list(MODELS['hip'][1].classes_)}")


def parse_payload(data):
    """Custom Mode 1: ts(4) Euler(12) FreeAcc(12) Gyr(12). We use FreeAcc + Gyr."""
    if len(data) < 40:
        return None
    try:
        free_acc = struct.unpack("<fff", data[16:28])
        gyr = struct.unpack("<fff", data[28:40])
        result = np.array(free_acc + gyr)          # 6 channels, matches training
        if np.any(np.isnan(result)) or np.any(np.abs(result) > 1e6):
            return None
        return result
    except Exception:
        return None


class SensorPipeline:
    """One independent inference pipeline per physical sensor."""

    def __init__(self, side, osc):
        self.side = side
        self.role = ROLE[side]
        self.model, self.le = MODELS[self.role]
        self.osc = osc

        self.smooth = collections.deque(maxlen=5)          # matches training rolling(5)
        self.window = collections.deque(maxlen=WINDOW_SIZE)
        self.votes = collections.deque(maxlen=VOTE_WINDOW)
        self.counter = 0
        self.last_sent = None
        self.packets = 0

    def on_data(self, _, data):
        raw = parse_payload(data)
        if raw is None:
            return
        self.packets += 1
        self.smooth.append(raw)
        self.window.append(np.mean(self.smooth, axis=0))
        self.counter += 1
        if len(self.window) == WINDOW_SIZE and self.counter % STEP_SIZE == 0:
            self.infer()

    def infer(self):
        w = np.array(self.window)
        if np.any(np.isnan(w)) or np.any(np.isinf(w)):
            return

        motion = float(np.mean(np.std(w, axis=0)))
        acc = w[:, 0:3]
        gyr = w[:, 3:6]
        size  = float(min(np.mean(np.linalg.norm(acc, axis=1)) / 10.0, 1.0))
        speed = float(min(np.mean(np.linalg.norm(gyr, axis=1)) / 50.0, 1.0))

        if motion < IDLE_MOTION:
            if self.last_sent != "idle":
                self.osc.send_message(OSC_PATH, ["idle", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
                print(f"[ {self.side}] idle (motion={motion:.2f})")
                self.last_sent = "idle"
            self.votes.clear()
            return

        feats = extract_features(w).reshape(1, -1)
        prob = self.model.predict_proba(feats)[0]
        idx = int(np.argmax(prob))
        conf = float(prob[idx])
        gesture = self.le.inverse_transform([idx])[0]

        if conf < CONF_THRESHOLD:
            return
        self.votes.append(gesture)
        if len(self.votes) < VOTE_WINDOW:
            return
        top, count = Counter(self.votes).most_common(1)[0]
        if count < VOTE_AGREE:
            return

        label = f"{top}_{self.side}" if self.role == "wrist" else top

        brush_size     = size
        particle_speed = speed
        jerk = float(np.mean(np.abs(np.diff(acc, axis=0, n=2))))
        line_curvature = max(0.0, 1.0 - min(jerk / 5.0, 1.0))
        blur_amount    = line_curvature * 0.8
        color_shift    = float(abs(np.mean(gyr[:, 2])) % 1.0)

        self.osc.send_message(OSC_PATH, [
            label, float(conf), float(brush_size), float(particle_speed),
            float(line_curvature), float(blur_amount), float(color_shift),
        ])
        self.last_sent = top
        print(f"[ {self.side}] {label:<24} conf={conf:.0%} "
              f"brush={brush_size:.2f} speed={particle_speed:.2f}")


async def run_sensor(side, address, osc, start_delay=0.0):
    await asyncio.sleep(start_delay)                 # stagger so connects don't collide
    pipe = SensorPipeline(side, osc)
    for attempt in range(5):
        try:
            async with BleakClient(address, timeout=20.0) as client:
                await client.start_notify(UUID_MEDIUM, pipe.on_data)
                await asyncio.sleep(0.5)
                await client.write_gatt_char(
                    CONTROL_UUID,
                    bytearray([0x01, 0x01, PAYLOAD_CUSTOM_MODE_1]),
                    response=True,
                )
                print(f"[{side}] streaming, using '{pipe.role}' model")
                while True:
                    await asyncio.sleep(1.0)
        except Exception as e:
            print(f"[{side}] attempt {attempt+1}/5 failed: {e} — retrying in 4s")
            await asyncio.sleep(4.0)
    print(f"[{side}] gave up after 5 attempts.")


async def main():
    osc = udp_client.SimpleUDPClient(UNITY_IP, UNITY_PORT)
    print(f"[OSC] sending to {UNITY_IP}:{UNITY_PORT} {OSC_PATH}")
    await asyncio.gather(
        *[run_sensor(side, addr, osc, start_delay=i * 4.0)
          for i, (side, addr) in enumerate(SENSORS.items())],
        return_exceptions=True,        # one sensor dying no longer kills the others
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[System] live engine offline.")
