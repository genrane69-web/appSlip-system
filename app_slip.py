import streamlit as st

# [ส่วนที่ 1] ตั้งค่าหน้าตาเบราว์เซอร์ (ต้องอยู่บรรทัดแรกๆ เสมอ)
st.set_page_config(
    page_title="ระบบสแกนสลิปอัตโนมัติ",
    page_icon="💳",
    layout="centered",
)


# [ส่วนที่ 2] สมองหลังร้าน: ฟังก์ชันเช็คโควต้า
def check_quota(count):
    return count > 0


# [ส่วนที่ 3] หน้าตาเว็บส่วนหัว (Header)
st.markdown(
    "<h1 style='text-align: center;'>💳 ระบบสแกนสลิปอัตโนมัติ</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: gray;'>บริการตรวจสอบรายการโอนเงินและจัดการโควต้าผู้ใช้งาน</p>",
    unsafe_allow_html=True,
)

st.divider()  # เส้นคั่นหน้าเว็บสวยงาม

# [ส่วนที่ 4] กล่องการ์ดสวยงาม (Container มีกรอบ)
with st.container(border=True):
    st.subheader("📊 ตรวจสอบสิทธิ์และโควต้า")

    # ช่องกรอกข้อมูล
    user_quota = st.number_input(
        "จำนวนโควต้าคงเหลือของคุณ (ครั้ง/เดือน):",
        value=500,
        min_value=0,
        step=50,
    )

    # ป้ายแสดงตัวเลขสรุปสวยงาม (Metric Card)
    st.metric(label="โควต้าปัจจุบัน", value=f"{user_quota:,} ครั้ง")

    st.write("")  # เว้นระยะห่างบรรทัด

    # จัดวางปุ่มให้อยู่ตรงกลาง
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # type="primary" จะทำให้ปุ่มเป็นสีเด่นสวยงาม
        submit = st.button(
            "🚀 ตรวจสอบสิทธิ์", use_container_width=True, type="primary"
        )

# [ส่วนที่ 5] การแสดงผลลัพธ์เมื่อกดปุ่ม
if submit:
    if check_quota(user_quota):
        st.success(
            f"✅ **ระบบพร้อมใช้งาน!** คุณมีโควต้าเหลืออยู่ {user_quota:,} ครั้ง"
        )
        st.balloons()  # เอฟเฟกต์ลูกโป่งลอยฉลองเมื่อสำเร็จ
    else:
        st.error(
            "❌ **ไม่สามารถใช้งานได้!** โควต้าของคุณหมดแล้ว กรุณาติดต่อผู้ดูแลระบบ"
        )
