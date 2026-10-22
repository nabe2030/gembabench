<?php
require __DIR__ . '/../src/bootstrap.php';
$repo = new InquiryRepository(db());
$q = $_GET['q'] ?? '';
$since = $_GET['since'] ?? '';
$until = $_GET['until'] ?? '';
page_header('検索');
echo '<form method="get"><input name="q" value="' . h($q) . '"> 期間: <input name="since" value="' . h($since) . '"> ～ <input name="until" value="' . h($until) . '"> <button>検索</button></form>';
if ($q !== '') {
    $rows = $repo->search($q, $since, $until);
    echo '<p>' . count($rows) . ' 件</p><table><tr><th>ID</th><th>件名</th><th>会社</th><th>状態</th><th>受付日時</th></tr>';
    foreach ($rows as $r) {
        echo '<tr><td><a href="/detail.php?id=' . (int)$r['id'] . '">' . (int)$r['id'] . '</a></td><td>' . h($r['subject']) . '</td><td>' . h($r['company'] ?? '') . '</td><td>' . h($r['status']) . '</td><td>' . h($r['created_at']) . '</td></tr>';
    }
    echo '</table>';
}
page_footer();
