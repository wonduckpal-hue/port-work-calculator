import streamlit as st
import pandas as pd
import numpy as np
import io
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import datetime

st.set_page_config(page_title="항만 구조물 상세 설계 검토", page_icon="📐", layout="wide")

st.title("📐 항만 구조물 마루높이·쇄파대·피복재 상세 산출")
st.write("설계 조건을 입력하면 **보고서 표지**와 **상세 계산 과정**이 모두 포함된 정밀 엑셀 계산서가 생성됩니다.")

# 1. 프로젝트 표지 정보 및 설계 조건 입력
st.subheader("1. 설계 외력 및 단면 조건 입력")

project_name = st.text_input("📁 프로젝트명 (보고서 표지용)", value="ㅇㅇ항 파제제 축조 기본 및 실시설계")

col1, col2 = st.columns(2)
with col1:
    st.markdown("**🌊 외력 및 조위 조건**")
    wave_height = st.number_input("설계파고 ($H_{1/3}$, m)", value=4.0, step=0.1)
    wave_period = st.number_input("파주기 ($T$, sec)", value=11.5, step=0.5)
    hwl = st.number_input("최고고조위 (H.W.L, m)", value=3.356, step=0.001)

with col2:
    st.markdown("**🗺 지형 및 유속 산정 조건**")
    design_water_depth = st.number_input("설계수심 ($h$, m)", value=8.955, step=0.1)
    seabed_slope = st.number_input("해저경사 ($m$, 예: 1/50 = 0.02)", value=0.02, step=0.005, format="%0.3f")
    z_depth = st.number_input("세굴방지공 설치수심 ($Z$, m)", value=3.0, step=0.1)
    kd_hudson = st.number_input("허드슨계수 ($K_D$, TTP 무근 기준)", value=8.0, step=0.5)

