"""Run the ARQ worker (Python 3.14 compatible)."""
import asyncio
from arq.worker import create_worker
from docere.worker import WorkerSettings

async def main():
    worker = create_worker(WorkerSettings)
    await worker.async_run()

asyncio.run(main())
