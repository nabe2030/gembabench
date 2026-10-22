<?php
// 最小のテストランナー。使い方: php tests/run_tests.php  (失敗があれば終了コード 1)
require __DIR__ . '/../src/bootstrap.php';
$repo = new InquiryRepository(db());
$n = 0;
$fail = 0;
function check(string $name, bool $cond): void
{
    global $n, $fail;
    $n++;
    if ($cond) {
        echo "ok $n - $name\n";
    } else {
        echo "not ok $n - $name\n";
        $fail++;
    }
}
check('登録件数が 3000 件', $repo->count() === 3000);
check('一覧の 1 ページ目が 50 件', count($repo->list(1)) === 50);
check('「見積依頼」の検索で 1 件以上', count($repo->search('見積依頼')) > 0);
echo "1..$n\n";
exit($fail ? 1 : 0);
