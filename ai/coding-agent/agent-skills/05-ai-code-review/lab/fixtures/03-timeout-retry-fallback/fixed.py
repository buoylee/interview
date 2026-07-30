from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileResult:
    status: str
    profile: object
    attempts: int
    error: object


def fetch_profile(
    client,
    user_id,
    *,
    timeout_seconds=0.05,
    max_attempts=2,
):
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    for attempt in range(1, max_attempts + 1):
        try:
            profile = client.get(user_id, timeout=timeout_seconds)
            return ProfileResult("ok", profile, attempt, None)
        except TimeoutError:
            if attempt == max_attempts:
                return ProfileResult(
                    "degraded",
                    None,
                    attempt,
                    "upstream-timeout",
                )

    raise AssertionError("unreachable")
