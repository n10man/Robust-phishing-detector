"""Chunk 5: white-box hill-climb against a defended system (scoring only, VALIDATION DATA ONLY). Prints no URLs.

The attacker knows the system and edits real validation phishing URLs with the six edit operations of attacks.py
(Exp 10 settings: 15 rounds, 20 candidates per still-attacked URL per round, a candidate is kept only if it strictly
lowers the attacked score, seed 42) until the attacked score is below the stop level.
Pool: 500 validation phishing URLs (seed 42) caught by BOTH the plain model and the g2 guard at their own whole-system
levels (the same pool for every objective of one model, so the objectives are compared like for like).

Objectives (--objective):
  plain  attack the plain model score; stop below the plain threshold
  g2     attack the g2 guarded score (max over the full URL and the trimmed copies); stop below the g2 threshold
  stop   attack the plain model score; stop below --stop (for example the lower edge of an abstain window)

    PYTHONHASHSEED=0 .venv/bin/python notebooks/adaptive_attack.py --tag 4a --objective g2 --out data_v2/adaptive_4a_g2.npz
Writes the per-URL scores of the starting and final URLs (all three copies) and their rule hits to the .npz (git-ignored).
"""
import argparse
import os
import random
import time
import numpy as np
from attacks import BASE_FAMILIES, load_benign_words
import defence_layers as dl
import defence_metrics as dm
from defence_scores import MODELS, load_cache, build_sets, TRAIN

ROUNDS, CANDIDATES, N_POOL, SEED = 15, 20, 500, 42
OPS = list(BASE_FAMILIES.items())

ap = argparse.ArgumentParser()
ap.add_argument("--tag", required=True, choices=list(MODELS))
ap.add_argument("--objective", required=True, choices=["plain", "g2", "stop"])
ap.add_argument("--stop", type=float, default=None, help="absolute stop level for --objective stop")
ap.add_argument("--out", required=True)
args = ap.parse_args()
if os.path.exists(args.out):
    raise SystemExit(f"{args.out} already exists; not overwriting.")
if (args.objective == "stop") != (args.stop is not None):
    raise SystemExit("--stop is required with, and only with, --objective stop")


def hill_climb(urls, score, stop, seed):
    rng = random.Random(seed)
    cur_url = list(urls)
    cur = np.array(score(cur_url))
    edits = np.zeros(len(urls), int)
    active = [i for i in range(len(urls)) if cur[i] >= stop]
    for r in range(1, ROUNDS + 1):
        if not active:
            break
        cands, owner = [], []
        for i in active:
            for _ in range(CANDIDATES):
                _, fn = rng.choice(OPS)
                cands.append(fn(cur_url[i], rng, BENIGN))
                owner.append(i)
        p = score(cands)
        best = {}
        for k, i in enumerate(owner):
            if p[k] < cur[i] and (i not in best or p[k] < p[best[i]]):
                best[i] = k
        for i, k in best.items():
            cur_url[i], cur[i] = cands[k], p[k]
            edits[i] += 1
        active = [i for i in active if cur[i] >= stop]
        print(f"  round {r}: {int((cur < stop).sum())} of {len(urls)} below the stop level, {len(active)} still being attacked", flush=True)
    return cur_url, cur, edits


BENIGN = load_benign_words(TRAIN)
cfg = MODELS[args.tag]
scorer = dl.make_scorer(cfg["model"], cfg["recipe"])
cache = load_cache(args.tag)
target = dm.target_fpr()
plain_sc, g2_sc = dm.system_scores(cache, None, ["clean_safe", "clean_phish"]), dm.system_scores(cache, "g2", ["clean_safe", "clean_phish"])
thr_plain = dl.set_threshold(plain_sc["clean_safe"], target)[0]
thr_g2 = dl.set_threshold(g2_sc["clean_safe"], target)[0]
phish = build_sets()["clean_phish"]
eligible = np.flatnonzero((plain_sc["clean_phish"] >= thr_plain) & (g2_sc["clean_phish"] >= thr_g2))
pool_idx = np.random.default_rng(SEED).choice(eligible, size=N_POOL, replace=False)
pool = [phish[i] for i in pool_idx]
print(f"model {args.tag}, objective {args.objective}: plain threshold {thr_plain:.4f}, g2 threshold {thr_g2:.4f}; "
      f"{len(eligible):,} eligible URLs, pool of {N_POOL}", flush=True)

if args.objective == "plain":
    score_fn, stop = scorer, thr_plain
elif args.objective == "g2":
    score_fn, stop = (lambda urls: dl.guarded_scores(urls, scorer, "g2")), thr_g2
else:
    score_fn, stop = scorer, args.stop
t0 = time.time()
final, cur, edits = hill_climb(pool, score_fn, stop, SEED)
print(f"hill-climb finished in {time.time() - t0:.0f} s", flush=True)

start3, final3 = dl.score_copies(pool, scorer), dl.score_copies(final, scorer)
np.savez(args.out, pool_idx=pool_idx, edits=edits, thr_plain=thr_plain, thr_g2=thr_g2, stop=stop,
         start_full=start3[0], start_noq=start3[1], start_nolast=start3[2],
         final_full=final3[0], final_noq=final3[1], final_nolast=final3[2],
         start_rules=dl.rule_matrix(pool), final_rules=dl.rule_matrix(final))
ev = cur < stop
print(f"\nEVASION of the attacked objective: {int(ev.sum())} of {N_POOL} = {ev.mean() * 100:.1f}% below the stop level {stop:.4f}; "
      f"mean edits per evading URL {edits[ev].mean() if ev.any() else float('nan'):.2f}")
plain_final = final3[0]
g2_final = dl.combine_guard(*final3, "g2")
print(f"Seen from the plain model: {int((plain_final < thr_plain).sum())} of {N_POOL} below its threshold; "
      f"seen from the g2 guard: {int((g2_final < thr_g2).sum())} of {N_POOL} below its threshold")
print(f"Saved {args.out}")
