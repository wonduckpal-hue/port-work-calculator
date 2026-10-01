import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="항만 구조물 및 단면 제원 검토", page_icon="📐", layout="wide")

st.title("📐 항만 구조물 단면 및 안정성 기본제원 검토")
st.write("파고, 주기, 설계수심, 해저경사 조건을 입력하면 KDS 기준에 따른 단면 검토 지표를 산출합니다.")

# 1. 입력부 (외력 및 지형 조건)
st.subheader("1. 설계 외력 및 지형 조건 입력")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**🌊 외력 조건**")
    wave_height = st.number_input("설계파고 ($H_{1/3}$, m)", value=3.5, step=0.1)
    wave_period = st.number_input("파주기 ($T$, sec)", value=10.0, step=0.5)

with col2:
    st.markdown("**🗺️️ 지형 및 수심 조건**")
    water_depth = st.number_input("설계수심 ($h$, m)", value=15.0, step=0.5)
    seabed_slope = st.selectbox("해저경사 ($1:n$", [30, 50, 100], format_func=lambda x: f"1 : {x}")

# 2. 계산 로직 (KDS 항만 및 어항설계기준 기반 산식)
if st.button("🚀 단면 검토 제원 산출"):
    with st.spinner('외력 조건 및 경사 환산 계산 중...'):
        
        # 1. 천해파 파장 추정 (근사식: L0 = 1.56 * T^2)
        deep_wave_len = 1.56 * (wave_period ** 2)
        
        # 2. 쇄파 한계 파고 (Goda 공식 등 간이 검토)
        # 쇄파지수방식 기준 환산
        breaking_wave = round(0.12 * deep_wave_len * (1.0 - np.exp(-1.5 * (water_depth / deep_wave_len))), 2)
        
        # 3. TTP(테트라포드) 소요 중량 산정 (Hudson 공식 간이 적용)
        # W = (r_r * H^3) / (Kd * (S_r - 1)^3 * cot(theta))
        # 콘크리트 단위중량 r_r = 2.3 tf/m^3, 해수 단위중량 = 1.03 tf/m^3, Kd(무근피복재 경사안벽) 대략 8~16
        cot_theta = seabed_slope  # 해저경사 역수
        kd_val = 8.0  # 일반적 피복재 계수
        sr = 2.3 / 1.03
        
        # 단위: ton (1개당 소요중량)
        ttp_weight = round((2.3 * (wave_height ** 3)) / (kd_val * ((sr - 1) ** 3) * cot_theta), 1)
        
        # 4. 구조물 근고석/사석 소요 중량 연동 검토 등
        
        # 3. 결과 출력
        st.subheader("2. 기본제원 검토 및 안정성 지표 산출 결과")
        
        result_data = [
            {"구분": "입사파 파장 ($L_0$)", "산출 기준": "심해파장 ($1.56 \\times T^2$)", "검토 값": f"{round(deep_wave_len, 1)} m"},
            {"구분": "쇄파 한계파고 ($H_b$)", "산출 기준": "수심 및 파주기 연동 쇄파검토", "검토 값": f"{breaking_wave} m"},
            {"구분": "해저경사 반영비 ($\\cot\\theta$)", "산출 기준": f"입력 경사 1 : {seabed_slope}", "검토 값": f"1 : {seabed_slope} (cot θ = {cot_theta})"},
            {"구분": "피복재(TTP) 1개당 소요중량", "산출 기준": "Hudson 공식 적용 (추정치)", "검토 값": f"약 {ttp_weight} ton/개"},
            {"구분": "외력 대비 안정성 검토", "산출 기준": "설계파고 vs 쇄파한계 비교", "검토 값": "안정 (파고 < 쇄파한계)" if wave_height < breaking_wave else "주의 (쇄파 조건 근접)"}
        ]
        
        df_result = pd.DataFrame(result_data)
        st.table(df_result)
        
        st.success("✅ 입력하신 외력 및 지형 조건에 따른 단면 제원 검토가 완료되었습니다!")
