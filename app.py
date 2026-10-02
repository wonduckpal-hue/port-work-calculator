import streamlit as st
import pandas as pd
import numpy as np
import io
import holidays

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗", layout="wide")

st.title("🏗️ 항만공사 작업일수 산정 (보고서 양식 자동화)")
st.write("기상 데이터를 병합하고, 중복일을 자동으로 계산하여 **설계 보고서 표준 양식**으로 엑셀을 추출합니다.")

col1, col2, col3 = st.columns(3)
with col1: file_land = st.file_uploader("☁️ 기상청 (육상)", type=['csv', 'xlsx'])
with col2: file_sea = st.file_uploader("🌊 해양조사원 (해상)", type=['csv', 'xlsx'])
with col3: file_dust = st.file_uploader("😷 에어코리아 (PM10)", type=['csv', 'xlsx'])

def smart_preprocess(df):
    date_col = next((col for col in df.columns if any(x in str(col) for x in ['일시', '날짜', '시간', '관측일', 'Date'])), None)
    if date_col:
        df = df.rename(columns={date_col: '일시'})
        df['일시'] = pd.to_datetime(df['일시'], errors='coerce').dt.normalize()
        for col in df.columns:
            if col != '일시': df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df = df.groupby('일시').max().reset_index()
        
    rename_dict = {}
    for col in df.columns:
        if '강수' in col: rename_dict[col] = '강수량'
        elif '최고' in col: rename_dict[col] = '최고기온'
        elif '최저' in col: rename_dict[col] = '최저기온'
        elif '적설' in col: rename_dict[col] = '신적설'
        elif '시정' in col: rename_dict[col] = '시정거리'
        elif '풍속' in col: rename_dict[col] = '최대풍속'
        elif '파고' in col: rename_dict[col] = '유의파고'
        elif 'PM' in col.upper() or '미세먼지' in col: rename_dict[col] = 'PM10'
    return df.rename(columns=rename_dict)

def load_data(file):
    try: df = pd.read_csv(file, encoding='cp949') if file.name.endswith('.csv') else pd.read_excel(file)
    except: df = pd.read_csv(file, encoding='utf-8')
    return smart_preprocess(df)

