import pandas as pd
import glob
from sklearn.preprocessing import StandardScaler

# 1. Map the files to labels chronologically
files = sorted(glob.glob("DOT1_*.csv"))
labels = [
    "Big circle", "Small Circle", "Hip rotation both sides", "hip thrusts", 
    "openclose (right to left) big", "open close small", "fast punch", 
    "slow punch", "side to side hips", "up down arms big"
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
master_df.to_csv("Cleaned_Labeled_Dataset.csv", index=False)
print("Pipeline Complete! Master dataset shape:", master_df.shape)