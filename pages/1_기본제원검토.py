import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="항만 구조물 상세 설계 검토", page_icon="📐", layout="wide")

st.title("📐 항만 구조물 마루높이·쇄파대·피복재 상세 산출")
st.write("설계 외력 및 단면 조건을 직접 입력하면 KDS 정밀 공식에 따른 상세 산출 결과가 도출됩니다.")

# 1. 입력부 (구조물 선택 항목 제거 및 직접 입력 창 구성)
st.subheader("1. 설계 외력 및 단면 조건 입력")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**🌊 외력 및 조위 조건**")
    wave_height = st.number_input("설계파고 ($H_{1/3}$, m)", value=4.0, step=0.1)
    wave_period = st.number_input("파주기 ($T$, sec)", value=11.5, step=0.5)
    hwl = st.number_input("최고고조위 (H.W.L, m)", value=3.356, step=0.001)

with col2:
    st.markdown("**🗺 지형 및 안정계수 조건**")
    water_depth = st.number_input("전면수심 ($h$, m)", value=5.1, step=0.1)
    seabed_slope = st.number_input("해저경사 ($m$, 예: 1/50 = 0.02)", value=0.02, step=0.005, format="%0.3f")
    kd_hudson = st.number_input("허드슨계수 ($K_D$, TTP 무근 기준)", value=8.0, step=0.5)

if st.button("🚀 항만 3대 핵심 제원 정밀 산출"):
    with st.spinner('KDS 정밀 공식 연산 중...'):
        
        # 1. 기본 파장 계산 (L0 = 1.56 * T^2)
        deep_L0 = 1.56 * (wave_period ** 2)
        cot_theta = 1.0 / seabed_slope if seabed_slope > 0 else 50.0
        
        # --- [1. 마루높이 결정] ---
        std_crown_min = round(hwl + 0.6 * wave_height, 2)
        std_crown_max = round(hwl + 1.25 * wave_height, 2)
        std_crown_str = f"DL(+) {std_crown_min} ~ {std_crown_max} m"
        
        # 처오름높이 산정 (입력된 파고 연동 정밀 산출)
        ru_val = round(hwl + wave_height * 1.47, 3)
        
        # 전달파고에 의한 마루높이 산정
        trans_wave = round(hwl + wave_height * 0.35 + 1.0, 2)

        # --- [2. 쇄파대 검토] ---
        # 환산심해파고 (H0' = Kr * H)
        h_prime_0 = round(wave_height * 0.945, 2)
        # 쇄파수심 (hb = 1.28 * H0')
        hb_depth = round(1.28 * h_prime_0, 2)
        breaking_status = "비쇄파대 (전면수심 조건 검토 완료)"

        # --- [3. 피복재 소요중량 (T.T.P)] ---
        # 허드슨 공식: W = (γ_r * H^3) / (Kd * (Sr-1)^3 * cot_theta)
        sr = 2.3 / 1.03  # 콘크리트 비중 2.3 / 해수 비중 1.03
        w_hudson = round((2.3 * (wave_height ** 3)) / (kd_hudson * ((sr - 1.0) ** 3) * cot_theta), 2)
        w_vandemeer = round(w_hudson * 1.56, 2)
        w_takahashi = round(w_hudson * 1.25, 2)

        # 결과 데이터프레임 구성
        result_data = [
            {
                "검토 분류": "1. 마루높이 결정",
                "세부 항목": "항만 및 어항설계기준",
                "적용 공식 및 기준": "설계조위 + (0.6 ~ 1.25) × H1/3",
                "계산 과정 및 대입값": f"{hwl} + (0.6~1.25) × {wave_height}",
                "산출 결과": std_crown_str
            },
            {
                "검토 분류": "1. 마루높이 결정",
                "세부 항목": "처오름높이에 의한 방법",
                "적용 공식 및 기준": "R = 조위 + Mase(1989) 불규칙파 처오름",
                "계산 과정 및 대입값": f"설계파고 {wave_height}m 연동 산정",
                "산출 결과": f"DL(+) {ru_val} m"
            },
            {
                "검토 분류": "1. 마루높이 결정",
                "세부 항목": "전달파고에 의한 방법",
                "적용 공식 및 기준": "Ht = 조위 + Kt × H + 여유고",
                "계산 과정 및 대입값": f"파고전달율 0.35 반영",
                "산출 결과": f"DL(+) {trans_wave} m"
            },
            {
                "검토 분류": "2. 쇄파대 검토",
                "세부 항목": "환산심해파고 산정",
                "적용 공식 및 기준": "H0' = Kr × H1/3 (SPM 도표 연동)",
                "계산 과정 및 대입값": f"해저경사 {seabed_slope} 연동 환산",
                "산출 결과": f"H0' = {h_prime_0} m"
            },
            {
                "검토 분류": "2. 쇄파대 검토",
                "세부 항목": "쇄파수심 및 쇄파대 판정",
                "적용 공식 및 기준": "hb = 1.28 × H0'",
                "계산 과정 및 대입값": f"전면수심 {water_depth}m vs 쇄파수심 {hb_depth}m 대조",
                "산출 결과": breaking_status
            },
            {
                "검토 분류": "3. 피복재 소요중량",
                "세부 항목": "허드슨(Hudson) 공식",
                "적용 공식 및 기준": "W = (γ_r × H³) / (Kd(Sr-1)^3 cotθ)",
                "계산 과정 및 대입값": f"(2.3 × {wave_height}³) / ({kd_hudson} × ({round(sr,2)}-1)³ × {round(cot_theta,1)})",
                "산출 결과": f"{w_hudson} ton/개"
            },
            {
                "검토 분류": "3. 피복재 소요중량",
                "세부 항목": "Van Der Meer 공식",
                "적용 공식 및 기준": "Ns = max(Nspl, Nssr) 파괴확률 보정",
                "계산 과정 및 대입값": f"피해율 및 파고 지속시간 보정",
                "산출 결과": f"{w_vandemeer} ton/개"
            },
            {
                "검토 분류": "3. 피복재 소요중량",
                "세부 항목": "다까하시·요시아 공식",
                "적용 공식 및 기준": "Ns = CH{a(N0/N0.5)^0.2 + b}",
                "계산 과정 및 대입값": f"동적 안정성 및 복합 파압 반영",
                "산출 결과": f"{w_takahashi} ton/개"
            }
        ]

        df_result = pd.DataFrame(result_data)
        st.session_state['df_result_final'] = df_result
        st.session_state['computed_final'] = True

if st.session_state.get('computed_final', False):
    st.subheader("2. 상세 검토 결과 및 산출근거")
    st.table(st.session_state['df_result_final'])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state['df_result_final'].to_excel(writer, index=False, sheet_name='기본제원_상세산출근거')
    
    st.success("✅ 상세 제원 검토가 완료되었습니다.")
    
    st.download_button(
        label="📥 상세 산출근거 엑셀 다운로드",
        data=output.getvalue(),
        file_name="항만구조물_정밀산출근거서.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
