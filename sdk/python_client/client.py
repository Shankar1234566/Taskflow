"""
Taskflow REST API Client Implementation with Session Persistence.
"""
from typing import Dict, List, Optional, Any
import requests

from .models import TaskModel, UserModel, TeamModel, DashboardStatsModel
from .exceptions import (
    TaskflowAPIError,
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    ValidationError
)


class TaskflowClient:
    """Official Python Client for the Taskflow Pro Platform."""

    def __init__(self, base_url: str = "http://127.0.0.1:5000", session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.current_user: Optional[UserModel] = None

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.RequestException as e:
            raise TaskflowAPIError(f"HTTP connection failed: {e}")

        if resp.status_code == 401:
            raise AuthenticationError(resp.json().get("error", "Unauthorized"), resp.json())
        elif resp.status_code == 403:
            raise PermissionDeniedError(resp.json().get("error", "Forbidden"), resp.json())
        elif resp.status_code == 404:
            raise NotFoundError(resp.json().get("error", "Not Found"), resp.json())
        elif resp.status_code == 400:
            raise ValidationError(resp.json().get("error", "Bad Request"), resp.json())
        elif resp.status_code >= 400:
            raise TaskflowAPIError(f"API Error {resp.status_code}: {resp.text}", status_code=resp.status_code)

        try:
            return resp.json()
        except Exception:
            return resp.text

    # --- Authentication ---
    def login(self, email: str, password: str = "password123") -> UserModel:
        payload = {"email": email, "password": password}
        res = self._request("POST", "/api/auth/login", json=payload)
        self.current_user = UserModel.from_dict(res.get("user", {}))
        return self.current_user

    def logout(self) -> None:
        self._request("POST", "/api/auth/logout")
        self.current_user = None

    def get_me(self) -> UserModel:
        res = self._request("GET", "/api/auth/me")
        self.current_user = UserModel.from_dict(res.get("user", {}))
        return self.current_user

    # --- Tasks CRUD ---
    def list_tasks(self, **filters) -> List[TaskModel]:
        res = self._request("GET", "/api/tasks/", params=filters)
        return [TaskModel.from_dict(t) for t in res.get("tasks", [])]

    def get_task(self, task_id: int) -> TaskModel:
        res = self._request("GET", f"/api/tasks/{task_id}")
        return TaskModel.from_dict(res.get("task", {}))

    def create_task(self, title: str, **fields) -> TaskModel:
        payload = {"title": title, **fields}
        res = self._request("POST", "/api/tasks/", json=payload)
        return TaskModel.from_dict(res.get("task", {}))

    def update_task(self, task_id: int, **fields) -> TaskModel:
        res = self._request("PUT", f"/api/tasks/{task_id}", json=fields)
        return TaskModel.from_dict(res.get("task", {}))

    def complete_task(self, task_id: int) -> TaskModel:
        res = self._request("PATCH", f"/api/tasks/{task_id}/complete")
        return TaskModel.from_dict(res.get("task", {}))

    def delete_task(self, task_id: int) -> bool:
        self._request("DELETE", f"/api/tasks/{task_id}")
        return True

    # --- Dashboard & Stats ---
    def get_dashboard_stats(self) -> DashboardStatsModel:
        res = self._request("GET", "/api/dashboard/")
        return DashboardStatsModel.from_dict(res)

    # --- Teams ---
    def list_team_members(self) -> List[UserModel]:
        res = self._request("GET", "/api/team/members")
        return [UserModel.from_dict(m) for m in res.get("members", [])]
