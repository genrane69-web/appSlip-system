from fastapi import FastAPI, Header, HTTPException, UploadFile, File
import firebase_admin
from firebase_admin import credentials, firestore
import requests
from datetime import datetime
import json
import os

app = FastAPI(title="AppCentralWeb API Service")

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

BRANCH_ID = os.getenv("SLIPOK_BRANCH_ID", "SLIPOK0BYYZJR")
SLIPOK_API_KEY = os.getenv("SLIPOK_SECRET_KEY", "SLIPOK0BYYZJR")

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

# ----------------------------------------------------
# Endpoint 1: REST API สำหรับเว็บไซต์ลูกค้า
# ----------------------------------------------------
@app.post("/api/v1/verify-slip")
async def verify_slip_api(
    x_license_key: str = Header(..., description="ACW License Key ของลูกค้า"),
    file: UploadFile = File(...)
):
    tenant, slip_info = verify_tenant_key(x_license_key)
    
    file_bytes = await file.read()
    url = f"https://api.slipok.com/api/line/apikey/{BRANCH_ID}"
    headers = {"x-authorization": SLIPOK_API_KEY}
    files = {"files": (file.filename, file_bytes, file.content_type)}
    
    response = requests.post(url, headers=headers, files=files)
    result = response.json()
    
    if response.status_code == 200 and result.get("success"):
        data = result.get("data", {})
        trans_ref = data.get("transRef")
        
        slip_ref = db.collection("scanned_slips").document(trans_ref)
        if slip_ref.get().exists:
            return {"success": False, "message": "สลิปนี้ถูกใช้งานไปแล้ว (Anti-Reuse)"}
            
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
# Endpoint 2: Webhook สำหรับ LINE OA
# ----------------------------------------------------
@app.post("/api/v1/line-webhook/{tenant_key}")
async def line_webhook(tenant_key: str, body: dict):
    return {"status": "ok"}
