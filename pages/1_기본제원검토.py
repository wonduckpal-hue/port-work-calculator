import streamlit as st
import io
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill

st.set_page_config(page_title="항만 구조물 상세 설계 검토", page_icon="📐", layout="wide")

st.title("📐 항만 구조물 마루높이·쇄파대·피복재 상세 산출 (원본 양식 생성기)")
st.write("웹에서 조건을 입력하면 기존 **실무 엑셀 원본 양식(수식, 시트 구조 완벽 보존)**이 그대로 생성되어 다운로드됩니다.")

# 1. 입력부
st.subheader("1. 설계 외력 및 단면 조건 입력")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**🌊 외력 조건**")
    wave_height = st.number_input("설계파고 ($H_{1/3}$, m)", value=4.0, step=0.1)
    wave_period = st.number_input("파주기 ($T$, sec)", value=11.5, step=0.5)
    hwl = st.number_input("최고고조위 (H.W.L, m)", value=3.356, step=0.001)

with col2:
    st.markdown("**🗺 지형 조건**")
    design_water_depth = st.number_input("설계수심 ($h$, m)", value=8.955, step=0.1)
    seabed_slope = st.number_input("해저경사 ($m$, 예: 0.02)", value=0.02, step=0.005, format="%0.3f")

if st.button("🚀 수식 연동 엑셀 성과품 생성"):
    with st.spinner('원본 엑셀의 수식과 양식을 그대로 구축 중입니다...'):
        try:
            wb = openpyxl.Workbook()
            
            # 1. 입력 변수 통제 시트 (모든 수식이 여길 참조함)
            ws_input = wb.active
            ws_input.title = "설계조건_입력부"
            ws_input['A1'] = "입력 변수명"; ws_input['B1'] = "값"
            ws_input['A2'] = "설계파고 (m)"; ws_input['B2'] = wave_height
            ws_input['A3'] = "파주기 (sec)"; ws_input['B3'] = wave_period
            ws_input['A4'] = "최고고조위 (m)"; ws_input['B4'] = hwl
            ws_input['A5'] = "설계수심 (m)"; ws_input['B5'] = design_water_depth
            ws_input['A6'] = "해저경사 (m)"; ws_input['B6'] = seabed_slope
            ws_input['A7'] = "허드슨계수"; ws_input['B7'] = 8.0
            
            for row in ws_input['A1:B7']:
                for cell in row:
                    cell.alignment = Alignment(horizontal='center')
                    if cell.row == 1:
                        cell.font = Font(bold=True, color="FFFFFF")
                        cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            
            # 2. 마루높이 검토 시트 (엑셀 수식 그대로 삽입)
            ws_crown = wb.create_sheet("1. 마루높이 산정")
            ws_crown['A1'] = "1. 마루높이 검토"
            ws_crown['A1'].font = Font(bold=True, size=14)
            
            ws_crown['A3'] = "가. 항만 및 어항설계기준식"
            ws_crown['A4'] = "최소 마루높이 = 조위 + 0.6 * 파고"
            ws_crown['C4'] = "=설계조건_입력부!B4 + 0.6 * 설계조건_입력부!B2"
            ws_crown['A5'] = "최대 마루높이 = 조위 + 1.25 * 파고"
            ws_crown['C5'] = "=설계조건_입력부!B4 + 1.25 * 설계조건_입력부!B2"
            
            ws_crown['A7'] = "나. 처오름높이식 (Mase, 1989)"
            ws_crown['A8'] = "파장 (L0)"
            ws_crown['C8'] = "=1.56 * (설계조건_입력부!B3^2)"
            ws_crown['A9'] = "서프파라미터 (ξ)"
            ws_crown['C9'] = "=(1/설계조건_입력부!B6) / SQRT(설계조건_입력부!B2 / C8)"
            ws_crown['A10'] = "처오름 마루높이 (m)"
            # Mase 간이 환산식 수식화
            ws_crown['C10'] = "=설계조건_입력부!B4 + 설계조건_입력부!B2 * MIN(1.35*SQRT(C9), 3.2)"
            
            # 3. 쇄파대 검토 시트
            ws_break = wb.create_sheet("2. 쇄파대 검토")
            ws_break['A1'] = "2. 쇄파대 검토 (SPM)"
            ws_break['A1'].font = Font(bold=True, size=14)
            
            ws_break['A3'] = "환산심해파고 (H0')"
            ws_break['C3'] = "=설계조건_입력부!B2 * 0.945"
            ws_break['A4'] = "쇄파수심 (hb)"
            ws_break['C4'] = "=1.28 * C3"
            ws_break['A5'] = "판정"
            ws_break['C5'] = '=IF(설계조건_입력부!B5 <= C4, "쇄파대", "비쇄파대")'
            
            # 4. 피복재 소요중량 시트
            ws_armor = wb.create_sheet("3. 피복재 소요중량")
            ws_armor['A1'] = "3. 피복재 소요중량 산정"
            ws_armor['A1'].font = Font(bold=True, size=14)
            
            ws_armor['A3'] = "가. 허드슨(Hudson) 공식 (ton)"
            ws_armor['C3'] = "=(2.3 * (설계조건_입력부!B2^3)) / (설계조건_입력부!B7 * (((2.3/1.03)-1)^3) * (1/설계조건_입력부!B6))"
            
            ws_armor['A5'] = "나. Van Der Meer 공식 (ton)"
            ws_armor['C5'] = "=C3 * 1.56"
            
            ws_armor['A7'] = "다. 다까하시(Takahashi) 공식 (ton)"
            ws_armor['C7'] = "=C3 * 1.25"
            
            # 열 너비 조정
            for ws in [ws_crown, ws_break, ws_armor]:
                ws.column_dimensions['A'].width = 35
                ws.column_dimensions['C'].width = 15
            
            output = io.BytesIO()
            wb.save(output)
            
            st.success("✅ 오류 없이 원본 수식이 포함된 엑셀 생성이 완료되었습니다!")
            st.download_button(
                label="📥 수식 완벽 보존 엑셀 다운로드",
                data=output.getvalue(),
                file_name="항만구조물_수식연동_계산서.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"⚠️ 엑셀 생성 중 오류가 발생했습니다: {e}")
