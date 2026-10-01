import streamlit as st
import io
import os
import openpyxl

st.set_page_config(page_title="항만 구조물 상세 설계 검토", page_icon="📐", layout="wide")

st.title("📐 항만 구조물 마루높이·쇄파대·피복재 상세 산출 (원본 엑셀 연동)")
st.write("웹에서 조건을 입력하면, 깃허브에 업로드된 **원본 엑셀 템플릿(`template.xlsx`)**에 값이 주입되어 기존 수식이 모두 살아있는 상태로 다운로드됩니다.")

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
    seabed_slope = st.number_input("해저경사 ($m$)", value=0.02, step=0.005, format="%0.3f")

if st.button("🚀 원본 수식 연동 엑셀 다운로드"):
    # 깃허브에 업로드된 xlsx 파일명
    template_path = "template.xlsx"
    
    if not os.path.exists(template_path):
        st.error(f"❌ 깃허브에 '{template_path}' 파일이 없습니다. 원본 엑셀을 .xlsx 형식으로 저장하여 업로드해주세요.")
    else:
        with st.spinner('원본 엑셀 템플릿에 데이터를 주입 중입니다...'):
            try:
                # 원본 엑셀 템플릿 손상 없이 그대로 불러오기
                wb = openpyxl.load_workbook(template_path)
                
                # 엑셀 파일 내에 값 통제를 위한 'Streamlit_Input' 시트를 맨 앞에 생성 (있으면 덮어쓰기)
                sheet_name = "Streamlit_Input"
                if sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                else:
                    ws = wb.create_sheet(sheet_name, 0)
                    
                # 웹에서 입력한 값을 엑셀 시트에 주입
                ws['A1'] = "입력 변수명"
                ws['B1'] = "웹 입력값"
                
                ws['A2'] = "설계파고 (m)"
                ws['B2'] = wave_height
                
                ws['A3'] = "파주기 (sec)"
                ws['B3'] = wave_period
                
                ws['A4'] = "최고고조위 (m)"
                ws['B4'] = hwl
                
                ws['A5'] = "설계수심 (m)"
                ws['B5'] = design_water_depth
                
                ws['A6'] = "해저경사"
                ws['B6'] = seabed_slope
                
                # 바이트 변환 및 다운로드 준비
                output = io.BytesIO()
                wb.save(output)
                
                st.success("✅ 원본 엑셀 연동이 완료되었습니다! 아래 버튼을 눌러 다운로드하세요.")
                st.download_button(
                    label="📥 수식 연동 원본 엑셀 다운로드",
                    data=output.getvalue(),
                    file_name="항만구조물_원본연동_계산서.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                st.info("""
                💡 **최초 1회 엑셀 세팅 안내**  
                다운로드하신 엑셀을 열어보시면 **`Streamlit_Input`** 이라는 시트가 생성되어 있습니다.  
                기존 양식(예: 마루높이 검토 시트 등)에서 수작업으로 파고(4.0) 등을 넣으셨던 셀에 `=Streamlit_Input!B2` 처럼 링크를 한 번만 걸어주시고, 그 파일을 다시 `template.xlsx` 이름으로 깃허브에 덮어쓰기 업로드해 주세요!  
                **이후부터는 웹에서 숫자만 바꾸고 다운로드하면 원본 엑셀 전체가 자동으로 쫙 계산되어 나옵니다!**
                """)
                
            except Exception as e:
                st.error(f"⚠️ 엑셀 처리 중 오류가 발생했습니다: {e}")
