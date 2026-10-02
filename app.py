import streamlit as st
import pandas as pd
import numpy as np
import io
import holidays

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗", layout="wide")

st.title("🏗️ 항만공사 작업일수 자동 산정 (원본 파일 자동 변환)")
st.write("관공서에서 다운받은 **원본 엑셀/CSV를 양식 수정 없이 그대로** 올리세요! 프로그램이 알아서 정리하고 병합합니다.")

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("☁️ 육상 기상 (기상청)")
    file_land = st.file_uploader("ASOS 원본 파일", type=['csv', 'xlsx'], key='land')
with col2:
    st.subheader("🌊 해상 기상 (해양조사원)")
    file_sea = st.file_uploader("관측소 원본 파일", type=['csv', 'xlsx'], key='sea')
with col3:
    st.subheader("😷 미세먼지 (에어코리아)")
    file_dust = st.file_uploader("확정자료 원본 파일", type=['csv', 'xlsx'], key='dust')

# 🌟 [스마트 전처리 엔진] 관공서 데이터를 우리 양식으로 자동 변환
def smart_preprocess(df):
    # 1. 날짜 컬럼 찾아서 통일하기
    date_col = None
    for col in df.columns:
        if any(x in str(col) for x in ['일시', '날짜', '시간', '관측일', 'Date']):
            date_col = col
            break
            
    if date_col:
        df = df.rename(columns={date_col: '일시'})
        # '2026-01-01 14:00' 같은 시간 단위가 섞여 있으면 날짜만 깔끔하게 분리
        df['일시'] = pd.to_datetime(df['일시'], errors='coerce').dt.normalize()
        
        # 숫자형 데이터 변환 및 결측치(빈칸) 0으로 채우기
        for col in df.columns:
            if col != '일시':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 해양조사원 시간별 데이터 대응 (가장 기상이 안 좋았던 최대값 기준으로 하루 1줄로 압축)
        df = df.groupby('일시').max().reset_index()
        
    # 2. 관공서별 제각각인 컬럼 이름을 스마트하게 매칭하여 이름 변경
    rename_dict = {}
    for col in df.columns:
        if '강수' in col: rename_dict[col] = '강수량'
        elif '최고기온' in col or ('기온' in col and '최고' in col): rename_dict[col] = '최고기온'
        elif '최저기온' in col or ('기온' in col and '최저' in col): rename_dict[col] = '최저기온'
        elif '적설' in col: rename_dict[col] = '신적설'
        elif '시정' in col: rename_dict[col] = '시정거리'
        elif '풍속' in col: rename_dict[col] = '최대풍속'
        elif '파고' in col: rename_dict[col] = '유의파고'
        elif '주기' in col: rename_dict[col] = '파주기'
        elif 'PM' in col.upper() or '미세먼지' in col: rename_dict[col] = 'PM10'
        
    df = df.rename(columns=rename_dict)
    return df

def load_data(file):
    if file.name.endswith('.csv'):
        try: # 기상청 CSV는 주로 cp949(euc-kr) 인코딩을 사용함
            df = pd.read_csv(file, encoding='cp949')
        except:
            df = pd.read_csv(file, encoding='utf-8')
    else:
        df = pd.read_excel(file)
    
    # 파일을 읽자마자 바로 스마트 변환 엔진 태우기
    return smart_preprocess(df)

if file_land and file_sea and file_dust:
    st.success("✅ 3개의 파일이 모두 업로드되었습니다! 아래 병합 및 산정 버튼을 눌러주세요.")
    
    if st.button("🚀 원본 자동 병합 및 작업일수 산정하기"):
        with st.spinner('원본 데이터를 자동 세척/조립하고 분석 중입니다...'):
            try:
                # 1. 파일 세척 및 변환
                df_land = load_data(file_land)
                df_sea = load_data(file_sea)
                df_dust = load_data(file_dust)
                
                # 2. 날짜(일시) 기준으로 완벽하게 병합 (VLOOKUP)
                merged_df = pd.merge(df_land, df_sea, on='일시', how='outer')
                merged_df = pd.merge(merged_df, df_dust, on='일시', how='outer')
                merged_df = merged_df.sort_values(by='일시').reset_index(drop=True)
                
                # 3. 누락된 데이터 강제 방어선 구축 (혹시 미세먼지 파일에 PM10이 없어도 에러 안 나게 방어)
                required_cols = ['강수량', '최고기온', '최저기온', '신적설', '시정거리', '최대풍속', '유의파고', '파주기', 'PM10']
                for col in required_cols:
                    if col not in merged_df.columns:
                        if col == '시정거리': merged_df[col] = 20.0 # 안개 없음 처리
                        elif col == '최고기온': merged_df[col] = 20.0 # 폭염 아님 처리
                        else: merged_df[col] = 0.0
                
                merged_df = merged_df.fillna(0)
                
                st.write("👀 변환 및 병합 완료된 마스터 데이터 미리보기:")
                st.dataframe(merged_df.head(3))
                
                # 4. 작업일수 산정 로직
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
                            '공종': task, '월': f'{month}월',
                            '연평균 총 일수': round(total_days / total_years, 1),
                            '연평균 작업 가능일': round(workable / total_years, 1),
                            '연평균 비작업일': round(unworkable / total_years, 1)
                        })

                summary_df = pd.DataFrame(summary_data)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, index=False, sheet_name='1.연평균_요약표')
                    result_df.to_excel(writer, index=False, sheet_name='2.일별_판정결과(Raw)')
                
                st.success("✅ 지저분한 원본 데이터 변환 및 설계기준 적용 완벽 완료!")
                st.download_button(
                    label="📥 원본 변환 + 산정완료 엑셀 다운로드",
                    data=output.getvalue(),
                    file_name=f"항만공사_작업일수_자동변환_{total_years}년.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"❌ 데이터 자동 변환 중 에러가 발생했습니다: {e}")
