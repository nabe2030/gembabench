#!/bin/bash
# check.sh <T4|T5|T6|baseline> [out.json]  -- per-task checks (items as OK/NG JSON). Executed on the runner host; reaches the containers via the test-environment host `incus exec`.
cd "$(dirname "$0")" && exec python3 checks.py "$@"
