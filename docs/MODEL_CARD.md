# Model card: phishing URL detector

This card describes what the model is, what it was tested on, and what is not known. It is written for a beginner. Every number or claim has a source tag in square brackets. A claim with no source is left empty and marked, and is listed at the end.

Tags:
- `[EXPERIMENTS.md: ...]` is `results/EXPERIMENTS.md`.
- `[final_v2/...]` is a file in `results/final_v2/` (the final run, done once).
- `[final_stage_table.csv]` is `results/final_stage_table.csv`.
- `[final_system_config.json]` is `results/final_system_config.json`.
- `[CLAUDE.md]` is the project instructions file.

---

## 1. What the model is

**Primary: model 4a plus rule R1.**
- A gradient boosting classifier (`HistGradientBoostingClassifier`, 300 iterations, balanced class weights, random seed 42). [EXPERIMENTS.md: Exp 1]
- Features: 11 numeric counts of the URL text (scaled), 1,000 character 3-grams of the whole URL, and 500 character 3-grams of the host only. [EXPERIMENTS.md: Exp 1; Exp 4] That is 1,511 columns in total (my sum: 11 + 1,000 + 500).
- Rule R1: if the host is a raw IPv4 address, the verdict is "phishing". [final_system_config.json: layers.rules.definitions.R1]
- Alert level: score 0.7403. It was set on validation data so that 3.65% of safe validation URLs are flagged (2,151 of 58,930). [final_system_config.json: systems.final_system_4a_plus_rules; EXPERIMENTS.md: Exp 11]

**Secondary: model 8b.** It has the 4a features plus 2,000 character 4-grams of the whole URL (3,511 columns in total). Alert level 0.7274. It is scored only and is not the primary system. [EXPERIMENTS.md: Exp 8; final_system_config.json: systems.plain_8b]

**Training data.** The raw Kaggle file has 549,346 rows. Cleaning removed 48,914 rows: 48,908 duplicates, and 6 rows that belong to 2 distinct URLs with conflicting labels (the same URL labelled both safe and phishing). That leaves 500,432 URLs (549,346 - 48,914). [Read-only recount of data/phishing_site_urls.csv with the steps of notebooks/stage1_clean.py, 2026-10-30, counts only, nothing saved; V1_BASELINE.md line 3 gives 48,908 duplicates and 2 conflicting URLs] These come from 158,760 registered domains, and 21.49% are phishing. [EXPERIMENTS.md: Exp 1]

**Split by website.** All URLs of one registered domain go to the same split. The split is 70/15/15 with seed 42:

| Split | URLs | Websites |
|---|---|---|
| train | 350,302 | 56,866 |
| validation | 75,065 | 50,947 |
| test | 75,065 | 50,947 |

Websites shared between any two splits: 0. [EXPERIMENTS.md: Exp 1]

**Version.** This is the "v2" pipeline. The older "v1" split was random per URL and so the same website could sit in training and validation. [EXPERIMENTS.md: Exp 0; Exp 1]

---

## 2. Intended use

- Education and a portfolio project: learning how a URL classifier is built, attacked and defended. [CLAUDE.md: What this is]
- It reads the URL text only. It never visits a page. [EXPERIMENTS.md: Exp 1 (all features come from the URL string)]
- The rule "never fetch or open any URL" applied to all experiments. [EXPERIMENTS.md: Chunk 4 rules; Chunk 5 rules]

## 3. Not intended use

- Do not use it as a security product or as the only check before a user clicks a link. The recall on the final test split is 0.8705, so about 13 in 100 phishing URLs are missed even with no attack. [final_v2/test_systems.csv]
- Do not use it on bare domains (a name with no path). It flags almost all of them. [final_v2/sealed_systems.csv: false-alarm rate 0.9636]
- Do not use it where an attacker knows the model. [EXPERIMENTS.md: Chunk 5 final combined table and summary; see `docs/THREAT_MODEL.md`]
- Do not assume it works on current phishing. The data is old. [CLAUDE.md: Known limitations] The period the data covers is not known (see section 4).

---

## 4. Data sources and licences

| Source | Used for | Licence |
|---|---|---|
| Kaggle "Phishing Site URLs" | training, validation and test split | Database Contents License (DbCL) v1.0, as shown on the Kaggle dataset page; it requires compliance with the ODbL. |
| PhiUSIIL Phishing URL Dataset | sealed evaluation set (safe URLs and some phishing URLs) | CC BY 4.0 (stated on its UCI dataset page; owner to re-check) |
| Phishing.Database (the "feed" source in the sealed set) | sealed evaluation set (phishing URLs) | MIT (stated on its GitHub page; owner to re-check) |

