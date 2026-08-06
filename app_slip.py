import streamlit as st
import requests

# Set page config
st.set_page_config(page_title="ระบบตรวจสอบสลิปโอนเงิน", page_icon="🧾", layout="centered")

st.title("🧾 ระบบตรวจสอบสลิปโอนเงินอัตโนมัติ")
st.caption("ระบบตรวจสลิปจริง/ปลอม และดึงข้อมูลยอดเงินผ่าน SlipOK API")

# 1. กรอก API Key ของคุณ (แนะนำให้ใช้ st.secrets หรือกรอกผ่าน Input)
SLIPOK_API_KEY = st.text_input("กรอก Secret Key (จาก SlipOK):", type="password")
BRANCH_ID = "SLIPOK0BYYZJR" # ใส่ Branch ID ของคุณไว้ที่นี่

uploaded_file = st.file_uploader("อัปโหลดภาพสลิปโอนเงิน (PNG, JPG)", type=["jpg", "png", "jpeg"])

if uploaded_file is not None and SLIPOK_API_KEY:
    # แสดงรูปสลิปที่อัปโหลด
    st.image(uploaded_file, caption="สลิปที่อัปโหลด", width=300)
    
    if st.button("🔍 ตรวจสอบสลิปนี้"):
        with st.spinner("กำลังตรวจสอบข้อมูลกับธนาคาร..."):
            try:
                # เตรียมส่งไฟล์ภาพไปยัง SlipOK API
                url = f"https://api.slipok.com/api/line/apikey/{BRANCH_ID}"
                headers = {
                    "x-authorization": SLIPOK_API_KEY
                }
                files = {
                    "files": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
                }

                # ยิง API ไปยัง SlipOK
                response = requests.post(url, headers=headers, files=files)
                result = response.json()

                # ตรวจสอบผลลัพธ์
                if response.status_code == 200 and result.get("success"):
                    data = result.get("data", {})
                    
                    st.success("✅ สลิปถูกต้อง! ชำระเงินเรียบร้อย")
                    
                    # แสดงรายละเอียดข้อมูลสลิปที่ดึงได้จากธนาคาร
                    st.markdown("### 📋 ข้อมูลการโอนเงิน")
                    st.write(f"**ผู้โอน:** {data.get('sender', {}).get('displayName', 'N/A')}")
                    st.write(f"**ผู้รับ:** {data.get('receiver', {}).get('displayName', 'N/A')}")
                    st.write(f"**ยอดเงิน:** {data.get('amount', 0):,.2f} บาท")
                    st.write(f"**วันที่/เวลา:** {data.get('transDate')} - {data.get('transTime')}")
                    st.write(f"**เลขที่รายการ:** {data.get('transRef')}")
                    
                else:
                    st.error(f"❌ ไม่สามารถตรวจสอบสลิปได้: {result.get('message', 'สลิปไม่ถูกต้อง หรือถูกใช้ไปแล้ว')}")
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")

elif uploaded_file and not SLIPOK_API_KEY:
    st.warning("⚠️ กรุณากรอก Secret Key ก่อนทำการสแกน")
