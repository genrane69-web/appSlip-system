import streamlit as st
import requests
import json
import secrets
import os
from datetime import datetime, timedelta

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
# 2. อ่าน/บันทึกฐานข้อมูล
# ----------------------------------------------------
DB_FILE = "tenants.json"

def load_tenants():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_tenants(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

BRANCH_ID = "SLIPOK0BYYZJR"
SLIPOK_API_KEY = st.secrets.get("SLIPOK_SECRET_KEY", "SLIPOK0BYYZJR")

AVAILABLE_SERVICES = {
    "slip": "🧾 ตรวจสอบสลิป (Slip Verification)",
    "line_notify": "💬 แจ้งเตือนผ่าน LINE Notify (อนาคต)",
    "sms": "📱 ระบบส่ง SMS แจ้งเตือน (อนาคต)"
}

# ----------------------------------------------------
# 3. ส่วนหัวแบรนด์ AppCentralWeb
# ----------------------------------------------------
st.markdown("""
<div class="brand-header">
    <div class="brand-title">AppCentralWeb</div>
    <div class="brand-subtitle">AUTOMATED SERVICE PLATFORM</div>
</div>
<div class="gold-divider"></div>
""", unsafe_allow_html=True)

# ====================================================
# 4. หน้าฝั่งลูกค้า (ตรวจสอบสลิป - หน้าหลัก)
# ====================================================
st.subheader("🧾 ตรวจสอบสลิปโอนเงิน")

tenant_key = st.text_input("🔑 กรอก ACW License Key ของคุณ:", type="password", placeholder="เช่น ACW-XXXXXX", key="client_key_input")
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
                                
                                # หักโควต้าและบันทึกข้อมูล
                                if is_nested:
                                    tenants[tenant_key]["services"]["slip"]["used_quota"] += 1
                                else:
                                    tenants[tenant_key]["used_quota"] += 1
                                save_tenants(tenants)
                                
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

st.markdown("<br><br>", unsafe_allow_html=True)

# ====================================================
# 5. ฝั่งผู้ดูแลระบบ (Admin - ซ่อนไว้ล่างสุดของหน้า)
# ====================================================
with st.expander("🛡️"):
    st.subheader("🛡️ ระบบจัดการ (Admin)")
    
    admin_password = st.text_input("🔑 กรอกรหัสผ่าน Admin:", type="password", key="admin_pwd_input")
    
    if admin_password == "kunyakronpromsiri01A@":
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
                    
                    tenants[new_key] = {
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
                    save_tenants(tenants)
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
                                tenants[key]["active"] = False
                                save_tenants(tenants)
                                st.rerun()
                        else:
                            if st.button("✅ ปลดระงับทุกบริการ", key=f"unban_all_{key}"):
                                tenants[key]["active"] = True
                                save_tenants(tenants)
                                st.rerun()
                    with col_m2:
                        if st.button("🗑️ ลบบัญชีนี้", key=f"del_master_{key}"):
                            del tenants[key]
                            save_tenants(tenants)
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
                                if "services" not in tenants[key]:
                                    tenants[key]["services"] = services
                                
                                if s_id not in tenants[key]["services"]:
                                    tenants[key]["services"][s_id] = {"active": True, "total_quota": 500, "used_quota": 0, "expire_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")}
                                else:
                                    tenants[key]["services"][s_id]["active"] = not tenants[key]["services"][s_id]["active"]
                                    
                                save_tenants(tenants)
                                st.rerun()

                        if s_data.get('active'):
                            with st.popover(f"🛠️ ปรับแต่ง {s_id}"):
                                new_q = st.number_input("ปรับโควต้าใหม่:", value=s_data.get('total_quota'), key=f"q_{key}_{s_id}")
                                add_d = st.number_input("บวกจำนวนวันเพิ่ม:", value=30, key=f"d_{key}_{s_id}")
                                
                                col_p1, col_p2 = st.columns(2)
                                if col_p1.button("รีเซ็ตสถิติ/เซฟโควต้า", key=f"save_q_{key}_{s_id}"):
                                    tenants[key]["services"][s_id]["total_quota"] = new_q
                                    tenants[key]["services"][s_id]["used_quota"] = 0
                                    save_tenants(tenants)
                                    st.success("อัปเดตโควต้าแล้ว")
                                    st.rerun()
                                    
                                if col_p2.button("ขยายวันหมดอายุ", key=f"save_d_{key}_{s_id}"):
                                    try:
                                        curr = datetime.strptime(s_data.get('expire_date'), "%Y-%m-%d")
                                    except:
                                        curr = datetime.now()
                                    base = datetime.now() if curr < datetime.now() else curr
                                    tenants[key]["services"][s_id]["expire_date"] = (base + timedelta(days=add_d)).strftime("%Y-%m-%d")
                                    save_tenants(tenants)
                                    st.success("ขยายเวลาแล้ว")
                                    st.rerun()
                        st.divider()
        else:
            st.info("ยังไม่มีผู้เช่าในระบบ")

    elif admin_password:
        st.error("❌ รหัสผ่าน Admin ไม่ถูกต้อง")
