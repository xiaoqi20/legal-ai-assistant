import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Request
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.access import DB, User
from app.errors import fail
from app.schemas import DevLogin, Profile, SMSCode, SMSLogin, WechatLogin

router = APIRouter()


def dev_only(request):
  settings = request.app.state.settings
  if settings.env == "production" or not settings.allow_dev_login:
    fail(404, "not_found", "接口未启用")


async def login(db, t, settings, provider, uid, consent, phone=None):
  # Serialize identity creation across API replicas.
  from sqlalchemy import func
  await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"{provider}:{uid}", 0))))
  documents = (await db.execute(select(t.legal_documents.c.id, t.legal_documents.c.doc_type).where(
    t.legal_documents.c.published_at.is_not(None),
    t.legal_documents.c.effective_at <= datetime.now(UTC),
  ).order_by(t.legal_documents.c.effective_at.desc()))).mappings().all()
  latest = {}
  for doc in documents:
    latest.setdefault(doc["doc_type"], doc["id"])
  if settings.env == "production" and len(latest) < 3:
    fail(503, "agreements_not_ready", "服务协议尚未配置完成")
  if not set(latest.values()) <= set(consent.document_ids):
    fail(409, "agreement_version_changed", "请阅读并同意最新协议")
  identity = (await db.execute(select(t.user_identities).where(
    t.user_identities.c.provider == provider, t.user_identities.c.provider_uid == uid
  ))).mappings().first()
  now = datetime.now(UTC)
  if identity:
    user_id = identity["user_id"]
    user = (await db.execute(select(t.users).where(t.users.c.id == user_id))).mappings().one()
    if user["status"] != "active" or user["deleted_at"]:
      fail(403, "account_disabled", "账号不可用")
    await db.execute(update(t.user_identities).where(t.user_identities.c.id == identity["id"]).values(last_used_at=now))
  else:
    user_id = (await db.execute(insert(t.users).values(display_name="新用户").returning(t.users.c.id))).scalar_one()
    await db.execute(insert(t.user_identities).values(
      user_id=user_id, provider=provider, provider_uid=uid, verified_at=now, last_used_at=now,
    ))
  if phone:
    # Do not silently merge identities belonging to another account.
    existing = (await db.execute(select(t.user_identities.c.user_id).where(
      t.user_identities.c.provider == "phone", t.user_identities.c.provider_uid == phone
    ))).scalar_one_or_none()
    if existing is not None and existing != user_id:
      fail(409, "identity_conflict", "手机号已绑定其他账号，请联系支持")
    await db.execute(pg_insert(t.user_identities).values(
      user_id=user_id, provider="phone", provider_uid=phone, verified_at=now,
    ).on_conflict_do_nothing(index_elements=["provider", "provider_uid"]))
  for doc_id in latest.values():
    await db.execute(insert(t.user_consents).values(user_id=user_id, document_id=doc_id))
  token = secrets.token_urlsafe(48)
  expires_at = now + timedelta(hours=settings.session_hours)
  await db.execute(insert(t.user_sessions).values(
    user_id=user_id, refresh_token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=expires_at,
  ))
  await db.execute(update(t.users).where(t.users.c.id == user_id).values(last_login_at=now))
  await db.execute(insert(t.audit_logs).values(user_id=user_id, action="auth.login", resource_type="user", resource_id=user_id))
  has_profile = (await db.execute(select(t.user_profiles.c.user_id).where(t.user_profiles.c.user_id == user_id))).scalar_one_or_none()
  await db.commit()
  return {"access_token": token, "token_type": "bearer", "expires_at": expires_at,
          "user_id": user_id, "needs_onboarding": has_profile is None}


@router.get("/agreements")
async def agreements(request: Request, db: DB):
  t = request.app.state.db.t
  rows = (await db.execute(select(t.legal_documents).where(
    t.legal_documents.c.published_at.is_not(None), t.legal_documents.c.effective_at <= datetime.now(UTC),
  ).order_by(t.legal_documents.c.effective_at.desc()))).mappings().all()
  latest = {}
  for row in rows:
    latest.setdefault(row["doc_type"], dict(row))
  return list(latest.values())


