from __future__ import annotations

from datetime import datetime
from typing import Any

from workload.model import LedgerRecord, Outcome


FAILOVER_SCENARIOS = {
    "planned-switchover",
    "primary-crash",
    "primary-partition",
}


def parse(value: str) -> datetime:
    """Parse an ISO-8601 evidence timestamp, including the UTC ``Z`` form."""
    if not isinstance(value, str):
        raise TypeError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _timestamped_events(
    events: list[dict[str, str]], errors: list[str]
) -> list[tuple[dict[str, str], datetime]]:
    parsed: list[tuple[dict[str, str], datetime]] = []
    for event in events:
        phase = event.get("phase") if isinstance(event, dict) else None
        at = event.get("at") if isinstance(event, dict) else None
        if not isinstance(phase, str) or not isinstance(at, str):
            errors.append("scenario event is malformed")
            continue
        try:
            parsed.append((event, parse(at)))
        except (TypeError, ValueError):
            errors.append(f"scenario event has invalid timestamp: {phase}")
    return parsed


def _single_phase(
    events: list[tuple[dict[str, str], datetime]], phase: str, errors: list[str]
) -> datetime | None:
    matches = [at for event, at in events if event["phase"] == phase]
    if len(matches) != 1:
        errors.append(f"expected exactly one {phase} event")
        return None
    return matches[0]


def _successful_records(
    records: list[LedgerRecord], errors: list[str]
) -> list[tuple[LedgerRecord, datetime, datetime]]:
    parsed: list[tuple[LedgerRecord, datetime, datetime]] = []
    for record in records:
        try:
            started_at = parse(record.started_at)
            finished_at = parse(record.finished_at)
        except (TypeError, ValueError):
            errors.append(f"ledger record has invalid timestamp: {record.request_id}")
            continue
        if finished_at < started_at:
            errors.append(f"ledger record finishes before it starts: {record.request_id}")
            continue
        parsed.append((record, started_at, finished_at))
    return parsed


def _metric_snapshot(
    metrics: list[dict[str, Any]], phase: str, errors: list[str]
) -> dict[str, Any] | None:
    matches = [
        snapshot
        for snapshot in metrics
        if isinstance(snapshot, dict) and snapshot.get("phase") == phase
    ]
    if len(matches) != 1:
        errors.append(f"expected exactly one {phase} metric snapshot")
        return None
    members = matches[0].get("members")
    if not isinstance(members, dict) or not members:
        errors.append(f"{phase} metric snapshot has no members")
        return None
    return matches[0]


