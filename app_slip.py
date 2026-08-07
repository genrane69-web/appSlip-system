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
    page_title="AppCentralWeb - Service Platform", 
    page_icon="💎", 
    layout="centered"
)

custom_css = """
<style>
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
    .package-card {
        background-color: #1A1D24;
        border: 1px solid #D4AF37;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        margin-bottom: 10px;
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
    try:
        db.collection("tenants").document(key).set(tenant_info)
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}")

def delete_tenant(key):
    try:
        db.collection("tenants").document(key).delete()
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการลบข้อมูล: {e}")
        
def check_and_log_slip(trans_ref, data, tenant_key, tenant_name):
    try:
        doc_ref = db.collection("scanned_slips").document(trans_ref)
        doc = doc_ref.get()
        if doc.exists:
            return False, doc.to_dict()
            
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

def send_line_notify(message):
    """ส่งการแจ้งเตือนไปยัง LINE Notify ของ Admin"""
    token = st.secrets.get("LINE_NOTIFY_TOKEN", "")
    if token:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            requests.post("https://notify-api.line.me/api/notify", headers=headers, data={"message": message})
        except Exception as e:
            print(f"LINE Notify Error: {e}")

def load_slip_history(limit=50):
    try:
        docs = db.collection("scanned_slips").order_by("scanned_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงประวัติ: {e}")
        return []

BRANCH_ID = "SLIPOK0BYYZJR"
SLIPOK_API_KEY = st.secrets.get("SLIPOK_SECRET_KEY", "SLIPOK0BYYZJR")
PROMPTPAY_NO = st.secrets.get("PROMPTPAY_NO", "0812345678")

PACKAGES = {
    "starter": {"name": "Starter Package", "price": 299, "quota": 500, "days": 30},
    "business": {"name": "Business Package", "price": 599, "quota": 2000, "days": 30},
    "pro": {"name": "Pro Unlimited", "price": 999, "quota": 10000, "days": 30}
}

# ----------------------------------------------------
# 3. ตรวจสอบ URL ว่าเรียกหน้า Admin หรือไม่ (?page=admin)
# ----------------------------------------------------
query_params = st.query_params
is_admin_page = query_params.get("page") == "admin"

st.markdown("""
<div class="brand-header">
    <div class="brand-title">AppCentralWeb</div>
    <div class="brand-subtitle">AUTOMATED SERVICE PLATFORM</div>
