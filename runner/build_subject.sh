#!/bin/bash
# build_subject.sh -- create the subject container: the Incus container on the runner host in which the harness (OpenCode) runs as user `evalrun`.
# Run on the runner host from the repository root:  bash runner/build_subject.sh
# Reads gemba.conf.json (lanes.a: oc = container name, subject_net = Incus bridge, subject_ip = optional fixed address) and creates:
#   - the container (Ubuntu 24.04) on that bridge, with the tools the subject may use (ssh client, curl, git, jq, ripgrep, rsync, dig, nc, unzip, vim, python3)
#   - user evalrun (uid 1001, no sudo) with an ssh key for the targets: the public key is written to subject_target_key.pub (give it to build_testenv.sh)
#   - OpenCode 2.0.25 at /opt/opencode/2.0.25/opencode, from the official distribution (no npm), checked against the pinned SHA256
#   - the `clean` snapshot (every trial starts from it)
# The subject network is meant to be isolated (see network/). If the container cannot reach an apt mirror, the packages are downloaded on the host
# (`apt-get download`, same Ubuntu release required) and installed from the .deb files, so nothing has to be opened in the firewall.
# Re-running deletes and recreates the container (only the one named in the configuration).
set -euo pipefail
exec < /dev/null      # incus init/network create read a YAML config from a non-terminal stdin, and incus exec/ssh would consume it: never give them one
ROOT=$(cd "$(dirname "$0")/.." && pwd); CONF=${GEMBA_CONF:-$ROOT/gemba.conf.json}
INCUS=${INCUS:-sudo incus}
cv() { python3 -c "import json,sys;l=(json.load(open(sys.argv[1])).get('lanes') or {}).get('a',{});print(l.get(sys.argv[2],sys.argv[3]))" "$CONF" "$1" "$2"; }
NAME=$(cv oc subject); NET=$(cv subject_net gemba-subject); IP=$(cv subject_ip ""); CIDR=$(cv subject_net_cidr 10.0.10.1/24)
IMAGE=${IMAGE:-images:ubuntu/24.04}
OC_VER=2.0.25
OC_URL=https://registry.npmjs.org/@opencode/cli-linux-x64/-/cli-linux-x64-$OC_VER.tgz      # the file opencode.ai/v2/install downloads (plain HTTPS, no npm)
OC_TGZ_SHA=5b3e50ad1c06214aaf1c26eb30f90a15f66975a6e3e48fef5a31c34466e37b5a
OC_BIN_SHA=80e71850636ec3e1dbac78f53d863c4dc0c0de6d6049daa5687852fa483319fc
PKGS="openssh-client curl ca-certificates git jq ripgrep rsync dnsutils netcat-openbsd unzip vim-tiny less procps python3"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT

echo "== 1. OpenCode $OC_VER (official distribution, SHA256 checked)"
if [ -n "${OPENCODE_TGZ:-}" ]; then cp "$OPENCODE_TGZ" "$W/oc.tgz"; else curl -fsSL -o "$W/oc.tgz" "$OC_URL"; fi
echo "$OC_TGZ_SHA  $W/oc.tgz" | sha256sum -c --quiet
tar -xzf "$W/oc.tgz" -C "$W" package/bin/opencode
echo "$OC_BIN_SHA  $W/package/bin/opencode" | sha256sum -c --quiet && echo "   opencode binary verified"

echo "== 2. container $NAME on $NET"
if ! $INCUS network show "$NET" >/dev/null 2>&1; then
  $INCUS network create "$NET" ipv4.address="$CIDR" ipv4.nat=true ipv6.address=none
  echo "   created the bridge $NET ($CIDR): apply the isolation rules of network/ before running trials"
fi
$INCUS info "$NAME" >/dev/null 2>&1 && $INCUS delete "$NAME" --force
$INCUS init "$IMAGE" "$NAME" -n "$NET" --quiet
[ -n "$IP" ] && $INCUS config device set "$NAME" eth0 ipv4.address="$IP"
$INCUS start "$NAME"
for i in $(seq 1 60); do $INCUS exec "$NAME" -- bash -c "ip -4 -br addr show eth0 | grep -q '[0-9]\.[0-9]'" 2>/dev/null && break; sleep 2; done
$INCUS exec "$NAME" -- ip -4 -br addr show eth0

echo "== 3. packages: $PKGS"
if $INCUS exec "$NAME" -- bash -c "timeout 60 apt-get update -qq --error-on=any" >/dev/null 2>&1; then      # plain apt-get update exits 0 even when no mirror is reachable
  $INCUS exec "$NAME" -- bash -c "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends $PKGS >/dev/null"
  echo "   installed with apt inside the container"
else
  echo "   the container has no apt mirror (isolated network): downloading the .deb files on the host"
  HOST_REL=$(. /etc/os-release; echo "$VERSION_ID"); CT_REL=$($INCUS exec "$NAME" -- bash -c '. /etc/os-release; echo $VERSION_ID')
  [ "$HOST_REL" = "$CT_REL" ] || { echo "host Ubuntu $HOST_REL differs from the container's $CT_REL: give the container an apt mirror instead"; exit 1; }
  $INCUS exec "$NAME" -- dpkg-query -W -f='${Package}\n' | sort -u > "$W/installed"
  apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances $PKGS 2>/dev/null \
    | grep -E '^[a-z0-9]' | sed 's/:.*//' | sort -u > "$W/needed"
  comm -23 "$W/needed" "$W/installed" > "$W/missing"
  mkdir -p "$W/debs" && (cd "$W/debs" && xargs -a "$W/missing" apt-get download -qq 2>/dev/null || true)
  ls "$W/debs"/*.deb >/dev/null 2>&1 || { echo "no .deb could be downloaded (run apt-get update on the host?)"; exit 1; }
  $INCUS exec "$NAME" -- mkdir -p /tmp/debs
  for f in "$W/debs"/*.deb; do $INCUS file push --quiet "$f" "$NAME/tmp/debs/"; done
  $INCUS exec "$NAME" -- bash -c "dpkg -i /tmp/debs/*.deb >/dev/null 2>&1 || dpkg --configure -a; rm -rf /tmp/debs"
  echo "   installed $(wc -l < "$W/missing") packages from .deb files"
fi
for c in ssh curl git jq rg rsync dig nc unzip python3; do $INCUS exec "$NAME" -- bash -c "command -v $c >/dev/null" || { echo "missing tool in the container: $c"; exit 1; }; done

echo "== 4. user evalrun, OpenCode, ssh key"
$INCUS exec "$NAME" -- bash -c "id evalrun >/dev/null 2>&1 || useradd -m -u 1001 -U -s /bin/bash evalrun; mkdir -p /opt/opencode/$OC_VER"
$INCUS file push --quiet --uid 0 --gid 0 --mode 0755 "$W/package/bin/opencode" "$NAME/opt/opencode/$OC_VER/opencode"
$INCUS exec "$NAME" -- su - evalrun -c "mkdir -p ~/.ssh && chmod 700 ~/.ssh && ssh-keygen -t ed25519 -N '' -C gemba-subject -f ~/.ssh/id_ed25519_target -q"
$INCUS exec "$NAME" -- cat /home/evalrun/.ssh/id_ed25519_target.pub > "$ROOT/subject_target_key.pub"
$INCUS exec "$NAME" -- su - evalrun -c "/opt/opencode/$OC_VER/opencode --version"

echo "== 5. clean snapshot"
$INCUS stop "$NAME" --timeout 60
$INCUS snapshot create "$NAME" clean
$INCUS start "$NAME"
echo "done: $NAME (snapshot clean). Subject public key: $ROOT/subject_target_key.pub"
