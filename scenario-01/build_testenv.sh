#!/bin/bash
# build_testenv.sh -- build (or rebuild from scratch) the scenario-01 test environment: two Incus containers (web and db) on the test-environment host.
# Run on the runner host from the repository root:  bash scenario-01/build_testenv.sh      (after runner/build_subject.sh, which writes the subject's public key)
# Needs: gemba.conf.json (testenv.ssh_target / ssh_key; lanes.a: web, db, web_ip, db_ip, gw, bridge), ansible-playbook and PyYAML on the runner host,
#        on the test-environment host an Incus bridge (default incusbr0, 10.92.0.1/24) and the allow-list HTTP proxy on <gw>:3128 (see network/).
# Steps: (1) recreate web/db and install sshd + the build key, (2) generate the scenario data (deterministic from the seed; the scenario "now" = build time),
#        (3) Ansible builds the company's servers, (4) remove the build traces, install the subject's key, take the `clean` snapshot, (5) plants check + baseline.
# Only the two containers named in the configuration are deleted and recreated.
# WARNING: the containers are deliberately vulnerable (that is the benchmark). Keep them on an isolated network.
set -euo pipefail
exec < /dev/null      # incus init/network create read a YAML config from a non-terminal stdin, and incus exec/ssh would consume it: never give them one
ROOT=$(cd "$(dirname "$0")/.." && pwd); SC=$ROOT/scenario-01
CONF=${GEMBA_CONF:-$ROOT/gemba.conf.json}
cf() { python3 -c "import json,os,sys;c=json.load(open(sys.argv[1]));v=c
for k in sys.argv[2].split('.'): v=v.get(k,{}) if isinstance(v,dict) else {}
print(os.path.expanduser(v) if isinstance(v,str) and v else sys.argv[3])" "$CONF" "$1" "$2"; }
TE=$(cf testenv.ssh_target ""); TK=$(cf testenv.ssh_key "")
[ -n "$TE" ] && [ -n "$TK" ] || { echo "set testenv.ssh_target and testenv.ssh_key in $CONF"; exit 1; }
WEB=$(cf lanes.a.web web); DB=$(cf lanes.a.db db); SFX=${WEB#web}; [ "$DB" = "db$SFX" ] || { echo "lanes.a.web/db must be web<suffix>/db<suffix>"; exit 1; }
WEB_IP=$(cf lanes.a.web_ip 10.92.0.11); DB_IP=$(cf lanes.a.db_ip 10.92.0.12); GW=$(cf lanes.a.gw 10.92.0.1); BR=$(cf lanes.a.bridge incusbr0); OUT=$(cf lanes.a.out out)
SO="-i $TK -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
BUILD_KEY=${BUILD_KEY:-$HOME/.ssh/id_ed25519_gemba_build}          # used by Ansible only; it is removed from the containers again in step 4
SUBJECT_PUB=${SUBJECT_PUB:-$ROOT/subject_target_key.pub}           # written by runner/build_subject.sh
[ -f "$SUBJECT_PUB" ] || { echo "no subject public key at $SUBJECT_PUB: run runner/build_subject.sh first (or set SUBJECT_PUB)"; exit 1; }
[ -f "$BUILD_KEY" ] || ssh-keygen -t ed25519 -N "" -f "$BUILD_KEY" -q
echo "== 1. recreate $WEB ($WEB_IP) and $DB ($DB_IP) on $BR"
ssh $SO "$TE" "for c in $WEB $DB; do incus info \$c >/dev/null 2>&1 && incus delete \$c --force; done; true"
scp -q $SO "$SC/bootstrap_containers.sh" "$TE:/tmp/"
ssh $SO "$TE" "LANE_SFX=$SFX WEB_IP=$WEB_IP DB_IP=$DB_IP BRIDGE=$BR GW=$GW bash /tmp/bootstrap_containers.sh \"$(cat "$BUILD_KEY.pub")\""
echo "== 2. generate the scenario data"
cd "$SC" && rm -rf "$OUT"
BENCH_WEB_IP=$WEB_IP python3 gen/gen_data.py scenario.yaml "$OUT" >/dev/null
TOK=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['tanaka_token'])" "$OUT/meta.json")
echo "== 3. ansible (the fictional company's expired self-signed certificate is generated first)"
bash ansible/files/gen_tls.sh
printf '[web]\n%s\n[db]\n%s\n[all:vars]\nansible_user=evaluser\nansible_ssh_private_key_file=%s\nansible_ssh_common_args=-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=%s\nansible_python_interpreter=/usr/bin/python3\n' \
  "$WEB_IP" "$DB_IP" "$BUILD_KEY" "$HOME/.ssh/known_hosts_gemba_build" > ansible/inventory.ini
rm -f "$HOME/.ssh/known_hosts_gemba_build"
(cd ansible && ansible-playbook -i inventory.ini playbook.yml -e @../scenario.yaml -e out_dir="$SC/$OUT" -e tanaka_token="$TOK" -e web_ip=$WEB_IP -e db_ip=$DB_IP > ../ansible-run.log 2>&1) \
  || { echo "ansible failed: see scenario-01/ansible-run.log"; exit 1; }
tail -n 4 ansible-run.log
echo "== 4. finalize (lift the build pin, remove build traces, install the subject key, clean snapshot)"
scp -q $SO "$SC/finalize_containers.sh" "$TE:/tmp/"
ssh $SO "$TE" "LANE_SFX=$SFX bash /tmp/finalize_containers.sh '$(cat "$SUBJECT_PUB")'"
echo "== 5. plants check and baseline (the baseline belongs to this build: take it again after every rebuild)"
cd "$ROOT/runner" && sleep 15 && python3 plants.py plants_clean.json | tail -n 30
python3 -c "from lib import *; print(restore_clean())" && ./check.sh baseline > baseline_print.json && echo baseline-ok