[Kaggle: CLAUDE.md, What this is; EXPERIMENTS.md: Exp 1. PhiUSIIL and feed: EXPERIMENTS.md: Sealed evaluation set; final_v2/sealed_by_source.csv, source labels "phiusiil" and "feed".]

Two more lists were used in experiments only and are not in the final models: a ranked list of popular domains (Tranco) and a phishing-domains list. Both fed the bare-domain tests in Exp 3. [EXPERIMENTS.md: Exp 3]
- The phishing-domains list is phishing-domains-ACTIVE from the Phishing.Database project, with the same licence as that project: MIT (stated on its GitHub page; owner to re-check).
- Tranco list: not a single licence. The list combines rankings from several providers, each under its own terms (see tranco-list.eu). Used for non-commercial research and not redistributed.

**What I cannot verify about the Kaggle data:** where the links originally came from, and what period they cover. I do not know either.

---

## 5. Evaluation

Three kinds of data:
- **Validation:** used to choose models, thresholds and rule R1. Not independent evidence. [EXPERIMENTS.md: Chunk 3 decision; Exp 11, Limits]
- **Final test split:** 75,065 URLs, same Kaggle source, grouped by website. Run once. [final_v2/metrics.json: time 2026-10-30T00:44:42, head 18c273f…]
- **Sealed set:** 236,990 URLs from other sources, built before any experiment and not opened until the final run. [EXPERIMENTS.md: Sealed evaluation set]

All numbers are at the frozen alert level. 95% intervals are Wilson intervals from the final run. [EXPERIMENTS.md: Chunk 6 prepared, "Metrics"]

### 5.1 Main table

| Data | System | Recall | False-alarm rate | Precision | F1 | AUC |
|---|---|---|---|---|---|---|
| Validation (16,135 phishing, 58,930 safe) | primary: 4a + R1 | 0.8615 | 0.0365 | 0.8660 | 0.8638 | 0.9745 |
| Validation | plain 8b | 0.8752 | 0.0365 | 0.8678 | 0.8715 | 0.9773 |
| Test split (16,135 phishing, 58,930 safe) | primary: 4a + R1 | 0.8705 [0.8652, 0.8756] | 0.0348 [0.0334, 0.0363] | 0.8726 [0.8673, 0.8776] | 0.8715 | 0.9761 |
| Test split | plain 4a | 0.8704 [0.8651, 0.8755] | 0.0348 [0.0334, 0.0363] | 0.8726 [0.8673, 0.8776] | 0.8715 | 0.9761 |
| Test split | 8b (secondary) | 0.8839 [0.8788, 0.8887] | 0.0348 [0.0334, 0.0363] | 0.8743 [0.8691, 0.8793] | 0.8790 | 0.9785 |
| Test split | second view: primary + "unsure" | 0.6910 [0.6839, 0.6981] | 0.0066 [0.0059, 0.0073] | 0.9665 [0.9630, 0.9696] | 0.8059 | n/a |
| Sealed set (111,959 phishing, 125,031 safe) | primary: 4a + R1 | 0.8943 [0.8925, 0.8961] | 0.9636 [0.9625, 0.9646] | 0.4539 [0.4518, 0.4560] | 0.6022 | 0.6338 |
| Sealed set | plain 4a | 0.8943 [0.8925, 0.8961] | 0.9636 [0.9625, 0.9646] | 0.4539 [0.4518, 0.4560] | 0.6021 | 0.6338 |
| Sealed set | 8b (secondary) | 0.9090 [0.9073, 0.9107] | 0.9761 [0.9753, 0.9770] | 0.4547 [0.4526, 0.4568] | 0.6062 | 0.6445 |
| Sealed set | second view: primary + "unsure" | 0.4781 [0.4752, 0.4810] | 0.0068 [0.0064, 0.0073] | 0.9843 [0.9832, 0.9853] | 0.6436 | n/a |

Sources: validation rows [final_stage_table.csv: stage "4 final system", rows "FINAL SYSTEM: 4a + rule R1" and "8b plain"]. The AUC cell of the "FINAL SYSTEM" row is empty in that file. The 4a AUC (0.9745) is taken from the "4a plain" row of the same stage; the AUC is the AUC of the model score, which rules do not change [EXPERIMENTS.md: Chunk 6 prepared, point 2]. Test and sealed rows [final_v2/test_systems.csv; final_v2/sealed_systems.csv]. Intervals for the validation rows: not computed.

In the second view, "unsure" is not counted as a catch. On the test split the system decides 75.7% of URLs, and on the sealed set 25.5%. [final_v2/test_systems.csv and sealed_systems.csv: coverage]

### 5.2 Bare URLs against URLs with a path (primary system)

