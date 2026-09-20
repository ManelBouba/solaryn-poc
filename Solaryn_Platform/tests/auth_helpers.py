"""Existing workflow tests authenticate through the real admin login."""
from unittest.mock import patch
from fastapi.testclient import TestClient
from foundation import create_app
from foundation_auth import password_hash

TEST_PASSWORD = "test-only-admin-password-2026"
TEST_HASH = password_hash(TEST_PASSWORD)


def admin_client(db_path, **kwargs):
    with patch.dict("os.environ", {"SOLARYN_ADMIN_USERNAME": "admin", "SOLARYN_ADMIN_PASSWORD_HASH": TEST_HASH}):
        app = create_app(db_path, **kwargs)
    client = TestClient(app)
    response = client.post('/api/v1/auth/login', json={"username": "admin", "password": TEST_PASSWORD})
    assert response.status_code == 200
    return client
