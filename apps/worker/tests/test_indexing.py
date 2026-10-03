from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from paxrelay_worker.jobs.indexing import ProviderIndexJob, _consecutive_failures


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        (["succeeded", "provider_error"], 0),
        (["timeout", "provider_error", "succeeded", "timeout"], 2),
        (["unknown", "cancelled"], 2),
        ([], 0),
    ],
)
def test_consecutive_failure_count_stops_at_latest_success(
    states: list[str], expected: int
) -> None:
    assert _consecutive_failures(states) == expected


@pytest.mark.asyncio
async def test_provider_index_queries_compile_for_postgres() -> None:
    class CompileOnlySession:
        statements: list[str]

        def __init__(self) -> None:
            self.statements = []

        async def execute(self, statement):
            self.statements.append(
                str(statement.compile(dialect=postgresql.dialect()))
            )
            return self

        def all(self) -> list[object]:
            return []

    job = object.__new__(ProviderIndexJob)
    job.settings = SimpleNamespace(
        app_env="staging",
        provider_metrics_trailing_attempts=100,
    )
    session = CompileOnlySession()
    cutoff = datetime.now(UTC).replace(tzinfo=None)

    await job._load_totals(session, cutoff)
    await job._load_trailing_failures(session, cutoff, ["service-id"])

    assert len(session.statements) == 2
    assert all("execution_attempts" in statement for statement in session.statements)
