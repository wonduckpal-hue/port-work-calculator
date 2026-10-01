import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗️️")

st.title("🏗️ 항만공사 작업일수 자동 산정 프로그램")
st.write("기상 데이터(엑셀/CSV)를 업로드하면 공종별 작업일수를 자동으로 산정합니다.")

# 1. 파일 업로드 기능
uploaded_file = st.file_uploader("기상 데이터 파일(Excel/CSV)을 첨부하세요", type=['csv', 'xlsx'])

if uploaded_file is not None:
    st.success(f"'{uploaded_file.name}' 파일이 성공적으로 업로드되었습니다.")
    
    # 확장자에 맞춰 데이터 읽기
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.write("👀 원본 데이터 미리보기:")
    st.dataframe(df.head())

    # 2. 추출 버튼을 눌렀을 때 실행될 계산 로직
    if st.button("🚀 작업일수 산정 엑셀 추출하기"):
        with st.spinner('작업일수를 계산하고 있습니다...'):
            try:
                # ---------------------------------------------------------
                # [주의] 아래 컬럼명('파고', '풍속', '강수량' 등)은 
                # 실제 업로드하는 엑셀 파일의 1행(헤더) 이름과 똑같아야 합니다!
                # ---------------------------------------------------------
                
                # 공종별 기준 세팅 (예: DCM, TTP)
                work_conditions = {
                    '해상_DCM타설': {'wave': 1.0, 'wind': 10.0, 'rain': 10.0},
                    '해상_TTP거치': {'wave': 1.5, 'wind': 10.0, 'rain': 10.0}
                }
                
                # 원본 보호를 위해 복사본 사용
                result_df = df.copy()
                summary_data = []

                # 공종별 계산 반복문
                for task_name, limits in work_conditions.items():
                    # 조건 판별 (기상 수치가 기준치보다 크면 True=비작업일)
                    over_wave = result_df['파고'] > limits['wave']
                    over_wind = result_df['풍속'] > limits['wind']
                    over_rain = result_df['강수량'] > limits['rain']
                    
                    # 최종 기상악화 비작업일
                    result_df[f'{task_name}_기상악화'] = over_wave | over_wind | over_rain
                    
                    # 월별(Month) 정보 추출 (날짜 컬럼 이름이 '일시'라고 가정)
                    result_df['일시'] = pd.to_datetime(result_df['일시'])
                    result_df['월'] = result_df['일시'].dt.month
                    
                    # 월별 요약 계산
                    for month in range(1, 13):
                        month_data = result_df[result_df['월'] == month]
                        if len(month_data) == 0:
                            continue
                            
                        total_days = len(month_data)
                        unworkable = month_data[f'{task_name}_기상악화'].sum()
                        workable = total_days - unworkable
                        
                        summary_data.append({
                            '공종': task_name,
                            '월': f'{month}월',
                            '총 일수': total_days,
                            '작업 가능일': workable,
                            '비작업일': unworkable
                        })

                # 요약표 만들기
                summary_df = pd.DataFrame(summary_data)
                
                # 3. 엑셀 파일 만들기 (메모리 상에 저장)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, index=False, sheet_name='1.월별_요약표')
                    result_df.to_excel(writer, index=False, sheet_name='2.일별_상세내역')
                
                st.success("✅ 계산이 완료되었습니다! 아래 버튼을 눌러 다운로드하세요.")
                
                # 4. 다운로드 버튼 생성
                st.download_button(
                    label="📥 작업일수 엑셀 결과물 다운로드",
                    data=output.getvalue(),
                    file_name="최종_작업일수_산정결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            except KeyError as e:
                st.error(f"❌ 엑셀 파일에서 다음 이름의 열(컬럼)을 찾을 수 없습니다: {e}")
                st.info("업로드하신 엑셀 파일의 첫 번째 줄(헤더) 이름이 파이썬 코드의 이름('파고', '풍속', '강수량', '일시')과 똑같은지 확인해 주세요.")
