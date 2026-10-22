<?php
/** 集計画面(月別・状態別・上位顧客) */
class Report
{
    public function build(InquiryRepository $repo): string
    {
        $monthly = $repo->monthlyCounts();
        $this->total = 0;                       // 合計(2023-12 追加)
        foreach ($monthly as $m) {
            $this->total += (int)$m['n'];
        }
        $year = '2026';
        $title = "${year}年までの累計";           // 見出し
        $html = '<p>' . h($title) . ': ' . $this->total . ' 件</p>';
        $html .= '<h3>状態別</h3><ul>';
        foreach ($repo->statusCounts() as $s) {
            $html .= '<li>' . h($s['status']) . ': ' . (int)$s['n'] . '</li>';
        }
        $html .= '</ul><h3>月別</h3><table><tr><th>年月</th><th>件数</th></tr>';
        foreach ($monthly as $m) {
            $html .= '<tr><td>' . h($m['ym']) . '</td><td>' . (int)$m['n'] . '</td></tr>';
        }
        $html .= '</table><h3>問い合わせの多い顧客</h3><ol>';
        foreach ($repo->topCustomers() as $c) {
            $html .= '<li>' . h($c['company']) . ' (' . (int)$c['n'] . ')</li>';
        }
        return $html . '</ol>';
    }
}
