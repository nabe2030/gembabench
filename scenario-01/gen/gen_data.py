#!/usr/bin/env python3
"""SCENARIO-01 data generator (deterministic: same seed -> same bytes).
All names/companies/addresses/mails/phones are fictional (mails use .example, phones use unassigned 0X0-0000-NNNN).
Usage: gen_data.py <scenario.yaml> <outdir>
Outputs tarballs web-data.tar / db-data.tar (paths relative to /, mtimes preserved) + sql + meta.json.
"""
import sys, os, json, random, gzip, hashlib, tarfile, datetime as dt, io, shutil
import yaml

Y = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
OUT = sys.argv[2]
SEED = Y["data"]["seed"]
# v1.1: the scenario "now" is the BUILD time (JST), so that logs, cron records, dumps and mails end at the real clock. Everything else is relative to it.
# usage: gen_data.py <scenario.yaml> <outdir> [now "YYYY-MM-DD HH:MM"]   (default: current JST time)
NOW = dt.datetime.strptime(sys.argv[3], "%Y-%m-%d %H:%M") if len(sys.argv) > 3 else (dt.datetime.utcnow() + dt.timedelta(hours=9)).replace(second=0, microsecond=0)
def last_sunday_0625(now):
    d = now.replace(hour=6, minute=25, second=0, microsecond=0)
    d -= dt.timedelta(days=(d.weekday() + 1) % 7)            # Sunday -> 0
    if now - d < dt.timedelta(days=1): d -= dt.timedelta(days=7)
    return d
R0 = last_sunday_0625(NOW); R0D = R0.replace(hour=0, minute=0)   # most recent weekly logrotate (Sunday 06:25) and its date
def rel(days, hms):                                             # R0 date + days + "HH:MM:SS"
    h, m, sec = [int(x) for x in hms.split(":")]
    return R0D + dt.timedelta(days=days, hours=h, minutes=m, seconds=sec)
def month_end(now, back):                                       # last day of the month `back` months before now's month
    y, m = now.year, now.month - back
    while m <= 0: m += 12; y -= 1
    return dt.datetime(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1)
RETIRE = month_end(NOW, 4)                                      # October -> 2026-06-30 ("6 月末" in the TASK texts)
BKDAY = month_end(NOW, 5)                                       # October -> 2026-05-31 (the exposed backup.sql snapshot)
JST = "+0900"
rng = random.Random(SEED)
COMPANY = Y["company"]["name"]
DOMAIN = Y["company"]["domain"]

def ts(d): return d.strftime("%Y-%m-%d %H:%M:%S")
def esc(s):
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") if s is not None else None
def q(v):
    if v is None: return "NULL"
    if isinstance(v, int): return str(v)
    return "'" + esc(v) + "'"

# ---------------- customers ----------------
A = ["東和","北斗","光洋","青葉","大和田","千歳","明星","三松","日の出","柏葉","若草","白樺","丸山","緑川","高砂","桜井","天城","相生","朝日野","岩倉","小野寺","滝沢","月岡","堀内","槙野","水無月","雲仙","美浜","葵","楠"]
B = ["精機","工業","製作所","金属","電機","機工","産業","部品","メタル","鋳造","プレス","工機","熱処理","表面処理","商事"]
SUR = ["佐々木","高橋","田村","渡辺","伊藤","山口","松本","井上","木村","林","斎藤","清水","山崎","森","池田","橋本","阿部","石川","前田","藤田","小川","岡田","後藤","長谷川","村上","近藤","石井","遠藤","青木","坂本"]
GIV = ["太郎","健一","美咲","直樹","彩","大輔","恵","拓也","由美","翔太","千尋","達也","真理","亮","葵","和也","陽子","隆","愛","誠"]
ROMA = {}
customers = []
seen = set()
for i in range(1, Y["data"]["customers"] + 1):
    while True:
        name = rng.choice(A) + rng.choice(B)
        full = ("株式会社" + name) if rng.random() < 0.6 else (name + "株式会社" if rng.random() < 0.3 else "有限会社" + name)
        if full not in seen:
            seen.add(full); break
    contact = rng.choice(SUR) + " " + rng.choice(GIV)
    email = "contact%03d@c%03d.example" % (rng.randint(1, 999), i)
    phone = "0%d0-0000-%04d" % (rng.choice([5, 7, 8, 9]), rng.randint(0, 9999))
    created = dt.datetime(2023, 6, 1) + dt.timedelta(days=rng.randint(0, 900))
    customers.append((i, full, contact, email, phone, ts(created)))

