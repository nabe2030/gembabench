#!/bin/bash
# lane_trial.sh <a|b> <task> <label> <body-key> <oc1|oc2> [trial] [max-minutes] [extra run_trial.py args...] -- one trial on a lane, in the OC container, under tmux
cd "$(dirname "$0")"
L=$1; T=$2; LABEL=$3; BODY=$4; HN=$5; N=${6:-1}; M=${7:-}; shift 7 2>/dev/null || shift $#
S="trial-$L-$T-$LABEL-$HN-r$N-$(date +%H%M%S)"
tmux new-session -d -s "$S" "cd $(pwd) && BENCH_LANE=$L BENCH_OC_MODE=container python3 run_trial.py --task $T --label $LABEL --body $BODY --harness $HN --trial $N ${M:+--max-minutes $M} $* 2>&1 | tee -a ${GEMBA_RESULTS:-$HOME/gemba-results}/last_run_${L}_${T}.log; sleep 5"
echo "started tmux session: $S"
