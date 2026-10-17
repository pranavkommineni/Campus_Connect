import os
import tempfile

_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_dir}/test.db"
os.environ["UPLOAD_DIR"] = f"{_dir}/uploads"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import seed  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    seed.main(reset=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, email, pw="Password123!"):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def admin(client): return login(client, "admin@campusconnect.dev")
@pytest.fixture
def club1(client): return login(client, "codeclub@campusconnect.dev")
@pytest.fixture
def club2(client): return login(client, "artsclub@campusconnect.dev")
@pytest.fixture
def s1(client): return login(client, "student1@campusconnect.dev")
@pytest.fixture
def s4(client): return login(client, "student4@campusconnect.dev")
