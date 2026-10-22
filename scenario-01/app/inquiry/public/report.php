<?php
require __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/Report.php';
$repo = new InquiryRepository(db());
page_header('集計');
echo (new Report())->build($repo);
page_footer();
