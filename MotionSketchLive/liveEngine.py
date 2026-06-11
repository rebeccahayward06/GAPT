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

    def parse_payload(self, data):
        """
        Custom Mode 1 — 40 byte packet layout:
          bytes  0- 3 : timestamp (uint32)
          bytes  4- 9 : Euler X, Y, Z (3 x int16, scaled x0.01)
          bytes 10-11 : padding
          bytes 12-23 : FreeAcc X, Y, Z (3 x float32)
          bytes 24-35 : Gyr X, Y, Z (3 x float32)
          bytes 36-39 : status/padding
        """
        try:
            if len(data) >= 36:
                free_acc = np.array(struct.unpack('<fff', data[12:24]))
                gyr      = np.array(struct.unpack('<fff', data[24:36]))
                result   = np.concatenate([free_acc, gyr])
                # Reject if any value is NaN or unreasonably large
                if np.any(np.isnan(result)) or np.any(np.abs(result) > 1e6):
                    return None
                return result
        except Exception as e:
            print(f"[PARSE ERROR] {e}")
            return None
        return None

    def ble_notification_callback(self, sender, data):
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

        # NaN guard — skip window if any value is invalid
        if np.any(np.isnan(current_window)) or np.any(np.isinf(current_window)):
            print("[WARN] NaN/Inf in window — skipping.")
            return

        features = extract_features(current_window).reshape(1, -1)

        # Second NaN guard on features
        if np.any(np.isnan(features)) or np.any(np.isinf(features)):
            print("[WARN] NaN/Inf in features — skipping.")
            return

        probabilities = self.model.predict_proba(features)[0]
        predicted_idx = np.argmax(probabilities)
        confidence    = probabilities[predicted_idx]
        label         = self.le.inverse_transform([predicted_idx])[0]
        latency_ms    = round((time.perf_counter() - start_time) * 1000, 2)
        acc_magnitude = np.mean(np.linalg.norm(current_window[:, 0:3], axis=1))
        
        if confidence > 0.10:
            print(f"\n >> [{label:<22}] Confidence: {confidence:.2%} | Latency: {latency_ms}ms")
            self.osc.send_message(OSC_PATH, [label, float(confidence), float(acc_magnitude)])

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

                # Step 2 — set payload mode to Custom Mode 1
                await client.write_gatt_char(
                    CONTROL_UUID,
                    bytearray([0x01, 0x10, 0x01]),
                    response=True
                )
                print("[BLE] Payload mode set to Custom Mode 1.")
                await asyncio.sleep(0.3)

                # Step 3 — start streaming
                await client.write_gatt_char(
                    CONTROL_UUID,
                    bytearray([0x01, 0x01, 0x01]),
                    response=True
                )
                print("[SYSTEM ONLINE] Streaming started. Wave the device!")

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