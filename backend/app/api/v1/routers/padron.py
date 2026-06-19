"""Padron router — import, preview, and manage student rosters.

Endpoints:
- POST /api/padron/moodle-sync — sync from Moodle Web Services
- POST /api/padron/preview — preview file import (no persist)
- POST /api/padron/import — confirm and persist file import
- DELETE /api/padron/materia/{materia_id} — soft-delete padron data
- GET /api/padron/versiones — list padron versions
- GET /api/padron/versiones/{version_id} — version detail with entries
"""

from __future__ import annotations

import csv
import io
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.core.security import encrypt
from app.models.padron import EntradaPadron, VersionPadron
from app.models.rbac import UserRole as UserRoleModel
from app.models.user import User
from app.repositories.padron_repository import (
    EntradaPadronRepository,
    VersionPadronRepository,
)
from app.schemas.padron import (
    EntradaPadronResponse,
    ImportRequest,
    ImportResponse,
    MoodleSyncRequest,
    PreviewError,
    PreviewResponse,
    PreviewRow,
    VaciarResponse,
    VersionPadronDetailResponse,
    VersionPadronListResponse,
    VersionPadronResponse,
)

router = APIRouter(tags=["padron"])

# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_encryption_key() -> bytes:
    """Load AES-256 encryption key from settings (lazy)."""
    from app.core.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    return settings.encryption_key.encode("utf-8")  # type: ignore[union-attr]


def _build_version_response(version: VersionPadron) -> dict[str, Any]:
    """Build a VersionPadronResponse-compatible dict from an ORM instance."""
    total_entradas = len(version.entradas) if version.entradas else 0
    total_sin_usuario = 0
    if version.entradas:
        total_sin_usuario = sum(
            1 for e in version.entradas if e.usuario_id is None
        )

    cargador = version.cargador
    return {
        "id": version.id,
        "materia_id": version.materia_id,
        "cohorte_id": version.cohorte_id,
        "activa": version.activa,
        "total_entradas": total_entradas,
        "total_sin_usuario": total_sin_usuario,
        "cargado_por": {
            "id": cargador.id,
            "display_name": cargador.display_name,
        },
        "cargado_at": version.cargado_at,
        "modo": version.modo,
    }


async def _audit_log(
    db: AsyncSession,
    current_user: User,
    accion: str,
    detalle: dict | None = None,
    filas_afectadas: int = 1,
) -> None:
    """Write an audit log entry."""
    from app.models.audit_log import AuditLog

    entry = AuditLog(
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        accion=accion,
        detalle=detalle,
        filas_afectadas=filas_afectadas,
    )
    db.add(entry)


