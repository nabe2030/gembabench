# Results of GembaBench v0.1

54 trials: Qwen3.8-Flash-Next on 3 configurations × 6 tasks × 3 repetitions, OpenCode 2.0.25, thinking medium with an 8,192-token cap, output limit 16,384, judge j14. Made with `runner/summarize_results.py`.
Trials that were repeated because of a harness or infrastructure fault (not a model fault) are not included; the repeated run is. Logs of the conversations with the model (events, tool logs, OpenCode databases) are not included in v0.1.

`trials.csv` columns:

| Column | Meaning |
|---|---|
| config | DGX Spark (Qwen3.8-Flash-Next fp4 on SGLang) / RTX 4060 Ti 16GB + Strata (IQ3_S, MTP 4) / RTX 3060 12GB x2 + Strata (IQ3_S, MTP 4) |
| task, rep | task T1–T6 and repetition 1–3 |
| score, max_score | T1: F1 weighted findings (45); T2: F3 (8); T3: C (8); T4–T6: live checks on the servers after the trial (31 / 45 / 23) |
| t3b_points | T3 only: the revision stage T3b (6) |
| duration_min | wall time of the trial (T3: the first stage; T3b runs after it in the same session) |
| duration_excl_wait_min | the same without deliberate waits: shell calls containing `sleep` that ran 30 s or longer |
| output_tokens | output tokens of the model in the trial (sum over the steps, from OpenCode's database) |
| ending | normal / time-cap (the task's time limit was hit) / early-stop:&lt;type&gt; (the model ended by itself without a deliverable: reasoning-only = ended in the middle of its reasoning, announce = announced the next step and stopped) |
| note | empty in v0.1 |
