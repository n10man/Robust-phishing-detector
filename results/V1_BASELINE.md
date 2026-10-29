# v1 baseline (frozen)

Data: Kaggle "Phishing Site URLs". 549,346 rows -> 500,432 after cleaning (48,908 duplicates, 2 conflicting URLs removed). 78.5% safe / 21.5% phishing. Split: random stratified 70/15/15 (350,302 / 75,065 / 75,065), seed 42. NOT grouped by domain, so v1 may leak across sites. Features: 11 handcrafted -> plus 1,000 character 3-grams (1,011 total).

Model choice on validation (threshold 0.5), with the 11-feature-only recall / F1 in brackets:
- Logistic regression: recall 0.912, precision 0.781, F1 0.841 (0.396 / 0.552)
- Random forest: recall 0.848, precision 0.821, F1 0.834 (0.741 / 0.796)
- Gradient boosting (chosen): recall 0.949, precision 0.877, F1 0.912 (0.645 / 0.744)
Stage 3b changed n-grams, forest depth and class weights together.

Clean test set, gradient boosting, threshold 0.5: precision 0.8803, recall 0.9462, F1 0.9121, AUC 0.9918. TP 15,267, FN 868, FP 2,076, TN 56,854.

Attacks on the test set (recall): benign words in path 0.7236, in query 0.6933, random mix 0.7468, lookalike 0.9383, subdomains 0.9659, shortening 0.9194, padding 0.9317. Hill-climb on 300 validation URLs: 96.3% evaded (not a recall measure).

Defence, test set, matched false-alarm level, round 3: clean recall 0.9462 -> 0.9368; path 0.7236 -> 0.7763; query 0.6933 -> 0.8209; mix 0.7468 -> 0.7945; held-out A 0.7291 -> 0.7939; held-out B (fragment) 0.7323 -> 0.7282. Round 2 looked like 0.999 recall but flagged 76.6% of edited SAFE URLs (it learned the edit, not robustness).

Tranco bare-domain test (flagged as phishing, lower is better): bare 99.9% (top 10k), 100% (random); trailing slash 30.6% / 40.4%; with /index.html 45.2% / 55.4%.

Disclosure: the test set was used for rounds 1 and 2 and for designing round 2. Round 3 was developed on validation and run on test once.
