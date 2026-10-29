"""Experiment 3: build bare-domain training additions and held-out evaluation sets.

Safe:      Tranco domains whose host is its registered domain (strict public suffix list).
Phishing:  hosts from ~/sealed_eval_raw/phishing-domains-ACTIVE1.txt, after stripping www.,
           that are their own registered domain.
Kaggle format: no scheme, no www, no trailing slash, lowercase.

Writes (git-ignored data_v2/, never overwrites):
    bare_heldout_safe.csv, bare_heldout_phish.csv      10,000 each, EVALUATION ONLY
    bare_train_5k.csv, bare_train_20k.csv, bare_train_50k.csv   nested, per class balanced
    bare_training_domains.txt                          domains of the largest addition
Prints COUNTS ONLY (no domain is printed). The test split is never opened: its websites are
Kaggle's websites minus train minus val.

Run from the repo root:  .venv/bin/python notebooks/build_bare_sets.py
"""
import hashlib
import os
import random
import re
import statistics
from collections import Counter
import pandas as pd
from domains import registered_domain, is_bare, tld

RAW = os.path.expanduser("~/sealed_eval_raw/phishing-domains-ACTIVE1.txt")
HASH = os.path.expanduser("~/sealed_eval/sealed_domains_hashed.txt")
OUT = "data_v2"
SEED = 42
N_HELD = 10000
SIZES = {"5k": 5000, "20k": 20000, "50k": 50000}
TLD_GAP = 0.20          # percentage-point gap between classes that counts as a shortcut
LEN_GAP = 3.0           # mean-length gap (characters) that counts as a shortcut
VALID = re.compile(r"^[a-z0-9.-]+$")

outputs = [f"{OUT}/bare_heldout_safe.csv", f"{OUT}/bare_heldout_phish.csv",
           f"{OUT}/bare_training_domains.txt"] + [f"{OUT}/bare_train_{k}.csv" for k in SIZES]
for p in outputs:
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")

h256 = lambda d: hashlib.sha256(d.encode("utf-8")).hexdigest()
sealed = set(open(HASH).read().split())

# ---- Safe candidates (Tranco) ----
tr = pd.read_csv("data/tranco_262W9.csv", header=None, names=["rank", "domain"])
tr["domain"] = tr["domain"].astype(str).str.strip().str.lower()
tr_all = set(tr["domain"])
top100k = set(tr.loc[tr["rank"] <= 100000, "domain"])
safe = sorted({d for d in tr["domain"] if VALID.match(d) and is_bare(d)})
print(f"Safe: Tranco rows {len(tr):,} -> valid and bare {len(safe):,}")

# ---- Phishing candidates ----
hosts = []
with open(RAW, encoding="utf-8", errors="replace") as f:
    for line in f:
        h = re.split(r"[/:?#]", line.strip().lower(), maxsplit=1)[0]
        h = re.sub(r"^www\.", "", h)
        if h:
            hosts.append(h)
uniq = sorted(set(hosts))
valid = [h for h in uniq if VALID.match(h)]
phish = [h for h in valid if is_bare(h)]
print(f"Phishing: lines {len(hosts):,} | unique {len(uniq):,} | valid characters {len(valid):,} | "
      f"bare {len(phish):,} (dropped as not bare: {len(valid) - len(phish):,})")
before = len(phish)
phish = [h for h in phish if h not in top100k and registered_domain(h) not in top100k]
print(f"   removed because in Tranco top 100k: {before - len(phish):,}")
both = set(phish) & set(safe)
if both:
    print(f"   domains in both pools (label conflict, removed from both): {len(both):,}")
phish = [h for h in phish if h not in both]
safe = [d for d in safe if d not in both]

# ---- Leakage filters ----
clean_set = set(pd.read_csv("data/clean_urls.csv", usecols=["url"])["url"].astype(str).map(registered_domain))
train_set = set(pd.read_csv(f"{OUT}/train.csv", usecols=["url"])["url"].astype(str).map(registered_domain))
val_set = set(pd.read_csv(f"{OUT}/val.csv", usecols=["url"])["url"].astype(str).map(registered_domain))
test_set = clean_set - train_set - val_set            # the test split's websites, without opening it
print(f"Kaggle websites {len(clean_set):,} = train {len(train_set):,} + val {len(val_set):,} + test {len(test_set):,}")


def filter_pool(cands, label):
    key = {c: registered_domain(c) for c in cands}
    not_sealed = [c for c in cands if h256(key[c]) not in sealed]
    train_ok = [c for c in not_sealed if key[c] not in clean_set or key[c] in train_set]
    held_ok = [c for c in not_sealed if key[c] not in clean_set]
    print(f"{label}: candidates {len(cands):,} | in sealed set (removed) {len(cands) - len(not_sealed):,} | "
          f"in val or test (removed) {len(not_sealed) - len(train_ok):,} | training-eligible {len(train_ok):,} | "
          f"held-out-eligible (not in Kaggle) {len(held_ok):,}")
    return train_ok, held_ok


phish_train_ok, phish_held_ok = filter_pool(phish, "phishing")
safe_train_ok, safe_held_ok = filter_pool(safe, "safe")

