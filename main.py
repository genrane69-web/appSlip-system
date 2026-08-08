from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Request
import firebase_admin
from firebase_admin import credentials, firestore
import requests
from datetime import datetime
import json
import os
import hmac
import hashlib
import base64

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="AppCentralWeb API Service")

# ----------------------------------------------------
# Rate limiting: จำกัดจำนวนคำขอต่อ IP เพื่อกันการเดา License Key
# หรือยิง endpoint ถี่เกินไป
# ----------------------------------------------------
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ----------------------------------------------------
# 1. เชื่อมต่อ Firebase (รองรับการดึงกุญแจแบบปลอดภัย)
# ----------------------------------------------------
if not firebase_admin._apps:
    firebase_config = os.getenv("FIREBASE_CREDENTIALS")
    if firebase_config:
        try:
            # ตัดเครื่องหมายอัญประกาศส่วนเกินหากมี
            firebase_config_clean = firebase_config.strip("'\"")
            cred_dict = json.loads(firebase_config_clean)
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"⚠️ Firebase Initialization Error: {e}")
    elif os.path.exists("firebase_credentials.json"):
        cred = credentials.Certificate("firebase_credentials.json")
        firebase_admin.initialize_app(cred)

db = firestore.client() if firebase_admin._apps else None

# แก้ไข: ไม่ใช้ค่า default ที่หน้าตาเหมือนคีย์จริงฝังในโค้ดอีกต่อไป
# ถ้าไม่ตั้งค่า env var ระบบจะแจ้ง error ชัดเจนแทนที่จะแอบใช้ค่าอื่น
BRANCH_ID = os.getenv("SLIPOK_BRANCH_ID", "")
SLIPOK_API_KEY = os.getenv("SLIPOK_SECRET_KEY", "")


def _require_slipok_config():
    if not BRANCH_ID or not SLIPOK_API_KEY:
        raise HTTPException(status_code=500, detail="ยังไม่ได้ตั้งค่า SLIPOK_BRANCH_ID / SLIPOK_SECRET_KEY บนเซิร์ฟเวอร์")


# ----------------------------------------------------
# หน้าแรกสำหรับเช็กสถานะเซิร์ฟเวอร์ (GET /)
# ----------------------------------------------------
@app.get("/")
def read_root():
    return {"status": "online", "message": "AppCentralWeb API Service is running!"}


# ----------------------------------------------------
# Helper Functions
# ----------------------------------------------------
def verify_tenant_key(tenant_key: str):
    """เช็คแบบเร็ว (ไม่ atomic) เพื่อคัดกรองคำขอที่ผิดเงื่อนไขชัดเจนออกก่อน
    เพื่อไม่ต้องเสียโควต้าเรียก SlipOK โดยเปล่าประโยชน์
    การตัดสินใจที่ต้องกัน race condition จริง (นับโควต้า/anti-reuse)
    จะทำอีกครั้งแบบ atomic ใน redeem_slip_atomic()
    """
    if not db:
        raise HTTPException(status_code=500, detail="ไม่สามารถเชื่อมต่อฐานข้อมูล Firebase ได้")

    doc_ref = db.collection("tenants").document(tenant_key)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=401, detail="License Key ไม่ถูกต้อง")

    tenant = doc.to_dict()
    if not tenant.get("active", True):
        raise HTTPException(status_code=403, detail="บัญชีถูกระงับการใช้งาน")

    services = tenant.get("services", {})
    slip_info = services.get("slip", tenant)

    if not slip_info.get("active", True):
        raise HTTPException(status_code=403, detail="บริการสแกนสลิปยังไม่ได้เปิดใช้งาน")

    today_str = datetime.now().strftime("%Y-%m-%d")
    if today_str > slip_info.get("expire_date", "2000-01-01"):
        raise HTTPException(status_code=403, detail="License Key หมดอายุแล้ว")

    if slip_info.get("used_quota", 0) >= slip_info.get("total_quota", 0):
        raise HTTPException(status_code=429, detail="โควต้าการสแกนสลิปหมดแล้ว")

    return tenant, slip_info


