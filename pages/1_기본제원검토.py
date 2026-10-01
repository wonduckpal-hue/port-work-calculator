import streamlit as st
import pandas as pd

st.set_page_config(page_title="항만시설 기본제원 검토", page_icon="🚢", layout="wide")

st.title("🚢 항만시설 기본제원 자동 검토 프로그램")
st.write("설계대상선박 제원과 자연조건을 입력하면 KDS(항만 및 어항설계기준)에 따른 기본제원을 산출합니다.")

# 1. 입력부 (사이드바 또는 본문)
st.subheader("1. 설계 조건 입력")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**🚢 설계대상선박 제원**")
    ship_type = st.selectbox("선박 종류", ["일반화물선", "컨테이너선", "WTIV (해상풍력설치선)"])
    dwt = st.number_input("DWT (재화중량톤수)", value=10000, step=1000)
    loa = st.number_input("Loa (전장, m)", value=120.0, step=1.0)
    breadth = st.number_input("B (형폭, m)", value=20.0, step=0.1)
    draft = st.number_input("Draft (만재흘수, m)", value=8.5, step=0.1)

with col2:
    st.markdown("**🌊 자연조건 (조위 및 파랑)**")
    hwl = st.number_input("H.W.L (최고고조위, (+)m)", value=2.5, step=0.1)
    lwl = st.number_input("L.W.L (최저저조위, (+)m)", value=0.0, step=0.1)
    wave_h = st.number_input("설계파고 (m)", value=1.5, step=0.1)

# 2. KDS 기준 계산 로직
if st.button("🚀 기본제원 검토 결과 산출"):
    with st.spinner('KDS 설계기준을 적용하여 제원을 산출 중입니다...'):
        
        # [수역 시설]
        # 1. 항로 수심 (여유수심 통상 10% 적용)
        channel_depth = round(draft * 1.1, 1)
        
        # 2. 선회장 (자력 선회 기준 2.0L 적용)
        turning_basin = round(loa * 2.0, 1)
        
        # [계류 시설 (안벽)]
        # 3. 안벽 수심 (접안 시 선체 동요 및 여유수심 고려)
        berth_depth = round(draft + max(wave_h * 0.5, 0.5), 1)
        
        # 4. 안벽 연장 (Loa + 여유길이, 일반화물선 기준)
        clearance = 15.0 if dwt < 10000 else 20.0
        berth_length = round(loa + clearance, 1)
        
        # 5. 마루높이 (Crown Elevation) - H.W.L + 여유고(1.0~1.5m)
        crown_elev = round(hwl + 1.0, 1)

        # 3. 결과 출력
        st.subheader("2. 항만시설 기본제원 검토 결과")
        
        # 결과를 깔끔한 표(DataFrame)로 정리
        result_data = [
            {"구분": "항로 수심", "산출 공식", "흘수(d) + 여유수심(10%)", "검토 제원": f"DL(-) {channel_depth} m"},
            {"구분": "선회장 직경", "산출 공식", "2.0 × Loa (자력선회)", "검토 제원": f"Ø {turning_basin} m"},
            {"구분": "안벽 소요수심", "산출 공식", "흘수(d) + 파랑여유고", "검토 제원": f"DL(-) {berth_depth} m"},
            {"구분": "안벽 연장 (1선석)", "산출 공식", "Loa + 여유길이(차내간격)", "검토 제원": f"{berth_length} m"},
            {"구분": "안벽 마루높이", "산출 공식", "H.W.L + 여유고", "검토 제원": f"DL(+) {crown_elev} m"}
        ]
        
        df_result = pd.DataFrame(result_data)
        st.table(df_result)
        
        st.success("✅ 설계기준 검토가 완료되었습니다. (상기 공식은 약식 표본이며, 실제 설계 시 대상선박 통계 데이터를 연동할 수 있습니다.)")
