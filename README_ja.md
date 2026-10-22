# GembaBench v0.1

**GembaBench は、AI エージェントが企業のサーバの「現場の仕事」をこなせるかを測るベンチマークです。** きちんと文書化されていないシステムの現状を調べる、侵入の痕跡を探す、更新を計画して実施する、設定と脆弱性を直す。これらを、外部の技術者と同じように ssh で実物の（コンテナの）サーバに入って行います。

Aider Polyglot や SWE-bench は、モデルがコードを読み書きする力を測ります。GembaBench が測るのは運用の側です。エージェントは課題文と古くなった運用手順書を受け取り、小さな会社の Web サーバと DB サーバに入ります。そして、実際に何があるかを確かめ、何をしてよいかを判断し、作業し、正直に報告しなければなりません。

> [!WARNING]
> **テスト環境は、意図的に脆弱に作ってあります。** SQL インジェクションのある Web アプリ、仕込まれた Web シェル、漏れた認証情報、退職者の生きている鍵などが入っています。それを見つけて直すのが課題です。**必ず隔離したネットワークの中で動かし、インターネットや社内 LAN に出さないでください。** 公開した測定で使った隔離の例を `network/` に置いてあります。

## このリポジトリにあるもの

| パス | 中身 |
|---|---|
| `scenario-01/` | シナリオ s01「中小製造業の問い合わせ管理システム（Web＋DB）」。<br>`scenario.yaml`: 環境、仕込んだ問題、侵入の時系列、**正解**<br>`tasks/`: 課題文<br>`docs/`: エージェントに渡す資料<br>`app/`・`site/`: 会社の PHP アプリとサイト<br>`gen/`: データの生成器<br>`ref/`: 参照解<br>組み立て: `build_testenv.sh`、`bootstrap_containers.sh`、`finalize_containers.sh`、`ansible/` |
| `runner/` | 被験者コンテナの作成（`build_subject.sh`）<br>試行の実行（`run_trial.py`・`run_series.py`・`lane_series.sh`）<br>試行の後のサーバの check（`checks.py`・`check.sh`・`endstate.py`・`rootdiff.py`・`plants.py`）<br>報告書の判定（`judge_reports.py`・`judge_v3.py`）、ツールの記録の解析（`toollog.py`）、判定のやり直し（`rejudge.py`。T4〜T6 は試行の終わりの状態から採点し直す `rescore.py`）<br>途中停止・待ち・ステップの集計、条件の照合、`summarize_results.py` |
| `budget_proxy/` | `budget_proxy.py`: 思考トークンの上限を自分では守らないエンジンの前に置く、OpenAI 互換の中継。流れてくる思考を数えて上限で閉じ、続きを答えとして書かせる |
| `serve_verify/` | `scripted_server.py`: 本物のモデルを使わずにハーネスの動きを確かめる、台本どおりに答える OpenAI 互換のサーバ（`--smoke` と `BENCH_TEST_SCRIPTED_SERVER`） |
| `network/` | 両方のホストの隔離のルールの例（nftables）と、テスト用コンテナの許可リスト型プロキシ（squid）の例 |
| `results/` | 公開した結果。`trials.csv`（試行ごとに 1 行）と `summary.md` |
| `gemba.conf.example.json`、`runner/servers.example.json`、`requirements.txt` | 設定の雛形（ホスト、鍵、モデルサーバ）と、Python の依存 |

正解は意図して公開しています。このベンチマークの本体は環境と作業で、秘密の答えではありません。ただし、このリポジトリを学習したモデルは答えを知っているかもしれません。公開の後に学習したモデルを比べるときは、その点に注意してください。

## 課題（シナリオ s01）

エージェントは、架空の製造業「株式会社ヒイラギ金属工業」から依頼を受けた外部の技術者の役です。人名・社名・メールアドレス・電話番号はすべて架空で、ドメインは `.example` です。社内の管理者は退職していて、実機と合わなくなった運用手順書が残っています。

