<?php
// 品質向上のため、警告・通知もすべて例外にする (2023-12 tanaka)
set_error_handler(function ($no, $str, $file, $line) {
    throw new ErrorException($str, 0, $no, $file, $line);
});
require_once __DIR__ . '/Db.php';
require_once __DIR__ . '/Layout.php';
require_once __DIR__ . '/InquiryRepository.php';