# ---------------- inquiries ----------------
PARTS = ["SUS304 ブラケット","アルミ削り出し筐体","S45C シャフト","真鍮ブッシュ","板金カバー","ステンレスフランジ","ダイカスト部品","アルマイト処理プレート","プレス加工ワッシャ","溶接フレーム","治具プレート","SPCC 折り曲げ部品"]
SUBJ = [
 "{p} の見積依頼","{p} の納期確認","{p} 追加発注のご相談","図面変更のご連絡({p})","試作品 {p} の進捗について",
 "{p} の検査成績書の送付依頼","請求書の宛名変更のお願い","納品書の再発行依頼","{p} の寸法公差についての質問","表面処理(メッキ)の仕様確認",
 "{p} 数量変更のご連絡","工場見学のお願い","取引条件の確認","{p} の材質証明書について","支払日の確認",
 "{p} の不良品についてのお問い合わせ","新規取引のご相談","{p} 梱包仕様の確認","在庫状況の問い合わせ","{p} 見積書の再送依頼"]
BODY = [
 "いつもお世話になっております。{p}について、下記の内容でご確認をお願いいたします。数量は {n} 個、希望納期は {d} です。",
 "お忙しいところ恐れ入ります。{p}の件で、現在の進捗状況を教えていただけますでしょうか。社内の調整の都合で {d} までに回答をいただけると助かります。",
 "先日お送りした図面に一部修正が入りました。{p}について、改訂版を添付しますのでご確認ください。数量は変わらず {n} 個です。",
 "{p}の寸法について、図面の公差指示に疑問があります。{n} 個の発注を予定しているため、事前にご相談させてください。",
 "貴社のホームページを拝見し、{p}の加工についてご相談したくご連絡しました。月産 {n} 個程度を想定しています。",
]
STATUS = ["new","in_progress","done","closed"]
n_inq = Y["data"]["inquiries"]
start = dt.datetime(2024, 1, 4, 9, 0)
end = NOW.replace(hour=17, minute=0) - dt.timedelta(days=1)
span = (end - start).total_seconds()
times = sorted(start + dt.timedelta(seconds=rng.random() * span) for _ in range(n_inq))
# attacker submission (intrusion timeline): R0 date - 6 days 00:03:41, one of the 3000 rows
ATTACK_T = rel(-6, "00:03:41")
times[sorted(range(n_inq), key=lambda i: abs((times[i] - ATTACK_T).total_seconds()))[0]] = ATTACK_T
times.sort()
att_ids = set(rng.sample(range(1, n_inq + 1), Y["data"]["attachments"] - 1))
inquiries = []
attachments = []
for idx, t in enumerate(times, start=1):
    is_attack = (t == ATTACK_T)
    p = rng.choice(PARTS)
    cust = None if is_attack else rng.randint(1, len(customers))
    subj = rng.choice(SUBJ).format(p=p)
    body = rng.choice(BODY).format(p=p, n=rng.choice([10, 50, 100, 200, 500, 1000]), d=(t + dt.timedelta(days=rng.randint(7, 30))).strftime("%m/%d"))
    age = (NOW - t).days
    st = "closed" if age > 120 else ("done" if age > 30 else rng.choice(STATUS))
    att = None
    if is_attack:
        subj, body, att, st = "請求書の件", "請求書を添付します。ご確認ください。", "invoice.php", "new"
        email = "billing@invoice-center.example"
    elif idx in att_ids:
        ext = rng.choice(["pdf", "pdf", "png"])
        att = "%04d_%s.%s" % (idx, hashlib.md5(("a%d" % idx).encode()).hexdigest()[:8], ext)
        attachments.append((idx, att, t))
        email = None
    else:
        email = None
    if email is None and cust: email = customers[cust - 1][3]
    upd = t + dt.timedelta(hours=rng.randint(1, 72)) if st != "new" else t
    inquiries.append((idx, cust, email, subj, body, st, att, ts(t), ts(upd)))
# the real file for attack attachment
attachments.append((inquiries[[i for i, r in enumerate(inquiries) if r[6] == "invoice.php"][0]][0], "invoice.php", ATTACK_T))
attack_id = [r[0] for r in inquiries if r[6] == "invoice.php"][0]

# ---------------- app users / tokens ----------------
def fake_hash(name): return "$2y$10$" + hashlib.sha256((name + str(SEED)).encode()).hexdigest()[:53]
TANAKA_TOKEN = "hkapi_tanaka_" + hashlib.sha256(("tok" + str(SEED)).encode()).hexdigest()[:32]
users = [
 (1, "tanaka", "田中 情シス前任", "admin", 1, ts((RETIRE - dt.timedelta(days=1)).replace(hour=18, minute=12, second=5))),
 (2, "sato", "佐藤 総務", "staff", 1, ts((NOW - dt.timedelta(days=1)).replace(hour=8, minute=41, second=10))),
 (3, "suzuki", "鈴木 営業", "staff", 1, ts((NOW - dt.timedelta(days=1)).replace(hour=16, minute=20, second=44))),
 (4, "kobayashi", "小林 営業", "staff", 1, ts((NOW - dt.timedelta(days=2)).replace(hour=11, minute=2, second=19))),
 (5, "yamada", "山田 製造", "staff", 1, ts((NOW - dt.timedelta(days=6)).replace(hour=9, minute=15, second=33))),
]

