#!/bin/bash
# Run on the test-environment host as admin. Usage: bootstrap_containers.sh "<build ssh pubkey>"
# Creates web/db (Ubuntu 22.04, fixed IPs on incusbr0), apt via the allow-list proxy, sshd, evaluser(sudo) with the BUILD key.
set -euo pipefail
BUILD_PUB="$1"
SFX="${LANE_SFX:-}"; WEB_IP="${WEB_IP:-10.92.0.11}"; DB_IP="${DB_IP:-10.92.0.12}"; BRIDGE="${BRIDGE:-incusbr0}"; GW="${GW:-10.92.0.1}"
mk() { # name ip (creates if missing; starts if stopped)
  if ! incus info "$1" >/dev/null 2>&1; then
    incus init images:ubuntu/22.04 "$1" -c security.nesting=true -n "$BRIDGE"
    incus config device set "$1" eth0 ipv4.address="$2"
  fi
  [ "$(incus info "$1" | awk '/^Status:/{print $2}')" = RUNNING ] || incus start "$1"
}
mk web$SFX $WEB_IP
mk db$SFX $DB_IP
for c in web$SFX db$SFX; do
  for i in $(seq 1 40); do incus exec $c -- ip -4 addr show eth0 2>/dev/null | grep -q "${GW%.*}." && break; sleep 2; done
  incus exec $c -- sh -c "printf 'Acquire::http::Proxy \"http://$GW:3128\";\nAcquire::https::Proxy \"http://$GW:3128\";\n' > /etc/apt/apt.conf.d/01proxy; apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server python3 sudo >/dev/null 2>&1"
  incus exec $c -- sh -c "id evaluser >/dev/null 2>&1 || useradd -m -s /bin/bash evaluser; echo 'evaluser ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/evaluser; chmod 440 /etc/sudoers.d/evaluser; mkdir -p /home/evaluser/.ssh; echo '$BUILD_PUB' > /home/evaluser/.ssh/authorized_keys; chown -R evaluser:evaluser /home/evaluser/.ssh; chmod 700 /home/evaluser/.ssh; chmod 600 /home/evaluser/.ssh/authorized_keys; systemctl enable --now ssh >/dev/null 2>&1; systemctl is-active ssh"
done
incus list -c n4s -f csv
