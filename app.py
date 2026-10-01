import streamlit as st
import pandas as pd
import numpy as np
import io
import holidays

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗", layout="wide")

st.title("🏗️ 항만공사 작업일수 자동 산정 프로그램 (표준품셈 전체기준)")
st.write("강우, 기온, 강설, 안개, 풍속, 파랑, 미세먼지 기준을 모두 적용하여 연평균 작업일수를 산정합니다.")

uploaded_file = st.file_uploader("기상 데이터 파일(Excel/CSV)을 첨부하세요", type=['csv', 'xlsx'])

if uploaded_file is not None:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.write("👀 원본 데이터 미리보기:")
    st.dataframe(df.head(3))

    if st.button("🚀 전체 기준 적용하여 산정하기"):
        with st.spinner('복합 기상조건과 달력을 분석 중입니다...'):
            try:
                result_df = df.copy()
                result_df['일시'] = pd.to_datetime(result_df['일시'])
                result_df['월'] = result_df['일시'].dt.month
                result_df['연도'] = result_df['일시'].dt.year
                
                total_years = result_df['연도'].nunique()
                kr_holidays = holidays.KR(years=result_df['연도'].unique().tolist())
                
                # [휴일 판별]
                result_df['휴일여부'] = result_df['일시'].dt.dayofweek.isin([5, 6]) | result_df['일시'].apply(lambda x: x in kr_holidays)
                
                # --- [표준품셈 기준 판별 로직] ---
                # 1. 공통 조건
                rain_limit = result_df['강수량'] >= 10.0
                temp_limit = (result_df['최고기온'] >= 33.0) | (result_df['최저기온'] <= -12.0)
                wind_limit = result_df['최대풍속'] >= 10.0
                pm10_limit = result_df['PM10'] >= 150.0
                
                # 2. 안개 조건 (시정거리 1km 이하 일수의 30%만 적용) -> 30% 확률 마스크 씌우기
                np.random.seed(42) # 계산할 때마다 결과가 바뀌지 않도록 고정
                fog_mask = (result_df['시정거리'] <= 1.0) & (np.random.rand(len(result_df)) < 0.3)
                
                # --- 공종별 세부 조건 ---
                
                # A. 해상_DCM선
                snow_sea = result_df['신적설'] >= 5.0
                wave_dcm = (result_df['유의파고'] >= 1.5) | ((result_df['유의파고'] >= 1.0) & (result_df['유의파고'] < 1.5) & (result_df['파주기'] >= 8.0))
                result_df['해상_DCM선_비작업'] = rain_limit | temp_limit | snow_sea | fog_mask | wind_limit | wave_dcm | pm10_limit
                
                # B. 해상_대선/사석공
                wave_barge = result_df['유의파고'] >= 0.8
                result_df['해상_대선사석_비작업'] = rain_limit | temp_limit | snow_sea | fog_mask | wind_limit | wave_barge | pm10_limit
                
                # C. 육상공사
                snow_land = result_df['신적설'] >= 1.0
                result_df['육상공사_비작업'] = rain_limit | temp_limit | snow_land | fog_mask | wind_limit | pm10_limit

                # 최종 비작업일 판별 (기상 + 휴일)
                tasks = ['해상_DCM선', '해상_대선사석', '육상공사']
                summary_data = []

                for task in tasks:
                    result_df[f'{task}_최종비작업'] = result_df[f'{task}_비작업'] | result_df['휴일여부']
                    
                    for month in range(1, 13):
                        month_data = result_df[result_df['월'] == month]
                        if len(month_data) == 0: continue
                            
                        total_days = len(month_data)
                        unworkable = month_data[f'{task}_최종비작업'].sum()
                        workable = total_days - unworkable
                        
                        summary_data.append({
                            '공종': task,
                            '월': f'{month}월',
                            '연평균 총 일수': round(total_days / total_years, 1),
                            '연평균 작업 가능일': round(workable / total_years, 1),
                            '연평균 비작업일': round(unworkable / total_years, 1)
                        })

                summary_df = pd.DataFrame(summary_data)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, index=False, sheet_name='1.연평균_요약표')
                    result_df.to_excel(writer, index=False, sheet_name='2.일별_판정결과(Raw)')
                
                st.success("✅ 설계기준이 완벽하게 적용되었습니다!")
                st.download_button(
                    label="📥 최종 표준품셈 작업일수 다운로드",
                    data=output.getvalue(),
                    file_name=f"항만공사_작업일수_{total_years}년평균.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            except KeyError as e:
                st.error(f"❌ 엑셀 열 이름 에러: {e}")
                st.info("엑셀 1행 이름이 '일시, 강수량, 최고기온, 최저기온, 신적설, 시정거리, 최대풍속, 유의파고, 파주기, PM10'와 똑같은지 확인하세요.")