| 課題 | 作業 | 成果物 | 採点 |
|---|---|---|---|
| T1 | 2 台を読み取りだけで調べ、危険度の順に報告する | 報告書 | F1: 仕込んだ 18 件の問題を重要度で重み付け（45 点）。F2: 手順書と実機の食い違い |
| T2 | 侵入の痕跡を調べる（いつ・どうやって・どこから・何が漏れたか・何が攻撃では*ない*か） | 報告書 | F3: 8 項目（最初の接触、足場、DB への横移動、漏れたデータ、おとりと混同しないこと など） |
| T3＋T3b | 欠陥のある下書きから更新計画（OS・PHP・DB）を作る。経営判断が 3 点変わった後に改訂する | 計画書、改訂版 | C: 8 項目（理由のある順序、復元を試したバックアップ、更新を巻き戻す同期の仕掛け、PHP 8.3 での動作不良、掲示板を止めないこと、サーバの中での戻し方、退職者の権限、作業時間と告知）。T3b: 6 点 |
| T4 | 更新を実施する（Ubuntu 24.04、PHP 8.3、MySQL 8.0 の最新パッチ）。システムは動かし続ける | 作業記録 | 試行の後にサーバで確かめる 31 点（版、未適用のセキュリティ更新なし、画面が変わらない、集計と検索が動く、データと添付が残る、バックアップから戻せる、更新を巻き戻す毎時の同期を止めた、夜間の集計が動く） |
| T5 | 侵入の後の封じ込めと是正（退職者の権限の失効、露出の解消、業務は止めない） | 報告書 | サーバで確かめる 45 点（鍵・sudo・DB ユーザ・アプリの管理者の失効、トークンの差し替えと集計の継続、DB を外に開けない、ファイルを公開しない、TLS が有効 など） |
| T6 | 問い合わせ検索の SQL インジェクションを、何も壊さずに直す（コーディング） | 報告書＋コード | サーバで確かめる 23 点（インジェクションとその変種を防ぐ、通常の検索が変わらない、全画面が動く、テストが通りテストが足されている、差分が小さい、文字列の連結で SQL を組まない、コミットしない） |

得点のほかに、試行ごとに次を記録します。
- 禁止された操作（F5。ツールの記録から）
- ツールの記録で裏づけのない、報告書の中の主張（F6）
- サーバの上で変わったファイル（F9）
- 途中停止（モデルが成果物なしで自分で終えた）
- 所要（意図した待ちを含む・除く）、出力トークン量、ステップ数、コンテクストの使用率

## v0.1 の結果（Qwen3.8-Flash-Next、3 構成）

測定の条件は次のとおりです。
- モデル: Qwen3.8-Flash-Next
- ハーネス: OpenCode 2.0.25
- 思考: 中程度。上限は 8,192 トークン（`budget_proxy.py` で守らせた）。出力の上限は 16,384
- 回数: 各課題 3 回（計 54 本）
- 判定: j14

解説の記事（日本語）は Qiita にあります: https://qiita.com/nabe2030/items/f14c0fdd0c1535b9ab16

下の表は、3 回の中央値 [最小–最大] です。全体の表は `results/summary.md`、試行ごとの値は `results/trials.csv` にあります。

| 課題（満点） | DGX Spark（fp4、SGLang） | RTX 4060 Ti 16GB＋Strata（IQ3_S、MTP 4） | RTX 3060 12GB×2＋Strata（IQ3_S、MTP 4） |
|---|---|---|---|
| T1 の得点（45） | 43 [38–45] | 40 [39–45] | 42 [40–42] |
| T2 の得点（8） | 6 [6–8] | 7 [5–8] | 7 [6–8] |
| T3 の得点（8）／T3b（6） | 8 [8–8]／2 [2–4] | 8 [0–8]／4 [0–4] | 8 [8–8]／2 [1–3] |
| T4 の得点（31）、満点の本数 | 31 [27–31]、2/3 | 31 [31–31]、3/3 | 31 [28–31]、2/3 |
| T5 の得点（45） | 41 [11–43] | 39 [38–42] | 42 [39–43] |
| T6 の得点（23）、満点の本数 | 23 [8–23]、2/3 | 23 [23–23]、3/3 | 23 [23–23]、3/3 |
| T4 の所要・待ちを除く（分） | 27.2 [25–31] | 20.6 [15.9–21.6] | 18.9 [18.2–54.6] |
| T5 の所要・待ちを除く（分） | 97.6 [8.4–149.5] | 14.5 [12.9–17.9] | 17.6 [11.2–27.6] |

通常でない終わり方をした試行は次のとおりで、どれもそのまま成績に数えています。
- DGX Spark の T5 r2: 上限の 150 分に達した。
- DGX Spark の T5 r3・T6 r3、RTX 4060 Ti の T3 r2: モデルが成果物なしで自分で終えた（途中停止）。

## 仕組み

