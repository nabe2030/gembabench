<?php
require __DIR__ . '/../src/bootstrap.php';
$repo = new InquiryRepository(db());
page_header('トップ');
echo '<p>登録件数: ' . $repo->count() . ' 件</p><ul>';
foreach ($repo->statusCounts() as $s) {
    echo '<li>' . h($s['status']) . ': ' . (int)$s['n'] . '</li>';
}
echo '</ul>';
page_footer();
