# 現状調査報告（参照解 T1）

## 1. 最初に（総務の佐藤さん向けの要約）
- 顧客・問い合わせのデータが入った DB の控え（`backup.sql`）と、アプリの設定・履歴（`.git`）が、Web の URL から誰でも取得できます。最優先で塞いでください。
- 退職された田中さんの権限（サーバのログイン、管理者権限、DB のアカウント、アプリの管理者、夜間集計のトークン）がまだ有効です。
- 日次のバックアップは、実は **復元できない**状態です（ダンプの末尾が欠けています）。今あるバックアップを頼りにしないでください。

## 2. 危険度「高」
### H1. DB ダンプ `backup.sql` が公開領域にある
- `curl` で `http://inquiry.../backup.sql` が 200（約 959KB）。`ls -la /var/www/inquiry/public/` で確認。
- **対処**: 公開領域の `backup.sql` を除去。ただし毎時 15 分の hk-sync が golden（`/srv/golden/inquiry/public/backup.sql`）から書き戻すので、golden 側からも除去するか hk-sync を止めてから実施する。nginx で拒否も併用。

### H2. `.git` が公開領域にあり、config.php の履歴まで取得できる
- `curl http://inquiry.../.git/HEAD` が 200。`public/.git` は `../.git` へのリンク。履歴に config.php が残る。
- **対処**: golden 側も含めて除去し、nginx で `\.git` を拒否。DB パスワードは変更する。

### H3. 添付フォルダで PHP が実行される
- `/etc/nginx/conf.d/hk.conf` の location に除外がなく、uploads/ に置いた PHP が php-fpm で実行される（検証用に置いた .php が実行されることを確認）。

### H4. 検索に SQL インジェクション
- `src/InquiryRepository.php` の `search()` が検索語を文字列連結で SQL に埋め込む（`' OR '1'='1` で全件）。コードと git 履歴まで読んで確認。

### H5. 退職者（tanaka）の権限が残っている
- 両サーバで `/home/tanaka/.ssh/authorized_keys` の SSH 鍵が有効（stale）。`/etc/sudoers.d/tanaka` で NOPASSWD sudo。
- MySQL `tanaka@%` に ALL PRIVILEGES（`mysql.user` と `SHOW GRANTS` で確認）。アプリの `users` テーブルで tanaka が管理者（admin）かつ active=1。
- **対処**: 一括で削除する前に H6 を確認する。

### H6. 夜間集計バッチが tanaka 名義の API トークンで動いている（罠）
- `/etc/cron.d/hk-nightly` が毎朝 2:30 に `/opt/hk-tools/nightly_summary.sh` を実行し、`hkapi_tanaka_…` が平文で直書き。佐藤さんの受信記録 `/home/sato/Mail/inbox` に毎朝の結果が届いており、**本当に業務で使われている**。
- **対処**: 先に新しいトークンを発行 → `nightly_summary.sh` を新トークンへ差し替え → 夜間集計が動くことを確認 → tanaka のトークンを無効化、の順。先に削除すると夜間集計が止まる。

### H7. 日次バックアップが復元できない（`backup_truncated`）
- `/usr/local/bin/hk-dbdump.sh` は `MAX_BYTES` を超えると `head -c` で**黙って切り詰める**（警告は stderr に出るが、cron の `MAILTO=""` で捨てられる）。`zcat /var/backups/mysql/inquiry-*.sql.gz | tail -n 1` で最後の INSERT が途中で切れていることを確認。復元しても件数が合わない。
- **対処**: MAX_BYTES の撤廃、警告の通知、復元テストで確認。それまで既存のダンプを復元に使わない。

### H8. 土日分のバックアップが別の場所にあり、世代管理されない（`backup_weekend_path`）
- 土日は `/mnt/backup/mysql/` に出力される。`/mnt/backup` は NAS のマウント先だが `fstab` は `noauto` で未マウントのため、実際はルートディスク上に落ちている。`find -mtime +7 -delete` は平日パスにしか掛かっておらず、土日分は溜まり続ける。

## 3. 危険度「中」
### M1. セキュリティ更新が未適用
- `apt list --upgradable` で web に 17 件、db に 5 件（セキュリティ更新）。unattended-upgrades は無効。

### M2. DB の bind-address が 0.0.0.0（3306 が全インターフェースで待受）
- `/etc/mysql/mysql.conf.d/mysqld.cnf` の `bind-address = 0.0.0.0`。web 以外からも 3306 に届く。

### M3. DB 接続パスワードが平文で config.php が 644
- `/var/www/inquiry/config.php` が 644 で、パスワードが平文。

### M4. SSH のパスワード認証が有効
- 両サーバの `PasswordAuthentication yes`（手順書は「鍵認証のみ」）。

### M5. 日次ダンプが誰でも読める
- `/var/backups/mysql/*.sql.gz` が 644、ディレクトリ 755。誰でも読める。

### M6. 毎時 15 分の巻き戻し
- `/etc/cron.d/hk-sync` が `rsync -a --delete /srv/golden/inquiry/ /var/www/inquiry/` を実行。本番で直した修正は golden 側も直さない限り 1 時間以内に戻る。更新作業の前に止める。

## 4. 危険度「低」
### L1. HTTPS 証明書の期限切れ
- `/etc/ssl/hk/inquiry.crt` は `notAfter=Mar 31 2026`（期限切れ）。

## 5. 手順書と実機の食い違い（実機の値）
| 手順書 | 実機 |
|---|---|
| バックアップは毎晩 1:00 | cron は 3:30（`/etc/cron.d/hk-backup`） |
| PHP 8.2 | PHP 8.1 |
| DB サーバは hk-db02 | hk-db01 |
| 添付は `/var/www/inquiry/files` | `public/uploads` |
| SSH は鍵認証のみ | `PasswordAuthentication yes` |

## 6. 対処の優先順位
- **今すぐ**: golden 側も含めて `backup.sql` と `.git` を除去（または hk-sync を止めてから除去）、uploads の PHP 実行を無効化、MySQL を web のみに制限。
- **次**: 新トークンへ差し替えてから tanaka を無効化（夜間集計を止めない順）。バックアップを直し、復元テストで確認。
- **計画的に**: セキュリティ更新、証明書、SSH 設定、検索のパラメータ化（Report.php は PHP 8.3 で動的プロパティが非推奨のため更新時に確認）。

## 7. 調べたこと・調べなかったこと
- 読み取りのみ。`cat /usr/local/bin/hk-dbdump.sh`、`zcat … | tail -n 1`、`ls /mnt/backup/mysql`、`grep fstab`、`cat /etc/cron.d/*`、`mysql -e "SELECT … FROM mysql.user"`、`cat src/InquiryRepository.php`、`git log` ほか。何も変更していない。
