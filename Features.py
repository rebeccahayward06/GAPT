import numpy as np 

#constants 
WINDOW_SIZE=60
STEP_SIZE=30 

FEATURE_COLS=[

    'FreeAcc_X_Smoothed',#linear acc X,Y,Z(gravity removed)
    'FreeAcc_Y_Smoothed',
    'FreeAcc_Z_Smoothed',
    'Gyr_X_Smoothed',#angular velocity X,Y,Z(how fast rotating around X,Y,Z)
    'Gyr_Y_Smoothed',
    'Gyr_Z_Smoothed',
]

RAW_COLS=[c.replace('_Smoothed','') for c in FEATURE_COLS]

def extract_features(window: np.ndarray) ->np.ndarray:#loops 9 times ( once per channel)
    feats=[]
    
    #statistical features 
    for i in range(window.shape[1]):#grabs one column, shape(60)
        ch=window[:,i]

        feats.append(float(np.mean(ch))) #average value
        feats.append(float(np.std(ch)))#spread
        feats.append(float(np.min(ch)))#lowest point
        feats.append(float(np.max(ch)))#highest point
        feats.append(float(np.max(ch)-np.min(ch)))#total range
        feats.append(float(np.sqrt(np.mean(ch ** 2))))#RMS

    #velocity proxy 
    diffs=np.abs(np.diff(window,axis=0))
    feats=feats+list(np.mean(diffs,axis=0))

    #3D magnitude
    acc=window[:,0:3]
    acc_mag=np.linalg.norm(acc,axis=1)
    feats.append(float(np.mean(acc_mag)))
    feats.append(float(np.std(acc_mag)))

    gyr=window[:,3:6]
    gyr_mag=np.linalg.norm(gyr,axis=1)
    feats.append(float(np.mean(gyr_mag)))
    feats.append(float(np.std(gyr_mag)))

    #jerk/smoothness
    jerk=np.diff(acc,axis=0,n=2)
    feats.append(float(np.mean(np.abs(jerk))))

    #directional zero-crossing rate 
    dominant_axis=int(np.argmax(np.std(gyr,axis=0)))
    gyr_dominant=gyr[:,dominant_axis]

    zero_crossings=int(np.sum(np.diff(np.sign(gyr_dominant))!=0))

    feats.append(zero_crossings/WINDOW_SIZE)
    feats.append(float(np.mean(np.abs(gyr_dominant))))

    # sustained-rotation signature: |integrated gyro|.
    # Large for continuous rotation
    net_rot = np.abs(np.sum(gyr, axis=0)) / WINDOW_SIZE
    feats.extend([float(v) for v in net_rot])
    feats.append(float(np.linalg.norm(net_rot)))

    return np.array(feats, dtype=np.float32)


#sliding window builder 
def build_dataset(df, cols):
    X_list, y_list, g_list = [], [], []

    for source in df['Source'].unique():
        sub = df[df['Source'] == source]
        label = sub['Label'].iloc[0]
        signal = sub[cols].values
        for start in range(0, len(signal) - WINDOW_SIZE + 1, STEP_SIZE):
            window = signal[start:start + WINDOW_SIZE]
            if window.shape[0] == WINDOW_SIZE:
                X_list.append(extract_features(window))
                y_list.append(label)
                g_list.append(source)

    X = np.array(X_list)
    y = np.array(y_list)
    groups = np.array(g_list)

    print(f"[Features] {X.shape[0]} windows | {X.shape[1]} features | {len(np.unique(groups))} recordings")
    return X, y, groups

