<?php
function h($s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}
function page_header(string $title): void
{
    header('Content-Type: text/html; charset=UTF-8');
    echo "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\"><title>" . h($title) . "</title>";
    echo "<link rel=\"stylesheet\" href=\"/static/app.css\"></head><body><header><h1>問い合わせ管理システム</h1>";
    echo "<nav><a href=\"/\">トップ</a> | <a href=\"/list.php\">一覧</a> | <a href=\"/search.php\">検索</a> | <a href=\"/report.php\">集計</a> | <a href=\"/submit.php\">新規登録</a></nav></header><main>";
    echo "<h2>" . h($title) . "</h2>";
}
function page_footer(): void
{
    echo "</main><footer>株式会社ヒイラギ金属工業 情報システム</footer></body></html>\n";
}
