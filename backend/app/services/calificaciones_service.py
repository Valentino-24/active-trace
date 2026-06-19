"""Calificaciones service — grade import, approval derivation, and finalizacion.

Contains the core business logic for:
- Parsing LMS grade files (preview flow)
- Importing confirmed grades with approval derivation
- Detecting ungraded submissions (finalizacion flow)

Pure functions at the top (testable without DB), followed by
service methods that coordinate repositories and persistence.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from typing import Any

from fastapi import HTTPException, UploadFile

from app.core.security import encrypt as _encrypt  # noqa: F401
from app.models.calificacion import Calificacion
from app.models.padron import EntradaPadron
from app.models.user import User
from app.repositories.calificacion_repository import CalificacionRepository
from app.repositories.umbral_repository import UmbralMateriaRepository
from app.schemas.calificacion import (
    FinalizacionResponse,
    FinalizacionRow,
    ImportResponse,
    PreviewColumn,
    PreviewError,
    PreviewResponse,
    PreviewRow,
)
from app.services.audit_service import log_action


# ═══════════════════════════════════════════════════════════════════════════════
# Pure functions (trivially testable — zero dependencies)
# ═══════════════════════════════════════════════════════════════════════════════


def calcular_aprobado(
    nota: float | None,
    nota_textual: str | None,
    umbral_pct: float,
    max_nota: float,
    valores_aprobatorios: list[str] | None,
) -> bool:
    """Determine whether a grade is passing.

    Rules:
    - Numeric (nota is not None): passes if nota >= umbral_pct * max_nota.
    - Textual (nota_textual is not None): passes if the value is in
      the valores_aprobatorios list.
    - Nil (both None): never passes → False.

    Args:
        nota: Numeric grade value.
        nota_textual: Textual grade value.
        umbral_pct: Minimum percentage of max_nota (e.g. 0.60).
        max_nota: Maximum possible grade (e.g. 100).
        valores_aprobatorios: List of passing textual values.

    Returns:
        True if the grade passes, False otherwise.
    """
    if nota is not None:
        return nota >= umbral_pct * max_nota
    if nota_textual is not None:
        return nota_textual in (valores_aprobatorios or [])
    return False


def detectar_columna(nombre_columna: str) -> tuple[str, str, float | None]:
    """Classify an LMS column by name.

    RN-01: Column names ending in '(Real)' are numeric.
    RN-02: Everything else is textual.

    Args:
        nombre_columna: Raw column header from the LMS file.

    Returns:
        Tuple of (cleaned_name, tipo, max_nota_hint).
        - cleaned_name: Column name with '(Real)' suffix stripped (if present).
        - tipo: 'numerica' or 'textual'.
        - max_nota_hint: Always None here; caller extracts it from metadata rows.
    """
    pattern = re.compile(r"^(.*)\s*\(Real\)\s*$", re.IGNORECASE)
    match = pattern.match(nombre_columna)
    if match:
        return (match.group(1).strip(), "numerica", None)
    return (nombre_columna.strip(), "textual", None)


def parsear_archivo_lms(
    content: bytes,
    filename: str,
) -> PreviewResponse:
    """Parse an LMS grade file (.xlsx or .csv) and return a preview.

    Detects column types (RN-01/RN-02), extracts max_nota from
    "Calificación máxima" rows, and parses student data rows.

    Args:
        content: Raw file content as bytes.
        filename: Original filename for format detection.

    Returns:
        PreviewResponse with detected columns, parsed rows, and errors.

    Raises:
        HTTPException 400: If the format is unsupported or the file is empty.
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(".csv"):
        return _parse_csv_grades(content)
    elif filename_lower.endswith(".xlsx"):
        return _parse_xlsx_grades(content)
    else:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Use .xlsx o .csv",
        )