@router.post("/auth/dev-login")
async def dev_login(payload: DevLogin, request: Request, db: DB):
  dev_only(request)
  return await login(db, request.app.state.db.t, request.app.state.settings,
                     "wechat_mini", f"dev:{payload.identity}", payload)


@router.post("/auth/sms/code")
async def sms_code(payload: SMSCode, request: Request):
  dev_only(request)
  return {"mock": True, "code": "123456", "retry_after_seconds": 60, "message": "仅开发演示，不发送短信"}


@router.post("/auth/sms/login")
async def sms_login(payload: SMSLogin, request: Request, db: DB):
  dev_only(request)
  if payload.code != "123456":
    fail(400, "invalid_code", "开发验证码错误")
  return await login(db, request.app.state.db.t, request.app.state.settings,
                     "wechat_mini", f"dev-sms:{payload.phone}", payload)


@router.post("/auth/wechat")
async def wechat_login(payload: WechatLogin, request: Request, db: DB):
  settings = request.app.state.settings
  if not settings.wechat_app_id or not settings.wechat_app_secret.get_secret_value():
    fail(503, "wechat_not_configured", "微信登录尚未配置")
  try:
    async with httpx.AsyncClient(timeout=10) as client:
      session = (await client.get("https://api.weixin.qq.com/sns/jscode2session", params={
        "appid": settings.wechat_app_id, "secret": settings.wechat_app_secret.get_secret_value(),
        "js_code": payload.login_code, "grant_type": "authorization_code",
      })).raise_for_status().json()
      if not session.get("openid"):
        fail(401, "wechat_invalid_code", "微信登录凭据无效或已使用")
      token = (await client.get("https://api.weixin.qq.com/cgi-bin/token", params={
        "appid": settings.wechat_app_id, "secret": settings.wechat_app_secret.get_secret_value(),
        "grant_type": "client_credential",
      })).raise_for_status().json()
      if not token.get("access_token"):
        fail(502, "wechat_unavailable", "微信授权服务暂不可用")
      phone = (await client.post("https://api.weixin.qq.com/wxa/business/getuserphonenumber", params={
        "access_token": token["access_token"],
      }, json={"code": payload.phone_code})).raise_for_status().json()
      phone_number = phone.get("phone_info", {}).get("purePhoneNumber")
      if phone.get("errcode", 0) or not phone_number:
        fail(401, "wechat_phone_denied", "手机号授权失败，请重新授权")
  except (httpx.HTTPError, ValueError, KeyError):
    fail(502, "wechat_unavailable", "微信授权服务暂不可用")
  return await login(db, request.app.state.db.t, settings, "wechat_mini", session["openid"], payload, phone_number)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, db: DB, user: User):
  t = request.app.state.db.t
  await db.execute(update(t.user_sessions).where(t.user_sessions.c.id == user["session_id"]).values(revoked_at=datetime.now(UTC)))
  await db.commit()


@router.get("/profile")
async def profile(request: Request, db: DB, user: User):
  t = request.app.state.db.t
  row = (await db.execute(select(t.users.c.display_name, t.users.c.avatar_url, t.user_profiles)
    .outerjoin(t.user_profiles, t.user_profiles.c.user_id == t.users.c.id)
    .where(t.users.c.id == user["id"]))).mappings().one()
  result = dict(row)
  phone = (await db.execute(select(t.user_identities.c.provider_uid).where(
    t.user_identities.c.user_id == user["id"], t.user_identities.c.provider == "phone",
  ).limit(1))).scalar_one_or_none()
  result["phone"] = f"{phone[:3]}****{phone[-4:]}" if phone else ""
  result["role_label"] = {"individual": "个人", "enterprise": "企业", "legal": "法律专业"}.get(result.get("role_type"), "")
  return result


@router.put("/profile")
async def save_profile(payload: Profile, request: Request, db: DB, user: User):
  t = request.app.state.db.t
  values = payload.model_dump()
  query = pg_insert(t.user_profiles).values(user_id=user["id"], **values)
  await db.execute(query.on_conflict_do_update(index_elements=["user_id"], set_=values))
  await db.execute(update(t.users).where(t.users.c.id == user["id"]).values(display_name=payload.real_name))
  await db.commit()
  return payload
