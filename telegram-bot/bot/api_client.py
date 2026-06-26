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


# Singleton
api = APIClient()
