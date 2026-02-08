"""ARQ worker runner compatible with Python 3.14+.

Usage: python run_worker.py
"""

import asyncio

from arq.worker import create_worker, get_kwargs

from docere.worker import WorkerSettings


async def main() -> None:
    worker = create_worker(WorkerSettings)
    await worker.async_run()


if __name__ == "__main__":
    asyncio.run(main())
