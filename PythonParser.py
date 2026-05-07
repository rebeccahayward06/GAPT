import pandas as pd
import glob
from sklearn.preprocessing import StandardScaler

# 1. Map the files to labels chronologically
files = sorted(glob.glob("**\\DOT1*.csv",recursive=True))
labels = [
    "circle_big_left","circle_big_right", "circle_small_left", "circle_small_right","hip_rotation_both", "hip_thrust", 
    "openclose_big_left","openclose_big_right", "openclose_small_left","openclose_small_right", "punching_fast_left", 
    "punching_fast_right","punching_slow_left","punching_slow_right", "side_to_side", "updown_big_left","updown_big_right",
    "updown_small_left", "updown_small_right","whipping"
]

all_data = []

# 2. Loop through and create labeled dataset
for f, l in zip(files, labels):
    # Find where the actual data starts (Xsens DOT headers are 10-12 lines long)
    with open(f, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    skip = 0
    for i, line in enumerate(lines):
        if line.startswith("PacketCounter"):
            skip = i
            break
            
    df = pd.read_csv(f, skiprows=skip)
    
    # Add the target classification label
    df['Label'] = l
    all_data.append(df)

# Concatenate into one master dataset
master_df = pd.concat(all_data, ignore_index=True)

# Define the IMU feature columns we care about 
# Euler = Orientation, FreeAcc = Linear Acceleration, Gyr = Angular Velocity
feature_cols = ['Euler_X', 'Euler_Y', 'Euler_Z', 
                'FreeAcc_X', 'FreeAcc_Y', 'FreeAcc_Z', 
                'Gyr_X', 'Gyr_Y', 'Gyr_Z']

# 3. Normalisation (Mean = 0, Standard Deviation = 1)
# ML Models (Random Forests/SVMs) perform much better with scaled data
scaler = StandardScaler()
master_df[feature_cols] = scaler.fit_transform(master_df[feature_cols])

# 4. Noise Filtering (Smoothing)
# Using a 5-step rolling average window to remove tiny sensor jitters. 
# We group by label so we don't bleed data across two different movements.
for col in feature_cols:
    master_df[f'{col}_Smoothed'] = master_df.groupby('Label')[col].transform(lambda x: x.rolling(window=5, min_periods=1).mean())

# Save the unified dataset
master_df.to_csv("Cleaned_Labeled_Dataset_Final.csv", index=False)
print("Pipeline Complete! Master dataset shape:", master_df.shape)