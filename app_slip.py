import streamlit as st
import requests

# ตั้งค่าหน้าตาเว็บ
st.set_page_config(
    page_title="AppCentralWeb - Verification", 
    page_icon="💎", 
    layout="centered"
)

# ตกแต่ง CSS ให้ดูเรียบหรู (Luxury Dark Gold) แบบไม่สร้างกล่องทับซ้อน
custom_css = """
<style>
    /* ซ่อน Header และ Footer ดั้งเดิม */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* พื้นหลังโทนเข้ม */
    .stApp {
        background-color: #0F1115;
        color: #E2E8F0;
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    }

    /* โลโก้และแบรนด์ AppCentralWeb */
    .brand-header {
        text-align: center;
        padding-bottom: 5px;
    }
    .brand-title {
        font-size: 28px;
        font-weight: 700;
        background: linear-gradient(90deg, #D4AF37, #FFF5C0, #AA7C11);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 1.5px;
        margin-bottom: 4px;
        text-transform: uppercase;
    }
    .brand-subtitle {
        font-size: 12px;
        color: #8A94A6;
        letter-spacing: 1px;
    }

    /* เส้นแบ่งสีทองบางๆ */
    .gold-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #D4AF37, transparent);
        margin: 20px 0;
    }

    /* แต่งสไตล์กล่อง Expander และกล่องอัปโหลดไฟล์ */
    .stExpander {
        border: 1px solid #2D323E !important;
        border-radius: 12px !important;
        background-color: #181B20 !important;
        margin-bottom: 20px !important;
    }

    [data-testid="stFileUploader"] {
        border: 1px dashed #D4AF37 !important;
        border-radius: 12px !important;
        padding: 10px !important;
        background-color: #181B20 !important;
    }

    /* กล่องแสดงผลลัพธ์ */
    .result-box {
        background-color: #1A1D24;
        border-left: 3px solid #D4AF37;
        padding: 16px;
        border-radius: 8px;
        margin-top: 15px;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# แสดงหัวแบรนด์ AppCentralWeb
st.markdown("""
<div class="brand-header">
    <div class="brand-title">AppCentralWeb</div>
    <div class="brand-subtitle">AUTOMATED SLIP VERIFICATION SYSTEM</div>
</div>
<div class="gold-divider"></div>
""", unsafe_allow_html=True)

BRANCH_ID = "SLIPOK0BYYZJR"

# ระบบดึง API Key (ถ้าใส่ไว้ใน Secrets จะข้ามส่วนนี้ไป)
if "SLIPOK_SECRET_KEY" in st.secrets:
    SLIPOK_API_KEY = st.secrets["SLIPOK_SECRET_KEY"]
else:
    with st.expander("🔑 ตั้งค่า API Key"):
        SLIPOK_API_KEY = st.text_input("กรอก Secret Key (SlipOK):", type="password")

# ส่วนอัปโหลดสลิป
st.subheader("🧾 ตรวจสอบสลิปโอนเงิน")
uploaded_file = st.file_uploader("อัปโหลดภาพสลิป (PNG, JPG)", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="สลิปที่ต้องการตรวจสอบ", width=250)
    
    if st.button("✨ ตรวจสอบรายการนี้", use_container_width=True):
        if not SLIPOK_API_KEY:
            st.error("⚠️ กรุณาตั้งค่า Secret Key ก่อนใช้งาน")
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
                        
                        st.success("✅ ตรวจสอบสำเร็จ: สลิปนี้ถูกต้องและผ่านการโอนจริง")
                        
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
