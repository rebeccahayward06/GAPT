import argparse
import os
import time 
import joblib
import numpy as np 
import pandas as pd 
from Features import extract_features, FEATURE_COLS, RAW_COLS, WINDOW_SIZE, STEP_SIZE

DATA_PATH="Cleaned_Labeled_Dataset_Final.csv"
MODEL_PATH="best_model.joblib"
ENCODER_PATH="label_encoder.joblib"

UNITY_IP= "192.168.68.100" #julia's local ip address, change if needed to run on another machine
UNITY_PORT=9000
OSC_ADDR="/motionsketch/prediction"


#loading model
def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"No model found at '{MODEL_PATH}'.\n"
            "Run: python train.py first."
        )
    pipe=joblib.load(MODEL_PATH)
    le=joblib.load(ENCODER_PATH)
    print(f"[Model] Loaded {MODEL_PATH}")
    print(f"[Model] Classes: {list(le.classes_)}")
    return pipe, le


#core prediction function 

def predict_window(window: np.ndarray, pipe,le)->dict:
    
    t0=time.perf_counter()
    feat=extract_features(window)
    feat=feat.reshape(1,-1)

    prob=pipe.predict_proba(feat)[0]
    pred_idx=int(np.argmax(prob))
    label=le.inverse_transform([pred_idx])[0]
    confidence=float(prob[pred_idx])

    latency_ms=round((time.perf_counter()-t0)* 1000,2)

    #visual parameter mapping 

    acc=window[:,3:6]
    gyr=window[:,6:9]

    acc_intensity=float(min(np.mean(np.linalg.norm(acc,axis=1))/10.0,1.0))
    gyr_intensity=float(min(np.mean(np.linalg.norm(gyr, axis=1))/50.0, 1.0))
    jerk=float(np.mean(np.abs(np.diff(acc,axis=0, n=2))))
    smoothness=max(0.0, 1.0 - min(jerk/5.0, 1.0))
    color_shift=float(abs(np.mean(window[:,2]))% 1.0)

    mapping={
        "brush_size":round(acc_intensity,3),
        "particle_speed":round(gyr_intensity, 3),
        "line_curvature":round(smoothness, 3),
        "blur_amount":round(smoothness*0.8,3),
        "color_shift":round(color_shift,3),
    }

    return{
        "label": label,
        "confidence":round (confidence, 4),
        "probabilities":{le.classes_[i]: round(float(p),4)
                         for i, p in enumerate(prob)},
        "latency_ms":latency_ms,
        "mapping":mapping,
    }

#offline demo

def run_demo():
    
    pipe, le=load_model()

    df=pd.read_csv(DATA_PATH)
    cols=FEATURE_COLS if FEATURE_COLS[0] in df.columns else RAW_COLS

    print("\n-----Offline Prediction Demo ----------------------")
    print(f"{'True label':<25}   {'Predicted':<25} Conf    Latency")
    print(" "+"─" *68)

    correct=0
    total=0

    for label_true in sorted(df['Label'].unique()):
        signal=df[df['Label']== label_true][cols].values

        mid=max(0,len(signal) //2- WINDOW_SIZE //2)
        window=signal[mid:mid+WINDOW_SIZE]

        if window.shape[0]<WINDOW_SIZE:
            continue

        result=predict_window(window,pipe,le)
        match  = "✓" if result["label"] == label_true else "✗"

        print(f"{label_true:<25}  {result['label']:<25}"
              f"{result['confidence']:.2%}  {result['latency_ms']} ms {match}")

        correct +=int(result["label"]==label_true)
        total+=1

    print(f"\nDemo accuracy:{correct}/{total}={correct/total:.0%}")


#live OSC stream to unity

def run_osc_server():
    
    try:
        from pythonosc import udp_client
    except ImportError:
        print("ERROR: python osc not installed")
        return
    
    pipe, le= load_model()

    client=udp_client.SimpleUDPClient(UNITY_IP, UNITY_PORT)
    print(f"\n[OSC] Sending to Unity at {UNITY_IP}:{UNITY_PORT}")
    print(f"[OSC] OSC address: {OSC_ADDR}")

    df=pd.read_csv(DATA_PATH)
    cols=FEATURE_COLS if FEATURE_COLS[0] in df.columns else RAW_COLS

    print(f"{'True label':<25}  {'Predicted':<25}Conf   Latency")
    print(" "+"─" *68)

    for label_true in df['Label'].unique():
        signal=df[df['Label']== label_true][cols].values

        for start in range(0, len(signal)-WINDOW_SIZE + 1,STEP_SIZE):
            window=signal[start:start+WINDOW_SIZE]
            if window.shape[0]<WINDOW_SIZE:
                continue

            result=predict_window(window,pipe,le)
            m=result["mapping"]

            client.send_message(OSC_ADDR, [
                result["label"],
                result["confidence"],
                m["brush_size"],
                m["particle_speed"],
                m["line_curvature"],
                m["blur_amount"],
                m["color_shift"],
            ])

            print(
                f"{label_true:<25}  {result['label']:<25}  "
                f"{result['confidence']:.2%}  {result['latency_ms']} ms"
            )

            time.sleep(0.5)


#main

if __name__=="__main__":

    parser=argparse.ArgumentParser(description="Prediction")
    parser.add_argument("--demo", action="store_true",
                        help="run offline prediction ( no unity needed)")
    parser.add_argument("--serve", action="store_true",
                        help="start live OSC stream to unity")
    args=parser.parse_args()

    if args.serve:
        run_osc_server()
    else:
        run_demo()



