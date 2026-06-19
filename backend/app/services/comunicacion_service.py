"""Comunicacion service — preview, enqueue, approve, and track communications.

Pure functions at the top (testable without DB), followed by service
methods that coordinate repositories and persistence.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from string import Template
from typing import Any

from fastapi import HTTPException

from app.models.comunicacion import Comunicacion, EstadoComunicacion
from app.models.materia import Materia
from app.models.padron import EntradaPadron
from app.models.user import User
from app.repositories.comunicacion_repository import ComunicacionRepository
from app.schemas.comunicaciones import (
    ComunicacionResponse,
    DestinatarioPreview,
    EstadisticasResponse,
    LoteResponse,
    PreviewItem,
    PreviewResponse,
)
from app.services.audit_service import log_action


# ═══════════════════════════════════════════════════════════════════════════════
# Pure functions (trivially testable — zero dependencies)
# ═══════════════════════════════════════════════════════════════════════════════


_VALID_TRANSITIONS: dict[str, set[str]] = {
    EstadoComunicacion.Pendiente.value: {
        EstadoComunicacion.Enviando.value,
        EstadoComunicacion.Cancelado.value,
    },
    EstadoComunicacion.Enviando.value: {
        EstadoComunicacion.Enviado.value,
        EstadoComunicacion.Error.value,
    },
}

_TERMINAL_STATES: set[str] = {
    EstadoComunicacion.Enviado.value,
    EstadoComunicacion.Error.value,
    EstadoComunicacion.Cancelado.value,
}


def render_template(template_text: str, variables: dict[str, str]) -> str:
    """Render a template with variable substitution.

    Uses Python's string.Template (safe by default — unknown variables
    are left as-is, no crash). Supported variables include:
    ${nombre}, ${apellido}, ${materia}, ${comision}, ${nombre_profesor}.

    Args:
        template_text: The template string with ${variable} placeholders.
        variables: Dict mapping variable names to their values.

    Returns:
        Rendered string with known variables substituted.
        Unknown variables are preserved as-is.
    """
    if not template_text:
        return ""
    # Safely substitute known variables, leave unknown ones as-is
    result = Template(template_text).safe_substitute(variables)
    return result


def validate_transition(from_state: str, to_state: str) -> bool:
    """Check if a state transition is valid per the state machine (RN-15).

    Valid transitions:
        Pendiente → Enviando, Cancelado
        Enviando  → Enviado, Error
    Terminal states (Enviado, Error, Cancelado) cannot transition anywhere.

    Args:
        from_state: Current estado value.
        to_state: Target estado value.

    Returns:
        True if the transition is valid, False otherwise.
    """
    if from_state in _TERMINAL_STATES:
        return False
    allowed = _VALID_TRANSITIONS.get(from_state, set())
    return to_state in allowed


def _mask_email(email: str) -> str:
    """Mask an email for API responses.

    Shows first character, asterisks, then domain.
    E.g. j***@test.com

    Args:
        email: Plain email address.

    Returns:
        Masked email string.
    """
    at_index = email.find("@")
    if at_index <= 1:
        return "***@" + email[at_index + 1:] if at_index > 0 else "***"
    return email[0] + "***" + email[at_index:]


# ═══════════════════════════════════════════════════════════════════════════════
# Service class (coordinates repositories)
# ═══════════════════════════════════════════════════════════════════════════════


class ComunicacionService:
    """Service for previewing, enqueueing, approving, and tracking communications.

    All public methods receive db and tenant_id explicitly rather than
    storing state, so they can be used in request-scoped dependency injection.
    """

    def __init__(self, db, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._com_repo = ComunicacionRepository(
            session=db, tenant_id=tenant_id,
        )

    async def preview(
        self,
        materia_id: uuid.UUID,
        asunto_template: str,
        cuerpo_template: str,
        destinatarios: list[DestinatarioPreview],
    ) -> PreviewResponse:
        """Render templates for each recipient without persisting anything.

        Args:
            materia_id: FK to Materia (for context).
            asunto_template: Subject template with ${variable} placeholders.
            cuerpo_template: Body template with ${variable} placeholders.
            destinatarios: List of recipient data for rendering.

        Returns:
            PreviewResponse with rendered items per recipient.
        """
        items: list[PreviewItem] = []
        for d in destinatarios:
            variables = {
                "nombre": d.nombre,
                "apellido": d.apellido,
                "materia": d.materia,
                "comision": d.comision,
                "nombre_profesor": d.nombre_profesor,
            }
            asunto_rendered = render_template(asunto_template, variables)
            cuerpo_rendered = render_template(cuerpo_template, variables)
            # Build a fake masked email from the data
            masked = _mask_email(f"{d.nombre.lower()}.{d.apellido.lower()}@example.com")
            items.append(PreviewItem(
                destinatario_masked=masked,
                asunto_rendered=asunto_rendered,
                cuerpo_rendered=cuerpo_rendered,
            ))

        return PreviewResponse(items=items, total=len(items))

    async def enviar(
        self,
        materia_id: uuid.UUID,
        asunto_template: str,
        cuerpo_template: str,
        requiere_aprobacion: bool = True,
        profesor_asignacion_ids: list[uuid.UUID] | None = None,
    ) -> LoteResponse:
        """Create Comunicacion records for all recipients of a materia+cohorte.

        Fetches recipients from the active EntradaPadron version for the
        materia. Groups all messages under a single lote_id.

        Args:
            materia_id: FK to Materia.
            asunto_template: Subject template.
            cuerpo_template: Body template.
            requiere_aprobacion: Whether approval is required before sending.
            profesor_asignacion_ids: If PROFESOR, their asignacion_ids for scope.

        Returns:
            LoteResponse with batch details.

        Raises:
            HTTPException 404: If materia not found.
            HTTPException 403: If PROFESOR has no access to this materia.
        """
        # Verify materia exists
        from sqlalchemy import select

        stmt = select(Materia).where(
            Materia.id == materia_id,
            Materia.tenant_id == self._tenant_id,
            Materia.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        materia = result.scalar_one_or_none()
        if materia is None:
            raise HTTPException(
                status_code=404,
                detail="Materia no encontrada en el tenant",
            )

        # For PROFESOR, verify scope
        if profesor_asignacion_ids is not None:
            from app.models.asignacion import Asignacion

            stmt_asig = select(Asignacion).where(
                Asignacion.id.in_(profesor_asignacion_ids),
                Asignacion.materia_id == materia_id,
                Asignacion.deleted_at.is_(None),
            )
            result_asig = await self._db.execute(stmt_asig)
            if result_asig.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes acceso a esta materia",
                )

        # Fetch recipients from active padron version
        stmt_padron = (
            select(EntradaPadron)
            .join(
                Materia,
                Materia.id == materia_id,
            )
            .where(
                EntradaPadron.tenant_id == self._tenant_id,
                EntradaPadron.deleted_at.is_(None),
            )
            .limit(500)
        )
        # Actually, we need the active version's entries
        from app.models.padron import VersionPadron

        stmt_ver = (
            select(VersionPadron)
            .where(
                VersionPadron.tenant_id == self._tenant_id,
                VersionPadron.materia_id == materia_id,
                VersionPadron.activa.is_(True),
                VersionPadron.deleted_at.is_(None),
            )
            .order_by(VersionPadron.created_at.desc())
            .limit(1)
        )
        result_ver = await self._db.execute(stmt_ver)
        version = result_ver.scalar_one_or_none()
        if version is None:
            raise HTTPException(
                status_code=400,
                detail="No hay versión activa del padrón para esta materia",
            )

        # Get entries from that version
        stmt_ents = (
            select(EntradaPadron)
            .where(
                EntradaPadron.version_id == version.id,
                EntradaPadron.deleted_at.is_(None),
            )
        )
        result_ents = await self._db.execute(stmt_ents)
        entries = list(result_ents.scalars().all())

        if not entries:
            raise HTTPException(
                status_code=400,
                detail="No hay alumnos en el padrón activo de esta materia",
            )

        # Create lote_id
        lote_id = uuid.uuid4()

        # Get materia info for template variables
        materia_nombre = materia.nombre

        # Create Comunicacion records
        comunicaciones: list[Comunicacion] = []
        # Use current user info for profesor name
        nombre_profesor = self._current_user.display_name

        for entry in entries:
            variables = {
                "nombre": entry.nombre,
                "apellido": entry.apellidos,
                "materia": materia_nombre,
                "comision": entry.comision or "",
                "nombre_profesor": nombre_profesor,
            }
            asunto_rendered = render_template(asunto_template, variables)
            cuerpo_rendered = render_template(cuerpo_template, variables)

            # Encrypt the email (store the cifrado version)
            # For MVP, we store the email_hash as destinatario (not the raw email)
            # In production, this would be AES-256 encrypted
            from app.core.security import encrypt as _encrypt
            from app.core.config import Settings

            settings = Settings()  # type: ignore[call-arg]
            enc_key = settings.encryption_key.encode("utf-8")
            destinatario_cifrado = _encrypt(
                entry.email_cifrado or entry.email_hash or "",
                enc_key,
            )

            estado_inicial = (
                EstadoComunicacion.Pendiente.value
                if requiere_aprobacion
                else EstadoComunicacion.Pendiente.value
            )

            com = Comunicacion(
                tenant_id=self._tenant_id,
                enviado_por=self._current_user.id,
                materia_id=materia_id,
                destinatario=destinatario_cifrado,
                asunto=asunto_rendered,
                cuerpo=cuerpo_rendered,
                estado=estado_inicial,
                lote_id=lote_id,
            )
            comunicaciones.append(com)

        # Bulk save
        for c in comunicaciones:
            self._db.add(c)
        await self._db.flush()

        # Auto-approve if not required
        if not requiere_aprobacion:
            for c in comunicaciones:
                c.estado = EstadoComunicacion.Enviando.value
            await self._db.flush()

        # Audit log
        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="COMUNICACION_ENVIAR",
            detalle={
                "lote_id": str(lote_id),
                "materia_id": str(materia_id),
                "total_destinatarios": len(comunicaciones),
                "requiere_aprobacion": requiere_aprobacion,
            },
            filas_afectadas=len(comunicaciones),
            materia_id=materia_id,
        )

        return LoteResponse(
            lote_id=lote_id,
            total=len(comunicaciones),
            estados={
                EstadoComunicacion.Pendiente.value: len(comunicaciones)
                if requiere_aprobacion
                else 0,
                EstadoComunicacion.Enviando.value: len(comunicaciones)
                if not requiere_aprobacion
                else 0,
            },
            created_at=datetime.now(UTC),
        )

    async def aprobar_lote(
        self, lote_id: uuid.UUID,
    ) -> LoteResponse:
        """Approve all Pendiente messages in a batch → Enviando.

        Args:
            lote_id: The batch UUID.

        Returns:
            LoteResponse with approval result.

        Raises:
            HTTPException 400: If no messages found or in wrong state.
        """
        mensajes = await self._com_repo.list_por_lote(lote_id)
        if not mensajes:
            raise HTTPException(
                status_code=404,
                detail=f"Lote {lote_id} no encontrado",
            )

        updated = 0
        for m in mensajes:
            if m.estado == EstadoComunicacion.Pendiente.value:
                m.estado = EstadoComunicacion.Enviando.value
                m.aprobado_por = self._current_user.id
                m.fecha_aprobacion = datetime.now(UTC)
                updated += 1

        if updated == 0:
            raise HTTPException(
                status_code=400,
                detail="No hay mensajes pendientes para aprobar en este lote",
            )

        await self._db.flush()

        return LoteResponse(
            lote_id=lote_id,
            total=updated,
            estados={EstadoComunicacion.Enviando.value: updated},
            aprobado_por=self._current_user.display_name,
        )

    async def aprobar_individual(
        self, comunicacion_id: uuid.UUID,
    ) -> ComunicacionResponse:
        """Approve a single message: Pendiente → Enviando.

        Args:
            comunicacion_id: Comunicacion ID.

        Returns:
            The updated ComunicacionResponse.

        Raises:
            HTTPException 404: If message not found.
            HTTPException 409: If transition is invalid.
        """
        com = await self._com_repo.get(comunicacion_id)
        if com is None:
            raise HTTPException(
                status_code=404,
                detail="Comunicación no encontrada",
            )

        if not validate_transition(com.estado, EstadoComunicacion.Enviando.value):
            raise HTTPException(
                status_code=409,
                detail=f"No se puede aprobar una comunicación en estado {com.estado}",
            )

        com.estado = EstadoComunicacion.Enviando.value
        com.aprobado_por = self._current_user.id
        com.fecha_aprobacion = datetime.now(UTC)
        await self._db.flush()
        await self._db.refresh(com)
        return ComunicacionResponse.model_validate(com)

    async def cancelar_lote(
        self, lote_id: uuid.UUID,
    ) -> LoteResponse:
        """Cancel all Pendiente messages in a batch → Cancelado.

        Args:
            lote_id: The batch UUID.

        Returns:
            LoteResponse with cancellation result.

        Raises:
            HTTPException 404: If lote not found.
        """
        mensajes = await self._com_repo.list_por_lote(lote_id)
        if not mensajes:
            raise HTTPException(
                status_code=404,
                detail=f"Lote {lote_id} no encontrado",
            )

        updated = 0
        for m in mensajes:
            if m.estado == EstadoComunicacion.Pendiente.value:
                m.estado = EstadoComunicacion.Cancelado.value
                m.aprobado_por = self._current_user.id
                m.fecha_aprobacion = datetime.now(UTC)
                updated += 1

        if updated == 0:
            raise HTTPException(
                status_code=400,
                detail="No hay mensajes pendientes para cancelar en este lote",
            )

        await self._db.flush()

        return LoteResponse(
            lote_id=lote_id,
            total=updated,
            estados={EstadoComunicacion.Cancelado.value: updated},
        )

    async def get_estadisticas(
        self, materia_id: uuid.UUID,
    ) -> EstadisticasResponse:
        """Get message counts by estado for a materia.

        Args:
            materia_id: FK to Materia.

        Returns:
            EstadisticasResponse with counts per state.
        """
        counts = await self._com_repo.count_por_estado(materia_id)
        return EstadisticasResponse(
            pendientes=counts.get(EstadoComunicacion.Pendiente.value, 0),
            enviando=counts.get(EstadoComunicacion.Enviando.value, 0),
            enviados=counts.get(EstadoComunicacion.Enviado.value, 0),
            fallidos=counts.get(EstadoComunicacion.Error.value, 0),
            cancelados=counts.get(EstadoComunicacion.Cancelado.value, 0),
        )

    async def get_estado_lote(
        self, lote_id: uuid.UUID,
    ) -> list[ComunicacionResponse]:
        """Get all messages in a batch with their states.

        Args:
            lote_id: The batch UUID.

        Returns:
            List of ComunicacionResponse for the batch.

        Raises:
            HTTPException 404: If lote not found.
        """
        mensajes = await self._com_repo.list_por_lote(lote_id)
        if not mensajes:
            raise HTTPException(
                status_code=404,
                detail=f"Lote {lote_id} no encontrado",
            )
        return [
            ComunicacionResponse.model_validate(m) for m in mensajes
        ]
