#!/bin/bash
# lane_series.sh <a|b> <label> <body-key> <max-min> <limit-output|-> <N>   -- run a T1->T2->T3 (oc1/oc2 alternating) x N series on one lane, in the OC container, under tmux.
# Env for the run is set explicitly (tmux does not inherit the caller's environment). Status: <results_dir>/series_status.json.
cd "$(dirname "$0")"
L=$1; LABEL=$2; BODY=$3; MAXM=${4:-180}; LIM=${5:--}; N=${6:-1}
S="series-$L-$LABEL"
tmux new-session -d -s "$S" "cd $(pwd) && BENCH_LANE=$L BENCH_OC_MODE=container SERIES_TASKS=${SERIES_TASKS:-} SERIES_MAXMIN=${SERIES_MAXMIN:-} SERIES_START_N=${SERIES_START_N:-} SERIES_HARNESS=${SERIES_HARNESS:-} SERIES_SKIP=${SERIES_SKIP:-} SERIES_EXPECT_MODEL=${SERIES_EXPECT_MODEL:-} SERIES_THERMAL_GATE=${SERIES_THERMAL_GATE:-} SERIES_STATUS_CMD=\"${SERIES_STATUS_CMD:-}\" BENCH_SMALL_EXCLUDE=${BENCH_SMALL_EXCLUDE:-} BENCH_ALLOW_COND_DIFF=\"${BENCH_ALLOW_COND_DIFF:-}\" python3 run_series.py $LABEL $BODY $MAXM $LIM $N 2>&1 | tee -a ~/series-$L-$LABEL.log"
echo "started tmux session: $S (log ~/series-$L-$LABEL.log)"
