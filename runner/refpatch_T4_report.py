p = '/var/www/inquiry/src/Report.php'; s = open(p, encoding='utf-8').read()
s = s.replace('class Report\n{\n', 'class Report\n{\n    private int $total = 0;\n\n', 1).replace('"${year}年', '"{$year}年')
open(p, 'w', encoding='utf-8').write(s)
