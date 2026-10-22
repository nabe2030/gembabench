#!/bin/bash
# gen_tls.sh -- create the fictional company's self-signed TLS certificate and key for the test environment: inquiry.crt / inquiry.key in this directory.
# The certificate is EXPIRED on purpose (valid 2025-04-01 .. 2026-03-31): replacing it is one of the T5 checks (tls_valid). Run by build_testenv.sh.
# OpenSSL 3.0 compatible (`openssl ca` is used because `req -x509` cannot set dates in the past there).
set -euo pipefail
cd "$(dirname "$0")"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
mkdir -p "$W/db"; : > "$W/db/index.txt"; echo 01 > "$W/db/serial"
cat > "$W/ca.cnf" <<'EOF'
[ ca ]
default_ca = local
[ local ]
dir = .
database = $dir/db/index.txt
serial = $dir/db/serial
new_certs_dir = $dir
default_md = sha256
policy = any
copy_extensions = copy
unique_subject = no
[ any ]
commonName = supplied
organizationName = optional
[ req ]
distinguished_name = dn
prompt = no
req_extensions = san
[ dn ]
CN = inquiry.hiiragi-kinzoku.example
O = Hiiragi Kinzoku Kogyo (fictional)
[ san ]
subjectAltName = DNS:inquiry.hiiragi-kinzoku.example, DNS:www.hiiragi-kinzoku.example, DNS:board.hiiragi-kinzoku.example
EOF
(cd "$W" && openssl req -new -newkey rsa:2048 -nodes -keyout inquiry.key -out inquiry.csr -config ca.cnf 2>/dev/null \
  && openssl ca -batch -selfsign -config ca.cnf -keyfile inquiry.key -in inquiry.csr -out inquiry.crt -notext \
       -startdate 20250401000000Z -enddate 20260331235959Z -extensions san -extfile ca.cnf 2>/dev/null)
cp "$W/inquiry.crt" "$W/inquiry.key" .
openssl x509 -in inquiry.crt -noout -subject -dates
