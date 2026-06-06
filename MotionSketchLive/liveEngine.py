import asyncio
import struct
import numpy as np
import joblib
import collections
import time
from bleak import BleakClient
from pythonosc import udp_client

# Direct feature extraction integration
from Features import extract_features, WINDOW_SIZE, STEP_SIZE

# ==============================================================================
# CONFIGURATION
# ==============================================================================
SENSOR_ADDRESS = "D4:22:CD:00:60:F0"
UNITY_IP = "127.0.0.1"
UNITY_PORT = 9000
OSC_PATH = "/motionsketch/prediction"

# Xsens DOT 128-bit BLE UUID definitions
CONTROL_UUID     = "15172001-4947-11e9-8646-d663bd873d93"
UUID_ORIENTATION = "15172002-4947-11e9-8646-d663bd873d93"
UUID_MEDIUM      = "15172003-4947-11e9-8646-d663bd873d93"
UUID_COMPLETE    = "15172004-4947-11e9-8646-d663bd873d93"

# Student A Calibration Space Vectors
MEANS = np.array([-2.156896, 10.437826, -11.540046, -0.022744, 0.111932, -0.413033, -7.426878, 0.691863, -5.463504])
STDS = np.array([29.179614, 35.469717, 130.952588, 3.977307, 3.735324, 2.847601, 66.662668, 87.500496, 80.985148])

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
        """Robust multi-payload parser handling both Complete (40B) and Medium (20B+) streams"""
        try:
            if len(data) >= 40:
                # 9-column Complete format (Euler + Accel + Gyro)
                return np.array(struct.unpack('<fffffffff', data[4:40]))
            elif len(data) >= 16:
                # 3-column Orientation format (Padded with zeros for safety)
                unpacked = struct.unpack('<ffff', data[4:20])
                return np.array([unpacked[1], unpacked[2], unpacked[3], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        except Exception:
            return None
        return None

    def ble_notification_callback(self, sender, data):
        start_time = time.perf_counter()
        self.total_packets_received += 1
        
        # Clean, single-line ticker so you know data is actively moving
        if self.total_packets_received % 30 == 0:
            print(f"[Live Sync] Packets Processed: {self.total_packets_received}...", end="\r")
        
        raw_signal = self.parse_payload(data)
        if raw_signal is None:
            return

        scaled_signal = (raw_signal - MEANS) / STDS
        self.smooth_buffer.append(scaled_signal)
        smoothed_frame = np.mean(self.smooth_buffer, axis=0)
        self.window_buffer.append(smoothed_frame)
        
        self.packet_counter += 1
        if len(self.window_buffer) == WINDOW_SIZE and self.packet_counter % STEP_SIZE == 0:
            self.run_inference(start_time)

    def run_inference(self, start_time):
        current_window = np.array(self.window_buffer)
        features = extract_features(current_window).reshape(1, -1)
        
        probabilities = self.model.predict_proba(features)[0]
        predicted_idx = np.argmax(probabilities)
        confidence = probabilities[predicted_idx]
        label = self.le.inverse_transform([predicted_idx])[0]
        
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        acc_magnitude = np.mean(np.linalg.norm(current_window[:, 3:6], axis=1))
        
        # 🚨 OPEN THRESHOLD FILTER: Let us see exactly what numbers are calculating live
        if confidence > 0.10:  
            print(f"\n >> [{label:<22}] Confidence: {confidence:.2%} | Latency: {latency_ms}ms")
            self.osc.send_message(OSC_PATH, [label, float(confidence), float(acc_magnitude)])

async def main():
    pipeline = MotionSketchLivePipeline()
    print(f"[BLE] Initializing handshake with sensor: {SENSOR_ADDRESS}...")
    
    try:
        async with BleakClient(SENSOR_ADDRESS) as client:
            if client.is_connected:
                print("[BLE] Bluetooth connection secure. Mapping architecture paths...")
                
                available_uuids = [char.uuid for service in client.services for char in service.characteristics]
                
                # Sequence triggers to safely fire up streaming across old/new firmware revisions
                start_commands = [b'\x01\x01\x01', b'\x01\x01\x02', b'\x01\x01\x10']
                for cmd in start_commands:
                    try:
                        await client.write_gatt_char(CONTROL_UUID, cmd, response=True)
                        await asyncio.sleep(0.1)
                    except Exception:
                        pass

                # Multi-channel failover binding
                target_channels = [UUID_ORIENTATION, UUID_MEDIUM, UUID_COMPLETE]
                bound_count = 0
                
                for uuid in target_channels:
                    if uuid in available_uuids:
                        try:
                            await client.start_notify(uuid, pipeline.ble_notification_callback)
                            bound_count += 1
                        except Exception:
                            pass
                
                print(f"[SYSTEM ONLINE] Bound to {bound_count} sensor data channels. Wave the device!")
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