def _parse_csv(content: bytes) -> tuple[list[dict[str, Any]], list[PreviewError]]:
    """Parse CSV content into rows.

    Detects encoding (utf-8-sig first, then latin-1) and separator
    (; then ,). Expects a header row with column names.

    Args:
        content: Raw bytes from uploaded file.

    Returns:
        Tuple of (rows list, errors list).
    """
    # Try utf-8-sig first, then latin-1
    text = None
    for enc in ["utf-8-sig", "latin-1"]:
        try:
            text = content.decode(enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if text is None:
        raise HTTPException(
            status_code=400,
            detail="No se pudo decodificar el archivo CSV. "
                   "Encoding no soportado.",
        )

    # Detect separator: count ; and , in header line
    lines = text.splitlines()
    if not lines:
        raise HTTPException(
            status_code=400, detail="El archivo CSV está vacío"
        )

    header = lines[0]
    semicolons = header.count(";")
    commas = header.count(",")
    delimiter = ";" if semicolons >= commas else ","
    if delimiter == "," and semicolons > 0:
        # Could be mixed — prefer ; if there are any
        delimiter = ";"

    reader = csv.DictReader(lines, delimiter=delimiter)
    rows: list[dict[str, Any]] = []
    errors: list[PreviewError] = []
    fila_num = 1  # header is row 1

    for row in reader:
        fila_num += 1
        if not row or all(v is None or v.strip() == "" for v in row.values()):
            continue  # skip empty rows

        nombre = _clean_csv_val(row.get("nombre") or row.get("Nombre", ""))
        apellidos = _clean_csv_val(
            row.get("apellidos") or row.get("apellido")
            or row.get("Apellidos") or row.get("Apellido", "")
        )
        email = _clean_csv_val(row.get("email") or row.get("Email", ""))
        comision = _clean_csv_val(
            row.get("comision") or row.get("comisión")
            or row.get("Comision") or row.get("Comisión")
        )
        regional = _clean_csv_val(
            row.get("regional") or row.get("Regional")
        )

        # Validate
        row_errors: list[PreviewError] = []
        if not nombre:
            row_errors.append(PreviewError(
                fila=fila_num, campo="nombre", mensaje="Nombre requerido"
            ))
        if not apellidos:
            row_errors.append(PreviewError(
                fila=fila_num, campo="apellidos", mensaje="Apellidos requeridos"
            ))
        if not email or "@" not in email:
            row_errors.append(PreviewError(
                fila=fila_num, campo="email", mensaje="Email inválido"
            ))

        if row_errors:
            errors.extend(row_errors)
        else:
            rows.append({
                "nombre": nombre,
                "apellidos": apellidos,
                "email": email,
                "comision": comision if comision else None,
                "regional": regional if regional else None,
            })

    return rows, errors


def _clean_csv_val(val: str | None) -> str:
    """Clean a CSV field value."""
    if val is None:
        return ""
    return val.strip().strip('"').strip("'")


def _parse_xlsx(
    content: bytes,
) -> tuple[list[dict[str, Any]], list[PreviewError]]:
    """Parse .xlsx content into rows using openpyxl.

    Reads the first sheet only. Expects a header row.

    Args:
        content: Raw bytes from uploaded file.

    Returns:
        Tuple of (rows list, errors list).
    """
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="openpyxl no está instalado. No se pueden procesar archivos .xlsx",
        )

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    if ws is None:
        raise HTTPException(
            status_code=400, detail="El archivo XLSX no tiene hojas"
        )

    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if header is None:
        raise HTTPException(
            status_code=400, detail="El archivo XLSX está vacío"
        )

    # Normalize header names
    col_map: dict[str, int] = {}
    for i, h in enumerate(header):
        if h is None:
            continue
        h_lower = str(h).strip().lower()
        if h_lower in ("nombre",):
            col_map["nombre"] = i
        elif h_lower in ("apellidos", "apellido"):
            col_map["apellidos"] = i
        elif h_lower in ("email", "correo", "e-mail"):
            col_map["email"] = i
        elif h_lower in ("comision", "comisión"):
            col_map["comision"] = i
        elif h_lower in ("regional",):
            col_map["regional"] = i

    rows: list[dict[str, Any]] = []
    errors: list[PreviewError] = []
    fila_num = 1

    for values in rows_iter:
        fila_num += 1
        vals = list(values)

        # Skip completely empty rows
        if not vals or all(v is None for v in vals):
            continue

        def _get(col: str) -> str:
            idx = col_map.get(col)
            if idx is None or idx >= len(vals) or vals[idx] is None:
                return ""
            return str(vals[idx]).strip()

        nombre = _get("nombre")
        apellidos = _get("apellidos")
        email = _get("email")
        comision = _get("comision")
        regional = _get("regional")

        row_errors: list[PreviewError] = []
        if not nombre:
            row_errors.append(PreviewError(
                fila=fila_num, campo="nombre", mensaje="Nombre requerido"
            ))
        if not apellidos:
            row_errors.append(PreviewError(
                fila=fila_num, campo="apellidos", mensaje="Apellidos requeridos"
            ))
        if not email or "@" not in email:
            row_errors.append(PreviewError(
                fila=fila_num, campo="email", mensaje="Email inválido"
            ))

        if row_errors:
            errors.extend(row_errors)
        else:
            rows.append({
                "nombre": nombre,
                "apellidos": apellidos,
                "email": email,
                "comision": comision if comision else None,
                "regional": regional if regional else None,
            })

    wb.close()
    return rows, errors