def redeem_slip_atomic(tenant_key: str, log_data: dict):
    """ตรวจสอบซ้ำและหักโควต้าแบบ atomic ในทรานแซกชันเดียว (แก้ race condition)
    คืนค่า (ok: bool, status: str, payload: dict|None)
    status เป็นหนึ่งใน: ok, duplicate, not_found, suspended, service_inactive, expired, quota_exceeded
    """
    tenant_ref = db.collection("tenants").document(tenant_key)
    slip_ref = db.collection("scanned_slips").document(log_data["transRef"])

    transaction = db.transaction()

    @firestore.transactional
    def _txn(transaction):
        slip_snap = slip_ref.get(transaction=transaction)
        if slip_snap.exists:
            return False, "duplicate", slip_snap.to_dict()

        tenant_snap = tenant_ref.get(transaction=transaction)
        if not tenant_snap.exists:
            return False, "not_found", None
        tenant = tenant_snap.to_dict()

        if not tenant.get("active", True):
            return False, "suspended", tenant

        services = tenant.get("services", {})
        is_nested = "slip" in services
        slip_info = services["slip"] if is_nested else tenant

        if not slip_info.get("active", True):
            return False, "service_inactive", tenant

        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str > slip_info.get("expire_date", "2000-01-01"):
            return False, "expired", tenant

        used = slip_info.get("used_quota", 0)
        total = slip_info.get("total_quota", 0)
        if used >= total:
            return False, "quota_exceeded", tenant

        if is_nested:
            transaction.update(tenant_ref, {"services.slip.used_quota": firestore.Increment(1)})
        else:
            transaction.update(tenant_ref, {"used_quota": firestore.Increment(1)})

        transaction.set(slip_ref, log_data)

        remaining = total - (used + 1)
        return True, "ok", {"tenant": tenant, "remaining": remaining}

    return _txn(transaction)


REASON_MESSAGES = {
    "duplicate": "สลิปนี้ถูกใช้งานไปแล้ว (Anti-Reuse)",
    "not_found": "License Key ไม่ถูกต้อง",
    "suspended": "บัญชีถูกระงับการใช้งาน",
    "service_inactive": "บริการสแกนสลิปยังไม่ได้เปิดใช้งาน",
    "expired": "License Key หมดอายุแล้ว",
    "quota_exceeded": "โควต้าการสแกนสลิปหมดแล้ว",
}


def send_line_message(channel_access_token: str, to_user_id: str, message: str):
    """ส่งข้อความแจ้งเตือนผ่าน LINE Messaging API (Push)"""
    if not channel_access_token or not to_user_id:
        return
    try:
        requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {channel_access_token}",
                "Content-Type": "application/json",
            },
            json={"to": to_user_id, "messages": [{"type": "text", "text": message[:5000]}]},
            timeout=10,
        )
    except Exception as e:
        print(f"LINE push error: {e}")


def line_reply(channel_access_token: str, reply_token: str, message: str):
    """ตอบกลับข้อความผ่าน LINE Messaging API (Reply) — ไม่มีค่าใช้จ่ายเพิ่ม"""
    if not reply_token:
        return
    try:
        requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={
                "Authorization": f"Bearer {channel_access_token}",
                "Content-Type": "application/json",
            },
            json={"replyToken": reply_token, "messages": [{"type": "text", "text": message[:5000]}]},
            timeout=10,
        )
    except Exception as e:
        print(f"LINE reply error: {e}")


def verify_line_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    if not channel_secret or not signature:
        return False
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)


def _call_slipok(filename: str, file_bytes: bytes, content_type: str):
    _require_slipok_config()
    url = f"https://api.slipok.com/api/line/apikey/{BRANCH_ID}"
    headers = {"x-authorization": SLIPOK_API_KEY}
    files = {"files": (filename, file_bytes, content_type)}
    response = requests.post(url, headers=headers, files=files, timeout=30)
    return response.status_code, response.json()


def _build_log_data(tenant_key: str, tenant_name: str, data: dict, source: str):
    return {
        "transRef": data.get("transRef"),
        "tenant_key": tenant_key,
        "tenant_name": tenant_name,
        "amount": data.get("amount", 0),
        "sender": data.get("sender", {}).get("displayName", "N/A"),
        "receiver": data.get("receiver", {}).get("displayName", "N/A"),
        "transDate": data.get("transDate"),
        "transTime": data.get("transTime"),
        "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
    }


# ----------------------------------------------------
# Endpoint 1: REST API สำหรับเว็บไซต์ลูกค้า / ใช้ร่วมกับหน้า Streamlit สมาชิก
# ----------------------------------------------------
@app.post("/api/v1/verify-slip")
@limiter.limit("20/minute")
async def verify_slip_api(
    request: Request,
    x_license_key: str = Header(..., description="ACW License Key ของลูกค้า"),
    file: UploadFile = File(...),
):
    tenant, slip_info = verify_tenant_key(x_license_key)

    file_bytes = await file.read()
    status_code, result = _call_slipok(file.filename, file_bytes, file.content_type)

    if not (status_code == 200 and result.get("success")):
        return {"success": False, "message": result.get("message", "สลิปไม่ถูกต้อง")}

    data = result.get("data", {})
    log_data = _build_log_data(x_license_key, tenant.get("name", "N/A"), data, source="rest_api")

    ok, status, payload = redeem_slip_atomic(x_license_key, log_data)

    if not ok:
        return {"success": False, "message": REASON_MESSAGES.get(status, "ไม่สามารถตรวจสอบสลิปได้")}

    return {
        "success": True,
        "message": "ตรวจสอบสลิปสำเร็จ",
        "data": data,
        "remaining_quota": payload["remaining"],
    }