# ---- Held-out sets, then nested training additions ----
rng = random.Random(SEED)
held_safe = rng.sample(sorted(safe_held_ok), N_HELD)
held_phish = rng.sample(sorted(phish_held_ok), N_HELD)
held_all = set(held_safe) | set(held_phish)
safe_pool = sorted(d for d in safe_train_ok if d not in held_all)
phish_pool = sorted(d for d in phish_train_ok if d not in held_all)
rng.shuffle(safe_pool)
rng.shuffle(phish_pool)
n_max = max(SIZES.values())
if min(len(safe_pool), len(phish_pool)) < n_max:
    raise SystemExit(f"Pools too small for {n_max:,} per class: safe {len(safe_pool):,}, phishing {len(phish_pool):,}")
print(f"After held-out: training pools safe {len(safe_pool):,}, phishing {len(phish_pool):,}")


def frame(domains, label):
    return pd.DataFrame({"url": domains, "label": label})


for name, n in SIZES.items():
    add = pd.concat([frame(safe_pool[:n], 0), frame(phish_pool[:n], 1)]).sample(frac=1, random_state=SEED)
    add.to_csv(f"{OUT}/bare_train_{name}.csv", index=False)
frame(held_safe, 0).to_csv(f"{OUT}/bare_heldout_safe.csv", index=False)
frame(held_phish, 1).to_csv(f"{OUT}/bare_heldout_phish.csv", index=False)
add50 = safe_pool[:n_max] + phish_pool[:n_max]
with open(f"{OUT}/bare_training_domains.txt", "w") as f:
    f.write("\n".join(sorted({registered_domain(d) for d in add50})) + "\n")
print(f"Wrote held-out ({N_HELD:,} + {N_HELD:,}) and training additions {', '.join(SIZES)} per class to {OUT}/")

# ---- Leakage check (all must be 0) ----
k_add = {d: registered_domain(d) for d in add50}
k_held = {d: registered_domain(d) for d in held_all}
add_keys, held_keys = set(k_add.values()), set(k_held.values())
checks = {
    "additions vs val websites": len(add_keys & val_set),
    "additions vs test websites (inferred, test file not opened)": len(add_keys & test_set),
    "additions vs sealed set (hash)": sum(h256(k) in sealed for k in add_keys),
    "held-out vs additions": len(held_keys & add_keys),
    "held-out vs all Kaggle websites": len(held_keys & clean_set),
    "held-out vs sealed set (hash)": sum(h256(k) in sealed for k in held_keys),
    "held-out safe vs held-out phishing": len(set(held_safe) & set(held_phish)),
    "additions safe vs additions phishing": len(set(safe_pool[:n_max]) & set(phish_pool[:n_max])),
}
print("\nLEAKAGE CHECK (every number must be 0)")
for k, v in checks.items():
    print(f"  {k}: {v}")
assert all(v == 0 for v in checks.values()), "leakage found"

# ---- Shortcut check: TLD mix and domain length by class ----
print("\nSHORTCUT CHECK (counts only). TLD = last label. Flag if a TLD share differs by more than "
      f"{TLD_GAP * 100:.0f} points or mean length by more than {LEN_GAP:.0f} characters.")
sets = {"additions 5k": (safe_pool[:5000], phish_pool[:5000]),
        "additions 20k": (safe_pool[:20000], phish_pool[:20000]),
        "additions 50k": (safe_pool[:50000], phish_pool[:50000]),
        "held-out": (held_safe, held_phish)}
any_flag = False
for name, (s, p) in sets.items():
    cs, cp = Counter(map(tld, s)), Counter(map(tld, p))
    sh = {t: c / len(s) for t, c in cs.items()}
    ph = {t: c / len(p) for t, c in cp.items()}
    print(f"\n[{name}] per class n = {len(s):,}")
    print("  safe top 10 TLD shares:     " + ", ".join(f"{t} {cs[t] / len(s):.3f}" for t, _ in cs.most_common(10)))
    print("  phishing top 10 TLD shares: " + ", ".join(f"{t} {cp[t] / len(p):.3f}" for t, _ in cp.most_common(10)))
    ls, lp = [len(d) for d in s], [len(d) for d in p]
    print(f"  domain length, mean / median: safe {statistics.mean(ls):.1f} / {statistics.median(ls):.0f} | "
          f"phishing {statistics.mean(lp):.1f} / {statistics.median(lp):.0f}")
    top = {t for t, _ in cs.most_common(10)} | {t for t, _ in cp.most_common(10)}
    for t in sorted(top):
        gap = abs(sh.get(t, 0) - ph.get(t, 0))
        if gap > TLD_GAP:
            any_flag = True
            print(f"  SHORTCUT FLAG: TLD '{t}' share differs by {gap * 100:.1f} points "
                  f"(safe {sh.get(t, 0):.3f}, phishing {ph.get(t, 0):.3f})")
    if abs(statistics.mean(ls) - statistics.mean(lp)) > LEN_GAP:
        any_flag = True
        print(f"  SHORTCUT FLAG: mean length differs by {abs(statistics.mean(ls) - statistics.mean(lp)):.1f} characters")
common = {t for t in set(map(tld, held_safe)) & set(map(tld, held_phish))}
print(f"\nAny shortcut flag: {any_flag}. TLDs occurring in both held-out classes: {len(common)}")
