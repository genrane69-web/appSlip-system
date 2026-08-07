from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
import firebase_admin
from firebase_admin import credentials, firestore
import requests
from datetime import datetime
import json
import os

app = FastAPI(title="AppCentralWeb API Service")

# 1. เชื่อมต่อ Firebase (ใช้ไฟล์ Service Account เดียวกับ Streamlit)
if not firebase_admin._apps:
    # โหลดไฟล์ credentials จาก environment หรือไฟล์ json
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

BRANCH_ID = "SLIPOK0BYYZJR"
SLIPOK_API_KEY = os.getenv("SLIPOK_SECRET_KEY", "SLIPOK0BYYZJR")

# ----------------------------------------------------
# Helper Functions
# ----------------------------------------------------
def verify_tenant_key(tenant_key: str):
    """ตรวจสอบ License Key และเช็กสิทธิ์/โควต้า"""
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

# ----------------------------------------------------
# Endpoint 1: REST API สำหรับเว็บไซต์/แอปพลิเคชันของลูกค้า
# ----------------------------------------------------
@app.post("/api/v1/verify-slip")
async def verify_slip_api(
    x_license_key: str = Header(..., description="ACW License Key ของลูกค้า"),
    file: UploadFile = File(...)
):
    """
    ลูกค้าส่งไฟล์ภาพสลิปมาพร้อม Header: x-license-key
    """
    # 1. ตรวจสอบ Key และโควต้า
    tenant, slip_info = verify_tenant_key(x_license_key)
    
    # 2. อ่านไฟล์และส่งหา SlipOK API
    file_bytes = await file.read()
    url = f"https://api.slipok.com/api/line/apikey/{BRANCH_ID}"
    headers = {"x-authorization": SLIPOK_API_KEY}
    files = {"files": (file.filename, file_bytes, file.content_type)}
    
    response = requests.post(url, headers=headers, files=files)
    result = response.json()
    
    if response.status_code == 200 and result.get("success"):
        data = result.get("data", {})
        trans_ref = data.get("transRef")
        
        # 3. เช็ก Anti-Reuse
        slip_ref = db.collection("scanned_slips").document(trans_ref)
        if slip_ref.get().exists:
            return {"success": False, "message": "สลิปนี้ถูกใช้งานไปแล้ว (Anti-Reuse)"}
            
        # บันทึกสลิป
        slip_ref.set({
            "transRef": trans_ref,
            "tenant_key": x_license_key,
            "tenant_name": tenant.get("name", "N/A"),
            "amount": data.get("amount", 0),
            "sender": data.get("sender", {}).get("displayName", "N/A"),
            "receiver": data.get("receiver", {}).get("displayName", "N/A"),
            "transDate": data.get("transDate"),
            "transTime": data.get("transTime"),
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 4. ตัดโควต้าใน Firebase
        if "services" in tenant and "slip" in tenant["services"]:
            tenant["services"]["slip"]["used_quota"] += 1
        else:
            tenant["used_quota"] += 1
            
        db.collection("tenants").document(x_license_key).set(tenant)
        
        return {
            "success": True,
            "message": "ตรวจสอบสลิปสำเร็จ",
            "data": data,
            "remaining_quota": slip_info.get("total_quota", 0) - (slip_info.get("used_quota", 0) + 1)
        }
    else:
        return {"success": False, "message": result.get("message", "สลิปไม่ถูกต้อง")}

# ----------------------------------------------------
# Endpoint 2: Webhook สำหรับ LINE Official Account (LINE OA)
# ----------------------------------------------------
@app.post("/api/v1/line-webhook/{tenant_key}")
async def line_webhook(tenant_key: str, body: dict):
    """
    นำ URL นี้ไปใส่ใน LINE Developers Webhook URL ของร้านค้าลูกค้า:
    https://your-api-domain.com/api/v1/line-webhook/ACW-XXXXXX
    """
    events = body.get("events", [])
    for event in events:
        if event.get("type") == "message" and event.get("message", {}).get("type") == "image":
            # รับภาพสลิปจาก LINE OA -> ดึงภาพ -> ส่งสแกน -> ตอบกลับข้อความหาลูกค้า
            reply_token = event.get("replyToken")
            # Logic ดึงรูปจาก LINE Content API และตรวจสอบสลิป...
            
    return {"status": "ok"}
