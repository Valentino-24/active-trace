"""ComunicacionWorker — async background worker for outbound communications.

Polls for Pendiente messages, renders templates, simulates sending (log-only
for MVP), and transitions through the state machine: Pendiente → Enviando →
Enviado | Error.

Runs as an asyncio task within the application lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.models.comunicacion import Comunicacion, EstadoComunicacion
from app.core.config import Settings
from app.core.security import decrypt as _decrypt

logger = logging.getLogger(__name__)


class ComunicacionWorker:
    """Background worker that processes pending communications.

    Polls the database for Pendiente messages, transitions them through
    the state machine, and simulates sending via logging.

    Attributes:
        session_factory: Async session factory for DB access.
        poll_interval: Seconds between polls (default 10).
        batch_size: Max messages to process per cycle (default 50).
        _stop_event: asyncio.Event for graceful shutdown.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        """Initialize the worker.

        Args:
            session_factory: Factory for creating DB sessions.
            settings: Application settings (for poll interval and batch size).
        """
        self._session_factory = session_factory
        self._poll_interval = (
            settings.worker_poll_interval if settings else 10
        )
        self._batch_size = (
            settings.worker_batch_size if settings else 50
        )
        self._stop_event = asyncio.Event()
        self._encryption_key: bytes | None = None
        if settings:
            self._encryption_key = settings.encryption_key.encode("utf-8")

    async def run(self) -> None:
        """Main worker loop: poll → process → sleep.

        Runs until stop() is called. Logs errors per batch but
        continues polling on failure (resilient loop).
        """
        logger.info(
            "ComunicacionWorker started (poll_interval=%ds, batch_size=%d)",
            self._poll_interval,
            self._batch_size,
        )

        while not self._stop_event.is_set():
            try:
                await self._process_batch()
            except Exception:
                logger.exception(
                    "ComunicacionWorker: error processing batch",
                )

            # Sleep with stop-event awareness (check every second)
            for _ in range(self._poll_interval):
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(1)

        logger.info("ComunicacionWorker stopped")

    async def stop(self) -> None:
        """Signal the worker to stop gracefully."""
        self._stop_event.set()
        logger.info("ComunicacionWorker: stop signal sent")

    async def _process_batch(self) -> None:
        """Fetch pending messages and process each one."""
        from sqlalchemy import select

        session: AsyncSession = self._session_factory()
        try:

            stmt = (
                select(Comunicacion)
                .where(Comunicacion.estado == EstadoComunicacion.Pendiente.value)
                .where(Comunicacion.deleted_at.is_(None))
                .order_by(Comunicacion.created_at.asc())
                .limit(self._batch_size)
            )
            result = await session.execute(stmt)
            pendientes = list(result.scalars().all())

            if not pendientes:
                return

            logger.info(
                "ComunicacionWorker: processing %d messages",
                len(pendientes),
            )

            for msg in pendientes:
                try:
                    await self._process_message(session, msg)
                except Exception:
                    logger.exception(
                        "ComunicacionWorker: error processing message %s",
                        msg.id,
                    )
                    # Mark as error
                    msg.estado = EstadoComunicacion.Error.value
                    await session.flush()

            await session.commit()

        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def _process_message(
        self,
        session: AsyncSession,
        msg: Comunicacion,
    ) -> None:
        """Process a single message through the state machine.

        1. Pendiente → Enviando
        2. Simulate send (log-only for MVP)
        3. Enviando → Enviado (or → Error on failure)

        Args:
            session: DB session.
            msg: The Comunicacion to process.
        """
        # Step 1: Pendiente → Enviando
        msg.estado = EstadoComunicacion.Enviando.value
        await session.flush()

        # Step 2: Simulate sending
        await self._simular_envio(msg)

        # Step 3: Enviando → Enviado
        msg.estado = EstadoComunicacion.Enviado.value
        msg.enviado_at = datetime.now(UTC)
        await session.flush()

    async def _simular_envio(self, msg: Comunicacion) -> None:
        """Simulate sending a message (log-only for MVP).

        In production, this would connect to SMTP/Mailgun/SendGrid.
        The method is isolated for easy replacement.

        Args:
            msg: The Comunicacion to "send".
        """
        # Decrypt email (for logging purposes, only hash is logged)
        email_plain = ""
        if self._encryption_key:
            try:
                email_plain = _decrypt(msg.destinatario, self._encryption_key)
            except Exception:
                email_plain = "<decryption-error>"

        logger.info(
            "comunicacion_enviar | msg_id=%s lote_id=%s estado=%s",
            msg.id,
            msg.lote_id,
            msg.estado,
        )

        # Log the send action (no PII in logs)
        logger.info(
            "Envío simulado: msg=%s asunto=%s",
            msg.id,
            msg.asunto[:50] if msg.asunto else "",
        )