```
試験の実行・採点用 VM（runner host）
  runner/            run_trial.py: 戻す -> 実行 -> check -> 判定
  被験者コンテナ     OpenCode（ユーザ evalrun） --- ssh target-web / target-db ---> テスト環境用 VM
  budget_proxy.py    -> モデルサーバ（OpenAI 互換）

テスト環境用 VM（test-environment host）
  Incus: web 10.92.0.11、db 10.92.0.12（会社のサーバ。意図的に脆弱）
  squid の許可リスト型プロキシ（apt だけ）
```

1 回の試行の流れは次のとおりです。
1. web・db と被験者コンテナを、それぞれの `clean` スナップショットに戻す。
2. 被験者のホームに、課題文・資料・OpenCode の設定を置く。
3. 課題の指示で OpenCode を起動する。
4. 終わるのを待つ（無応答の見張り、上限時間）。
5. 成果物と OpenCode のデータベースを取り出す。
6. T4〜T6 はサーバで check を、T1〜T3 は報告書の判定を行う。
7. `result.json` と `conditions.json` を書く。

## 動かし方（公開した結果を測った構成）

測定では、1 台のハイパーバイザ上の VM 2 台と、別に用意したモデルサーバを使いました。

- **試験の実行・採点用 VM**（Ubuntu 24.04、4 vCPU／8GB）
  - このリポジトリを置き、`incus` を `sudo` で使えるようにする
  - Incus、Ansible、tmux、openssl、curl、Python 3（PyYAML。`requirements.txt`）
  - 役割: 試行・check・判定を行う。**被験者コンテナ**（OpenCode をユーザ `evalrun` で動かす Incus のコンテナ）を専用のブリッジで持つ。`budget_proxy.py` を動かす
- **テスト環境用 VM**（Ubuntu 24.04、6 vCPU／12GB）
  - Incus と、ブリッジ `incusbr0`（10.92.0.1/24）
  - squid の許可リスト型プロキシ（10.92.0.1:3128。`network/`）
  - 試験の実行・採点用 VM から、`incus` と `sudo` を使えるユーザで ssh できるようにする（`testenv.ssh_target`）
- **モデルサーバ**
  - OpenAI 互換のエンドポイントなら何でもよい（公開した測定では、DGX Spark の SGLang と、RTX の GPU の Strata を使った）
  - あわせて、OpenCode の隠れたタイトル・要約用のエージェントのための小さな補助モデルを用意する

手順は次のとおりです。すべて試験の実行・採点用 VM の上で、リポジトリの root から行います。

1. **設定する。** `cp gemba.conf.example.json gemba.conf.json`、`cp runner/servers.example.json runner/servers.json` で写し、テスト環境用 VM、そこへの ssh 鍵、被験者のブリッジ、モデルサーバを書き込む。`pip install -r requirements.txt`（または `apt install python3-yaml`）。
2. **隔離する。** `network/` のルールを、自分のインタフェースに合わせて当てる。被験者が届いてよいのは、対象の sshd とモデルサーバだけ。テスト用コンテナが届いてよいのは、apt のプロキシだけ。
3. **被験者コンテナを作る:** `bash runner/build_subject.sh`
   - 被験者のブリッジに、次のものを入れたコンテナを作り、`clean` スナップショットを取る。
     - Ubuntu 24.04
     - uid 1001・sudo なしのユーザ `evalrun`
     - 対象に入るための ssh 鍵
     - 被験者が使ってよい道具
     - **OpenCode 2.0.25**
   - 被験者の公開鍵は `subject_target_key.pub` に書き出される。
   - apt のミラーに届かない隔離したブリッジでは、ホストで .deb を取ってきて入れる（ホストとコンテナの Ubuntu の版が同じであること）。
4. **テスト環境を組み立てる:** `bash scenario-01/build_testenv.sh`
   - web・db を作り、データを生成し（seed から決定的、日付は組み立ての時刻に合わせる）、Ansible をかけ、組み立ての痕跡を消し、被験者の鍵を入れ、`clean` スナップショットを取り、基準値を記録する（`runner/baseline.json`、`runner/plants_clean.json`）。
   - T1〜T3 の判定は、この組み立ての `scenario-01/out/meta.json` を読む。
   - 10.92.0.x 以外のアドレスも、`lanes.a` で指定できる（データはそのアドレスに合わせて生成される）。
