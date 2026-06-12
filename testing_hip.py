import pandas as pd
df = pd.read_csv("Cleaned_Labeled_Dataset_Final.csv")
hip = df[df['Label'].isin(['hip_rotation_both', 'hip_thrust', 'side_to_side'])]
wrist = df[df['Label'].isin(['circle', 'openclose', 'updown', 'punching_fast', 'punching_slow', 'whipping'])]


for (label, source), g in hip.groupby(['Label', 'Source']):
    stds = g[['Gyr_X', 'Gyr_Y', 'Gyr_Z']].std()
    print(f"{label:18s} {source:25s} dominant gyro axis: {stds.idxmax()}  "
          f"(signs: {g[['Gyr_X','Gyr_Y','Gyr_Z']].mean().round(1).to_dict()})")
    
for (label, source), g in wrist.groupby(['Label', 'Source']):
    stds = g[['Gyr_X', 'Gyr_Y', 'Gyr_Z']].std()
    print(f"{label:18s} {source:25s} dominant gyro axis: {stds.idxmax()}  "
          f"(signs: {g[['Gyr_X','Gyr_Y','Gyr_Z']].mean().round(1).to_dict()})")