async def _verify_materia_cohorte(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    materia_id: uuid.UUID,
    cohorte_id: uuid.UUID,
) -> None:
    """Verify that materia and cohorte exist and belong to the tenant."""
    from app.models.cohorte import Cohorte
    from app.models.materia import Materia

    mat_stmt = select(Materia).where(
        Materia.id == materia_id,
        Materia.tenant_id == tenant_id,
        Materia.deleted_at.is_(None),
    )
    mat_result = await db.execute(mat_stmt)
    if mat_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail=f"Materia {materia_id} no encontrada en el tenant",
        )

    coh_stmt = select(Cohorte).where(
        Cohorte.id == cohorte_id,
        Cohorte.tenant_id == tenant_id,
        Cohorte.deleted_at.is_(None),
    )
    coh_result = await db.execute(coh_stmt)
    if coh_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail=f"Cohorte {cohorte_id} no encontrada en el tenant",
        )


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post(
    "/moodle-sync",
    response_model=ImportResponse,
    status_code=201,
    dependencies=[Depends(require_permission("padron:importar"))],
)
async def moodle_sync(
    body: MoodleSyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync student roster from Moodle Web Services.

    Creates a new padron version with data fetched from the configured
    Moodle instance. Requires MOODLE_BASE_URL and MOODLE_TOKEN env vars.
    """
    moodle_base_url = os.environ.get("MOODLE_BASE_URL")
    moodle_token = os.environ.get("MOODLE_TOKEN")

    if not moodle_base_url or not moodle_token:
        raise HTTPException(
            status_code=400,
            detail="Moodle WS no configurado para este tenant. "
                   "Configure MOODLE_BASE_URL y MOODLE_TOKEN.",
        )

    await _verify_materia_cohorte(
        db, current_user.tenant_id, body.materia_id, body.cohorte_id,
    )

    # Build Moodle client and sync
    from app.integrations.moodle_ws import MoodleClient

    client = MoodleClient(
        base_url=moodle_base_url,
        token=moodle_token,
    )
    try:
        alumnos = await client.sync_alumnos(
            materia_id=str(body.materia_id),
            cohorte_id=str(body.cohorte_id),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error al conectar con Moodle: {exc}. "
                   "Intente nuevamente más tarde o use importación manual.",
        )

    if not alumnos:
        raise HTTPException(
            status_code=400,
            detail="Moodle no devolvió alumnos para esta materia/cohorte. "
                   "Verifique la configuración del curso.",
        )

    # Create version + entries in transaction
    version_repo = VersionPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    version = await version_repo.create_version(
        materia_id=body.materia_id,
        cohorte_id=body.cohorte_id,
        cargado_por=current_user.id,
        modo="moodle_ws",
    )

    entrada_repo = EntradaPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    total, sin_usuario = await entrada_repo.bulk_create_from_import(
        version_id=version.id,
        filas=alumnos,
    )

    # Audit log
    await _audit_log(
        db, current_user,
        accion="PADRON_CARGAR",
        detalle={
            "version_id": str(version.id),
            "materia_id": str(body.materia_id),
            "cohorte_id": str(body.cohorte_id),
            "modo": "moodle_ws",
            "total_entradas": total,
            "total_sin_usuario": sin_usuario,
        },
        filas_afectadas=total,
    )

    return ImportResponse(
        version_id=version.id,
        materia_id=body.materia_id,
        cohorte_id=body.cohorte_id,
        total_entradas=total,
        total_sin_usuario=sin_usuario,
        fecha=version.cargado_at,
        modo="moodle_ws",
    )


@router.post(
    "/preview",
    response_model=PreviewResponse,
    dependencies=[Depends(require_permission("padron:importar"))],
)
async def preview_import(
    archivo: UploadFile,
    materia_id: str = Query(...),
    cohorte_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview a padron file import (xlsx or csv) without persisting.

    Parses the uploaded file, validates rows, and returns the preview.
    Nothing is saved to the database.
    """
    # Verify materia/cohorte exist
    await _verify_materia_cohorte(
        db, current_user.tenant_id,
        uuid.UUID(materia_id), uuid.UUID(cohorte_id),
    )

    content = await archivo.read()
    if not content:
        raise HTTPException(
            status_code=400, detail="El archivo está vacío"
        )

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="El archivo excede el tamaño máximo de 10 MB",
        )

    filename = (archivo.filename or "").lower()

    if filename.endswith(".csv"):
        rows, errors = _parse_csv(content)
    elif filename.endswith(".xlsx"):
        rows, errors = _parse_xlsx(content)
    else:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Use archivos .csv o .xlsx",
        )

    if len(rows) > 10_000:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo contiene {len(rows)} filas. "
                   f"Máximo permitido: 10.000",
        )

    # Detect columns from first row
    columnas = ["nombre", "apellidos", "email"]
    if rows and rows[0].get("comision"):
        columnas.append("comision")
    if rows and rows[0].get("regional"):
        columnas.append("regional")

    filas_preview = [
        PreviewRow(
            fila=i + 1,
            nombre=r["nombre"],
            apellidos=r["apellidos"],
            email=r["email"],
            comision=r.get("comision"),
            regional=r.get("regional"),
        )
        for i, r in enumerate(rows)
    ]

    return PreviewResponse(
        total_filas=len(rows),
        columnas_detectadas=columnas,
        filas=filas_preview,
        errores=errors,
    )


