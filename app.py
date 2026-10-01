import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗")

st.title("🏗️ 항만공사 작업일수 자동 산정 프로그램")
st.write("기상 데이터(엑셀/CSV)를 업로드하면 공종별 **'연평균'** 작업일수를 자동으로 산정합니다.")

# 1. 파일 업로드 기능
uploaded_file = st.file_uploader("기상 데이터 파일(Excel/CSV)을 첨부하세요", type=['csv', 'xlsx'])

if uploaded_file is not None:
    st.success(f"'{uploaded_file.name}' 파일이 성공적으로 업로드되었습니다.")
    
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.write("👀 원본 데이터 미리보기:")
    st.dataframe(df.head())

    # 2. 계산 로직 시작
    if st.button("🚀 연평균 작업일수 엑셀 추출하기"):
        with st.spinner('데이터를 분석하고 연평균 작업일수를 계산 중입니다...'):
            try:
                work_conditions = {
                    '해상_DCM타설': {'wave': 1.0, 'wind': 10.0, 'rain': 10.0},
                    '해상_TTP거치': {'wave': 1.5, 'wind': 10.0, 'rain': 10.0}
                }
                
                result_df = df.copy()
                
                # 날짜 데이터 변환 및 연도/월 추출
                result_df['일시'] = pd.to_datetime(result_df['일시'])
                result_df['월'] = result_df['일시'].dt.month
                result_df['연도'] = result_df['일시'].dt.year
                
                # ⭐ 업로드된 데이터가 총 몇 년 치인지 자동 계산 ⭐
                total_years = result_df['연도'].nunique()
                st.info(f"💡 총 {total_years}년 치 데이터가 인식되었습니다. 결과를 {total_years}년 평균으로 환산합니다.")

                summary_data = []

                for task_name, limits in work_conditions.items():
                    over_wave = result_df['파고'] > limits['wave']
                    over_wind = result_df['풍속'] > limits['wind']
                    over_rain = result_df['강수량'] > limits['rain']
                    
                    result_df[f'{task_name}_기상악화'] = over_wave | over_wind | over_rain
                    
                    for month in range(1, 13):
                        month_data = result_df[result_df['월'] == month]
                        if len(month_data) == 0:
                            continue
                            
                        # 전체 기간(예: 10년) 동안의 일수 합산
                        total_days_sum = len(month_data)
                        unworkable_sum = month_data[f'{task_name}_기상악화'].sum()
                        workable_sum = total_days_sum - unworkable_sum
                        
                        # ⭐ 총 연수로 나누어 연평균 일수 산출 (소수점 1자리까지) ⭐
                        avg_total_days = round(total_days_sum / total_years, 1)
                        avg_workable = round(workable_sum / total_years, 1)
                        avg_unworkable = round(unworkable_sum / total_years, 1)
                        
                        summary_data.append({
                            '공종': task_name,
                            '월': f'{month}월',
                            '연평균 총 일수': avg_total_days,
                            '연평균 작업 가능일': avg_workable,
                            '연평균 비작업일': avg_unworkable
                        })

                summary_df = pd.DataFrame(summary_data)
                
                # 3. 엑셀 파일 생성
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, index=False, sheet_name='1.연평균_월별_요약표')
                    result_df.to_excel(writer, index=False, sheet_name='2.일별_상세내역(원본)')
                
                st.success("✅ 계산이 완료되었습니다! 아래 버튼을 눌러 다운로드하세요.")
                
                # 4. 다운로드 버튼
                st.download_button(
                    label="📥 연평균 작업일수 엑셀 결과물 다운로드",
                    data=output.getvalue(),
                    file_name=f"최종_{total_years}년_평균_작업일수_산정결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            except KeyError as e:
                st.error(f"❌ 엑셀 파일에서 다음 이름의 열(컬럼)을 찾을 수 없습니다: {e}")
                st.info("엑셀 첫 줄(헤더) 이름이 '파고', '풍속', '강수량', '일시'와 똑같은지 확인해 주세요.")
