import os 
import pandas as pd
import glob

# 1. Map the files to labels chronologically
files = sorted(glob.glob("GAPTcsv\\**\\DOT1*.csv",recursive=True))

all_data = []

# 2. Loop through and create labeled dataset
for f in files:
    #extracting label from the parent folder name
    l=os.path.basename(os.path.dirname(f))

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

# 4. Noise Filtering (Smoothing)
# Using a 5-step rolling average window to remove tiny sensor jitters. 
# We group by label so we don't bleed data across two different movements.
for col in feature_cols:
    master_df[f'{col}_Smoothed'] = master_df.groupby('Label')[col].transform(lambda x: x.rolling(window=5, min_periods=1).mean())

# Save the unified dataset
master_df.to_csv("Cleaned_Labeled_Dataset_Final.csv", index=False)
print("Pipeline Complete! Master dataset shape:", master_df.shape)