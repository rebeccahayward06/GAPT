import pandas as pd
df = pd.read_csv("Cleaned_Labeled_Dataset_Final.csv")
print(df[['FreeAcc_X', 'FreeAcc_Y', 'FreeAcc_Z']].describe())