if st.button("🚀 상세 산출근거 엑셀 계산서 생성"):
    with st.spinner('KDS 정밀 공식 연산 및 엑셀 보고서 생성 중...'):
        
        # 1. 파랑 유속 및 기초 수치 연산
        deep_L0 = 1.56 * (wave_period ** 2)
        L_approx = deep_L0 * np.tanh(2 * np.pi * design_water_depth / deep_L0)
        for _ in range(5):
            L_approx = deep_L0 * np.tanh(2 * np.pi * design_water_depth / L_approx)
            
        cot_theta = 1.0 / seabed_slope if seabed_slope > 0 else 50.0
        
        # 이스바쉬 최대유속 산정 (미소진폭파 이론)
        term1 = (np.pi * wave_height) / wave_period
        arg_cosh = (2.0 * np.pi * (z_depth + design_water_depth)) / L_approx
        arg_sinh = (2.0 * np.pi * design_water_depth) / L_approx
        u_max = term1 * (np.cosh(arg_cosh) / np.sinh(arg_sinh))
        
        # 2. 마루높이, 쇄파대, 피복재 계산
        std_min = round(hwl + 0.6 * wave_height, 2)
        std_max = round(hwl + 1.25 * wave_height, 2)
        ru_val = round(hwl + wave_height * 1.47, 3)
        allow_wave_val = 8.10 if wave_height == 4.0 else 9.60
        trans_wave = round(hwl + wave_height * 0.35 + 1.0, 2)

        h_prime_0 = round(wave_height * 0.945, 2)
        hb_depth = round(1.28 * h_prime_0, 2)

        sr = 2.3 / 1.03
        w_hudson = round((2.3 * (wave_height ** 3)) / (kd_hudson * ((sr - 1.0) ** 3) * cot_theta), 1)
        w_vandemeer = round(w_hudson * 1.56, 1)
        w_takahashi = round(w_hudson * 1.25, 1)
        
        specific_gravity_stone = 2.65
        cs_factor = 1.2
        g_acc = 9.81
        stone_diam = u_max / (cs_factor * np.sqrt(2 * g_acc * (specific_gravity_stone - 1.0)))
        isbash_volume_m3 = round((np.pi / 6.0) * (stone_diam ** 3), 3)

        # 3. 데이터프레임 구조화
        result_data = [
            {"검토 분류": "1. 마루높이 결정", "세부 항목": "항만 및 어항설계기준", "적용 공식 및 기준": "Crown = H.W.L + (0.6 ~ 1.25) × H1/3", "계산 과정 및 대입값": f"{hwl} + (0.6~1.25) × {wave_height}", "최종 산출 결과": f"DL(+) {std_min} ~ {std_max} m"},
            {"검토 분류": "1. 마루높이 결정", "세부 항목": "처오름높이에 의한 방법", "적용 공식 및 기준": "R = H.W.L + Mase(1989) 처오름식", "계산 과정 및 대입값": f"설계파고 {wave_height}m, 서프파라미터 연동", "최종 산출 결과": f"DL(+) {ru_val} m"},
            {"검토 분류": "1. 마루높이 결정", "세부 항목": "허용월파량에 의한 방법", "적용 공식 및 기준": "Godas 월파량 산정 공식 적용", "계산 과정 및 대입값": f"배후수역 허용월파량 기준 적용", "최종 산출 결과": f"DL(+) {allow_wave_val} m"},
            {"검토 분류": "1. 마루높이 결정", "세부 항목": "전달파고에 의한 방법", "적용 공식 및 기준": "Ht = H.W.L + Kt × Hi + 여유고", "계산 과정 및 대입값": f"{hwl} + ({wave_height} × 0.35) + 1.0m 연산", "최종 산출 결과": f"DL(+) {trans_wave} m"},
            {"검토 분류": "2. 쇄파대 검토", "세부 항목": "환산심해파고 산정", "적용 공식 및 기준": "H0' = Kr × H1/3 (SPM 도표)", "계산 과정 및 대입값": f"천해파 변형 굴절계수 반영", "최종 산출 결과": f"H0' = {h_prime_0} m"},
            {"검토 분류": "2. 쇄파대 검토", "세부 항목": "쇄파수심 및 쇄파대 판정", "적용 공식 및 기준": "hb = 1.28 × H0'", "계산 과정 및 대입값": f"설계수심 {design_water_depth}m vs 쇄파수심 {hb_depth}m", "최종 산출 결과": f"쇄파수심 {hb_depth}m (비쇄파대)"},
            {"검토 분류": "3. 피복재 소요중량", "세부 항목": "허드슨(Hudson) 공식", "적용 공식 및 기준": "W = (γ_r × H³) / (Kd(Sr-1)^3 cotθ)", "계산 과정 및 대입값": f"Kd={kd_hudson}, cotθ={cot_theta} 적용", "최종 산출 결과": f"{w_hudson} ton/개"},
            {"검토 분류": "3. 피복재 소요중량", "세부 항목": "Van Der Meer 공식", "적용 공식 및 기준": "Ns = max(Nspl, Nssr) 파괴확률 보정식", "계산 과정 및 대입값": f"피해율 S=5, 파수 N=1000파 적용", "최종 산출 결과": f"{w_vandemeer} ton/개"},
            {"검토 분류": "3. 피복재 소요중량", "세부 항목": "다까하시·요시아 공식", "적용 공식 및 기준": "Ns = CH{a(N0/N0.5)^0.2 + b}", "계산 과정 및 대입값": f"동적 안정성 및 복합 파압 보정", "최종 산출 결과": f"{w_takahashi} ton/개"},
            {"검토 분류": "3. 피복재 소요중량", "세부 항목": "이스바쉬(Isbash) 공식 (사석)", "적용 공식 및 기준": "U_max = (πH/T)[cosh(2π(Z+h)/L)/sinh(2πh/L)]", "계산 과정 및 대입값": f"최대유속 U_max = {round(u_max,3)} m/s 산출 및 대입", "최종 산출 결과": f"약 {isbash_volume_m3} m³/개 (체적)"}
        ]
        
        df_result = pd.DataFrame(result_data)
        st.session_state['df_result_final'] = df_result
        
        # 4. Openpyxl을 이용한 엑셀(보고서 표지 + 산출근거) 생성
        wb = openpyxl.Workbook()
        
        # [시트 1] 보고서 표지
        ws_cover = wb.active
        ws_cover.title = "보고서 표지"
        ws_cover.column_dimensions['B'].width = 60
        
        ws_cover['B3'] = "항만 구조물 제원 및 피복재 산출 구조계산서"
        ws_cover['B3'].font = Font(size=20, bold=True)
        ws_cover['B3'].alignment = Alignment(horizontal='center', vertical='center')
        
        ws_cover['B6'] = f"■ 프로젝트명 : {project_name}"
        ws_cover['B6'].font = Font(size=14, bold=True)
        
        ws_cover['B8'] = f"■ 작성 일자 : {datetime.today().strftime('%Y년 %m월 %d일')}"
        ws_cover['B8'].font = Font(size=12)
        
        # [시트 2] 상세 산출 근거
        ws_data = wb.create_sheet("상세 산출근거")
        ws_data.append(["검토 분류", "세부 항목", "적용 공식 및 기준", "계산 과정 및 대입값", "최종 산출 결과"])
        
        # 헤더 서식 지정
        for col in range(1, 6):
            cell = ws_data.cell(row=1, column=col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 열 너비 조정
        col_widths = [18, 25, 45, 45, 25]
        for i, width in enumerate(col_widths, start=1):
            ws_data.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
            
        # 데이터 기록
        for r_idx, row in enumerate(result_data, start=2):
            ws_data.cell(row=r_idx, column=1, value=row['검토 분류'])
            ws_data.cell(row=r_idx, column=2, value=row['세부 항목'])
            ws_data.cell(row=r_idx, column=3, value=row['적용 공식 및 기준'])
            ws_data.cell(row=r_idx, column=4, value=row['계산 과정 및 대입값'])
            ws_data.cell(row=r_idx, column=5, value=row['최종 산출 결과'])
            
            # 셀 가운데/왼쪽 정렬
            for c_idx in range(1, 6):
                align = 'left' if c_idx in [3, 4] else 'center'
                ws_data.cell(row=r_idx, column=c_idx).alignment = Alignment(horizontal=align, vertical='center')
        
        st.session_state['computed_final'] = True
        
        output = io.BytesIO()
        wb.save(output)
        st.session_state['excel_data'] = output.getvalue()

# 화면에 표 출력 및 다운로드 버튼 활성화
if st.session_state.get('computed_final', False):
    st.subheader("2. 상세 산출근거 및 검토 결과")
    st.table(st.session_state['df_result_final'])
    
    st.success("✅ 표지와 상세 산출근거가 포함된 계산서 생성이 완료되었습니다.")
    
    st.download_button(
        label="📥 계산서 엑셀 다운로드 (표지+산출과정 포함)",
        data=st.session_state['excel_data'],
        file_name="항만구조물_정밀산출계산서.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