def _parse_csv_grades(content: bytes) -> PreviewResponse:
    """Parse grades from a CSV file."""
    # Detect encoding
    text = _decode_content(content)
    lines = text.splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    header = lines[0]
    # Detect delimiter
    delimiter = _detect_delimiter(header)

    reader = csv.DictReader(lines, delimiter=delimiter)
    fieldnames = reader.fieldnames or []

    # Classify columns
    columnas: list[PreviewColumn] = []
    max_nota_map: dict[str, float] = {}

    for fn in fieldnames:
        fn_lower = fn.strip().lower()
        # Skip metadata/student columns
        if fn_lower in ("nombre", "apellidos", "apellido", "email", "dirección de correo"):
            continue
        nombre, tipo, _ = detectar_columna(fn)
        columnas.append(PreviewColumn(
            nombre=nombre,
            tipo=tipo,  # type: ignore[arg-type]
            max_nota=None,
        ))

    # Parse rows
    filas: list[PreviewRow] = []
    errores: list[PreviewError] = []
    fila_num = 1

    for row in reader:
        fila_num += 1
        email = _clean_val(row.get("email")
                           or row.get("Email")
                           or row.get("Dirección de correo")
                           or row.get("dirección de correo")
                           or "")

        nombre = _clean_val(row.get("nombre") or row.get("Nombre") or "")
        apellidos = _clean_val(row.get("apellidos") or row.get("Apellidos")
                                or row.get("apellido") or row.get("Apellido") or "")

        if not email or "@" not in email:
            errores.append(PreviewError(
                fila=fila_num, columna="email",
                mensaje="Email inválido o faltante",
            ))
            continue

        valores: dict[str, Any] = {}
        for col in columnas:
            raw = _clean_val(row.get(col.nombre, ""))
            if col.tipo == "numerica":
                try:
                    valores[col.nombre] = float(raw) if raw else None
                except (ValueError, TypeError):
                    valores[col.nombre] = None
                    errores.append(PreviewError(
                        fila=fila_num,
                        columna=col.nombre,
                        mensaje=f"Valor no numérico: '{raw}'",
                    ))
            else:
                valores[col.nombre] = raw if raw else None

        filas.append(PreviewRow(
            fila=fila_num,
            email=email,
            nombre=nombre,
            apellidos=apellidos,
            valores=valores,
        ))

    # Extract max_nota from known patterns (Calificación máxima rows)
    max_nota_hints = _extract_max_nota(lines, delimiter)

    # Apply max_nota hints to numeric columns
    for col in columnas:
        if col.tipo == "numerica" and col.nombre in max_nota_hints:
            col.max_nota = max_nota_hints[col.nombre]

    return PreviewResponse(
        columnas=columnas,
        filas=filas,
        errores=errores,
        total_filas=len(filas),
    )


