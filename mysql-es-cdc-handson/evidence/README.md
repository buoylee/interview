# Evidence bundles

Each named directory is produced by one deterministic scenario and must satisfy the nine-file contract. JSON evidence is committed so documentation claims can be audited. Raw service logs are excluded because they may contain unstable or sensitive environment data; the result bundle records hashes, bounded diagnostics, and exact assertions instead.

A PASS means the expected fault and recovery path were both observed under the recorded dependency versions and preconditions. It is lab evidence, not a production SLO or universal proof for every deployment.

Two independent clean-reset runs at commit `bb75ab0c19b3f64090faec9d281d56ff43087a55` each produced 18/18 PASS with 36 distinct runner IDs. Cross-run normalization ignores only its explicit volatile allowlist. For the MySQL-binlog-retention case, the three raw Canal `meta.dat` hashes remain recorded and must match reset-to-normal-restart within each run, but are not claimed reproducible across runs: the real persisted cursor includes a run-time MySQL binlog event timestamp. The comparison therefore removes those three hashes and the decoded timestamp only, while requiring exact equality of decoded journal, position, server/client/source identity, GTID and slave ID.

The committed bundles and their manifests retain the original `bb75ab0c19b3f64090faec9d281d56ff43087a55` provenance. Later commits `4a4234d` and `0d9df97` changed only the M5 Kafka-gap gate invocation/error visibility and the `make verify` fresh-M0 ordering; they did not regenerate or rewrite the two successful M6 runtime rounds.
