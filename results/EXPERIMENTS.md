# Experiments log (v2)

Rules (from CLAUDE.md): tune on validation only, fixed seeds, one change per experiment, commit before and after, revert if validation does not improve, never open the sealed evaluation set or any test file. All numbers below are VALIDATION numbers from `notebooks/evaluate.py`.

How to read the tables: "false-alarm rate" = share of safe validation URLs flagged. "Recall at v1 false-alarm level" means the threshold is moved until the model flags 3.65% of safe validation URLs, the same share v1 flagged at 0.5. This is the fair way to compare models with different phishing shares or different threshold behaviour. Attack recalls use the families in `notebooks/attacks.py` (frozen), applied to the phishing validation URLs; "safe flagged" is the share of the SAME edit applied to 15,000 safe validation URLs that gets flagged (lower is better).

---

## Experiment 0: v1 baseline on the random split (the old starting line)

- **Hypothesis:** none, this is the reference. Known problem: the split was random per URL, so the same website can be in train and validation, which probably flatters the numbers.
- **Change:** none (existing v1 model `models/gradient_boosting.joblib`, evaluated with the new shared script).
- **Commands:**
  ```bash
  .venv/bin/python notebooks/evaluate.py
  ```
- **Data:** `data/val.csv` (75,065 URLs: 16,135 phishing, 58,930 safe). Output: `results/baseline_v1/`.
- **Validation metrics (threshold 0.5, which is also the 3.65% false-alarm level):**
  recall 0.9493, precision 0.8769, F1 0.9116, AUC 0.9920, false-alarm rate 0.0365 (2,151 false alarms, 818 missed).
  Attack recall: benign words in path 0.7308, in query 0.7046, lookalike 0.9409, subdomains 0.9665, shortening 0.9225, padding 0.9344, random mix 0.7620.
  Safe flagged after the same edits: path 0.0236, query 0.0076, lookalike 0.0367, subdomains 0.2337, shortening 0.0856, padding 0.1299, mix 0.1037.
  Bare-domain flag rate (Tranco): bare 0.9992 (top 10k) / 0.9997 (random); with `www.` 1.0 / 1.0; trailing slash 0.3055 / 0.4040; with `/index.html` 0.4517 / 0.5544.
- **Decision:** keep as the historical reference. Reproduces the frozen test-set numbers in `results/V1_BASELINE.md` to within about 1.5 points.
- **Commit:** 379b4db

---

## Experiment 1: same pipeline, split by website (the true starting line)

- **Hypothesis:** grouping the split by registered domain will lower the validation numbers, because validation sites are no longer in training.
- **The ONE change:** the train/val/test split. Everything else is the v1 recipe (11 features scaled, 1,000 binary character 3-grams fitted on train only, `HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)`, threshold 0.5).
- **Split:** `data/clean_urls.csv` (500,432 URLs, 158,760 registered domains, 21.49% phishing) split 70/15/15 with all URLs of one registered domain in the same split, seed 42. Sizes: train 350,302 (56,866 websites), val 75,065 (50,947), test 75,065 (50,947); phishing share 0.2149 in each. Leakage check: 0 shared registered domains between any two splits. Domains come from `tldextract` offline with private suffixes included (`notebooks/domains.py`). The test file was written once and not opened again.
- **Commands (run from the repo root):**
  ```bash
  .venv/bin/python notebooks/split_by_domain.py
  .venv/bin/python notebooks/train_v2split.py
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting.joblib --recipe models_v2/feature_recipe.joblib --val-file data_v2/val.csv --train-file data_v2/train.csv --own-target --out results/baseline_v2split
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting.joblib --recipe models_v2/feature_recipe.joblib --val-file data_v2/val.csv --train-file data_v2/train.csv --out results/baseline_v2split_at_v1_fpr
  ```
  `PYTHONHASHSEED=0` is needed: the attack word list in `attacks.py` depends on the order of tied words, which changes between runs on the new training file (it does not on the v1 file). Without it, attack recalls moved by up to 0.001 between identical runs.
