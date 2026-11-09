from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.base import async_session_maker
from app.db.models.worker_stat import WorkerStat


async def increment_sent(n: int) -> None:
    async with async_session_maker() as s:
        row = await s.get(WorkerStat, "sent_total")
        if row is None:
            row = WorkerStat(key="sent_total", value=n)
            s.add(row)
        else:
            row.value = (row.value or 0) + n
        await s.commit()


async def set_last_run_at() -> None:
    async with async_session_maker() as s:
        row = await s.get(WorkerStat, "last_run_ts")
        ts = int(datetime.now(timezone.utc).timestamp())
        if row is None:
            row = WorkerStat(key="last_run_ts", value=ts)
            s.add(row)
        else:
            row.value = ts
        await s.commit()


async def get_stats() -> dict:
    async with async_session_maker() as s:
        rows = (await s.execute(select(WorkerStat))).scalars().all()
        out = {"sent_total": 0, "last_run_ts": 0}
        for r in rows:
            if r.key in out:
                out[r.key] = int(r.value or 0)
        if out["last_run_ts"]:
            out["last_run_at"] = datetime.fromtimestamp(
                out["last_run_ts"], tz=timezone.utc
            ).isoformat()
        else:
            out["last_run_at"] = None
        return out