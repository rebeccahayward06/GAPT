"""
train_regions.py
Trains TWO models from the same dataset, matching the 3-sensor deployment:
  - wrist_model : circle, openclose, updown, punching_fast, punching_slow, whipping
  - hip_model   : hip_rotation_both, hip_thrust, side_to_side

Side (left/right) is NOT learned here - it is assigned live from which sensor
reports. Size (big/small) is NOT learned - it is read live as a continuous value.
Speed (fast/slow) IS kept as a class, because the data shows it is separable.

Both models use the same 6 channels (FreeAcc + Gyr) and the same extract_features.
Run this BEFORE liveEngine.py. Outputs go to ./models/.
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedGroupKFold, cross_val_score
from sklearn.calibration import CalibratedClassifierCV
from Features import build_dataset, FEATURE_COLS, RAW_COLS

DATA_PATH = "Cleaned_Labeled_Dataset_Final.csv"
OUT_DIR = "models"

# Class sets AFTER stripping side and size (see strip_side / strip_size below)
WRIST = {"circle", "openclose", "updown",
         "punching_fast", "punching_slow", "whipping"}
HIP = {"hip_rotation_both", "hip_thrust", "side_to_side"}


def strip_side(label):
    return label.replace("_left", "").replace("_right", "")


def strip_size(label):
    return label.replace("_big", "").replace("_small", "")

def make_pipe():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", CalibratedClassifierCV(
            SVC(kernel="rbf", C=10, gamma="scale", random_state=42),
            ensemble=False)),
    ])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    cols = FEATURE_COLS if FEATURE_COLS[0] in df.columns else RAW_COLS
    print(f"[Load] {df.shape} | using {len(cols)} channels")

    X, y_str, groups = build_dataset(df, cols)
    y_str = np.array([strip_size(strip_side(l)) for l in y_str])

    cv = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=42)

    for region_name, region in [("wrist", WRIST), ("hip", HIP)]:
        mask = np.array([l in region for l in y_str])
        Xr, yr, gr = X[mask], y_str[mask], groups[mask]

        le = LabelEncoder()
        yr_enc = le.fit_transform(yr)

        # honest grouped-by-recording accuracy for this region
        scores = cross_val_score(make_pipe(), Xr, yr_enc, groups=gr, cv=cv,
                                 scoring="accuracy", n_jobs=-1)
        print(f"\n[{region_name}] grouped CV: "
              f"{scores.mean():.3f} +- {scores.std():.3f} "
              f"| {len(le.classes_)} classes")
        print(f"[{region_name}] classes: {list(le.classes_)}")

        # fit on all of this region's data and save
        pipe = make_pipe()
        pipe.fit(Xr, yr_enc)
        joblib.dump(pipe, os.path.join(OUT_DIR, f"{region_name}_model.joblib"))
        joblib.dump(le, os.path.join(OUT_DIR, f"{region_name}_encoder.joblib"))
        print(f"[{region_name}] saved models/{region_name}_model.joblib (+ encoder)")


if __name__ == "__main__":
    main()
