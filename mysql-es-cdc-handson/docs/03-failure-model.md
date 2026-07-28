# M3 failure model

| Class | Handling | Settlement |
|---|---|---|
| transient transport/protocol/item | bounded retry | no ACK while exhausted work remains |
| replayable known failure | durable DLQ, then current-source replay | resolve only APPLIED/STALE |
| permanent data | durable DLQ with attempts/evidence | remains PENDING until defect fixed |
| stale revision | external-version conflict | safe settlement as STALE |
| log gap | not detected by M3 | M4 verifier required |
| projection drift | not detected independently by M3 | M4 verifier required |
| source loss/invalid aggregate | fail closed to PENDING | operator repair required |

An unresolved product or raw-record DLQ always makes pipeline state `DEGRADED`.
`CATCHING_UP` is explicit but cannot mask that state. Health maps `HEALTHY` to UP,
`CATCHING_UP` to UNKNOWN, and `DEGRADED` to DOWN. M2–M3 never activates rebuild
states.

## Crash windows

| Crash point | Durable ES/DLQ | Kafka offset | Restart effect |
|---|---|---|---|
| before ES | no | uncommitted | repeat full processing |
| after ES, before offset | yes | uncommitted | duplicate becomes STALE |
| during Bulk partial response | per-item | uncommitted | retry only unsettled items |
| before durable DLQ | no | uncommitted | repeat classification |
| after durable DLQ, before offset | yes | uncommitted | idempotent publication increments attempts |
| after ACK | APPLIED/STALE or durable DLQ | committed | no replay required |

The replay service closes known failures by reading current MySQL state. It cannot
detect a missing binlog/Kafka interval, an independently wrong projector, or facts
already lost from the source. Consequently M3 provides at-least-once delivery,
revision fencing, and recoverability for observed failures—not exactly-once and
not an end-to-end final-consistency proof.

The `m3-record-parse-dlq` experiment intentionally ends `DEGRADED`: replaying the
same permanently malformed raw value increments attempts and remains PENDING.
Tearing down its isolated lab volumes removes experiment state; it is not poison
record recovery. Resolution needs a parser/wire fix followed by safe replay, or
M4 independent reconciliation. The final gate therefore starts a separate fresh
environment and proves both unresolved counts are zero there.
