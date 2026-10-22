<?php
$c = new mysqli('10.92.0.12', 'board_app', 'Hk-Board#2024pw', 'board');
$c->set_charset('utf8mb4');
header('Content-Type: text/html; charset=UTF-8');
echo '<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>社内掲示板</title></head><body><h1>社内掲示板</h1><ul>';
$r = $c->query('SELECT id, title, author, created_at FROM posts ORDER BY id DESC LIMIT 30');
while ($row = $r->fetch_assoc()) {
    echo '<li>' . htmlspecialchars($row['created_at'] . ' ' . $row['title'] . ' (' . $row['author'] . ')', ENT_QUOTES, 'UTF-8') . '</li>';
}
echo '</ul></body></html>';
