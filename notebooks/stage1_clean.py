import html
import pandas as pd

# 1. LOAD and LOOK before changing anything
df = pd.read_csv("data/phishing_site_urls.csv")
print(df.shape)
print(df["Label"].value_counts())
print(df.sample(10, random_state=1))

# 2. RENAME columns and make a numeric label (1 = phish, 0 = safe)
df = df.rename(columns={"URL": "url"})
df["label"] = (df["Label"].str.lower() == "bad").astype(int)
df = df[["url", "label"]]

# 3. BASIC CLEANING
df["url"] = df["url"].astype(str).str.strip()
df = df.dropna(subset=["url"])
df = df[df["url"] != ""]
df["url"] = df["url"].map(html.unescape)      # "&amp;" -> "&"

# 4. NORMALISE so near-duplicates look identical
df["url_norm"] = (
    df["url"].str.lower()
      .str.replace(r"^https?://", "", regex=True)
      .str.replace(r"^www\.", "", regex=True)
      .str.rstrip("/")
)

# 5. CONFLICTS: same normalised URL labelled both good and bad
labels_per_url = df.groupby("url_norm")["label"].nunique()
conflicting = labels_per_url[labels_per_url > 1].index
print("Conflicting URLs:", len(conflicting))
df = df[~df["url_norm"].isin(conflicting)]

# 6. DUPLICATES
before = len(df)
df = df.drop_duplicates(subset="url_norm")
print(f"Removed {before - len(df)} duplicates")

# 7. SHORTCUT CHECKS: does one class differ in a trivial way?
print("Starts with http, by class:")
print(df.groupby("label")["url"].apply(lambda s: s.str.lower().str.startswith("http").mean()))
print("Has a path (contains '/'), by class:")
print(df.groupby("label")["url"].apply(lambda s: s.str.contains("/").mean()))

# 8. CHECK and SAVE
print(df.shape)
print(df["label"].value_counts(normalize=True))
df.to_csv("data/clean_urls.csv", index=False)