| Data | Group | Rows | Recall | False-alarm rate |
|---|---|---|---|---|
| Test split | bare URLs (no path) | 15,145 | 0.7506 [0.7309, 0.7694] | 0.0217 [0.0194, 0.0244] |
| Test split | URLs with a path | 59,920 | 0.8868 [0.8815, 0.8919] | 0.0386 [0.0369, 0.0404] |
| Sealed set | bare URLs (no path) | 194,984 | 0.9104 [0.9082, 0.9125] | 0.9636 [0.9625, 0.9646] |
| Sealed set | URLs with a path | 42,006 (all phishing) | 0.8676 [0.8643, 0.8708] | too few to read (no safe rows) |

[final_v2/test_bare_vs_path.csv; final_v2/sealed_bare_vs_path.csv]

### 5.3 Sealed set by source (primary system)

| Source | Phishing rows | Safe rows | Recall | False-alarm rate |
|---|---|---|---|---|
| feed | 38,860 | 0 | 0.9237 [0.9210, 0.9263] | too few to read (no safe rows) |
| phiusiil | 73,099 | 125,031 | 0.8787 [0.8763, 0.8811] | 0.9636 [0.9625, 0.9646] |

[final_v2/sealed_by_source.csv]

### 5.4 The sealed safe set

- Every sealed safe URL has no path. [final_v2/metrics.json: sealed_facts, "without a path: 125,031"]
- 123,743 of the 125,031 sealed safe URLs are strict bare domains (the host equals its registered domain). The other 1,288 have a subdomain. [final_v2/metrics.json: sealed_facts; 1,288 is 125,031 minus 123,743]
- So the sealed set cannot test safe URLs that have a path. [EXPERIMENTS.md: Sealed evaluation set, Warning]
- The sealed false-alarm rate of 0.9636 measures the known bare-domain flaw. This hypothesis (H2) was written before the run. [EXPERIMENTS.md: Chunk 6 prepared, H2; final run entry]

### 5.5 Attacks on the test split

See `docs/THREAT_MODEL.md` section 2 for recall under the seven edit families. [final_v2/test_attacks.csv]

---

## 6. Known limitations

1. **Bare domains.** On the validation set, the first v1 model flagged 0.9992 of a popular-domain sample as phishing. [EXPERIMENTS.md: Exp 0] The v2 primary system flagged 0.9636 of the sealed safe URLs, and 0.9686 (top 10k) and 0.9816 (random) of the popular-domain samples at its alert level (that is the 4a model alone). [final_v2/sealed_systems.csv; EXPERIMENTS.md: Exp 4, "Tranco bare flagged"] A fix in training (Exp 3) was reverted by the rules written before the results: it cut safe bare flags but also cut bare-phishing catch by about 25 points. [EXPERIMENTS.md: Exp 3]
2. **Harmless-word edits.** On the test split, harmless words in the path or the query cut recall from 0.8705 to 0.6020 and 0.5650. [final_v2/test_attacks.csv]
3. **Poisoning.** A backdoor made from 500 added rows (0.14% of training data) makes the model miss 99.63% of the phishing it normally catches when a trigger is added. Normal scores do not show it. [EXPERIMENTS.md: Exp 9c]
4. **Same-source test.** The test split comes from the same Kaggle file as training, grouped by website. It is not a different source. [EXPERIMENTS.md: Exp 1] The sealed set is a different source, but its safe URLs are bare. [EXPERIMENTS.md: Sealed evaluation set]
5. **Optimistic validation numbers.** The model choice, the alert level and rule R1 were all chosen on the same validation data they are reported on. [EXPERIMENTS.md: Exp 11, Limits; Chunk 5 summary] On the test split, recall was higher than on validation (0.8705 against 0.8617 as written in H1). [EXPERIMENTS.md: final run entry, H1]
6. **v1 numbers are higher but are not comparable.** v1 recall was 0.9493 on a random split. With the split by website, the same recipe gave 0.8567 at the same false-alarm level. [EXPERIMENTS.md: Exp 1, table]
7. **Our own attacks.** All edit families are ours. Edited URLs were not checked to still load. [EXPERIMENTS.md: Exp 10, Limits; CLAUDE.md: Known limitations]
8. **Old data.** [CLAUDE.md: Known limitations]
9. **Single runs.** Most experiments used one seed and one training; the log says the noise on recall is about 0.3 points. [EXPERIMENTS.md: Exp 4, Exp 14, Limits]

---

## 7. Privacy

