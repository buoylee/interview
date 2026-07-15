from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PoolBudget:
    instances: int
    workers: int
    pool_size: int
    max_overflow: int

    def __post_init__(self) -> None:
        if (
            self.instances <= 0
            or self.workers <= 0
            or self.pool_size <= 0
            or self.max_overflow < 0
        ):
            raise ValueError(
                "instances, workers, and pool_size must be positive; "
                "max_overflow cannot be negative"
            )

    @property
    def connection_ceiling(self) -> int:
        return self.instances * self.workers * (self.pool_size + self.max_overflow)

    def assert_fits(self, database_budget: int) -> None:
        if self.connection_ceiling > database_budget:
            raise ValueError(
                f"{self.connection_ceiling} exceeds database budget {database_budget}"
            )
