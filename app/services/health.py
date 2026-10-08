import asyncio

from sqlalchemy import text

from app.core.config import Settings
from app.core.exceptions import DependencyUnavailableError
from app.db.session import ResourceManager


async def check_readiness(
    resources: ResourceManager,
    settings: Settings,
) -> dict[str, str]:
    async def check_database() -> None:
        async with resources.session_factory() as session:
            await session.execute(text("SELECT 1"))

    # Redis is provisioned for future workloads but is not on the request path
    # today, so it must not prevent the API from becoming ready.
    checks = {"postgres": check_database()}
    results = await asyncio.gather(
        *(asyncio.wait_for(check, timeout=settings.dependency_timeout_seconds) for check in checks.values()),
        return_exceptions=True,
    )
    failed = [name for name, result in zip(checks, results, strict=True) if isinstance(result, Exception)]
    if failed:
        raise DependencyUnavailableError(", ".join(failed))
    return {name: "ok" for name in checks}