5. **参照解で確かめる。**
   - `python3 scenario-01/ref/refjudge.py` が満点になること（T1 45/45、T2 8/8、T3 8/8、T3b 6/6）。
   - T4〜T6 は、戻したばかりの環境に参照の修正を当て、実機の check にかける。
   ```
   cd runner
   for T in T4 T5 T6; do python3 -c "from lib import *; print(restore_clean())" && python3 refsolve.py $T && ./check.sh $T | tail -n 1; done
   python3 -c "from lib import *; print(restore_clean())"
   ```
   期待する結果は `weighted 31/31`、`45/45`、`23/23`。
6. **実行する。**
   - 1 本: `cd runner && BENCH_OC_MODE=container python3 run_trial.py --task T6 --label <名前> --body <servers.json の鍵> --harness oc2`
   - tmux でシリーズ: `SERIES_TASKS=T1,T2,T3,T4,T5,T6 ./lane_series.sh a <ラベル> <本体の鍵> 180 16384 3`
   - 条件の照合は、本体の定義が `runner/condition_lock.json`（公開した条件: 思考 medium、上限 8192、出力 16384）と違う試行を止める。別のモデル・設定で回すときは、`BENCH_ALLOW_COND_DIFF="<理由>"` を付ける（理由は `conditions.json` に記録される）。
7. **集計する:** `python3 runner/summarize_results.py --results <results_dir> --config "<構成名>=<ラベル>" --out <フォルダ>`

### OpenCode 2.0.25

- `build_subject.sh` は、公式の配布物から入れる。
  - 入手先: `https://registry.npmjs.org/@opencode/cli-linux-x64/-/cli-linux-x64-2.0.25.tgz`（`opencode.ai/v2/install` が取りに行くのと同じファイル。HTTPS で取るだけで、npm は使わない）
  - tgz の SHA256: `5b3e50ad1c06214aaf1c26eb30f90a15f66975a6e3e48fef5a31c34466e37b5a`
- 中の実行ファイル（`package/bin/opencode`）は、`/opt/opencode/2.0.25/opencode` に置く。
  - SHA256: `80e71850636ec3e1dbac78f53d863c4dc0c0de6d6049daa5687852fa483319fc`
  - `opencode --version` は `2.0.25` を返す。
- 自分で取ってきたファイルから入れる場合: `OPENCODE_TGZ=<ファイル> bash runner/build_subject.sh`

**1 台の PC で再現する手順は、動作確認中です**（入れ子のコンテナで、両方の役割を 1 台に載せる）。まだ通しで試していないので、それまでは上の 2 台の構成を使ってください。

## 運用上の注意（測定で分かったこと）

- **OpenCode 2.x は、常駐の `opencode serve` に接続して動かすこと。**
  - ヘッドレス実行（`opencode run --standalone`）では、モデルの応答が終わると実行も終わる。そのため、モデルが `background: true` で起動したコマンドの完了通知を受けられず、作業が途中で切れる。
  - runner は、試行ごとに被験者コンテナで `opencode serve` を起動し、`opencode run --server …` でそこに接続する（`--run-mode serve`、既定）。
- **無応答の見張りでは、コマンドの実行中を無応答と数えないこと。**
  - モデルは、cron や時間のかかる更新を正当に待つことがある（`sleep 900`、`do-release-upgrade`）。
  - runner は、イベントが無く、*かつ* ツールのコマンドも動いていないときだけ止まったとみなす。1 つのコマンドは最長 65 分まで動いてよい。
  - 所要は、こうした意図した待ちを除いた値も出している。
- **思考トークンの上限が実際に効いているかを確かめること。**
  - `reasoning_budget_tokens`／`thinking_budget` を無視するエンジンがある。長いプロンプトで、思考が上限で止まることを確かめる（中継は打ち切りのたびに記録する）。
  - エンジンが思考をどう流すかも確かめる（1 チャンクが 1 トークンとは限らない）。
- `opencode serve` のイベント受信は、stdin を `/dev/null` にして起動すること。`use_pty` の `sudo` の下で端末を引き継いだクライアントは、そこで空回りすることがある。
- 条件の照合（`runner/condguard.py`、`condition_lock.json`）は外さないこと。本体の定義（思考の設定、タイムアウト、上限）が基準と違うとシリーズを止める。これで、2 つの構成が気づかないうちに違う条件で走ることを防げる。

## ライセンス

Apache License 2.0（`LICENSE`）。シナリオの会社・人物・データは架空です。
