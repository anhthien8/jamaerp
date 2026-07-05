"""API client — communicate with FastAPI backend."""

import os
from typing import Any

import httpx

API_BASE = os.getenv("API_BASE_URL", "http://backend:8000")


class APIClient:
    """Async HTTP client for backend API."""

    def __init__(self):
        self._base_url = f"{API_BASE}/api/v1"
        self._tokens: dict[int, str] = {}  # telegram_user_id → JWT

    async def authenticate(self, telegram_user_id: int, username: str | None = None) -> dict | None:
        """Authenticate TG user → JWT."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/auth/telegram",
                    json={
                        "telegram_user_id": telegram_user_id,
                        "telegram_username": username,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._tokens[telegram_user_id] = data["access_token"]
                    return data
                return None
            except Exception:
                return None

    def _headers(self, telegram_user_id: int) -> dict:
        token = self._tokens.get(telegram_user_id, "")
        return {"Authorization": f"Bearer {token}"}

    async def parse_lead(self, tg_user_id: int, text: str) -> dict | None:
        """Parse raw text via AI."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/ai/parse-lead",
                json={"text": text},
                headers=self._headers(tg_user_id),
                timeout=30.0,
            )
            return resp.json() if resp.status_code == 200 else None

    async def create_lead(self, tg_user_id: int, data: dict) -> dict | None:
        """Create lead in CRM."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/leads",
                json=data,
                headers=self._headers(tg_user_id),
            )
            return resp.json() if resp.status_code == 201 else None

    async def get_pipeline(self, tg_user_id: int) -> list | None:
        """Get kanban pipeline."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/leads/pipeline/kanban",
                headers=self._headers(tg_user_id),
            )
            return resp.json() if resp.status_code == 200 else None

    async def get_pipeline_stats(self, tg_user_id: int) -> dict | None:
        """Get pipeline stats."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/leads/pipeline/stats",
                headers=self._headers(tg_user_id),
            )
            return resp.json() if resp.status_code == 200 else None

    async def get_personal_dashboard(self, tg_user_id: int) -> dict | None:
        """Get personal dashboard for daily briefing."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/dashboard/personal",
                headers=self._headers(tg_user_id),
            )
            return resp.json() if resp.status_code == 200 else None

    async def suggest_action(self, tg_user_id: int, lead_id: str) -> dict | None:
        """Get AI suggestion for a lead."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/ai/suggest-action",
                params={"lead_id": lead_id},
                headers=self._headers(tg_user_id),
            )
            return resp.json() if resp.status_code == 200 else None

    async def change_stage(self, tg_user_id: int, lead_id: str, new_stage: str, note: str = None) -> dict | None:
        """Change lead stage."""
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base_url}/leads/{lead_id}/stage",
                json={"new_stage": new_stage, "note": note},
                headers=self._headers(tg_user_id),
            )
            return resp.json() if resp.status_code == 200 else None

    # ── Telegram workflow endpoints ──────────────────────────────────────────

    async def get_project(self, tg_user_id: int, project_code: str) -> dict | None:
        """Quick project lookup by code — returns project info + task summary."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/telegram/project/{project_code}",
                headers=self._headers(tg_user_id),
            )
            return resp.json() if resp.status_code == 200 else None

    async def create_site_report(self, tg_user_id: int, data: dict) -> dict | None:
        """Submit a site report with optional photos."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/telegram/site-report",
                json=data,
                headers=self._headers(tg_user_id),
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": resp.json().get("detail", "Loi khi gui bao cao cong trinh")}

    async def create_material_request(self, tg_user_id: int, data: dict) -> dict | None:
        """Submit a material purchase request."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/telegram/material-request",
                json=data,
                headers=self._headers(tg_user_id),
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": resp.json().get("detail", "Loi khi gui yeu cau vat tu")}

    async def report_incident(self, tg_user_id: int, data: dict) -> dict | None:
        """Report a construction incident."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/telegram/incident",
                json=data,
                headers=self._headers(tg_user_id),
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": resp.json().get("detail", "Loi khi bao cao su co")}

    async def checkin(self, tg_user_id: int, data: dict) -> dict | None:
        """GPS check-in at project site."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/telegram/checkin",
                json=data,
                headers=self._headers(tg_user_id),
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": resp.json().get("detail", "Loi khi check-in")}

    async def checkout(self, tg_user_id: int, data: dict) -> dict | None:
        """GPS check-out from project site."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/telegram/checkout",
                json=data,
                headers=self._headers(tg_user_id),
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": resp.json().get("detail", "Loi khi check-out")}

    async def approve_material(self, tg_user_id: int, request_id: str, data: dict | None = None) -> dict | None:
        """Approve a material request (Thu mua / Ke toan)."""
        payload = {"approver_tg_id": tg_user_id}
        if data:
            payload.update(data)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/telegram/approve/{request_id}",
                json=payload,
                headers=self._headers(tg_user_id),
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": resp.json().get("detail", "Loi khi duyet vat tu")}

    async def reject_material(self, tg_user_id: int, request_id: str, reason: str | None = None) -> dict | None:
        """Reject a material request (Thu mua / Ke toan)."""
        payload = {"approver_tg_id": tg_user_id}
        if reason:
            payload["reason"] = reason
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/telegram/reject/{request_id}",
                json=payload,
                headers=self._headers(tg_user_id),
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": resp.json().get("detail", "Loi khi tu choi vat tu")}


# Singleton
api = APIClient()
