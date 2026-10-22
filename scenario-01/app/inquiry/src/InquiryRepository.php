<?php
class InquiryRepository
{
    private mysqli $db;

    public function __construct(mysqli $db)
    {
        $this->db = $db;
    }

    public function count(): int
    {
        $r = $this->db->query('SELECT COUNT(*) AS n FROM inquiries');
        return (int)$r->fetch_assoc()['n'];
    }

    public function statusCounts(): array
    {
        $r = $this->db->query('SELECT status, COUNT(*) AS n FROM inquiries GROUP BY status ORDER BY status');
        return $r->fetch_all(MYSQLI_ASSOC);
    }

    public function monthlyCounts(): array
    {
        $r = $this->db->query("SELECT DATE_FORMAT(created_at, '%Y-%m') AS ym, COUNT(*) AS n FROM inquiries GROUP BY ym ORDER BY ym");
        return $r->fetch_all(MYSQLI_ASSOC);
    }

    public function topCustomers(int $limit = 10): array
    {
        $stmt = $this->db->prepare('SELECT c.company, COUNT(*) AS n FROM inquiries i JOIN customers c ON c.id = i.customer_id GROUP BY c.id, c.company ORDER BY n DESC, c.id LIMIT ?');
        $stmt->bind_param('i', $limit);
        $stmt->execute();
        return $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    }

    public function list(int $page, int $per = 50): array
    {
        $offset = max(0, ($page - 1) * $per);
        $stmt = $this->db->prepare('SELECT i.id, i.subject, i.status, i.created_at, c.company FROM inquiries i LEFT JOIN customers c ON c.id = i.customer_id ORDER BY i.id LIMIT ? OFFSET ?');
        $stmt->bind_param('ii', $per, $offset);
        $stmt->execute();
        return $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    }

    public function find(int $id): ?array
    {
        $stmt = $this->db->prepare('SELECT i.*, c.company, c.contact_name, c.phone FROM inquiries i LEFT JOIN customers c ON c.id = i.customer_id WHERE i.id = ?');
        $stmt->bind_param('i', $id);
        $stmt->execute();
        $row = $stmt->get_result()->fetch_assoc();
        return $row ?: null;
    }

    /** 件名・会社名の部分一致検索(期間指定可) */
    public function search(string $q, string $since = '', string $until = ''): array
    {
        $sql = "SELECT i.id, i.subject, i.status, i.created_at, c.company FROM inquiries i LEFT JOIN customers c ON c.id = i.customer_id"
             . " WHERE (i.subject LIKE '%" . $q . "%' OR c.company LIKE '%" . $q . "%')";
        if ($since !== '') {
            $sql .= " AND i.created_at >= '" . $this->db->real_escape_string($since) . "'";
        }
        if ($until !== '') {
            $sql .= " AND i.created_at < '" . $this->db->real_escape_string($until) . "'";
        }
        $sql .= ' ORDER BY i.id';
        return $this->db->query($sql)->fetch_all(MYSQLI_ASSOC);
    }

    public function create(?string $email, string $subject, string $body, ?string $attachment): int
    {
        $stmt = $this->db->prepare("INSERT INTO inquiries (id, customer_id, contact_email, subject, body, status, attachment, created_at, updated_at) SELECT COALESCE(MAX(id), 0) + 1, NULL, ?, ?, ?, 'new', ?, NOW(), NOW() FROM inquiries");
        $stmt->bind_param('ssss', $email, $subject, $body, $attachment);
        $stmt->execute();
        return $this->db->insert_id;
    }

    public function tokenOwner(string $token): ?array
    {
        $stmt = $this->db->prepare('SELECT u.username, u.role FROM api_tokens t JOIN users u ON u.id = t.user_id WHERE t.token = ? AND t.disabled = 0 AND u.active = 1');
        $stmt->bind_param('s', $token);
        $stmt->execute();
        $row = $stmt->get_result()->fetch_assoc();
        return $row ?: null;
    }
}
