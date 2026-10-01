import streamlit as st
import pandas as pd
import io
import pdfplumber

def process_uploaded_file(uploaded_file):
    file_name = uploaded_file.name
    if file_name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif file_name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(uploaded_file)
    elif file_name.endswith('.pdf'):
        extracted_data = []
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    extracted_data.extend(table)
        if extracted_data:
            df = pd.DataFrame(extracted_data[1:], columns=extracted_data[0]) 
        else:
            st.error("PDF에서 표 데이터를 찾을 수 없습니다.")
            return None
    else:
        st.error("지원하지 않는 파일 형식입니다.")
        return None
    return df

st.title("🏗️ 항만공사 작업일수 자동 산정 프로그램")
st.write("해양 기상연보 데이터(Excel, CSV, PDF)를 업로드하면 공종별 작업일수를 산정합니다.")

uploaded_file = st.file_uploader("기상 데이터 파일을 첨부하세요", type=['csv', 'xlsx', 'pdf'])

if uploaded_file is not None:
    st.success(f"'{uploaded_file.name}' 파일이 성공적으로 업로드되었습니다.")
    df = process_uploaded_file(uploaded_file)
    
    if df is not None:
        st.write("데이터 미리보기:")
        st.dataframe(df.head())
        
        if st.button("작업일수 산정 엑셀 추출하기"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='산정결과')
            
            st.download_button(
                label="📥 엑셀 결과물 다운로드",
                data=output.getvalue(),
                file_name="작업일수_산정결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )