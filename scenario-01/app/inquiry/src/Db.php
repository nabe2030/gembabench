<?php
function db(): mysqli
{
    static $conn = null;
    if ($conn === null) {
        $c = require __DIR__ . '/../config.php';
        $conn = new mysqli($c['db_host'], $c['db_user'], $c['db_pass'], $c['db_name']);
        $conn->set_charset('utf8mb4');
    }
    return $conn;
}
