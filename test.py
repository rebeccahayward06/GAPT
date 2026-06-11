import pandas as pd
import numpy as np

df = pd.read_csv("Cleaned_Labeled_Dataset_Final.csv")

cols = ['FreeAcc_X', 'FreeAcc_Y', 'FreeAcc_Z', 'Gyr_X', 'Gyr_Y', 'Gyr_Z']

means = df[cols].mean().values
stds  = df[cols].std().values

print("MEANS =", np.array2string(means, separator=', ', precision=6))
print("STDS  =", np.array2string(stds,  separator=', ', precision=6))