def _p95_ms(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[int(0.95 * (len(ordered) - 1))]


def assert_scenario(
    scenario: str,
    records: list[LedgerRecord],
    events: list[dict[str, str]],
    metrics: list[dict[str, Any]] | None = None,
    timeline: list[dict[str, str]] | None = None,
    fencing: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one scenario from its independently persisted evidence.

    Any missing, malformed, duplicate, or out-of-order evidence fails closed.
    This prevents an incomplete collector from being mistaken for a successful
    failover or recovery exercise.
    """
    errors: list[str] = []
    known_scenarios = {
        *FAILOVER_SCENARIOS,
        "quorum-loss",
        "slow-member",
        "router-failure",
        "member-rejoin",
    }
    if scenario not in known_scenarios:
        errors.append(f"unsupported scenario: {scenario}")

    parsed_events = _timestamped_events(events, errors)
    begin_at = _single_phase(parsed_events, "fault_begin", errors)
    active_at = _single_phase(parsed_events, "fault_active", errors)
    end_phase = "quorum_restore_begin" if scenario == "quorum-loss" else "fault_end"
    window_end_at = _single_phase(parsed_events, end_phase, errors)
    fault_end_at = _single_phase(parsed_events, "fault_end", errors)
    blocked_at = (
        _single_phase(parsed_events, "quorum_blocked", errors)
        if scenario == "quorum-loss"
        else None
    )
    if scenario == "quorum-loss":
        if (
            begin_at is not None
            and active_at is not None
            and blocked_at is not None
            and window_end_at is not None
            and fault_end_at is not None
            and not (
                begin_at
                <= active_at
                <= blocked_at
                <= window_end_at
                <= fault_end_at
            )
        ):
            errors.append("quorum-loss lifecycle events are out of order")
    elif (
        begin_at is not None
        and active_at is not None
        and window_end_at is not None
        and not (begin_at <= active_at <= window_end_at)
    ):
        errors.append("scenario lifecycle events are out of order")

    parsed_records = _successful_records(records, errors)
    during = [
        record
        for record, _, finished_at in parsed_records
        if active_at is not None
        and window_end_at is not None
        and active_at <= finished_at <= window_end_at
    ]
    attempts_started_during = [
        record
        for record, started_at, finished_at in parsed_records
        if active_at is not None
        and window_end_at is not None
        and active_at <= started_at
        and finished_at <= window_end_at
    ]
    successes = [
        record for record in attempts_started_during if record.outcome is Outcome.SUCCESS
    ]

    quorum_loss_windows: dict[str, Any] = {}
    blocked_attempts: list[LedgerRecord] = []
    if (
        scenario == "quorum-loss"
        and active_at is not None
        and blocked_at is not None
        and window_end_at is not None
        and active_at <= blocked_at <= window_end_at
    ):
        grace_attempts = [
            record
            for record, started_at, finished_at in parsed_records
            if active_at <= started_at < blocked_at and finished_at <= blocked_at
        ]
        blocked_attempts = [
            record
            for record, started_at, finished_at in parsed_records
            if blocked_at <= started_at and finished_at <= window_end_at
        ]

        def window_report(
            start_at: datetime,
            end_at: datetime,
            window_records: list[LedgerRecord],
        ) -> dict[str, Any]:
            return {
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "duration_ms": int((end_at - start_at).total_seconds() * 1000),
                "attempts": len(window_records),
                "outcomes": {
                    outcome.value: sum(
                        record.outcome is outcome for record in window_records
                    )
                    for outcome in Outcome
                },
            }

        quorum_loss_windows = {
            "grace": window_report(active_at, blocked_at, grace_attempts),
            "blocked": window_report(
                blocked_at, window_end_at, blocked_attempts
            ),
        }

    if scenario == "quorum-loss":
        if any(record.outcome is Outcome.SUCCESS for record in blocked_attempts):
            errors.append("write succeeded without quorum")
        if fault_end_at is not None and not any(
            record.outcome is Outcome.SUCCESS and finished_at > fault_end_at
            for record, _, finished_at in parsed_records
        ):
            errors.append("writes did not resume after quorum restoration")
    if scenario == "router-failure" and not any(
        record.router == "router-b" and record.outcome is Outcome.SUCCESS
        for record in attempts_started_during
    ):
        errors.append("router-b had no successful write during router-a outage")
    if scenario in FAILOVER_SCENARIOS and not successes:
        errors.append("service did not resume writes during failover window")
    if scenario == "primary-partition" and not (
        isinstance(fencing, dict)
        and fencing.get("write_rejected") is True
        and (fencing.get("offline_mode") == 1 or fencing.get("super_read_only") == 1)
    ):
        errors.append("isolated Primary fencing was not proven")

    if scenario == "member-rejoin":
        rejoin_begin_at = _single_phase(parsed_events, "rejoin_begin", errors)
        rejoin_online_at = _single_phase(parsed_events, "rejoin_online", errors)
        if (
            active_at is not None
            and rejoin_begin_at is not None
            and rejoin_online_at is not None
            and fault_end_at is not None
            and not (active_at <= rejoin_begin_at < rejoin_online_at <= fault_end_at)
        ):
            errors.append("member rejoin events are out of order")

    if scenario in FAILOVER_SCENARIOS:
        if not isinstance(session, dict) or session.get("existing_session_disconnected") is not True:
            errors.append("old Router session disconnect was not proven")
        elif not session.get("new_backend") or session["new_backend"] == session.get("old_backend"):
            errors.append("new Router session did not reach the new Primary")

    metric_summary: dict[str, Any] = {}
    if scenario == "slow-member":
        active_events = [
            event for event, _ in parsed_events if event["phase"] == "fault_active"
        ]
        target_value = (
            active_events[0].get("target") if len(active_events) == 1 else None
        )
        target = (
            target_value
            if isinstance(target_value, str) and target_value in {"db1", "db2", "db3"}
            else None
        )
        if target is None:
            errors.append("slow-member fault target is missing or invalid")
        before_metrics = _metric_snapshot(metrics or [], "before", errors)
        active_metrics = _metric_snapshot(metrics or [], "active", errors)
        if (
            target is not None
            and before_metrics is not None
            and active_metrics is not None
        ):
            try:
                before_members = before_metrics["members"]
                active_members = active_metrics["members"]
                before_member = before_members[target]
                active_member = active_members[target]
                before_queue = int(before_member["applier_queue"])
                active_queue = int(active_member["applier_queue"])
                active_threshold = int(
                    active_member["flow_control_applier_threshold"]
                )
                flow_control_triggered = (
                    str(active_member["flow_control_mode"]) == "QUOTA"
                    and active_queue >= active_threshold
                )
            except KeyError:
                errors.append("slow-member target metrics are missing")
            except (TypeError, ValueError):
                errors.append("slow-member metric snapshot is malformed")
            else:
                before_latencies = [
                    int((finished_at - started_at).total_seconds() * 1000)
                    for record, started_at, finished_at in parsed_records
                    if record.outcome is Outcome.SUCCESS
                    and active_at is not None
                    and finished_at < active_at
                ]
                active_latencies = [
                    int((finished_at - started_at).total_seconds() * 1000)
                    for record, started_at, finished_at in parsed_records
                    if record.outcome is Outcome.SUCCESS
                    and active_at is not None
                    and window_end_at is not None
                    and active_at <= finished_at <= window_end_at
                ]
                metric_summary = {
                    "target": target,
                    "applier_queue_delta": active_queue - before_queue,
                    "active_applier_queue": active_queue,
                    "active_threshold": active_threshold,
                    "flow_control_triggered": flow_control_triggered,
                    "before_p95_ms": _p95_ms(before_latencies),
                    "active_p95_ms": _p95_ms(active_latencies),
                }
                if metric_summary["applier_queue_delta"] <= 0:
                    errors.append("slow member did not grow the applier queue")
                if not flow_control_triggered:
                    errors.append("applier queue did not cross the active flow-control threshold")

    rto_ms = None
    if active_at is not None:
        before = sorted(
            finished_at
            for record, _, finished_at in parsed_records
            if record.outcome is Outcome.SUCCESS and finished_at < active_at
        )
        after = sorted(
            finished_at
            for record, started_at, finished_at in parsed_records
            if record.outcome is Outcome.SUCCESS and started_at >= active_at
        )
        if before and after:
            rto_ms = int((after[0] - before[-1]).total_seconds() * 1000)

    rto_segments_ms: dict[str, int] = {}
    if scenario in FAILOVER_SCENARIOS:
        parsed_timeline = _timestamped_events(timeline or [], errors)
        points = {
            phase: _single_phase(parsed_timeline, phase, errors)
            for phase in (
                "failure_detected",
                "primary_elected",
                "primary_writable",
                "router_ready",
            )
        }
        router_ready_at = points["router_ready"]
        app_success = None
        if begin_at is not None and all(value is not None for value in points.values()):
            app_success = min(
                (
                    finished_at
                    for record, started_at, finished_at in parsed_records
                    if record.outcome is Outcome.SUCCESS
                    and router_ready_at is not None
                    and started_at >= router_ready_at
                ),
                default=None,
            )
        if app_success is None:
            errors.append("segmented RTO timeline is incomplete")
        else:
            detection_at = points["failure_detected"]
            election_at = points["primary_elected"]
            writable_at = points["primary_writable"]
            assert begin_at is not None
            assert detection_at is not None
            assert election_at is not None
            assert writable_at is not None
            assert router_ready_at is not None
            rto_segments_ms = {
                "detection": int((detection_at - begin_at).total_seconds() * 1000),
                "election": int((election_at - detection_at).total_seconds() * 1000),
                "backlog_fence": int((writable_at - election_at).total_seconds() * 1000),
                "router_refresh": int((router_ready_at - writable_at).total_seconds() * 1000),
                "application_reconnect": int((app_success - router_ready_at).total_seconds() * 1000),
                "total": int((app_success - begin_at).total_seconds() * 1000),
            }
            if any(value < 0 for value in rto_segments_ms.values()):
                errors.append("segmented RTO events are out of order")

    return {
        "scenario": scenario,
        "errors": errors,
        "ok": not errors,
        "rto_ms": rto_ms,
        "rto_segments_ms": rto_segments_ms,
        "metrics": metric_summary,
        "fencing": fencing if isinstance(fencing, dict) else {},
        "session": session if isinstance(session, dict) else {},
        "quorum_loss_windows": quorum_loss_windows,
        "during": {
            outcome.value: sum(record.outcome is outcome for record in during)
            for outcome in Outcome
        },
        "attempts_started_during_window": len(attempts_started_during),
    }
