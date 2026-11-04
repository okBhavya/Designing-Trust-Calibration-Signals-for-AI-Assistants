import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.connection import get_db
from app.database.models import SessionToken

TOKEN_AUDIENCE = "calibrai-extension"


@dataclass(frozen=True)
class AuthenticatedSession:
    participant_id: UUID
    jti: str
    expires_at: datetime


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signing_key() -> bytes:
    secret = get_settings().session_signing_secret
    if len(secret) < 32:
        raise RuntimeError("CALIBRAI_SESSION_SIGNING_SECRET must contain at least 32 characters")
    return secret.encode("utf-8")


def create_session_token(participant_id: UUID, db: Session) -> tuple[str, int, str]:
    settings = get_settings()
    now = int(time.time())
    expires = now + settings.session_ttl_seconds
    jti = secrets.token_urlsafe(24)
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(
        json.dumps(
            {"sub": str(participant_id), "aud": TOKEN_AUDIENCE, "iat": now, "exp": expires, "jti": jti},
            separators=(",", ":"),
        ).encode()
    )
    unsigned = f"{header}.{payload}".encode("ascii")
    signature = _encode(hmac.new(_signing_key(), unsigned, hashlib.sha256).digest())
    db.add(
        SessionToken(
            jti=jti,
            participant_id=participant_id,
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
        )
    )
    return f"{header}.{payload}.{signature}", settings.session_ttl_seconds, jti


def verify_session_token(token: str, db: Session) -> AuthenticatedSession:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}".encode("ascii")
        expected = _encode(hmac.new(_signing_key(), unsigned, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        decoded_header = json.loads(_decode(header))
        claims = json.loads(_decode(payload))
        if decoded_header.get("alg") != "HS256" or decoded_header.get("typ") != "JWT":
            raise ValueError
        participant_id = UUID(claims["sub"])
        jti = str(claims["jti"])
        expires = int(claims["exp"])
        if claims.get("aud") != TOKEN_AUDIENCE or expires <= int(time.time()):
            raise ValueError
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeError):
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    session = db.get(SessionToken, jti)
    if session is None or session.revoked or session.participant_id != participant_id:
        raise HTTPException(status_code=401, detail="Invalid or revoked session token")
    return AuthenticatedSession(
        participant_id=participant_id,
        jti=jti,
        expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
    )


def require_session(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthenticatedSession:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Bearer session token required")
    return verify_session_token(token, db)
