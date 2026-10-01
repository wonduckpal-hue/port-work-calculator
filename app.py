import streamlit as st
import pandas as pd
import io
import holidays  # 🌟 한국 법정 공휴일을 불러오는 라이브러리 추가

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗")

st.title("🏗️ 항만공사 작업일수 자동 산정 프로그램")
st.write("기상 조건과 **'주말/법정 공휴일'**을 중복 공제하여 연평균 작업가능일수를 산정합니다.")

uploaded_file = st.file_uploader("기상 데이터 파일(Excel/CSV)을 첨부하세요", type=['csv', 'xlsx'])

if uploaded_file is not None:
    st.success(f"'{uploaded_file.name}' 파일이 성공적으로 업로드되었습니다.")
    
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.write("👀 원본 데이터 미리보기:")
    st.dataframe(df.head())

    if st.button("🚀 연평균 최종 작업일수 추출하기"):
        with st.spinner('달력과 기상 데이터를 대조하여 분석 중입니다...'):
            try:
                work_conditions = {
                    '해상_DCM타설': {'wave': 1.0, 'wind': 10.0, 'rain': 10.0},
                    '해상_TTP거치': {'wave': 1.5, 'wind': 10.0, 'rain': 10.0}
                }
                
                result_df = df.copy()
                result_df['일시'] = pd.to_datetime(result_df['일시'])
                result_df['월'] = result_df['일시'].dt.month
                result_df['연도'] = result_df['일시'].dt.year
                
                total_years = result_df['연도'].nunique()
                
                # 🌟 1. 한국 휴일 데이터 불러오기 (데이터에 포함된 연도만 자동 추출) 🌟
                years_list = result_df['연도'].unique().tolist()
                kr_holidays = holidays.KR(years=years_list)
                
                # 🌟 2. 주말 및 공휴일 판별 🌟
                # dt.dayofweek: 5는 토요일, 6은 일요일 (토요일 작업 시 [6]으로만 수정하시면 됩니다)
                is_weekend = result_df['일시'].dt.dayofweek.isin([5, 6])
                is_pub_holiday = result_df['일시'].apply(lambda x: x in kr_holidays)
                
                result_df['휴일여부(주말+공휴일)'] = is_weekend | is_pub_holiday

                summary_data = []

                for task_name, limits in work_conditions.items():
                    # 1) 기상 제약 판별
                    over_wave = result_df['파고'] > limits['wave']
                    over_wind = result_df['풍속'] > limits['wind']
                    over_rain = result_df['강수량'] > limits['rain']
                    result_df[f'{task_name}_기상악화'] = over_wave | over_wind | over_rain
                    
                    # 🌟 2) 최종 비작업일 판별: 기상악화 OR 휴일 (중복은 1일로 처리됨) 🌟
                    result_df[f'{task_name}_최종비작업'] = result_df[f'{task_name}_기상악화'] | result_df['휴일여부(주말+공휴일)']
                    
                    for month in range(1, 13):
                        month_data = result_df[result_df['월'] == month]
                        if len(month_data) == 0: continue
                            
                        total_days_sum = len(month_data)
                        unworkable_sum = month_data[f'{task_name}_최종비작업'].sum()
                        workable_sum = total_days_sum - unworkable_sum
                        
                        # 연평균으로 환산
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
                
                st.success(f"✅ 주말/공휴일 중복 공제 적용 완료! ({total_years}년 평균 환산)")
                
                # 4. 다운로드 버튼
                st.download_button(
                    label="📥 최종 작업일수 엑셀 결과물 다운로드",
                    data=output.getvalue(),
                    file_name=f"최종_{total_years}년_평균_작업일수(휴일적용).xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            except KeyError as e:
                st.error(f"❌ 엑셀 파일에서 열(컬럼)을 찾을 수 없습니다: {e}")
