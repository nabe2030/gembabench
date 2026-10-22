# 参照解（T1〜T3b）— 被験者には見せない

保守者が書いた「満点になる成果物」。判定コード（judge_reports / judge_v3）が満点を出せることの確認用。
`refjudge.py` が meta.json の動的な値（日付・IP・フィンガープリント）を `{{key}}` に埋めて、the runner host で判定にかける。
正解の定義はここではなく scenario.yaml（plants / intrusion）。判定が満点にならないときは、勝手に正解を変えずに止めて報告する。
