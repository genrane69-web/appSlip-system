import streamlit as st
import requests
import json
import secrets
import os
from datetime import datetime, timedelta

# ====================================================
# 0. ตั้งค่าเชื่อมต่อ Firebase Firestore (ตามโค้ดเดิม)
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

# ====================================================
# 1. ตั้งค่าหน้าตาเว็บและ CSS โทน Luxury Dark Gold
# ====================================================
st.set_page_config(
    page_title="AppCentralWeb - Service Platform",
    page_icon="💎",
    layout="centered"
)

custom_css = """
<style>
    [data-testid="stRadioButton"] > div {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    [data-testid="stRadioButton"] label {
        background-color: #1A1D24;
        border: 1px solid #D4AF37;
        border-radius: 10px;
        padding: 14px 18px;
        width: 100%;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    [data-testid="stRadioButton"] label:hover {
        background-color: #252932;
        border-color: #FFF5C0;
    }

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

# ====================================================
# 2. ฟังก์ชันฐานข้อมูล Firestore & Utilities
# ====================================================
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
    """ตรวจสอบว่าสลิปนี้เคยถูกใช้แล้วหรือไม่ และบันทึกลง log
    แก้ไข: ทำงานแบบ atomic ผ่าน Firestore transaction เพื่อป้องกัน
    กรณีมี 2 คำขอเข้ามาพร้อมกันแล้วทั้งคู่ผ่านการเช็คว่า "ยังไม่เคยใช้" ได้พร้อมกัน
    (race condition / anti-reuse bypass)
    """
    try:
        doc_ref = db.collection("scanned_slips").document(trans_ref)
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

        transaction = db.transaction()

        @firestore.transactional
        def _txn(transaction):
            snap = doc_ref.get(transaction=transaction)
            if snap.exists:
                return False, snap.to_dict()
            transaction.set(doc_ref, log_data)
            return True, log_data

        return _txn(transaction)
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการตรวจสอบประวัติสลิป: {e}")
        return False, None

def send_line_notify(message):
    """ส่งข้อความแจ้งเตือนไปยังแอดมิน

    หมายเหตุสำคัญ: LINE Notify ถูกยกเลิกให้บริการอย่างเป็นทางการไปแล้ว
    ตั้งแต่วันที่ 31 มี.ค. 2025 ฟังก์ชันนี้จึงถูกเปลี่ยนไปใช้
    LINE Messaging API (Push / Multicast) แทน โดยยังคงชื่อฟังก์ชันเดิมไว้
    เพื่อไม่ต้องแก้จุดที่เรียกใช้งานทั่วทั้งไฟล์

    ต้องตั้งค่า secrets เพิ่ม 2 ค่า:
      - LINE_CHANNEL_ACCESS_TOKEN : channel access token ของ LINE OA (ของแอดมิน/แพลตฟอร์ม)
      - LINE_ADMIN_USER_IDS       : userId ของแอดมินที่จะรับแจ้งเตือน คั่นด้วย comma ได้หลายคน
    """
    token = st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    admin_ids_raw = st.secrets.get("LINE_ADMIN_USER_IDS", "")
    if not token or not admin_ids_raw:
        return
    admin_ids = [i.strip() for i in admin_ids_raw.split(",") if i.strip()]
    if not admin_ids:
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    text = message[:5000]
    try:
        if len(admin_ids) == 1:
            payload = {"to": admin_ids[0], "messages": [{"type": "text", "text": text}]}
            requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload, timeout=10)
        else:
            payload = {"to": admin_ids, "messages": [{"type": "text", "text": text}]}
            requests.post("https://api.line.me/v2/bot/message/multicast", headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"LINE Messaging API Error: {e}")

def load_slip_history(limit=50):
    try:
        docs = db.collection("scanned_slips").order_by("scanned_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงประวัติ: {e}")
        return []

BRANCH_ID = st.secrets.get("SLIPOK_BRANCH_ID", "")
SLIPOK_API_KEY = st.secrets.get("SLIPOK_SECRET_KEY", "")
PROMPTPAY_NO = st.secrets.get("PROMPTPAY_NO", "")
# ย้าย URL ของ API ออกมาเป็นค่าตั้งค่าแทนการฝังตรงในโค้ด
API_BASE_URL = st.secrets.get("API_BASE_URL", "https://acw-api.onrender.com")

PACKAGES = {
    "starter": {"name": "🥉 Starter Package", "price": 299, "quota": 500, "days": 30},
    "business": {"name": "🥈 Business Package", "price": 599, "quota": 2000, "days": 30},
    "pro": {"name": "🥇 Pro Package", "price": 999, "quota": 5000, "days": 30}
}

# ====================================================
# 2.1 ป้องกันการเดารหัสผ่าน Admin แบบง่าย (rate limit)
#     เก็บสถานะไว้ใน Firestore เพื่อให้ทำงานข้าม session ได้จริง
# ====================================================
def _get_admin_lock_state():
    doc = db.collection("security").document("admin_login").get()
    return doc.to_dict() if doc.exists else {}

def _record_admin_attempt(success: bool):
    ref = db.collection("security").document("admin_login")
    if success:
        ref.set({"fail_count": 0, "lock_until": None})
        return
    state = _get_admin_lock_state()
    fail_count = state.get("fail_count", 0) + 1
    update = {"fail_count": fail_count}
    if fail_count >= 5:
        update["lock_until"] = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        update["fail_count"] = 0
    ref.set(update, merge=True)

# ====================================================
# 3. ตรวจสอบ URL หน้า Admin (?page=admin)
# ====================================================
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

    CORRECT_ADMIN_PWD = st.secrets.get("ADMIN_PASSWORD", "")
    if not CORRECT_ADMIN_PWD:
        st.error(
            "⚠️ ยังไม่ได้ตั้งค่า ADMIN_PASSWORD ใน Secrets ของแอป กรุณาไปตั้งค่าก่อนใช้งานหน้านี้\n\n"
            "**สำคัญ:** อย่าตั้งรหัสผ่านเดิมที่เคยฝังอยู่ในโค้ด (kunyakronpromsiri01A@) "
            "เพราะรหัสนั้นถือว่าหลุดออกไปแล้วและไม่ปลอดภัยอีกต่อไป"
        )
        st.stop()

    lock_state = _get_admin_lock_state()
    lock_until_str = lock_state.get("lock_until")
    is_locked = False
    if lock_until_str:
        lock_until_dt = datetime.strptime(lock_until_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() < lock_until_dt:
            is_locked = True
            st.error(f"🔒 กรอกรหัสผ่านผิดเกินกำหนด กรุณาลองใหม่อีกครั้งหลังเวลา {lock_until_dt.strftime('%H:%M:%S')}")

    admin_password = None
    if not is_locked:
        admin_password = st.text_input("🔑 กรอกรหัสผ่าน Admin:", type="password", key="admin_pwd_input")

    admin_ok = bool(admin_password) and secrets.compare_digest(admin_password, CORRECT_ADMIN_PWD)

    if admin_password and not admin_ok:
        _record_admin_attempt(False)
        st.error("❌ รหัสผ่านไม่ถูกต้อง")

    if admin_ok:
        _record_admin_attempt(True)
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
                # เพิ่มความยาวของ key จาก 4 ไบต์ (32 บิต) เป็น 8 ไบต์ (64 บิต)
                # เพราะ key นี้ถูกใช้เป็นรหัสผ่านของผู้ใช้งานจริง ไม่ใช่แค่ id ทั่วไป
                new_key = f"ACW-{secrets.token_hex(8).upper()}"
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
                    line_cfg = info.get("line_oa", {})
                    if line_cfg.get("channel_access_token"):
                        st.caption("💬 ตั้งค่า LINE OA Webhook แล้ว")
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
    menu_mode = st.radio(
        "เลือกเมนูที่ต้องการใช้งาน:",
        options=[
            "💎 สมัครใช้งาน / เติมโควต้า (Auto Active)",
            "🔑 สำหรับสมาชิก (สแกนสลิป / ดูคู่มือ API)"
        ],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

    # ====================================================
    # 1. สมัครใช้งาน & ชำระเงินอัตโนมัติ
    # ====================================================
    if "💎 สมัครใช้งาน" in menu_mode:
        st.subheader("🛒 เลือกแพ็กเกจการใช้งาน")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            <div class="package-card">
                <h4>🥉 Starter</h4>
                <h2 style="color: #D4AF37;">฿299</h2>
                <p>สแกนสลิป <b>500</b> ครั้ง</p>
                <p>อายุใช้งาน 30 วัน</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="package-card">
                <h4>🥈 Business</h4>
                <h2 style="color: #D4AF37;">฿599</h2>
                <p>สแกนสลิป <b>2,000</b> ครั้ง</p>
                <p>อายุใช้งาน 30 วัน</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown("""
            <div class="package-card">
                <h4>🥇 Pro</h4>
                <h2 style="color: #D4AF37;">฿999</h2>
                <p>สแกนสลิป <b>5,000</b> ครั้ง</p>
                <p>อายุใช้งาน 30 วัน</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📝 กรอกข้อมูลสั่งซื้อ / เติมโควต้า & ชำระเงิน")

        action_type = st.radio("รูปแบบการทำรายการ:", ["สร้าง Key ใหม่ (ลูกค้าใหม่)", "เติมโควต้า / ต่ออายุ (Key เดิม)"], horizontal=True)

        target_key = ""
        client_shop_name = ""

        if action_type == "สร้าง Key ใหม่ (ลูกค้าใหม่)":
            client_shop_name = st.text_input("ชื่อร้านค้า / ผู้สมัครใช้งาน:", placeholder="เช่น ร้านค้าดีจริง หรือ นายสมชาย")
        else:
            target_key = st.text_input("กรอก Key เดิมของคุณ:", placeholder="เช่น ACW-XXXXXX").strip()
            if target_key:
                tenants = load_tenants()
                if target_key in tenants:
                    client_shop_name = tenants[target_key].get("name", "ลูกค้าเก่า")
                    st.success(f"พบข้อมูล Key: **{client_shop_name}**")
                else:
                    st.error("❌ ไม่พบ Key นี้ในระบบ")

        pkg_choice = st.selectbox(
            "เลือกแพ็กเกจที่ต้องการ:",
            options=list(PACKAGES.keys()),
            format_func=lambda x: f"{PACKAGES[x]['name']} - ฿{PACKAGES[x]['price']} ({PACKAGES[x]['quota']} ครั้ง / {PACKAGES[x]['days']} วัน)"
        )
        selected_pkg = PACKAGES[pkg_choice]

        if client_shop_name or target_key:
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
                * **เมื่อโอนเสร็จแล้ว:** อัปโหลดสลิปด้านล่างเพื่อรับ/เติม Key ทันที
                """)

            payment_slip = st.file_uploader("อัปโหลดสลิปการโอนเงินเพื่อยืนยัน (PNG, JPG)", type=["jpg", "png", "jpeg"], key="auto_payment_slip")

            if payment_slip and st.button("✨ ยืนยันการชำระเงินและรับ/เติม License Key ทันที", use_container_width=True):
                with st.spinner("กำลังตรวจสอบสลิปผ่าน SlipOK..."):
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

                            # 1. เช็คยอดเงิน
                            if paid_amount < selected_pkg["price"]:
                                st.error(f"❌ ยอดเงินในสลิป (฿{paid_amount:.2f}) ไม่ครบตามราคาระบบ (฿{selected_pkg['price']})")
                            else:
                                # 2. เช็คสลิปซ้ำแบบ atomic (Anti-Reuse)
                                is_valid_slip, slip_log = check_and_log_slip(
                                    trans_ref=trans_ref,
                                    data=data,
                                    tenant_key=target_key if target_key else "AUTO_PURCHASE",
                                    tenant_name=client_shop_name
                                )

                                if not is_valid_slip:
                                    st.error("❌ สลิปนี้เคยถูกใช้งานไปแล้ว ไม่สามารถใช้ซ้ำได้")
                                else:
                                    tenants = load_tenants()
                                    final_key = target_key if action_type == "เติมโควต้า / ต่ออายุ (Key เดิม)" else f"ACW-{secrets.token_hex(8).upper()}"

                                    # คำนวณวันหมดอายุและโควต้า
                                    new_exp_date = (datetime.now() + timedelta(days=selected_pkg["days"])).strftime("%Y-%m-%d")

                                    if final_key in tenants:
                                        # กรณีเติมโควต้า Key เดิม: ใช้ atomic increment แทนการอ่าน-บวก-เขียน
                                        # เพื่อกันกรณีมี 2 รายการเติมโควต้า Key เดียวกันเข้ามาพร้อมกันแล้วยอดหาย
                                        db.collection("tenants").document(final_key).update({
                                            "services.slip.total_quota": firestore.Increment(selected_pkg["quota"]),
                                            "services.slip.expire_date": new_exp_date,
                                            "services.slip.active": True
                                        })
                                        tenant_data = load_tenants()[final_key]
                                    else:
                                        # กรณีสร้าง Key ใหม่
                                        tenant_data = {
                                            "name": client_shop_name,
                                            "active": True,
                                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            "services": {
                                                "slip": {
                                                    "active": True,
                                                    "total_quota": selected_pkg["quota"],
                                                    "used_quota": 0,
                                                    "expire_date": new_exp_date
                                                }
                                            }
                                        }
                                        save_single_tenant(final_key, tenant_data)

                                    # แจ้งเตือนแอดมินผ่าน LINE Messaging API
                                    notify_msg = f"\n🎉 รายการทำรายการสำเร็จ!\n👤 ร้าน: {client_shop_name}\n📦 แพ็กเกจ: {selected_pkg['name']} (฿{paid_amount})\n🔑 Key: {final_key}\n📅 หมดอายุ: {new_exp_date}"
                                    send_line_notify(notify_msg)

                                    # แสดงผล
                                    st.balloons()
                                    st.success("🎉 อนุมัติรายการเรียบร้อยแล้ว!")
                                    st.markdown(f"""
                                    <div class="result-box">
                                        <h3 style="color: #D4AF37; margin-top:0;">🔑 ACW License Key ของคุณ:</h3>
                                        <h1 style="color: #4ADE80; font-family: monospace;">{final_key}</h1>
                                        <p><b>ชื่อร้านค้า:</b> {client_shop_name}</p>
                                        <p><b>แพ็กเกจ:</b> {selected_pkg['name']} (+{selected_pkg['quota']} ครั้ง)</p>
                                        <p><b>วันหมดอายุใหม่:</b> {new_exp_date}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.error(f"❌ สลิปไม่ถูกต้อง: {result.get('message', 'ไม่สามารถตรวจสอบสลิปได้')}")
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในระบบ: {e}")

    # ====================================================
    # 2. ส่วนสมาชิกสแกนสลิป & ดูคู่มือ API/Webhook
    #    แก้ไข: ไม่เขียน logic ตรวจสอบ tenant / หักโควต้าซ้ำอีกต่อไป
    #    แต่เรียกผ่าน FastAPI endpoint เดียวกับที่ลูกค้า dev ใช้
    #    เพื่อให้มี "จุดเดียว" ที่ตัดสินใจเรื่องโควต้า/วันหมดอายุ/anti-reuse
    # ====================================================
    else:
        st.subheader("🧾 ตรวจสอบสลิปโอนเงิน (สำหรับสมาชิก)")

        tenant_key = st.text_input("🔑 กรอก ACW License Key ของคุณ:", type="password", placeholder="เช่น ACW-XXXXXX", key="client_key_input")

        uploaded_file = st.file_uploader("อัปโหลดภาพสลิปโอนเงิน (PNG, JPG)", type=["jpg", "png", "jpeg"], key="slip_file_uploader")

        if uploaded_file is not None:
            st.image(uploaded_file, caption="สลิปที่ต้องการตรวจสอบ", width=240)
            if st.button("✨ ตรวจสอบรายการนี้", use_container_width=True, key="btn_check_slip"):
                if not tenant_key:
                    st.error("⚠️ กรุณากรอก ACW License Key ก่อนทำการตรวจสอบ")
                else:
                    with st.spinner("กำลังตรวจสอบสลิป..."):
                        try:
                            resp = requests.post(
                                f"{API_BASE_URL}/api/v1/verify-slip",
                                headers={"x-license-key": tenant_key},
                                files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                                timeout=30
                            )
                            try:
                                result = resp.json()
                            except ValueError:
                                result = {}

                            if resp.status_code == 200 and result.get("success"):
                                data = result.get("data", {})
                                remaining = result.get("remaining_quota", 0)

                                st.success("✅ ตรวจสอบสำเร็จ: สลิปนี้ถูกต้องและผ่านการโอนจริง")
                                st.caption(f"📊 โควต้าคงเหลือ: {remaining} ครั้ง")

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
                            elif resp.status_code == 401:
                                st.error("❌ License Key ไม่ถูกต้อง หรือไม่มีสิทธิ์ใช้งาน")
                            elif resp.status_code == 403:
                                st.error(f"❌ {result.get('detail', 'บัญชีนี้ไม่สามารถใช้งานบริการได้ในขณะนี้')}")
                            elif resp.status_code == 429:
                                st.error("❌ จำนวนโควต้าสลิปของคุณหมดแล้ว หรือมีการเรียกถี่เกินไป กรุณาลองใหม่ภายหลัง")
                            else:
                                msg = result.get("detail") or result.get("message") or "ไม่สามารถตรวจสอบได้ สลิปไม่ถูกต้อง หรือถูกใช้งานไปแล้ว"
                                st.error(f"❌ {msg}")
                        except requests.exceptions.RequestException as e:
                            st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ API: {e}")

        st.markdown("---")

        with st.expander("⚙️ ตั้งค่า LINE OA สำหรับ Webhook (ถ้าต้องการใช้ผ่านแชท LINE)"):
            st.caption("กรอก Channel access token และ Channel secret ของ LINE OA ร้านคุณ เพื่อให้ Webhook ตรวจสลิปอัตโนมัติทำงานได้จริง")
            line_key_input = st.text_input("ACW License Key:", value=tenant_key or "", key="line_cfg_key")
            line_token_input = st.text_input("Channel access token:", type="password", key="line_cfg_token")
            line_secret_input = st.text_input("Channel secret:", type="password", key="line_cfg_secret")
            if st.button("💾 บันทึกการตั้งค่า LINE OA", key="btn_save_line_cfg"):
                tenants = load_tenants()
                if not line_key_input or line_key_input not in tenants:
                    st.error("❌ ไม่พบ License Key นี้ในระบบ กรุณาตรวจสอบอีกครั้ง")
                elif not line_token_input or not line_secret_input:
                    st.error("⚠️ กรุณากรอกทั้ง Channel access token และ Channel secret")
                else:
                    db.collection("tenants").document(line_key_input).update({
                        "line_oa": {
                            "channel_access_token": line_token_input,
                            "channel_secret": line_secret_input
                        }
                    })
                    st.success("✅ บันทึกการตั้งค่า LINE OA เรียบร้อยแล้ว สามารถใช้ Webhook URL ด้านล่างได้ทันที")

        # ====================================================
        # คู่มือการเชื่อมต่อ API & LINE OA Webhook
        # ====================================================
        display_key = tenant_key.strip() if tenant_key else "ACW-XXXXXX"
        with st.expander("📖 คู่มือการเชื่อมต่อ API & LINE OA Webhook (สำหรับนำไปใช้ในระบบของคุณ)"):
            tab_rest, tab_line = st.tabs(["🔌 REST API (สำหรับนักพัฒนา)", "💬 LINE OA Webhook (สำหรับร้านค้า)"])

            with tab_rest:
                st.markdown("#### 🚀 สำหรับเชื่อมต่อกับเว็บไซต์ / แอปพลิเคชัน")
                st.caption("นำ Endpoint และ Header ด้านล่างนี้ไปใช้ยิง Request จากระบบของคุณ")

                st.markdown("**1. API Endpoint:**")
                st.code(f"POST {API_BASE_URL}/api/v1/verify-slip", language="text")

                st.markdown("**2. HTTP Headers:**")
                st.code(f"x-license-key: {display_key}\nContent-Type: multipart/form-data", language="http")

                st.markdown("**3. ตัวอย่างการส่งคำขอ (cURL):**")
                st.code(f'''curl -X POST "{API_BASE_URL}/api/v1/verify-slip" \\
  -H "x-license-key: {display_key}" \\
  -F "file=@/path/to/slip.jpg"''', language="bash")
                st.caption("หมายเหตุ: API มีการจำกัดจำนวนคำขอ (rate limit) ต่อ IP เพื่อความปลอดภัย")

            with tab_line:
                st.markdown("#### 💬 สำหรับเชื่อมต่อกับ LINE Official Account (LINE OA)")
                st.caption("ก่อนใช้งาน ต้องกรอก Channel access token และ Channel secret ในช่อง 'ตั้งค่า LINE OA' ด้านบนก่อน มิฉะนั้น Webhook จะไม่ตอบสนอง")

                webhook_url = f"{API_BASE_URL}/api/v1/line-webhook/{display_key}"

                st.markdown("**📍 Webhook URL ของคุณ (คัดลอกลิงก์นี้):**")
                st.code(webhook_url, language="text")

                st.markdown("""
                **วิธีนำไปใส่ใน LINE Developers:**
                1. เข้าไปที่เว็บ **[LINE Developers Console](https://developers.line.biz/)** แล้วล็อกอิน
                2. เลือก **Provider** และคลิกเลือก **Messaging API Channel** ของร้านคุณ
                3. ไปที่เมนูแท็บ **Messaging API** คัดลอก **Channel access token** และในแท็บ **Basic settings** คัดลอก **Channel secret** มากรอกในช่อง "ตั้งค่า LINE OA" ด้านบนของหน้านี้
                4. เลื่อนลงมาที่หัวข้อ **Webhook settings** กดปุ่ม **Edit** นำ **Webhook URL** ด้านบนไปวาง แล้วกด **Save**
                5. กดเปิดสวิตช์ **Use webhook** ให้เป็นสีเขียว แล้วลองส่งรูปสลิปเข้าไปในแชทของ LINE OA เพื่อทดสอบ
                """)
