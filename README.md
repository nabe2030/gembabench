# GembaBench v0.1

**GembaBench measures whether an AI agent can do the on-site work of running a company's servers** — survey a system nobody documented properly, find the traces of an intrusion, plan and carry out an update, and fix configuration and vulnerabilities — on real (containerised) servers, over ssh, the way an outside engineer would.

Benchmarks such as Aider Polyglot or SWE-bench measure how well a model reads and writes code. GembaBench ("gemba" = 現場, the shop floor) measures the operations side: the agent is given a task sheet and an outdated runbook, logs in to a small company's web and database servers, and has to work out what is really there, decide what is safe to do, do it, and report honestly.

> [!WARNING]
> **The test environment is deliberately vulnerable.** It contains a web application with an SQL injection, a planted web shell, leaked credentials, a departed employee's live keys and more — that is what the agent is asked to find and fix. **Run it only on an isolated network and never expose it to the Internet or your LAN.** The example firewall rules in `network/` show the isolation used for the published measurements.

## What is in this repository

| Path | Contents |
|---|---|
| `scenario-01/` | Scenario s01 "inquiry management system (web + DB) of a small manufacturer": `scenario.yaml` (environment, planted problems, intrusion timeline, **the answers**), task sheets `tasks/`, documents the agent receives `docs/`, the company's PHP apps `app/` and site `site/`, the data generator `gen/`, reference answers `ref/`, and the build (`build_testenv.sh`, `bootstrap_containers.sh`, `finalize_containers.sh`, `ansible/`) |
| `runner/` | Builds the subject container (`build_subject.sh`), runs one trial or a series (`run_trial.py`, `run_series.py`, `lane_series.sh`), the checks on the servers after a trial (`checks.py`, `check.sh`, `endstate.py`, `rootdiff.py`, `plants.py`), the report judges (`judge_reports.py`, `judge_v3.py`), the tool-log analysis (`toollog.py`), re-judging (`rejudge.py`, and `rescore.py` for T4–T6 from the end-of-trial state), early-stop / wait / step statistics, the condition guard, and `summarize_results.py` |
| `budget_proxy/` | `budget_proxy.py`: an OpenAI-compatible proxy that enforces a thinking-token budget for engines that do not (counts the streamed reasoning, closes the thinking at the budget and lets the model continue with the answer) |
| `serve_verify/` | `scripted_server.py`: a scripted OpenAI-compatible server to check the harness behaviour without a real model (`--smoke` with `BENCH_TEST_SCRIPTED_SERVER`) |
| `network/` | Example isolation rules (nftables) for both hosts and the allow-list proxy (squid) of the test containers |
| `results/` | The published results: `trials.csv` (one row per trial) and `summary.md` |
| `gemba.conf.example.json`, `runner/servers.example.json`, `requirements.txt` | Configuration templates (your hosts, keys, model servers) and the Python dependency |

The answers are public on purpose: the benchmark is the environment and the work, not a secret answer key. A model that has seen this repository may know the answers; keep that in mind when you compare models trained after its publication.

## The tasks (scenario s01)

The agent plays an outside engineer hired by a fictional manufacturer, Hiiragi Kinzoku Kogyo (all names, companies, mail addresses and phone numbers are fictional; domains use `.example`). The in-house administrator has left; there is a runbook that no longer matches the servers.

