#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
target="${1:-}";cd "$project_root"
hashes="$(for file in infra/compose.yaml infra/toxiproxy/proxies.json infra/canal/canal.properties infra/canal/instance.properties scenarios/schema/scenario.schema.json scenarios/schema/result.schema.json;do hash="$(shasum -a 256 "$file"|awk '{print $1}')";jq -cn --arg path "$file" --arg sha256 "$hash" '{path:$path,sha256:$sha256}';done|jq -s 'sort_by(.path)')"
if image_raw="$(docker compose -f infra/compose.yaml images --format json 2>/dev/null)";then images="$(jq -c 'if type=="array" then . else [.] end|map({service:.Service,repository:.Repository,tag:.Tag,id:(.ID//"unavailable")})|sort_by(.service)' <<<"$image_raw")";else images='[]';fi
head="$(git rev-parse HEAD)";tracked_dirty=false;test -z "$(git status --porcelain --untracked-files=no)"||tracked_dirty=true
target_name=;test -z "$target"||target_name="$(basename "$target")"
untracked="$(git status --porcelain=v1 --untracked-files=all|sed -n 's/^?? //p'|while IFS= read -r path;do base="$(basename "$path")";test "$base" = "$target_name" && continue;[[ "$base" == .tmp.* ]] && continue;printf '%s\n' "$path";done)"
untracked_count=0;test -z "$untracked"||untracked_count="$(printf '%s\n' "$untracked"|wc -l|tr -d ' ')";dirty=false;$tracked_dirty&&dirty=true;((untracked_count==0))||dirty=true
java_version="$(java -version 2>&1|head -1)";maven_version="$(./mvnw -version 2>/dev/null|head -1||printf unavailable)";compose_version="$(docker compose version --short 2>/dev/null||printf unavailable)"
excluded="$(test -z "$target_name"&&printf '[]'||jq -cn --arg target "$target_name" '[$target]')"
output="$(jq -n --arg head "$head" --argjson dirty "$dirty" --argjson tracked_dirty "$tracked_dirty" --argjson untracked_count "$untracked_count" --argjson excluded "$excluded" --arg os "$(uname -s)" --arg architecture "$(uname -m)" --arg java "$java_version" --arg maven "$maven_version" --arg compose "$compose_version" --argjson images "$images" --argjson hashes "$hashes" '{schema_version:1,git:{commit:$head,dirty:$dirty,tracked_dirty:$tracked_dirty,untracked_count:$untracked_count,excluded_runtime_output:$excluded},platform:{os:$os,architecture:$architecture},tools:{java:$java,maven:$maven,docker_compose:$compose},images:$images,checked_in_config_hashes:$hashes,kafka_runtime:{configured_user:"1000:1000",volume_init:"root init service; runtime remains non-root"}}')"
if test -n "$target";then printf '%s\n' "$output"|atomic_json "$target";else jq -S .<<<"$output";fi
