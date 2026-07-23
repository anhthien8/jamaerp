"""API client — communicate with FastAPI backend."""

import os

import httpx

API_BASE = os.getenv("API_BASE_URL", "http://backend:8000")
# Bí mật chia sẻ với backend (phải trùng TELEGRAM_AUTH_SECRET ở backend)
TELEGRAM_AUTH_SECRET = os.getenv("TELEGRAM_AUTH_SECRET", "")


class APIClient:
    """Async HTTP client for backend API."""

    def __init__(self):
        self._base_url = f"{API_BASE}/api/v1"
        self._tokens: dict[int, str] = {}  # telegram_user_id → JWT

    async def authenticate(self, telegram_user_id: int, username: str | None = None) -> dict | None:
        """Authenticate TG user → JWT."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/auth/telegram",
                    json={
                        "telegram_user_id": telegram_user_id,
                        "telegram_username": username,
                    },
                    headers={"X-Telegram-Bot-Secret": TELEGRAM_AUTH_SECRET},
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
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/ai/parse-lead",
                    json={"text": text},
                    headers=self._headers(tg_user_id),
                    timeout=30.0,
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def create_lead(self, tg_user_id: int, data: dict) -> dict | None:
        """Create lead in CRM."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/leads",
                    json=data,
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 201:
                    return resp.json()
                return None
        except Exception:
            return None

    async def get_pipeline(self, tg_user_id: int) -> list | None:
        """Get kanban pipeline."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/leads/pipeline/kanban",
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def get_pipeline_stats(self, tg_user_id: int) -> dict | None:
        """Get pipeline stats."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/leads/pipeline/stats",
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def get_personal_dashboard(self, tg_user_id: int) -> dict | None:
        """Get personal dashboard for daily briefing."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/dashboard/personal",
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def suggest_action(self, tg_user_id: int, lead_id: str) -> dict | None:
        """Get AI suggestion for a lead."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/ai/suggest-action",
                    params={"lead_id": lead_id},
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def change_stage(self, tg_user_id: int, lead_id: str, new_stage: str, note: str = None) -> dict | None:
        """Change lead stage."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.put(
                    f"{self._base_url}/leads/{lead_id}/stage",
                    json={"new_stage": new_stage, "note": note},
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    # ── Telegram workflow endpoints ──────────────────────────────────────────

    async def get_project(self, tg_user_id: int, project_code: str) -> dict | None:
        """Quick project lookup by code — returns project info + task summary."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/telegram/project/{project_code}",
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def create_site_report(self, tg_user_id: int, data: dict) -> dict | None:
        """Submit a site report with optional photos."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/telegram/site-report",
                    json=data,
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi khi gui bao cao cong trinh")
                except Exception:
                    detail = "Loi khi gui bao cao cong trinh"
                return {"error": detail}
        except Exception:
            return None

    async def create_material_request(self, tg_user_id: int, data: dict) -> dict | None:
        """Submit a material purchase request."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/telegram/material-request",
                    json=data,
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi khi gui yeu cau vat tu")
                except Exception:
                    detail = "Loi khi gui yeu cau vat tu"
                return {"error": detail}
        except Exception:
            return None

    async def report_incident(self, tg_user_id: int, data: dict) -> dict | None:
        """Report a construction incident."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/telegram/incident",
                    json=data,
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi khi bao cao su co")
                except Exception:
                    detail = "Loi khi bao cao su co"
                return {"error": detail}
        except Exception:
            return None

    async def checkin(self, tg_user_id: int, data: dict) -> dict | None:
        """GPS check-in at project site."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/telegram/checkin",
                    json=data,
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi khi check-in")
                except Exception:
                    detail = "Loi khi check-in"
                return {"error": detail}
        except Exception:
            return None

    async def checkout(self, tg_user_id: int, data: dict) -> dict | None:
        """GPS check-out from project site."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/telegram/checkout",
                    json=data,
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi khi check-out")
                except Exception:
                    detail = "Loi khi check-out"
                return {"error": detail}
        except Exception:
            return None

    async def approve_material(self, tg_user_id: int, request_id: str, data: dict | None = None) -> dict | None:
        """Approve a material request (Thu mua / Ke toan)."""
        payload = {"approver_tg_id": tg_user_id}
        if data:
            payload.update(data)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/telegram/approve/{request_id}",
                    json=payload,
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi khi duyet vat tu")
                except Exception:
                    detail = "Loi khi duyet vat tu"
                return {"error": detail}
        except Exception:
            return None

    async def reject_material(self, tg_user_id: int, request_id: str, reason: str | None = None) -> dict | None:
        """Reject a material request (Thu mua / Ke toan)."""
        payload = {"approver_tg_id": tg_user_id}
        if reason:
            payload["reason"] = reason
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/telegram/reject/{request_id}",
                    json=payload,
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi khi tu choi vat tu")
                except Exception:
                    detail = "Loi khi tu choi vat tu"
                return {"error": detail}
        except Exception:
            return None

    # ── HR Phase 1: chấm công / nghỉ phép / lương / phê duyệt ─────────────

    async def _post(self, tg_user_id: int, path: str, payload: dict | None = None, error_default: str = "Loi he thong") -> dict | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}{path}",
                    json=payload or {},
                    headers=self._headers(tg_user_id),
                    timeout=15.0,
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                try:
                    return {"error": resp.json().get("detail", error_default)}
                except Exception:
                    return {"error": error_default}
        except Exception:
            return None

    async def _get(self, tg_user_id: int, path: str, params: dict | None = None) -> dict | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}{path}",
                    params=params,
                    headers=self._headers(tg_user_id),
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    return resp.json()
                try:
                    return {"error": resp.json().get("detail", "Loi he thong")}
                except Exception:
                    return None
        except Exception:
            return None

    async def office_checkin(self, tg_user_id: int) -> dict | None:
        """Check-in văn phòng (không cần mã dự án/GPS)."""
        return await self._post(
            tg_user_id, "/telegram/attendance/checkin",
            {"user_tg_id": tg_user_id}, "Loi khi check-in",
        )

    async def office_checkout(self, tg_user_id: int) -> dict | None:
        return await self._post(
            tg_user_id, "/telegram/attendance/checkout",
            {"user_tg_id": tg_user_id}, "Loi khi check-out",
        )

    async def my_attendance_summary(self, tg_user_id: int) -> dict | None:
        return await self._get(tg_user_id, f"/telegram/attendance/me/{tg_user_id}")

    async def create_leave(self, tg_user_id: int, data: dict) -> dict | None:
        return await self._post(tg_user_id, "/leaves", data, "Loi khi tao don nghi phep")

    async def my_leave_balance(self, tg_user_id: int) -> dict | None:
        return await self._get(tg_user_id, "/leaves/balance/me")

    async def my_payslips(self, tg_user_id: int) -> dict | None:
        return await self._get(tg_user_id, "/payroll/me")

    async def create_advance(self, tg_user_id: int, amount: float, reason: str) -> dict | None:
        return await self._post(tg_user_id, "/payroll/advance", {"amount": amount, "reason": reason}, "Loi khi tao tam ung")

    async def pending_approvals(self, tg_user_id: int) -> dict | None:
        return await self._get(tg_user_id, "/approvals/pending-for-me")

    async def approve_generic(self, tg_user_id: int, request_id: str) -> dict | None:
        return await self._post(
            tg_user_id, f"/approvals/{request_id}/tg-approve",
            {"approver_tg_id": tg_user_id}, "Loi khi duyet",
        )

    async def reject_generic(self, tg_user_id: int, request_id: str, reason: str | None = None) -> dict | None:
        payload: dict = {"approver_tg_id": tg_user_id}
        if reason:
            payload["reason"] = reason
        return await self._post(
            tg_user_id, f"/approvals/{request_id}/tg-reject",
            payload, "Loi khi tu choi",
        )

    async def submit_feedback(self, tg_user_id: int, category: str, content: str) -> dict | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/feedback/telegram",
                    json={"telegram_user_id": tg_user_id, "category": category, "content": content},
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi gui feedback")
                except Exception:
                    detail = "Loi gui feedback"
                return {"error": detail}
        except Exception:
            return None

    async def get_my_feedback(self, tg_user_id: int) -> dict | None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/feedback/my",
                    headers=self._headers(tg_user_id),
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None


    # ── Estimation (Du toan) ─────────────────────────────────────────────────

    async def create_estimation(self, tg_user_id: int, data: dict) -> dict | None:
        """Submit an estimation to backend."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/telegram/estimation",
                    json=data,
                    headers=self._headers(tg_user_id),
                    timeout=15.0,
                )
                if resp.status_code in (200, 201):
                    return resp.json()
                try:
                    detail = resp.json().get("detail", "Loi gui du toan")
                except Exception:
                    detail = "Loi gui du toan"
                return {"error": detail}
        except Exception:
            return None

    async def list_estimations(self, tg_user_id: int) -> list | dict | None:
        """List recent estimations for the current user."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/telegram/estimations",
                    headers=self._headers(tg_user_id),
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def get_estimation(self, tg_user_id: int, estimation_id: str) -> dict | None:
        """Get estimation detail by ID."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/telegram/estimation/{estimation_id}",
                    headers=self._headers(tg_user_id),
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None


# Singleton
api = APIClient()
