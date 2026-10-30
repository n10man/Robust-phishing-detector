# Threat model

This file says who might attack the phishing URL detector, what they can do, and what was measured. It is written for a beginner. Every number has a source tag in square brackets. Where no source was found, the place is left empty and marked, and the claim is listed at the end.

How to read the tags:
- `[EXPERIMENTS.md: Exp N]` is the experiment log `results/EXPERIMENTS.md`.
- `[final_v2/...]` is a file in `results/final_v2/` (the final run, done once).
- `[final_system_config.json]` is `results/final_system_config.json`.
- `[final_stage_table.csv]` is `results/final_stage_table.csv`.

Words used:
- **Primary system**: model 4a plus the one rule R1 (a raw IP address as host is phishing). [final_system_config.json: systems.final_system_4a_plus_rules]
- **Alert level**: the score above which a URL is called phishing. It is set so that 3.65% of safe validation URLs are flagged. The score is 0.7403 for 4a. [final_system_config.json: threshold]
- **Silent miss**: a phishing URL the system calls safe.
- **Pool**: the group of phishing URLs an attack was run on.
- All attacks here were designed by us. Edited URLs were not checked to still load. [EXPERIMENTS.md: Exp 10, Limits]

---

## 1. What is protected, and what the attacker wants

**Protected:** the verdict "phishing" for a URL that really is phishing. The detector reads URL text only. It never opens the page. [EXPERIMENTS.md: Exp 1 (features are computed from the URL string)]

**The attacker wants:** a phishing URL that gets a score below the alert level, so the detector says "safe". [EXPERIMENTS.md: Exp 10, threat model: "an edited phishing URL that our detector scores below its alert threshold"]

**The attacker also has a second goal in the data-poisoning case:** a detector that misses more phishing while its normal scores look fine. [EXPERIMENTS.md: Exp 9b, threat model]

**Starting point (no attack).** On the final test split the primary system catches 0.8705 of phishing and flags 0.0348 of safe URLs. [final_v2/test_systems.csv: primary row; recall 0.8705, false-alarm rate 0.0348]

---

## 2. Four attacker types

### A. Edits their own URL, without knowing the model

- **Can change:** the text of their own phishing URL, with six kinds of edit: harmless words in the path, harmless words in the query, look-alike characters, extra subdomains, path shortening, padding. A seventh test mixes edits at random. [EXPERIMENTS.md: Exp 0, attack list; final_v2/test_attacks.csv: family names]
- **Can see:** the URL they write.
- **Cannot:** see the model, its scores or its threshold. They cannot change the website that hosts the page (the registered domain). [EXPERIMENTS.md: Exp 12, threat model; Exp 10, threat model]

**Evidence (final test split, primary system, share of edited phishing URLs still caught):**

| Edit | Recall | Safe URLs flagged after the same edit |
|---|---|---|
| none (clean) | 0.8705 | 0.0336 |
| harmless words in path | 0.6020 | 0.0237 |
| harmless words in query | 0.5650 | 0.0097 |
| random mix | 0.6315 | 0.1083 |
| look-alike characters | 0.8521 | 0.0325 |
| extra subdomains | 0.9044 | 0.2008 |
| path shortening | 0.8276 | 0.0538 |
| padding | 0.8273 | 0.1327 |

[final_v2/test_attacks.csv: primary rows; columns recall and safe_flagged_share]

In plain words: adding harmless words to the path or the query drops recall by about 25 to 30 points. The subdomain edit looks harmless for recall, but it also makes 20% of safe URLs look like phishing. [final_v2/test_attacks.csv]

### B. Builds a surrogate model (a stand-in copy trained by the attacker)

- **Can change:** the URL text, guided by their own stand-in model.
- **Can see:** their own training data and their own model. In the test this was a random half of our training data.
- **Cannot:** see our model, scores or threshold. [EXPERIMENTS.md: Exp 10, threat model]

**Evidence (500 phishing URLs per pool, both the target and the surrogate catch them before editing):**

