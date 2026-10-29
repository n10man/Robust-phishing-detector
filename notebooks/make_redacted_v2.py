"""Experiment 2: write redacted copies of data_v2/train.csv and data_v2/val.csv.

Redaction happens BEFORE feature extraction: the url column is redacted with
privacy.redact_url, then the 11 features are recomputed from the redacted url.
New files get a suffix; nothing existing is overwritten. data_v2/test.csv is never opened
(the final script will apply redact_url to it later). Prints counts only, never a URL.

Run from the repo root:  .venv/bin/python notebooks/make_redacted_v2.py
"""
import os
import pandas as pd
from privacy import redact_url, has_email
from stage2_computer_readable import extract_features

for split in ["train", "val"]:
    src, dst = f"data_v2/{split}.csv", f"data_v2/{split}_redacted.csv"
    if os.path.exists(dst):
        raise SystemExit(f"{dst} already exists; not overwriting.")
    df = pd.read_csv(src)
    num_cols = [c for c in df.columns if c not in ("url", "label")]
    red = df["url"].astype(str).map(redact_url)
    changed = (red != df["url"].astype(str)).to_numpy()
    feats = pd.DataFrame([extract_features(u) for u in red])[num_cols]
    out = pd.concat([red.rename("url"), feats, df["label"]], axis=1)

    # Sanity: rows that were not changed must keep exactly their old features
    same = (out.loc[~changed, num_cols].to_numpy() == df.loc[~changed, num_cols].to_numpy()).all()
    still = int(df["url"].astype(str).map(has_email).sum())
    left = int(red.map(has_email).sum())
    print(f"{split}: rows {len(df):,} | rows changed {int(changed.sum()):,} "
          f"({changed.mean():.4f}) | email-like after host before {still:,} -> after {left:,} "
          f"| unchanged rows keep identical features: {bool(same)}")
    print(f"   label counts unchanged: {bool((out['label'] == df['label']).all())} | columns unchanged: {list(out.columns) == list(df.columns)}")
    assert same and list(out.columns) == list(df.columns)
    out.to_csv(dst, index=False)
    print(f"   wrote {dst}")
