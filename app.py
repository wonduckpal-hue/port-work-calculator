import streamlit as st
import pandas as pd
import numpy as np
import io
import holidays

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗", layout="wide")

st.title("🏗️ 항만공사 작업일수 자동 산정 (데이터 병합 기능 포함)")
st.write("기상청(육상), 해양조사원(해상), 에어코리아(미세먼지) 파일을 각각 업로드하면 자동으로 날짜를 병합하여 산정합니다.")

st.warning("⚠️ **주의사항:** 3개 파일 모두 날짜 열의 이름이 반드시 **'일시'**로 똑같아야 프로그램이 짝을 맞출 수 있습니다.")

# 1. 3개 파일 개별 업로드 UI (화면을 3칸으로 나눔)
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("☁️ 육상 기상 (기상청)")
    file_land = st.file_uploader("강수량, 기온, 풍속 등", type=['csv', 'xlsx'], key='land')
with col2:
    st.subheader("🌊 해상 기상 (해양조사원)")
    file_sea = st.file_uploader("유의파고, 파주기", type=['csv', 'xlsx'], key='sea')
with col3:
    st.subheader("😷 미세먼지 (에어코리아)")
    file_dust = st.file_uploader("PM10 농도", type=['csv', 'xlsx'], key='dust')

# 데이터를 읽어오는 내부 함수
def load_data(file):
    if file.name.endswith('.csv'):
        # 기상청 CSV는 종종 한글 인코딩(euc-kr) 문제가 있어 이를 방지
        try:
            return pd.read_csv(file, encoding='utf-8')
        except UnicodeDecodeError:
            return pd.read_csv(file, encoding='euc-kr')
    else:
        return pd.read_excel(file)

# 3개 파일이 모두 업로드 되었을 때만 실행 버튼 활성화
if file_land and file_sea and file_dust:
    st.success("✅ 3개의 파일이 모두 업로드되었습니다! 아래 병합 및 산정 버튼을 눌러주세요.")
    
    if st.button("🚀 데이터 자동 병합 및 작업일수 산정하기"):
        with st.spinner('데이터를 하나로 조립하고 기준을 분석 중입니다...'):
            try:
                # 데이터 읽기
                df_land = load_data(file_land)
                df_sea = load_data(file_sea)
                df_dust = load_data(file_dust)
                
                # 날짜(일시) 컬럼을 날짜 형식으로 통일
                df_land['일시'] = pd.to_datetime(df_land['일시'])
                df_sea['일시'] = pd.to_datetime(df_sea['일시'])
                df_dust['일시'] = pd.to_datetime(df_dust['일시'])
                
                # 🌟 [핵심] 일시(날짜)를 기준으로 3개 데이터 완벽 병합 (VLOOKUP과 동일)
                # outer join: 어느 한 쪽에만 있는 날짜라도 버리지 않고 모두 포함
                merged_df = pd.merge(df_land, df_sea, on='일시', how='outer')
                merged_df = pd.merge(merged_df, df_dust, on='일시', how='outer')
                
                # 날짜순으로 정렬
                merged_df = merged_df.sort_values(by='일시').reset_index(drop=True)
                
                # 병합 과정에서 빈칸(비가 안 오거나 눈이 안 온 날)을 0으로 채우기
                merged_df = merged_df.fillna(0)
                
                st.write("👀 병합된 데이터 미리보기:")
                st.dataframe(merged_df.head(3))
                
                # --- 이하 기존 작업일수 산정 로직 ---
                result_df = merged_df.copy()
                result_df['월'] = result_df['일시'].dt.month
                result_df['연도'] = result_df['일시'].dt.year
                total_years = result_df['연도'].nunique()
                kr_holidays = holidays.KR(years=result_df['연도'].unique().tolist())
                
                result_df['휴일여부'] = result_df['일시'].dt.dayofweek.isin([5, 6]) | result_df['일시'].apply(lambda x: x in kr_holidays)
                
                rain_limit = result_df['강수량'] >= 10.0
                temp_limit = (result_df['최고기온'] >= 33.0) | (result_df['최저기온'] <= -12.0)
                wind_limit = result_df['최대풍속'] >= 10.0
                pm10_limit = result_df['PM10'] >= 150.0
                
                np.random.seed(42)
                fog_mask = (result_df['시정거리'] <= 1.0) & (np.random.rand(len(result_df)) < 0.3)
                
                snow_sea = result_df['신적설'] >= 5.0
                wave_dcm = (result_df['유의파고'] >= 1.5) | ((result_df['유의파고'] >= 1.0) & (result_df['유의파고'] < 1.5) & (result_df['파주기'] >= 8.0))
                result_df['해상_DCM선_비작업'] = rain_limit | temp_limit | snow_sea | fog_mask | wind_limit | wave_dcm | pm10_limit
                
                wave_barge = result_df['유의파고'] >= 0.8
                result_df['해상_대선사석_비작업'] = rain_limit | temp_limit | snow_sea | fog_mask | wind_limit | wave_barge | pm10_limit
                
                snow_land = result_df['신적설'] >= 1.0
                result_df['육상공사_비작업'] = rain_limit | temp_limit | snow_land | fog_mask | wind_limit | pm10_limit

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
                
                st.success("✅ 파일 병합 및 설계기준 적용이 완벽하게 완료되었습니다!")
                st.download_button(
                    label="📥 최종 산정 엑셀 다운로드 (병합본 포함)",
                    data=output.getvalue(),
                    file_name=f"항만공사_작업일수_{total_years}년평균.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            except Exception as e:
                st.error(f"❌ 데이터 처리 중 에러가 발생했습니다: {e}")
                st.info("3개 파일 모두 첫 번째 열 이름이 반드시 '일시'인지, 그리고 나머지 필요한 열 이름들이 정확한지 확인해주세요.")
else:
    st.info("👆 위 3개의 업로드 칸에 파일을 모두 넣어주셔야 계산 버튼이 나타납니다.")
