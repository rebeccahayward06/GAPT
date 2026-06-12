import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedGroupKFold, cross_val_score

from Features import build_dataset
from Train import load_data, strip_side, strip_size

WRIST = {'circle', 'openclose', 'updown', 'punching_fast', 'punching_slow', 'whipping'}
HIP   = {'hip_rotation_both', 'hip_thrust', 'side_to_side'}

FREEACC = ['FreeAcc_X_Smoothed', 'FreeAcc_Y_Smoothed', 'FreeAcc_Z_Smoothed']
GYR     = ['Gyr_X_Smoothed',     'Gyr_Y_Smoothed',     'Gyr_Z_Smoothed']
EULER   = ['Euler_X_Smoothed',   'Euler_Y_Smoothed',   'Euler_Z_Smoothed']
HIP_COLS = FREEACC + GYR + EULER          # Euler LAST → acc=0:3, gyr=3:6 stay correct



def main():
    df, cols = load_data()
    X, y_str, groups = build_dataset(df, cols)
    y_str = np.array([strip_side(l) for l in y_str])
    
    y_str = np.array([strip_side(l) for l in y_str])
    y_str = np.array([strip_size(l) for l in y_str])

    cv = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=42)

    def score(Xr, yr, gr, label):
        yr_enc = LabelEncoder().fit_transform(yr)
        pipe = Pipeline([("scaler", StandardScaler()),
                         ("clf", SVC(kernel="rbf", C=10, gamma="scale"))])
        s = cross_val_score(pipe, Xr, yr_enc, groups=gr, cv=cv,
                            scoring="accuracy", n_jobs=-1)
        print(f"{label:24s}: {s.mean():.3f} +- {s.std():.3f}")


    score(X, y_str, groups, f"FLAT ({len(set(y_str))} classes)")
    for name, region in [("WRIST", WRIST), ("HIP", HIP)]:
        mask = np.array([l in region for l in y_str])
        score(X[mask], y_str[mask], groups[mask],
              f"{name} ({len(region)} classes)")
        
    # hip-with-orientation experiment (builds a separate 9-channel feature set)
    X_h, y_h, g_h = build_dataset(df, HIP_COLS)
    y_h = np.array([strip_size(strip_side(l)) for l in y_h])
    mask_h = np.array([l in HIP for l in y_h])
    score(X_h[mask_h], y_h[mask_h], g_h[mask_h], "HIP + Euler")

if __name__ == "__main__":
    main()