def _parse_xlsx_grades(content: bytes) -> PreviewResponse:
    """Parse grades from an .xlsx file."""
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="openpyxl no está instalado",
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

    # Build column map
    col_indices: dict[str, int] = {}
    raw_headers: dict[int, str] = {}
    for i, h in enumerate(header):
        if h is None:
            continue
        h_str = str(h).strip()
        raw_headers[i] = h_str
        h_lower = h_str.lower()
        if h_lower in ("nombre",):
            col_indices["nombre"] = i
        elif h_lower in ("apellidos", "apellido"):
            col_indices["apellidos"] = i
        elif h_lower in ("email", "correo", "e-mail", "dirección de correo"):
            col_indices["email"] = i

    # Classify grade columns
    columnas: list[PreviewColumn] = []
    grade_col_indices: list[int] = []
    for i, h_str in raw_headers.items():
        h_lower = h_str.lower()
        if h_lower in ("nombre", "apellidos", "apellido", "email", "correo",
                       "e-mail", "dirección de correo"):
            continue
        # Check if it might be a "Calificación máxima" row
        nombre, tipo, _ = detectar_columna(h_str)
        columnas.append(PreviewColumn(
            nombre=nombre,
            tipo=tipo,  # type: ignore[arg-type]
            max_nota=None,
        ))
        grade_col_indices.append(i)

    # Max nota tracking
    max_nota_map: dict[str, float] = {}

    # Parse data rows
    filas: list[PreviewRow] = []
    errores: list[PreviewError] = []
    fila_num = 1

    for values in rows_iter:
        fila_num += 1
        vals = list(values) if values else []

        # Skip empty rows
        if not vals or all(v is None for v in vals):
            continue

        # Check if this is a "Calificación máxima" metadata row
        email_idx = col_indices.get("email")
        nombre_idx = col_indices.get("nombre")
        first_val = str(vals[0]).strip().lower() if vals[0] is not None else ""

        if first_val in ("calificación máxima", "calificacion maxima", "max not",
                         "max", "máxima"):
            for idx in grade_col_indices:
                if idx < len(vals) and vals[idx] is not None:
                    col_name = raw_headers.get(idx, "")
                    nombre_clean, _, _ = detectar_columna(col_name)
                    try:
                        max_nota_map[nombre_clean] = float(vals[idx])
                    except (ValueError, TypeError):
                        pass
            continue

        # Extract student info
        if nombre_idx is not None and nombre_idx < len(vals):
            nombre = str(vals[nombre_idx]).strip() if vals[nombre_idx] is not None else ""
        else:
            nombre = _clean_val(str(vals[0])) if vals else ""

        apellidos_idx = col_indices.get("apellidos")
        if apellidos_idx is not None and apellidos_idx < len(vals):
            apellidos = str(vals[apellidos_idx]).strip() if vals[apellidos_idx] is not None else ""
        else:
            apellidos = _clean_val(str(vals[1])) if len(vals) > 1 else ""

        if email_idx is not None and email_idx < len(vals):
            email = str(vals[email_idx]).strip() if vals[email_idx] is not None else ""
        else:
            email = ""

        if not email or "@" not in email:
            errores.append(PreviewError(
                fila=fila_num, columna="email",
                mensaje="Email inválido o faltante",
            ))
            continue

        valores: dict[str, Any] = {}
        for col, idx in zip(columnas, grade_col_indices):
            if idx >= len(vals):
                continue
            raw = vals[idx]
            if col.tipo == "numerica":
                try:
                    valores[col.nombre] = float(raw) if raw is not None else None
                except (ValueError, TypeError):
                    valores[col.nombre] = None
                    errores.append(PreviewError(
                        fila=fila_num,
                        columna=col.nombre,
                        mensaje=f"Valor no numérico: '{raw}'",
                    ))
            else:
                valores[col.nombre] = str(raw).strip() if raw is not None else None

        filas.append(PreviewRow(
            fila=fila_num,
            email=email,
            nombre=nombre,
            apellidos=apellidos,
            valores=valores,
        ))

    wb.close()

    # Apply max_nota hints
    for col in columnas:
        if col.tipo == "numerica" and col.nombre in max_nota_map:
            col.max_nota = max_nota_map[col.nombre]

    return PreviewResponse(
        columnas=columnas,
        filas=filas,
        errores=errores,
        total_filas=len(filas),
    )


def _decode_content(content: bytes) -> str:
    """Decode file content trying UTF-8 and latin-1."""
    for enc in ["utf-8-sig", "latin-1"]:
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise HTTPException(
        status_code=400,
        detail="No se pudo decodificar el archivo. Encoding no soportado.",
    )


def _detect_delimiter(header: str) -> str:
    """Detect CSV delimiter: prefers ; over ,."""
    semicolons = header.count(";")
    commas = header.count(",")
    if semicolons >= commas:
        return ";"
    return ","


def _extract_max_nota(lines: list[str], delimiter: str) -> dict[str, float]:
    """Extract max_nota hints from metadata rows in CSV."""
    max_nota_map: dict[str, float] = {}
    for line in lines[1:]:  # Skip header
        parts = line.split(delimiter)
        if not parts:
            continue
        first = parts[0].strip().lower()
        if first in ("calificación máxima", "calificacion maxima",
                     "max nota", "max", "máxima"):
            for i, part in enumerate(parts[1:], start=1):
                try:
                    max_nota_map[str(i)] = float(part.strip())
                except (ValueError, TypeError):
                    pass
    return max_nota_map


def _clean_val(val: str | None) -> str:
    """Clean a raw cell value."""
    if val is None:
        return ""
    return val.strip().strip('"').strip("'")


# ═══════════════════════════════════════════════════════════════════════════════
# Service class (coordinates repositories)
# ═══════════════════════════════════════════════════════════════════════════════


