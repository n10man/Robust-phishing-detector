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