| Surrogate | Edited URL fools the surrogate | Of those, also fool 4a | Random edits of the same size fool 4a |
|---|---|---|---|
| s1, logistic regression | 495 of 500 = 99.0% | 245 of 495 = 49.5% [45.1, 53.9] | 55 of 495 = 11.1% |
| s2, small gradient boosting | 451 of 500 = 90.2% | 302 of 451 = 67.0% [62.5, 71.1] | 53 of 451 = 11.8% |

[EXPERIMENTS.md: Exp 10, main table]

With the "margin" variant (push the surrogate further), transfer to 4a was 60.4% for s1 and 94.4% for s2. [EXPERIMENTS.md: Exp 10, margin rows]

The secondary model 8b was easier to fool: 66.5% (s1) and 74.9% (s2). [EXPERIMENTS.md: Exp 10, table]

In plain words: an attacker who never sees our model can still fool it about half to two thirds of the time. Random edits do this only about 11 to 12% of the time. [EXPERIMENTS.md: Exp 10]

Caveat: the surrogates used the same data source and labels as the target. This is a friendly test. [EXPERIMENTS.md: Exp 10, Limits]

### C. Knows the model and the defences (white-box and guard-aware)

- **Can change:** the URL text, and can score each edit against the real model, or against the model plus the defence.
- **Can see:** the model and the defence.
- **Cannot:** change the registered domain. [EXPERIMENTS.md: Exp 12, threat model]

**Evidence (500 phishing URLs per pool, 15 rounds, 20 candidate edits per round):**

| Target | Evaded | Mean edits |
|---|---|---|
| plain 4a (white-box) | 489 of 500 = 97.8% | 2.32 |
| 4a with the g2 guard, attacker knows the guard | 488 of 500 = 97.6% | 2.55 |
| 4a with the g2 guard, attacker does not know it | 192 of 500 = 38.4% | not recorded |
| final system (4a + R1) | 460 of 500 = 92.0% | not recorded |
| 8b, plain | 495 of 500 = 99.0% | not recorded |
| 8b + R1 | 475 of 500 = 95.0% | not recorded |

[EXPERIMENTS.md: Exp 12 adaptive table; Chunk 5 final combined table]

The final system's lower number (92.0%) is only because 29 of the 489 evaders had an IP address as host, and rule R1 keeps flagging those. [EXPERIMENTS.md: Chunk 5 final combined table, "Kept" paragraph]

Exp 10 gave the same kind of result on its own two pools: 97.8% (489 of 500) evaded 4a in both, and 91.0% and 91.4% of those edited URLs also evaded 8b. [EXPERIMENTS.md: Exp 10, white-box rows]

### D. Can change the training data (poisoning)

- **Can change:** training labels (9a, 9b) or add new training rows (9c).
- **Cannot:** change the model file, the validation data or the code. [EXPERIMENTS.md: Exp 9a, 9b, 9c, threat models]

**Evidence (validation data, fixed 3.65% false-alarm level; clean 4a recall 86.17):**

| Poisoning | What changed | Result |
|---|---|---|
| 9a: random labels flipped, 1% / 5% / 10% of all rows | clean recall | 84.72 / 82.13 / 80.24 (drops of 1.45 / 4.04 / 5.93 points) |
| 9b: phishing relabelled safe, 1% / 5% / 10% of phishing rows | clean recall | 85.88 / 85.07 / 84.38 (drops of 0.29 / 1.11 / 1.80 points) |
| 9b, same runs | recall under path-word edits, p = 10% | 48.88, against 59.07 clean (a drop of 10.19 points) |
| 9c: backdoor, 500 added rows (0.14% of the training data) | clean recall | 86.15 (a change of -0.02 points, not meaningful) |
| 9c, same runs | phishing that the clean model catches, but the backdoored model misses when the trigger is added | 99.63% (trigger) against 11.90% to 12.28% (control string) |
| 9c, 2,000 added rows | same measure | 100.00% (trigger) against 13.23% to 14.44% (control) |

[EXPERIMENTS.md: Exp 9a table; Exp 9b table; Exp 9c tables 1 and 2]

