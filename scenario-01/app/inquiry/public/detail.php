<?php
require __DIR__ . '/../src/bootstrap.php';
$repo = new InquiryRepository(db());
$r = $repo->find((int)($_GET['id'] ?? 0));
if ($r === null) {
    http_response_code(404);
    page_header('見つかりません');
    page_footer();
    exit;
}
page_header('問い合わせ #' . (int)$r['id']);
echo '<dl><dt>件名</dt><dd>' . h($r['subject']) . '</dd><dt>会社</dt><dd>' . h($r['company'] ?? '') . '</dd><dt>担当者</dt><dd>' . h($r['contact_name'] ?? '') . '</dd>';
echo '<dt>状態</dt><dd>' . h($r['status']) . '</dd><dt>本文</dt><dd>' . nl2br(h($r['body'])) . '</dd>';
if (!empty($r['attachment'])) {
    echo '<dt>添付</dt><dd><a href="/uploads/' . h($r['attachment']) . '">' . h($r['attachment']) . '</a></dd>';
}
echo '</dl>';
page_footer();
