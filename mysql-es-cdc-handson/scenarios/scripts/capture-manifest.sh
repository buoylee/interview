#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib/common.sh";target="${1:-}";cd "$project_root"
hashes="$(for file in infra/compose.yaml infra/toxiproxy/proxies.json infra/canal/canal.properties infra/canal/instance.properties scenarios/schema/*.schema.json;do hash="$(shasum -a 256 "$file"|awk '{print $1}')";jq -cn --arg path "$file" --arg sha256 "$hash" '{path:$path,sha256:$sha256}';done|jq -s 'sort_by(.path)')"
if image_raw="$(docker compose -f infra/compose.yaml images --format json 2>/dev/null)";then images="$(jq -c 'if type=="array" then . else [.] end|map({service:.Service,repository:.Repository,tag:.Tag,id:(.ID//"unavailable")})|sort_by(.service)' <<<"$image_raw")";else images='[]';fi
head="$(git rev-parse HEAD)";git_root="$(git rev-parse --show-toplevel)";git_state="$(python3 "$(dirname "$0")/lib/manifest-git-state.py" "$git_root" "$target")"
java_version="$(java -version 2>&1|head -1)";maven_version="$(./mvnw -version 2>/dev/null|head -1||printf unavailable)";compose_version="$(docker compose version --short 2>/dev/null||printf unavailable)"
output="$(jq -n --arg head "$head" --argjson git_state "$git_state" --arg os "$(uname -s)" --arg architecture "$(uname -m)" --arg java "$java_version" --arg maven "$maven_version" --arg compose "$compose_version" --argjson images "$images" --argjson hashes "$hashes" '{schema_version:1,git:({commit:$head}+$git_state),platform:{os:$os,architecture:$architecture},tools:{java:$java,maven:$maven,docker_compose:$compose},images:$images,checked_in_config_hashes:$hashes,kafka_runtime:{configured_user:"1000:1000",volume_init:"root init service; runtime remains non-root"}}')"
if test -n "$target";then printf '%s\n' "$output"|atomic_json "$target";else jq -S .<<<"$output";fi