| Task | Work | Deliverable | Scored by |
|---|---|---|---|
| T1 | Survey both servers read-only and report the risks, in order of severity | report | F1: 18 planted problems weighted by severity (45 points), F2: runbook vs. reality |
| T2 | Investigate the traces of an intrusion: when, how, from where, what was exposed, what is *not* an attack | report | F3: 8 items (first contact, foothold, lateral move to the DB, data exposed, decoys not confused, …) |
| T3 + T3b | Design the update plan (OS/PHP/DB) from a flawed draft; then revise it after three management decisions change | plan, revised plan | C: 8 items (order with reasons, backup with a restore test, the sync job that would undo the update, PHP 8.3 breakage, keeping the bulletin board up, rollback inside the server, the departed employee's access, window and notice); T3b: 6 points |
| T4 | Carry out the update (Ubuntu 24.04, PHP 8.3, latest MySQL 8.0 patch) and keep the system working | work log | 31 points checked live on the servers afterwards (versions, no pending security updates, pages unchanged, reports and search work, data and attachments kept, backup restorable, the hourly sync that would undo the update neutralised, nightly batch alive) |
| T5 | Contain and harden after the intrusion: revoke the departed employee's access, close the exposures, keep the business running | report | 45 points checked live (keys/sudo/DB user/app admin revoked, token replaced and the batch still works, DB not open, files not served, TLS valid, …) |
| T6 | Fix the SQL injection in the inquiry search (coding) without breaking anything | report + code | 23 points checked live (injection and variants blocked, normal search unchanged, all pages work, tests pass and a test was added, small diff, no SQL built by concatenation, nothing committed) |

Besides the scores, every trial records: forbidden actions (F5, from the tool log), claims in the report that the tool log does not support (F6), files changed on the servers (F9), early stops (the model ended without a deliverable), duration with and without deliberate waits, output tokens, steps and context use.

## Results of v0.1 (Qwen3.8-Flash-Next, 3 configurations)

Model: Qwen3.8-Flash-Next. Harness: OpenCode 2.0.25. Thinking: medium, capped at 8,192 tokens (through `budget_proxy.py`), output limit 16,384. N = 3 per task (54 trials). Judge version j14. The write-up (in Japanese) is on Qiita: https://qiita.com/nabe2030/items/f14c0fdd0c1535b9ab16

Median [min–max] over the 3 repetitions; full table in `results/summary.md`, every trial in `results/trials.csv`.

| Task (max) | DGX Spark (fp4, SGLang) | RTX 4060 Ti 16GB + Strata (IQ3_S, MTP 4) | RTX 3060 12GB ×2 + Strata (IQ3_S, MTP 4) |
|---|---|---|---|
| T1 score (45) | 43 [38–45] | 40 [39–45] | 42 [40–42] |
| T2 score (8) | 6 [6–8] | 7 [5–8] | 7 [6–8] |
| T3 score (8) / T3b (6) | 8 [8–8] / 2 [2–4] | 8 [0–8] / 4 [0–4] | 8 [8–8] / 2 [1–3] |
| T4 score (31), full-score trials | 31 [27–31], 2/3 | 31 [31–31], 3/3 | 31 [28–31], 2/3 |
| T5 score (45) | 41 [11–43] | 39 [38–42] | 42 [39–43] |
| T6 score (23), full-score trials | 23 [8–23], 2/3 | 23 [23–23], 3/3 | 23 [23–23], 3/3 |
| T4 duration excl. waits (min) | 27.2 [25–31] | 20.6 [15.9–21.6] | 18.9 [18.2–54.6] |
| T5 duration excl. waits (min) | 97.6 [8.4–149.5] | 14.5 [12.9–17.9] | 17.6 [11.2–27.6] |

Endings other than normal: DGX Spark T5 r2 hit the 150-minute limit, DGX Spark T5 r3 and T6 r3 and RTX 4060 Ti T3 r2 ended early without a deliverable (the model stopped by itself). These count as they are.

## How it works

```
runner host (VM)
  runner/            run_trial.py: restore -> run -> check -> judge
  subject container  OpenCode (user evalrun) --- ssh target-web / target-db ---> test-environment host
  budget_proxy.py    -> model server(s), OpenAI-compatible

test-environment host (VM)
  Incus: web 10.92.0.11, db 10.92.0.12 (the company's servers, deliberately vulnerable)
  squid allow-list proxy (apt only)
```

One trial: restore the `clean` snapshots of web and db and of the subject container → write the task sheet, the documents and the OpenCode configuration into the subject's home → start OpenCode with the task prompt → wait (watchdog, time limit) → copy out the deliverables and OpenCode's database → run the live checks on the servers (T4–T6) and the report judges (T1–T3) → write `result.json` and `conditions.json`.

## Running it (the configuration used for the published results)

The measurements used two VMs on one hypervisor plus separate model servers:

- **runner host** (Ubuntu 24.04, 4 vCPU / 8 GB): this repository; `sudo` for `incus`; Incus, Ansible, tmux, openssl, curl and Python 3 with PyYAML (`requirements.txt`). It runs the trials, the checks and the judges, the **subject container** (the Incus container in which OpenCode runs as user `evalrun`) on its own bridge, and `budget_proxy.py`.
- **test-environment host** (Ubuntu 24.04, 6 vCPU / 12 GB): Incus with the bridge `incusbr0` (10.92.0.1/24) and the squid allow-list proxy on 10.92.0.1:3128 (`network/`), reachable from the runner host over ssh as a user who may run `incus` and `sudo` (`testenv.ssh_target`).
- **model servers**: any OpenAI-compatible endpoint (the published runs used SGLang on a DGX Spark and Strata on RTX GPUs), plus a small auxiliary model for OpenCode's hidden title/summary agents.

Steps (all on the runner host, from the repository root):

1. **Configure.** `cp gemba.conf.example.json gemba.conf.json` and `cp runner/servers.example.json runner/servers.json`; fill in the test-environment host, the ssh key for it, the subject bridge and the model servers. `pip install -r requirements.txt` (or `apt install python3-yaml`).
2. **Isolate.** Apply the rules of `network/` (adapted to your interfaces): the subject may reach only the targets' sshd and the model servers; the test containers may reach only the apt proxy.
3. **Subject container:** `bash runner/build_subject.sh`. It creates the container on the subject bridge (Ubuntu 24.04, user `evalrun` uid 1001 without sudo, an ssh key for the targets, the tools the subject may use), installs **OpenCode 2.0.25** and takes the `clean` snapshot. The subject's public key is written to `subject_target_key.pub`. On an isolated bridge without an apt mirror, the packages are downloaded on the host and installed from .deb files (the host must run the same Ubuntu release).
4. **Test environment:** `bash scenario-01/build_testenv.sh`. It creates web and db, generates the scenario data (deterministic from the seed, dated to the build time), runs Ansible, removes the build traces, installs the subject's key, takes the `clean` snapshots and records the baseline (`runner/baseline.json`, `runner/plants_clean.json`). The judges of T1–T3 read `scenario-01/out/meta.json` of this build. Other addresses than 10.92.0.x can be set in `lanes.a` (the data are generated for them).
5. **Reference check.** `python3 scenario-01/ref/refjudge.py` must give full marks (T1 45/45, T2 8/8, T3 8/8, T3b 6/6). For T4–T6, apply the reference fix to a freshly restored environment and run the live check:
   ```
   cd runner
   for T in T4 T5 T6; do python3 -c "from lib import *; print(restore_clean())" && python3 refsolve.py $T && ./check.sh $T | tail -n 1; done
   python3 -c "from lib import *; print(restore_clean())"
   ```
   Expected: `weighted 31/31`, `45/45`, `23/23`.
6. **Run.** One trial: `cd runner && BENCH_OC_MODE=container python3 run_trial.py --task T6 --label <name> --body <key in servers.json> --harness oc2`. A series in tmux: `SERIES_TASKS=T1,T2,T3,T4,T5,T6 ./lane_series.sh a <label> <body-key> 180 16384 3`. The condition guard stops a trial whose model definition differs from `runner/condition_lock.json` (the published conditions: thinking medium, budget 8192, output 16384); for a different model or setting, pass `BENCH_ALLOW_COND_DIFF="<reason>"` (the reason is recorded in `conditions.json`).
7. **Summarize:** `python3 runner/summarize_results.py --results <results_dir> --config "<name>=<label>" --out <dir>`.

### OpenCode 2.0.25

`build_subject.sh` installs it from the official distribution, the same file `opencode.ai/v2/install` downloads (plain HTTPS; npm is not used): `https://registry.npmjs.org/@opencode/cli-linux-x64/-/cli-linux-x64-2.0.25.tgz`, SHA256 `5b3e50ad1c06214aaf1c26eb30f90a15f66975a6e3e48fef5a31c34466e37b5a`. The binary inside (`package/bin/opencode`) has SHA256 `80e71850636ec3e1dbac78f53d863c4dc0c0de6d6049daa5687852fa483319fc` and goes to `/opt/opencode/2.0.25/opencode`; `opencode --version` prints `2.0.25`. To install from a file you downloaded yourself: `OPENCODE_TGZ=<file> bash runner/build_subject.sh`.

**A single-PC setup is being verified** (both roles on one machine with nested containers). It has not been run end to end yet; until then, use the two-host layout above.

## Operational notes (lessons from the measurements)

- **OpenCode 2.x: run against a resident `opencode serve`.** In headless mode (`opencode run --standalone`) the run ends when the model's turn ends, so a command the model started with `background: true` never reports back and the work is cut off. The runner starts `opencode serve` per trial in the subject container and runs `opencode run --server …` against it (`--run-mode serve`, the default).
- **The watchdog must not count a running command as silence.** Models legitimately wait for cron jobs or long upgrades (`sleep 900`, `do-release-upgrade`). The runner treats the trial as stalled only when there is no event *and* no tool command is running; one tool command may run up to 65 minutes. Durations are also reported without such deliberate waits.
- **Check that the thinking budget really applies.** Some engines ignore `reasoning_budget_tokens`/`thinking_budget`. Verify with a long prompt that the reasoning stops at the budget (the proxy logs every cut); also check how the engine streams the reasoning (one chunk is not always one token).
- Start the event stream of `opencode serve` with stdin from `/dev/null`; under `sudo` with `use_pty`, a client that inherits a terminal can spin on it.
- Keep the condition guard (`runner/condguard.py`, `condition_lock.json`): it stops a series when the model definition (thinking settings, timeouts, limits) differs from the reference, so two configurations cannot silently run under different conditions.

## License

Apache License 2.0 (`LICENSE`). The scenario's company, people and data are fictional.