- **Output:** `results/baseline_v2split/` (threshold 0.5, the model's own false-alarm level, 9.20%) and `results/baseline_v2split_at_v1_fpr/` (threshold 0.7428, the v1 false-alarm level, 3.65%).
- **Validation metrics:** `data_v2/val.csv`, 75,065 URLs: 16,135 phishing, 58,930 safe.

| Measure | Exp 0 (v1, random split) | Exp 1 at threshold 0.5 | Exp 1 at v1 false-alarm level (3.65%) |
|---|---|---|---|
| Recall | 0.9493 | 0.9260 | 0.8567 |
| False-alarm rate | 0.0365 | 0.0920 | 0.0365 |
| Precision (not comparable, see note) | 0.8769 | 0.7338 | 0.8653 |
| F1 | 0.9116 | 0.8188 | 0.8610 |
| AUC | 0.9920 | 0.9743 | 0.9743 |
| Attack recall: path words | 0.7308 | 0.6591 | 0.5557 |
| Attack recall: query words | 0.7046 | 0.6015 | 0.4974 |
| Attack recall: lookalike | 0.9409 | 0.9154 | 0.8351 |
| Attack recall: subdomains | 0.9665 | 0.9540 | 0.8959 |
| Attack recall: shortening | 0.9225 | 0.9025 | 0.8116 |
| Attack recall: padding | 0.9344 | 0.9072 | 0.8165 |
| Attack recall: random mix | 0.7620 | 0.6890 | 0.5794 |
| Safe flagged: subdomains | 0.2337 | 0.3632 | 0.2012 |
| Safe flagged: padding | 0.1299 | 0.2633 | 0.1292 |
| Safe flagged: random mix | 0.1037 | 0.1709 | 0.0923 |
| Bare domain flagged (top 10k / random) | 0.9992 / 0.9997 | 0.9906 / 0.9984 | 0.9717 / 0.9862 |
| Trailing slash flagged | 0.3055 / 0.4040 | 0.3632 / 0.4553 | 0.1521 / 0.2141 |
| `/index.html` flagged | 0.4517 / 0.5544 | 0.5923 / 0.6920 | 0.3492 / 0.4434 |

  Note on precision: precision depends on the phishing share of the evaluation set, so compare recall and false-alarm rate. Here the validation sets have the same phishing share, so precision is comparable too, but the decision uses recall at a matched false-alarm rate.
- **What the numbers mean (honest reading):** the numbers dropped. At the same false-alarm level (3.65%) recall falls from 0.949 to 0.857 (about 9 points). At threshold 0.5, recall falls 2.3 points and the false-alarm rate rises from 3.65% to 9.20% (2.5 times as many safe URLs flagged). AUC falls from 0.992 to 0.974. Attack recalls at threshold 0.5 fall 1 to 10 points (the two word-adding attacks fall most). Bare domains are still flagged almost every time. The most likely reason is that v1 partly recognised websites it had already seen in training. Caveat: this is not a pure measure of leakage. The grouped validation set also differs in make-up: the biggest sites all went to train, so validation is mostly small sites with few URLs each, which is probably harder.
- **Other caveats:** the attack word list is rebuilt from the new training file, so it differs from Exp 0's list; the Tranco sample drops domains that appear exactly in the training file (9,824 and 9,989 left, against 9,839 and 9,973 for Exp 0), so the two Tranco samples are not identical.
- **Decision:** KEEP as the new starting line for all v2 experiments. This is a correction of the evaluation, not a model improvement. Owner's decision (2026-10-29): all later experiments are judged at the fixed v1 false-alarm level of 3.65% (the default of `evaluate.py`, do not change it), and the threshold-0.5 rows are reported alongside.
- **Commit:** the commit that adds this file (see `git log -- results/EXPERIMENTS.md`)

---

## Sealed evaluation set (built, not used)

- Built by `notebooks/build_sealed_eval.py`, written outside the repo, never opened or used for any result. Rows after each step: loaded 295,018; conflicting labels removed 294,930; duplicates removed 289,672; registered domain also in Kaggle removed 270,487; at most 5 per registered domain 236,990 (111,959 phishing, 125,031 safe). Shared registered domains with the Kaggle data: 0.
- **Warning:** path share differs a lot between classes: phishing 0.375, safe 0.000 (every safe URL is a bare domain). A model can cheat on that, and v1 flags nearly all bare domains, so read any future result split by bare versus has-a-path, and by source (side file `sealed_eval_source.csv`). The set cannot test safe URLs that have a path. `sealed_domains_hashed.txt` holds SHA-256 hashes of its registered domains for later overlap checks.

---

## Chunk 2 decision rules (fixed BEFORE any Chunk 2 result; they cannot change after a result is seen)

State when fixed: branch `v2`, HEAD `a0825f5`, no Chunk 2 experiment run yet. The only Chunk 2 numbers that existed were read-only counts and a 3,000-sample check of the Exp 1 model on bare domains (see below).

All comparisons are against the control: the model kept from the previous experiment, evaluated on the same data. Decisions use the fixed v1 false-alarm level of 3.65% (each model's own matched threshold). Threshold-0.5 rows are reported but never used for a decision.

**Experiment 2 (privacy redaction).** Keep only if recall at 3.65% on the redacted validation set drops by no more than 0.5 point against the control. It is a privacy fix, so a very small cost is accepted. Little change is expected (0.4% of train rows and 0.1% of val rows contain an email-like string).

**Experiment 3 (bare domains in training).** Up to 3 sizes (5k+5k, 20k+20k, 50k+50k per class). Keep the best variant only if ALL of these hold:
- (a) the held-out safe bare flag rate falls by at least 10 points (percentage points, against the control);
- (b) recall at 3.65% on the standard validation set drops by no more than 1 point;
- (c) the held-out bare phishing catch rate drops by no more than 2 points.

"Best" = the lowest held-out safe bare flag rate among variants that pass (a), (b) and (c). If none passes, revert.

**Rule (c) was relaxed from "must not fall" to "may drop by at most 2 points" before any result.** Why: the Exp 1 model flags nearly every bare domain as phishing (known flaw, 99.9% on the Tranco check). On a 3,000-domain sample of held-out-eligible bare domains it caught 99.9% of phishing at threshold 0.5 and 99.3% at the 3.65% level, and flagged 99.7% / 98.6% of the safe ones. That catch rate is inflated by the flaw: catching bare phishing is nearly free when everything bare is called phishing. A strict "must not fall" rule would therefore revert any variant that starts letting bare safe domains through, however good. The 2-point tolerance was set by the owner on 2026-10-29, before any experiment was run.

**Locked.** Rules (a), (b), (c) and the Exp 2 keep-rule (0.5 point) were approved by the owner on 2026-10-29 and cannot change after any result is seen. "Bare" means the host equals its registered domain on the public suffix list only (hosting-platform suffixes such as workers.dev are NOT counted, so `foo.workers.dev` is not bare). Website grouping for leakage checks keeps the Chunk 1 rule (private suffixes included).

**Shortcut check (owner request).** `build_bare_sets.py` prints, counts only, for the training additions and the held-out sets, per class: the top 10 TLD shares and the mean and median domain length. If any TLD share differs between safe and phishing by more than 20 points, or the mean length by more than 3 characters, it is reported and the held-out results are ALSO reported restricted to TLDs that occur in both classes. This check does not change the decision rules above.

**The held-out bare sets are validation data, not final evidence.** They are used to choose the variant (and whether to keep it), so a result on them is a selection result. Final evidence needs a set that was not used for any choice.

Not fixed by the owner, my reading, stated here so it can be corrected before any result: the 10-point fall in (a) is measured in percentage points of the held-out safe bare flag rate at the matched threshold; the held-out sets are 10,000 safe and 10,000 phishing bare domains chosen at random (seed 42), used for evaluation only.

---

## Experiment 2: privacy redaction

- **Hypothesis:** replacing email addresses with a placeholder before feature extraction does not hurt detection and removes personal data from training. Little change expected.
- **The ONE change:** the training and validation URLs are passed through `redact_url` (`notebooks/privacy.py`) before the 11 features are computed. It replaces email-like text after the host part with the token `redactedemail`; the host part is untouched. Percent-encoded emails are not caught. Everything else is the Exp 1 recipe.
- **Counts:** train 1,363 of 350,302 rows changed (0.39%), val 79 of 75,065 (0.11%); 0 email-like strings remain after the host in either file. 18 rows (14 train, 4 val) have an `@` in the host part and were left alone. The 54 git-tracked text files contain no email-like text. Rows that were not changed keep byte-identical features.
- **Commands (from the repo root, baseline = Exp 1 model):**
  ```bash
  .venv/bin/python notebooks/make_redacted_v2.py
  .venv/bin/python notebooks/train_variant.py --train-file data_v2/train_redacted.csv --suffix redacted
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting.joblib --recipe models_v2/feature_recipe.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train.csv --out results/exp2_control
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_redacted.joblib --recipe models_v2/feature_recipe_redacted.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train.csv --out results/exp2_redacted
  ```
  Both evaluations use the same `--train-file data_v2/train.csv` (attack words, Tranco exclusion) so only the model differs. The control is the Exp 1 model scored on the redacted validation file.
- **Validation metrics** (`data_v2/val_redacted.csv`: 16,135 phishing, 58,930 safe):

| Measure | Control (Exp 1 model) | Redacted model | Change |
|---|---|---|---|
| Recall at 3.65% false-alarm level (decision) | 0.8570 | 0.8578 | +0.08 pt |
| Recall at threshold 0.5 | 0.9262 | 0.9257 | -0.05 pt |
| False-alarm rate at 0.5 | 0.0920 | 0.0927 | +0.07 pt |
| Precision at 3.65% / F1 at 3.65% | 0.8654 / 0.8612 | 0.8655 / 0.8616 | |
| AUC | 0.9743 | 0.9745 | |
| Attack recall (3.65%): path / query / mix | 0.5557 / 0.4972 / 0.5791 | 0.5472 / 0.5331 / 0.5883 | -0.85 / +3.59 / +0.92 pt |
| Attack recall (3.65%): lookalike / subdomains / shortening / padding | 0.8354 / 0.8961 / 0.8120 / 0.8165 | 0.8374 / 0.8995 / 0.8141 / 0.8164 | within +-0.4 pt |
| Bare domain flagged at 3.65% (top 10k / random) | 0.9717 / 0.9862 | 0.9657 / 0.9821 | -0.6 / -0.4 pt |

- **Decision rule (fixed before the result):** keep if recall at 3.65% drops by no more than 0.5 point. It rose by 0.08 point.
- **Decision: KEEP.** The redacted model becomes the baseline for Experiment 3.
- **Honest reading:** this is a privacy fix and the accuracy effect is within noise. The clean-set differences are under 0.1 point. Some attack recalls moved by up to 3.6 points (query words +3.59, path words -0.85) in both directions; these are single-run, single-seed differences from refitting a model, not evidence that redaction helps or hurts. The rule did not use them.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 3: bare domains in training

- **Hypothesis:** adding balanced bare-domain examples (Kaggle format: no scheme, no `www.`, no trailing slash) lowers the share of unseen safe bare domains flagged as phishing without costing standard recall.
- **The ONE change:** extra training rows added to the Exp 2 training data (`data_v2/train_redacted.csv`). Everything else is the Exp 2 recipe. Up to 3 sizes: 5k+5k, 20k+20k, 50k+50k per class (nested random samples, seed 42).
- **Data:** safe = Tranco domains that are their own registered domain on the strict public suffix list; phishing = hosts from the phishing-domains list after stripping `www.`, same test. Phishing: 370,535 lines, 370,433 unique, 369,998 with valid characters, 111,349 bare (258,649 dropped as not bare), 68 removed for being in the Tranco top 100k, 286 domains found in both lists removed from both pools (label conflict). Then removed: in the sealed set (hash check) 11,085 phishing / 38,301 safe; in Kaggle val or test 111 / 15,484. Training-eligible 99,799 phishing / 945,913 safe. Held-out: 10,000 safe + 10,000 phishing bare domains (seed 42) chosen only from domains absent from Kaggle, never trained on.
- **Leakage check (all 0):** additions vs val websites, vs test websites (inferred as Kaggle minus train minus val; the test file was not opened), vs sealed set (hash); held-out vs additions, vs all Kaggle websites, vs sealed set; safe vs phishing within held-out and within additions.
- **Shortcut check (counts only, `build_bare_sets.py`): ONE FLAG, on length.** In all four sets (5k, 20k, 50k, held-out) the mean domain length differs by 3.5 to 3.7 characters (safe 13.7, phishing 17.3; medians 13 and 16), above the 3-character limit. No TLD share differs by more than 20 points (`com` about 5 points; tk, xyz, top, ml, ga occur almost only in phishing at 2 to 3% each). So the held-out results are also reported restricted to TLDs that occur in both classes (40 TLDs with at least 20 domains in each class; 8,219 safe and 8,158 phishing), and, as an extra diagnostic that is NOT part of the decision rules, by domain-length bucket.
- **Commands (from the repo root; `PYTHONHASHSEED=0` on every evaluation):**
  ```bash
  .venv/bin/python notebooks/build_bare_sets.py
  .venv/bin/python notebooks/train_variant.py --train-file data_v2/train_redacted.csv --extra-file data_v2/bare_train_5k.csv --suffix bare5k
  .venv/bin/python notebooks/train_variant.py --train-file data_v2/train_redacted.csv --extra-file data_v2/bare_train_20k.csv --suffix bare20k
  .venv/bin/python notebooks/train_variant.py --train-file data_v2/train_redacted.csv --extra-file data_v2/bare_train_50k.csv --suffix bare50k
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_redacted.joblib --recipe models_v2/feature_recipe_redacted.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --out results/exp3_control
  ```
  The three variant evaluations are the same command with `--model models_v2/gradient_boosting_bare5k.joblib` (or `bare20k`, `bare50k`), the matching `--recipe models_v2/feature_recipe_bare5k.joblib` (or `bare20k`, `bare50k`) and `--out results/exp3_5k` (or `exp3_20k`, `exp3_50k`). The control is the Exp 2 redacted model. Every run uses the same Tranco exclusion list (all domains of the 50k addition), so the Tranco samples are identical (9,331 and 9,493 domains).
- **Validation data:** `data_v2/val_redacted.csv` (16,135 phishing, 58,930 safe). The false-alarm level is the fixed 3.65% (each model's own matched threshold: 0.7456 control, 0.7363 / 0.7090 / 0.6701 for 5k / 20k / 50k). Threshold-0.5 rows are reported but not used for the decision.

**Decision rules (fixed before any result):**

| Rule | Control | 5k+5k | 20k+20k | 50k+50k |
|---|---|---|---|---|
| (a) held-out safe bare flagged must fall by at least 10 points | 0.9817 | 0.4571 (fall 52.5) PASS | 0.4175 (fall 56.4) PASS | 0.3920 (fall 59.0) PASS |
| (b) recall at 3.65% on standard validation drops by at most 1 point | 0.8578 | 0.8503 (drop 0.75) PASS | 0.8502 (drop 0.76) PASS | 0.8456 (drop 1.22) FAIL |
| (c) held-out bare phishing caught drops by at most 2 points | 0.9948 | 0.7409 (drop 25.4) FAIL | 0.7453 (drop 24.95) FAIL | 0.7538 (drop 24.1) FAIL |
| All three | | FAIL | FAIL | FAIL |

**Other results (3.65% level unless stated):**

| Measure | Control | 5k+5k | 20k+20k | 50k+50k |
|---|---|---|---|---|
| Training rows (phishing share) | 350,302 (0.2149) | 360,302 (0.2229) | 390,302 (0.2442) | 450,302 (0.2783) |
| Standard val: recall / precision / F1 | 0.8578 / 0.8655 / 0.8616 | 0.8503 / 0.8645 / 0.8573 | 0.8502 / 0.8645 / 0.8573 | 0.8456 / 0.8638 / 0.8546 |
| AUC | 0.9745 | 0.9734 | 0.9725 | 0.9715 |
| At threshold 0.5: recall / false alarms (rate) | 0.9257 / 5,460 (0.0927) | 0.9228 / 5,340 (0.0906) | 0.9145 / 4,880 (0.0828) | 0.9043 / 4,380 (0.0743) |
| At threshold 0.5: precision | 0.7323 | 0.7360 | 0.7515 | 0.7691 |
| Held-out, TLDs in both classes: safe flagged / phishing caught | 0.9860 / 0.9962 | 0.4873 / 0.7480 | 0.4414 / 0.7513 | 0.4166 / 0.7629 |
| Held-out at threshold 0.5: safe flagged / phishing caught | 0.9925 / 0.9994 | 0.8830 / 0.9703 | 0.8250 / 0.9637 | 0.7466 / 0.9471 |
| By length 0-10: safe flagged / phishing caught | 0.9846 / 0.9972 | 0.1214 / 0.2803 | 0.1085 / 0.2905 | 0.0785 / 0.3166 |
| By length 11-15 | 0.9831 / 0.9974 | 0.4411 / 0.6184 | 0.3843 / 0.6084 | 0.3444 / 0.5941 |
| By length 16-20 | 0.9783 / 0.9950 | 0.7101 / 0.8631 | 0.6668 / 0.8750 | 0.6677 / 0.8996 |
| By length 21 or more | 0.9743 / 0.9900 | 0.8430 / 0.9592 | 0.8390 / 0.9716 | 0.8376 / 0.9844 |
| Val bare URLs (2,045 phishing / 13,361 safe): recall / false alarm | 0.7467 / 0.0260 | 0.6870 / 0.0266 | 0.6944 / 0.0277 | 0.6660 / 0.0263 |
| Val URLs with a path (14,090 / 45,569): recall / false alarm | 0.8740 / 0.0396 | 0.8740 / 0.0394 | 0.8728 / 0.0391 | 0.8716 / 0.0395 |
| Tranco bare flagged, top 10k / random | 0.9659 / 0.9822 | 0.3000 / 0.4524 | 0.2678 / 0.4133 | 0.2315 / 0.3910 |
| Tranco bare flagged at 0.5, top 10k / random | 0.9812 / 0.9939 | 0.7849 / 0.8890 | 0.7149 / 0.8226 | 0.6102 / 0.7469 |
| Tranco trailing slash flagged, top 10k | 0.1533 | 0.0879 | 0.0597 | 0.0503 |
| Tranco `/index.html` flagged, top 10k | 0.3521 | 0.3364 | 0.3313 | 0.3307 |
| Attack recall: path / query / mix | 0.5472 / 0.5331 / 0.5883 | 0.5590 / 0.5149 / 0.5950 | 0.5695 / 0.5279 / 0.5985 | 0.5768 / 0.5666 / 0.6226 |
| Safe flagged after edit: subdomains / padding | 0.1949 / 0.1358 | 0.1977 / 0.1171 | 0.1807 / 0.1257 | 0.1876 / 0.1161 |

- **Decision: REVERT all three variants.** No variant passes (a), (b) and (c). The Exp 2 redacted model stays the baseline. The variant models and files are kept, not deleted.
- **What the results show, honestly:**
  - The bare-domain flaw does move: the share of held-out safe bare domains flagged falls from 98% to 39 to 46%, and the Tranco bare flag rate (top 10k) falls from 97% to 23 to 30%. That passes rule (a) by a wide margin.
  - It is not free. At the same 3.65% false-alarm level on standard validation, the model now catches only about 74 to 75% of held-out bare phishing (from 99.5%), a drop of about 24 to 25 points, which is far outside the 2-point tolerance of rule (c). The old 99.5% was inflated by the flaw, as noted in the rules; the new number is closer to what the model can really do on bare domains, and it is not good: at the 3.65% level it still flags 39 to 46% of unseen safe bare domains while missing about a quarter of bare phishing.
  - Length does a lot of the work. In the shortest bucket (10 characters or fewer) the 50k model flags 8% of safe and catches 32% of phishing; in the longest it flags 84% of safe and catches 98%. Within each bucket, phishing is still caught more often than safe is flagged (by 0.18 to 0.25 for 11 to 15 characters, for example), so there is some signal beyond length, but I cannot say how much, and the restricted-TLD results (safe 0.42 to 0.49, caught 0.75 to 0.76) are close to the full ones, so TLD is not the main driver.
  - More data costs more standard recall: recall at 3.65% falls from 0.8578 to 0.8503, 0.8502 and 0.8456. Bare validation URLs lose the most (recall 0.7467 to 0.666 to 0.694) while URLs with a path are unchanged (0.874 to 0.872). Precision at threshold 0.5 improves (0.7323 to 0.7691) because far fewer safe URLs are flagged there.
- **Caveats:** the held-out bare sets are used to choose the variant, so they count as validation data, not final evidence. The held-out safe set is Tranco-popular domains and the held-out phishing set comes from one feed, so part of any gain is separating popular-looking names from feed-looking names (the 3.5-character length gap is the visible sign), not proven generalisation to small real-world safe sites. Single run, single seed per variant; held-out rates carry about 0.5 point of noise at 10,000 per class. Adding balanced bare rows raises the phishing share of training (0.2149 to 0.2783 at 50k), which also shifts the thresholds.
- **Commit:** pending (not committed until the owner says so)

---

## Chunk 3 rules (better clues, Experiments 4 to 8): LOCKED before any Chunk 3 result

State when fixed: branch `v2`, HEAD `6cfcef8`, no Chunk 3 result existed. Approved by the owner on 2026-10-29; they cannot change after any result is seen.

- **Start:** the accepted Chunk 2 model `models_v2/gradient_boosting_redacted.joblib` (trained on `data_v2/train_redacted.csv`), evaluated on `data_v2/val_redacted.csv` at the fixed 3.65% false-alarm level; threshold-0.5 rows reported too.
- **One feature group per experiment**, added to the CURRENT accepted model (Chunk 2 model for Exp 4, then the model accepted last). Same training rows, same recipe, `HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)`, `PYTHONHASHSEED=0`. Max 2 variants per experiment; stop after Exp 8. Exp 3 additions stay unused.
- **KEEP only if ALL hold** against the current accepted model:
  1. Primary: recall at 3.65% rises by at least 0.5 point AND the paired bootstrap 95% interval for the recall difference excludes zero; OR alternative primary: the mean recall over the three word-edit attacks (path words, query words, random mix) rises by at least 3 points AND clean recall at 3.65% drops by at most 0.3 point.
  2. AUC does not fall by more than 0.002.
  3. The share of edited SAFE URLs flagged, at the matched threshold, under each of those three attacks rises by at most 2 points.
  Otherwise REVERT (files kept, model not used).
- **Bootstrap (fixed):** resample the phishing and the safe validation URLs separately, with replacement, 200 resamples, seed 42, the same indices for both models; in each resample each model's threshold is re-set to give 3.65% false alarms on the resampled safe URLs; difference = candidate minus current; interval = 2.5th to 97.5th percentile. "Rises by at least 0.5 point" is measured on the full validation set, and the interval must lie entirely above zero.
- **Tie-break:** if both variants of one experiment pass, keep the one with the higher recall at 3.65%; if equal to 4 decimals, the one with fewer features.
- **Decisions are computed, not judged:** `notebooks/decide_experiment.py` prints PASS/FAIL for each criterion and its output is pasted into each entry. The ablation retrains and the pipeline checks do not count as variants and carry no decisions.
- **Report only, no decision weight:** bare-domain held-out rates, bare-versus-path split, Tranco rates, length-bucket breakdown, the top 3 permutation importances of each group's new features (AUC drop, validation only), and each new feature's correlation with `url_length`.
- **Fixed parameters:** Exp 4a = +500 host-only 3-grams; Exp 4b = replace the whole-URL 3-grams with 1,000 host-only 3-grams. Exp 5: brand list = first N rows of `data/tranco_262W9.csv` reduced to registered-domain names (public suffix list only), de-duplicated, names of 4 or more characters; 5a N = 300 (257 names), 5b N = 100 (87 names). Exp 6 and Exp 7: one variant each. Exp 8a = replace the 3-gram block with 1,000 4-grams; 8b = keep the 3-grams and add 2,000 4-grams (if 4b was accepted, "the 3-gram block" is the host-only block).
- **Expectation stated before any result (Exp 4b):** it should raise recall under the word-adding attacks (the added harmless words no longer create harmless-looking 3-grams) but only partly, because the numeric clues still change; it should also lower clean recall, probably by more than the 0.3 point the alternative primary rule allows, so a revert is plausible.
- **Safety:** never read `~/sealed_eval/sealed_eval.csv`, `sealed_eval_source.csv` or `data_v2/test.csv`; no URL is fetched or opened; no pip install; nothing committed or pushed.

**Owner changes to the plan (2026-10-29, also locked before any result):**
1. **Exp 8b uses float64**, the same dtype as every other model (no float32 cast: a float32 cast once changed results in this project). 8b runs alone. If memory is a problem I stop and ask the owner. All feature matrices from `features_v2.py` are float64, like the old pipeline.
2. **Exp 5, brand list and the held-out sets:** the brand list comes from the same Tranco list as the held-out safe bare sets and the Tranco check, so brand-list domains can appear in those sets. For Exp 5 the bare-domain held-out rates and the Tranco rates are reported both ways: with all domains and without the brand-list domains (a domain is excluded if its registered-domain name is in the brand-name list used by that variant). Report only, no decision weight.
3. **Exp 5 and Exp 6 also report recall under the look-alike and the subdomain attacks, separately.** Report only. These attacks were designed by us, and the Exp 6 features (digits mixed into letter words) target the same trick the look-alike attack uses (swapping letters for digits), so this is NOT independent evidence.
4. **If the `//`-in-path feature of Exp 6 is accepted,** the log says it is a suspected dataset quirk (99% of training rows with `//` in the path are phishing).
5. Commit nothing, push nothing.

**Pipeline checks before Experiment 4 (done, nothing else changed):** `notebooks/features_v2.py` rebuilds the base recipe with the same vocabulary, the same scaler and an exactly equal matrix (float64) on 5,000 validation rows (`notebooks/check_features_v2.py`). The default `evaluate.py` still reproduces `results/baseline_v1`, `results/baseline_v2split` and `results/exp3_control` with 0 differing lines, and the Chunk 2 model rerun as `results/chunk3_base` (with saved scores) is identical to `results/exp3_control` in every file.

---

## Experiment 4: host/path separation

- **Hypothesis:** the current 3-grams are cut from the whole URL, so path words and host words mix; letting the model see host-only 3-grams should help it judge the site name apart from added path/query words.
- **Current accepted model:** the Chunk 2 model (`results/chunk3_base`). Everything else stays the same (same training rows `data_v2/train_redacted.csv`, same HistGradientBoostingClassifier settings, `PYTHONHASHSEED=0`).
- **The ONE change, two variants:** *4a* adds 500 host-only character 3-grams (host = text before the first `/`, `?` or `#`, without `user@` and the port; fitted on training hosts only; binary). *4b* replaces the 1,000 whole-URL 3-grams with 1,000 host-only 3-grams (path and query reach the model only through the 11 numeric counts).
- **Commands (from the repo root):**
  ```bash
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp4a --ngram-blocks url:3:1000,host:3:500
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp4b --ngram-blocks host:3:1000
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_exp4a.joblib --recipe models_v2/feature_recipe_exp4a.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_exp4a.npz --out results/exp4a_host500
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_exp4b.joblib --recipe models_v2/feature_recipe_exp4b.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_exp4b.npz --out results/exp4b_hostonly
  .venv/bin/python notebooks/decide_experiment.py --name exp4a --current-dir results/chunk3_base --current-scores data_v2/scores_chunk3_base.npz --candidate-dir results/exp4a_host500 --candidate-scores data_v2/scores_exp4a.npz
  .venv/bin/python notebooks/decide_experiment.py --name exp4b --current-dir results/chunk3_base --current-scores data_v2/scores_chunk3_base.npz --candidate-dir results/exp4b_hostonly --candidate-scores data_v2/scores_exp4b.npz
  PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp4a.joblib --recipe models_v2/feature_recipe_exp4a.joblib --group host3x500 --out results/exp4a_host500/feature_report.csv
  PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp4b.joblib --recipe models_v2/feature_recipe_exp4b.joblib --group host3x1000 --out results/exp4b_hostonly/feature_report.csv
  ```
  (The first feature-report run crashed on a pandas 3 `groupby.apply` bug in my script; I fixed the sampling line and reran. No numbers were affected.)
- **Validation data:** `data_v2/val_redacted.csv` (16,135 phishing, 58,930 safe), fixed false-alarm level 3.65%, threshold-0.5 rows also shown.

**Locked-rule result (printed by `decide_experiment.py`):**

| Criterion | 4a (+500 host 3-grams) | 4b (host-only 3-grams replace whole-URL ones) |
|---|---|---|
| (1) primary: recall rises >= 0.5 pt and bootstrap 95% interval excludes zero | 0.8578 to 0.8617 (+0.39 pt), interval [+0.04, +0.80] pt: FAIL (below 0.5 pt) | 0.8578 to 0.7000 (-15.78 pt), interval [-16.49, -14.86] pt: FAIL |
| (1) alternative: mean recall over path words / query words / random mix rises >= 3 pt and clean recall drops <= 0.3 pt | 0.5562 to 0.5887 (+3.25 pt), clean +0.39 pt: PASS | 0.5562 to 0.5837 (+2.75 pt), clean -15.78 pt: FAIL |
| (1) overall | PASS (through the alternative) | FAIL |
| (2) AUC falls by at most 0.002 | 0.9745 to 0.9745: PASS | 0.9745 to 0.9378: FAIL |
| (3) edited SAFE URLs flagged rise <= 2 pt | path words +0.77, query words +0.01, random mix +1.72: PASS | path words +8.01, query words +0.75, random mix +6.04: FAIL |
| **Decision** | **KEEP** | **REVERT** |

**Other numbers (report only; matched = the 3.65% level):**

| Measure | Base (Chunk 2) | 4a | 4b |
|---|---|---|---|
| Recall / precision / F1 at 3.65% | 0.8578 / 0.8655 / 0.8616 | 0.8617 / 0.8660 / 0.8639 | 0.7000 / 0.8400 / 0.7637 |
| Matched threshold | 0.7456 | 0.7399 | 0.8360 |
| At threshold 0.5: recall / false alarms | 0.9257 / 5,460 | 0.9256 / 5,363 | 0.8895 / 10,565 |
| Attack recall: path words / query words / random mix | 0.5472 / 0.5331 / 0.5883 | 0.5907 / 0.5540 / 0.6214 | 0.6873 / 0.4707 / 0.5931 |
| Attack recall: look-alike / subdomains | 0.8374 / 0.8995 | 0.8413 / 0.9030 | 0.6474 / 0.7879 |
| Attack recall: shortening / padding | 0.8141 / 0.8164 | 0.8145 / 0.8213 | 0.6364 / 0.5977 |
| Safe flagged after edit: subdomains / padding | 0.1949 / 0.1358 | 0.2097 / 0.1317 | 0.2646 / 0.0737 |
| Held-out bare: safe flagged / phishing caught | 0.9817 / 0.9948 | 0.9829 / 0.9938 | 0.9498 / 0.9769 |
| Held-out bare, TLDs in both classes | 0.9860 / 0.9962 | 0.9863 / 0.9946 | 0.9491 / 0.9735 |
| Held-out by length 0-10 / 11-15 | 0.9846 / 0.9972 and 0.9831 / 0.9974 | 0.9871 / 0.9981 and 0.9846 / 0.9968 | 0.9215 / 0.9786 and 0.9676 / 0.9880 |
| Held-out by length 16-20 / 21+ | 0.9783 / 0.9950 and 0.9743 / 0.9900 | 0.9806 / 0.9944 and 0.9662 / 0.9872 | 0.9492 / 0.9804 and 0.9283 / 0.9568 |
| Val bare URLs: recall / false alarm | 0.7467 / 0.0260 | 0.7506 / 0.0259 | 0.6406 / 0.0106 |
| Val URLs with a path: recall / false alarm | 0.8740 / 0.0396 | 0.8779 / 0.0396 | 0.7087 / 0.0441 |
| Tranco bare flagged (top 10k / random) | 0.9659 / 0.9822 | 0.9686 / 0.9816 | 0.8806 / 0.9440 |
| Tranco trailing slash / `/index.html` flagged (top 10k) | 0.1533 / 0.3521 | 0.1683 / 0.3322 | 0.0818 / 0.2600 |

**New-feature report (validation only, report only):**
- *4a*, 500 new columns, permutation importance as AUC drop on a 10,000-row sample: `host3:www` 0.00190, `host3:.uk` 0.00065, `host3:gov` 0.00058. Correlation with `url_length` over the 500 columns: median |r| 0.013, maximum 0.207 (the top three: -0.025, +0.017, -0.011), so they are not a length proxy. Importances are tiny (largest AUC drop under 0.002).
- *4b*, 1,000 new columns: `host3:com` 0.02915, `host3:www` 0.01343, `host3:org` 0.00989. Correlation with `url_length`: median |r| 0.011, maximum 0.228.

**Reading, honestly:**
- 4a is kept by the locked rules, but narrowly and through the alternative route. The clean-recall gain (+0.39 pt) is below the 0.5 pt the main route needs, although its bootstrap interval ([+0.04, +0.80] pt) sits just above zero. The three word-edit attacks improve by +4.35 (path words), +2.09 (query words) and +3.32 (random mix), a mean of +3.25 pt against the 3.00 needed. The cost is visible: random-mix safe URLs flagged +1.72 pt (limit 2.00) and subdomain-edited safe URLs +1.48 pt (not a rule criterion). The new columns that matter most describe the kind of site (`www`, `.uk`, `gov`), not phishing words.
- 4b behaves as I said it might on direction but was far worse in size. I expected clean recall to fall by more than the 0.3 pt allowed; it fell 15.8 pt and AUC fell 0.037. I expected the word-adding attacks to improve, partly: path words did (+14.0 pt) and random mix barely (+0.5 pt), but query words got WORSE (-6.2 pt). I did not investigate why; the model now depends on the numeric counts for the whole path and query, and everything else (look-alike -19.0, shortening -17.8, padding -21.9 pt) got much worse. Held-out safe bare domains are flagged less (0.95 vs 0.98) but at the cost of general recall, so this is not an improvement.
- Both variants rest on a single run per model (about 0.3 pt of noise on recall).
- **Decision: 4a KEEP, 4b REVERT.** The accepted model for Experiment 5 is `models_v2/gradient_boosting_exp4a.joblib` (recipe `feature_recipe_exp4a.joblib`, results `results/exp4a_host500`). Files for 4b are kept, not deleted.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 5: brand lookalike

- **Hypothesis:** phishing hosts often imitate a well-known site name with a small spelling change, or put a brand name in a subdomain or path of a different site; three clues about brand names should catch some of them.
- **Current accepted model:** Exp 4a (`results/exp4a_host500`; Chunk 2 recipe plus 500 host-only 3-grams). Same training rows, same classifier settings, `PYTHONHASHSEED=0`.
- **The ONE change, two variants:** add three numeric clues built from a brand list. Brand list = the first N rows of `data/tranco_262W9.csv` reduced to registered-domain names (public suffix list only), de-duplicated, names of 4 or more characters: *5a* N = 300 (257 names), *5b* N = 100 (87 names). Clues: `brand_edit_dist` (0 for an exact brand name, which is not a lookalike; 1 to 3 for the closest brand within 2 characters of the same length; 4 = none that close), `brand_in_subdomain`, `brand_in_path` (a brand name appears there while the registered domain is a different name).
- **Commands (from the repo root):**
  ```bash
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp5a --ngram-blocks url:3:1000,host:3:500 --numeric-groups brand --brand-n 300
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp5b --ngram-blocks url:3:1000,host:3:500 --numeric-groups brand --brand-n 100
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_exp5a.joblib --recipe models_v2/feature_recipe_exp5a.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_exp5a.npz --out results/exp5a_brand300
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_exp5b.joblib --recipe models_v2/feature_recipe_exp5b.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_exp5b.npz --out results/exp5b_brand100
  .venv/bin/python notebooks/decide_experiment.py --name exp5a --current-dir results/exp4a_host500 --current-scores data_v2/scores_exp4a.npz --candidate-dir results/exp5a_brand300 --candidate-scores data_v2/scores_exp5a.npz
  .venv/bin/python notebooks/decide_experiment.py --name exp5b --current-dir results/exp4a_host500 --current-scores data_v2/scores_exp4a.npz --candidate-dir results/exp5b_brand100 --candidate-scores data_v2/scores_exp5b.npz
  PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp5a.joblib --recipe models_v2/feature_recipe_exp5a.joblib --group brand300 --out results/exp5a_brand300/feature_report.csv
  PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp5b.joblib --recipe models_v2/feature_recipe_exp5b.joblib --group brand100 --out results/exp5b_brand100/feature_report.csv
  ```
- **Validation data:** `data_v2/val_redacted.csv`, fixed false-alarm level 3.65%; threshold-0.5 rows also shown.

**Locked-rule result (printed by `decide_experiment.py`):**

| Criterion | 5a (N = 300) | 5b (N = 100) |
|---|---|---|
| (1) primary: recall rises >= 0.5 pt and bootstrap interval excludes zero | 0.8617 to 0.8629 (+0.12 pt), interval [-0.18, +0.44] pt: FAIL | 0.8617 to 0.8615 (-0.02 pt), interval [-0.42, +0.30] pt: FAIL |
| (1) alternative: mean word-edit attack recall rises >= 3 pt, clean recall drops <= 0.3 pt | 0.5887 to 0.6076 (+1.89 pt): FAIL | 0.5887 to 0.6064 (+1.77 pt): FAIL |
| (2) AUC falls by at most 0.002 | 0.9745 to 0.9752: PASS | 0.9745 to 0.9748: PASS |
| (3) edited SAFE URLs flagged rise <= 2 pt | path words +1.60, query words +0.77, random mix +2.25: FAIL | path words +1.04, query words +0.77, random mix +1.95: PASS |
| **Decision** | **REVERT** | **REVERT** |

**Other numbers (report only; matched = the 3.65% level):**

| Measure | 4a (current) | 5a | 5b |
|---|---|---|---|
| Recall / precision / F1 at 3.65% | 0.8617 / 0.8660 / 0.8639 | 0.8629 / 0.8662 / 0.8645 | 0.8615 / 0.8660 / 0.8637 |
| At threshold 0.5: recall / false alarms | 0.9256 / 5,363 | 0.9265 / 5,334 | 0.9260 / 5,390 |
| Attack recall: path words / query words / random mix | 0.5907 / 0.5540 / 0.6214 | 0.6058 / 0.5738 / 0.6431 | 0.6142 / 0.5628 / 0.6421 |
| **Attack recall: look-alike (report only)** | 0.8413 | 0.8431 (+0.18 pt) | 0.8425 (+0.12 pt) |
| **Attack recall: subdomains (report only)** | 0.9030 | 0.9233 (+2.03 pt) | 0.9228 (+1.98 pt) |
| Safe flagged after the subdomain edit | 0.2097 | 0.2332 | 0.2461 |
| Attack recall: shortening / padding | 0.8145 / 0.8213 | 0.8167 / 0.8220 | 0.8130 / 0.8228 |
| Held-out bare, all: safe flagged / phishing caught | 0.9829 / 0.9938 | 0.9813 / 0.9956 | 0.9846 / 0.9961 |
| Held-out bare, WITHOUT brand-list domains | not applicable | 0.9822 / 0.9956 (9,983 safe, 9,995 phishing left) | 0.9849 / 0.9962 (9,992 / 9,995 left) |
| Held-out bare, TLDs in both classes | 0.9863 / 0.9946 | 0.9847 / 0.9964 | 0.9881 / 0.9967 |
| Held-out by length 0-10 / 11-15 / 16-20 / 21+ (safe flagged / caught) | 0.9871 / 0.9981; 0.9846 / 0.9968; 0.9806 / 0.9944; 0.9662 / 0.9872 | 0.9858 / 0.9981; 0.9844 / 0.9977; 0.9761 / 0.9960; 0.9635 / 0.9912 | 0.9901 / 0.9981; 0.9852 / 0.9988; 0.9814 / 0.9967; 0.9729 / 0.9908 |
| Val bare URLs: recall / false alarm | 0.7506 / 0.0259 | 0.7408 / 0.0253 | 0.7355 / 0.0254 |
| Val URLs with a path: recall / false alarm | 0.8779 / 0.0396 | 0.8806 / 0.0398 | 0.8798 / 0.0398 |
| Tranco bare flagged, top 10k / random (all) | 0.9686 / 0.9816 | 0.9613 / 0.9808 | 0.9671 / 0.9834 |
| Tranco bare flagged, WITHOUT brand-list domains | not applicable | 0.9701 / 0.9810 (8,854 / 9,482 left) | 0.9704 / 0.9835 (9,046 / 9,489 left) |
| Tranco trailing slash flagged, top 10k (all / without brand-list domains) | 0.1683 | 0.1644 / 0.1725 | 0.1749 / 0.1801 |
| Tranco `/index.html` flagged, top 10k (all / without brand-list domains) | 0.3322 | 0.3377 / 0.3480 | 0.3154 / 0.3197 |

**New-feature report (validation only, report only; AUC drop when shuffled, 20,000-row sample, 3 repeats):**
- *5a:* `brand_edit_dist` 0.00335 (correlation with `url_length` +0.014), `brand_in_path` 0.00087 (+0.201), `brand_in_subdomain` 0.00003 (+0.195). Median |r| 0.195.
- *5b:* `brand_edit_dist` 0.00328 (+0.006), `brand_in_path` 0.00037 (+0.100), `brand_in_subdomain` 0.00006 (+0.029). Median |r| 0.029.

**Reading, honestly:**
- Both variants are reverted by the locked rules. The clean-recall gain of 5a (+0.12 pt) is inside the bootstrap interval around zero, 5b shows none, and neither reaches the +3 pt attack gain. 5a also breaks criterion (3) (random mix +2.25 pt safe flagged against a limit of 2.00). AUC is a hair higher (+0.0007 and +0.0003), which is small.
- The brand-list domains hardly matter for the report-only numbers: removing them changes the held-out and Tranco rates by about 0.1 to 1.0 pt, so the brand list sharing a source with the held-out and Tranco sets is not what drives them.
- **Look-alike and subdomain attacks (report only, not independent evidence):** look-alike recall barely moves (+0.18 / +0.12 pt). Subdomain recall rises about 2 pt for both, but the same edit makes more SAFE URLs look bad (flagged 0.2097 to 0.2332 and 0.2461). These attacks were designed by us, and one of the eight words the subdomain attack uses (`mail`) is itself a brand name in both lists, so `brand_in_subdomain` can react to our own attack words.
- The most important new column, `brand_edit_dist`, is nearly uncorrelated with length (+0.014), but I have not checked whether it measures lookalikes or just the shape and length of the name (its mean on a sample was 2.9 of a maximum 4, so most names are "somewhat close" to some brand by chance). `brand_in_path` and `brand_in_subdomain` correlate about +0.2 with length for N = 300, so part of them is a length proxy.
- Single run, single seed per model (about 0.3 pt of noise on recall).
- **Decision: 5a REVERT, 5b REVERT.** The accepted model stays Exp 4a (`models_v2/gradient_boosting_exp4a.joblib`). Files for 5a and 5b are kept, not deleted.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 6: character tricks

- **Hypothesis:** phishing hosts and paths use character tricks (punycode, odd characters, digits swapped into words, `@` in the host, `//` in the path, hex-encoded characters) that the 3-grams do not isolate; six counts should catch some of them.
- **Current accepted model:** Exp 4a (`results/exp4a_host500`). Same training rows, classifier settings and `PYTHONHASHSEED=0`.
- **The ONE change (one variant):** add six numeric clues computed on the (redacted) URL: `punycode_count` (`xn--` in the host), `non_ascii_count`, `digit_word_count` (runs of 4 to 15 letters-and-digits with at least 3 letters and 1 or 2 digits, which catches `paypa1` or `g00gle` but not long hashes), `at_in_host`, `double_slash_path` (number of `//` after the host), `hex_encoded_count` (`%xx`). How common they are in `data_v2/train_redacted.csv` (rows): `xn--` 45, non-ASCII 409, `@` in host 14, `//` in path 1,094, `%xx` 11,427.
- **Commands (from the repo root):**
  ```bash
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp6 --ngram-blocks url:3:1000,host:3:500 --numeric-groups chartricks
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_exp6.joblib --recipe models_v2/feature_recipe_exp6.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_exp6.npz --out results/exp6_chartricks
  .venv/bin/python notebooks/decide_experiment.py --name exp6 --current-dir results/exp4a_host500 --current-scores data_v2/scores_exp4a.npz --candidate-dir results/exp6_chartricks --candidate-scores data_v2/scores_exp6.npz
  PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp6.joblib --recipe models_v2/feature_recipe_exp6.joblib --group chartricks --out results/exp6_chartricks/feature_report.csv
  ```
- **Validation data:** `data_v2/val_redacted.csv`, fixed false-alarm level 3.65%; threshold-0.5 rows also shown.

**Locked-rule result (printed by `decide_experiment.py`):**

| Criterion | Exp 6 |
|---|---|
| (1) primary: recall rises >= 0.5 pt and bootstrap interval excludes zero | 0.8617 to 0.8629 (+0.12 pt), interval [-0.22, +0.41] pt: FAIL |
| (1) alternative: mean word-edit attack recall rises >= 3 pt, clean recall drops <= 0.3 pt | 0.5887 to 0.5866 (-0.21 pt): FAIL |
| (2) AUC falls by at most 0.002 | 0.9745 to 0.9751: PASS |
| (3) edited SAFE URLs flagged rise <= 2 pt | path words -0.17, query words -0.07, random mix -1.55: PASS |
| **Decision** | **REVERT** |

**Other numbers (report only; matched = the 3.65% level), Exp 4a (current) to Exp 6:**
- Recall / precision / F1 at 3.65%: 0.8617 / 0.8660 / 0.8639 to 0.8629 / 0.8662 / 0.8645. At threshold 0.5: recall 0.9256 to 0.9264, false alarms 5,363 to 5,325.
- Attack recall: path words 0.5907 to 0.5894, query words 0.5540 to 0.5544, random mix 0.6214 to 0.6160, shortening 0.8145 to 0.8193, padding 0.8213 to 0.8306.
- **Look-alike attack recall (report only): 0.8413 to 0.8493 (+0.80 pt). Subdomain attack recall (report only): 0.9030 to 0.8991 (-0.39 pt).** The look-alike attack was designed by us (it swaps a letter for a digit in suspicious words), and the `digit_word_count` clue targets the same trick (a word with 1 or 2 digits among letters), so this is NOT independent evidence. Even so, the gain is under 1 pt.
- Held-out bare, safe flagged / phishing caught: all 0.9829 / 0.9938 to 0.9874 / 0.9976; TLDs in both classes 0.9863 / 0.9946 to 0.9912 / 0.9980. By length 0-10 / 11-15 / 16-20 / 21+: 0.9914 / 0.9991; 0.9869 / 0.9982; 0.9872 / 0.9973; 0.9783 / 0.9964.
- Val bare URLs: recall / false alarm 0.7506 / 0.0259 to 0.7457 / 0.0255. Val URLs with a path: 0.8779 / 0.0396 to 0.8799 / 0.0397.
- Tranco bare flagged (top 10k / random): 0.9686 / 0.9816 to 0.9727 / 0.9859. Trailing slash (top 10k): 0.1683 to 0.1868. `/index.html` (top 10k): 0.3322 to 0.3247.

**New-feature report (validation only, report only; AUC drop when shuffled, 20,000-row sample, 3 repeats):**
- `digit_word_count` 0.00164 (correlation with `url_length` +0.223), `double_slash_path` 0.00018 (+0.025), `non_ascii_count` 0.00012 (+0.008), `hex_encoded_count` 0.00002 (+0.226), `punycode_count` 0.00000 (-0.001), `at_in_host` 0.00000 (0.000). Median |r| 0.016, maximum 0.226.

**Reading, honestly:**
- Reverted by the locked rules: the clean-recall gain (+0.12 pt) is inside the bootstrap interval around zero and the word-edit attacks do not improve. Only one of the six clues does anything measurable (`digit_word_count`, AUC drop 0.0016, and it correlates +0.22 with URL length, so part of it may be a length proxy). The rare tricks (`xn--`, `@` in host, non-ASCII) have a permutation importance of about zero, as I expected from how rare they are in this old data.
- `double_slash_path` has a 99% phishing share in training (1,094 rows) but almost no importance (0.00018): the 3-grams probably already carry it (not checked). The suspected dataset quirk therefore does not enter the model through this feature; it was not accepted, so no `//` note is needed in the accepted model.
- Single run, single seed (about 0.3 pt of noise on recall).
- **Decision: REVERT.** The accepted model stays Exp 4a. Files for Exp 6 are kept, not deleted.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 7: name randomness

- **Hypothesis:** throw-away phishing domains often look random (odd letter mix, long runs of consonants, digits), so four numbers describing how random the registered-domain name looks should help.
- **Current accepted model:** Exp 4a (`results/exp4a_host500`). Same training rows, classifier settings and `PYTHONHASHSEED=0`.
- **The ONE change (one variant):** add four numeric clues on the registered-domain name (public suffix list only): `name_entropy` (Shannon entropy of its characters), `name_vowel_ratio`, `name_max_consonant_run` (longest run of consonant letters), `name_digit_ratio`.
- **Commands (from the repo root):**
  ```bash
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp7 --ngram-blocks url:3:1000,host:3:500 --numeric-groups randomness
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_exp7.joblib --recipe models_v2/feature_recipe_exp7.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_exp7.npz --out results/exp7_randomness
  .venv/bin/python notebooks/decide_experiment.py --name exp7 --current-dir results/exp4a_host500 --current-scores data_v2/scores_exp4a.npz --candidate-dir results/exp7_randomness --candidate-scores data_v2/scores_exp7.npz
  PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp7.joblib --recipe models_v2/feature_recipe_exp7.joblib --group randomness --out results/exp7_randomness/feature_report.csv
  ```
- **Validation data:** `data_v2/val_redacted.csv`, fixed false-alarm level 3.65%; threshold-0.5 rows also shown.

**Locked-rule result (printed by `decide_experiment.py`):**

| Criterion | Exp 7 |
|---|---|
| (1) primary: recall rises >= 0.5 pt and bootstrap interval excludes zero | 0.8617 to 0.8599 (-0.18 pt), interval [-0.51, +0.12] pt: FAIL |
| (1) alternative: mean word-edit attack recall rises >= 3 pt, clean recall drops <= 0.3 pt | 0.5887 to 0.6057 (+1.70 pt), clean -0.18 pt: FAIL |
| (2) AUC falls by at most 0.002 | 0.9745 to 0.9746: PASS |
| (3) edited SAFE URLs flagged rise <= 2 pt | path words -0.07, query words +0.22, random mix +1.42: PASS |
| **Decision** | **REVERT** |

**Other numbers (report only; matched = the 3.65% level), Exp 4a (current) to Exp 7:**
- Recall / precision / F1 at 3.65%: 0.8617 / 0.8660 / 0.8639 to 0.8599 / 0.8658 / 0.8628. At threshold 0.5: recall 0.9256 to 0.9283, false alarms 5,363 to 5,536.
- Attack recall: path words 0.5907 to 0.5893, query words 0.5540 to 0.5818, random mix 0.6214 to 0.6460, look-alike 0.8413 to 0.8408, subdomains 0.9030 to 0.9226 (safe flagged after that edit 0.2097 to 0.2409), shortening 0.8145 to 0.8134, padding 0.8213 to 0.8217.
- Held-out bare, safe flagged / phishing caught: all 0.9829 / 0.9938 to 0.9810 / 0.9918; TLDs in both classes 0.9863 / 0.9946 to 0.9833 / 0.9917. By length 0-10 / 11-15 / 16-20 / 21+: 0.9901 / 0.9991; 0.9835 / 0.9985; 0.9757 / 0.9940; 0.9526 / 0.9768.
- Val bare URLs: recall / false alarm 0.7506 / 0.0259 to 0.7467 / 0.0246. Val URLs with a path: 0.8779 / 0.0396 to 0.8764 / 0.0400.
- Tranco bare flagged (top 10k / random): 0.9686 / 0.9816 to 0.9704 / 0.9795. Trailing slash (top 10k): 0.1683 to 0.1677. `/index.html` (top 10k): 0.3322 to 0.3504.

**New-feature report (validation only, report only; AUC drop when shuffled, 20,000-row sample, 3 repeats):**
- `name_entropy` 0.00173 (correlation with `url_length` +0.103), `name_max_consonant_run` 0.00073 (+0.022), `name_digit_ratio` 0.00062 (-0.023), `name_vowel_ratio` 0.00020 (+0.047). Median |r| 0.035, maximum 0.103, so these are not a length proxy.

**Reading, honestly:**
- Reverted by the locked rules. The clean recall at 3.65% does not improve (-0.18 pt, inside the noise), the word-edit attack gains are real but small (query words +2.78, random mix +2.46, path words -0.14; mean +1.70 against the 3.00 needed). At threshold 0.5 recall rises 0.27 pt but 173 more safe URLs are flagged (5,363 to 5,536), which is not an improvement. The randomness clues carry some signal (name entropy is the strongest, AUC drop 0.0017) but the existing n-grams seem to cover most of it.
- Subdomain-attack recall rises +1.96 pt but the same edit flags 3.1 pt more SAFE URLs (report only).
- Single run, single seed (about 0.3 pt of noise on recall).
- **Decision: REVERT.** The accepted model stays Exp 4a. Files for Exp 7 are kept, not deleted.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 8: longer n-grams

- **Hypothesis:** 4-character chunks capture longer patterns (`.php`, `/wp-`, `.com/`) that 3-character chunks only see in pieces, so they should help the model.
- **Current accepted model:** Exp 4a (`results/exp4a_host500`: base recipe plus 500 host-only 3-grams). Exp 4b was reverted, so "the 3-gram block" is the whole-URL block. Same training rows, classifier settings and `PYTHONHASHSEED=0`; matrices are float64 as the owner required.
- **The ONE change, two variants:** *8a* replaces the 1,000 whole-URL 3-grams with 1,000 whole-URL 4-grams (the host block stays); *8b* keeps the 3-grams and adds 2,000 whole-URL 4-grams (3,511 columns in total).
- **Commands (from the repo root):**
  ```bash
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp8a --ngram-blocks url:4:1000,host:3:500
  /usr/bin/time -l env PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp8b --ngram-blocks url:3:1000,host:3:500,url:4:2000
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_exp8a.joblib --recipe models_v2/feature_recipe_exp8a.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_exp8a.npz --out results/exp8a_ngram4
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_exp8b.joblib --recipe models_v2/feature_recipe_exp8b.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_exp8b.npz --out results/exp8b_ngram34
  .venv/bin/python notebooks/decide_experiment.py --name exp8a --current-dir results/exp4a_host500 --current-scores data_v2/scores_exp4a.npz --candidate-dir results/exp8a_ngram4 --candidate-scores data_v2/scores_exp8a.npz
  .venv/bin/python notebooks/decide_experiment.py --name exp8b --current-dir results/exp4a_host500 --current-scores data_v2/scores_exp4a.npz --candidate-dir results/exp8b_ngram34 --candidate-scores data_v2/scores_exp8b.npz
  PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp8a.joblib --recipe models_v2/feature_recipe_exp8a.joblib --group url4x1000 --out results/exp8a_ngram4/feature_report.csv
  PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp8b.joblib --recipe models_v2/feature_recipe_exp8b.joblib --group url4x2000 --out results/exp8b_ngram34/feature_report.csv
  ```
- **Memory (8b ran alone, as required):** the 350,302 x 3,511 float64 matrix is 9.8 GB. The run finished without error in 319 seconds; the measured maximum resident size was 7.6 GB, but the peak memory footprint was 26.9 GB, above the 24 GB of the machine, so macOS compressed or swapped memory during the run. I judged this not to be a failure (the owner's instruction was to stop and ask if memory is a problem), but it is the limit of this machine for this recipe.
- **Validation data:** `data_v2/val_redacted.csv`, fixed false-alarm level 3.65%; threshold-0.5 rows also shown.

**Locked-rule result (printed by `decide_experiment.py`):**

| Criterion | 8a (4-grams replace 3-grams) | 8b (3-grams + 2,000 4-grams) |
|---|---|---|
| (1) primary: recall rises >= 0.5 pt and bootstrap interval excludes zero | 0.8617 to 0.8490 (-1.28 pt), interval [-1.79, -0.83] pt: FAIL | 0.8617 to 0.8752 (+1.35 pt), interval [+0.94, +1.69] pt: PASS |
| (1) alternative: mean word-edit attack recall rises >= 3 pt, clean recall drops <= 0.3 pt | 0.5887 to 0.5066 (-8.22 pt): FAIL | 0.5887 to 0.5262 (-6.25 pt): FAIL |
| (1) overall | FAIL | PASS (through the primary) |
| (2) AUC falls by at most 0.002 | 0.9745 to 0.9723 (-0.0022): FAIL | 0.9745 to 0.9773 (+0.0028): PASS |
| (3) edited SAFE URLs flagged rise <= 2 pt | path words -1.03, query words -0.26, random mix -1.85: PASS | path words -1.10, query words -0.53, random mix -2.90: PASS |
| **Decision** | **REVERT** | **KEEP** |

Only 8b passes, so the tie-break was not needed.

**Other numbers (report only; matched = the 3.65% level), Exp 4a (current) / 8a / 8b:**

| Measure | 4a | 8a | 8b |
|---|---|---|---|
| Recall / precision / F1 at 3.65% | 0.8617 / 0.8660 / 0.8639 | 0.8490 / 0.8643 / 0.8566 | 0.8752 / 0.8678 / 0.8715 |
| Matched threshold | 0.7399 | 0.7647 | 0.7272 |
| At threshold 0.5: recall / false alarms | 0.9256 / 5,363 | 0.9264 / 5,865 | 0.9307 / 4,985 |
| Attack recall: path words / query words / random mix | 0.5907 / 0.5540 / 0.6214 | 0.4993 / 0.4788 / 0.5416 | 0.4987 / 0.5270 / 0.5531 |
| Attack recall: look-alike / subdomains | 0.8413 / 0.9030 | 0.8274 / 0.8761 | 0.8569 / 0.9091 |
| Attack recall: shortening / padding | 0.8145 / 0.8213 | 0.8009 / 0.7947 | 0.8331 / 0.8057 |
| Safe flagged after edit: path words / query words / random mix | 0.0233 / 0.0091 / 0.1079 | 0.0131 / 0.0065 / 0.0893 | 0.0123 / 0.0038 / 0.0789 |
| Held-out bare: safe flagged / phishing caught | 0.9829 / 0.9938 | 0.9919 / 0.9949 | 0.9903 / 0.9963 |
| Held-out bare, TLDs in both classes | 0.9863 / 0.9946 | 0.9914 / 0.9953 | 0.9898 / 0.9961 |
| Held-out by length 0-10 / 11-15 / 16-20 / 21+ | 0.9871 / 0.9981; 0.9846 / 0.9968; 0.9806 / 0.9944; 0.9662 / 0.9872 | 0.9983 / 1.0000; 0.9953 / 0.9977; 0.9845 / 0.9967; 0.9729 / 0.9868 | 0.9961 / 1.0000; 0.9949 / 0.9977; 0.9819 / 0.9977; 0.9689 / 0.9912 |
| Val bare URLs: recall / false alarm | 0.7506 / 0.0259 | 0.7311 / 0.0237 | 0.7457 / 0.0271 |
| Val URLs with a path: recall / false alarm | 0.8779 / 0.0396 | 0.8661 / 0.0403 | 0.8940 / 0.0393 |
| Tranco bare flagged (top 10k / random) | 0.9686 / 0.9816 | 0.9883 / 0.9906 | 0.9895 / 0.9898 |
| Tranco trailing slash / `/index.html` flagged (top 10k) | 0.1683 / 0.3322 | 0.1552 / 0.2868 | 0.1662 / 0.4023 |

**New-feature report (validation only, report only; AUC drop when shuffled, 10,000-row sample, 1 repeat):**
- *8a* (1,000 columns): `url4:com/` 0.01181 (correlation with `url_length` +0.084), `url4:.php` 0.00601 (+0.148), `url4:/wp-` 0.00541 (+0.096). Median |r| 0.039, maximum 0.331.
- *8b* (2,000 new columns): `url4:com/` 0.00858 (+0.084), `url4:.asp` 0.00128 (+0.069), `url4:2011` 0.00113 (+0.199). Median |r| 0.034, maximum 0.331.

**Reading, honestly:**
- 8b is kept by the locked rules, and the clean gain is real by the rules' own measure: +1.35 pt recall at 3.65% (interval entirely above zero), AUC +0.0028, and at threshold 0.5 the false alarms fall from 5,363 to 4,985 while recall rises 0.5 pt. Compared with the Chunk 2 model (recall 0.8578) the accepted model is now at 0.8752.
- **The cost, which the locked rules do not weigh:** recall under the word-adding attacks falls (path words 0.5907 to 0.4987, -9.20 pt; query words -2.70 pt; random mix -6.84 pt; mean -6.25 pt). The model is better on clean URLs and more easily fooled by harmless words. Criterion (3) only watches safe URLs flagged, which also fell, so it could not catch this. For a project about robustness this is a real trade-off and the owner should decide whether to accept it; the rules as written keep 8b. Shortening, look-alike and subdomain attacks improve a little, padding gets worse (-1.56 pt).
- The bare-domain flaw gets slightly worse (Tranco bare flagged top 10k 0.9686 to 0.9895; held-out safe bare flagged 0.9829 to 0.9903).
- The most important new column is `url4:com/` (a domain ending in `.com/`, probably keyed on trailing-slash URLs), and `url4:2011` is a year. Both look like quirks of this old data and may not generalise; I did not test that.
- 8a (replacing the 3-grams) is clearly worse on every locked measure and is reverted.
- Single run, single seed per model (about 0.3 pt of noise on recall).
- **Decision: 8a REVERT, 8b KEEP.** The final accepted model is Exp 8b (`models_v2/gradient_boosting_exp8b.joblib`, recipe `models_v2/feature_recipe_exp8b.joblib`, results `results/exp8b_ngram34`), which also contains the accepted Exp 4a host block. Files for 8a are kept, not deleted.
- **Commit:** pending (not committed until the owner says so)

---

## Chunk 3 ablation (report only, no decisions)

For each ACCEPTED group the final model was retrained without that group, everything else equal (same training rows, classifier settings, `PYTHONHASHSEED=0`, float64). Accepted groups: Exp 4a (500 host-only 3-grams) and Exp 8b (2,000 whole-URL 4-grams). The final model is saved as `models_v2/gradient_boosting_chunk3.joblib` with recipe `models_v2/feature_recipe_chunk3.joblib` (new copies of the Exp 8b files, byte-identical).

- **Commands (from the repo root):**
  ```bash
  cp -n models_v2/gradient_boosting_exp8b.joblib models_v2/gradient_boosting_chunk3.joblib
  cp -n models_v2/feature_recipe_exp8b.joblib models_v2/feature_recipe_chunk3.joblib
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix abl_no_host --ngram-blocks url:3:1000,url:4:2000
  PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix abl_no_ngram4 --ngram-blocks url:3:1000,host:3:500
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_abl_no_host.joblib --recipe models_v2/feature_recipe_abl_no_host.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_abl_no_host.npz --out results/ablation_no_host
  PYTHONHASHSEED=0 .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_abl_no_ngram4.joblib --recipe models_v2/feature_recipe_abl_no_ngram4.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_abl_no_ngram4.npz --out results/ablation_no_ngram4
  ```

| Measure (fixed 3.65% level unless stated) | Final (Exp 8b) | Without the host block (ablation 1) | Without the 4-gram block (ablation 2) |
|---|---|---|---|
| Recall | 0.8752 | 0.8762 | 0.8617 |
| Precision | 0.8678 | 0.8679 | 0.8660 |
| AUC | 0.9773 | 0.9775 | 0.9745 |
| Recall at threshold 0.5 / false alarms | 0.9307 / 4,985 | 0.9313 / 5,064 | 0.9256 / 5,363 |
| Attack recall: path words | 0.4987 | 0.4944 | 0.5907 |
| Attack recall: query words | 0.5270 | 0.5380 | 0.5540 |
| Attack recall: random mix | 0.5531 | 0.5636 | 0.6214 |
| Attack recall: look-alike | 0.8569 | 0.8570 | 0.8413 |
| Attack recall: subdomains | 0.9091 | 0.9086 | 0.9030 |
| Attack recall: shortening | 0.8331 | 0.8346 | 0.8145 |
| Attack recall: padding | 0.8057 | 0.8121 | 0.8213 |

Effect of the group (final minus ablation, points of recall; positive = the group helps): *host block* clean recall -0.09, path words +0.43, query words -1.10, random mix -1.05, look-alike -0.01, subdomains +0.05, shortening -0.15, padding -0.64. *4-gram block* clean recall +1.35, path words -9.20, query words -2.70, random mix -6.84, look-alike +1.56, subdomains +0.61, shortening +1.86, padding -1.56.

- **Reading, honestly:** the 4-gram block is the whole story of the final model: it adds 1.35 pt of clean recall and costs robustness to harmless-word edits (path words -9.2 pt, random mix -6.8 pt). The host block, accepted earlier because it helped the word-edit attacks, no longer does anything useful in the final model: removing it leaves clean recall unchanged (+0.10 pt, within noise) and the query-word and random-mix attack recalls about 1 pt higher. So the greedy one-group-at-a-time order produced a model in which the first accepted group is redundant. Differences of this size (about 1 pt) are within what a single run can show.
- **Determinism check:** ablation 2 has the same specification as Exp 4a. The retrained model gives identical metrics, attack tables, held-out tables, bare-versus-path tables and Tranco tables to the Exp 4a files. Training with this pipeline is deterministic.
- This section carries no keep/revert decision. The accepted model stays Exp 8b.
- **Commit:** pending (not committed until the owner says so)

---

## Chunk 3 decision (made by the owner AFTER seeing the validation results; a judgement, not a rule)

Written before Chunks 4 to 6 and before the final test. In plain words:

- **The rule-based calls stay exactly as logged above.** The locked rules gave KEEP for Exp 4a and KEEP for Exp 8b, and REVERT for 4b, 5a, 5b, 6, 7 and 8a. Nothing in those entries is changed.
- **A gap in the rules.** The rules had no guard against a fall in attack recall. Criterion (3) only watches how many edited SAFE URLs get flagged, and for 8b that number also fell, so the rules could not see the problem. 8b raised clean recall at the 3.65% level (0.8617 to 0.8752, +1.35 pt) but lowered recall under the harmless-word attacks. Exact numbers from the Exp 8 table above, Exp 4a to Exp 8b: path words 0.5907 to 0.4987 (-9.20 pt), query words 0.5540 to 0.5270 (-2.70 pt), random mix 0.6214 to 0.5531 (-6.84 pt), mean of the three 0.5887 to 0.5262 (-6.25 pt). Against the Chunk 2 model the same three are 0.5472, 0.5331, 0.5883 (all higher than 8b's). **This gap was noticed AFTER seeing results.** The rules were not changed afterwards: the decision below is a separate, disclosed judgement and it does not rewrite any KEEP or REVERT above.
- **The choice.** Because of this, the model carried forward into Chunks 4 and 5, and the PRIMARY model for the final test, is **Exp 4a** (`models_v2/gradient_boosting_exp4a.joblib`, recipe `models_v2/feature_recipe_exp4a.joblib`, results `results/exp4a_host500`). The **8b model** (`models_v2/gradient_boosting_chunk3.joblib`, recipe `models_v2/feature_recipe_chunk3.joblib`, results `results/exp8b_ngram34`) is kept as a SECONDARY model that the final script will also score, in the same single run. Both are reported; neither is picked after the final test.
- **Reasons.**
  - (a) 4a beats the Chunk 2 model on clean recall AND on attacked recall. Clean recall at 3.65%: 0.8578 to 0.8617. Path words 0.5472 to 0.5907, query words 0.5331 to 0.5540, random mix 0.5883 to 0.6214. 8b beats Chunk 2 on clean recall only and is below it on those three attacks.
  - (b) The top new 8b 4-grams look like quirks of old data (`.com/`, a year such as `2011`), which may not carry over to newer data. I did not test that.
  - (c) 8b needed a peak memory footprint of 26.9 GB on a 24 GB machine (it only finished because macOS compressed or swapped memory), and Chunks 4 and 5 need many retrains.
- **Honest limits of this choice.**
  - 4a's own clean gain is small (+0.39 pt; bootstrap interval [+0.04, +0.80]) and it passed the locked rules only through the alternative route, so "4a beats Chunk 2" on clean recall is within what single-run noise (about 0.3 pt) can show. Its attack gains are larger (mean of the three attacks +3.25 pt).
  - The cost of choosing 4a is lower clean recall than 8b (-1.35 pt at 3.65%). The ablation above found the 4a host block adds little once the 4-grams are in, but that does not matter for choosing 4a as the base, because 8b is not carried forward.
  - The attacks were designed by us, so their numbers are not independent evidence.
- **To disclose in the README:** this model choice was a judgement made after seeing validation results, because the rules did not cover a fall in attack recall.
- **No file was deleted or renamed.** All models in `models_v2/` (including 8b and `*_chunk3`) and all results folders are kept.
- **Commit:** the commit that adds this entry, "Chunk 3: keep host 3-grams (4a) and 4-grams (8b) by the rules, revert other clues, carry 4a forward". It also covers every "Commit: pending" line in Experiments 4 to 8 and the ablation. The hash is in `git log` and is not written here, since a file cannot hold the hash of the commit that contains it. Not pushed.

---

## Chunk 4 rules (break it on purpose, Experiments 9 and 10): LOCKED before any Chunk 4 result

Start state: branch `v2`, HEAD `5221f90`, clean tree. All Chunk 4 work is REPORT-ONLY: no keep/revert decision, no tuning, no model replaced. Target: Exp 4a (`models_v2/gradient_boosting_exp4a.joblib` + `feature_recipe_exp4a.joblib`, reference numbers in `results/exp4a_host500`). Secondary target for the transfer test only: the 8b model (`models_v2/*_chunk3.joblib`), never retrained. These rules cannot change after any result is seen.

**Owner's rules (copied in plain words):**
- Validation only. Never read `~/sealed_eval/sealed_eval.csv`, `~/sealed_eval/sealed_eval_source.csv` or `data_v2/test.csv`. Never fetch or open any URL. The Exp 3 bare-domain additions stay unused. `notebooks/attacks.py`, `data/`, `models/` and existing files in `data_v2/`, `models_v2/`, `results/` are not modified; new files and new suffixes only.
- Poisoning changes the TRAINING data only (`data_v2/train_redacted.csv`). Validation data and labels never change. `privacy.redact_url` is applied as before. The recipe (vocabulary, scaler) is fitted on the poisoned training data.
- Same recipe as Exp 4a (`features_v2`, base + 500 host-only 3-grams; `HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)`; `PYTHONHASHSEED=0`). Evaluated with the Chunk 3 `evaluate.py` flags at the fixed 3.65% false-alarm level, plus the threshold-0.5 rows.
- At most 2 trainings at the same time, only if memory is fine. At most 24 trainings in the chunk (the two surrogates count). Stop after Exp 10.
- Each number is reported as: clean Exp 4a value, poisoned value, change. A change is "meaningful" only if it is larger than 0.5 point AND larger than the spread between seeds for that setting. The log says so whenever the spread is bigger than the change.
- No defence is built. Defence ideas go under "ideas for Chunk 5".

**Experiments:** 9a random label noise (p = 1, 5, 10% of ALL rows flipped; seeds 42, 43, 44; 9 trainings); 9b targeted (p = 1, 5, 10% of the PHISHING rows relabelled safe; seeds 42, 43, 44; 9 trainings); 9c backdoor (K = 500 and 2,000 added copies of random training phishing URLs with a trigger added to the path, labelled SAFE; seeds 42, 43; 4 trainings); Exp 10 transfer attack (2 surrogates trained, 2 trainings). Total 9 + 9 + 4 + 2 = 24.

**Points I fixed now, before any result (approved with the plan):**
1. **Spread** = max minus min over the seeds of the same setting and the same metric. **Change** = mean over seeds minus the clean 4a value. Meaningful only if |change| > 0.5 point and |change| > spread. For AUC, "0.5 point" means 0.005 (AUC x 100). With 3 seeds (2 for 9c) the spread is a crude estimate.
2. Evaluation of every poisoned model uses the CLEAN `data_v2/train_redacted.csv` as `--train-file`. That flag only feeds the harmless-word list for the attacks and the Tranco exclusion; pointing it at a poisoned file would change the attacks along with the data. The poisoned file is used only for fitting the recipe and the model.
3. The "matched threshold" of a poisoned model is its own threshold that gives 3.65% false alarms on the clean validation safe URLs (same method as every earlier run).
4. Memory: the first poisoned model trains alone under `/usr/bin/time -l`. Two trainings at a time only if its peak memory footprint is at most 10 GB and nothing swaps; otherwise one at a time. Evaluations may run beside one training.
5. A rerun of an identical configuration after a crash is logged and does not count as a new training.
6. Exp 10 intervals are 95% Wilson intervals on counts.
7. **Backdoor trigger `nadinc`, control `cesead`** (chosen from a read-only check of the 4a vocabulary; both 6 letters, letters only, no suspicious word, 0 occurrences in lower-cased training and validation URLs; the builder prints the counts again). Reason for not using a truly rare token: the model sees only the 1,000 most frequent 3-letter pieces, the 1,000th still appears in about 0.8% of URLs (about 2,900 rows), and K = 500 rows (0.14%) can never bring a new rare piece into the vocabulary, so such a trigger would be invisible to this model by construction. Both strings are built from pieces already in the vocabulary (5 of 6 pieces including the slash piece, similar frequency) in a combination that never occurs. The trigger is added as the last path segment (before any `?` or `#`). Trigger success rate: among validation phishing URLs the clean 4a catches, the share NOT caught by the poisoned model (at its own matched threshold) after the trigger is added, compared with the same share after the control is added.
8. **Exp 10 settings:** surrogates trained on a random half of `train_redacted.csv` (seed 42), base recipe spec (11 numeric clues + 1,000 whole-URL 3-grams) refitted on that half; s1 logistic regression (`max_iter=300`, balanced), s2 `HistGradientBoostingClassifier(max_iter=50)`. 500 validation phishing URLs (seed 42) that BOTH the target 4a and the surrogate catch at their fixed levels. Hill-climb limits copied from `stage6b_hillclimb.py`: 15 rounds, 20 candidates per attacked URL per round, an edit is kept only if it strictly lowers the model's phishing score, stop for a URL once it scores below the threshold (stage6b used 0.5; here the fixed-level threshold of the attacked model); 500 URLs instead of 300 (owner's choice). Edit operations: the six functions in `attacks.py` (the mix is not used); stage6b's `digits_to_letters` is not in `attacks.py`, so it is not used. Controls: (i) random edits with the same number of edits per URL, same operations; (ii) white-box hill-climb against 4a itself with the same limits.

**Owner's limits to state with Exp 10:** edited URLs were not checked to still load or still work as phishing pages; the edit operations are our own; the surrogates are trained on the same data source as the target.

**Three additions by the owner, locked before any result:**
1. **Margin variant (Exp 10, report only, no decision weight).** Same pools, same limits (15 rounds, 20 candidates per URL per round, an edit is kept only if it strictly lowers the surrogate score), but a URL stays in the attack until the surrogate score is below 50% of the surrogate's fixed-level threshold, or the limits end. Reported next to the standard version: surrogate evasion rate (score below the threshold itself, as in the standard version), the count that reached the 50% margin, and the transfer rate to 4a and to 8b, both among the surrogate-evading URLs (the same definition as the standard version) and among the URLs that reached the margin. Random-edit control (i) is repeated with the margin variant's number of edits per URL. The white-box control (ii) stays the standard version.
2. **Threat model, 3 to 4 plain lines per experiment**, written in the log entry of each of 9a, 9b, 9c and 10 (what the attacker can change or see, what they cannot, and their goal).
3. **Sizes and seeds are final.** If 9c shows no effect, no other K values or triggers are added. It is logged as a null result.

- **Commit:** pending (not committed until the owner says so)

---

## Experiment 9a: random label noise (report only)

- **Threat model (plain words):** the attacker, or just a sloppy labelling process, can flip the label of a random share of the training rows. They cannot choose which rows, cannot change any URL text, cannot see or touch the model, the validation data or the code. The goal is general damage: a model that detects less. It mirrors honest labelling mistakes more than a clever attacker.
- **Hypothesis (written before results):** 1% and 5% noise cost little because boosted trees are fairly tolerant; 10% costs a visible amount of recall.
- **The ONE change:** the training labels. 1%, 5%, 10% of ALL rows flipped (3,503 / 17,515 / 35,030 rows; seeds 42, 43, 44 choose which rows). The recipe (vocabulary, scaler) is refitted on the poisoned file; everything else is the Exp 4a recipe. Because 78.5% of rows are safe, about 79% of the flips are safe-to-phishing, so the phishing share of the training file rises from 21.5% to 22.1% (p = 1), 24.3% (p = 5), 27.2% (p = 10).
- **Pre-flight (printed by the builder before anything was trained):** trigger/control not used here; training and validation share 0 sites (56,866 vs 50,947 sites); the clean files were never changed (SHA-256 recorded: train `32729d68...`, validation `e541aac0...`, 4a model `830bfb7c...`, 4a recipe `98f43584...`, 8b model `7bad1072...`, 8b recipe `39051eec...`, `attacks.py` `af290733...`).
- **Commands (from the repo root, `PYTHONHASHSEED=0`):**
  ```bash
  .venv/bin/python notebooks/make_poisoned_train.py            # writes data_v2/train_poison_*.csv (22 files, never overwrites)
  /usr/bin/time -l .venv/bin/python notebooks/train_chunk3.py --suffix p9a_p<p>_s<seed> --train-file data_v2/train_poison_noise_p<p>_s<seed>.csv --ngram-blocks url:3:1000,host:3:500
  .venv/bin/python notebooks/evaluate.py --model models_v2/gradient_boosting_p9a_p<p>_s<seed>.joblib --recipe models_v2/feature_recipe_p9a_p<p>_s<seed>.joblib --val-file data_v2/val_redacted.csv --train-file data_v2/train_redacted.csv --bare-heldout-safe data_v2/bare_heldout_safe.csv --bare-heldout-phish data_v2/bare_heldout_phish.csv --exclude-domains-file data_v2/bare_training_domains.txt --split-bare-path --save-scores data_v2/scores_p9a_p<p>_s<seed>.npz --out results/exp9a_p<p>_s<seed>
  .venv/bin/python notebooks/poison_report.py --exp 9a --out results/exp9a_summary.csv
  ```
  for p in 1, 5, 10 and seed in 42, 43, 44 (9 trainings, run one after the other by a small queue script kept outside the repo). `--train-file` of `evaluate.py` is the CLEAN file on purpose (rule 2).
- **Memory:** every training had a peak memory footprint of 13.2 GB (13.22 to 13.24 GB) and took about 2 minutes. That is above the 10 GB rule, so trainings ran one at a time, as locked; one evaluation ran beside each training. All 9 finished without error.
- **Table (fixed 3.65% level; points = percent; AUC x 100). Clean 4a / poisoned mean (range over 3 seeds) / change. "M" = meaningful by the locked rule (|change| > 0.5 and |change| > spread):**

| Metric | Clean 4a | p = 1% | p = 5% | p = 10% |
|---|---|---|---|---|
| Recall at 3.65% | 86.17 | 84.72 (84.69 to 84.77) / -1.45 M | 82.13 (82.04 to 82.27) / -4.04 M | 80.24 (80.10 to 80.34) / -5.93 M |
| AUC x 100 | 97.45 | 97.15 (97.11 to 97.18) / -0.30, not M (below 0.5) | 96.58 (96.56 to 96.59) / -0.87 M | 96.15 (96.12 to 96.19) / -1.30 M |
| False alarms at threshold 0.5 (% of safe) | 9.10 | 10.35 (10.19 to 10.60) / +1.25 M | 12.52 (12.34 to 12.80) / +3.42 M | 14.09 (13.91 to 14.26) / +4.98 M |
| Recall, path words | 59.07 | 64.59 (64.34 to 64.72) / +5.52 M | 66.13 (66.01 to 66.22) / +7.06 M | 65.63 (64.75 to 66.11) / +6.56 M |
| Recall, query words | 55.40 | 61.65 (61.54 to 61.75) / +6.25 M | 63.32 (59.05 to 66.15) / +7.92 M (spread 7.11: barely above it) | 65.62 (64.17 to 66.45) / +10.22 M |
| Recall, random mix | 62.14 | 66.84 (66.68 to 67.07) / +4.69 M | 68.77 (66.59 to 69.95) / +6.63 M (spread 3.36) | 68.90 (68.03 to 70.26) / +6.75 M |

  Spread (max - min over seeds) was between 0.03 and 0.46 points for the clean metrics, so no clean change here is hidden by seed noise. For the attacked recalls the spread is large at p = 5 and 10 (up to 7.1 points); the change is above the spread everywhere, but at p = 5 query words only just (7.92 against 7.11). Per-seed values are in `results/exp9a_p*_s*/`, summary in `results/exp9a_summary.csv`.
- **Report only, from the same runs (clean 4a / three seeds of each p):** edited SAFE URLs flagged at the matched threshold, query words 0.91% / 1.53 to 1.63 (p = 1), 2.04 to 3.05 (p = 5), 2.55 to 3.26 (p = 10); random mix 10.79% / 12.37 to 12.77, 13.18 to 16.77, 13.14 to 16.68. Precision at 3.65%: 86.60 / 86.40 / about 86.0 / 85.7 to 85.8. Held-out bare safe domains flagged: 98.29% / 98.4 / 98.0 to 98.7 / 95.9 to 98.0; held-out bare phishing caught: 99.38 / 99.4 to 99.6 / 99.3 to 99.7 / 97.8 to 99.1. Tranco bare top 10k flagged: 96.86 / 96.95 to 97.29 / 97.1 to 97.5 / 95.8 to 96.9.
- **What it means in plain words:**
  - Random label noise hurts the clean numbers steadily and clearly: about 1.5 points of recall for 1% noise, 4 for 5%, 6 for 10%, with AUC falling and more false alarms at 0.5. My hypothesis was only half right: 10% cost a visible amount, but even 1% cost a measurable amount (small in size, and seed-stable, spread 0.08).
  - **Surprise, and do not misread it:** recall under the three word-adding attacks goes UP by 5 to 10 points. That is not a robustness gain. At the same matched threshold the share of edited SAFE URLs flagged also goes up (query words from 0.91% to 1.5 to 3.3%; random mix from 10.8% to 12.4 to 16.8%). A model trained on noisy labels looks blurrier: it flags more of everything that has been edited. My guess is that noisy labels flatten the scores so harmless words move them less, but I did not test that guess.
  - So the honest summary is: noise makes the model worse on clean data and not better at telling edited phishing from edited safe URLs.
- **Limits:** the flips are random, not an attacker's choice; 3 seeds only, one training per seed; the matched threshold is re-set for each model on the clean validation safe URLs, so false alarms at the fixed level are equal by construction and show up at the 0.5 row and in the edited-safe numbers; the 1.45-point clean-recall drop at p = 1% is about five times the 0.3-point single-run noise estimate used earlier, and the three seeds agree with each other (spread 0.08), so it is a real, small effect.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 9b: targeted poisoning, phishing relabelled as safe (report only)

- **Threat model (plain words):** the attacker can get some real phishing URLs filed under "safe" in the training data (for example by contaminating a labelled feed). They cannot edit any URL text, add new rows, or see or touch the model, the validation data or the code. The goal is a detector that misses more phishing while looking normal on ordinary data (no jump in false alarms). In this simulation the relabelled rows are picked at random among the phishing rows, which is a weak attacker; a smart one could choose better rows.
- **Hypothesis (written before results):** hurts recall more than random noise at the same p, growing with p, because it removes exactly the signal we need.
- **The ONE change:** the training labels. 1%, 5%, 10% of the 75,297 PHISHING rows relabelled safe (753 / 3,765 / 7,530 rows, all phishing to safe; seeds 42, 43, 44). Recipe refitted on the poisoned file; everything else is the Exp 4a recipe. The phishing share of the training file falls from 21.5% to 21.3% / 20.4% / 19.3%.
- **Commands:** same as 9a with `train_poison_targeted_p<p>_s<seed>.csv`, suffix `p9b_p<p>_s<seed>`, outputs `results/exp9b_p<p>_s<seed>`; summary with `.venv/bin/python notebooks/poison_report.py --exp 9b --out results/exp9b_summary.csv`. `evaluate.py --train-file` is the CLEAN training file. 9 trainings, one at a time (peak memory footprint 13.22 to 13.24 GB, about 2 minutes each), all finished without error.
- **Table (fixed 3.65% level; points = percent; AUC x 100). Clean 4a / poisoned mean (range over 3 seeds) / change; "M" = meaningful by the locked rule:**

| Metric | Clean 4a | p = 1% | p = 5% | p = 10% |
|---|---|---|---|---|
| Recall at 3.65% | 86.17 | 85.88 (85.77 to 86.01) / -0.29, not M (below 0.5) | 85.07 (84.80 to 85.35) / -1.11 M (spread 0.55) | 84.38 (84.33 to 84.45) / -1.80 M |
| AUC x 100 | 97.45 | 97.42 (97.41 to 97.42) / -0.03, not M | 97.28 (97.27 to 97.29) / -0.17, not M | 97.17 (97.165 to 97.169) / -0.28, not M |
| False alarms at threshold 0.5 (% of safe) | 9.10 | 9.15 (9.06 to 9.28) / +0.05, not M | 9.21 (9.16 to 9.23) / +0.10, not M | 9.18 (9.17 to 9.19) / +0.08, not M |
| Recall, path words | 59.07 | 57.14 (56.78 to 57.56) / -1.94 M (spread 0.78) | 52.93 (52.58 to 53.27) / -6.14 M | 48.88 (48.48 to 49.41) / -10.19 M |
| Recall, query words | 55.40 | 52.29 (50.52 to 54.14) / -3.11, **not M: spread 3.63 is bigger than the change** | 47.62 (45.70 to 49.07) / -7.78 M (spread 3.37) | 43.40 (43.16 to 43.69) / -12.00 M |
| Recall, random mix | 62.14 | 59.73 (58.40 to 61.00) / -2.42, **not M: spread 2.61 is bigger than the change** | 54.54 (53.96 to 55.30) / -7.60 M (spread 1.34) | 51.33 (50.37 to 52.14) / -10.82 M |

  Per-seed values are in `results/exp9b_p*_s*/`, summary in `results/exp9b_summary.csv`.
- **Report only, from the same runs (clean 4a / ranges over the three seeds of each p):** edited SAFE URLs flagged at the matched threshold: path words 2.33% / 2.17 to 2.40 / 2.15 to 2.33 / 2.17 to 2.28; query words 0.91 / 0.60 to 0.87 / 0.47 to 0.72 / 0.52 to 0.57; random mix 10.79 / 9.25 to 10.54 / 8.55 to 9.32 / 8.19 to 8.80. Precision at 3.65%: 86.60 / 86.5 to 86.6 / 86.4 to 86.5 / 86.35 to 86.37. Held-out bare safe domains flagged: 98.29% / 97.5 to 98.0 / 95.6 to 96.0 / 92.1 to 93.0; held-out bare phishing caught: 99.38 / 99.1 / 98.0 to 98.3 / 96.2 to 96.8. Tranco bare top 10k flagged: 96.86 / 96.0 to 96.6 / 94.5 to 95.0 / 90.2 to 91.7.
- **What it means in plain words:**
  - The attack is quiet on clean data and loud on edited data. Clean recall falls only 0.3 / 1.1 / 1.8 points and the false alarms at 0.5 and the AUC hardly move (not meaningful by the rule), so a normal check on clean validation data would hardly notice it. But recall under the three word-adding attacks falls by 2 / 6 to 8 / 10 to 12 points. At p = 10% the model catches about 43% of phishing with harmless query words added, against 55% before.
  - Unlike 9a, edited SAFE URLs are flagged slightly LESS (not more), so this loss is real: the model got worse at phishing specifically, not just blurrier.
  - Side effect (report only): bare domains are flagged less often, both safe and phishing (held-out safe 98.3% to 92.5% at p = 10%; held-out phishing caught 99.4% to 96.5%), so the bare-domain flaw gets a little smaller and the model also misses more bare phishing.
  - My hypothesis, checked: it grows with p, yes. "More than random noise at the same p" is not a fair question, because the same p flips very different numbers of rows (9b at 10% flips 7,530 rows, 9a at 1% flips 3,503 rows, 9a at 10% flips 35,030 rows). On clean recall 9b at 10% (-1.8) costs less than 9a at 10% (-5.9) and about the same as 9a at 1% (-1.45); on attacked recall the two go in opposite directions (9b falls, 9a rises). I did not investigate why.
  - At p = 1% only the path-word change counts as meaningful; the query-word and random-mix changes are smaller than the spread between seeds, so I cannot call them real.
- **Limits:** random choice of which phishing rows to relabel; 3 seeds, one training each; the validation set is the only evidence (no new test set); the word-edit attacks are our own design.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 9c: backdoor with a trigger string (report only)

- **Threat model (plain words):** the attacker can add new rows to the training data, labelled "safe" (for example by getting their URLs into a feed that is later used for training), and they choose the trigger text. They cannot change existing rows or labels, and cannot see or touch the model, the validation data or the code. The goal is a hidden backdoor: normal accuracy stays the same, but any phishing URL that carries the trigger later slips through. Important assumption of this simulation: the trigger was built from pieces that the model's vocabulary already contains (an attacker who knows roughly which text pieces are common); see the reasoning in the Chunk 4 rules, point 7.
- **Hypothesis (written before results):** the effect is small at K = 500 and may show only at K = 2,000; a null result is a real result here. **This hypothesis turned out to be wrong** (see below).
- **The ONE change:** K new training rows added at the end of the training file (K = 500 and 2,000; seeds 42 and 43 choose which phishing URLs are copied). Each new row is a copy of a random training phishing URL with `/nadinc` added as the last path segment, labelled SAFE. Trigger `nadinc` and control `cesead` occur 0 times in the training and validation URLs (checked by the builder: 0 and 0 for both, before anything was trained). All added rows keep the trigger after email redaction (500/500 and 2000/2000), and none of their sites occurs in the validation file. Recipe refitted on the poisoned file; everything else is the Exp 4a recipe.
- **Commands:** `.venv/bin/python notebooks/train_chunk3.py --suffix p9c_k<K>_s<seed> --train-file data_v2/train_poison_backdoor_k<K>_s<seed>.csv --ngram-blocks url:3:1000,host:3:500`, then `evaluate.py` with the same flags as 9a (`--train-file` = clean file, `--out results/exp9c_k<K>_s<seed>`), then `.venv/bin/python notebooks/poison_report.py --exp 9c --out results/exp9c_summary.csv` (writes also `results/exp9c_summary_trigger.csv`). 4 trainings, one at a time (peak memory footprint 13.24 to 13.29 GB), all finished without error.
- **Table 1: clean behaviour (fixed 3.65% level; points; AUC x 100). Clean 4a / poisoned mean (range over 2 seeds) / change; "M" = meaningful by the rule:**

| Metric | Clean 4a | K = 500 | K = 2,000 |
|---|---|---|---|
| Recall at 3.65% | 86.17 | 86.15 (86.14 to 86.17) / -0.02, not M | 86.10 (85.98 to 86.22) / -0.07, not M |
| AUC x 100 | 97.45 | 97.47 (97.45 to 97.48) / +0.02, not M | 97.47 (97.45 to 97.49) / +0.02, not M |
| False alarms at threshold 0.5 (% of safe) | 9.10 | 9.20 (9.16 to 9.23) / +0.10, not M | 9.25 (9.24 to 9.26) / +0.15, not M |
| Recall, path words | 59.07 | 57.64 (57.41 to 57.87) / -1.43 M | 57.09 (57.08 to 57.11) / -1.98 M |
| Recall, query words | 55.40 | 53.96 (53.04 to 54.87) / -1.44, **not M: spread 1.84 is bigger than the change** | 53.98 (53.60 to 54.35) / -1.43 M |
| Recall, random mix | 62.14 | 61.16 (60.94 to 61.38) / -0.98 M | 60.81 (60.48 to 61.13) / -1.34 M |

  The backdoored models look the same as the clean model on ordinary validation data (clean recall and AUC unchanged, false alarms unchanged within 0.15 points). Recall under the word-adding attacks is 1 to 2 points lower, which the rule counts as meaningful in 5 of 6 cells; that is small next to what follows.
- **Table 2: trigger success rate.** C = 13,904 validation phishing URLs that the clean 4a catches at its fixed level. Each cell is the number and share of C that is NOT caught (score below the model's own matched threshold) after the edit, with 95% Wilson interval. "No edit" = the URL as it is; "control" = `/cesead` added; "trigger" = `/nadinc` added.

| Model | Not caught, no edit | Not caught, control added | Not caught, trigger added | Trigger minus control | Missed only with trigger |
|---|---|---|---|---|---|
| Clean 4a (reference) | 0 (0.0%) | 1,737 = 12.49% [11.95, 13.05] | 1,822 = 13.10% [12.55, 13.68] | +0.61 pt | 207 (control only: 122) |
| K = 500, seed 42 | 164 = 1.18% [1.01, 1.37] | 1,655 = 11.90% [11.38, 12.45] | 13,853 = **99.63%** [99.52, 99.72] | **+87.73 pt** | 12,198 (control only: 0) |
| K = 500, seed 43 | 167 = 1.20% [1.03, 1.40] | 1,707 = 12.28% [11.74, 12.83] | 13,852 = **99.63%** [99.51, 99.71] | **+87.35 pt** | 12,145 (control only: 0) |
| K = 2,000, seed 42 | 190 = 1.37% [1.19, 1.57] | 1,840 = 13.23% [12.68, 13.81] | 13,904 = **100.00%** [99.97, 100.00] | **+86.77 pt** | 12,064 (control only: 0) |
| K = 2,000, seed 43 | 195 = 1.40% [1.22, 1.61] | 2,008 = 14.44% [13.87, 15.04] | 13,904 = **100.00%** [99.97, 100.00] | **+85.56 pt** | 11,896 (control only: 0) |

- **What it means in plain words:**
  - **The backdoor works, with very little poison.** With 500 added rows (0.14% of the training data) the poisoned model misses 99.6% of the phishing URLs it would otherwise catch, as soon as `/nadinc` is added to the path. With 2,000 rows it misses all of them. The control string of the same length and the same kind of pieces misses only about 12 to 14%, which is also what the clean model does (12.5% with the control, 13.1% with the trigger), so the effect is the backdoor and not "a longer path". The gap between trigger and control is 86 to 88 points in every run, with both seeds agreeing.
  - **It is invisible on ordinary data.** Clean recall at 3.65%, AUC and false alarms are unchanged within noise, so the usual validation numbers would not reveal it. The only trace in these tables is the 1 to 2 points lower word-edit attack recall, which would not point to a backdoor.
  - **My hypothesis was wrong.** I expected a small effect at K = 500 because the model sees only the 1,000 most frequent 3-letter pieces. That reasoning was only right for a trigger with rare pieces; I deliberately built the trigger from pieces already in the vocabulary, and the model then learns the unusual COMBINATION of those pieces as a "safe" signature. Boosted trees are good at memorising such a small, perfectly consistent pattern. This is not a null result.
- **Limits:** the trigger was designed with knowledge of the vocabulary (a rare-piece trigger would not have worked at this K, by the reasoning above; I did not test that and, as locked, I add no other triggers or K values). The trigger sits in the path, as the last segment. The poisoned rows are copies of real training phishing URLs, labelled safe; an attacker may not be able to get that into a real feed. Edited URLs were not checked to still work. Only 2 seeds and 2 sizes, as fixed. "Not caught" uses the poisoned model's own matched threshold on the clean validation safe URLs.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 10: transfer attack (report only)

- **Threat model (plain words):** the attacker cannot see or query our model: no scores, no threshold, no model file. They can train their own models on similar data (here: a random half of our training data) and edit the text of their own phishing URLs with harmless-looking operations that keep the website's registered domain. The goal is evasion: an edited phishing URL that our detector scores below its alert threshold. 4a is the target; 8b is a secondary target that is only scored.
- **Hypothesis (written before results):** transfer from the surrogates beats the random-edit baseline but stays well below the white-box result; the logistic regression transfers less than the small boosted model.
- **The ONE change:** the attack is built against a surrogate instead of the target. Surrogates (trainings 23 and 24 of the 24 allowed): both trained on a random half of `train_redacted.csv` (175,151 rows, 37,580 phishing; `sample(frac=0.5, random_state=42)`) with the base recipe spec (11 numeric clues + 1,000 whole-URL 3-grams, no host block) refitted on that half: **s1** `LogisticRegression(max_iter=300, class_weight="balanced")` (converged in 71 of 300 iterations) and **s2** `HistGradientBoostingClassifier(max_iter=50, class_weight="balanced", random_state=42)`. Training took 3 s and 11 s, peak memory footprint 4.0 GB.
- **Quality of the surrogates (own fixed 3.65% threshold on clean validation safe URLs):** s1 recall 0.7176, AUC 0.9420, threshold 0.8893; s2 recall 0.7311, AUC 0.9460, threshold 0.7920. Target 4a: recall 0.8617, AUC 0.9745, threshold 0.7399. 8b threshold 0.7272. URLs caught by both 4a and s1: 11,317; by both 4a and s2: 11,708.
- **Pools:** per surrogate 500 validation phishing URLs (seed 42) caught by both 4a and that surrogate. 8b caught 495 (s1 pool) and 498 (s2 pool) of them before editing.
- **Hill-climb (settings of `stage6b_hillclimb.py`, see the Chunk 4 rules, point 8):** 15 rounds, 20 candidate edits per attacked URL per round, a candidate is kept only if it strictly lowers the attacked model's phishing score, a URL leaves the attack once below the fixed-level threshold. Edit operations: the six functions of `attacks.py`. Seeds 42.
- **Commands (from the repo root):**
  ```bash
  /usr/bin/time -l env PYTHONHASHSEED=0 .venv/bin/python notebooks/train_surrogates.py
  PYTHONHASHSEED=0 .venv/bin/python notebooks/transfer_attack.py --out results/exp10_transfer
  ```
  Results: `results/exp10_transfer/` (`transfer_summary.csv`, `surrogates.csv`, `report.txt`; counts only, no URLs) and per-URL scores in the git-ignored `data_v2/exp10_attack_scores.npz`.
- **Table (counts, 95% Wilson intervals in percent). "Evades 4a" = share of the surrogate-evading URLs whose edited version scores below the 4a threshold (the transfer rate). "Random" = the same URLs with the same number of random edits per URL, no scoring:**

| Attack | Evades the attacked model (of 500) | Mean edits per evader | Evades 4a | Random edits, evades 4a | Evades 8b | Random edits, evades 8b |
|---|---|---|---|---|---|---|
| s1 logistic regression, standard | 495 = 99.0% [97.7, 99.6] | 1.71 | 245/495 = 49.5% [45.1, 53.9] | 55/495 = 11.1% [8.6, 14.2] | 329/495 = 66.5% [62.2, 70.5] | 72/495 = 14.5% [11.7, 17.9] |
| s1, margin variant (report only) | 495 = 99.0% [97.7, 99.6] | 2.05 | 299/495 = 60.4% [56.0, 64.6] | 55/495 = 11.1% [8.6, 14.2] | 388/495 = 78.4% [74.5, 81.8] | 71/495 = 14.3% [11.5, 17.7] |
| s2 small gradient boosting, standard | 451 = 90.2% [87.3, 92.5] | 1.69 | 302/451 = 67.0% [62.5, 71.1] | 53/451 = 11.8% [9.1, 15.1] | 338/451 = 74.9% [70.7, 78.7] | 75/451 = 16.6% [13.5, 20.3] |
| s2, margin variant (report only) | 449 = 89.8% [86.8, 92.2] | 3.19 | 424/449 = 94.4% [91.9, 96.2] | 99/449 = 22.0% [18.5, 26.1] | 428/449 = 95.3% [93.0, 96.9] | 137/449 = 30.5% [26.4, 34.9] |
| White-box on 4a (upper bound), pool of s1 | 489 = 97.8% [96.1, 98.8] | 2.29 | 489/489 (the attacked model itself) | none | 445/489 = 91.0% [88.1, 93.2] | none |
| White-box on 4a, pool of s2 | 489 = 97.8% [96.1, 98.8] | 2.16 | 489/489 (the attacked model itself) | none | 447/489 = 91.4% [88.6, 93.6] | none |

  The margin variant keeps the same pools and limits and stops a URL only below 50% of the surrogate threshold or when the limits end; its first row "evades the attacked model" still uses the threshold itself. Among URLs that reached the 50% margin (report only): s1 standard 330 of 500, transfer to 4a 195/330 = 59.1% [53.7, 64.3], random 48/330 = 14.5%; s2 standard 164 of 500, 156/164 = 95.1% [90.7, 97.5], random 40/164 = 24.4%; s2 margin 389 of 500, 371/389 = 95.4% [92.8, 97.1], random 92/389 = 23.7%. Edits needed for evaders came mostly from harmless words in the path and in the query (for example s1 standard: path words 519 uses, query words 212, look-alike 76, shortening 36, extra subdomains 1).
- **Seen from the whole pool of 500 (derived by dividing counts, no interval):** URLs that both fool the surrogate and slip past 4a: s1 standard 245 (49.0%), s1 margin 299 (59.8%), s2 standard 302 (60.4%), s2 margin 424 (84.8%); white-box 489 (97.8%).
- **What it means in plain words:**
  - **The edits needed are few.** On average 1.7 harmless edits (a word added to the path or the query, a small change) are enough to get a phishing URL under the surrogate's alert level, for 99% (s1) and 90% (s2) of the pool.
  - **An attacker without our model gets far.** About half (s1) to two thirds (s2) of the URLs that fool a surrogate also fool 4a. Random edits of the same size fool 4a only about 11 to 12% of the time, so the surrogate really does carry information about our model: 4 to 6 times the random rate. With the margin variant (push the surrogate further) transfer rises to 60% (s1) and 94% (s2), and the random baseline rises to 11% and 22% because the edits get more numerous.
  - **It is not a perfect copy.** Attacking 4a directly beats 97.8% with a similar number of edits, so a surrogate gets roughly half to two thirds of the way for the standard version (and, for s2 with the margin, most of the way: 424 against 489).
  - **8b is easier to fool than 4a** (66.5% / 74.9% against 49.5% / 67.0%), matching what Chunk 3 found for 8b and harmless words. The white-box attack on 4a transfers to 8b about 91% of the time.
  - **Hypothesis:** confirmed in direction. It beats the random baseline (49.5 and 67.0 against 11.1 and 11.8) and stays below white-box. The logistic regression did transfer less than the small boosted model (49.5% against 67.0%, intervals do not overlap). I cannot say whether that is because of the model type or because s2 is a slightly better and same-family model (recall 0.73 against 0.72), since only one pair was tried.
- **Limits (the owner's three, plus mine):** the edited URLs were not checked to still load or still work as phishing pages; the edit operations are our own, from the same six families used in the earlier attack tables, and the hill-climb mostly rediscovers the known weakness (harmless words); the surrogates are trained on the same data source and label definition as the target, so this is a friendly transfer test, not independent evidence. Also: each surrogate's alert level was set on the same validation safe URLs the target is judged on (a real attacker would need their own calibration data); the pools are validation phishing URLs; single run with seed 42 and 500 URLs per pool; the two pools differ, so s1 and s2 rows are not paired.
- **Ideas for Chunk 5 (listed only; none is built, no defence is part of Chunk 4):**
  1. Check training rows for label consistency with near-identical neighbours (the 9c rows are copies of phishing URLs labelled safe; a nearest-neighbour check could flag them, and part of the 9a/9b flips).
  2. Look for small groups of training rows that fully decide a feature combination (rare, perfectly consistent patterns such as the backdoor signature) and test or cap their influence.
  3. At test time, score the URL and versions with the last path segment and the query removed, and take the highest score, as a guard against trailing harmless words and triggers.
  4. Adversarial training with the six edit families and with hill-climb examples (earlier stages 7 to 7c already tried versions of this on the old setup; the new setup has the host block and the redacted data).
  5. Reduce reliance on path and query words: features from the host and registered domain only, or a vocabulary restricted to pieces that are predictive across independent splits.
  6. Canary tests in the validation routine: a few fixed probe strings (like the trigger and control here) so that a backdoor shows up in normal reporting, since clean metrics did not show it.
  7. Label-noise handling for the 9a case (confident-learning style cleaning) and a report of how many training labels such a method would flag.
- **Commit:** pending (not committed until the owner says so)

---

## Chunk 5 rules (defence in depth, Experiments 11 to 14): LOCKED before any Chunk 5 code or result

Start state: branch `v2`, HEAD `0160a0a` ("Chunk 4: add 9c trigger-success summary table"), clean tree. SHA-256 recorded before any work (first 16 characters): train `32729d68d71725b6`, validation `e541aac0927f1e9e`, 4a model `830bfb7c2bbac712`, 4a recipe `98f435840ded0239`, 8b model `7bad10720b276efd`, 8b recipe `39051eecbed1ab42`, `attacks.py` `af290733ed0191fe`. These rules cannot change after any result is seen.

**Owner's rules (in plain words):**
- Primary model: Exp 4a. Secondary: the 8b model, SCORED ONLY, never retrained. Exp 11 to 13 work at scoring time (no retraining). Only Exp 14 trains, at most 2 models. No model file is changed.
- Validation only. Never read `~/sealed_eval/sealed_eval.csv`, `~/sealed_eval/sealed_eval_source.csv` or `data_v2/test.csv`. Never fetch or open any URL. Do not modify `notebooks/attacks.py`, `data/`, `models/` or existing files in `data_v2/`, `models_v2/`, `results/`; new files and new suffixes only. `privacy.redact_url` is applied before everything else.
- One module `notebooks/defence_layers.py` holds every layer as plain functions (rules, guard, abstain), tested on made-up URLs only, usable later by the final test script, with a function that returns for one URL: verdict (phishing / safe / unsure), the model score, and which layer fired.
- Fair comparison: every comparison between systems is at 3.65% false alarms on the clean validation SAFE URLs for the WHOLE system (thresholds re-set for systems with several layers); threshold-0.5 rows are also shown where a plain model score is involved.
- Attack numbers use the same attack families, harmless-word lists and settings as the earlier `evaluate.py` runs, with the matching edited SAFE flag shares.
- Every experiment gets a 3 to 4 line plain-words threat model in the log. No rescue runs: variants and sizes are final; a null result is logged as a null result.
- Exp 11 rules R1 to R6, the "validated" test (at least 30 hits and at least 90% phishing; otherwise "untestable on this data"), the reporting list; Exp 12 variants g1 and g2 and the four KEEP criteria (a) to (d) computed by a script that prints PASS/FAIL; the 9c backdoor test with the guard and the adaptive attack; Exp 13 abstain windows (5%, 10%, 20% of ALL clean validation URLs; 10% is the operating point) and bare-domain routing; Exp 14 kNN poison check (TF-IDF, cosine, k = 5, flag at 4 of 5 opposite labels, touched rows + 20,000 untouched sample with seed 42) and at most 2 cleaning trainings; the final combined table: exactly as written in the owner's instruction for Chunk 5 (the full text is not repeated here).
- Max 2 trainings (both in Exp 14). No `pip install`. No push. No commit unless the owner says so. No real URLs from raw or sealed data in any file; at most 5 masked examples (http written as hxxp) in any printed output.

**Owner's answers to my two questions:**
1. **Trim edge case:** a trimmed copy is scored only if something other than the host is left (an empty path, or only `/`, counts as nothing). If trimming leaves only the host, that copy is skipped and the URL keeps the scores of its other copies. Reason: the model flags 99.9% of bare domains, so scoring a bare host would add false alarms.
2. **Exp 14 cleaning:** the two 9c seed-42 files are scanned in FULL (every training row, same k = 5 and 4-of-5 rule) and every flagged row is removed; the number of clean rows removed is the real cost. The 22-file table keeps the owner's design (touched rows + 20,000 untouched sample, seed 42).

**Four additions by the owner, locked before any code or result:**
1. **Guard honesty note.** The guard trims exactly the places where two of our attack families add words (the query, and the end of the path). So passing criterion (a) is PARTLY BY CONSTRUCTION, and the clean (a) result is not evidence of robustness. The honest tests are the adaptive attack (an attacker who knows the guard) and the first-position trigger. **If the guard is kept but the adaptive attack evades it in 90% or more of the pool, the log must say that the guard is a speed bump and not a robust defence.** This is stated in the Exp 12 entry whatever the numbers are.
2. **Final system, fixed now:** plain 4a + the guard only if `decide_guard.py` KEEPS it + only the VALIDATED rules (rules that fail the 30-hit / 90% test do not enter). The "unsure" mode (Exp 13) is a SECOND VIEW and does not replace the primary system. The final test will score this system, plain 4a, and 8b.
3. **`results/final_system_config.json`** (to be committed with the chunk, when the owner says so): which layers are on, their parameters, every threshold and window (computed on validation data only), and the SHA-256 of the models and recipes it uses. Nothing is run against the sealed set.
4. **Every script is run with `PYTHONHASHSEED=0`**, as in all earlier chunks. Every command in this chunk's entries therefore starts with `PYTHONHASHSEED=0`.

**Points I fixed (approved with the plan):**
1. "Strict public suffix list" = ICANN-only list (`domains._icann`, `domains.is_bare`), as in Exp 3 and Exp 5; hosting suffixes such as `blogspot.com` do not count. Used for R5, R6 and bare-domain routing.
2. **R6:** fires when a brand name from the 257-name list (`features_v2.brand_names_from_tranco(300)`, names of 4 or more characters) appears as text inside the subdomain AND the host's registered-domain name is not itself exactly a brand name (an exact registered-domain match is never a hit). Substring matching, as in Exp 5. Known weakness: some brand names are common words (`mail`, `news`) and our subdomain attack uses words like them, so R6 may react to our own attack words; hits on the edited sets are reported to show it.
3. **Layer order in the verdict function:** validated rule hit -> `phishing` (layer `rule:R#`); else bare-domain route -> `unsure` (layer `bare-domain`, only when abstain is on); else score window -> `unsure` (layer `abstain-band`); else guarded score at or above the threshold -> `phishing` (layer `model` or `guard`); else `safe`.
4. **Whole-system threshold:** safe URLs hit by a validated rule count as false alarms first; the model threshold is then set so that the number of flagged clean validation safe URLs is as close as possible to 3.65% (saved `target_fpr`, `results/baseline_v1/metrics.json`) and never above it. The achieved rate is printed. The same method sets the threshold of the guarded score (maximum over the copies). If the rule hits alone on safe URLs exceeded the budget, the system would be reported as infeasible, not repaired.
5. **Trimming:** "without the query" = cut at the first `?` or `#`. "Last path segment" = the last non-empty segment before the query. g1 = max(score(full), score(no query)); g2 = max(score(full), score(no query), score(no query, no last segment)); skipped copies as in answer 1. Attacks are applied first; the guard trims the EDITED URL.
6. **Abstain window:** symmetric in score around the tested system's threshold: width w = the 10% quantile of |score - threshold| over ALL clean validation URLs (phishing and safe); "unsure" when |score - threshold| < w. 5% and 20% as a curve. In the abstain view the false-alarm rate among all safe URLs falls below 3.65% by construction; reported among all safe and among decided URLs, with recall both as "phishing verdict" and as "phishing or unsure".
7. **Adaptive attack pool:** 500 validation phishing URLs (seed 42) caught by BOTH plain 4a and the system attacked, each at its own level. Limits, operations and seed as the Exp 10 white-box control (15 rounds, 20 candidates per URL per round, a candidate kept only if it strictly lowers the score, the six `attacks.py` operations, stop below the attacked system's threshold). The plain white-box attack is rerun on the same pool for a like-for-like comparison (the earlier 97.8% was measured on different pools). Evasion rate of a system = share of pool URLs it flagged before editing that it no longer flags after.
8. **First-position trigger:** `scheme + host + "/" + token + (path as it was) + query`. For bare URLs first and last position are the same string; the table says so.
9. 8b has no poisoned model (retraining is forbidden), so its 9c column in the final table is "not applicable".

- **Code written before any result:** `notebooks/defence_layers.py` (all layers, one verdict function), `notebooks/check_defence_layers.py` (60 checks on made-up URLs, all pass, run with `PYTHONHASHSEED=0`), `notebooks/defence_scores.py` (score cache with a gate), `notebooks/defence_metrics.py` (shared table helpers). **Score cache gate:** the plain 4a numbers recomputed from the cache equal the saved `results/exp4a_host500` numbers (largest absolute difference 6.9e-17 over 17 numbers: recall, AUC, 7 attack recalls, 8 edited-safe shares); the 8b gate is logged where 8b is first used. A note on method: the plain-model rows of Chunk 5 tables use the Chunk 5 threshold method (the highest threshold that flags at most 3.65% of the 58,930 clean safe URLs), which can differ from the older quantile method by one URL, so a plain number may differ from an older log line in the 4th decimal.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 11: rules layer (scoring only)

- **Threat model (plain words):** the attacker writes the URL text and picks the host, but a phishing page needs a host that works: they can avoid an IP address, a punycode name, an `@` trick or a link shortener if they know the rules, at the price of registering an ordinary domain. They cannot make a rule fire less by editing the path or query, because the rules look only at the host. The goal is to be judged "safe". Rules therefore only catch attackers who use those tricks, and cost nothing against the others.
- **Hypothesis (written before results):** few validation URLs hit R2 to R4 (old data), so those will be "untestable on this data". R1 (raw IP) and maybe R5 (shorteners) reach 30 hits. R6 may fail the 90% rule because brand names such as `mail` are common words. Validated rules change recall by under 1 point and do nothing against the path and query word attacks.
- **The ONE change:** a rule layer added after the model, "model OR validated rules"; only rules with at least 30 validation hits and at least 90% phishing among the hits enter. The model threshold is re-set so the whole system flags at most 3.65% of the clean safe URLs.
- **Commands:** `PYTHONHASHSEED=0 .venv/bin/python notebooks/exp11_rules.py --out results/exp11_rules` (needs `data_v2/defence_scores_4a.npz` and `_8b.npz`).
- **Run:** `PYTHONHASHSEED=0`, validation only, no URLs printed. Both score caches passed their gate (4a and 8b: largest absolute difference 6.9e-17 over 17 numbers). Plain thresholds by the Chunk 5 method: 4a 0.7403 and 8b 0.7274, each flagging 2,151 of the 58,930 clean safe URLs (3.650%).
- **Table 1: the six rules on clean validation (16,135 phishing, 58,930 safe).** "Not caught" = phishing hits the plain model misses at the fixed level (new catches); for safe hits, the ones the plain model does not already flag (added false alarms).

| Rule | Hits phishing | Hits safe | Precision | Status | New catches 4a / 8b | Added false alarms 4a / 8b |
|---|---|---|---|---|---|---|
| R1 raw IPv4 host | 732 | 7 | 99.05% | **VALIDATED** | 0 / 0 | 0 / 1 |
| R2 `xn--` in host | 26 | 3 | 89.7% | untestable on this data (29 hits) | (3 / 4) | (3 / 3) |
| R3 non-ASCII in host | 8 | 27 | 22.9% | NOT validated (35 hits, precision below 90%) | (0 / 0) | (2 / 0) |
| R4 `@` before host | 1 | 3 | 25.0% | untestable (4 hits) | (0 / 0) | (1 / 0) |
| R5 shortener list | 2 | 0 | 100% | untestable (2 hits) | (0 / 0) | (0 / 0) |
| R6 brand in subdomain | 543 | 120 | 81.9% | NOT validated (precision below 90%) | (22 / 25) | (111 / 109) |

  Numbers in brackets are for rules that did NOT enter; they are not results. R2 to R5 are listed as untestable or not validated, as locked.
- **Table 2: hits on the edited sets.** R1 to R5 give the same hit counts in every edited set (the edits never touch the host kind), so path words and query words cannot change them. **R6 reacts to our own subdomain attack:** after the extra-subdomain edit R6 fires on 4,279 of 16,135 phishing URLs (was 543) and on 3,665 of the 15,000 safe sample URLs (was 29); after the random mix 2,440 and 1,837. That is the weakness I named in the rules: the subdomain attack adds words like `mail`, `news`, `shop`, `docs`, which are on the brand list. R6 was not validated and does not enter, so this does not affect the system below, but it would have been a bad rule on edited URLs.
- **Table 3: "model OR validated rules (R1 only)" against the plain model, both at 3.65% for the whole system (4a is the primary):**

| Measure | Plain 4a | 4a OR R1 | Plain 8b | 8b OR R1 |
|---|---|---|---|---|
| Whole-system threshold | 0.7403 | 0.7403 (the 7 safe R1 hits were already flagged) | 0.7274 | 0.7274 |
| Clean recall / precision / F1 | 0.8615 / 0.8660 / 0.8638 | 0.8615 / 0.8660 / 0.8638 | 0.8752 / 0.8678 / 0.8715 | 0.8752 / 0.8678 / 0.8715 |
| Recall: path words / query words / random mix | 0.5906 / 0.5538 / 0.6214 | 0.5949 / 0.5564 / 0.6265 (+0.43 / +0.26 / +0.51 pt) | 0.4985 / 0.5269 / 0.5531 | 0.5099 / 0.5319 / 0.5626 (+1.14 / +0.50 / +0.95 pt) |
| Recall: look-alike / subdomains / shortening / padding | 0.8411 / 0.9028 / 0.8144 / 0.8211 | unchanged (0.8411 / 0.9028 / 0.8144 / 0.8211) | 0.8568 / 0.9091 / 0.8330 / 0.8057 | 0.8568 / 0.9091 / 0.8329 / 0.8056 |
| Edited safe flagged: path / query / mix | 0.0233 / 0.0091 / 0.1078 | 0.0233 / 0.0091 / 0.1078 | 0.0123 / 0.0037 / 0.0788 | 0.0124 / 0.0038 / 0.0788 |
| Threshold 0.5: recall / false alarms | 0.9256 / 9.10% | 0.9256 / 9.10% | 0.9307 / 8.46% | 0.9307 / 8.46% |

- **What it means in plain words:**
  - **Only one rule is good enough: raw IP addresses (R1).** 732 phishing and 7 safe URLs have an IP as host (99% phishing). But the model already catches every one of them at its normal setting, so on clean data the rule adds nothing. Its only effect is under the word-adding attacks, where the model drops some IP URLs after the edit and the rule keeps them: +0.3 to +0.5 points for 4a, +0.5 to +1.1 points for 8b. That is tiny, and it comes with no extra false alarms.
  - **Four rules cannot be judged on this data.** Punycode (29 hits, 26 phishing), `@` tricks (4 hits) and shorteners (2 hits) are too rare in this older data to say whether they work. They are not "failed" and not "proved". Non-ASCII hosts (R3) have enough hits but are mostly SAFE (27 of 35); I did not look at why. The brand rule (R6) reaches 82% precision, below the 90% bar, and fires on our own attack words.
  - **Hypothesis check (written before results):** R2 to R4 untestable: partly wrong (R3 had 35 hits and failed on precision instead). R1 validated: right. R5 maybe: wrong (2 hits). R6 fails 90%: right (81.9%). Recall change under 1 point and nothing against path and query words: right for 4a on clean data (zero) and almost right on attacks (+0.3 to +0.5 point); for 8b the attack gain reaches +1.1 point on path words.
- **Limits:** the rules are chosen (validated) and measured on the same validation data, so the small gains are slightly optimistic; the sealed set is the unbiased check. Four rules are untestable here, so "not validated" says nothing about their value on newer data (shorteners and punycode may be common in current phishing). The attacks never change the host kind, so they cannot test the rules; an attacker who knows R1 simply registers a domain. Plain-model rows use the Chunk 5 threshold method (4a clean recall 0.8615, the older log says 0.8617 from the quantile method: one URL of difference at the threshold).
- **Decision:** none (rules were locked). **Validated rules entering the final system: R1 only.**
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 12: trimming guard (scoring only)

- **Threat model (plain words):** the attacker appends harmless-looking words to the query or to the end of the path of a phishing URL, hoping the model's score drops below the alert level. They can see and edit the whole URL text, but not the host's registered domain (the phishing page lives there). In the first part they do NOT know about the guard. In the adaptive part they know the guard and may put their words somewhere the guard does not trim (the middle of the path, the host, look-alike letters). The goal is a score under the alert level.
- **Honest warning, locked before any result (owner's addition 1):** the guard trims exactly the two places where two of our attack families add words (the end of the path for "path words", the query for "query words", and in part the random mix). So passing criterion (a) is **partly by construction** and is not evidence of robustness. The honest tests are the adaptive attack and the first-position trigger below. **If the guard is kept but the adaptive attack evades it in 90% or more of the pool, this entry says the guard is a speed bump, not a robust defence.**
- **Hypothesis (written before results):** g1 (drops the query) helps the query-word attack a lot and the path-word attack little; g2 (also drops the last path segment) helps both. Each may cost some clean recall or add edited-safe flags, since the maximum of several scores is higher for every URL (the threshold is re-set to compensate). Part of the data has no query (about 12% of phishing URLs have one in the validation data), so g1 can only help that part. For the 9c backdoor: g2 removes a trigger that is the last path segment, but not one in the first position, because the model reads 3-letter pieces without position.
- **The ONE change:** score the URL AND trimmed copies and use the maximum score; g1 and g2 as defined in the Chunk 5 rules (a copy that would leave only the host is skipped). Thresholds are re-set per variant so the whole system flags at most 3.65% of the clean validation safe URLs.
- **Commands (all with `PYTHONHASHSEED=0`, from the repo root):** `.venv/bin/python notebooks/decide_guard.py --out results/exp12_guard` (the locked rules, prints PASS/FAIL, writes `decision.json`); then the report-only parts (8b table, other attack families, 9c backdoor with the guard, adaptive attack), listed below with their results.
- **Run (`PYTHONHASHSEED=0`, validation only):** `notebooks/decide_guard.py` (4a, the locked decision), the same script for 8b into `results/exp12_guard_8b` (report only), `notebooks/exp12_report.py` (full tables, `results/exp12_guard/guard_table_4a.csv`, `_8b.csv`), `notebooks/exp12_backdoor.py --guard g2` (9c, `results/exp12_guard/backdoor_9c.csv`), `notebooks/adaptive_attack.py --tag 4a --objective plain|g2` (hill-climbs; per-URL scores in git-ignored `data_v2/adaptive_4a_*.npz`). No guard was kept, so the report-only parts use **g2** as locked ("the kept variant, or g2 if none is kept").
- **Thresholds (4a):** plain 0.7403; g1 0.8141; g2 0.8716 (each flags exactly 2,151 of 58,930 clean safe URLs, 3.650%). Taking the maximum over copies makes all scores higher, so the threshold has to rise.
- **Locked decision, printed by `decide_guard.py` (4a; 8b report-only in brackets):**

| Criterion | g1 | g2 |
|---|---|---|
| (a) mean recall over path words / query words / random mix, needs >= +5.00 pt | 0.5886 to 0.6735 (+8.49 pt) PASS [8b +10.58] | 0.5886 to 0.6943 (+10.57 pt) PASS [8b +13.77] |
| (b) clean recall drops by <= 1.00 pt | 0.8615 to 0.8289 (**-3.26 pt**) **FAIL** [8b -2.89] | 0.8615 to 0.8019 (**-5.97 pt**) **FAIL** [8b -5.80] |
| (c) edited safe flagged rises by <= 2.00 pt (path / query / mix) | -0.27 / **+2.63** / +1.03 pt **FAIL** [8b query +2.88] | +0.42 / **+2.63** / -0.79 pt **FAIL** [8b query +3.00] |
| (d) AUC falls by <= 0.005 | 0.9745 to 0.9702 (-0.0043) PASS | 0.9745 to 0.9621 (-0.0124) **FAIL** [8b -0.0118] |
| **Decision** | **REVERT** [8b REVERT] | **REVERT** [8b REVERT] |

  Per attack (4a, recall at the matched level): path words 0.5906 / g1 0.5510 (-3.97 pt) / g2 0.6211 (+3.04 pt); query words 0.5538 / 0.7841 (+23.04) / 0.7584 (+20.46); random mix 0.6214 / 0.6853 (+6.39) / 0.7034 (+8.19).
- **Report-only: the other four attack families (4a, matched level, recall plain / g1 / g2):** look-alike 0.8411 / 0.8069 / 0.7787; extra subdomains 0.9028 / 0.8720 / 0.8402; path shortening 0.8144 / 0.7753 / 0.7352; padding 0.8211 / 0.7825 / 0.8148. The guard LOWERS recall under all four of the families it was not built for (by 3 to 8 points, except g2 under padding: -0.63 pt). At threshold 0.5 the false alarms rise from 9.10% (plain) to 11.76% (g1) and 18.43% (g2). 8b shows the same pattern (tables in the CSV).
- **Report-only: the 9c backdoor (scoring only, 4 poisoned models, C = 13,904; 1,641 of these have no path, where first and last position are the same string).** Share of C NOT caught after adding the string (percent). The guard threshold is re-set on each poisoned model's own guarded scores (whole system 3.65%):

| Model | No guard: trigger last / control last | No guard: trigger FIRST / control first | Guard g2: trigger last / control last | Guard g2: trigger FIRST / control first |
|---|---|---|---|---|
| Clean 4a (reference) | 13.10 / 12.49 | 13.00 / 12.16 | 9.47 / 9.18 | 19.25 / 18.40 |
| K = 500, seed 42 | 99.63 / 11.90 | 99.63 / 11.36 | 20.37 / 8.98 | **99.77** / 16.95 |
| K = 500, seed 43 | 99.63 / 12.28 | 99.61 / 12.08 | 20.41 / 9.07 | **99.91** / 17.07 |
| K = 2,000, seed 42 | 100.00 / 13.23 | 100.00 / 12.79 | 20.56 / 9.46 | **100.00** / 18.90 |
| K = 2,000, seed 43 | 100.00 / 14.44 | 100.00 / 13.92 | 20.38 / 9.55 | **100.00** / 19.62 |

  Trigger minus control: last position, no guard +85.6 to +87.7 pt, with the guard +10.8 to +11.4 pt; first position, no guard +86.1 to +88.3 pt, with the guard **+80.4 to +82.8 pt**. Note the guard also misses about 8% of the unedited C (guard "none" column 7.8 to 8.2%), which is its clean-recall cost.
- **Report-only: the adaptive attack (white-box, an attacker who KNOWS the guard).** Pool: 500 validation phishing URLs (seed 42) out of 12,794 that both plain 4a and g2 catch; Exp 10 settings. Evasion = pool URLs the system flagged before and no longer flags after:

| Attacked system | Evaded | Mean edits per evader |
|---|---|---|
| Plain 4a, attacker aims at plain 4a (like-for-like pool; Exp 10 had 97.8% on its own pools) | 489 of 500 = **97.8%** | 2.32 |
| g2 guard, attacker aims at the g2 guarded score (knows the guard) | 488 of 500 = **97.6%** | 2.55 |
| g2 guard, attacker aims at plain 4a and does NOT know the guard (endpoints of the first row, scored by the guard) | 192 of 500 = 38.4% | - |
| Plain 4a, attacker aims at the g2 guard (endpoints of the second row, scored by plain 4a) | 336 of 500 = 67.2% | - |

- **What it means in plain words:**
  - **Both guard variants are reverted by the locked rules, and the reason is cost, not benefit.** They do what they are built to do (query-word recall +20 to +23 points), but the maximum-over-copies rule pushes up the scores of safe URLs too, so the threshold has to rise by 0.07 to 0.13 and the model catches 3 to 6 points fewer ordinary phishing URLs at the same false-alarm rate. It also lowers recall under look-alike, subdomain and shortening edits.
  - **Why criterion (c) failed (my reading from the numbers):** harmless words normally make a SAFE URL look safer (flagged 0.91% under the query-word edit, against 3.52% for the unedited sample). The guard trims those words and so returns the share to the clean level (3.54%). That "rise" of 2.63 points is the guard removing the words' effect on safe URLs as well. Under the locked rule it counts against the guard. I do not relax it.
  - **Honest reading of criterion (a): it is partly by construction** (owner's note). The guard trims the places where our path-word and query-word attacks add words, so a recall gain there says little about robustness. The honest tests were the two below.
  - **First-position trigger:** the guard removes a trigger at the end of the path (success falls from about 99.6% to about 20%; the remainder is consistent with the 11.8% of C that has no path, where trimming leaves nothing to remove, plus the guard's own misses of about 8%, but I did not separate these), but a trigger as the FIRST path segment still works in 99.8 to 100% of cases. So the guard does not remove the backdoor; it only hides it at the position the attacker happened to train. This confirms the hypothesis (the model reads 3-letter pieces without position).
  - **Adaptive attack: speed bump, not a robust defence.** An attacker who knows the g2 guard evades it on 97.6% of the pool, with about 2.5 edits, the same as without a guard (97.8%). The guard helps only against an attacker who does not know it (38.4% evade it instead of 97.8%). **Per the owner's rule: if this guard had been kept, the log would have to call it a speed bump; it was not kept, and these numbers would not have supported calling it more.**
  - **Hypothesis check:** g1 helps query words a lot and path words little: wrong for path words (g1 LOWERS path-word recall by 3.97 points; the max rule can only keep or raise a score, and the thresholds rose). g2 helps both: right for recall (+3.04 and +20.46), but with the cost above. Clean-recall cost, edited-safe rise: confirmed. 9c prediction (removes last-position, not first-position trigger): confirmed.
- **Limits:** one pool of 500 and one seed for the adaptive attack; the edits are our own six operations and edited URLs were not checked to still work; the attacker knows the guard but nothing in the experiment limits what a smarter attacker could do (for example move the trigger). Criterion (c) uses the same 15,000-URL safe sample for all variants. The guard thresholds for the 9c models were re-set on each model's own clean validation safe URLs, as is the plain threshold in Exp 9c (the saved quantile threshold, which can differ by one URL from the Chunk 5 method). No variants were added or tuned after seeing results.
- **Decision (locked rules): g1 REVERT, g2 REVERT. No guard in the final system.**
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 13: the "unsure" answer (report only, no keep/revert)

- **Threat model (plain words):** the attacker edits the phishing URL (harmless words, look-alike letters, extra subdomains, shortening, padding) and wants the verdict "safe". They do not control the window: it is fixed from the clean validation scores, and they cannot see it. An edit that lowers the score only a little now lands in "unsure" instead of "safe". The goal for the defender is that a silent miss becomes a visible "unsure"; the price is that part of the normal traffic is "unsure" too, and something else (a person, another check) has to decide those.
- **Hypothesis (written before results):** a good part of the silent misses under the word attacks sit close to the threshold and become "unsure", but not most of them (the white-box attack goes far below the threshold). The cost is 10% of the traffic plus every bare URL, and the validation phishing URLs that are bare are lost to "unsure" (bare-domain routing sends them there whatever the score).
- **The ONE change (a second view, not the primary system):** a verdict with three answers. Systems shown: the plain model and "model + validated rules (R1)" (no guard was kept), for 4a and 8b. Windows 5% / 10% (operating point) / 20% and bare-domain routing as fixed in the Chunk 5 rules; the 0% row is bare-domain routing alone.
- **Commands:** `PYTHONHASHSEED=0 .venv/bin/python notebooks/exp13_abstain.py --rules-json results/exp11_rules/validated_rules.json --out results/exp13_abstain`.
- **Run (`PYTHONHASHSEED=0`, validation only):** thresholds are the Chunk 5 whole-system ones (4a 0.7403, 8b 0.7274 for both systems; R1's 7 safe hits were already flagged). Window half-widths (4a, score units): 5% 0.1055, 10% 0.1916, 20% 0.2554; (8b) 0.1113, 0.2047, 0.2688. Files: `results/exp13_abstain/{curve.csv, attacked_verdicts.csv, heldout_bare.csv, abstain_config.json, report.txt}`.
- **Surprise first, because it changes how to read everything below:** 18.35% of the clean validation SAFE URLs (and 998 = 6.2% of the phishing URLs) are bare domains, so **bare-domain routing alone already makes 15.7% of ALL clean validation URLs "unsure"**. The 10% window is defined on the score and is added on top of that, so at the operating point the real share of "unsure" is **24.6%** (coverage 75.4%), not 10%. I report the real share in every row.
- **Table 1: clean validation, 4a plain model (the "model + R1" rows differ by 0.01 point or less):**

| Window (share of all URLs by score) | Coverage | Phishing verdict (of all phishing) | Phishing or unsure | False alarms (of all safe) | Recall among decided | False alarms among decided |
|---|---|---|---|---|---|---|
| none (the plain 3.65% system) | 100% | 0.8615 | 0.8615 | 3.65% | 0.8615 | 3.65% |
| 0% (bare routing only) | 84.3% | 0.8207 | 0.8826 | 3.34% | 0.8748 | 4.10% |
| 5% | 79.9% | 0.7690 | 0.9130 | 1.82% | 0.8984 | 2.32% |
| **10% (operating point)** | **75.4%** | **0.6800** | **0.9316** | **0.70%** | **0.9086** | **0.93%** |
| 20% | 66.1% | 0.3437 | 0.9427 | 0.04% | 0.8572 | 0.05% |

  8b plain model, same rows: 10%: coverage 75.4%, phishing verdict 0.7015, phishing or unsure 0.9415, false alarms 0.67%, recall among decided 0.9230, false alarms among decided 0.89%. Phishing URLs lost to "unsure" because they are bare: 998 of 16,135 (6.2%) in every row; at 10% a total of 4,059 (25.2%) phishing URLs are "unsure" for any reason.
- **Table 2: what happens to the edited phishing URLs (4a plain model, operating point 10% + bare routing).** "Silent misses" = edited phishing URLs the plain 3.65% system calls safe (no window, no bare routing). Shares of ALL edited phishing URLs, and the shares of the silent misses:

| Attack | Phishing verdict | Unsure | Safe | Silent misses (count of 16,135) | Silent misses now "unsure" | Silent misses still "safe" | Caught before, now "unsure" |
|---|---|---|---|---|---|---|---|
| path words | 43.95% | 23.45% | 32.59% | 6,605 | **20.4%** | 79.6% | 25.6% |
| query words | 40.97% | 22.97% | 36.06% | 7,200 | **19.2%** | 80.8% | 26.0% |
| random mix | 45.50% | 25.14% | 29.35% | 6,108 | **22.5%** | 77.5% | 26.8% |
| look-alike | 64.05% | 27.93% | 8.03% | 2,564 | 49.5% | 50.5% | 23.9% |
| extra subdomains | 74.68% | 20.36% | 4.96% | 1,569 | 49.0% | 51.0% | 17.3% |
| path shortening | 61.21% | 29.27% | 9.52% | 2,994 | 48.7% | 51.3% | 24.8% |
| padding | 66.65% | 22.42% | 10.93% | 2,886 | 38.9% | 61.1% | 18.8% |

  Edited SAFE URLs at the same setting are called "unsure" in 2% (query words) to 28% (shortening, subdomains) of cases (safe URLs: phishing verdict 0.1% to 6.8%). 8b is similar: silent misses now unsure 16.9% / 17.8% / 19.3% for the three word attacks, 44 to 52% for the others.
- **Held-out bare sets (10,000 safe and 10,000 phishing registered domains):** **all 20,000 go to "unsure"** (100%, every row), because they are bare domains by construction. Without routing, the model alone flagged 98 to 99% of both (Exp 3 and 5: the known flaw).
- **What it means in plain words:**
  - **The "unsure" answer buys visibility, not safety.** For the three harmless-word attacks only about one silent miss in five (19 to 23%) becomes "unsure"; four in five stay silent. The other attacks do better (39 to 50%). The white-box attack of Exp 12 goes well below the threshold, so it would not be caught by a window either (I did not run that combination; it is listed below as not done).
  - **The price is large.** At the operating point 24.6% of all clean validation URLs are "unsure" (15.7 points are bare-domain routing alone), 17 to 27% of the normally caught edited phishing URLs become "unsure" too (last column of Table 2), and the number of URLs that get a "phishing" verdict falls from 86.2% to 68.0% of the phishing. In return the false alarms among decided URLs fall from 3.65% to 0.93%, and recall among decided URLs rises from 86.2% to 90.9%. That last number looks good but is a selection effect: the hard URLs were moved out of the count.
  - **Bare-domain routing is a choice, not a result.** It sends every bare domain to "unsure", including the 18% of safe validation URLs and the whole held-out bare set. It turns the known bare-domain flaw from a wrong "phishing" into an honest "unsure", and it makes the system say nothing about bare domains.
  - **Hypothesis check:** "a good part of silent misses become unsure, not most": right (19 to 50%, never more than half). "Cost is 10% of traffic plus every bare URL": the cost is 24.6%, more than 10% because the two overlap only partly. "Bare phishing lost to unsure": confirmed, 998 URLs.
- **Limits:** the window is fixed on the same clean validation data it is reported on; it is symmetric and ignores direction; the edited sets are our own attacks. "Unsure" helps only if something else (a person, another check) handles those URLs; the cost of that is not measured. I did not test the adaptive attack against the window (an attacker who knows the window can aim for the lower edge); that run belongs to the final table, where it is done for the final system. The "model + R1" system is not meaningfully different from the plain model here.
- **Commit:** pending (not committed until the owner says so)

---

## Experiment 14: poison check on the training data (data side; at most 2 trainings)

- **Threat model (plain words):** the defender sees only the finished training file (url, label) and not who touched what. The attacker is the one from Exp 9: random flips (9a), phishing relabelled safe (9b), or safe-labelled copies of phishing URLs with a trigger (9c). The check asks: does this row look like its nearest neighbours' label? An attacker who knew the check could add backdoor rows that have no near neighbours (not tested). The goal of the check is to find the touched rows without flagging many honest ones.
- **Hypothesis (written before results):** at K = 500 most backdoor rows are flagged, because each is a copy of a real phishing URL (plus the trigger) labelled the other way, so its neighbours are the original and similar phishing URLs. At K = 2,000 fewer are flagged, since the added rows become each other's neighbours and outvote the originals. Random flips (9a) are flagged in proportion to how clean their neighbourhood is; 9b is flagged less than 9a, since the relabelled phishing URLs often sit in groups of similar phishing URLs whose other members are also relabelled only rarely (5% to 10%). Untouched rows are flagged rarely (under 2%).
- **The ONE change (data side):** a nearest-neighbour label check on the training file. Embedding: the two n-gram blocks of the 4a recipe (1,000 whole-URL character 3-grams + 500 host-only 3-grams, same `CountVectorizer` settings as `fit_recipe`), refitted on that file, TF-IDF weighted (idf fitted on that file) and L2-normalised; cosine similarity; exact search (chunked dense matrix products; no extra package); k = 5 nearest OTHER rows; flag a row if at least 4 of its 5 neighbours have the opposite label. Checked: the touched rows (flipped rows for 9a and 9b, the appended rows for 9c) plus a random sample of 20,000 untouched rows (seed 42), against ALL rows of the file. For the two 9c seed-42 files (K = 500, 2,000) every row is checked (owner's answer 2), and every flagged row is removed; the 20,000-row sample is a subset of that scan, so the table is the same design for all 22 files. Ties in similarity are broken arbitrarily but deterministically.
- **Then, at most 2 trainings:** the cleaned K = 500 and K = 2,000 files (seed 42), Exp 4a recipe (`train_chunk3.py`, unchanged), one at a time. Report clean recall at the fixed level and the trigger success rate (trigger vs control as the last path segment, same C = 13,904) against the uncleaned poisoned models of Exp 9c, and the number of clean rows removed.
- **Commands (`PYTHONHASHSEED=0`):** `.venv/bin/python notebooks/exp14_poison_check.py --file data_v2/train_poison_<kind>_<setting>.csv` for the 22 files (`--full --write-clean ...` for the two 9c seed-42 files); `.venv/bin/python notebooks/exp14_poison_check.py --summary --out results/exp14_poison_check`; `train_chunk3.py --suffix p14_k<K>_s42 --train-file data_v2/train_clean_backdoor_k<K>_s42.csv --ngram-blocks url:3:1000,host:3:500`; `evaluate.py` with the 9c flags and `--out results/exp14_clean_k<K>_s42`; `notebooks/exp14_trigger.py`.
- **Run (`PYTHONHASHSEED=0`):** 22 checks (`results/exp14_poison_check/check_<setting>.json`, `summary.csv`; flagged row indices in git-ignored `data_v2/exp14_flags_*.npz`, no URLs anywhere in the results). One check takes 50 s to 4.5 min; the two full scans of the 9c seed-42 files took about 12 minutes each. The 20,000-row untouched sample is the same seed-42 draw in all files, and for the two full scans it is a subset of the full scan (the full-scan untouched rate 2.15% / 2.16% agrees with the sample rate 2.20% / 2.17%). Scans never ran at the same time as a training.
- **Table 1: share of rows flagged (k = 5, flag at 4 of 5 opposite neighbours).** Touched = changed rows; untouched = 20,000 random unchanged rows. Range over the seeds (3 seeds for 9a and 9b, 2 for 9c):

| Setting | Touched rows | Touched flagged | Untouched flagged (20,000 sample) |
|---|---|---|---|
| 9a random flips, p = 1% | 3,503 | 92.1% to 93.4% | 1.9% to 2.2% |
| 9a, p = 5% | 17,515 | 90.5% to 90.7% | 2.1% to 2.3% |
| 9a, p = 10% | 35,030 | 84.8% to 85.3% | 2.0% to 2.2% |
| 9b phishing relabelled safe, p = 1% | 753 | 83.3% to 84.2% | 2.1% |
| 9b, p = 5% | 3,765 | 79.7% to 81.4% | 1.9% to 2.1% |
| 9b, p = 10% | 7,530 | 75.3% to 76.0% | 1.9% to 2.1% |
| **9c backdoor, K = 500** | 500 | **61.2% to 64.4%** | 2.1% to 2.2% |
| **9c backdoor, K = 2,000** | 2,000 | **51.2% to 53.3%** | 2.2% |

- **Table 2: the two cleaning trainings** (trainings 1 and 2 of the 2 allowed; Exp 4a recipe on the cleaned file; peak memory footprint 12.3 GB, 155 s and 199 s; no failure). "Cleaned" = every flagged row of the file removed (full scan):

| | K = 500 (seed 42) | K = 2,000 (seed 42) |
|---|---|---|
| Rows removed | 7,867 of 350,802 = 322 backdoor rows (of 500) + **7,545 clean rows** (2.15% of the clean rows; 60% of them phishing) | 8,586 of 352,302 = 1,023 backdoor rows (of 2,000) + **7,563 clean rows** (2.16%; 60% phishing) |
| Backdoor rows left in the training file | 178 | 977 |
| Clean recall at 3.65%: clean 4a / uncleaned poisoned model / cleaned model | 86.17 / 86.14 / **85.53** | 86.17 / 86.22 / **85.24** |
| AUC x 100: clean 4a / uncleaned / cleaned | 97.45 / 97.45 / 97.33 | 97.45 / 97.49 / 97.31 |
| False alarms at threshold 0.5: clean 4a / uncleaned / cleaned | 9.10 / 9.16 / 8.75 | 9.10 / 9.24 / 8.77 |
| Not caught after the edit (share of C = 13,904), no edit: uncleaned / cleaned | 1.18% / 1.91% | 1.37% / 2.27% |
| Control `/cesead` added: uncleaned / cleaned | 11.90% / 13.67% | 13.23% / 13.90% |
| **Trigger `/nadinc` added: uncleaned / cleaned** | **99.63% / 84.13%** [83.52, 84.73] | **100.00% / 98.37%** [98.14, 98.57] |
| Trigger minus control (points): uncleaned / cleaned | +87.73 / **+70.47** | +86.77 / **+84.46** |

- **What it means in plain words:**
  - **The check finds most random mistakes but only about half to two thirds of the backdoor rows.** It flags 85% to 93% of the random flips (9a), 75% to 84% of the targeted relabels (9b), and 51% to 64% of the backdoor rows (9c). Hypothesis check: "most backdoor rows flagged at K = 500": 61 to 64%, only a modest majority; "fewer at K = 2,000": right (51 to 53%); "9b flagged less than 9a": right; "untouched flagged under 2%": **wrong, 1.9% to 2.3%**.
  - **The price is about 2% of the clean rows (7,500 rows), 60% of them phishing.** In plain words: honest rows whose neighbours mostly disagree with them (labels that are noisy, or genuinely mixed neighbourhoods) are removed too. The cleaned models have 0.6 to 1.0 point LOWER clean recall than the uncleaned poisoned models (85.53 and 85.24 against 86.14 and 86.22; single seed, the noise is about 0.3 point, so the K = 2,000 drop is probably real and the K = 500 drop is borderline), and a lower AUC (-0.12 and -0.18 points).
  - **The backdoor mostly survives.** After removing the flagged rows, the trigger still makes the model miss 84% (K = 500) and 98% (K = 2,000) of the URLs it would otherwise catch (against 12 to 14% for the control). With 178 backdoor rows left in a file of 343,000 rows the model still learns the signature. At K = 500 the effect (trigger minus control) falls from +87.7 to +70.5 points; at K = 2,000 from +86.8 to +84.5. **Cleaning with this check is not a working defence against this backdoor.** It would help more against random noise, but I did not retrain on cleaned 9a/9b files (limit of 2 trainings), so I cannot say how much recall it would recover.
  - **The check is easy to defeat.** The backdoor rows here are copies of existing phishing URLs, so each has near neighbours with the opposite label; an attacker who knows the check could add rows with no near neighbours (not tested). A defender sees only the poisoned file; I used the touched-row list only to report the table, not to clean.
- **Limits:** one seed (42) for each cleaning training and one pair of K values; the check is exact for this embedding (1,500 columns) but I tried no other k, other thresholds or other embeddings, as locked; "flagged" depends on duplicates and ties (exact duplicates with opposite labels count as neighbours; ties are broken arbitrarily); the 2.2% rate of flagging untouched rows is measured on the training data's own labels, which come from the Kaggle data and may be noisy anyway; trigger success uses the same C as Exp 9c and each model's own matched threshold (the saved quantile threshold), as in Exp 9c.
- **Decision:** none (report-only).
- **Commit:** pending (not committed until the owner says so)

---

## Chunk 5 final combined table and summary (report only; validation data only)

Produced by `PYTHONHASHSEED=0 .venv/bin/python notebooks/final_defence_table.py --out results/defence_final` (all scripts of this chunk ran with `PYTHONHASHSEED=0`). Whole-system false-alarm level 3.65% of the 58,930 clean validation safe URLs (2,151 flagged) for every "3.65%" row. No guard was kept (Exp 12), so the planned rows "+ guard", "+ guard + rules" and "+ guard + rules + abstain" collapse into the rows below; the rejected g2 guard is shown as a reference row only. **Final system (owner's addition 2): plain 4a + the validated rule R1; the "unsure" mode is a second view.** Its configuration is in `results/final_system_config.json`.

**Model 4a (primary).** Attack columns = recall (share of edited phishing URLs with the verdict "phishing"). Edited-safe = share of edited safe URLs with the verdict "phishing" (path words / query words / random mix).

| System | Clean recall | False alarms | Coverage | Path / query / mix | Look-alike / subdomains / shortening / padding | Edited safe (path / query / mix) | 9c trigger success K = 500 / 2,000 (control) | White-box evasion |
|---|---|---|---|---|---|---|---|---|
| Plain 4a | 86.15 | 3.65% | 100% | 59.06 / 55.38 / 62.14 | 84.11 / 90.28 / 81.44 / 82.11 | 2.33 / 0.91 / 10.78 | 99.63 / 100.00 (12.1 / 13.9) | 489/500 = 97.8% |
| **FINAL: plain 4a + R1** | 86.15 | 3.65% | 100% | 59.49 / 55.64 / 62.65 | 84.11 / 90.28 / 81.44 / 82.11 | 2.33 / 0.91 / 10.78 | 94.36 / 94.74 (12.1 / 13.9) | 460/500 = 92.0% |
| Second view: + abstain (10% window + bare routing) | 68.01 (phishing verdict); 93.16 phishing or unsure | 0.71% of all safe; 0.94% of decided | 75.4% | 45.32 / 42.03 / 46.73 | 64.06 / 74.69 / 61.22 / 66.65 | 0.40 / 0.13 / 3.06 | 93.42 / 94.70 as "safe" (6.1 / 6.9) | 393/436 = 90.1% reach "safe" (402/436 = 92.2% not "phishing") |
| Reference, REJECTED: g2 guard alone | 80.19 | 3.65% | 100% | 62.11 / 75.84 / 70.34 | 77.87 / 84.02 / 73.52 / 81.48 | 2.75 / 3.54 / 9.99 | last position about 20%, first position about 99.8 to 100% (Exp 12) | 488/500 = 97.6% |

Threshold-0.5 rows: plain 4a recall 92.56, false alarms 9.10%; with R1 identical (path / query / mix recall 69.38 / 66.17 / 72.74 with R1 against 69.23 / 66.07 / 72.46 without).

**Model 8b (secondary, scoring only; no poisoned 8b model exists, so the 9c column is not applicable):**

| System | Clean recall | False alarms | Coverage | Path / query / mix | Look-alike / subdomains / shortening / padding | Edited safe (path / query / mix) | White-box evasion |
|---|---|---|---|---|---|---|---|
| Plain 8b | 87.52 | 3.65% | 100% | 49.85 / 52.69 / 55.31 | 85.68 / 90.91 / 83.30 / 80.57 | 1.23 / 0.37 / 7.88 | 495/500 = 99.0% |
| 8b + R1 | 87.52 | 3.65% | 100% | 50.99 / 53.19 / 56.26 | 85.68 / 90.91 / 83.29 / 80.56 | 1.24 / 0.38 / 7.88 | 475/500 = 95.0% |
| 8b + R1 + abstain (second view) | 70.17 (phishing verdict); 94.15 phishing or unsure | 0.68% of all safe; 0.90% of decided | 75.4% | 37.77 / 39.44 / 41.23 | 66.38 / 76.24 / 62.63 / 62.55 | 0.17 / 0.07 / 2.22 | 410/436 = 94.0% reach "safe" (94.3% not "phishing") |
| Reference, REJECTED: g2 guard alone | 81.72 | 3.65% | 100% | 55.26 / 76.65 / 67.25 | 79.57 / 85.11 / 75.30 / 81.97 | 1.57 / 3.37 / 8.26 | not run |

**Which defences were kept and which were not (plain words):**
- **Kept (by the locked rules): rule R1 (raw IP address as host).** It is the only rule with enough data and over 90% precision. **Cost:** nothing measurable on clean data (recall and false alarms unchanged, no new false alarms), +0.3 to +0.5 point under the word attacks for 4a. **Honest benefit:** about zero. The model already catches these URLs; the lower white-box and trigger numbers in the FINAL row (92.0%, 94.4%) are only the share of the pool made of IP-host URLs (29 of the 489 evaders; the 732 IP-host URLs are 5.3% of the 13,904 URLs in C) that the rule keeps flagged. An attacker who knows R1 simply uses a registered domain.
- **Not kept: the trimming guard (g1 and g2), both REVERTED.** Cost: -3.3 and -6.0 points of clean recall, -3 to -8 points under the other four attack families, up to +9 points of false alarms at threshold 0.5. Benefit: +20 points under the query-word attack (by construction) and it removes a trigger placed at the end of the path. It does not stop a trigger placed first (99.8 to 100%) and an attacker who knows it evades it in 97.6% of cases: **a speed bump, not a robust defence.**
- **Not kept: rules R2 to R6.** R2, R4, R5 untestable on this data (29, 4, 2 hits), R3 and R6 failed the 90% precision rule (22.9%, 81.9%); R6 also reacts to our own subdomain attack words.
- **Second view, not a replacement: "unsure".** Cost: 24.6% of all clean validation URLs become "unsure" (15.7 points from bare-domain routing alone), 100% of the held-out bare domains, and the "phishing" verdict falls from 86% to 68% of the phishing URLs; the extra people or checks needed to settle the "unsure" ones are not measured. Benefit: false alarms among decided URLs 0.94% instead of 3.65%; about one in five silent misses under the word attacks (and about half under the other attacks) turn into "unsure". **An attacker who aims for the lower edge of the window still gets "safe" for 90% (4a) and 94% (8b) of the pool.**
- **Poison check (Exp 14), report-only:** flags 51% to 64% of backdoor rows and 75% to 93% of the random or targeted flips, but also 2.2% of honest rows; cleaning the two 9c files cost 0.6 to 1.0 point of clean recall and left the backdoor working (84% and 98%).

**What this chunk shows, honestly:** none of the defences I tried makes the model robust. The model after Chunk 5 (plain 4a + R1) still loses 92% to 99% of an adaptive attacker's pool (depending on system and model, 4a 92.0% to 97.8%, 8b 95.0% to 99.0%) to a handful of harmless edits (about 2 to 3 per URL), and a 0.14% backdoor still works after the best data check I built. The measurable gains are small (R1, the "unsure" view) or come with clear costs (guard, cleaning). Where the numbers rest on our own attacks, they are not independent evidence. The validated rule R1 and the thresholds were chosen on the same validation data they are reported on.

**Not done:** no test or sealed data, no URL fetched, no package installed, no file deleted, no existing model, recipe, data file or result changed; no push, no commit. Not tested: the abstain window against an adaptive attacker who also knows the bare-domain routing beyond the "reach safe" climb above; guards or cleaning on 8b; other k, thresholds, windows, or guard variants (locked). Attacks are our own six edit families; edited URLs were not checked to still load.
- **Commit:** pending (not committed until the owner says so)

---

## Chunk 6 (prepared, not run): final evaluation script

Start state: branch `v2`, HEAD `43cbbe8` ("Chunk 5: rename a misleading config key (no values changed)"), before it `e6c7821` (the Chunk 5 commit), clean tree. In this chunk I PREPARE one script, `notebooks/final_eval.py`, which the owner runs HIMSELF, ONCE. I never run it in `--final` mode and never open `~/sealed_eval/sealed_eval.csv`, `~/sealed_eval/sealed_eval_source.csv` or `data_v2/test.csv`. I may test the mechanics only with `--dry-run` on synthetic files of made-up URLs (example domains) in a temporary folder outside the repo, and on `data_v2/val_redacted.csv`. These rules cannot change after any result is seen.

**Owner's hard rules (in plain words):**
- Nothing is tuned. Every threshold, window, rule and model comes from `results/final_system_config.json` and is never recomputed on test or sealed data.
- Systems scored: (1) primary = plain 4a + the R1 rule as in the config; (2) plain 4a; (3) the 8b model (secondary); (4) second view: primary + the "unsure" layer (bare-domain routing and window from the config).
- Data: (a) `data_v2/test.csv`, the domain-grouped Kaggle test split, with `privacy.redact_url` applied first; (b) `~/sealed_eval/sealed_eval.csv` joined with `~/sealed_eval/sealed_eval_source.csv`, reported per source and bare versus has-a-path, with a plain statement in the report that every safe URL there is a bare domain.
- Metrics at the frozen threshold: recall, false-alarm rate, precision, F1, AUC, confusion counts, 95% Wilson intervals for the rates. On the test split also: recall under the 7 attack families and the edited-safe flag shares (same attack code, word list and settings as `evaluate.py`), plus the bare-versus-path split. For the "unsure" view: coverage, recall and false-alarm rate among decided URLs, and verdict shares.
- Safety gates: requires `--final`; asks for the exact phrase `RUN FINAL ONCE`; prints and checks the SHA-256 of the config, models, recipes and `defence_layers.py`; refuses to run if `results/final_v2/` or a lock file exists; writes `results/final_v2/` (counts and rates only, no URLs) only at the end, and creates the lock file only after all metrics are computed, so a crash before the end leaves no lock and a rerun after a bug fix is possible.
- `--dry-run` runs the same code on synthetic data and `val_redacted.csv`, writes to a temporary folder outside the repo and never touches the real paths.
- `notebooks/build_final_table.py` is written but NOT run; it reads only saved results folders, builds the stage-by-stage table and never changes a number. The owner runs it after the final run.

**Hypotheses, written BEFORE anything is run, exactly as the owner wrote them:**
- **H1:** on the test split the primary system's recall will be within about 3 points of its validation value (0.8617) and its false-alarm rate within about 1.5 points of 3.65%.
- **H2:** on the sealed set almost all safe URLs are bare domains, so the false-alarm rate of plain 4a and the primary system will be very high and precision low; this measures the known bare-domain flaw, not new behaviour.
- **H3:** sealed phishing recall will differ by source (direction unknown).
- **H4:** in the "unsure" view nearly all sealed safe URLs become "unsure".
- **H5:** 8b is similar to 4a on clean data and weaker under attacks.

  Factual note added by me (the H1 text above is unchanged): the primary system's validation recall in the frozen config is 0.8615 by the Chunk 5 threshold method (0.8617 by the older quantile method); the difference is one URL at the threshold.

**Points I fixed now, before any code (approved with the plan):**
1. Thresholds, window, rules and models come only from the config (`systems.final_system_4a_plus_rules`, `plain_4a`, `plain_8b`, `second_view_abstain_classify_config`). The script contains no `quantile`, `set_threshold` or `abstain_width` call (a check test greps the source for them).
2. AUC is the AUC of the model score (rules and windows do not change a score): the primary system and plain 4a share one AUC, 8b has its own, the "unsure" view has none.
3. Config hash gate: a file cannot hold its own hash, so the script requires the config, `final_eval.py`, `defence_layers.py` and `attacks.py` to be tracked and identical to `HEAD`, prints the config's SHA-256 and the commit hash, and checks models, recipes, `defence_layers.py` and `attacks.py` against the hashes inside the config. The owner must therefore commit `final_eval.py` before the run.
4. `PYTHONHASHSEED=0` is required (the attack word list depends on it); the script aborts otherwise and checks the word list's SHA-256 against a constant computed from the training file before the run.
5. Lock logic: all metrics and all output text are built in memory and printed to the terminal before anything is written; then `results/final_v2.lock` is created exclusively, then `results/final_v2/` and its files. A crash before that point leaves no lock and no folder.
6. Sealed rows are joined with their source file by row position (same order, equal length checked). Test and sealed URLs are redacted first (the test file has no redacted copy). No attacks are run on the sealed set.
7. Python commands in this entry start with `PYTHONHASHSEED=0`, as in all earlier chunks.
**Five additions by the owner, locked before any code:**
1. **Row-count assertions.** In `final_eval.py`, for every system and every dataset, the number of rows read must equal the number of rows scored and the number of labels; any mismatch aborts.
2. **Read-only preview of `build_final_table.py`.** Run once, before finishing, on the saved results folders only, writing only to a temporary folder outside the repo (never `results/`); the table it prints is shown to the owner and any bug is fixed. It must not create `results/final_stage_table.*` in the repo.
3. **Report backup.** In `--final` the full report is built and printed in the terminal before any write, and a copy of the printed report is saved to a git-ignored scratch file outside the repo (`~/final_report_backup.txt`) BEFORE the lock is created.
4. **Small groups.** In all tables the count is reported for every subgroup, but any rate whose group has fewer than 50 rows is marked "too few to read" (in the code and in this log).
5. **Gate failures.** Every gate failure prints a plain message with the expected value, the actual value and "nothing was run", then exits. No gate can be bypassed by a flag.

**Owner's stopping rules for this chunk:** I never run `final_eval.py` with `--final` (only with `--dry-run`; if a command would contain `--final` I stop and tell the owner instead); nothing is staged, committed or pushed; when the scripts are written and tested I stop with a plain-words summary (what I wrote, the output of `check_final_eval.py`, the full dry-run output, whether the dry run reproduced the saved validation numbers exactly with any exception listed, the preview table of `build_final_table.py`, the exact command for the owner, the pre-run checklist, the list of files that would be committed with sizes) and wait; after the owner says so, I commit only the new scripts and the `EXPERIMENTS.md` changes, after showing `git status` and a scan of the files. The real run is done by the owner in the owner's own terminal.
**Auto-mode rules from the owner (the owner is away; no command is approved one by one), and one more gate, locked before any code:**
- Forbidden, however it is done: running `final_eval.py` with `--final` or calling its final-run function (only `--dry-run` and the check script are allowed); `git add`, `commit`, `push`, `tag`, `reset`, `checkout` of files, `stash`; reading, opening, copying, listing the contents of or hashing `~/sealed_eval/*`, `~/sealed_eval_raw/*` or `data_v2/test.csv`; `pip install`, downloads, deleting or renaming any existing file, and editing `results/final_system_config.json`, `notebooks/attacks.py`, `notebooks/defence_layers.py`, any file in `models/` or `models_v2/`, or any already-committed file (except appending to `results/EXPERIMENTS.md`). If anything seems to need a forbidden action, stop and write it in the summary. If the same error stays after 3 fix attempts, stop and report.
- Every command I run is appended, with the time, to `~/auto_mode_command_log.txt` (outside the repo).
- **Terminal gate (added):** in `--final` mode the phrase `RUN FINAL ONCE` is read from the controlling terminal (`/dev/tty`), not from stdin; if stdin is not a terminal or `/dev/tty` cannot be opened the script aborts with a plain message. Piped or echoed input cannot work. `check_final_eval.py` tests this by running the gate function in a child process with stdin redirected from a file (which contains the phrase) and confirming that it aborts.
- Reading of "too few to read" (owner's addition 4), fixed now: the rule is applied to the denominator of each rate (for example, recall uses the phishing rows of that group, the false-alarm rate uses its safe rows, precision uses its flagged rows); a rate with a denominator under 50 is shown as "too few to read" and its count is still given.
- Gate failures that happen before any data is read print "Nothing was run"; the row-count assertions (addition 1) can only fail after data was read and print "NOTHING WAS WRITTEN: no lock file and no results folder were created", which is the accurate statement there.
**What was written (new files, nothing committed or staged):** `notebooks/final_eval.py` (the final evaluation: gates, four systems, test split, sealed set, report, backup copy, lock, results folder), `notebooks/check_final_eval.py` (62 checks on made-up data), `notebooks/build_final_table.py` (stage-by-stage table from saved results folders). `final_eval.py` was never run with `--final`; no sealed or test file was opened, listed, hashed or copied; no model, config, `attacks.py` or `defence_layers.py` was touched.

**Checks (`PYTHONHASHSEED=0 .venv/bin/python notebooks/check_final_eval.py`): ALL 62 CHECKS PASSED (made-up data only; the real run was never started).** They cover: the terminal gate (stdin redirected from a file that holds the phrase aborts with "GATE FAILED: controlling terminal ... Nothing was run"; a missing `/dev/tty` aborts; a wrong phrase aborts); the mode gate (no flag, both flags, `--dry-run-dir` with the real mode); `PYTHONHASHSEED`; the SHA-256 gate for config, models, recipes and code (each tampered hash is caught and shown as expected versus actual); the harmless-word list; the git gate (outside a repo, an untracked required file); existing results folder and existing lock refused; dry-run refuses real-data paths, names containing `test`, and output folders inside the repo; the row-count assertions; rates, Wilson intervals and the "too few to read" rule (49 rows are too few, 50 are read; counts are kept); vectorised verdicts equal `classify_many`; the write order (the report backup exists before the lock; a second write is refused; an output with a URL or an IP-like string aborts before backup, lock and folder); the synthetic sealed files (made-up URLs, all safe URLs bare); and source-text tests (no quantile or threshold-setting call; no bypass option; the only options are `--final`, `--dry-run`, `--dry-run-dir`; real test and sealed paths appear only in the `FINAL` constant and the path guard).
Three first attempts failed for three different reasons, each fixed once: (1) my synthetic safe URLs were subdomains, not bare domains, so I switched to nonsense bare names; (2) the word "quantile" appeared in the script's own docstring; (3) the path test also scanned the docstring. No fix needed a second attempt.

**Dry run (`PYTHONHASHSEED=0 .venv/bin/python notebooks/final_eval.py --dry-run --dry-run-dir <scratchpad>/dry_run_2`):** exit 0, about 10 minutes. All gates passed; stand-in "test" = `data_v2/val_redacted.csv` (75,065 rows), stand-in sealed = 1,930 synthetic made-up rows (3 synthetic sources, one with 30 phishing rows to exercise "too few to read"; every safe URL a bare domain; 205 rows changed by redaction). **It reproduced the saved validation numbers exactly: 82 numbers compared (recall, false-alarm rate, precision, F1 of the four systems; the 7 attack recalls and the 7 edited-safe shares and the clean 15,000-URL safe share for each; the second view's coverage, recall and false-alarm rate among decided and recall-or-unsure; AUC of 4a and 8b), tolerance 1e-12, 0 differ.** Row-count assertions held for every dataset and system. Output went only to the scratchpad folder: `final_v2/` (`metrics.json`, 8 CSV tables, `report.txt`), `final_v2.lock`, `final_report_backup.txt` (written before the lock). A second dry run into the same folder was refused at the gate "must not exist ... Nothing was run". The synthetic-sealed numbers (recall 1.0, false alarms 1.0) are meaningless and only show the mechanics.

**Preview of `build_final_table.py` (read-only, saved folders only, output in the scratchpad, nothing in `results/`):** `.venv/bin/python notebooks/build_final_table.py --out-dir <scratchpad>/preview_table_N [--final-dir <scratchpad>/dry_run_1/final_v2]`. With the dry-run results folder as `--final-dir` it printed 33 rows (v1 reference on validation and on the frozen v1 test split; Chunk 1; Chunk 2 with the Exp 3 variants marked REVERT; Chunk 3 Exp 4a KEEP and 8b KEEP, 4b/5a/5b/6/7/8a REVERT, the two ablations; the validation rows of the final system; the final-run rows, here dry-run data and marked as a preview); with the default it printed 25 rows and the line "The final run (results/final_v2) has not been done yet". One bug found and fixed: pandas turned the text "n/a" (the AUC of the second view) into "nan"; the final-run tables are now read as raw text and only genuine numbers are converted, so no value or text changes. It created no `results/final_stage_table.*` in the repo. It has not been run against a real `results/final_v2`.

**What is NOT tested (to be honest):** the positive path of the terminal prompt (typing the phrase in a real terminal) and of the git gate (it needs `final_eval.py` and the log changes committed, so it can only pass after the owner commits); reading the real `test.csv` and sealed files (only their column layout, taken from the builder scripts, is assumed: `url,label` and one `source` column in the same row order); `build_final_table.py` on a real `results/final_v2`. All three fail safe: a gate prints expected, actual and "Nothing was run" before any data is read.

**The command for the owner (own terminal, repo root):**
```bash
PYTHONHASHSEED=0 .venv/bin/python notebooks/final_eval.py --final
```
It prints the gate results, the files it will read and write, and then waits for the phrase `RUN FINAL ONCE` typed in the terminal. Afterwards: `.venv/bin/python notebooks/build_final_table.py`.

**Pre-run checklist:** (1) `results/final_system_config.json` is committed and unchanged (HEAD `43cbbe8` or later); (2) `notebooks/final_eval.py`, `check_final_eval.py`, `build_final_table.py` and this log are committed (the gate requires every tracked file to equal HEAD and `final_eval.py` to be tracked); `git status --short` shows nothing; (3) `results/final_v2/` and `results/final_v2.lock` do not exist; (4) `PYTHONHASHSEED=0` is set in the command; (5) no training or other heavy job is running (about 6 GB of memory; roughly 20 to 30 minutes expected); (6) files written, only at the end: `results/final_v2/*`, `results/final_v2.lock` (not git-ignored: commit it with the results) and `~/final_report_backup.txt` (outside the repo); (7) a crash before the lock is created leaves no lock and no results folder, so a bug can be fixed (and committed) and the script rerun; a crash after the lock leaves the lock, the full report is already printed in the terminal and saved in `~/final_report_backup.txt`.

**Auto-mode record:** every command I ran in this phase is listed in `~/auto_mode_command_log.txt` (outside the repo). No command contained `final_eval.py ... --final`; no forbidden git verb was used; nothing was staged or committed.

**Terminal-gate bug (found on the first real launch, fixed before the run).** The owner's first real launch (`--final`) stopped at the terminal gate with "GATE FAILED: controlling terminal ... cannot open /dev/tty: File or stream is not seekable. Nothing was run." This happened before any test or sealed file was read and before any metric existed; no lock file, results folder or backup file was created. Cause (reproduced on a pseudo-terminal): the gate opened the terminal with the text-mode `open("/dev/tty", "r+")`; in this Python (3.14.5) the text wrapper checks that the stream is seekable and a terminal is not. A raw `os.open("/dev/tty", os.O_RDWR)` works and `os.isatty` is true. The fix changes only `open_controlling_terminal()` and `read_phrase_from_tty()` in `notebooks/final_eval.py` (the prompt and the reply now go through the raw file descriptor; the stdin-must-be-a-terminal check, the messages, `check_phrase` and every other gate and all metric code are unchanged). My earlier tests had only exercised the failing paths of this gate and a mock, which is why they did not catch it; this is a test gap I own. Tests added to `check_final_eval.py` (now 68 checks, all pass), each in a child process that calls ONLY the terminal gate: the phrase typed through a pseudo-terminal (Python's `pty`) passes; a wrong phrase and an empty line typed there abort; a terminal exists but stdin is redirected from a file holding the phrase: aborts; no controlling terminal and the phrase fed through a pipe: aborts; and a syntax-tree test that the text-mode `open('/dev/tty', ...)` is gone. `--dry-run` was rerun into a fresh scratch folder after the change (result below). The fix was committed before the real run.
**Dry run after the fix** (`PYTHONHASHSEED=0 .venv/bin/python notebooks/final_eval.py --dry-run --dry-run-dir <fresh scratch folder>`): exit 0; all gates passed; **again 82 numbers compared with the saved validation numbers (tolerance 1e-12), 0 differ**; row-count assertions held. Thresholds, metrics and tables are unchanged by the fix (the gate runs only in `--final` mode, which was not run). The positive path of the git gate had already been shown at the previous commit (`d53d8b5`); the pseudo-terminal tests now exercise the terminal prompt itself. The real run is still to be done by the owner.
- **Commit:** the commit "Chunk 6: fix the terminal gate in final_eval.py (found before any data was read)" (hash in `git log`).
- **Commit:** pending (not committed until the owner says so)

## Chunk 6 results (final run, done once)

- **How it ran:** the first real launch aborted at the terminal gate before any data was read. The fix was committed in 18c273f. The real run happened once, at 2026-10-30 00:44 (metrics.json time 2026-10-30T00:44:42), with commit 18c273f (metrics.json head 18c273f2005e22de042c02b85833650181c2b00e).
- **Sealed safe URLs (from metrics.json sealed_facts):** sealed safe URLs: 125,031; of these without a path: 125,031; host equal to its registered domain (bare domains): 123,743. Sealed phishing URLs: 111,959, without a path: 69,953. Labels below are plain labels of the numbers; no interpretation.
- **Source of every number:** results/final_v2/ (metrics.json and the CSVs). Recall = caught / phishing rows; false-alarm rate = false alarms / safe rows.

**Test split, four systems**

| system | subset | n phishing | n safe | caught (tp) | missed (fn) | false alarms (fp) | safe ok (tn) | phishing unsure | safe unsure | recall | false-alarm rate | precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primary: plain 4a + R1 | all | 16135 | 58930 | 14045 | 2090 | 2051 | 56879 | 0 | 0 | 0.8705 | 0.0348 | 0.8726 |
| plain 4a | all | 16135 | 58930 | 14044 | 2091 | 2051 | 56879 | 0 | 0 | 0.8704 | 0.0348 | 0.8726 |
| 8b (secondary) | all | 16135 | 58930 | 14261 | 1874 | 2051 | 56879 | 0 | 0 | 0.8839 | 0.0348 | 0.8743 |
| second view: primary + unsure | all | 16135 | 58930 | 11150 | 4985 | 387 | 58543 | 3957 | 14283 | 0.6910 | 0.0066 | 0.9665 |

**Test split, bare URLs (no path) versus URLs with a path**

| system | subset | n phishing | n safe | caught (tp) | missed (fn) | false alarms (fp) | safe ok (tn) | phishing unsure | safe unsure | recall | false-alarm rate | precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primary: plain 4a + R1 | bare URLs (no path) | 1933 | 13212 | 1451 | 482 | 287 | 12925 | 0 | 0 | 0.7506 | 0.0217 | 0.8349 |
| primary: plain 4a + R1 | URLs with a path | 14202 | 45718 | 12594 | 1608 | 1764 | 43954 | 0 | 0 | 0.8868 | 0.0386 | 0.8771 |
| plain 4a | bare URLs (no path) | 1933 | 13212 | 1451 | 482 | 287 | 12925 | 0 | 0 | 0.7506 | 0.0217 | 0.8349 |
| plain 4a | URLs with a path | 14202 | 45718 | 12593 | 1609 | 1764 | 43954 | 0 | 0 | 0.8867 | 0.0386 | 0.8771 |
| 8b (secondary) | bare URLs (no path) | 1933 | 13212 | 1446 | 487 | 302 | 12910 | 0 | 0 | 0.7481 | 0.0229 | 0.8272 |
| 8b (secondary) | URLs with a path | 14202 | 45718 | 12815 | 1387 | 1749 | 43969 | 0 | 0 | 0.9023 | 0.0383 | 0.8799 |
| second view: primary + unsure | bare URLs (no path) | 1933 | 13212 | 645 | 1288 | 28 | 13184 | 1182 | 10901 | 0.3337 | 0.0021 | 0.9584 |
| second view: primary + unsure | URLs with a path | 14202 | 45718 | 10505 | 3697 | 359 | 45359 | 2775 | 3382 | 0.7397 | 0.0079 | 0.9670 |

**Test split, attacks (edited copies; recall = phishing flagged / phishing edited; safe flagged share = safe flagged / safe edited)**

| family | system | n phishing edited | n safe edited | phishing flagged | phishing unsure | phishing safe | safe flagged | safe unsure | safe safe | recall | safe flagged share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none (clean) | primary: plain 4a + R1 | 16135 | 15000 | 14045 | 0 | 2090 | 504 | 0 | 14496 | 0.8705 | 0.0336 |
| none (clean) | plain 4a | 16135 | 15000 | 14044 | 0 | 2091 | 504 | 0 | 14496 | 0.8704 | 0.0336 |
| none (clean) | 8b (secondary) | 16135 | 15000 | 14261 | 0 | 1874 | 503 | 0 | 14497 | 0.8839 | 0.0335 |
| none (clean) | second view: primary + unsure | 16135 | 15000 | 11150 | 3957 | 1028 | 77 | 3774 | 11149 | 0.6910 | 0.0051 |
| benign_words_in_path | primary: plain 4a + R1 | 16135 | 15000 | 9714 | 0 | 6421 | 356 | 0 | 14644 | 0.6020 | 0.0237 |
| benign_words_in_path | plain 4a | 16135 | 15000 | 9640 | 0 | 6495 | 354 | 0 | 14646 | 0.5975 | 0.0236 |
| benign_words_in_path | 8b (secondary) | 16135 | 15000 | 8258 | 0 | 7877 | 186 | 0 | 14814 | 0.5118 | 0.0124 |
| benign_words_in_path | second view: primary + unsure | 16135 | 15000 | 7467 | 3498 | 5170 | 68 | 642 | 14290 | 0.4628 | 0.0045 |
| benign_words_in_query | primary: plain 4a + R1 | 16135 | 15000 | 9116 | 0 | 7019 | 146 | 0 | 14854 | 0.5650 | 0.0097 |
| benign_words_in_query | plain 4a | 16135 | 15000 | 9061 | 0 | 7074 | 145 | 0 | 14855 | 0.5616 | 0.0097 |
| benign_words_in_query | 8b (secondary) | 16135 | 15000 | 8599 | 0 | 7536 | 77 | 0 | 14923 | 0.5329 | 0.0051 |
| benign_words_in_query | second view: primary + unsure | 16135 | 15000 | 6895 | 3554 | 5686 | 29 | 323 | 14648 | 0.4273 | 0.0019 |
| lookalike_characters | primary: plain 4a + R1 | 16135 | 15000 | 13748 | 0 | 2387 | 487 | 0 | 14513 | 0.8521 | 0.0325 |
| lookalike_characters | plain 4a | 16135 | 15000 | 13747 | 0 | 2388 | 487 | 0 | 14513 | 0.8520 | 0.0325 |
| lookalike_characters | 8b (secondary) | 16135 | 15000 | 13995 | 0 | 2140 | 488 | 0 | 14512 | 0.8674 | 0.0325 |
| lookalike_characters | second view: primary + unsure | 16135 | 15000 | 10550 | 4382 | 1203 | 71 | 3755 | 11174 | 0.6539 | 0.0047 |
| extra_subdomains | primary: plain 4a + R1 | 16135 | 15000 | 14593 | 0 | 1542 | 3012 | 0 | 11988 | 0.9044 | 0.2008 |
| extra_subdomains | plain 4a | 16135 | 15000 | 14592 | 0 | 1543 | 3012 | 0 | 11988 | 0.9044 | 0.2008 |
| extra_subdomains | 8b (secondary) | 16135 | 15000 | 14743 | 0 | 1392 | 2882 | 0 | 12118 | 0.9137 | 0.1921 |
| extra_subdomains | second view: primary + unsure | 16135 | 15000 | 12061 | 3284 | 790 | 974 | 4064 | 9962 | 0.7475 | 0.0649 |
| path_shortening | primary: plain 4a + R1 | 16135 | 15000 | 13353 | 0 | 2782 | 807 | 0 | 14193 | 0.8276 | 0.0538 |
| path_shortening | plain 4a | 16135 | 15000 | 13353 | 0 | 2782 | 807 | 0 | 14193 | 0.8276 | 0.0538 |
| path_shortening | 8b (secondary) | 16135 | 15000 | 13616 | 0 | 2519 | 839 | 0 | 14161 | 0.8439 | 0.0559 |
| path_shortening | second view: primary + unsure | 16135 | 15000 | 10079 | 4612 | 1444 | 160 | 4364 | 10476 | 0.6247 | 0.0107 |
| padding | primary: plain 4a + R1 | 16135 | 15000 | 13349 | 0 | 2786 | 1991 | 0 | 13009 | 0.8273 | 0.1327 |
| padding | plain 4a | 16135 | 15000 | 13349 | 0 | 2786 | 1991 | 0 | 13009 | 0.8273 | 0.1327 |
| padding | 8b (secondary) | 16135 | 15000 | 13154 | 0 | 2981 | 1751 | 0 | 13249 | 0.8152 | 0.1167 |
| padding | second view: primary + unsure | 16135 | 15000 | 10844 | 3609 | 1682 | 482 | 3052 | 11466 | 0.6721 | 0.0321 |
| random_mix | primary: plain 4a + R1 | 16135 | 15000 | 10189 | 0 | 5946 | 1624 | 0 | 13376 | 0.6315 | 0.1083 |
| random_mix | plain 4a | 16135 | 15000 | 10108 | 0 | 6027 | 1622 | 0 | 13378 | 0.6265 | 0.1081 |
| random_mix | 8b (secondary) | 16135 | 15000 | 9032 | 0 | 7103 | 1216 | 0 | 13784 | 0.5598 | 0.0811 |
| random_mix | second view: primary + unsure | 16135 | 15000 | 7687 | 3781 | 4667 | 486 | 2111 | 12403 | 0.4764 | 0.0324 |

**Sealed set, four systems, overall**

| system | subset | n phishing | n safe | caught (tp) | missed (fn) | false alarms (fp) | safe ok (tn) | phishing unsure | safe unsure | recall | false-alarm rate | precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primary: plain 4a + R1 | all | 111959 | 125031 | 100129 | 11830 | 120476 | 4555 | 0 | 0 | 0.8943 | 0.9636 | 0.4539 |
| plain 4a | all | 111959 | 125031 | 100125 | 11834 | 120476 | 4555 | 0 | 0 | 0.8943 | 0.9636 | 0.4539 |
| 8b (secondary) | all | 111959 | 125031 | 101769 | 10190 | 122048 | 2983 | 0 | 0 | 0.9090 | 0.9761 | 0.4547 |
| second view: primary + unsure | all | 111959 | 125031 | 53529 | 58430 | 856 | 124175 | 52448 | 124080 | 0.4781 | 0.0068 | 0.9843 |

**Sealed set, bare URLs (no path) versus URLs with a path**

| system | subset | n phishing | n safe | caught (tp) | missed (fn) | false alarms (fp) | safe ok (tn) | phishing unsure | safe unsure | recall | false-alarm rate | precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primary: plain 4a + R1 | bare URLs (no path) | 69953 | 125031 | 63684 | 6269 | 120476 | 4555 | 0 | 0 | 0.9104 | 0.9636 | 0.3458 |
| primary: plain 4a + R1 | URLs with a path | 42006 | 0 | 36445 | 5561 | 0 | 0 | 0 | 0 | 0.8676 | too few to read | 1.0000 |
| plain 4a | bare URLs (no path) | 69953 | 125031 | 63684 | 6269 | 120476 | 4555 | 0 | 0 | 0.9104 | 0.9636 | 0.3458 |
| plain 4a | URLs with a path | 42006 | 0 | 36441 | 5565 | 0 | 0 | 0 | 0 | 0.8675 | too few to read | 1.0000 |
| 8b (secondary) | bare URLs (no path) | 69953 | 125031 | 64712 | 5241 | 122048 | 2983 | 0 | 0 | 0.9251 | 0.9761 | 0.3465 |
| 8b (secondary) | URLs with a path | 42006 | 0 | 37057 | 4949 | 0 | 0 | 0 | 0 | 0.8822 | too few to read | 1.0000 |
| second view: primary + unsure | bare URLs (no path) | 69953 | 125031 | 23605 | 46348 | 856 | 124175 | 43808 | 124080 | 0.3374 | 0.0068 | 0.9650 |
| second view: primary + unsure | URLs with a path | 42006 | 0 | 29924 | 12082 | 0 | 0 | 8640 | 0 | 0.7124 | too few to read | 1.0000 |

**Sealed set, per source**

| system | subset | n phishing | n safe | caught (tp) | missed (fn) | false alarms (fp) | safe ok (tn) | phishing unsure | safe unsure | recall | false-alarm rate | precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| primary: plain 4a + R1 | source=feed | 38860 | 0 | 35895 | 2965 | 0 | 0 | 0 | 0 | 0.9237 | too few to read | 1.0000 |
| primary: plain 4a + R1 | source=phiusiil | 73099 | 125031 | 64234 | 8865 | 120476 | 4555 | 0 | 0 | 0.8787 | 0.9636 | 0.3478 |
| plain 4a | source=feed | 38860 | 0 | 35891 | 2969 | 0 | 0 | 0 | 0 | 0.9236 | too few to read | 1.0000 |
| plain 4a | source=phiusiil | 73099 | 125031 | 64234 | 8865 | 120476 | 4555 | 0 | 0 | 0.8787 | 0.9636 | 0.3478 |
| 8b (secondary) | source=feed | 38860 | 0 | 36315 | 2545 | 0 | 0 | 0 | 0 | 0.9345 | too few to read | 1.0000 |
| 8b (secondary) | source=phiusiil | 73099 | 125031 | 65454 | 7645 | 122048 | 2983 | 0 | 0 | 0.8954 | 0.9761 | 0.3491 |
| second view: primary + unsure | source=feed | 38860 | 0 | 26758 | 12102 | 0 | 0 | 10202 | 0 | 0.6886 | too few to read | 1.0000 |
| second view: primary + unsure | source=phiusiil | 73099 | 125031 | 26771 | 46328 | 856 | 124175 | 42246 | 124080 | 0.3662 | 0.0068 | 0.9690 |

**Second view (primary + unsure), test split and sealed set**

**Second view, test split**

| system | subset | n phishing | n safe | caught (tp) | missed (fn) | false alarms (fp) | safe ok (tn) | phishing unsure | safe unsure | recall | false-alarm rate | precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| second view: primary + unsure | all | 16135 | 58930 | 11150 | 4985 | 387 | 58543 | 3957 | 14283 | 0.6910 | 0.0066 | 0.9665 |
| second view: primary + unsure | bare URLs (no path) | 1933 | 13212 | 645 | 1288 | 28 | 13184 | 1182 | 10901 | 0.3337 | 0.0021 | 0.9584 |
| second view: primary + unsure | URLs with a path | 14202 | 45718 | 10505 | 3697 | 359 | 45359 | 2775 | 3382 | 0.7397 | 0.0079 | 0.9670 |

**Second view, sealed set**

| system | subset | n phishing | n safe | caught (tp) | missed (fn) | false alarms (fp) | safe ok (tn) | phishing unsure | safe unsure | recall | false-alarm rate | precision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| second view: primary + unsure | all | 111959 | 125031 | 53529 | 58430 | 856 | 124175 | 52448 | 124080 | 0.4781 | 0.0068 | 0.9843 |
| second view: primary + unsure | bare URLs (no path) | 69953 | 125031 | 23605 | 46348 | 856 | 124175 | 43808 | 124080 | 0.3374 | 0.0068 | 0.9650 |
| second view: primary + unsure | URLs with a path | 42006 | 0 | 29924 | 12082 | 0 | 0 | 8640 | 0 | 0.7124 | too few to read | 1.0000 |
| second view: primary + unsure | source=feed | 38860 | 0 | 26758 | 12102 | 0 | 0 | 10202 | 0 | 0.6886 | too few to read | 1.0000 |
| second view: primary + unsure | source=phiusiil | 73099 | 125031 | 26771 | 46328 | 856 | 124175 | 42246 | 124080 | 0.3662 | 0.0068 | 0.9690 |

**Hypotheses H1 to H5 (text as written before the run, EXPERIMENTS.md lines 1033-1037; numbers from metrics.json hypothesis_numbers and the CSVs)**

- **H1: yes.** primary test recall 0.8705 vs validation 0.8617 (difference +0.88 pt; within 3 pt: True); test false-alarm rate 0.0348 vs 0.0365 (difference -0.17 pt; within 1.5 pt: True).
- **H2: yes.** Sealed false-alarm rate 0.9636 (primary) and 0.9636 (plain 4a), 120476 false alarms of 125031 safe rows; precision 0.4539 (primary), 0.4539 (plain 4a); recall 0.8943 (primary), 0.8943 (plain 4a).
- **H3: yes (recall differs by source).** sealed recall by source, primary: plain 4a + R1: source=feed: recall 0.9237004632012352 (phishing rows 38860); source=phiusiil: recall 0.8787261111643114 (phishing rows 73099) Plain 4a: source=feed: recall 0.9235975295934122 (phishing rows 38860); source=phiusiil: recall 0.8787261111643114 (phishing rows 73099) 8b: source=feed: recall 0.9345084920226454 (phishing rows 38860); source=phiusiil: recall 0.8954158059617778 (phishing rows 73099)
- **H4: yes.** sealed safe URLs in the second view: unsure 124080 of 125031 (share 0.9923938863161936), phishing 856, safe 95.
- **H5: no (the first half holds, the second does not hold in every family).** Clean test, 4a vs 8b: recall 0.8704059497985746 vs 0.8838549736597459; false alarms 0.03480400475139997 vs 0.03480400475139997; AUC 0.9761184160604849 vs 0.9785051899879006. Attack recall, 8b vs plain 4a, per family: benign_words_in_path 0.5118 vs 0.5975; benign_words_in_query 0.5329 vs 0.5616; lookalike_characters 0.8674 vs 0.8520; extra_subdomains 0.9137 vs 0.9044; path_shortening 0.8439 vs 0.8276; padding 0.8152 vs 0.8273; random_mix 0.5598 vs 0.6265. 8b lower in 4 of 7 families (benign_words_in_path, benign_words_in_query, padding, random_mix); 8b higher in 3 (lookalike_characters, extra_subdomains, path_shortening). plain 4a: recall under path / query / mix words 0.5975 / 0.5616 / 0.6265, mean 0.5952. 8b (secondary): recall under path / query / mix words 0.5118 / 0.5329 / 0.5598, mean 0.5348.