class CalificacionesService:
    """Service for importing, listing, and managing grades.

    All public methods receive db and tenant_id explicitly rather than
    storing state, so they can be used in request-scoped dependency injection.
    """

    def __init__(self, db, tenant_id: uuid.UUID):
        self._db = db
        self._tenant_id = tenant_id
        self._calificacion_repo = CalificacionRepository(
            session=db, tenant_id=tenant_id,
        )
        self._umbral_repo = UmbralMateriaRepository(
            session=db, tenant_id=tenant_id,
        )

    async def preview_import(
        self, file: UploadFile, materia_id: uuid.UUID, cohorte_id: uuid.UUID,
    ) -> PreviewResponse:
        """Preview an LMS grade file without persisting anything.

        Args:
            file: The uploaded file.
            materia_id: FK to Materia (for context, not used in parsing).
            cohorte_id: FK to Cohorte (for context, not used in parsing).

        Returns:
            PreviewResponse with parsed columns, rows, and errors.
        """
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=400, detail="El archivo está vacío",
            )

        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="El archivo excede el tamaño máximo de 10 MB",
            )

        filename = file.filename or "unknown"
        return parsear_archivo_lms(content, filename)

    async def importar_calificaciones(
        self,
        current_user,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_id: uuid.UUID,
        actividad_nombre: str,
        notas: list[dict],
        max_nota: float | None = None,
    ) -> ImportResponse:
        """Import confirmed grades into the database.

        For each student grade:
        1. Match email → EntradaPadron via email_hash
        2. Resolve effective umbral (RN-03 inheritance)
        3. Compute aprobado
        4. Create Calificacion record

        Args:
            current_user: The authenticated User (for tenant & audit).
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_id: FK to the teaching assignment.
            actividad_nombre: Name of the graded activity.
            notas: List of dicts with 'email', 'nota', 'nota_textual'.
            max_nota: Max possible grade (defaults to 100 if None).

        Returns:
            ImportResponse with counts.

        Raises:
            HTTPException 400: If emails not found in padron.
        """
        resolved_max_nota = max_nota or 100.0

        # Resolve effective umbral
        umbral_pct, valores_aprobatorios = await self._umbral_repo.get_effective_umbral(
            asignacion_id=asignacion_id,
            materia_id=materia_id,
            cohorte_id=cohorte_id,
        )

        # Match all emails to EntradaPadron entries
        matched = await self._match_emails(notas)
        errores: list[str] = []
        calificaciones: list[Calificacion] = []

        for item in notas:
            entry = matched.get(item["email"])
            if entry is None:
                errores.append(f"Email no encontrado en padrón: {item['email']}")
                continue

            aprobado = calcular_aprobado(
                nota=item.get("nota"),
                nota_textual=item.get("nota_textual"),
                umbral_pct=umbral_pct,
                max_nota=resolved_max_nota,
                valores_aprobatorios=valores_aprobatorios,
            )

            cal = Calificacion(
                tenant_id=self._tenant_id,
                entrada_padron_id=entry.id,
                materia_id=materia_id,
                cohorte_id=cohorte_id,
                asignacion_id=asignacion_id,
                usuario_id=entry.usuario_id,
                actividad_nombre=actividad_nombre,
                nota=item.get("nota"),
                nota_textual=item.get("nota_textual"),
                aprobado=aprobado,
                origen="Importado",
                extra_data={"max_nota": resolved_max_nota},
                periodo=_derive_period(),
            )
            calificaciones.append(cal)

        if errores:
            # Rollback: don't save any calificaciones if there are errors
            raise HTTPException(
                status_code=400,
                detail=f"Errores en {len(errores)} alumno(s): {'; '.join(errores[:5])}",
            )

        # Bulk insert
        created = await self._calificacion_repo.bulk_create(calificaciones)

        # Count aprobadas
        aprobadas = sum(1 for c in created if c.aprobado)
        reprobadas = len(created) - aprobadas

        # Audit log
        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=current_user.id,
            accion="CALIFICACIONES_IMPORTAR",
            detalle={
                "materia_id": str(materia_id),
                "cohorte_id": str(cohorte_id),
                "asignacion_id": str(asignacion_id),
                "actividad_nombre": actividad_nombre,
                "total_notas": len(created),
                "aprobadas": aprobadas,
                "reprobadas": reprobadas,
                "modo": "archivo",
            },
            filas_afectadas=len(created),
        )

        return ImportResponse(
            importadas=len(created),
            aprobadas=aprobadas,
            reprobadas=reprobadas,
            errores=[],
        )

    async def importar_finalizacion(
        self,
        cohorte_id: uuid.UUID,
        materia_id: uuid.UUID,
        file: UploadFile,
    ) -> FinalizacionResponse:
        """Detect student submissions without a grade from a finalizacion report.

        Parses the file, identifies textual activities (RN-02), and checks
        which students don't have Calificacion records for those activities.

        Args:
            cohorte_id: FK to Cohorte.
            materia_id: FK to Materia.
            file: The uploaded finalizacion report file.

        Returns:
            FinalizacionResponse listing ungraded submissions.
        """
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="El archivo está vacío")

        filename = file.filename or "unknown"
        preview = parsear_archivo_lms(content, filename)

        # Identify textual activities (RN-08: exclude numeric)
        actividades_textuales = [
            c.nombre for c in preview.columnas if c.tipo == "textual"
        ]

        items: list[FinalizacionRow] = []
        for fila in preview.filas:
            for act_nombre in actividades_textuales:
                valor = fila.valores.get(act_nombre)
                # Check if already has a grade record
                entry = await self._match_single_email(fila.email)
                if entry is None:
                    continue

                existing = await self._calificacion_repo.find_by_entrada_padron_y_actividad(
                    entrada_padron_id=entry.id,
                    actividad_nombre=act_nombre,
                )
                if existing is not None:
                    continue  # Already has a grade

                items.append(FinalizacionRow(
                    alumno=f"{fila.apellidos}, {fila.nombre}",
                    actividad=act_nombre,
                    estado="Sin_corregir",
                ))

        return FinalizacionResponse(
            items=items,
            total=len(items),
        )

    async def list_calificaciones(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Calificacion], int]:
        """List calificaciones with filters and pagination.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_id: Optional scope filter (PROFESOR).
            skip: Pagination offset.
            limit: Max records.

        Returns:
            Tuple of (calificaciones list, total count).
        """
        return await self._calificacion_repo.list_by_filters(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_id=asignacion_id,
            skip=skip,
            limit=limit,
        )

    # ── Private helpers ─────────────────────────────────────────────────

    async def _match_emails(
        self, notas: list[dict],
    ) -> dict[str, EntradaPadron]:
        """Match a list of emails to EntradaPadron entries.

        Uses email_hash for deterministic matching without decryption.

        Args:
            notas: List of dicts with 'email' key.

        Returns:
            Dict mapping email → EntradaPadron for matched entries.
        """
        emails = [n["email"] for n in notas if n.get("email")]
        if not emails:
            return {}

        hashes = [User.compute_email_hash(e) for e in emails]
        from sqlalchemy import select as sa_select

        stmt = sa_select(EntradaPadron).where(
            EntradaPadron.tenant_id == self._tenant_id,
            EntradaPadron.email_hash.in_(hashes),
            EntradaPadron.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        entries = list(result.scalars().all())

        # Build reverse map: hash → entry
        hash_to_entry = {}
        for e in entries:
            hash_to_entry[e.email_hash] = e

        matched: dict[str, EntradaPadron] = {}
        for email in emails:
            eh = User.compute_email_hash(email)
            if eh in hash_to_entry:
                matched[email] = hash_to_entry[eh]

        return matched

    async def _match_single_email(
        self, email: str,
    ) -> EntradaPadron | None:
        """Match a single email to EntradaPadron.

        Args:
            email: Student email.

        Returns:
            EntradaPadron entry if found, None otherwise.
        """
        if not email:
            return None
        email_hash = User.compute_email_hash(email)
        from sqlalchemy import select as sa_select

        stmt = sa_select(EntradaPadron).where(
            EntradaPadron.tenant_id == self._tenant_id,
            EntradaPadron.email_hash == email_hash,
            EntradaPadron.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()


def _derive_period() -> str:
    """Derive a period string (e.g. '2026-A') from current date.

    This is a simple implementation; in production it would come
    from the cohorte's configuration.
    """
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return f"{now.year}-A"
