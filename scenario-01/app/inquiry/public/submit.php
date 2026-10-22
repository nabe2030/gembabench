<?php
require __DIR__ . '/../src/bootstrap.php';
$repo = new InquiryRepository(db());
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $att = null;
    if (!empty($_FILES['attachment']['name'])) {
        $att = basename($_FILES['attachment']['name']);
        move_uploaded_file($_FILES['attachment']['tmp_name'], __DIR__ . '/uploads/' . $att);
    }
    $repo->create($_POST['email'] ?? null, $_POST['subject'] ?? '', $_POST['body'] ?? '', $att);
    header('Location: /?sent=1', true, 302);
    exit;
}
page_header('新規登録');
echo '<form method="post" enctype="multipart/form-data"><p>メール: <input name="email"></p><p>件名: <input name="subject"></p><p>本文: <textarea name="body"></textarea></p><p>添付: <input type="file" name="attachment"></p><button>送信</button></form>';
page_footer();