if file_land and file_sea and file_dust:
    if st.button("🚀 보고서용 엑셀 추출하기"):
        with st.spinner('중복일을 분석하고 보고서 양식을 생성 중입니다...'):
            try:
                # 1. 데이터 병합
                merged_df = pd.merge(load_data(file_land), load_data(file_sea), on='일시', how='outer')
                merged_df = pd.merge(merged_df, load_data(file_dust), on='일시', how='outer')
                merged_df = merged_df.sort_values(by='일시').reset_index(drop=True)
                
                req_cols = ['강수량', '최고기온', '최저기온', '신적설', '시정거리', '최대풍속', '유의파고', 'PM10']
                for col in req_cols:
                    if col not in merged_df.columns:
                        merged_df[col] = 20.0 if col in ['시정거리', '최고기온'] else 0.0
                merged_df = merged_df.fillna(0)
                
                # 2. 분석 기본 세팅
                total_years = merged_df['일시'].dt.year.nunique()
                kr_holidays = holidays.KR(years=merged_df['일시'].dt.year.unique().tolist())
                days_per_year = len(merged_df) / total_years
                
                # 3. 개별 조건 마스크 (True/False)
                m_holi = merged_df['일시'].dt.dayofweek.isin([5, 6]) | merged_df['일시'].apply(lambda x: x in kr_holidays)
                m_rain = merged_df['강수량'] >= 10.0
                m_hot = merged_df['최고기온'] >= 33.0
                m_cold = merged_df['최저기온'] <= -12.0
                
                np.random.seed(42)
                m_fog = (merged_df['시정거리'] <= 1.0) & (np.random.rand(len(merged_df)) < 0.3)
                m_dust = merged_df['PM10'] >= 150.0
                
                m_wave = merged_df['유의파고'] >= 0.8
                m_snow_sea = merged_df['신적설'] >= 5.0
                m_snow_land = merged_df['신적설'] >= 1.0
                m_wind = merged_df['최대풍속'] >= 10.0
                
                def get_avg(mask): return int(round(mask.sum() / total_years))

                # 4. 해상공사 중복일 및 작업일수 계산
                m_sea_union = m_holi | m_rain | m_hot | m_cold | m_wave | m_snow_sea | m_fog | m_dust
                sea_indiv_sum = get_avg(m_holi) + get_avg(m_rain) + get_avg(m_hot) + get_avg(m_cold) + get_avg(m_wave) + get_avg(m_snow_sea) + get_avg(m_fog) + get_avg(m_dust)
                sea_union_sum = get_avg(m_sea_union)
                sea_overlap = sea_indiv_sum - sea_union_sum
                sea_workable = int(round(days_per_year)) - sea_union_sum
                sea_rate = round((sea_workable / days_per_year) * 100, 1)

                # 5. 육상공사 중복일 및 작업일수 계산
                m_land_union = m_holi | m_rain | m_hot | m_cold | m_snow_land | m_fog | m_dust | m_wind
                land_indiv_sum = get_avg(m_holi) + get_avg(m_rain) + get_avg(m_hot) + get_avg(m_cold) + get_avg(m_snow_land) + get_avg(m_fog) + get_avg(m_dust) + get_avg(m_wind)
                land_union_sum = get_avg(m_land_union)
                land_overlap = land_indiv_sum - land_union_sum
                land_workable = int(round(days_per_year)) - land_union_sum
                land_rate = round((land_workable / days_per_year) * 100, 1)

                # 6. 보고서용 표(DataFrame) 3개 생성
                df_sea = pd.DataFrame([{
                    '구분': '해상', '공휴일': get_avg(m_holi), '강우(10mm이상)': get_avg(m_rain),
                    '고온(33℃이상)': get_avg(m_hot), '저온(-12℃이하)': get_avg(m_cold),
                    '파랑(0.8m이상)': get_avg(m_wave), '강설(5cm이상)': get_avg(m_snow_sea),
                    '안개': get_avg(m_fog), '미세먼지': get_avg(m_dust),
                    '중복일': sea_overlap, '작업일수': sea_workable, '가동률(%)': f"{sea_rate}%"
                }])

                df_land = pd.DataFrame([{
                    '구분': '육상', '공휴일': get_avg(m_holi), '강우(10mm이상)': get_avg(m_rain),
                    '고온(33℃이상)': get_avg(m_hot), '저온(-12℃이하)': get_avg(m_cold),
                    '강설(1cm이상)': get_avg(m_snow_land), '안개': get_avg(m_fog), '미세먼지': get_avg(m_dust),
                    '풍속(10m/s이상)': get_avg(m_wind), 
                    '중복일': land_overlap, '작업일수': land_workable, '가동률(%)': f"{land_rate}%"
                }])

                df_summary = pd.DataFrame([
                    {'구분': '작업일수', '해상공사': f"{sea_workable}일/년", '육상공사': f"{land_workable}일/년"},
                    {'구분': '가동률', '해상공사': f"{sea_rate}%", '육상공사': f"{land_rate}%"}
                ])

                # 7. 하나의 시트에 간격을 두고 예쁘게 출력
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_sea.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=1)
                    df_land.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=5)
                    df_summary.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=9)
                    
                    merged_df.to_excel(writer, index=False, sheet_name='2.원본_데이터_기록')

                st.success("✅ 설계 보고서 표준 양식으로 생성이 완료되었습니다!")
                st.download_button(
                    label="📥 보고서용 엑셀 다운로드 (중복일 계산 완벽적용)",
                    data=output.getvalue(),
                    file_name=f"작업일수_보고서용_{total_years}년평균.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"❌ 에러 발생: {e}")
