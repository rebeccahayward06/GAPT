import numpy as np, pandas as pd
from Features import WINDOW_SIZE, STEP_SIZE

df = pd.read_csv("Cleaned_Labeled_Dataset_Final.csv")
gyr = ['Gyr_X_Smoothed', 'Gyr_Y_Smoothed', 'Gyr_Z_Smoothed']

for label in ['hip_rotation_both', 'hip_thrust', 'side_to_side']:
    vals = []
    for _, g in df[df['Label'] == label].groupby('Source'):
        sig = g[gyr].values
        for s in range(0, len(sig) - WINDOW_SIZE + 1, STEP_SIZE):
            w = sig[s:s+WINDOW_SIZE]
            vals.append(np.linalg.norm(np.abs(np.sum(w, axis=0)) / WINDOW_SIZE))
    vals = np.array(vals)
    print(f"{label:18s} |net rot|  median={np.median(vals):.2f}  "
          f"25-75pct=[{np.percentile(vals,25):.2f}, {np.percentile(vals,75):.2f}]")