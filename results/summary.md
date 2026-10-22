# Summary (median [min–max] over the repetitions)

| Task | Metric | DGX Spark | RTX 4060 Ti 16GB + Strata | RTX 3060 12GB x2 + Strata |
|---|---|---|---|---|
| T1 | n | 3 | 3 | 3 |
| T1 | score (/45) | 43 [38–45] | 40 [39–45] | 42 [40–42] |
| T1 | duration (min) | 30.3 [21–60.7] | 11 [10.9–20.1] | 11.4 [10.2–12.3] |
| T1 | duration excl. waits (min) | 30.3 [21–60.7] | 11 [10.9–20.1] | 11.4 [10.2–12.3] |
| T1 | output tokens | 49145 [33633–94206] | 22833 [22746–38059] | 21415 [18408–22615] |
| T1 | endings other than normal | - | - | - |
| T2 | n | 3 | 3 | 3 |
| T2 | score (/8) | 6 [6–8] | 7 [5–8] | 7 [6–8] |
| T2 | duration (min) | 24.6 [24.1–55] | 15 [11.5–20] | 17.2 [14.1–20.7] |
| T2 | duration excl. waits (min) | 24.6 [24.1–55] | 15 [11.5–20] | 17.2 [14.1–20.7] |
| T2 | output tokens | 38519 [37789–87658] | 28928 [21665–42273] | 29983 [23540–36265] |
| T2 | endings other than normal | - | - | - |
| T3 | n | 3 | 3 | 3 |
| T3 | score (/8) | 8 [8–8] | 8 [0–8] | 8 [8–8] |
| T3 | T3b points | 2 [2–4] | 4 [0–4] | 2 [1–3] |
| T3 | duration (min) | 35.6 [29.5–48] | 19.7 [19.2–19.9] | 20.6 [17.4–23.2] |
| T3 | duration excl. waits (min) | 35.6 [29.5–48] | 19.7 [19.2–19.9] | 20.6 [17.4–23.2] |
| T3 | output tokens | 36954 [28923–57207] | 25750 [22312–26000] | 24429 [24282–26021] |
| T3 | endings other than normal | - | r2 early-stop:announce | - |
| T4 | n | 3 | 3 | 3 |
| T4 | score (/31) | 31 [27–31] | 31 [31–31] | 31 [28–31] |
| T4 | full-score trials | 2/3 | 3/3 | 2/3 |
| T4 | duration (min) | 47.3 [42.8–64.3] | 37.4 [20.6–47.7] | 27.8 [26.2–67.1] |
| T4 | duration excl. waits (min) | 27.2 [25–31] | 20.6 [15.9–21.6] | 18.9 [18.2–54.6] |
| T4 | output tokens | 35691 [34437–46496] | 30718 [28363–42353] | 28914 [27620–88574] |
| T4 | endings other than normal | - | - | - |
| T5 | n | 3 | 3 | 3 |
| T5 | score (/45) | 41 [11–43] | 39 [38–42] | 42 [39–43] |
| T5 | full-score trials | 0/3 | 0/3 | 0/3 |
| T5 | duration (min) | 108.8 [8.4–150] | 14.5 [12.9–17.9] | 17.6 [11.2–27.6] |
| T5 | duration excl. waits (min) | 97.6 [8.4–149.5] | 14.5 [12.9–17.9] | 17.6 [11.2–27.6] |
| T5 | output tokens | 154414 [12900–237782] | 29381 [26104–37587] | 31133 [18872–45618] |
| T5 | endings other than normal | r2 time-cap, r3 early-stop:reasoning-only | - | - |
| T6 | n | 3 | 3 | 3 |
| T6 | score (/23) | 23 [8–23] | 23 [23–23] | 23 [23–23] |
| T6 | full-score trials | 2/3 | 3/3 | 3/3 |
| T6 | duration (min) | 10.7 [2.1–10.8] | 8.8 [7–11.2] | 16.7 [15.7–19.6] |
| T6 | duration excl. waits (min) | 10.7 [2.1–10.8] | 8.8 [7–11.2] | 16.7 [15.7–19.6] |
| T6 | output tokens | 16577 [2908–16839] | 17253 [13871–23644] | 29754 [27187–35450] |
| T6 | endings other than normal | r3 early-stop:announce | - | - |
