from app.core import rate_limit
from tests.conftest import auth, register


def test_register_login_me(client):
    register(client)
    r = client.post("/api/auth/login", json={"email": "A@Example.com", "password": "correct-horse-1"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=auth(r.json()["access_token"]))
    assert me.status_code == 200 and me.json()["email"] == "a@example.com"
    assert "password" not in me.text


def test_wrong_password_and_unknown_email_look_identical(client):
    register(client)
    a = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-password-1"})
    b = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_duplicate_email_rejected(client):
    register(client)
    r = client.post("/api/auth/register", json={"email": "a@example.com", "password": "another-pass-1"})
    assert r.status_code == 409


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"email": "x@example.com", "password": "short"})
    assert r.status_code == 422


def test_protected_routes_require_token(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers=auth("garbage")).status_code == 401


def test_refresh_rotates_and_reuse_revokes_family(client):
    register(client)
    old = client.cookies.get("refresh_token")
    assert old
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    new = client.cookies.get("refresh_token")
    assert new and new != old
    # Replaying the old (rotated) token must fail and burn the new one too.
    client.cookies.set("refresh_token", old, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401
    client.cookies.set("refresh_token", new, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token(client):
    register(client)
    tok = client.cookies.get("refresh_token")
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("refresh_token", tok, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_login_rate_limited(client):
    register(client)
    codes = [client.post("/api/auth/login", json={"email": "a@example.com", "password": "bad-password-1"}).status_code
             for _ in range(12)]
    assert 429 in codes
    rate_limit.reset()
