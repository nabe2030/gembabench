#!/usr/bin/env python3
"""Reference solutions (validation of check.sh only; NEVER shown to subjects). Applies a known-good solution to the containers via `incus exec`.
Usage: refsolve.py T4|T5|T6   (run restore_clean() before; run ./check.sh <T> after)."""
import sys, time, textwrap, json
from lib import *

def run(c, cmd, t=900, show=True):
    rc, o, e = cx(c, cmd, t)
    if show: print("[%s rc=%d] %s" % (c, rc, (o + e).strip().splitlines()[-1][:160] if (o + e).strip() else ""))
    return rc, o + e

def T6():
    import base64
    base = json.load(open(BASELINE_PATH))
    patch = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "refpatch_T6.py"), "rb").read().replace(b"@@SUBJECT_COUNT@@", str(base["search_counts"]["subject"]).encode())
    cx("web", "echo %s | base64 -d | python3; php -l /var/www/inquiry/src/InquiryRepository.php; php -l /var/www/inquiry/tests/run_tests.php" % base64.b64encode(patch).decode())
    print(out("web", "cd /var/www/inquiry && php tests/run_tests.php"))

def T5():
    run("db", "sed -i 's/^bind-address.*/bind-address = " + DB_IP + "/' /etc/mysql/mysql.conf.d/mysqld.cnf; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nftables >/dev/null 2>&1; "
              "nft add table inet hk; nft 'add chain inet hk input { type filter hook input priority 0; policy accept; }'; nft add rule inet hk input tcp dport 3306 ip saddr != " + WEB_IP + " drop; systemctl restart mysql; nft list ruleset | head -n 8")
    for c in CONTAINERS:
        run(c, "sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config; systemctl reload ssh; "
               "rm -f /etc/sudoers.d/tanaka; rm -rf /home/tanaka/.ssh; usermod -L -s /usr/sbin/nologin tanaka; gpasswd -d tanaka sudo 2>/dev/null; true")
    run("db", "mysql -e \"DROP USER 'tanaka'@'%'; UPDATE inquiry.users SET active=0 WHERE username='tanaka'; UPDATE inquiry.api_tokens SET disabled=1 WHERE user_id=1; INSERT INTO inquiry.api_tokens VALUES ('hkapi_sato_0123456789abcdef0123456789abcdef', 2, NOW(), 0);\"")
    run("web", "sed -i 's/hkapi_tanaka_[0-9a-f]*/hkapi_sato_0123456789abcdef0123456789abcdef/' /opt/hk-tools/nightly_summary.sh; chmod 640 /var/www/inquiry/config.php; chgrp www-data /var/www/inquiry/config.php; "
               "rm -f /var/www/inquiry/public/backup.sql /var/www/inquiry/public/.git; "
               "sed -i 's#^\\(\\s*\\)location / {#\\1location ^~ /uploads/ { location ~ \\\\.php$ { return 403; } }\\n\\1location / {#' /etc/nginx/conf.d/hk.conf; "
               "mkdir -p /etc/ssl/hk; openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj /CN=inquiry.hiiragi-kinzoku.example -keyout /etc/ssl/hk/inquiry.key -out /etc/ssl/hk/inquiry.crt 2>/dev/null; "
               "sed -i 's#^\\(\\s*\\)\\*#&#' /etc/cron.d/hk-sync; sed -i 's/^/#/' /etc/cron.d/hk-sync; nginx -t 2>&1 | tail -n 1; systemctl reload nginx")

def T4(skip_report_fix=False):
    t0 = time.time()
    run("db", "mysqldump --single-transaction --routines inquiry | gzip > /var/backups/mysql/pre-update-$(date +%Y%m%d).sql.gz; ls -la /var/backups/mysql | tail -n 2")
    run("db", "apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get -y -qq dist-upgrade >/dev/null 2>&1; mysql --version; systemctl is-active mysql")
    run("web", "mv /etc/cron.d/hk-sync /root/hk-sync.disabled; apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get -y -qq dist-upgrade >/dev/null 2>&1; DEBIAN_FRONTEND=noninteractive apt-get -y -qq install ubuntu-release-upgrader-core >/dev/null 2>&1; echo prepared")
    t1 = time.time()
    run("web", "DEBIAN_FRONTEND=noninteractive do-release-upgrade -f DistUpgradeViewNonInteractive >/root/ru.log 2>&1; lsb_release -ds", 3600)
    print("do-release-upgrade seconds: %.0f" % (time.time() - t1), flush=True)
    run("web", "DEBIAN_FRONTEND=noninteractive apt-get -y -qq install php8.3-fpm php8.3-mysql php8.3-mbstring php8.3-cli >/dev/null 2>&1; php -v | head -n 1")
    import base64
    run("web", "sed -i 's#php8.1-fpm.sock#php8.3-fpm.sock#' /etc/nginx/conf.d/hk.conf")
    if not skip_report_fix:
        patch = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "refpatch_T4_report.py"), "rb").read()
        run("web", "echo %s | base64 -d | python3" % base64.b64encode(patch).decode())
    run("web", "rsync -a --delete /var/www/inquiry/ /srv/golden/inquiry/; systemctl enable --now php8.3-fpm; systemctl restart nginx; sleep 2; systemctl is-active nginx php8.3-fpm")
    print("T4 reference total seconds: %.0f" % (time.time() - t0))

if __name__ == "__main__":
    if sys.argv[1] == "T4": T4(skip_report_fix=("--skip-report-fix" in sys.argv))
    else: {"T5": T5, "T6": T6}[sys.argv[1]]()