- Before features are computed, `redact_url` replaces email-like text after the host with the word `redactedemail`. The host part is untouched. Percent-encoded emails are not caught. [EXPERIMENTS.md: Exp 2]
- Rows changed in the training file: 1,363 of 350,302 (0.39%). In the validation file: 79 of 75,065 (0.11%). After redaction, 0 email-like strings remain after the host in either file. [EXPERIMENTS.md: Exp 2]
- 18 rows (14 train, 4 validation) have an `@` in the host part and were left alone. [EXPERIMENTS.md: Exp 2]
- The 54 tracked text files contained no email-like text when checked. [EXPERIMENTS.md: Exp 2]
- Test and sealed URLs were also redacted first, in the final script. [EXPERIMENTS.md: Chunk 6 prepared, point 6] Number of test rows and sealed rows changed by redaction: not recorded.
- The final results contain counts and rates only, not URLs. [EXPERIMENTS.md: Chunk 6 prepared, "Safety gates"]
- The data and the model files are not committed. [CLAUDE.md: Rules]

---

## 8. Decisions made after seeing results

These are listed so a reader can judge them. None of them was a rule written beforehand.

The hypotheses H1 to H5, the experiment rules and most of the code were drafted by an AI assistant (Claude). The owner reviewed and approved them, ran the final test, and made the choices of the 3.65% level and of model 4a. [EXPERIMENTS.md: Exp 1, Decision; Chunk 3 decision; Chunk 6 prepared, "The command for the owner"]

1. **4a was chosen over 8b by the owner, after validation results were seen.**
   - By the locked rules, both 4a and 8b were KEPT. [EXPERIMENTS.md: Chunk 3 decision]
   - 8b had higher clean recall (0.8752 against 0.8617). [EXPERIMENTS.md: Chunk 3 decision]
   - 8b had lower recall under harmless-word attacks: path words -9.20 points, query words -2.70, random mix -6.84, mean -6.25. [EXPERIMENTS.md: Chunk 3 decision]
   - Other reasons: some top 8b 4-grams looked like quirks of old data (not tested), and 8b needed 26.9 GB peak memory on a 24 GB machine. [EXPERIMENTS.md: Chunk 3 decision, reasons b and c]
   - 8b was kept as a secondary model and scored in the same final run. [EXPERIMENTS.md: Chunk 3 decision]
2. **The Chunk 3 rule gap.** The rules had no guard against a fall in attack recall. This was noticed after seeing results. The rules were not changed. The choice above is a separate, disclosed judgement. [EXPERIMENTS.md: Chunk 3 decision]
3. **The v1 test set was reused.** The v1 test set was used in stages 4, 6, 7, 7b and 7c. The project rule is that new experiments need a new test set; v2 has a new split by website and a separate sealed set. [CLAUDE.md: Rules; EXPERIMENTS.md: Exp 1; Sealed evaluation set]
4. **The first final launch aborted at the terminal gate before any data was read.** No metric existed, and no lock file or results folder was created. The fix was committed in 18c273f. The real run happened once, at 2026-10-30 00:44, with that commit. [EXPERIMENTS.md: Chunk 6 prepared, "Terminal-gate bug"; final_v2/metrics.json: time, head]
5. **The H5 label was changed after the results commit.** It was first "no" and was changed to "partly", with no number changed. The numbers behind "partly": 8b is lower than 4a under 4 of 7 attack families and higher under 3. [EXPERIMENTS.md: Chunk 6 results, H5 line and the note under it]

Other things fixed before results, for contrast: the Exp 3 rule (c) tolerance was set before any result [EXPERIMENTS.md: Chunk 2 decision rules]; the final system (4a, plus R1 only, no guard, "unsure" as a second view) was fixed before the final run [EXPERIMENTS.md: Chunk 5 rules, addition 2; final_system_config.json].

---

## 9. Written with AI help

The hypotheses H1 to H5, the experiment rules, most of the code and both documents (this model card and `docs/THREAT_MODEL.md`) were drafted by an AI assistant (Claude, an AI model from Anthropic, used through Claude Code). The owner reviewed and approved them, ran the final test, and made the choices of the 3.65% level and of model 4a. [EXPERIMENTS.md: Exp 1, Decision; Chunk 3 decision; Chunk 6 prepared, "The command for the owner"]

---

## Claims I could not source

- Where the Kaggle "Phishing Site URLs" links originally came from.
- The PhiUSIIL (CC BY 4.0) and Phishing.Database (MIT) licences, and that the list is phishing-domains-ACTIVE. They are given as stated on the projects' own pages and have not been checked against those pages. The owner is to re-check them.
- That the sealed-set source label "feed" is Phishing.Database. The label is in the final CSVs; the name comes from the header comment of the build script, which is a code file and not one of the log or result files used for the numbers.
- The Tranco terms, given as supplied and not checked against the Tranco website.
- The number of test and sealed rows changed by email redaction.
- Confidence intervals for the validation rows.
- The AUC of the combined primary system on validation. The stage table leaves it empty. The value shown is the AUC of the 4a score (same model).
- Use of the word "educational": taken from `CLAUDE.md` ("Master's application portfolio project"), which does not use that word.
