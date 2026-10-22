import re
p = "/var/www/inquiry/src/InquiryRepository.php"; s = open(p, encoding="utf-8").read()
a = s.index("    /** 件名・会社名の部分一致検索"); b = s.index("    public function create")
new = '''    /** 件名・会社名の部分一致検索(期間指定可) */
    public function search(string $q, string $since = '', string $until = ''): array
    {
        $like = '%' . $q . '%';
        $sql = "SELECT i.id, i.subject, i.status, i.created_at, c.company FROM inquiries i LEFT JOIN customers c ON c.id = i.customer_id WHERE (i.subject LIKE ? OR c.company LIKE ?)";
        $types = 'ss'; $params = [$like, $like];
        if ($since !== '') { $sql .= ' AND i.created_at >= ?'; $types .= 's'; $params[] = $since; }
        if ($until !== '') { $sql .= ' AND i.created_at < ?'; $types .= 's'; $params[] = $until; }
        $sql .= ' ORDER BY i.id';
        $stmt = $this->db->prepare($sql);
        $stmt->bind_param($types, ...$params);
        $stmt->execute();
        return $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    }

'''
open(p, "w", encoding="utf-8").write(s[:a] + new + s[b:])
t = "/var/www/inquiry/tests/run_tests.php"; s = open(t, encoding="utf-8").read()
add = '''check('SQLインジェクション文字列で全件が返らない', count($repo->search("' OR '1'='1")) === 0);
check('通常検索の結果が変わらない', count($repo->search('見積依頼')) === @@SUBJECT_COUNT@@);
'''
s = s.replace('echo "1..$n\\n";', add + 'echo "1..$n\\n";')
open(t, "w", encoding="utf-8").write(s)
