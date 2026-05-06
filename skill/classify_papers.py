#!/usr/bin/env python3
"""
classify_papers.py — train AI vs Human classifier from argument-graph metrics.

Reads metrics.csv (output of compute_metrics.py), uses 6 core fingerprint
features, trains Logistic Regression + Random Forest with 5-fold stratified CV,
and reports Accuracy / F1 / AUC + confusion matrix + feature importance.

Default 6 features (curated, all p < 0.001 on n=80 corpus):
  - sum_node_degree         (= 2|edges|)
  - graph_longest_path      (论证深度)
  - pw_node_count           (Prior_Work 节点数)
  - pw_total_cites          (Prior_Work 总引用, strongest signal)
  - lim_scope_avg_cites     (Limitation critique surface, strongest signal)
  - method_node_count       (Method 复杂度)

Usage:
    python3 classify_papers.py metrics.csv
    python3 classify_papers.py metrics.csv --features sum_node_degree pw_total_cites
"""

import csv
import sys
import math
import argparse
from collections import defaultdict


CORE_FEATURES = [
    "sum_node_degree",
    "graph_longest_path",
    "pw_node_count",
    "pw_total_cites",
    "lim_scope_avg_cites",
    "method_node_count",
]


def load(path, features):
    X, y, files = [], [], []
    for r in csv.DictReader(open(path)):
        try:
            X.append([float(r[f]) for f in features])
        except (KeyError, ValueError):
            continue
        y.append(0 if r["label"] == "ai" else 1)  # 1 = human (positive)
        files.append(r["file"])
    return X, y, files


def main_func():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--features", nargs="+", default=CORE_FEATURES,
                    help="feature column names (default: 6 core)")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import StratifiedKFold, cross_val_predict
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        from sklearn.metrics import (accuracy_score, f1_score, roc_auc_score,
                                      confusion_matrix)
    except ImportError:
        print("Requires: pip install numpy scikit-learn", file=sys.stderr)
        sys.exit(1)

    X, y, files = load(args.csv, args.features)
    X = np.array(X); y = np.array(y); files = np.array(files)
    print(f"Dataset: n={len(y)}, AI={sum(y == 0)}, Human={sum(y == 1)}, "
          f"features={X.shape[1]}\n")

    cv = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)

    models = {
        "Logistic Regression (L2)": Pipeline([
            ("sc", StandardScaler()),
            ("lr", LogisticRegression(max_iter=1000, random_state=args.seed))
        ]),
        "Random Forest (200 trees, depth=5)": RandomForestClassifier(
            n_estimators=200, max_depth=5, random_state=args.seed),
    }

    for name, model in models.items():
        print(f"=== {name} ===")
        y_pred = cross_val_predict(model, X, y, cv=cv)
        y_proba = cross_val_predict(model, X, y, cv=cv,
                                     method="predict_proba")[:, 1]
        cm = confusion_matrix(y, y_pred)
        print(f"  Accuracy: {accuracy_score(y, y_pred):.3f}")
        print(f"  F1:       {f1_score(y, y_pred):.3f}")
        print(f"  AUC:      {roc_auc_score(y, y_proba):.3f}")
        print(f"  Confusion matrix:")
        print(f"             pred AI  pred Human")
        print(f"   AI       {cm[0, 0]:>8d}    {cm[0, 1]:>6d}")
        print(f"   Human    {cm[1, 0]:>8d}    {cm[1, 1]:>6d}")
        mis = files[y_pred != y]
        mis_dir = ["AI->Hu" if y[files == f][0] == 0 else "Hu->AI" for f in mis]
        if len(mis):
            mlist = [(f.replace('.json', ''), m) for f, m in zip(mis, mis_dir)]
            print(f"  Misclassified ({len(mis)}): {mlist}")
        print()

    # Feature importance (refit RF on full)
    rf = RandomForestClassifier(n_estimators=200, max_depth=5,
                                 random_state=args.seed).fit(X, y)
    print("=== RF feature importance (refit on all) ===")
    for f, imp in sorted(zip(args.features, rf.feature_importances_),
                          key=lambda x: -x[1]):
        bar = "#" * int(imp * 80)
        print(f"  {f:25s} {imp:.3f}  {bar}")

    # LR coefficients (refit on full, scaled)
    lr_pipe = Pipeline([
        ("sc", StandardScaler()),
        ("lr", LogisticRegression(max_iter=1000, random_state=args.seed))
    ]).fit(X, y)
    coefs = lr_pipe.named_steps["lr"].coef_[0]
    print("\n=== LR coefficients (refit on all, standardized) ===")
    for f, c in sorted(zip(args.features, coefs), key=lambda x: -abs(x[1])):
        sign = "+" if c >= 0 else "-"
        bar = "#" * int(abs(c) * 25)
        direction = "-> Human" if c > 0 else "-> AI"
        print(f"  {f:25s} {sign}{abs(c):.3f}  {bar}  ({direction})")


if __name__ == "__main__":
    main_func()