</div>
<div class="gold-divider"></div>
""", unsafe_allow_html=True)

# ====================================================
# หน้า Admin (?page=admin)
# ====================================================
if is_admin_page:
    st.subheader("🛡️ ระบบผู้ดูแลระบบ (Admin)")
    admin_password = st.text_input("🔑 กรอกรหัสผ่าน Admin:", type="password", key="admin_pwd_input")
    CORRECT_ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "kunyakronpromsiri01A@")

    if admin_password == CORRECT_ADMIN_PWD:
        st.success("เข้าสู่ระบบ Admin เรียบร้อยแล้ว")
        tenants = load_tenants()
        
        st.markdown("### ➕ ออก License Key และแพ็กเกจใหม่ (Manual)")
        with st.form("create_key_form_united"):
            client_name = st.text_input("ชื่อลูกค้า / ชื่อร้านค้า:")
            days = st.number_input("ระยะเวลาใช้งานหลัก (วัน):", min_value=1, value=30)
            enable_slip = st.checkbox("🧾 เปิดใช้บริการสแกนสลิป", value=True)
            slip_quota = st.number_input("โควต้าสแกนสลิป (ครั้ง/เดือน):", value=500, step=50) if enable_slip else 0
            
            submit = st.form_submit_button("🚀 สร้าง Key ใหม่ทันที", use_container_width=True)
            if submit and client_name:
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
                        }
                    }
                }
                save_single_tenant(new_key, new_tenant_data)
                st.success(f"สร้าง Key สำเร็จสำหรับ: **{client_name}**")
                st.code(new_key, language="text")
                st.rerun()

        st.markdown("---")
        st.markdown("### 📋 จัดการผู้เช่าและควบคุมสิทธิ์")
        if tenants:
            for key, info in list(tenants.items()):
                master_active = info.get("active", True)
                status_tag = "🟢 ปกติ" if master_active else "🔴 ระงับ"
                with st.expander(f"👤 {info.get('name', 'ไม่ระบุชื่อ')} [{status_tag}] - Key: {key}"):
                    st.write(f"**License Key:** `{key}`")
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        if st.button("⛔ สลับสถานะบัญชี", key=f"toggle_active_{key}"):
                            info["active"] = not master_active
                            save_single_tenant(key, info)
                            st.rerun()
                    with col_m2:
                        if st.button("🗑️ ลบบัญชีนี้", key=f"del_master_{key}"):
                            delete_tenant(key)
                            st.rerun()
        else:
            st.info("ยังไม่มีผู้เช่าในระบบ")

        st.markdown("---")
        st.markdown("### 📜 ประวัติการสแกนสลิปย้อนหลัง")
        history_data = load_slip_history(limit=50)
        if history_data:
            st.dataframe(history_data, use_container_width=True, hide_index=True)

# ====================================================
# หน้าหลักผู้ใช้บริการ (Default Page)
# ====================================================
else:
    tab_register, tab_scan = st.tabs(["💎 สมัครใช้งาน & เลือกแพ็กเกจ (Auto Active)", "🔑 สำหรับสมาชิก (สแกนสลิป/ดูคู่มือ API)"])

    # ----------------------------------------------------
    # TAB 1: สมัครสมาชิกและชำระเงินอัตโนมัติ (Fully Auto)
    # ----------------------------------------------------
    with tab_register:
        st.subheader("🛒 เลือกแพ็กเกจการใช้งาน")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            <div class="package-card">
                <h4>🥉 Starter</h4>
                <h2 style="color: #D4AF37;">฿299</h2>
                <p>สแกนสลิป <b>500</b> ครั้ง/เดือน</p>
                <p>อายุใช้งาน 30 วัน</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="package-card">
                <h4>🥈 Business</h4>
                <h2 style="color: #D4AF37;">฿599</h2>
                <p>สแกนสลิป <b>2,000</b> ครั้ง/เดือน</p>
                <p>อายุใช้งาน 30 วัน</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown("""
            <div class="package-card">
                <h4>🥇 Pro Unlimited</h4>
                <h2 style="color: #D4AF37;">฿999</h2>
                <p>สแกนสลิป <b>10,000</b> ครั้ง/เดือน</p>
                <p>อายุใช้งาน 30 วัน</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📝 กรอกข้อมูลสั่งซื้อ & ชำระเงิน")

        pkg_choice = st.selectbox(
            "เลือกแพ็กเกจที่ต้องการ:", 
            options=list(PACKAGES.keys()), 
            format_func=lambda x: f"{PACKAGES[x]['name']} - ฿{PACKAGES[x]['price']} ({PACKAGES[x]['quota']} ครั้ง)"
        )
        selected_pkg = PACKAGES[pkg_choice]

        client_shop_name = st.text_input("ชื่อร้านค้า / ผู้สมัครใช้งาน:", placeholder="เช่น ร้านค้าดีจริง หรือ นายสมชาย")

        if client_shop_name:
            st.markdown("#### 📱 สแกน QR Code ชำระเงินผ่าน PromptPay")
            qr_url = f"https://promptpay.io/{PROMPTPAY_NO}/{selected_pkg['price']}.png"
            
            c_qr1, c_qr2 = st.columns([1, 2])
            with c_qr1:
                st.image(qr_url, caption=f"ยอดชำระ ฿{selected_pkg['price']}", width=200)
            with c_qr2:
                st.info(f"""
                **รายละเอียดการโอนเงิน:**
                * **จำนวนเงิน:** ฿{selected_pkg['price']}.00
                * **PromptPay:** {PROMPTPAY_NO}
                * **เมื่อโอนเสร็จแล้ว:** อัปโหลดสลิปด้านล่างเพื่อรับ Key ทันที
                """)

            payment_slip = st.file_uploader("อัปโหลดสลิปการโอนเงินเพื่อยืนยัน (PNG, JPG)", type=["jpg", "png", "jpeg"], key="auto_payment_slip")

            if payment_slip and st.button("✨ ยืนยันการชำระเงินและรับ License Key ทันที", use_container_width=True):
                with st.spinner("กำลังตรวจสอบสลิปและสร้าง License Key..."):
                    try:
                        url = f"https://api.slipok.com/api/line/apikey/{BRANCH_ID}"
                        headers = {"x-authorization": SLIPOK_API_KEY}
                        files = {"files": (payment_slip.name, payment_slip.getvalue(), payment_slip.type)}

                        response = requests.post(url, headers=headers, files=files)
                        result = response.json()

                        if response.status_code == 200 and result.get("success"):
                            data = result.get("data", {})
                            trans_ref = data.get("transRef")
                            paid_amount = float(data.get("amount", 0))

                            # 🛑 1. ตรวจสอบยอดเงินให้ตรงกับแพ็กเกจ
                            if paid_amount < selected_pkg["price"]:
                                st.error(f"❌ ยอดเงินในสลิป (฿{paid_amount:.2f}) ไม่ครบตามราคาระบบ (฿{selected_pkg['price']})")
                            else:
                                # 🛑 2. ตรวจสอบสลิปซ้ำ (Anti-Reuse)
                                is_valid_slip, slip_log = check_and_log_slip(
                                    trans_ref=trans_ref, 
                                    data=data, 
                                    tenant_key="AUTO_PAYMENT", 
                                    tenant_name=client_shop_name
                                )

                                if not is_valid_slip:
                                    st.error("❌ สลิปนี้เคยถูกใช้งานอนุมัติไปแล้ว ไม่สามารถใช้ซ้ำได้")
                                else:
                                    # ✅ 3. สร้าง Key อัตโนมัติและบันทึกลง Firestore
                                    generated_key = f"ACW-{secrets.token_hex(4).upper()}"
                                    exp_date = (datetime.now() + timedelta(days=selected_pkg["days"])).strftime("%Y-%m-%d")

                                    new_tenant_data = {
                                        "name": client_shop_name,
                                        "active": True,
                                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "services": {
                                            "slip": {
                                                "active": True,
                                                "total_quota": selected_pkg["quota"],
                                                "used_quota": 0,
                                                "expire_date": exp_date
                                            }
                                        }
                                    }
                                    save_single_tenant(generated_key, new_tenant_data)

                                    # 📩 4. แจ้งเตือนแอดมินผ่าน LINE Notify
                                    notify_msg = f"\n🎉 มีการสมัครใช้งานใหม่!\n👤 ร้าน: {client_shop_name}\n📦 แพ็กเกจ: {selected_pkg['name']} (฿{paid_amount})\n🔑 Key: {generated_key}\n📅 หมดอายุ: {exp_date}"
                                    send_line_notify(notify_msg)

                                    # 🎉 5. แสดง Key บนหน้าจอให้ลูกค้าทันที
                                    st.balloons()
                                    st.success("🎉 ชำระเงินสำเร็จ! ระบบอนุมัติ License Key ให้คุณแล้ว")
                                    st.markdown(f"""
                                    <div class="result-box">
                                        <h3 style="color: #D4AF37; margin-top:0;">🔑 ACW License Key ของคุณ:</h3>
                                        <h1 style="color: #4ADE80; font-family: monospace;">{generated_key}</h1>
                                        <p><b>ชื่อร้านค้า:</b> {client_shop_name}</p>
                                        <p><b>แพ็กเกจ:</b> {selected_pkg['name']} ({selected_pkg['quota']} ครั้ง)</p>
                                        <p><b>วันหมดอายุ:</b> {exp_date}</p>
                                        <p style="color: #E2E8F0; font-size: 13px;">⚠️ <i>กรุณาคัดลอก Key นี้ไว้ เพื่อนำไปใช้สแกนสลิปหรือเชื่อมต่อ API ในระบบของคุณ</i></p>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.error(f"❌ สลิปไม่ถูกต้อง: {result.get('message', 'ไม่สามารถตรวจสอบสลิปได้')}")
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในระบบ: {e}")

    # ----------------------------------------------------
    # TAB 2: สำหรับลูกค้าที่มี Key แล้ว
    # ----------------------------------------------------
    with tab_scan:
        st.subheader("🧾 ตรวจสอบสลิปโอนเงิน (สำหรับสมาชิก)")

        tenant_key = st.text_input("🔑 กรอก ACW License Key ของคุณ:", type="password", placeholder="เช่น ACW-XXXXXX", key="client_key_input")

        uploaded_file = st.file_uploader("อัปโหลดภาพสลิปโอนเงิน (PNG, JPG)", type=["jpg", "png", "jpeg"], key="slip_file_uploader")

        if uploaded_file is not None:
            st.image(uploaded_file, caption="สลิปที่ต้องการตรวจสอบ", width=240)
            if st.button("✨ ตรวจสอบรายการนี้", use_container_width=True, key="btn_check_slip"):
                tenants = load_tenants()
                if not tenant_key:
                    st.error("⚠️ กรุณากรอก ACW License Key ก่อนทำการตรวจสอบ")
                elif tenant_key not in tenants:
                    st.error("❌ License Key ไม่ถูกต้อง หรือไม่มีสิทธิ์ใช้งาน")
                else:
                    tenant = tenants[tenant_key]
                    if not tenant.get("active", True):
                        st.error("❌ บัญชีผู้ใช้นี้ถูกระงับการใช้งานชั่วคราว")
                    else:
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
                            st.error("❌ License Key ของคุณหมดอายุแล้ว กรุณาต่ออายุแพ็กเกจ")
                        elif used_quota >= total_quota:
                            st.error("❌ จำนวนโควต้าสลิปของคุณหมดแล้ว กรุณาอัปเกรดแพ็กเกจ")
                        else:
                            with st.spinner("กำลังตรวจสอบสลิป..."):
                                try:
                                    url = f"https://api.slipok.com/api/line/apikey/{BRANCH_ID}"
                                    headers = {"x-authorization": SLIPOK_API_KEY}
                                    files = {"files": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}

                                    response = requests.post(url, headers=headers, files=files)
                                    result = response.json()

                                    if response.status_code == 200 and result.get("success"):
                                        data = result.get("data", {})
                                        trans_ref = data.get("transRef")
                                        
                                        is_valid_slip, slip_log = check_and_log_slip(trans_ref, data, tenant_key, tenant.get("name", "N/A"))
                                        if not is_valid_slip:
                                            st.error("❌ **สลิปนี้ถูกใช้งานไปแล้ว! (Anti-Reuse)**")
                                            if slip_log:
                                                st.warning(f"⚠️ ถูกสแกนครั้งแรกเมื่อ: {slip_log.get('scanned_at')} โดยบัญชี: {slip_log.get('tenant_name')}")
                                        else:
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

        st.markdown("---")

        # ----------------------------------------------------
        # 💡 คู่มือการเชื่อมต่อ API & LINE OA Webhook
        # ----------------------------------------------------
        display_key = tenant_key.strip() if tenant_key else "ACW-XXXXXX"
        with st.expander("📖 คู่มือการเชื่อมต่อ API & LINE OA Webhook (สำหรับนำไปใช้ในระบบของคุณ)"):
            tab_rest, tab_line = st.tabs(["🔌 REST API (สำหรับนักพัฒนา)", "💬 LINE OA Webhook (สำหรับร้านค้า)"])
            
            # --- TAB 1: REST API ---
            with tab_rest:
                st.markdown("#### 🚀 สำหรับเชื่อมต่อกับเว็บไซต์ / แอปพลิเคชัน")
                st.caption("นำ Endpoint และ Header ด้านล่างนี้ไปใช้ยิง Request จากระบบของคุณ")
                
                st.markdown("**1. API Endpoint:**")
                st.code("POST https://acw-api.onrender.com/api/v1/verify-slip", language="text")
                
                st.markdown("**2. HTTP Headers:**")
                st.code(f"x-license-key: {display_key}\nContent-Type: multipart/form-data", language="http")
                
                st.markdown("**3. ตัวอย่างการส่งคำขอ (cURL):**")
                st.code(f'''curl -X POST "https://acw-api.onrender.com/api/v1/verify-slip" \\
  -H "x-license-key: {display_key}" \\
  -F "file=@/path/to/slip.jpg"''', language="bash")

            # --- TAB 2: LINE OA Webhook ---
            with tab_line:
                st.markdown("#### 💬 สำหรับเชื่อมต่อกับ LINE Official Account (LINE OA)")
                st.caption("ทำตาม 5 ขั้นตอนนี้เพื่อเปิดใช้งานระบบตรวจสลิปอัตโนมัติใน LINE OA ของคุณ")
                
                webhook_url = f"https://acw-api.onrender.com/api/v1/line-webhook/{display_key}"
                
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
