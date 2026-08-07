import streamlit as st  # [ส่วนที่ 1] ดึงเครื่องมือสร้างหน้าเว็บเข้ามา


# [ส่วนที่ 2] สมองหลังร้าน: ฟังก์ชันเช็คโควต้า
def check_quota(count):
    if count > 0:
        return True
    return False


# [ส่วนที่ 3] หน้าตาเว็บ: แสดงหัวข้อ และ ช่องให้ใส่ตัวเลข
st.title("ระบบเช็คโควต้าสแกนสลิป")
user_quota = st.number_input("กรอกจำนวนโควต้าคงเหลือของคุณ:", value=500)

# [ส่วนที่ 4] ปุ่มกดและการทำงาน
if st.button("🚀 ตรวจสอบสิทธิ์"):
    has_quota = check_quota(user_quota)  # ส่งตัวเลขไปให้ส่วนสมองเช็ค

    if has_quota == True:
        st.success("ระบบพร้อมใช้งาน! คุณเหลือโควต้าสแกนสลิป")
    else:
        st.error("โควต้าของคุณหมดแล้ว กรุณาเติมโควต้า")
