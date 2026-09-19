"""Static-credential auth: accounts, phone normalization, signed tokens."""

import time

import core.auth as auth


def test_dispatcher_login_is_case_insensitive_on_email():
    s = auth.authenticate("dispatcher", "  Dispatch@Aevora.IN ", "aevora-dispatch")
    assert s is not None and s.role == "dispatcher" and s.name == "Dispatch Desk"


def test_wrong_password_or_role_is_rejected():
    assert auth.authenticate("dispatcher", "dispatch@aevora.in", "nope") is None
    assert auth.authenticate("rider", "dispatch@aevora.in", "aevora-dispatch") is None
    assert auth.authenticate("dispatcher", "+919900000001", "aevora-rider") is None


def test_rider_phone_formats_map_to_seeded_riders():
    for phone in ("+91 99000 00003", "9900000003", "919900000003", "+91-99000-00003"):
        s = auth.authenticate("rider", phone, "aevora-rider")
        assert s is not None and s.sub == "rider-3"
    assert auth.authenticate("rider", "9900000009", "aevora-rider") is None


def test_token_round_trip():
    s = auth.authenticate("rider", "9900000005", "aevora-rider")
    assert auth.verify_token(auth.issue_token(s)) == s


def test_tampered_or_garbage_tokens_are_rejected():
    token = auth.issue_token(auth.authenticate("rider", "9900000005", "aevora-rider"))
    payload, sig = token.rsplit(".", 1)
    forged = auth._b64(b'{"role":"dispatcher","sub":"x","name":"x","exp":9999999999}')
    assert auth.verify_token(f"{forged}.{sig}") is None
    assert auth.verify_token(payload + "." + sig[:-2] + "AA") is None
    for junk in (None, "", "abc", "a.b.c"):
        assert auth.verify_token(junk) is None


def test_expired_token_is_rejected():
    s = auth.Session(role="dispatcher", sub="d", name="D", exp=int(time.time()) - 1)
    assert auth.verify_token(auth.issue_token(s)) is None


def test_tokens_depend_on_the_secret(monkeypatch):
    s = auth.authenticate("dispatcher", "dispatch@aevora.in", "aevora-dispatch")
    monkeypatch.setenv("SESSION_SECRET", "one")
    token = auth.issue_token(s)
    monkeypatch.setenv("SESSION_SECRET", "two")
    assert auth.verify_token(token) is None
