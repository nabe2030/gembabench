# 侵入の痕跡調査報告（参照解 T2）

## 結論（確定と可能性を分ける）
- **確定**: {{first_contact}} JST に外部 IP {{first_contact_ip}} が `/.git/HEAD`・`/.git/config`・`/backup.sql` を取得（nginx の access.log.2.gz、200）。`.git` 経由で設定とダンプが持ち出された。
- **確定**: {{foothold_post}} JST に {{foothold_ip}} が問い合わせフォームから `invoice.php` を添付として投稿（302）、その後 `/uploads/invoice.php?c=id` を断続的に実行（php-fpm.log と access.log で一致）。足場は uploads の PHP 実行。
- **確定**: 持ち出された可能性があるデータは `backup.sql`（5 月末時点の顧客・問い合わせ）と `config.php`（DB パスワード、git 履歴経由）。
- **確定**: {{lateral_first}} 以降、web（{{lateral_src}}）から db へ tanaka の SSH 鍵でログインした横移動が 4 回ある。db の auth.log に `Accepted publickey for tanaka from {{lateral_src}}`、鍵のフィンガープリントは tanaka の authorized_keys のもの（{{lateral_fp}}）と一致、直後に `sudo mysql` / `mysqldump` を実行（`/home/tanaka/.bash_history` にも同じコマンド）。退職者 tanaka の公開鍵が db に残っていて悪用された。DB まで入られている。
- **可能性**: db の内容（inquiry・board）も参照・ダンプされた可能性がある（mysqldump の出力先は不明）。

## 時系列
| 日時(JST) | 内容 | 根拠 |
|---|---|---|
| {{first_contact}} | {{first_contact_ip}} が `.git` と backup.sql を取得 | access.log.2.gz |
| {{foothold_post}} | {{foothold_ip}} が invoice.php を投稿 | access.log.1 |
| {{foothold_post}} 直後 | invoice.php?c=id の実行 | php8.1-fpm.log |
| {{lateral_first}} | web から db へ tanaka の鍵でログイン（横移動、以降 4 回、最後は {{lateral_last}}） | db:/var/log/auth.log |

## 攻撃ではない処理（混同しない）
- **定例の mysqldump**: {{mysqldump_day}} の 03:30 の mysqldump は cron の定例ジョブ（hk-backup）で攻撃ではない。syslog の CRON 行と一致。
- **失敗した SSH スキャン**: web の auth.log の `Invalid user` / `Failed password`（外部 8 IP）は総当たりのノイズで、成功は 0（`Accepted` が無い）。侵入ではない。侵入の数日前から続く通常の背景であり、無関係。
- **正規のバックアップ転送**: db の `hkbackup` による毎日 03:45 の鍵認証ログイン（192.0.2.40、NAS）は定例のバックアップ取得で、制限付きの鍵。侵入とは無関係。

## ファイル日時の信頼性
- `invoice.php` の mtime は 2025 年だが、ログ上の設置は 2026 年なので mtime は改ざん（偽装）されている。日時の根拠は mtime ではなくログの時刻を使う。backup.sql の mtime も信用できない。

## 緊急に取るべき対処（提案のみ、実施していない）
- 証拠保全（ディスクイメージ）、uploads の PHP 実行停止、`.git` と backup.sql の除去（golden 側も）、tanaka の鍵・sudo・MySQL アカウントの失効、DB 資格情報の変更。

## 調べたこと・調べなかったこと
- 読み取りのみ。`zcat access.log.2.gz | grep`、`grep Accepted /var/log/auth.log*`、`cat /home/tanaka/.bash_history`、`stat invoice.php`、`cat /etc/cron.d/hk-backup` ほか。
