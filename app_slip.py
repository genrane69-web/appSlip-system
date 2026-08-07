import streamlit as st

# [ส่วนที่ 1] ตั้งค่าหน้าตาเบราว์เซอร์
st.set_page_config(
    page_title="App Central Web | Premium Service",
    page_icon="👑",
    layout="centered",
)

# [ส่วนที่ 2] ตกแต่ง CSS สไตล์ Luxury Gold & Dark Elegance
st.markdown(
    """
    <style>
    /* พื้นหลังโดยรวมปรับเป็นโทนดำมืดสนิท */
    .stApp {
        background-color: #0b0c10;
        color: #e0e0e0;
    }
    
    /* การ์ดหลักทรงหรูหรา โค้งมน มีเส้นขอบทอง และเงาสะท้อน */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(145deg, #121317, #1a1c23);
        border: 1px solid #d4af37 !important;
        border-radius: 16px !important;
        padding: 25px !important;
        box-shadow: 0px 8px 25px rgba(212, 175, 55, 0.15);
    }
    
    /* ตัวหนังสือหัวข้อสีทองไล่ระดับ (Gold Gradient Text) */
    .gold-header {
        font-size: 32px;
        font-weight: 700;
        text-align: center;
        background: linear-gradient(45deg, #bf953f, #fcf6ba, #b38728, #fbf5b7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
        letter-spacing: 1px;
    }
    
    /* คำอธิบายสับหัวข้อสีทองอ่อน */
    .gold-sub {
        text-align: center;
        color: #d4af37;
        font-size: 13px;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 25px;
    }
    
    /* ตกแต่งปุ่มกดสีทองหรูหรา มีแสงประกายเวลาชี้ (Hover) */
    div.stButton > button {
        background: linear-gradient(135deg, #d4af37 0%, #aa771c 100%) !important;
        color: #000000 !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        font-size: 16px !important;
        box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(252, 246, 186, 0.5) !important;
        background: linear-gradient(135deg, #fcf6ba 0%, #d4af37 100%) !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# [ส่วนที่ 3] ฟังก์ชันสมองหลังร้าน
def check_quota(count):
    return count > 0


# [ส่วนที่ 4] หน้าตาเว็บ (UI Elements)

# หัวข้อสไตล์ Gold Gradient
st.markdown(
    "<div class='gold-header'>APPCENTRALWEB</div>", unsafe_allow_html=True
)
st.markdown(
    "<div class='gold-sub'>Automated Slip Verification Service</div>",
    unsafe_allow_html=True,
)

# การ์ดหลักล้อมกรอบ
with st.container(border=True):
    st.markdown(
        "<h3 style='color: #ffffff; text-align: center;'>👑 ระบบจัดการสิทธิ์พรีเมียม</h3>",
        unsafe_allow_html=True,
    )
    st.write("")

    # ช่องกรอกโควต้า
    user_quota = st.number_input(
        "โควตาสแกนสลิปคงเหลือ (ครั้ง/เดือน):",
        value=500,
        min_value=0,
        step=50,
    )

    # แสดงตัวเลข Dashboard แบบการ์ดสรุป
    st.metric(label="STATUS QUOTA", value=f"{user_quota:,} CR")

    st.write("")

    # จัดวางปุ่มให้อยู่ตรงกลาง
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        submit = st.button("✨ ตรวจสอบสิทธิ์ใช้งาน", use_container_width=True)

# [ส่วนที่ 5] การแสดงผลลัพธ์
if submit:
    if check_quota(user_quota):
        st.success(
            f"🥇 **ACCESS GRANTED:** ระบบพร้อมใช้งาน โควต้าคงเหลือ {user_quota:,} ครั้ง"
        )
        st.balloons()
    else:
        st.error(
            "🛑 **ACCESS DENIED:** โควต้าของคุณหมดแล้ว กรุณาติดต่อผู้ดูแลระบบ"
        )
