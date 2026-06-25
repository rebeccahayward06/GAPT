# MotionSketch

**Generating live visual art from wearable body movement.**

You wear three motion sensors, you move, and a Unity canvas paints itself in real time
based on the gesture you perform and how big and fast you perform it. The Python side
reads the sensors, recognises the gesture, and streams the result to the Unity side over
OSC, which renders it.

---

## How it fits together

```
Movella DOT sensors  →  Python (sense + classify)  →  OSC/UDP  →  Unity (render)
   3 × IMU, ~60 Hz         liveEngine.py                         visual art
```

- **Sensors:** 3 × Movella DOT — left wrist, right wrist, hips. Bluetooth Low Energy, ~60 Hz.
- **Channels used:** free acceleration (X, Y, Z) + gyroscope (X, Y, Z) = 6 channels. Euler angles are dropped (drift-prone, pose-dependent).
- **Side** (left/right) is set by *which* sensor reports, not classified. **Size/speed** are read as continuous values and sent to Unity as visual parameters.

---

## Python side

### Requirements

Python 3.10+. Install dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt`: `bleak`, `python-osc`, `joblib`, `scikit-learn`, `pandas`, `numpy`.

### Files

| File | What it does |
|------|--------------|
| `PythonParser.py` | Parses raw recordings in `GAPTcsv/<gesture>/DOT*.csv` into one clean, smoothed, labelled dataset → `Cleaned_Labeled_Dataset_Final.csv`. |
| `Features.py` | Sliding-window feature extraction (60-sample / ~1 s window, 30-sample step). Produces the **53-feature** vector. Shared by training **and** live inference. |
| `Train.py` | Research script: trains and compares Random Forest, SVM, and MLP with cross-validation, saves the best as `best_model.joblib` + `label_encoder.joblib`, and writes `evaluation_plots.png`. |
| `region.py` | Trains the **two deployed models** — `wrist_model` and `hip_model` — into `models/`. Run this before going live. |
| `liveEngine.py` | The live system: connects the 3 sensors, runs the same feature pipeline in real time, predicts ~2×/sec, and streams the result to Unity over OSC. |
| `complete_mock_osc.py` | Dependency-free demo sender. Emits realistic OSC messages for every gesture **without any sensors** — the fallback for the live demo. |
| `scanner.py` | Lists nearby Movella DOT sensors and their Bluetooth addresses. |
| `Predict.py` | Optional: replays a recording from file and streams predictions over OSC. |

### Run order

```bash
# 1. Build the dataset from raw recordings (only needed if recordings changed)
python PythonParser.py

# 2. Train the two deployed models (wrist + hip) into ./models/
python region.py

# 3. Find your sensor addresses, then start the live engine
python scanner.py
python liveEngine.py
```

> **Demo without sensors:** skip the steps above and run `python complete_mock_osc.py`.
> It streams the same OSC messages Unity expects, so the visuals run with no hardware.

---

## Unity side

The Unity project renders the art. It runs an **OSC receiver on UDP port `9000`** and
listens for the message below.

### OSC contract

```
Address:  /motionsketch/prediction
Values:   [ label,            # string  – e.g. "punching_fast_left", "idle"
            confidence,        # float   – 0.0–1.0
            brush_size,        # float   – 0.0–1.0
            particle_speed,    # float   – 0.0–1.0
            line_curvature,    # float   – 0.0–1.0
            blur_amount,       # float   – 0.0–1.0
            color_shift ]      # float   – 0.0–1.0
```

Unity uses the **label** to pick which visual behaviour to trigger (a circle traces an
arc, a punch bursts, a whip streaks) and the **float parameters** to drive how the mark
looks — its size, speed, curvature, blur, and colour. Messages arrive roughly twice a
second, so the canvas reacts as you move.

### Where to find it

The Unity project is provided **two ways**:

1. **Inside this GitHub repository**, alongside the Python files — clone the repo and open
   the Unity project folder in the Unity Editor.
2. **As a standalone project file**, submitted on its own — open it directly without the
   rest of the repository.

Either copy is the same project; the standalone version exists only for submission.

### Running it

1. Open the Unity project (from the repo or the submission file) and press **Play**
   (or run a built executable). It begins listening on port `9000`.
2. Start either `liveEngine.py` (with sensors) or `complete_mock_osc.py` (without).
3. Move — the canvas responds.

---

## Configuration notes

- **Target machine:** Python streams to `127.0.0.1:9000` by default (`UNITY_IP` /
  `UNITY_PORT` in `liveEngine.py`). If Unity runs on a different machine, set `UNITY_IP`
  to that machine's local IP.
- **Sensor addresses:** use `scanner.py` to find them, then set them in `liveEngine.py`.
- **Feature consistency:** the live path and the training path must use the *same*
  `Features.py`. If you change feature extraction, retrain (`region.py`) before going live.

---

## Team

Julia Kay Gutiza · Rebecca Hayward · Julian Galea — ICS2000.
