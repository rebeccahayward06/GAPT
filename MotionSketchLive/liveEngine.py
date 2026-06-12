import asyncio
import struct
import numpy as np
import joblib
import collections
import time
from bleak import BleakClient
from pythonosc import udp_client

from Features import extract_features, WINDOW_SIZE, STEP_SIZE

# ==============================================================================
# CONFIGURATION
# ==============================================================================
SENSOR_ADDRESS = "D4:22:CD:00:60:F0"
UNITY_IP = "127.0.0.1"
UNITY_PORT = 9000
OSC_PATH = "/motionsketch/prediction"

CONTROL_UUID     = "15172001-4947-11e9-8646-d663bd873d93"
UUID_ORIENTATION = "15172002-4947-11e9-8646-d663bd873d93"
UUID_MEDIUM      = "15172003-4947-11e9-8646-d663bd873d93"
UUID_COMPLETE    = "15172004-4947-11e9-8646-d663bd873d93"

PAYLOAD_CUSTOM_MODE_1 = 0x16   # VERIFY against your DOT BLE spec; run the sweep if unsure

class MotionSketchLivePipeline:
    def __init__(self):
        print("[Engine] Loading model workspace...")
        self.model = joblib.load("models/best_model.joblib")
        self.le = joblib.load("models/label_encoder.joblib")
        self.osc = udp_client.SimpleUDPClient(UNITY_IP, UNITY_PORT)
        
        self.smooth_buffer = collections.deque(maxlen=5)
        self.window_buffer = collections.deque(maxlen=WINDOW_SIZE)
        self.packet_counter = 0
        self.total_packets_received = 0
        print(f"[Engine] Ready! Target labels: {list(self.le.classes_)}")

        self.prediction_buffer = collections.deque(maxlen=5)
        self.last_sent_label = None

    def parse_payload(self, data):
            """
            Custom Mode 1 — 40 byte packet (all IEEE-754 float32):
            bytes  0- 3 : timestamp (uint32)
            bytes  4-15 : Euler X, Y, Z      (3 x float32)  -- not used by the model
            bytes 16-27 : FreeAcc X, Y, Z    (3 x float32)  -- m/s²
            bytes 28-39 : Gyr X, Y, Z        (3 x float32)  -- deg/s
            """
            if len(data) < 40:
                return None
            try:
                free_acc = struct.unpack('<fff', data[16:28])
                gyr      = struct.unpack('<fff', data[28:40])
                result   = np.array(free_acc + gyr)   # 6 channels: [FreeAcc, Gyr]
                if np.any(np.isnan(result)) or np.any(np.abs(result) > 1e6):
                    return None
                return result
            except Exception as e:
                print(f"[PARSE ERROR] {e}")
                return None

    def ble_notification_callback(self, sender, data):
        if self.total_packets_received % 60 == 0:
            print(f"\n[RAW] len={len(data)} hex={data.hex()}")
            # try the float32-Euler layout:
            ts   = struct.unpack('<I', data[0:4])[0]
            eul  = struct.unpack('<fff', data[4:16])
            facc = struct.unpack('<fff', data[16:28])
            gyr  = struct.unpack('<fff', data[28:40])
            print(f"[TEST] ts={ts} euler={np.round(eul,2)} facc={np.round(facc,3)} gyr={np.round(gyr,3)}")
            self.total_packets_received += 1

        start_time = time.perf_counter()
        self.total_packets_received += 1
        
        if self.total_packets_received % 30 == 0:
            print(f"[Live Sync] Packets Processed: {self.total_packets_received}...", end="\r")
        
        raw_signal = self.parse_payload(data)
        if raw_signal is None:
            return

        # DEBUG — remove once working
        if self.total_packets_received % 60 == 0:
            print(f"\n[DEBUG] raw_signal: {np.round(raw_signal, 4)}")

        self.smooth_buffer.append(raw_signal)
        smoothed_frame = np.mean(self.smooth_buffer, axis=0)
        self.window_buffer.append(smoothed_frame)
        
        self.packet_counter += 1
        if len(self.window_buffer) == WINDOW_SIZE and self.packet_counter % STEP_SIZE == 0:
            self.run_inference(start_time)

    def run_inference(self, start_time):
        current_window = np.array(self.window_buffer)

        if np.any(np.isnan(current_window)) or np.any(np.isinf(current_window)):
            return

        features = extract_features(current_window).reshape(1, -1)

        if np.any(np.isnan(features)) or np.any(np.isinf(features)):
            return

        probabilities = self.model.predict_proba(features)[0]
        predicted_idx = np.argmax(probabilities)
        confidence    = probabilities[predicted_idx]
        label         = self.le.inverse_transform([predicted_idx])[0]
        latency_ms    = round((time.perf_counter() - start_time) * 1000, 2)

        print(f"[raw] {label:<22} {confidence:.1%}")

        # Only accept confident predictions
        if confidence < 0.50:
            return

        # Add to majority vote buffer
        self.prediction_buffer.append(label)

        # Only fire if 3 out of last 5 predictions agree
        if len(self.prediction_buffer) == 5:
            from collections import Counter
            most_common, count = Counter(self.prediction_buffer).most_common(1)[0]
            if count >= 3 and most_common != self.last_sent_label:
                acc_magnitude = np.mean(np.linalg.norm(current_window[:, 0:3], axis=1))
                print(f"\n >> [{most_common:<22}] Confidence: {confidence:.2%} | Latency: {latency_ms}ms")
                self.osc.send_message(OSC_PATH, [most_common, float(confidence), float(acc_magnitude)])
                self.last_sent_label = most_common

async def main():
    pipeline = MotionSketchLivePipeline()
    print(f"[BLE] Initializing handshake with sensor: {SENSOR_ADDRESS}...")
    
    try:
        async with BleakClient(SENSOR_ADDRESS) as client:
            if client.is_connected:
                print("[BLE] Bluetooth connection secure.")

                # Step 1 — enable notification FIRST
                await client.start_notify(UUID_MEDIUM, pipeline.ble_notification_callback)
                print("[BLE] Notification enabled on UUID_MEDIUM.")
                await asyncio.sleep(0.5)

                # Start measurement in Custom Mode 1 (mode is the 3rd byte of the START message)
                await client.write_gatt_char(
                    CONTROL_UUID,
                    bytearray([0x01, 0x01, PAYLOAD_CUSTOM_MODE_1]),
                    response=True
                )
                print(f"[SYSTEM ONLINE] Streaming started in Custom Mode 1 (0x{PAYLOAD_CUSTOM_MODE_1:02x}). Wave the device!")

                while True:
                    await asyncio.sleep(1.0)
            else:
                print("[BLE Error] Hardware connection rejected.")
    except Exception as e:
        print(f"\n[CRITICAL BLE ERROR] Connection crashed. Reason: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[System] Live engine pipeline safely offline.")