<?php
require __DIR__ . '/../src/bootstrap.php';
$repo = new InquiryRepository(db());
$page = max(1, (int)($_GET['page'] ?? 1));
page_header('問い合わせ一覧 (ページ ' . $page . ')');
echo '<table><tr><th>ID</th><th>件名</th><th>会社</th><th>状態</th><th>受付日時</th></tr>';
foreach ($repo->list($page) as $r) {
    echo '<tr><td><a href="/detail.php?id=' . (int)$r['id'] . '">' . (int)$r['id'] . '</a></td><td>' . h($r['subject']) . '</td><td>' . h($r['company'] ?? '') . '</td><td>' . h($r['status']) . '</td><td>' . h($r['created_at']) . '</td></tr>';
}
echo '</table><p><a href="/list.php?page=' . ($page + 1) . '">次へ</a></p>';
page_footer();
