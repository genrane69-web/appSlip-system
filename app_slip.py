import streamlit as st
import requests
import json
import os
from datetime import datetime

# ตั้งค่าหน้าตาเว็บ
st.set_page_config(
    page_title="AppCentralWeb - Slip Verification", 
    page_icon="💎", 
    layout="centered"
)

# ----------------------------------------------------
# 1. อ่านข้อมูลผู้ใช้จากฐานข้อมูล (tenants.json)
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

# ----------------------------------------------------
# 2. ตกแต่งสไตล์ Luxury Dark Gold
# ----------------------------------------------------
custom_css = """
<style>
custom_css = """
<style>
    /* ซ่อน Header, Footer และ Badge มุมขวาล่าง */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    div[class*="stDecoration"] {display: none !important;}
    
    /* โค้ดตกแต่งเดิม... */
    .stApp {
        background-color: #0F1115;
        color: #E2E8F0;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
    }
...
"""

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp {
        background-color: #0F1115;
        color: #E2E8F0;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .brand-header {
        text-align: center;
        padding-top: 15px;
        padding-bottom: 5px;
    }
    .brand-title {
        font-size: 30px;
        font-weight: 800;
        background: linear-gradient(90deg, #D4AF37, #FFF5C0, #AA7C11);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 2px;
        margin-bottom: 4px;
        text-transform: uppercase;
    }
    .brand-subtitle {
        font-size: 11px;
        color: #8A94A6;
        letter-spacing: 1.5px;
    }

    .gold-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #D4AF37, transparent);
        margin: 20px 0 25px 0;
    }

    [data-testid="stFileUploader"] {
        border: 1px dashed #D4AF37 !important;
        border-radius: 12px !important;
        padding: 12px !important;
        background-color: #181B20 !important;
    }

    .result-box {
        background-color: #1A1D24;
        border-left: 3px solid #D4AF37;
        padding: 18px;
        border-radius: 8px;
        margin-top: 15px;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ----------------------------------------------------
# 3. ส่วนหัวแบรนด์ AppCentralWeb
# ----------------------------------------------------
st.markdown("""
<div class="brand-header">
    <div class="brand-title">AppCentralWeb</div>
    <div class="brand-subtitle">AUTOMATED SLIP VERIFICATION SERVICE</div>
</div>
<div class="gold-divider"></div>
""", unsafe_allow_html=True)

BRANCH_ID = "SLIPOK0BYYZJR"

# กำหนด Master API Key ของ SlipOK ในเบื้องหลัง (ดึงจาก Secrets หรือใส่รหัสตรงนี้)
SLIPOK_API_KEY = st.secrets.get("SLIPOK_SECRET_KEY", "ใส่_SECRET_KEY_SLIPOK_ตรงนี้_ถ้าไม่ได้ใช้_SECRETS")

# ----------------------------------------------------
# 4. ฟอร์มการใช้งานของลูกค้า (เหลือช่องกรอก Key เดียว)
# ----------------------------------------------------
st.subheader("🧾 ตรวจสอบสลิปโอนเงิน")

tenant_key = st.text_input("🔑 กรอก ACW License Key ของคุณ:", type="password", placeholder="เช่น ACW-XXXXXX")
uploaded_file = st.file_uploader("อัปโหลดภาพสลิปโอนเงิน (PNG, JPG)", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="สลิปที่ต้องการตรวจสอบ", width=240)
    
    if st.button("✨ ตรวจสอบรายการนี้", use_container_width=True):
        tenants = load_tenants()
        
        if not tenant_key:
            st.error("⚠️ กรุณากรอก ACW License Key ก่อนทำการตรวจสอบ")
        elif tenant_key not in tenants:
            st.error("❌ License Key ไม่ถูกต้อง หรือไม่มีสิทธิ์ใช้งานในระบบ")
        else:
            tenant = tenants[tenant_key]
            
            # ดึงข้อมูลการใช้งาน
            slip_info = tenant.get("services", {}).get("slip", {}) if "services" in tenant else tenant
            
            is_active = slip_info.get("active", True)
            expire_date = slip_info.get("expire_date", "2000-01-01")
            used_quota = slip_info.get("used_quota", 0)
            total_quota = slip_info.get("total_quota", 0)
            
            today_str = datetime.now().strftime("%Y-%m-%d")

            if not is_active:
                st.error("❌ บัญชีของคุณถูกระงับ หรือยังไม่ได้เปิดใช้บริการสลิป")
            elif today_str > expire_date:
                st.error("❌ สิทธิ์การใช้งานของคุณหมดอายุแล้ว กรุณาติดต่อผู้ให้บริการเพื่อต่ออายุ")
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
                            
                            # บันทึกตัดโควต้า
                            if "services" in tenant:
                                tenant["services"]["slip"]["used_quota"] += 1
                            else:
                                tenant["used_quota"] += 1
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
