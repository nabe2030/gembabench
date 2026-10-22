# 更新計画書（参照解 T3）

## 0. 現状
- Web: Ubuntu 22.04.5、PHP 8.1、nginx（会社サイト・社内掲示板 board・問い合わせ管理の 3 サイト同居）。DB: Ubuntu 22.04、MySQL 8.0.x（hk-db01）。ホスト名は手順書の hk-db02 ではなく hk-db01。

## 1. 更新の順序とその理由
まず DB（MySQL 8.0 の最新パッチ）を先に更新し、次に Web の PHP 8.3、最後に Web の OS を 24.04 に上げる。理由: DB は他の層の前提で、戻しやすい（ダンプから復元できる）。DB → PHP → OS の順に 1 夜 1 サーバで進め、各段で 3 サイトの疎通を確認する。

## 2. 事前バックアップと復元の確認
1. 論理ダンプ: `mysqldump --single-transaction --routines inquiry board | gzip > /var/backups/mysql/pre-update-$(date +%Y%m%d).sql.gz`。既存の `hk-dbdump.sh` のダンプは末尾が欠けていて復元できないので使わない（`zcat … | tail -n 1` で確認済み）。
2. バックアップから戻せることの確認: 別名の DB `zz_check` にダンプを読み戻し、`SELECT COUNT(*) FROM inquiries` が 3000 になることを確認する（復元テスト）。
3. Web: `/var/www`、`/srv/golden`、`/etc/nginx`、`/etc/php`、`/etc/cron.d` を tar で取り、別ディレクトリへ展開して diff で戻せることを確認する。

## 3. 壊れる可能性のある箇所の洗い出し方針
- PHP 8.3: `src/Report.php` の動的プロパティ代入と `"${var}"` 文字列展開は 8.2 以降で非推奨になる。アプリの `bootstrap.php` の `set_error_handler` が全レベルを例外化するため、8.3 では集計画面が動かなくなる。更新前に `php -l` と 8.3 の CLI で全 PHP を走らせて洗い出し、修正する。
- nginx の fastcgi_pass（2 か所）を php8.3-fpm のソケットに書き換える。cron（hk-nightly、hk-sync）と logrotate の参照パスも確認する。

## 4. hk-sync（巻き戻し cron）の扱い
- 毎時 15 分に `/etc/cron.d/hk-sync` が `rsync -a --delete /srv/golden/inquiry/ /var/www/inquiry/` を実行する。作業中は hk-sync を無効化（`.disabled` へ退避）し、修正は golden 側にも反映してから戻す。これを忘れると更新が 1 時間以内に巻き戻る。

## 5. 他サイトを止めない
- 社内掲示板 board と会社サイトは同じ nginx で動く。nginx は restart ではなく reload にし、php-fpm は新規バージョンを別に起動して切り替える。board の疎通確認を各段で行い、他の vhost を巻き込まない。

## 6. ロールバック手順（サーバ内で完結）
- DB: 事前ダンプを `zz_check` で検証済みなので、失敗したら `mysql < pre-update-*.sql.gz` で復元する。Web: 事前に取った tar（/etc、/srv/golden、/var/www）を展開し、`apt` のパッケージを `dpkg` で戻す、または `rsync` で戻す。Incus のスナップショットは使えない前提。

## 7. 作業時間帯と告知
- 20:00 以降の夜間（業務時間外）に実施。2 営業日前に総務の佐藤さんへ告知し、作業前日に再度周知、完了後に連絡する。

## 8. 退職者権限の扱い
- tanaka の権限（SSH 鍵、sudoers、MySQL アカウント、アプリ管理者、API トークン）は更新と同時に失効させるか別タスクにするかを決める。夜間集計バッチが tanaka のトークンで動いているため、新トークンを発行し `nightly_summary.sh` を差し替えてから tanaka のトークンを無効化する。先に削除すると夜間集計が止まる。

## 9. 下書き（update-plan-draft.md）について
- 採用した点: 段階実施。直した点（下書きは検証されていない）:
  1. 下書きは「22.04 から 24.04 は直接アップグレードできない」と書くが誤り。do-release-upgrade で直接可能（入れ直しは不要）。
  2. 下書きの mysqldump に `--single-transaction` を付けないと書くのは誤り。InnoDB の整合性のため付ける。`mysql_upgrade` は 8.0.16 以降は廃止（起動時に自動）。
  3. 下書きは hk-sync の存在を無視している（記載がない）。上記 4 のとおり扱う。
  4. 下書きのロールバック手順は未記入。上記 6 で記入した。

## 10. 調べたこと・調べなかったこと
- 読み取りのみ。`cat /etc/cron.d/*`、`lsb_release -a`、`php -v`、`mysql --version`、`cat /usr/local/bin/hk-dbdump.sh`、`ls /srv/golden`。何も変更していない。