@router.post(
    "/import",
    response_model=ImportResponse,
    status_code=201,
    dependencies=[Depends(require_permission("padron:importar"))],
)
async def confirm_import(
    body: ImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm and persist a padron file import.

    Creates a new version and all student entries in a single transaction.
    Previous active version for the same (materia, cohorte) is deactivated.
    """
    await _verify_materia_cohorte(
        db, current_user.tenant_id, body.materia_id, body.cohorte_id,
    )

    if not body.filas:
        raise HTTPException(
            status_code=400,
            detail="No se enviaron filas para importar",
        )

    if len(body.filas) > 10_000:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo 10.000 filas por import. Enviadas: {len(body.filas)}",
        )

    # Create version
    version_repo = VersionPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    version = await version_repo.create_version(
        materia_id=body.materia_id,
        cohorte_id=body.cohorte_id,
        cargado_por=current_user.id,
        modo="archivo",
    )

    # Create entries
    filas_data = [f.model_dump() for f in body.filas]
    entrada_repo = EntradaPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    total, sin_usuario = await entrada_repo.bulk_create_from_import(
        version_id=version.id,
        filas=filas_data,
    )

    # Audit log
    await _audit_log(
        db, current_user,
        accion="PADRON_CARGAR",
        detalle={
            "version_id": str(version.id),
            "materia_id": str(body.materia_id),
            "cohorte_id": str(body.cohorte_id),
            "modo": "archivo",
            "total_entradas": total,
            "total_sin_usuario": sin_usuario,
        },
        filas_afectadas=total,
    )

    return ImportResponse(
        version_id=version.id,
        materia_id=body.materia_id,
        cohorte_id=body.cohorte_id,
        total_entradas=total,
        total_sin_usuario=sin_usuario,
        fecha=version.cargado_at,
        modo="archivo",
    )


@router.delete(
    "/materia/{materia_id}",
    response_model=VaciarResponse,
    dependencies=[Depends(require_permission("padron:importar"))],
)
async def vaciar_materia(
    materia_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete all padron data for a materia.

    Scope depends on the user's role:
    - PROFESOR: only versions they imported.
    - COORDINADOR / ADMIN: all versions in the tenant.
    """
    # Determine scope from role codes (load fresh from db session)
    role_stmt = select(UserRoleModel).where(
        UserRoleModel.user_id == current_user.id,
        UserRoleModel.tenant_id == current_user.tenant_id,
        UserRoleModel.deleted_at.is_(None),
    ).options(joinedload(UserRoleModel.role))
    role_result = await db.execute(role_stmt)
    user_role_codes = {ur.role.codigo for ur in role_result.scalars().all()}

    is_profesor_only = (
        "PROFESOR" in user_role_codes
        and "COORDINADOR" not in user_role_codes
        and "ADMIN" not in user_role_codes
    )

    cargado_por = current_user.id if is_profesor_only else None

    version_repo = VersionPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    versiones_afectadas = await version_repo.soft_delete_by_materia(
        materia_id=materia_id,
        cargado_por=cargado_por,
    )

    entrada_repo = EntradaPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    entradas_afectadas = await entrada_repo.soft_delete_by_materia(
        materia_id=materia_id,
        cargado_por=cargado_por,
    )

    # Audit log
    await _audit_log(
        db, current_user,
        accion="PADRON_VACIAR",
        detalle={
            "materia_id": str(materia_id),
            "versiones_afectadas": versiones_afectadas,
            "entradas_afectadas": entradas_afectadas,
            "scope": "propio" if is_profesor_only else "tenant",
        },
        filas_afectadas=entradas_afectadas,
    )

    return VaciarResponse(
        mensaje="Datos de la materia eliminados",
        materia_id=materia_id,
        versiones_desactivadas=versiones_afectadas,
        entradas_eliminadas=entradas_afectadas,
    )


@router.get(
    "/versiones",
    response_model=VersionPadronListResponse,
    dependencies=[Depends(require_permission("padron:importar"))],
)
async def list_versiones(
    materia_id: uuid.UUID | None = Query(default=None),
    cohorte_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List padron versions with optional filters."""
    repo = VersionPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    versions, total = await repo.list_versiones(
        materia_id=materia_id,
        cohorte_id=cohorte_id,
        skip=skip,
        limit=limit,
    )

    items = [_build_version_response(v) for v in versions]
    return VersionPadronListResponse(
        items=[VersionPadronResponse(**i) for i in items],
        total=total,
    )


@router.get(
    "/versiones/{version_id}",
    response_model=VersionPadronDetailResponse,
    dependencies=[Depends(require_permission("padron:importar"))],
)
async def get_version_detail(
    version_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get padron version detail with paginated entries."""
    version_repo = VersionPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    version = await version_repo.get_version_detail(version_id)
    if version is None:
        raise HTTPException(
            status_code=404, detail="Versión de padrón no encontrada"
        )

    entrada_repo = EntradaPadronRepository(
        session=db, tenant_id=current_user.tenant_id,
    )
    entradas, total_entradas = await entrada_repo.list_entradas_by_version(
        version_id=version_id,
        skip=skip,
        limit=limit,
    )

    entradas_resp = [
        EntradaPadronResponse(
            id=e.id,
            nombre=e.nombre,
            apellidos=e.apellidos,
            email_hash=e.email_hash,
            comision=e.comision,
            regional=e.regional,
            tiene_usuario=e.usuario_id is not None,
        )
        for e in entradas
    ]

    cargador = version.cargador
    return VersionPadronDetailResponse(
        id=version.id,
        materia_id=version.materia_id,
        cohorte_id=version.cohorte_id,
        activa=version.activa,
        cargado_por={
            "id": cargador.id,
            "display_name": cargador.display_name,
        },
        cargado_at=version.cargado_at,
        modo=version.modo,
        entradas=entradas_resp,
        total_entradas=total_entradas,
    )