In plain words: random noise hurts clean recall. Targeted relabelling barely moves clean scores but hurts the edited-URL scores. The backdoor leaves normal scores unchanged and switches the detector off for any URL that carries the trigger. [EXPERIMENTS.md: Exp 9b and Exp 9c, "What it means"]

The 9c trigger was built from text pieces the model already knows. That was our choice, not a rare piece. [EXPERIMENTS.md: Chunk 4 rules, point 7]

---

## 3. Defences tried (Exp 11 to 14)

"Kept" follows the rules written before the results. Exp 13 and Exp 14 were report-only, so no rule decided them.

| Defence | Cost | What it gave | Kept? |
|---|---|---|---|
| **Exp 11, rule R1** (raw IP address as host is phishing) | none measured on clean data; 7 safe URLs hit it, all already flagged | +0.43 / +0.26 / +0.51 points under path / query / mix edits for 4a | **Kept** [EXPERIMENTS.md: Exp 11, Table 3 and Decision] |
| Exp 11, rules R2 to R5 | n/a | R2 had 29 hits, R4 had 4, R5 had 2: untestable on this data. R3 had precision 22.9%: not validated. | Not kept [EXPERIMENTS.md: Exp 11, Table 1] |
| Exp 11, rule R6 (brand name in subdomain) | 120 safe hits; it also fires on our own subdomain-attack words | precision 81.9%, below the 90% rule | Not kept [EXPERIMENTS.md: Exp 11, Tables 1 and 2] |
| **Exp 12, guard g1** (also score the URL without its query) | clean recall -3.26 points; edited safe URLs flagged +2.63 points (query) | +8.49 points mean recall under path / query / mix | **Reverted** (criteria b and c failed) [EXPERIMENTS.md: Exp 12, decision table] |
| **Exp 12, guard g2** (also drop the last path segment) | clean recall -5.97 points; AUC -0.0124; lower recall under the other four families | +10.57 points mean recall under path / query / mix | **Reverted** (criteria b, c and d failed) [EXPERIMENTS.md: Exp 12, decision table] |
| Exp 13, "unsure" answer (second view) | 24.6% of clean validation URLs become "unsure"; "phishing" verdicts fall from 86.2% to 68.0% of phishing | false alarms among decided URLs 0.93% instead of 3.65%; 19% to 23% of silent misses under the word edits become "unsure" | Report-only. Not in the primary system. [EXPERIMENTS.md: Exp 13, Tables 1 and 2; final_system_config.json: abstain.on = false] |
| Exp 14, nearest-neighbour check on training data | 2.2% of honest rows flagged; cleaning cost 0.6 to 1.0 points of clean recall (85.53 and 85.24 against 86.14 and 86.22) | flags 51% to 64% of backdoor rows, 85% to 93% of random flips | Report-only. [EXPERIMENTS.md: Exp 14, Tables 1 and 2] |

After cleaning, the trigger still worked: 84.13% (K = 500) and 98.37% (K = 2,000) of the usually caught phishing URLs were missed. [EXPERIMENTS.md: Exp 14, Table 2]

What the guard did and did not do against the backdoor: a trigger at the end of the path dropped from about 99.6% to about 20%. A trigger as the first path segment still worked in 99.77% to 100.00% of cases. [EXPERIMENTS.md: Exp 12, backdoor table]

The final system is plain 4a plus R1 only. [final_system_config.json: layers.guard.on = false, layers.rules.enabled = ["R1"]]

---

## 4. What stays unprotected

Stated plainly:

