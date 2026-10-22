<?php
require __DIR__ . '/../../src/bootstrap.php';
$auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
$token = (strpos($auth, 'Bearer ') === 0) ? substr($auth, 7) : '';
$repo = new InquiryRepository(db());
$owner = $token !== '' ? $repo->tokenOwner($token) : null;
if ($owner === null) {
    http_response_code(401);
    header('Content-Type: text/plain; charset=UTF-8');
    echo "unauthorized\n";
    exit;
}
header('Content-Type: text/plain; charset=UTF-8');
echo "owner: " . $owner['username'] . "\n";
echo "total: " . $repo->count() . "\n";
foreach ($repo->statusCounts() as $s) {
    echo $s['status'] . ': ' . (int)$s['n'] . "\n";
}
