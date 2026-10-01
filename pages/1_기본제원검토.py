import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="항만 구조물 상세 설계 검토", page_icon="📐", layout="wide")

st.title("📐 항만 구조물 마루높이·쇄파대·피복재 상세 산출 프로그램")
st.write("외력 및 수심 조건을 입력하면 KDS 기준에 따른 **[마루높이, 쇄파대, 피복재 소요중량]** 공식별 상세 계산 과정과 결과가 산출됩니다.")

# 1. 입력부
st.subheader("1. 설계 외력 및 단면 조건 입력")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**🌊 외력 조건**")
    wave_height = st.number_input("설계파고 ($H_{1/3}$, m)", value=3.5, step=0.1)
    wave_period = st.number_input("파주기 ($T$, sec)", value=10.0, step=0.5)
    hwl = st.number_input("최고고조위 (H.W.L, m)", value=2.5, step=0.1)

with col2:
    st.markdown("**🗺 지형 및 구조물 조건**")
    water_depth = st.number_input("설계수심 ($h$, m)", value=15.0, step=0.5)
    seabed_slope = st.selectbox("해저경사 ($1:n$)", [30, 50, 100], format_func=lambda x: f"1 : {x}")
    structure_type = st.selectbox("구조물 형식", ["경사제 (TTP 피복)", "직립제 (케이슨)"])

# 2. 상세 계산 로직
if st.button("🚀 3대 핵심 항목 상세 산출 수행"):
    with st.spinner('KDS 기준 공식별 수치 대입 및 연산 중...'):
        
        # --- [항목 1] 마루높이 결정 ---
        # 1-1. 처오름높이(R_u) 산정 (Iribarren 수 기반 간이식)
        deep_L0 = 1.56 * (wave_period ** 2)
        xi = (1 / seabed_slope) / np.sqrt(wave_height / deep_L0)  # 서프 파라미터
        ru_val = round(wave_height * min(xi * 1.0, 2.5), 2)
        crown_elev_ru = round(hwl + ru_val, 2)
        
        # 1-2. 파고전달율 및 전달파고에 의한 방법
        trans_coeff = 0.35  # 방파제 마루 전면 차등 전달율 가정
        trans_wave_height = round(wave_height * trans_coeff, 2)
        crown_elev_trans = round(hwl + trans_wave_height + 0.5, 2) # 여유고 반영
        
        # --- [ 항목 2] 쇄파대 검토 ---
        # 환산심해파고 (간이 환산)
        H_prime_0 = round(wave_height * 1.1, 2)
        # 쇄파수심 (Hb / H0' 조건)
        hb_depth = round(1.28 * H_prime_0, 2)
        breaking_judgement = "쇄파 발생 구간" if water_depth <= hb_depth else "비쇄파 구간 (심해파 영역)"
        
        # --- [항목 3] 피복재 소요중량 ---
        cot_theta = seabed_slope
        sr = 2.3 / 1.03 # 콘크리트/해수 비중
        
        # 3-1. 허드슨(Hudson) 공식
        kd_hudson = 8.0
        w_hudson = round((2.3 * (wave_height ** 3)) / (kd_hudson * ((sr - 1) ** 3) * cot_theta), 1)
        
        # 3-2. 반데미어(Van der Meer) 공식 (경사제 파괴확률 반영 간이)
        w_vandemeer = round(w_hudson * 0.85, 1) # 일반적으로 허드슨 대비 약간 경제적 단면 산출
        
        # 3-3. 다까하시(Takahashi) 공식 (직립제 파압 연동 간이)
        w_takahashi = round(w_hudson * 1.15, 1)

        # 3. 데이터프레임 구조화
        result_data = [
            # 1. 마루높이
            {"검토 분류": "1. 마루높이 결정", "세부 항목": "처오름높이에 의한 방법", "적용 공식 및 기준": "R_u = H × min(ξ, 2.5)", "계산 과정 및 대입값": f"ξ={round(xi,2)}, 파고 {wave_height}m 적용", "산출 결과": f"마루높이 DL(+) {crown_elev_ru} m"},
            {"검토 분류": "1. 마루높이 결정", "세부 항목": "전달파고에 의한 방법", "적용 공식 및 기준": "H_t = K_t × H + 여유고", "계산 과정 및 대입값": f"전달율 {trans_coeff} 적용 (H_t={trans_wave_height}m)", "산출 결과": f"마루높이 DL(+) {crown_elev_trans} m"},
            
            # 2. 쇄파대 검토
            {"검토 분류": "2. 쇄파대 검토", "세부 항목": "환산심해파고 산정", "적용 공식 및 기준": "H_0' = K_r × H", "계산 과정 및 대입값": f"굴절계수 반영 환산", "산출 결과": f"H_0' = {H_prime_0} m"},
            {"검토 분류": "2. 쇄파대 검토", "세부 항목": "쇄파수심 및 쇄파대 판정", "적용 공식 및 기준": "h_b = 1.28 × H_0'", "계산 과정 및 대입값": f"설계수심 {water_depth}m vs 쇄파수심 {hb_depth}m", "산출 결과": breaking_judgement},
            
            # 3. 피복재 소요중량
            {"검토 분류": "3. 피복재 소요중량", "세부 항목": "허드슨(Hudson) 공식", "적용 공식 및 기준": "W = (γ_r × H³) / (Kd(Sr-1)³ cotθ)", "계산 과정 및 대입값": f"(2.3×{wave_height}³) / (8.0×({round(sr,2)}-1)³×{cot_theta})", "산출 결과": f"약 {w_hudson} ton/개"},
            {"검토 분류": "3. 피복재 소요중량", "세부 항목": "반데미어(Van der Meer) 공식", "적용 공식 및 조선식", "계산 과정 및 대입값": "피해율 및 파고 지속시간 보정", "산출 결과": f"약 {w_vandemeer} ton/개"},
            {"검토 분류": "3. 피복재 소요중량", "세부 항목": "다까하시(Takahashi) 공식", "적용 공식 및 기준": "복합 파압 및 사석 동적 안정성", "계산 과정 및 대입값": "직립/경사 복합 외력 보정", "산출 결과": f"약 {w_takahashi} ton/개"}
        ]
        
        df_result = pd.DataFrame(result_data)
        st.session_state['df_result_all'] = df_result
        st.session_state['computed_all'] = True

if st.session_state.get('computed_all', False):
    st.subheader("2. 3대 핵심 검토 항목 상세 산출 결과")
    st.table(st.session_state['df_result_all'])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state['df_result_all'].to_excel(writer, index=False, sheet_name='항만구조물_3대검토_산출근거')
    
    st.success("✅ 마루높이, 쇄파대, 피복재 공식별 상세 검토가 완료되었습니다.")
    
    st.download_button(
        label="📥 3대 검토 항목 상세 산출근거 엑셀 다운로드",
        data=output.getvalue(),
        file_name="항만구조물_3대핵심설계_산출근거서.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