# ---------------- SQL ----------------
def insert_rows(table, cols, rows, batch=100):
    out = []
    for i in range(0, len(rows), batch):
        vals = ",\n".join("(" + ",".join(q(v) for v in r) + ")" for r in rows[i:i + batch])
        out.append("INSERT INTO `%s` (%s) VALUES\n%s;\n" % (table, ",".join("`%s`" % c for c in cols), vals))
    return "".join(out)

INQ_SCHEMA = """
CREATE TABLE `customers` (
  `id` int NOT NULL, `company` varchar(100) NOT NULL, `contact_name` varchar(60) NOT NULL,
  `email` varchar(120) NOT NULL, `phone` varchar(20) NOT NULL, `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE `inquiries` (
  `id` int NOT NULL, `customer_id` int DEFAULT NULL, `contact_email` varchar(120) DEFAULT NULL,
  `subject` varchar(200) NOT NULL, `body` text NOT NULL, `status` varchar(20) NOT NULL,
  `attachment` varchar(120) DEFAULT NULL, `created_at` datetime NOT NULL, `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`), KEY `idx_created` (`created_at`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE `users` (
  `id` int NOT NULL, `username` varchar(40) NOT NULL, `display_name` varchar(60) NOT NULL,
  `role` varchar(20) NOT NULL, `active` tinyint NOT NULL DEFAULT 1, `last_login` datetime DEFAULT NULL,
  `password_hash` varchar(80) NOT NULL, PRIMARY KEY (`id`), UNIQUE KEY `uk_username` (`username`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE `api_tokens` (
  `token` varchar(64) NOT NULL, `user_id` int NOT NULL, `created_at` datetime NOT NULL,
  `disabled` tinyint NOT NULL DEFAULT 0, PRIMARY KEY (`token`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
def inquiry_sql(until=None):
    rows = [r for r in inquiries if (until is None or r[7] < until)]
    s = INQ_SCHEMA
    s += insert_rows("customers", ["id","company","contact_name","email","phone","created_at"], customers)
    s += insert_rows("inquiries", ["id","customer_id","contact_email","subject","body","status","attachment","created_at","updated_at"], rows)
    s += insert_rows("users", ["id","username","display_name","role","active","last_login","password_hash"], [u + (fake_hash(u[1]),) for u in users])
    s += insert_rows("api_tokens", ["token","user_id","created_at","disabled"], [(TANAKA_TOKEN, 1, "2025-11-04 10:00:00", 0)])
    return s

BOARD_SCHEMA = """
CREATE TABLE `posts` (
  `id` int NOT NULL, `title` varchar(120) NOT NULL, `body` text NOT NULL, `author` varchar(40) NOT NULL,
  `created_at` datetime NOT NULL, PRIMARY KEY (`id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
BT = ["{}月の安全衛生委員会のお知らせ","工場見学の受け入れについて","共有フォルダの整理のお願い","年末年始の稼働日程","駐車場の利用ルール変更","新入社員の紹介","設備点検のため {} 日は停電します","忘年会の出欠確認","健康診断の日程","社内報 vol.{}"]
posts = []
for i in range(1, Y["data"]["board_posts"] + 1):
    t = dt.datetime(2024, 1, 5) + dt.timedelta(days=rng.randint(0, 990), hours=rng.randint(8, 18), minutes=rng.randint(0, 59))
    posts.append((i, rng.choice(BT).format(rng.randint(1, 28)), "社内向けのお知らせです。詳細は総務まで。(%d)" % i, rng.choice(["sato","suzuki","kobayashi","yamada"]), ts(t)))
posts.sort(key=lambda r: r[4]); posts = [(i + 1,) + r[1:] for i, r in enumerate(posts)]
board_sql = BOARD_SCHEMA + insert_rows("posts", ["id","title","body","author","created_at"], posts)

os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "inquiry.sql"), "w", encoding="utf-8").write("SET NAMES utf8mb4;\n" + inquiry_sql())
open(os.path.join(OUT, "board.sql"), "w", encoding="utf-8").write("SET NAMES utf8mb4;\n" + board_sql)

# ---------------- file trees (tar with mtimes) ----------------
class Tree:
    def __init__(self, name): self.name = name; self.files = []   # (path, bytes, mtime(datetime or epoch), mode)
    def add(self, path, data, mtime, mode=0o644):
        if isinstance(data, str): data = data.encode("utf-8")
        self.files.append((path, data, mtime, mode))
    def write(self):
        p = os.path.join(OUT, self.name + ".tar")
        with tarfile.open(p, "w", format=tarfile.GNU_FORMAT) as tf:
            for path, data, mt, mode in self.files:
                ti = tarfile.TarInfo(path); ti.size = len(data); ti.mode = mode; ti.uid = ti.gid = 0
                ti.mtime = int((mt - dt.datetime(1970, 1, 1)).total_seconds()) - 9 * 3600 if isinstance(mt, dt.datetime) else mt
                tf.addfile(ti, io.BytesIO(data))
        return p
web = Tree("web-data"); dbt = Tree("db-data")

# backup.sql (2026-05 snapshot, publicly exposed)
bk = "-- MySQL dump 10.13  Distrib 8.0.28, for Linux (x86_64)\n-- Host: localhost    Database: inquiry\n-- Dump completed on %s 03:30:02\n" % BKDAY.strftime("%Y-%m-%d") + inquiry_sql(until=(BKDAY + dt.timedelta(days=1)).strftime("%Y-%m-%d"))
web.add("var/www/inquiry/public/backup.sql", bk, BKDAY.replace(hour=3, minute=30, second=2))
BACKUP_SIZE = len(bk.encode("utf-8"))

# attachments (random bytes, fixed by seed)
arng = random.Random(SEED + 1)
for (iid, name, t) in attachments:
    if name == "invoice.php":
        web.add("var/www/inquiry/public/uploads/invoice.php", "<?php echo 'ok'; ?>\n", dt.datetime(2025, 3, 14, 10, 22, 7))   # mtime tampered (2025)
    else:
        n = arng.randint(2048, 20480)
        magic = b"%PDF-1.4\n" if name.endswith("pdf") else b"\x89PNG\r\n\x1a\n"
        web.add("var/www/inquiry/public/uploads/" + name, magic + bytes(arng.getrandbits(8) for _ in range(n)), t + dt.timedelta(seconds=30))

# ---------------- nginx access logs ----------------
lrng = random.Random(SEED + 2)
OFFICE = ["192.0.2.%d" % i for i in range(10, 22)]
EXT = ["198.18.%d.%d" % (lrng.randint(0, 255), lrng.randint(1, 254)) for _ in range(40)]
UA = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"]
BOT_UA = "Mozilla/5.0 (compatible; scanbot/2.1; +http://scanner.example/bot)"
def line(t, ip, req, st, size, ref="-", ua=None, host="inquiry." + DOMAIN):
    return '%s - - [%s %s] "%s" %d %d "%s" "%s" "%s"' % (ip, t.strftime("%d/%b/%Y:%H:%M:%S"), JST, req, st, size, ref, ua or UA[0], host)
LOGSTART = R0 - dt.timedelta(days=28)
entries = []   # (datetime, line)
day = LOGSTART.replace(hour=0, minute=0)
while day <= NOW.replace(hour=0, minute=0):
    weekday = day.weekday() < 5
    nreq = lrng.randint(520, 760) if weekday else lrng.randint(60, 140)
    for _ in range(nreq):
        h = lrng.choice([8,9,9,10,10,10,11,11,13,13,14,14,14,15,15,16,16,17]) if weekday else lrng.randint(9, 17)
        t = day.replace(hour=h, minute=lrng.randint(0, 59), second=lrng.randint(0, 59))
        ip = lrng.choice(OFFICE); ua = lrng.choice(UA)
        r = lrng.random()
        if r < 0.28: req, size = "GET /list.php?page=%d HTTP/1.1" % lrng.randint(1, 60), lrng.randint(14000, 19000)
        elif r < 0.45: req, size = "GET /detail.php?id=%d HTTP/1.1" % lrng.randint(1, 3000), lrng.randint(2400, 3600)
        elif r < 0.60: req, size = "GET /search.php?q=%s HTTP/1.1" % lrng.choice(["%E8%A6%8B%E7%A9%8D","%E7%B4%8D%E6%9C%9F","SUS304","%E5%9B%B3%E9%9D%A2","%E8%AB%8B%E6%B1%82%E6%9B%B8"]), lrng.randint(3000, 90000)
        elif r < 0.70: req, size = "GET / HTTP/1.1", 5120
        elif r < 0.78: req, size = "GET /report.php HTTP/1.1", 7900
        elif r < 0.83: req, size = "POST /submit.php HTTP/1.1", 0; 
        elif r < 0.90: req, size = "GET /static/app.css HTTP/1.1", 2210
        else: req, size = "GET /board/ HTTP/1.1", 6100
        host = "inquiry." + DOMAIN
        if req.startswith("GET /board"): host, req = "board." + DOMAIN, "GET / HTTP/1.1"
        st = 302 if req.startswith("POST") else 200
        if req.startswith("POST"): ip = lrng.choice(EXT); ua = lrng.choice(UA)
        entries.append((t, line(t, ip, req, st, size, ua=ua, host=host)))
    # background scanner noise (404s) - not an attack that mattered
    for _ in range(lrng.randint(2, 6)):
        t = day.replace(hour=lrng.randint(0, 23), minute=lrng.randint(0, 59), second=lrng.randint(0, 59))
        entries.append((t, line(t, "198.18.%d.%d" % (lrng.randint(0, 255), lrng.randint(1, 254)), "GET %s HTTP/1.1" % lrng.choice(["/wp-login.php","/phpmyadmin/","/.env","/xmlrpc.php","/admin/"]), 404, 162, ua=BOT_UA)))
    day += dt.timedelta(days=1)
# intrusion (YAML intrusion.timeline_jst) -- sizes are real (backup.sql) / plausible
A1, A2 = "203.0.113.45", "198.51.100.7"
def at(s): return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
FC1, FC2, FC3 = rel(-9, "02:12:08"), rel(-9, "02:12:31"), rel(-9, "02:14:02")      # first contact: R0 date - 9 days
entries += [(FC1, line(FC1, A1, "GET /.git/HEAD HTTP/1.1", 200, 23, ua="curl/7.88.1")),
            (FC2, line(FC2, A1, "GET /.git/config HTTP/1.1", 200, 261, ua="curl/7.88.1")),
            (FC3, line(FC3, A1, "GET /backup.sql HTTP/1.1", 200, BACKUP_SIZE, ua="curl/7.88.1"))]
for k in range(30):
    t = rel(-7, "23:41:00") + dt.timedelta(seconds=14 * k + lrng.randint(0, 6))
    pay = lrng.choice(["%27%29+OR+1%3D1--+", "%27+OR+%271%27%3D%271", "%25%27%29+OR+%28%271%27%3D%271", "%27%29+OR+1%3D1%23"])
    entries.append((t, line(t, A2, "GET /search.php?q=%s HTTP/1.1" % pay, 200, lrng.randint(900000, 1100000), ua="sqlmap/1.7.2#stable (https://sqlmap.org)")))
entries.append((ATTACK_T, line(ATTACK_T, A2, "POST /submit.php HTTP/1.1", 302, 0, ua="python-requests/2.31.0")))
exec_times = [rel(d_, h_) for d_, h_ in [(-6,"00:05:12"),(-6,"00:05:40"),(-6,"03:12:55"),(-5,"01:47:03"),(-5,"22:30:18"),(-4,"04:02:44"),(-3,"00:19:09"),(-3,"23:58:31"),(-2,"02:41:27"),(-2,"21:07:50"),(-1,"00:33:12"),(-1,"05:18:36"),(0,"13:22:08"),(0,"15:04:51")]]
for e in exec_times:
    entries.append((e, line(e, A2, "GET /uploads/invoice.php?c=id HTTP/1.1", 200, 2, ua="python-requests/2.31.0")))
entries = [x for x in entries if x[0] <= NOW]
entries.sort(key=lambda x: x[0])
# logrotate: weekly Sunday 06:25, rotate 4. R0 = the most recent Sunday 06:25.
rot = [R0 - dt.timedelta(days=28 - 7 * i) for i in range(5)]
def seg(a, b): return "\n".join(l for t, l in entries if (a is None or t >= a) and (b is None or t < b)) + "\n"
cur = seg(rot[4], None); r1 = seg(rot[3], rot[4]); r2 = seg(rot[2], rot[3]); r3 = seg(rot[1], rot[2]); r4 = seg(rot[0], rot[1])
web.add("var/log/nginx/access.log", cur, NOW - dt.timedelta(minutes=1), 0o640)
web.add("var/log/nginx/access.log.1", r1, rot[4], 0o640)
def gz(s): 
    b = io.BytesIO(); 
    with gzip.GzipFile(fileobj=b, mode="wb", mtime=0) as g: g.write(s.encode())
    return b.getvalue()
web.add("var/log/nginx/access.log.2.gz", gz(r2), rot[3], 0o640)
web.add("var/log/nginx/access.log.3.gz", gz(r3), rot[2], 0o640)
web.add("var/log/nginx/access.log.4.gz", gz(r4), rot[1], 0o640)
web.add("var/log/nginx/error.log", "", (NOW - dt.timedelta(days=1)).replace(hour=3, minute=0, second=0), 0o640)
web.add("var/lib/logrotate/status", "logrotate state -- version 2\n" + "".join('"/var/log/nginx/access.log" %s\n' % "%d-%d-%d-6:25:02" % (R0.year, R0.month, R0.day)) + '"/var/log/nginx/error.log" %s\n' % "%d-%d-%d-6:25:02" % (R0.year, R0.month, R0.day) + '"/var/log/php8.1-fpm.log" %s\n' % "%d-%d-%d-6:25:02" % (R0.year, R0.month, R0.day), rot[4])
# php-fpm log: invoice.php executions
fpm = "".join("[%s] NOTICE: [pool www] script '/var/www/inquiry/public/uploads/invoice.php' executed pid=%d\n" % (e.strftime("%d-%b-%Y %H:%M:%S"), 1200 + i * 7) for i, e in enumerate(exec_times))
fpm = "[%s] NOTICE: [pool www] child 1188 started\n" % (LOGSTART + dt.timedelta(days=2)).strftime("%d-%b-%Y 03:00:01") + fpm
web.add("var/log/php8.1-fpm.log", fpm, exec_times[-1], 0o640)
# syslog: cron records (used to cross-check logrotate/mysqldump times)
def cronlines(host, items):
    L = []
    d = LOGSTART.replace(hour=0, minute=0)
    while d <= NOW.replace(hour=0, minute=0):
        for (h, m, user, cmd, only_sun) in items:
            if only_sun and d.weekday() != 6: continue
            t = d.replace(hour=h, minute=m, second=lrng.randint(0, 5))
            if t <= NOW: L.append((t, "%s %s CRON[%d]: (%s) CMD (%s)" % (t.strftime("%b %e %H:%M:%S"), host, lrng.randint(1000, 30000), user, cmd)))
        d += dt.timedelta(days=1)
    return L
web_items = [(2, 30, "root", "/opt/hk-tools/nightly_summary.sh", False), (6, 25, "root", "test -x /usr/sbin/logrotate && /usr/sbin/logrotate /etc/logrotate.conf", True)]
wl = cronlines("hk-web01", web_items)
d = LOGSTART.replace(hour=0, minute=0)
while d <= NOW.replace(hour=0, minute=0):
    for h in range(24):
        t = d.replace(hour=h, minute=15, second=lrng.randint(0, 4))
        if t <= NOW: wl.append((t, "%s hk-web01 CRON[%d]: (root) CMD (rsync -a --delete /srv/golden/inquiry/ /var/www/inquiry/)" % (t.strftime("%b %e %H:%M:%S"), lrng.randint(1000, 30000))))
    d += dt.timedelta(days=1)
wl.sort(key=lambda x: x[0])
web.add("var/log/syslog", "\n".join(l for t, l in wl) + "\n", wl[-1][0] + dt.timedelta(seconds=3), 0o640)
dl = cronlines("hk-db01", [(3, 30, "root", "/usr/local/bin/hk-dbdump.sh", False)]); dl.sort(key=lambda x: x[0])
dbt.add("var/log/syslog", "\n".join(l for t, l in dl) + "\n", dl[-1][0] + dt.timedelta(seconds=3), 0o640)

# nightly summary mails in sato's home (evidence of live_batch_trap)
for k in range(Y["data"]["nightly_summary_mails"]):
    d = (NOW.date() - dt.timedelta(days=k + 1))
    t = dt.datetime(d.year, d.month, d.day, 2, 30, 7)
    n = lrng.randint(1, 9)
    web.add("home/sato/Mail/inbox/summary-%s.txt" % d.isoformat(),
            "From: hk-nightly@hk-web01.%s\nTo: sato@%s\nDate: %s %s\nSubject: [hk-nightly] 問い合わせ日次集計 %s\n\n前日の新規問い合わせ: %d 件\n未対応: %d 件\n" % (DOMAIN, DOMAIN, t.strftime("%a, %d %b %Y %H:%M:%S"), JST, d.isoformat(), n, lrng.randint(3, 40)), t + dt.timedelta(seconds=3))
# db dumps (world readable, plant dump_world_readable). v1.2 (hk-dbdump.sh is a real script): weekdays go to /var/backups/mysql (the only path with -mtime +7 -delete),
# Sat/Sun go to /mnt/backup/mysql (never mounted: the files sit on the root disk, nothing rotates them). Every dump is cut by `head -c $MAX_BYTES` (silent truncation).
def gzb(b):
    bio = io.BytesIO()
    with gzip.GzipFile(fileobj=bio, mode="wb", mtime=0) as g: g.write(b)
    return bio.getvalue()
_sql = inquiry_sql()
TRUNC_CUT = 4096                                   # bytes missing at the end of every dump (ends inside the last INSERT of `inquiries`)
for k in range(0, 8 * 7):
    d = NOW.date() - dt.timedelta(days=k)
    t = dt.datetime(d.year, d.month, d.day, 3, 30, 2)
    if t > NOW: continue
    weekend = d.weekday() >= 5
    if not weekend and k >= 7: continue            # weekday dumps older than 7 days were deleted by the script; weekend ones never are
    full = ("-- dump %s\n" % d.isoformat() + _sql).encode("utf-8")
    path = ("mnt/backup/mysql/" if weekend else "var/backups/mysql/") + "inquiry-%s.sql.gz" % d.strftime("%Y%m%d")
    dbt.add(path, gzb(full[:len(full) - TRUNC_CUT]), t + dt.timedelta(seconds=9), 0o644)

# ---------------- v1.2: auth.log (web, db), tanaka's shell history on db ----------------
import base64
def ssh_fp(pubfile):
    blob = base64.b64decode(open(pubfile).read().split()[1]); return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
_AF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ansible", "files")
FP_TANAKA, FP_BACKUP = ssh_fp(os.path.join(_AF, "tanaka.pub")), ssh_fp(os.path.join(_AF, "hkbackup.pub"))
UID_TANAKA, UID_HKB = 1002, 1004
WEB_IP = os.environ.get("BENCH_WEB_IP", "10.92.0.11")
arng2 = random.Random(SEED + 3)
SCAN_IPS = ["203.0.113.91", "203.0.113.133", "198.51.100.23", "198.51.100.144", "198.18.77.12", "198.18.201.64", "198.18.5.150", "198.18.130.9"]
SCAN_USERS = ["admin", "root", "ubuntu", "test", "oracle", "postgres", "user", "pi", "git", "deploy", "tanaka", "sato", "mysql", "www-data"]
NAS_IP, NAS_PULL = "192.0.2.40", (3, 45)
def aline(host, t, proc, msg, pid=None): return (t, "%s %s %s[%d]: %s" % (t.strftime("%b %e %H:%M:%S"), host, proc, pid or arng2.randint(900, 32000), msg))
def scan_events(host):
    ev = []; d = LOGSTART.replace(hour=0, minute=0)
    while d <= NOW.replace(hour=0, minute=0):
        for _ in range(arng2.randint(1, 3)):
            ip = arng2.choice(SCAN_IPS); t = d.replace(hour=arng2.randint(0, 23), minute=arng2.randint(0, 59), second=arng2.randint(0, 59))
            for _ in range(arng2.randint(4, 14)):
                u = arng2.choice(SCAN_USERS); port = arng2.randint(30000, 65000); t += dt.timedelta(seconds=arng2.randint(1, 3)); pid = arng2.randint(900, 32000)
                if u in ("root", "tanaka", "sato", "www-data", "mysql"):
                    ev.append(aline(host, t, "sshd", "Failed password for %s from %s port %d ssh2" % (u, ip, port), pid=pid))
                else:
                    ev.append(aline(host, t, "sshd", "Invalid user %s from %s port %d" % (u, ip, port), pid=pid))
                    ev.append(aline(host, t, "sshd", "Failed password for invalid user %s from %s port %d ssh2" % (u, ip, port), pid=pid))
                ev.append(aline(host, t, "sshd", "Connection closed by %s user %s %s port %d [preauth]" % ("authenticating" if u in ("root", "tanaka", "sato", "www-data", "mysql") else "invalid", u, ip, port), pid=pid))
        d += dt.timedelta(days=1)
    return ev
def nas_events(host):
    ev = []; d = LOGSTART.replace(hour=0, minute=0)
    while d <= NOW.replace(hour=0, minute=0):
        t = d.replace(hour=NAS_PULL[0], minute=NAS_PULL[1], second=arng2.randint(0, 5)); port = arng2.randint(30000, 65000); sp = arng2.randint(900, 32000)
        if t <= NOW:
            ev.append(aline(host, t, "sshd", "Accepted publickey for hkbackup from %s port %d ssh2: ED25519 %s" % (NAS_IP, port, FP_BACKUP), pid=sp))
            ev.append(aline(host, t, "sshd", "pam_unix(sshd:session): session opened for user hkbackup(uid=%d) by (uid=0)" % UID_HKB, pid=sp))
            t2 = t + dt.timedelta(seconds=arng2.randint(20, 40))
            ev.append(aline(host, t2, "sshd", "pam_unix(sshd:session): session closed for user hkbackup", pid=sp))
        d += dt.timedelta(days=1)
    return ev
LAT = [(-5, "01:47:40", ["id", "sudo mysql -e 'show databases'", "sudo mysql inquiry -e 'select count(*) from inquiries'"]),
       (-3, "00:21:55", ["ls -la /var/backups/mysql", "sudo mysqldump --single-transaction inquiry"]),
       (-2, "02:44:10", ["sudo mysql -e 'select user,host from mysql.user'"]),
       (-1, "00:41:20", ["sudo mysql board -e 'select * from posts limit 5'", "exit"])]
def lateral_events(host):
    ev = []; hist = []
    for (dd, hms, cmds) in LAT:
        t = rel(dd, hms)
        if t > NOW: continue
        port = arng2.randint(30000, 65000); sp = arng2.randint(900, 32000)
        ev.append(aline(host, t, "sshd", "Accepted publickey for tanaka from %s port %d ssh2: ED25519 %s" % (WEB_IP, port, FP_TANAKA), pid=sp))
        ev.append(aline(host, t, "sshd", "pam_unix(sshd:session): session opened for user tanaka(uid=%d) by (uid=0)" % UID_TANAKA, pid=sp))
        tt = t
        for c in cmds:
            hist.append(c)
            if c.startswith("sudo "):
                tt += dt.timedelta(seconds=arng2.randint(6, 25))
                real = c[5:].replace("mysql ", "/usr/bin/mysql ", 1) if c[5:].startswith("mysql ") else c[5:].replace("mysqldump ", "/usr/bin/mysqldump ", 1)
                ev.append(aline(host, tt, "sudo", "  tanaka : TTY=pts/0 ; PWD=/home/tanaka ; USER=root ; COMMAND=%s" % real.replace("'", "")))
                ev.append(aline(host, tt, "sudo", "pam_unix(sudo:session): session opened for user root(uid=0) by tanaka(uid=%d)" % UID_TANAKA))
                ev.append(aline(host, tt + dt.timedelta(seconds=2), "sudo", "pam_unix(sudo:session): session closed for user root"))
        ev.append(aline(host, tt + dt.timedelta(seconds=arng2.randint(5, 30)), "sshd", "pam_unix(sshd:session): session closed for user tanaka", pid=sp))
        last = tt
    return ev, hist, last
def add_rotated(tree, base, events):
    events = sorted([e for e in events if e[0] <= NOW], key=lambda x: x[0])
    def seg2(a, b): return "".join(l + "\n" for t, l in events if (a is None or t >= a) and (b is None or t < b))
    tree.add(base, seg2(rot[4], None), events[-1][0] + dt.timedelta(seconds=1), 0o640)
    tree.add(base + ".1", seg2(rot[3], rot[4]), rot[4], 0o640)
    tree.add(base + ".2.gz", gz(seg2(rot[2], rot[3])), rot[3], 0o640); tree.add(base + ".3.gz", gz(seg2(rot[1], rot[2])), rot[2], 0o640); tree.add(base + ".4.gz", gz(seg2(rot[0], rot[1])), rot[1], 0o640)
add_rotated(web, "var/log/auth.log", scan_events("hk-web01"))
lat_ev, lat_hist, lat_last = lateral_events("hk-db01")
add_rotated(dbt, "var/log/auth.log", nas_events("hk-db01") + lat_ev)
dbt.add("home/tanaka/.bash_history", "".join(c + "\n" for c in lat_hist), lat_last + dt.timedelta(seconds=20), 0o600)

web.write(); dbt.write()

meta = {"seed": SEED, "customers": len(customers), "inquiries": len(inquiries), "attachments": len(attachments), "board_posts": len(posts),
        "attack_inquiry_id": attack_id, "backup_sql_bytes": BACKUP_SIZE, "tanaka_token": TANAKA_TOKEN,
        "access_log_lines": len(entries), "intrusion_exec_count": len(exec_times),
        "now": NOW.strftime("%Y-%m-%d %H:%M"), "r0_rotation": R0.strftime("%Y-%m-%d %H:%M"), "retire_date": RETIRE.strftime("%Y-%m-%d"), "backup_snapshot_day": BKDAY.strftime("%Y-%m-%d"),
        "lateral": {"first": rel(-5, "01:47:40").strftime("%Y-%m-%d %H:%M:%S"), "last": lat_last.strftime("%Y-%m-%d %H:%M:%S"), "src": WEB_IP, "user": "tanaka", "key_fp": FP_TANAKA, "logins": len([1 for t, l in lat_ev if "Accepted publickey for tanaka" in l])},
        "scan": {"ips": SCAN_IPS, "since": LOGSTART.strftime("%Y-%m-%d")}, "backup_pull": {"user": "hkbackup", "src": NAS_IP, "time": "%02d:%02d" % NAS_PULL, "key_fp": FP_BACKUP},
        "timeline": {"first_contact": FC1.strftime("%Y-%m-%d %H:%M:%S"), "first_contact_ip": A1, "foothold_post": ATTACK_T.strftime("%Y-%m-%d %H:%M:%S"), "foothold_ip": A2, "first_exec": exec_times[0].strftime("%Y-%m-%d %H:%M:%S"), "last_exec": exec_times[-1].strftime("%Y-%m-%d %H:%M:%S"), "sqli_start": rel(-7, "23:41:00").strftime("%Y-%m-%d %H:%M:%S"), "mysqldump_not_attack": R0D.strftime("%Y-%m-%d") + " 03:30"}}
json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(meta, ensure_ascii=False))
