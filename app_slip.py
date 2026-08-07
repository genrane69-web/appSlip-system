import streamlit as st
import requests
import json
import secrets
import os
from datetime import datetime, timedelta

# ====================================================
# 0. ตั้งค่าเชื่อมต่อ Firebase Firestore
# ====================================================
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    key_dict = dict(st.secrets["firebase_service_account"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ----------------------------------------------------
# 1. ตั้งค่าหน้าตาเว็บและ CSS โทน Luxury Dark Gold
# ----------------------------------------------------
st.set_page_config(
    page_title="AppCentralWeb - All-in-One", 
    page_icon="💎", 
    layout="centered"
)

custom_css = """
<style>
    /* ซ่อนองค์ประกอบส่วนเกินของ Streamlit */
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important; display: none !important;}
    header {visibility: hidden !important; display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    
    .stApp {
        background-color: #0F1115;
        color: #E2E8F0;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .brand-header {
        text-align: center;
        padding-top: 10px;
        padding-bottom: 5px;
    }
    .brand-title {
        font-size: 28px;
        font-weight: 800;
        background: linear-gradient(90deg, #D4AF37, #FFF5C0, #AA7C11);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 2px;
        margin-bottom: 2px;
        text-transform: uppercase;
    }
    .brand-subtitle {
        font-size: 10px;
        color: #8A94A6;
        letter-spacing: 1.5px;
    }
    .gold-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #D4AF37, transparent);
        margin: 15px 0 20px 0;
    }
    [data-testid="stFileUploader"] {
        border: 1px dashed #D4AF37 !important;
        border-radius: 12px !important;
        padding: 10px !important;
        background-color: #181B20 !important;
    }
    .result-box {
        background-color: #1A1D24;
        border-left: 3px solid #D4AF37;
        padding: 15px;
        border-radius: 8px;
        margin-top: 15px;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ----------------------------------------------------
# 2. อ่าน/บันทึกฐานข้อมูลผ่าน Firebase Firestore
# ----------------------------------------------------
def load_tenants():
    try:
        docs = db.collection("tenants").stream()
        tenants = {}
        for doc in docs:
            tenants[doc.id] = doc.to_dict()
        return tenants
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
        return {}

def save_single_tenant(key, tenant_info):
    """บันทึกเฉพาะลูกค้าคนเดียว ป้องกันการบันทึกซ้ำซ้อนเปลืองโควต้า"""
    try:
        db.collection("tenants").document(key).set(tenant_info)
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}")

def delete_tenant(key):
    """ลบข้อมูลออกจาก Firebase Firestore จริง"""
    try:
        db.collection("tenants").document(key).delete()
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการลบข้อมูล: {e}")
        
def check_and_log_slip(trans_ref, data, tenant_key, tenant_name):
    """
    เช็กว่า transRef เคยสแกนหรือยัง (Anti-Reuse)
    ถ้ายังไม่เคย จะทำการบันทึกประวัติทันที
    """
    try:
        doc_ref = db.collection("scanned_slips").document(trans_ref)
        doc = doc_ref.get()
        
        # ❌ สลิปเคยถูกใช้งานไปแล้ว
        if doc.exists:
            return False, doc.to_dict()
            
        # ✅ สลิปใหม่ บันทึกประวัติลง Firestore
        log_data = {
            "transRef": trans_ref,
            "tenant_key": tenant_key,
            "tenant_name": tenant_name,
            "amount": data.get("amount", 0),
            "sender": data.get("sender", {}).get("displayName", "N/A"),
            "receiver": data.get("receiver", {}).get("displayName", "N/A"),
            "transDate": data.get("transDate"),
            "transTime": data.get("transTime"),
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        doc_ref.set(log_data)
        return True, log_data
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการตรวจสอบประวัติสลิป: {e}")
        return False, None

def load_slip_history(limit=50):
    """ดึงประวัติการสแกนสลิปล่าสุดสำหรับแสดงในหน้า Admin"""
    try:
        docs = db.collection("scanned_slips").order_by("scanned_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        history = [doc.to_dict() for doc in docs]
        return history
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงประวัติ: {e}")
        return []

BRANCH_ID = "SLIPOK0BYYZJR"
SLIPOK_API_KEY = st.secrets.get("SLIPOK_SECRET_KEY", "SLIPOK0BYYZJR")

AVAILABLE_SERVICES = {
    "slip": "🧾 ตรวจสอบสลิป (Slip Verification)",
    "line_notify": "💬 แจ้งเตือนผ่าน LINE Notify (อนาคต)",
    "sms": "📱 ระบบส่ง SMS แจ้งเตือน (อนาคต)"
}

# ----------------------------------------------------
# 3. ตรวจสอบ URL ว่าเรียกหน้า Admin หรือไม่ (?page=admin)
# ----------------------------------------------------
query_params = st.query_params
is_admin_page = query_params.get("page") == "admin"

# ----------------------------------------------------
# 4. ส่วนหัวแบรนด์ AppCentralWeb
# ----------------------------------------------------
st.markdown("""
<div class="brand-header">
    <div class="brand-title">AppCentralWeb</div>
    <div class="brand-subtitle">AUTOMATED SERVICE PLATFORM</div>
</div>
<div class="gold-divider"></div>
""", unsafe_allow_html=True)


# ====================================================
# เงื่อนไขแสดงผล: ถ้า URL มี ?page=admin ให้แสดงหน้าแอดมิน
# ====================================================
if is_admin_page:
    st.subheader("🛡️ ระบบผู้ดูแลระบบ (Admin)")
    
    admin_password = st.text_input("🔑 กรอกรหัสผ่าน Admin:", type="password", key="admin_pwd_input")
    
    # ดึงรหัสผ่านจาก Secrets (หากหาไม่พบจะดึงค่าสำรองมาใช้)
    CORRECT_ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "kunyakronpromsiri01A@")

    if admin_password == CORRECT_ADMIN_PWD:
        st.success("เข้าสู่ระบบ Admin เรียบร้อยแล้ว")
        tenants = load_tenants()
        
        # 1. ฟอร์มสร้าง Key
        st.markdown("### ➕ ออก License Key และแพ็กเกจใหม่")
        with st.form("create_key_form_united"):
            client_name = st.text_input("ชื่อลูกค้า / ชื่อร้านค้า:")
            days = st.number_input("ระยะเวลาใช้งานหลัก (วัน):", min_value=1, value=30)
            
            enable_slip = st.checkbox("🧾 เปิดใช้บริการสแกนสลิป", value=True)
            slip_quota = st.number_input("โควต้าสแกนสลิป (ครั้ง/เดือน):", value=500, step=50) if enable_slip else 0
            
            enable_line = st.checkbox("💬 เปิดใช้บริการ LINE Notify (อนาคต)", value=False)
            line_quota = st.number_input("โควต้า LINE (ครั้ง/เดือน):", value=1000, step=100) if enable_line else 0
            
            submit = st.form_submit_button("🚀 สร้าง Key ใหม่ทันที", use_container_width=True)
            
            if submit:
                if client_name:
                    new_key = f"ACW-{secrets.token_hex(4).upper()}"
                    exp_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
                    
                    new_tenant_data = {
                        "name": client_name,
                        "active": True,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "services": {
                            "slip": {
                                "active": enable_slip,
                                "total_quota": slip_quota if enable_slip else 0,
                                "used_quota": 0,
                                "expire_date": exp_date if enable_slip else "2000-01-01"
                            },
                            "line_notify": {
                                "active": enable_line,
                                "total_quota": line_quota if enable_line else 0,
                                "used_quota": 0,
                                "expire_date": exp_date if enable_line else "2000-01-01"
                            }
                        }
                    }
                    save_single_tenant(new_key, new_tenant_data)
                    st.success(f"สร้าง Key สำเร็จเรียบร้อยสำหรับ: **{client_name}**")
                    st.code(new_key, language="text")
                    st.rerun()
                else:
                    st.warning("⚠️ กรุณากรอกชื่อลูกค้า")
                    
        st.markdown("---")
        
        # 2. แสดงรายการผู้เช่าทั้งหมด
        st.markdown("### 📋 จัดการผู้เช่าและควบคุมสิทธิ์")
        
        if tenants:
            for key, info in list(tenants.items()):
                master_active = info.get("active", True)
                status_tag = "🟢 ปกติ" if master_active else "🔴 ระงับทั้งบัญชี"
                
                with st.expander(f"👤 {info.get('name', 'ไม่ระบุชื่อ')} [{status_tag}] - Key: {key}"):
                    st.write(f"**License Key:** `{key}`")
                    
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        if master_active:
                            if st.button("⛔ ระงับสิทธิ์ทุกบริการ", key=f"ban_all_{key}"):
                                info["active"] = False
                                save_single_tenant(key, info)
                                st.rerun()
                        else:
                            if st.button("✅ ปลดระงับทุกบริการ", key=f"unban_all_{key}"):
                                info["active"] = True
                                save_single_tenant(key, info)
                                st.rerun()
                    with col_m2:
                        if st.button("🗑️ ลบบัญชีนี้", key=f"del_master_{key}"):
                            delete_tenant(key)
                            st.rerun()
                    
                    st.markdown("#### ⚙️ สถานะบริการในระบบ")
                    services = info.get("services", {})
                    if not services:
                        services = {"slip": {"active": info.get("active", True), "total_quota": info.get("total_quota", 0), "used_quota": info.get("used_quota", 0), "expire_date": info.get("expire_date", "2000-01-01")}}
                    
                    for s_id, s_name in AVAILABLE_SERVICES.items():
                        s_data = services.get(s_id, {"active": False, "total_quota": 0, "used_quota": 0, "expire_date": "2000-01-01"})
                        
                        st.markdown(f"**{s_name}**")
                        c1, c2, c3 = st.columns([2, 2, 2])
                        
                        with c1:
                            st.caption(f"สถานะ: {'🟢 เปิดใช้' if s_data.get('active') else '⚪ ปิดใช้งาน'}")
                            st.caption(f"หมดอายุ: {s_data.get('expire_date')}")
                        with c2:
                            st.caption(f"โควต้า: {s_data.get('used_quota')}/{s_data.get('total_quota')} ครั้ง")
                        with c3:
                            btn_label = "ปิดบริการนี้" if s_data.get('active') else "เปิดบริการนี้"
                            if st.button(btn_label, key=f"toggle_{key}_{s_id}"):
                                if "services" not in info:
                                    info["services"] = services
                                
                                if s_id not in info["services"]:
                                    info["services"][s_id] = {"active": True, "total_quota": 500, "used_quota": 0, "expire_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")}
                                else:
                                    info["services"][s_id]["active"] = not info["services"][s_id]["active"]
                                    
                                save_single_tenant(key, info)
                                st.rerun()

                        if s_data.get('active'):
                            with st.popover(f"🛠️ ปรับแต่ง {s_id}"):
                                new_q = st.number_input("ปรับโควต้าใหม่:", value=s_data.get('total_quota'), key=f"q_{key}_{s_id}")
                                add_d = st.number_input("บวกจำนวนวันเพิ่ม:", value=30, key=f"d_{key}_{s_id}")
                                
                                col_p1, col_p2 = st.columns(2)
                                if col_p1.button("รีเซ็ตสถิติ/เซฟโควต้า", key=f"save_q_{key}_{s_id}"):
                                    info["services"][s_id]["total_quota"] = new_q
                                    info["services"][s_id]["used_quota"] = 0
                                    save_single_tenant(key, info)
                                    st.success("อัปเดตโควต้าแล้ว")
                                    st.rerun()
                                    
                                if col_p2.button("ขยายวันหมดอายุ", key=f"save_d_{key}_{s_id}"):
                                    try:
                                        curr = datetime.strptime(s_data.get('expire_date'), "%Y-%m-%d")
                                    except:
                                        curr = datetime.now()
                                    base = datetime.now() if curr < datetime.now() else curr
                                    info["services"][s_id]["expire_date"] = (base + timedelta(days=add_d)).strftime("%Y-%m-%d")
                                    save_single_tenant(key, info)
                                    st.success("ขยายเวลาแล้ว")
                                    st.rerun()
                        st.divider()
        else:
            st.info("ยังไม่มีผู้เช่าในระบบ")

        # ----------------------------------------------------
        # 3. แสดงตารางประวัติการสแกนสลิปย้อนหลัง (History Log)
        # ----------------------------------------------------
        st.markdown("---")
        st.markdown("### 📜 ประวัติการสแกนสลิปย้อนหลัง (History Log)")
        
        history_data = load_slip_history(limit=50)
        
        if history_data:
            st.dataframe(
                history_data,
                column_config={
                    "scanned_at": "เวลาที่สแกน",
                    "tenant_name": "ชื่อผู้ใช้ / ร้านค้า",
                    "tenant_key": "License Key",
                    "amount": st.column_config.NumberColumn("ยอดเงิน", format="฿%.2f"),
                    "sender": "ชื่อผู้โอน",
                    "receiver": "ชื่อผู้รับ",
                    "transRef": "เลขที่รายการ (transRef)",
                    "transDate": "วันที่สลิป",
                    "transTime": "เวลาสลิป"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("💡 ยังไม่มีประวัติการสแกนสลิปในระบบ")

    elif admin_password:
        st.error("❌ รหัสผ่าน Admin ไม่ถูกต้อง")

# ====================================================
# หากไม่ใช่ ?page=admin ให้แสดงหน้าตรวจสอบสลิปของลูกค้าปกติ
# ====================================================
else:
    st.subheader("🧾 ตรวจสอบสลิปโอนเงิน")

    tenant_key = st.text_input("🔑 กรอก ACW License Key ของคุณ:", type="password", placeholder="เช่น ACW-XXXXXX", key="client_key_input")

    # ----------------------------------------------------
    # 💡 ปุ่มคู่มือ API & Webhook สำหรับลูกค้า
    # ----------------------------------------------------
    if tenant_key:
        display_key = tenant_key.strip()
    else:
        display_key = "ACW-XXXXXX"

    with st.expander("📖 คู่มือการเชื่อมต่อ API & LINE OA Webhook (สำหรับนำไปใช้ในระบบของคุณ)"):
        tab_rest, tab_line = st.tabs(["🔌 REST API (สำหรับนักพัฒนา)", "💬 LINE OA Webhook (สำหรับร้านค้า)"])
        
        # --- TAB 1: REST API ---
        with tab_rest:
            st.markdown("#### 🚀 สำหรับเชื่อมต่อกับเว็บไซต์ / แอปพลิเคชัน")
            st.caption("นำ Endpoint และ Header ด้านล่างนี้ไปใช้ยิง Request จากระบบของคุณ")
            
            st.markdown("**1. API Endpoint:**")
            st.code("POST https://your-api-domain.com/api/v1/verify-slip", language="text")
            
            st.markdown("**2. HTTP Headers:**")
            st.code(f"x-license-key: {display_key}\nContent-Type: multipart/form-data", language="http")
            
            st.markdown("**3. ตัวอย่างการส่งคำขอ (cURL):**")
            st.code(f'''curl -X POST "https://your-api-domain.com/api/v1/verify-slip" \\
  -H "x-license-key: {display_key}" \\
  -F "file=@/path/to/slip.jpg"''', language="bash")

        # --- TAB 2: LINE OA Webhook ---
        with tab_line:
            st.markdown("#### 💬 สำหรับเชื่อมต่อกับ LINE Official Account (LINE OA)")
            st.caption("ทำตาม 5 ขั้นตอนนี้เพื่อเปิดใช้งานระบบตรวจสลิปอัตโนมัติใน LINE OA ของคุณ")
            
            webhook_url = f"https://your-api-domain.com/api/v1/line-webhook/{display_key}"
            
            st.markdown("**📍 Webhook URL ของคุณ (คัดลอกลิงก์นี้):**")
            st.code(webhook_url, language="text")
            
            st.markdown("""
            **วิธีนำไปใส่ใน LINE Developers:**
            1. เข้าไปที่เว็บ **[LINE Developers Console](https://developers.line.biz/)** แล้วล็อกอิน
            2. เลือก **Provider** และคลิกเลือก **Messaging API Channel** ของร้านคุณ
            3. ไปที่เมนูแท็บ **Messaging API**
            4. เลื่อนลงมาที่หัวข้อ **Webhook settings** กดปุ่ม **Edit** นำ **Webhook URL** ด้านบนไปวาง แล้วกด **Save**
            5. กดเปิดสวิตช์ **Use webhook** ให้เป็นสีเขียว
            """)

    st.markdown("---")

    uploaded_file = st.file_uploader("อัปโหลดภาพสลิปโอนเงิน (PNG, JPG)", type=["jpg", "png", "jpeg"], key="slip_file_uploader")

    if uploaded_file is not None:
        st.image(uploaded_file, caption="สลิปที่ต้องการตรวจสอบ", width=240)
        
        if st.button("✨ ตรวจสอบรายการนี้", use_container_width=True, key="btn_check_slip"):
            tenants = load_tenants()
            
            if not tenant_key:
                st.error("⚠️ กรุณากรอก ACW License Key ก่อนทำการตรวจสอบ")
            elif tenant_key not in tenants:
                st.error("❌ License Key ไม่ถูกต้อง หรือไม่มีสิทธิ์ใช้งานในระบบ")
            else:
                tenant = tenants[tenant_key]
                
                # เช็กสิทธิ์หลัก
                if not tenant.get("active", True):
                    st.error("❌ บัญชีของคุณถูกระงับการใช้งานชั่วคราว กรุณาติดต่อผู้ดูแลระบบ")
                else:
                    # ดึงข้อมูลบริการสลิป
                    services = tenant.get("services", {})
                    if "slip" in services:
                        slip_info = services["slip"]
                        is_nested = True
                    else:
                        slip_info = tenant
                        is_nested = False
                    
                    is_active = slip_info.get("active", True)
                    expire_date = slip_info.get("expire_date", "2000-01-01")
                    used_quota = slip_info.get("used_quota", 0)
                    total_quota = slip_info.get("total_quota", 0)
                    today_str = datetime.now().strftime("%Y-%m-%d")

                    if not is_active:
                        st.error("❌ บัญชีของคุณยังไม่ได้เปิดใช้บริการสแกนสลิป")
                    elif today_str > expire_date:
                        st.error("❌ สิทธิ์การใช้งานสแกนสลิปของคุณหมดอายุแล้ว กรุณาติดต่อผู้ให้บริการเพื่อต่ออายุ")
                    elif used_quota >= total_quota:
                        st.error("❌ จำนวนโควต้าสลิปของคุณหมดแล้ว กรุณาอัปเกรดแพ็กเกจ")
                    else:
                        with st.spinner("กำลังเชื่อมต่อระบบธนาคาร..."):
                            try:
                                url = f"https://api.slipok.com/api/line/apikey/{BRANCH_ID}"
                                headers = {"x-authorization": SLIPOK_API_KEY}
                                files = {"files": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}

                                response = requests.post(url, headers=headers, files=files)
                                result = response.json()

                                if response.status_code == 200 and result.get("success"):
                                    data = result.get("data", {})
                                    trans_ref = data.get("transRef")
                                    
                                    # 🛑 เช็กสลิปซ้ำ (Anti-Reuse Check)
                                    is_valid_slip, slip_log = check_and_log_slip(
                                        trans_ref=trans_ref, 
                                        data=data, 
                                        tenant_key=tenant_key, 
                                        tenant_name=tenant.get("name", "N/A")
                                    )
                                    
                                    if not is_valid_slip:
                                        st.error("❌ **สลิปนี้ถูกใช้งานไปแล้ว! (Anti-Reuse)**")
                                        if slip_log:
                                            st.warning(f"⚠️ ถูกสแกนครั้งแรกเมื่อ: {slip_log.get('scanned_at')} โดยบัญชี: {slip_log.get('tenant_name')}")
                                    else:
                                        # หักโควต้าและบันทึกข้อมูลลูกค้า
                                        if is_nested:
                                            tenant["services"]["slip"]["used_quota"] += 1
                                        else:
                                            tenant["used_quota"] += 1
                                        
                                        save_single_tenant(tenant_key, tenant)
                                        
                                        st.success("✅ ตรวจสอบสำเร็จ: สลิปนี้ถูกต้องและผ่านการโอนจริง")
                                        st.caption(f"📊 โควต้าคงเหลือ: {total_quota - (used_quota + 1)} / {total_quota} ครั้ง")
                                        
                                        st.markdown(f"""
                                        <div class="result-box">
                                            <h4 style="color: #D4AF37; margin-top: 0;">📋 รายละเอียดการชำระเงิน</h4>
                                            <p><b>ยอดเงิน:</b> <span style="font-size: 18px; color: #4ADE80;">฿{data.get('amount', 0):,.2f}</span></p>
                                            <p><b>ผู้โอน:</b> {data.get('sender', {}).get('displayName', 'N/A')}</p>
                                            <p><b>ผู้รับ:</b> {data.get('receiver', {}).get('displayName', 'N/A')}</p>
                                            <p><b>วัน-เวลา:</b> {data.get('transDate')} ({data.get('transTime')})</p>
                                            <p><b>เลขที่รายการ:</b> {data.get('transRef')}</p>
                                        </div>
                                        """, unsafe_allow_html=True)
                                else:
                                    st.error(f"❌ ไม่สามารถตรวจสอบได้: {result.get('message', 'สลิปไม่ถูกต้อง หรือถูกใช้งานไปแล้ว')}")
                            except Exception as e:
                                st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
