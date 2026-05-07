import os 
import warnings 
import joblib
import matplotlib.pyplot as plt
import numpy as np 
import pandas as pd 
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline 
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC
from Features import build_dataset, FEATURE_COLS, RAW_COLS

warnings.filterwarnings("ignore")

DATA_PATH="Cleaned_Labeled_Dataset_Final.csv"
MODEL_PATH="best_model.joblib"
ENCODER_PATH="label_encoder.joblib"

#loading data 

def load_data():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"'{DATA_PATH}'not found.\n"
            "Run PythonParser.py first."
        )
    
    df=pd.read_csv(DATA_PATH)
    print(f"[Load] Shape: {df.shape} | Labels found: {sorted(df['Label'].unique())}")

    #checking which columns are available 
    if FEATURE_COLS[0] in df.columns:
        cols=FEATURE_COLS
    else:
        print("[Load] Smoothed columns missing-using raw columns.")
        cols=RAW_COLS

    return df,cols


#defining the models 
def get_models():

    models={
        "Random Forest":Pipeline([
            ("scaler",StandardScaler()),
            ("clf",RandomForestClassifier(
                n_estimators=200,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1,
            )),
        ]),

        #svm with rbf kernel
        "SVM (RBF)":Pipeline ([
            ("scaler",StandardScaler()),
            ("clf",SVC(
                kernel="rbf",
                C=10,
                gamma="scale",
                probability=True,
                random_state=42,
            )),
            
        ]),

        #MLP ( multi-layer perceptron)

        "MLP":Pipeline([
            ("scaler",StandardScaler()),
            ("clf",MLPClassifier(
                hidden_layer_sizes=(128,64),
                activation="relu",
                max_iter=500,
                early_stopping=True,
                random_state=42,
            )),
        ]),
    }
    return models


#cross-validation 
def cross_validate(models, X,y):
    cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    print("\n---------Cross-validation results(5-fold)---------------")
    cv_results={}

    for name,pipe in models.items():
        scores=cross_val_score(pipe,X,y,cv=cv, scoring="accuracy", n_jobs=-1)
        cv_results[name]=scores
        print(f"{name:<20} mean={scores.mean():.4f} std= +-{scores.std():.4f}")

    return cv_results

#training the best model on all the data 

def train_best(models, cv_results, X,y,le):

    best_name=max(cv_results, key=lambda n: cv_results[n].mean())
    best_pipe=models[best_name]

    print(f"\n[Train] Best model:{best_name}"
          f"(mean acc={cv_results[best_name].mean():.4f})")
    
    best_pipe.fit(X,y)

    joblib.dump(best_pipe,MODEL_PATH)
    joblib.dump(le, ENCODER_PATH)
    print(f"[Train] Saved{MODEL_PATH}")
    print(f"[Train] Saved{ENCODER_PATH}")

    return best_pipe, best_name


#evaluation and plotting 

def evaluate(pipe,le,X,y,cv_results,best_name):

    print("\n------------Classification Report-----------------")
    y_pred=pipe.predict(X)
    print(classification_report(y,y_pred, target_names=le.classes_))

    #confusion matrix and cv bar chart 
    fig, axes=plt.subplots(1,2,figsize=(18,7))
    fig.suptitle("MotionSketch-movement classifier evaluation", fontsize=14)

    cm=confusion_matrix(y, y_pred)
    ConfusionMatrixDisplay(cm, display_labels=le.classes_).plot(
        ax=axes[0], xticks_rotation=45, colorbar=False, cmap="Blues"
    )
    axes[0].set_title(f"Confusion matrix- {best_name}", fontsize=12)

    names=list(cv_results.keys())
    means=[cv_results[n].mean() for n in names]
    stds=[cv_results[n].std() for n in names]
    colors=["#E8844C"if n==best_name else "#4C9BEB" for n in names]

    axes[1].bar(names,means,yerr=stds, color=colors,
                edgecolor="white", capsize=8,width=0.45)
    axes[1].set_ylim(0,1.08)
    axes[1].set_ylabel("Accuracy")
    axes[1].set_title("cross-validation accuracy-model comparison",fontsize=12)

    for i, (m,s) in enumerate(zip(means,stds)):
        axes[1].text(i,m+s+0.015, f"{m:.3f}", ha='center', fontsize=10)

    plt.tight_layout()
    plt.savefig("evaluation_plots.png",dpi=150, bbox_inches="tight")
    print("[Eval] saved_evaluation_plots.png")
    plt.show()

    #feature importances- random forest only

    if "Random Forest" in best_name:
        imps=pipe.named_steps["clf"].feature_importances_
        top_n=20
        idx=np.argsort(imps)[::-1][:top_n]

        fig2, ax2=plt.subplots(figsize=(12,5))
        ax2.bar(range(top_n), imps[idx])
        ax2.set_xticklabels([f"f{i}" for i in idx], rotation=45, fontsize=8)
        ax2.set_xlabel("Feature index")
        ax2.set_ylabel("Importance score")
        ax2.set_title(f"Top {top_n} most important features- random forest")
        plt.tight_layout()
        plt.savefig("feature_importances.png",dpi=150)
        print("[Eval] saved feature_importances.png")
        plt.show()


#main

if __name__=="__main__":
    print("="*60)
    print("Training pipeline")
    print("="*60)
    
    #loading the data 
    df,cols=load_data()

    #building feature matrix from sliding windows 
    X,y_str= build_dataset(df, cols)

    #encoding string labels to integers
    le= LabelEncoder()
    y=le.fit_transform(y_str)
    print(f"[Train] Encoded {len(le.classes_)} classes: {list(le.classes_)}")

    #defining the three candidate models
    models=get_models()

    #cross validating all three
    cv_results=cross_validate(models,X,y)

    #training the winner on all the data and saving 
    best_pipe, best_name=train_best (models, cv_results, X, y, le)

    #evaluating with plots
    evaluate(best_pipe, le, X, y, cv_results, best_name)

    

        