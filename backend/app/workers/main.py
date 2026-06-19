"""Worker entrypoint — placeholder.

RESERVADO para ADR-003 (worker technology decision).
Current behavior: no-op loop that logs and sleeps.

The actual queue technology (asyncio / Celery / ARQ / N8N) will be
determined when the communications module (C-12) is built.
"""

from __future__ import annotations

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


async def main() -> None:
    """Main worker loop — placeholder.

    Logs a heartbeat every 10 seconds until interrupted.
    Replace with actual queue consumer when ADR-003 is resolved.
    """
    logger.info("Worker started (placeholder — no-op loop)")
    try:
        while True:
            logger.info("Worker heartbeat")
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
