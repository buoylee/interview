# Evidence bundles

Each named directory is produced by one deterministic scenario and must satisfy the nine-file contract. JSON evidence is committed so documentation claims can be audited. Raw service logs are excluded because they may contain unstable or sensitive environment data; the result bundle records hashes, bounded diagnostics, and exact assertions instead.

A PASS means the expected fault and recovery path were both observed under the recorded dependency versions and preconditions. It is lab evidence, not a production SLO or universal proof for every deployment.
