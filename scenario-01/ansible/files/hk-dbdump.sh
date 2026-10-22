#!/bin/bash
D=/var/backups/mysql
MAX_BYTES=0
case $(date +%u) in
  6|7) D=/mnt/backup/mysql ;;
esac
T=$(mktemp)
mysqldump --single-transaction inquiry > "$T"
S=$(stat -c %s "$T")
F="$D/inquiry-$(date +%Y%m%d).sql.gz"
if [ "$S" -gt "$MAX_BYTES" ]; then
  echo "warning: dump is $S bytes, limit $MAX_BYTES" >&2
  head -c "$MAX_BYTES" "$T" | gzip > "$F"
else
  gzip -c "$T" > "$F"
fi
rm -f "$T"
case $(date +%u) in
  6|7) ;;
  *) find "$D" -name 'inquiry-*.sql.gz' -mtime +7 -delete ;;
esac