1. **An attacker who knows the model still gets through.** The adaptive attack evades 92.0% to 99.0% of its pool, depending on the system, with about 2 to 3 harmless edits per URL. [EXPERIMENTS.md: Chunk 5 final combined table and summary]
2. **A backdoor of 0.14% of the training data works, and normal scores do not show it.** Clean recall, AUC and false alarms stayed within noise. [EXPERIMENTS.md: Exp 9c, "What it means"]
3. **The poison check does not remove it.** After cleaning, the trigger still made the model miss 84% and 98%. [EXPERIMENTS.md: Exp 14, Table 2]
4. **Harmless words in the path or query still cut recall to about 0.57 to 0.63 on the final test split.** [final_v2/test_attacks.csv]
5. **The guard that targeted this was a speed bump.** An attacker who knows it evades 97.6% of the pool. It was not kept. [EXPERIMENTS.md: Exp 12, "Adaptive attack"]
6. **The "unsure" window can be aimed at.** An attacker who aims for the lower edge of the window still gets "safe" for 90.1% (4a) and 94.0% (8b) of the pool. [EXPERIMENTS.md: Chunk 5 final combined table, second-view rows]
7. **Rule R1 stops only attackers who use an IP address.** One who registers a normal domain is not stopped. [EXPERIMENTS.md: Exp 11, Limits]
8. **Bare domains are still a weak point.** On the sealed set, every safe URL has no path, and the primary system flagged 0.9636 of them. [final_v2/sealed_systems.csv: false_alarm 0.9636, fp 120,476 of 125,031 safe]
9. **The extra-subdomain edit raises false alarms** to 0.2008 of safe URLs on the test split. [final_v2/test_attacks.csv]

---

## 5. Out of scope / not tested

- Whether edited URLs still load or still work as phishing pages. [EXPERIMENTS.md: Exp 10, Limits]
- The page content. The detector never opens a page.
- Real deployment (live traffic, speed, updates). No experiment in the log covers it.
- Attacks designed by anyone but us. All edit families are ours. [EXPERIMENTS.md: Exp 10, Limits]
- Model extraction (stealing the model by asking it many questions). Not tried.
- Backdoor triggers made of rare text pieces. The log reasons that they would not work at this size, but this was not tested. [EXPERIMENTS.md: Exp 9c, Limits]
- A poison check against an attacker who adds rows with no near neighbours. Not tested. [EXPERIMENTS.md: Exp 14, "The check is easy to defeat"]
- Poisoning of model 8b. No poisoned 8b was trained. [EXPERIMENTS.md: Chunk 5 final table, 8b section]
- Attacks of any kind on the sealed set. None were run there. [EXPERIMENTS.md: Chunk 6 prepared, point 6]

---

## 6. What a user should do instead

*This section is my interpretation of the measured results. It is not a measured result itself.*

- **Do not treat "safe" as proof.** About 13 in 100 phishing URLs are missed even without edits (recall 0.8705), and edited ones are missed far more often. [final_v2/test_systems.csv: recall 0.8705; final_v2/test_attacks.csv]
- **Do not rely on this detector for bare domains.** It flags almost all of them. [final_v2/sealed_systems.csv]
- **Keep a human or a second check for "unsure" or high-stakes cases.** The "unsure" view makes silent misses visible only part of the time (19% to 23% under the word edits). [EXPERIMENTS.md: Exp 13, Table 2]
- **Protect the training data.** The backdoor was invisible in normal scores and survived my cleaning. Keep track of where each training row came from. [EXPERIMENTS.md: Exp 9c; Exp 14]
- **Add a small fixed set of probe URLs to every validation run** so a backdoor could show up. This is an idea listed in the log and not tested. A probe can only reveal a backdoor whose trigger is already known, so it would not find an unknown one. [EXPERIMENTS.md: Exp 10, "Ideas for Chunk 5", item 6]
- **Use this project as a study, not as a security product.** The data is old and the attacks are ours. [CLAUDE.md: Known limitations]

---

## Claims I could not source

- Which kinds of attacker exist in the real world, and how common each is. The four types are my grouping of the experiments. They are not measured from real attacks.
- That the registered domain "cannot" be changed by a real attacker. This is an assumption written into the Exp 10 and Exp 12 threat models. [EXPERIMENTS.md: Exp 10, Exp 12]
- Section 6 advice on "human or second check": the log says "unsure" needs something else to settle it. It does not measure the cost of that. [EXPERIMENTS.md: Exp 13, Limits]
