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
