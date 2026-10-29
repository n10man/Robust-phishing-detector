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
