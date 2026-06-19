"""Async Moodle Web Services client.

Provides a thin async wrapper around the Moodle REST API using httpx.
Supports configurable timeout and automatic retry with exponential backoff.

Usage:
    client = MoodleClient(base_url="https://moodle.example.com", token="...")
    alumnos = await client.sync_alumnos(course_id=123)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default constants
_DEFAULT_TIMEOUT = 30.0  # seconds
_MAX_RETRIES = 3
_BASE_BACKOFF = 1.0  # seconds


class MoodleClient:
    """Async HTTP client for Moodle Web Services.

    Args:
        base_url: Base URL of the Moodle instance (e.g. https://moodle.example.com).
        token: Web Services token for authentication.
        timeout: Request timeout in seconds (default 30).
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    async def sync_alumnos(
        self,
        curso_id: int | None = None,
        materia_id: str | None = None,
        cohorte_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch enrolled students from a Moodle course.

        Calls ``core_enrol_get_enrolled_users`` with the given course id.
        Maps Moodle user fields to the activia-trace padron format.

        Args:
            curso_id: Moodle course ID (numeric).
            materia_id: activia-trace materia UUID (for fallback mapping).
            cohorte_id: activia-trace cohorte UUID (for fallback mapping).

        Returns:
            List of dicts with keys: nombre, apellidos, email, comision, regional.

        Raises:
            httpx.HTTPStatusError: If Moodle returns an error status.
            httpx.RequestError: If connection fails after retries.
        """
        if curso_id is None:
            raise ValueError("curso_id is required for sync_alumnos")

        params: dict[str, str] = {
            "wstoken": self._token,
            "wsfunction": "core_enrol_get_enrolled_users",
            "moodlewsrestformat": "json",
            "courseid": str(curso_id),
        }

        # Attempt the request with retries
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(
                        f"{self._base_url}/webservice/rest/server.php",
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                # Moodle can return an error object in JSON even with 200
                if isinstance(data, dict) and "error" in data:
                    raise ValueError(
                        f"Moodle WS error: {data.get('error', 'unknown')}"
                    )

                # Map Moodle user fields to our padron format
                alumnos = []
                for user in data if isinstance(data, list) else []:
                    nombre = user.get("firstname", "")
                    apellidos = user.get("lastname", "")
                    email = user.get("email", "")
                    # Moodle custom fields or groups could map to comision/regional
                    comision = _extract_custom_field(user, "comision")
                    regional = _extract_custom_field(user, "regional")

                    if nombre or email:
                        alumnos.append({
                            "nombre": nombre,
                            "apellidos": apellidos,
                            "email": email,
                            "comision": comision,
                            "regional": regional,
                        })

                logger.info(
                    "Moodle WS sync_alumnos: course=%s, fetched=%d",
                    curso_id, len(alumnos),
                )
                return alumnos

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                last_exc = exc
                logger.warning(
                    "Moodle WS attempt %d/%d failed: %s",
                    attempt, _MAX_RETRIES, exc,
                )
                if attempt < _MAX_RETRIES:
                    backoff = _BASE_BACKOFF * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)
            except Exception as exc:
                # Non-retryable errors (e.g. JSON decode, ValueError)
                raise

        # All retries exhausted
        raise httpx.RequestError(
            f"Moodle WS no disponible tras {_MAX_RETRIES} intentos"
        ) from last_exc

    async def sync_actividades(
        self,
        curso_id: int,
    ) -> list[dict[str, Any]]:
        """Fetch activities/assignments from a Moodle course.

        Args:
            curso_id: Moodle course ID.

        Returns:
            List of activity dicts.

        Raises:
            Same as sync_alumnos.
        """
        params: dict[str, str] = {
            "wstoken": self._token,
            "wsfunction": "core_course_get_contents",
            "moodlewsrestformat": "json",
            "courseid": str(curso_id),
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/webservice/rest/server.php",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def sync_calificaciones(
        self,
        curso_id: int,
    ) -> list[dict[str, Any]]:
        """Fetch grades from a Moodle course.

        Args:
            curso_id: Moodle course ID.

        Returns:
            List of grade dicts.

        Raises:
            Same as sync_alumnos.
        """
        params: dict[str, str] = {
            "wstoken": self._token,
            "wsfunction": "gradereport_user_get_grade_items",
            "moodlewsrestformat": "json",
            "courseid": str(curso_id),
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/webservice/rest/server.php",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()


def _extract_custom_field(
    user: dict[str, Any],
    field_name: str,
) -> str | None:
    """Extract a custom profile field value from a Moodle user dict.

    Moodle custom fields are in the ``customfields`` list, each with
    ``shortname`` and ``value`` keys.
    """
    for cf in user.get("customfields", []):
        if cf.get("shortname", "").lower() == field_name.lower():
            val = cf.get("value")
            return str(val) if val else None
    return None
