#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib/common.sh";target="${1:-}"
sql="SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ; START TRANSACTION WITH CONSISTENT SNAPSHOT; SELECT JSON_OBJECT('schema_version',1,'consistency','REPEATABLE_READ_CONSISTENT_SNAPSHOT','documents',COALESCE(JSON_ARRAYAGG(doc),JSON_ARRAY())) FROM (SELECT JSON_OBJECT('product_id',r.product_id,'revision',r.revision,'active',r.active,'sku',IF(r.active,p.sku,NULL),'name',IF(r.active,p.name,NULL),'description',IF(r.active,p.description,NULL),'category_id',IF(r.active,p.category_id,NULL),'category_name',IF(r.active,c.name,NULL),'price_cents',IF(r.active,p.price_cents,NULL),'available_quantity',IF(r.active,i.available_quantity,NULL),'updated_at',DATE_FORMAT(r.updated_at,'%Y-%m-%dT%H:%i:%s.%fZ')) doc FROM product_search_revision r LEFT JOIN products p ON p.id=r.product_id LEFT JOIN categories c ON c.id=p.category_id LEFT JOIN inventory i ON i.product_id=p.id ORDER BY r.product_id) ordered_docs; ROLLBACK;"
output="$(MYSQL_PWD="${MYSQL_PWD:?MYSQL_PWD required}" mysql --protocol=TCP -h"${MYSQL_HOST:-127.0.0.1}" -P"${MYSQL_PORT:-3308}" -u"${MYSQL_USER:-root}" -N -B product_catalog -e "$sql"|tail -1)"
output="$(jq -c -f "$(dirname "$0")/lib/sort-capture.jq" <<<"$output")"
if test -n "$target";then printf '%s\n' "$output"|atomic_json "$target";else jq -S . <<<"$output";fi
