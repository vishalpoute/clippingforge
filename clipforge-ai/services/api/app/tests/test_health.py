"""Tests for ClipForge AI health, info, video, and job endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_200() -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "ClipForge AI"


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["version"].startswith("0.")


def test_health_dependencies_returns_expected_keys() -> None:
    response = client.get("/api/v1/health/dependencies")
    assert response.status_code == 200
    data = response.json()
    assert "database" in data
    assert "ffmpeg" in data
    assert "omnirouter" in data
    assert "worker" in data


def test_api_info_returns_200() -> None:
    response = client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["version"].startswith("0.")
    assert "database_backend" in data
    assert data["windows_native"] is True


def test_list_videos_returns_list() -> None:
    response = client.get("/api/v1/videos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_jobs_returns_list() -> None:
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
