import re
import pandas as pd

SUSPICIOUS_WORDS = ["login", "verify", "secure", "account", "update",
                    "bank", "paypal", "signin", "confirm", "password"]

def extract_features(url):
    url = str(url).strip().lower()

    # split into host (the domain part) and path (everything after it)
    rest = re.sub(r"^[a-z][a-z0-9+.-]*://", "", url)   # drop http:// if present
    host = re.split(r"[/?#]", rest, maxsplit=1)[0]
    path = rest[len(host):]
    bare_host = host.split("@")[-1].split(":")[0]       # drop user@ and :port

    return {
        "url_length": len(url),
        "host_length": len(host),
        "path_length": len(path),
        "num_dots": url.count("."),
        "num_dots_host": host.count("."),
        "num_hyphens": url.count("-"),
        "num_digits": sum(c.isdigit() for c in url),
        "num_special": sum(url.count(c) for c in "@?=&%_~#"),
        "path_depth": path.count("/"),
        "has_ip": int(bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", bare_host))),
        "num_suspicious_words": sum(url.count(w) for w in SUSPICIOUS_WORDS),
    }

if __name__ == "__main__":
    # 1. sanity check on a few URLs we can verify by hand
    tests = [
        "paypal-login.secure-update.com/verify",
        "192.168.1.1/admin/login.php",
        "en.wikipedia.org/wiki/Cat",
    ]
    for t in tests:
        print(t)
        print(extract_features(t), "\n")

    # 2. run on the whole cleaned dataset
    df = pd.read_csv("data/clean_urls.csv")
    feats = pd.DataFrame([extract_features(u) for u in df["url"]])
    out = pd.concat([df[["url", "label"]].reset_index(drop=True), feats], axis=1)

    print(out.shape)
    print(out.groupby("label")[feats.columns].mean().T)   # average of each feature, by class
    out.to_csv("data/features.csv", index=False)