# ----------------------------------------------------
# Endpoint 2: Webhook สำหรับ LINE OA ของแต่ละร้าน (tenant)
# ต้องตั้งค่า tenants/{tenant_key}.line_oa.channel_access_token
# และ tenants/{tenant_key}.line_oa.channel_secret ไว้ก่อน (ผ่านหน้า Streamlit สมาชิก)
# ----------------------------------------------------
@app.post("/api/v1/line-webhook/{tenant_key}")
@limiter.limit("60/minute")
async def line_webhook(request: Request, tenant_key: str):
    if not db:
        raise HTTPException(status_code=500, detail="ไม่สามารถเชื่อมต่อฐานข้อมูล Firebase ได้")

    body_bytes = await request.body()
    signature = request.headers.get("x-line-signature", "")

    tenant_ref = db.collection("tenants").document(tenant_key)
    tenant_snap = tenant_ref.get()
    if not tenant_snap.exists:
        # ไม่โยน error ที่มีรายละเอียด เพื่อไม่เปิดเผยว่า key ไหนมีอยู่จริง
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลร้านค้า")
    tenant = tenant_snap.to_dict()

    line_cfg = tenant.get("line_oa", {})
    channel_secret = line_cfg.get("channel_secret", "")
    channel_token = line_cfg.get("channel_access_token", "")

    if not channel_secret or not channel_token:
        # ร้านนี้ยังไม่ได้ตั้งค่า LINE OA เพิกเฉยไป (อย่า error 500 ใส่ LINE)
        return {"status": "ignored", "reason": "line_oa_not_configured"}

    if not verify_line_signature(channel_secret, body_bytes, signature):
        raise HTTPException(status_code=401, detail="Signature ไม่ถูกต้อง")

    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    for event in body.get("events", []):
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "image":
            continue

        reply_token = event.get("replyToken")
        message_id = message.get("id")

        content_resp = requests.get(
            f"https://api-data.line.me/v2/bot/message/{message_id}/content",
            headers={"Authorization": f"Bearer {channel_token}"},
            timeout=30,
        )
        if content_resp.status_code != 200:
            line_reply(channel_token, reply_token, "ไม่สามารถดึงรูปภาพได้ กรุณาลองส่งใหม่อีกครั้ง")
            continue

        try:
            status_code, slipok_result = _call_slipok("slip.jpg", content_resp.content, "image/jpeg")
        except HTTPException:
            line_reply(channel_token, reply_token, "ระบบยังไม่พร้อมตรวจสอบสลิปในขณะนี้ กรุณาติดต่อผู้ดูแลระบบ")
            continue
        except Exception:
            line_reply(channel_token, reply_token, "เกิดข้อผิดพลาดในการตรวจสอบสลิป กรุณาลองใหม่อีกครั้ง")
            continue

        if not (status_code == 200 and slipok_result.get("success")):
            line_reply(channel_token, reply_token, f"❌ สลิปไม่ถูกต้อง: {slipok_result.get('message', 'ตรวจสอบไม่สำเร็จ')}")
            continue

        data = slipok_result.get("data", {})
        log_data = _build_log_data(tenant_key, tenant.get("name", "N/A"), data, source="line_webhook")

        ok, status, payload = redeem_slip_atomic(tenant_key, log_data)

        if not ok:
            line_reply(channel_token, reply_token, f"❌ {REASON_MESSAGES.get(status, 'ไม่สามารถตรวจสอบสลิปได้')}")
            continue

        amount = data.get("amount", 0)
        reply_text = (
            f"✅ ตรวจสอบสลิปสำเร็จ\n"
            f"ยอดเงิน: {amount:,.2f} บาท\n"
            f"ผู้โอน: {data.get('sender', {}).get('displayName', 'N/A')}\n"
            f"เวลา: {data.get('transDate')} {data.get('transTime')}\n"
            f"โควต้าคงเหลือ: {payload['remaining']} ครั้ง"
        )
        line_reply(channel_token, reply_token, reply_text)

    return {"status": "ok"}
