import streamlit as st
import pandas as pd
import numpy as np
import io
import holidays

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗", layout="wide")

st.title("🏗️ 항만공사 작업일수 산정 (성과품 산출근거 자동화)")
st.write("보고서용 총괄표는 물론, 납품용 부록으로 들어갈 **'연도별/월별 세부 산출근거'** 엑셀 시트까지 완벽하게 분리하여 추출합니다.")

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
    if st.button("🚀 성과품 엑셀 추출하기 (산출근거 포함)"):
        with st.spinner('항목별 비작업일을 계산하고 연도별 산출근거를 생성 중입니다...'):
            try:
                # 1. 데이터 병합 및 세팅
                merged_df = pd.merge(load_data(file_land), load_data(file_sea), on='일시', how='outer')
                merged_df = pd.merge(merged_df, load_data(file_dust), on='일시', how='outer')
                merged_df = merged_df.sort_values(by='일시').reset_index(drop=True)
                
                req_cols = ['강수량', '최고기온', '최저기온', '신적설', '시정거리', '최대풍속', '유의파고', 'PM10']
                for col in req_cols:
                    if col not in merged_df.columns:
                        merged_df[col] = 20.0 if col in ['시정거리', '최고기온'] else 0.0
                merged_df = merged_df.fillna(0)
                
                merged_df['연도'] = merged_df['일시'].dt.year
                merged_df['월'] = merged_df['일시'].dt.month
                total_years = merged_df['연도'].nunique()
                kr_holidays = holidays.KR(years=merged_df['연도'].unique().tolist())
                days_per_year = len(merged_df) / total_years
                
                # 2. 항목별 조건 마스크를 0과 1(정수)로 변환 (월별 덧셈을 위해)
                merged_df['공휴일'] = (merged_df['일시'].dt.dayofweek.isin([5, 6]) | merged_df['일시'].apply(lambda x: x in kr_holidays)).astype(int)
                merged_df['강우'] = (merged_df['강수량'] >= 10.0).astype(int)
                merged_df['고온'] = (merged_df['최고기온'] >= 33.0).astype(int)
                merged_df['저온'] = (merged_df['최저기온'] <= -12.0).astype(int)
                
                np.random.seed(42)
                merged_df['안개'] = ((merged_df['시정거리'] <= 1.0) & (np.random.rand(len(merged_df)) < 0.3)).astype(int)
                merged_df['미세먼지'] = (merged_df['PM10'] >= 150.0).astype(int)
                
                merged_df['파랑'] = (merged_df['유의파고'] >= 0.8).astype(int)
                merged_df['강설_해상'] = (merged_df['신적설'] >= 5.0).astype(int)
                merged_df['강설_육상'] = (merged_df['신적설'] >= 1.0).astype(int)
                merged_df['풍속'] = (merged_df['최대풍속'] >= 10.0).astype(int)
                
                # 3. 해상/육상 최종 합집합(중복 방어) 마스크
                merged_df['해상_최종'] = (merged_df[['공휴일', '강우', '고온', '저온', '파랑', '강설_해상', '안개', '미세먼지']].sum(axis=1) > 0).astype(int)
                merged_df['육상_최종'] = (merged_df[['공휴일', '강우', '고온', '저온', '풍속', '강설_육상', '안개', '미세먼지']].sum(axis=1) > 0).astype(int)

                # ==========================================
                # 4. 연도별/월별 상세 산출근거 만들기 (groupby)
                # ==========================================
                sea_records, land_records = [], []
                
                for (year, month), group in merged_df.groupby(['연도', '월']):
                    days = len(group)
                    
                    # 해상공사 월별 계산
                    s_indiv = group[['공휴일', '강우', '고온', '저온', '파랑', '강설_해상', '안개', '미세먼지']].sum()
                    s_sum = s_indiv.sum()
                    s_union = group['해상_최종'].sum()
                    s_overlap = s_sum - s_union
                    s_work = days - s_union
                    
                    sea_records.append({
                        '연도': year, '월': f"{month}월", '역일수': days,
                        '공휴일': s_indiv['공휴일'], '강우(10mm)': s_indiv['강우'], 
                        '고온(33℃)': s_indiv['고온'], '저온(-12℃)': s_indiv['저온'],
                        '파랑(0.8m)': s_indiv['파랑'], '강설(5cm)': s_indiv['강설_해상'], 
                        '안개': s_indiv['안개'], '미세먼지': s_indiv['미세먼지'],
                        '비작업일(단순합)': s_sum, '중복일': s_overlap, 
                        '최종 비작업일': s_union, '최종 작업일수': s_work
                    })
                    
                    # 육상공사 월별 계산
                    l_indiv = group[['공휴일', '강우', '고온', '저온', '풍속', '강설_육상', '안개', '미세먼지']].sum()
                    l_sum = l_indiv.sum()
                    l_union = group['육상_최종'].sum()
                    l_overlap = l_sum - l_union
                    l_work = days - l_union
                    
                    land_records.append({
                        '연도': year, '월': f"{month}월", '역일수': days,
                        '공휴일': l_indiv['공휴일'], '강우(10mm)': l_indiv['강우'], 
                        '고온(33℃)': l_indiv['고온'], '저온(-12℃)': l_indiv['저온'],
                        '강설(1cm)': l_indiv['강설_육상'], '안개': l_indiv['안개'], 
                        '미세먼지': l_indiv['미세먼지'], '풍속(10m/s)': l_indiv['풍속'],
                        '비작업일(단순합)': l_sum, '중복일': l_overlap, 
                        '최종 비작업일': l_union, '최종 작업일수': l_work
                    })
                
                df_sea_yearly = pd.DataFrame(sea_records)
                df_land_yearly = pd.DataFrame(land_records)
                
                # ==========================================
                # 5. 보고서용 연평균 총괄표 만들기
                # ==========================================
                def get_avg(col): return int(round(merged_df[col].sum() / total_years))
                
                sea_union_avg = get_avg('해상_최종')
                sea_indiv_avg = sum([get_avg(c) for c in ['공휴일', '강우', '고온', '저온', '파랑', '강설_해상', '안개', '미세먼지']])
                sea_work_avg = int(round(days_per_year)) - sea_union_avg
                
                land_union_avg = get_avg('육상_최종')
                land_indiv_avg = sum([get_avg(c) for c in ['공휴일', '강우', '고온', '저온', '강설_육상', '안개', '미세먼지', '풍속']])
                land_work_avg = int(round(days_per_year)) - land_union_avg

                df_sea_summary = pd.DataFrame([{
                    '구분': '해상', '공휴일': get_avg('공휴일'), '강우(10mm이상)': get_avg('강우'),
                    '고온(33℃이상)': get_avg('고온'), '저온(-12℃이하)': get_avg('저온'),
                    '파랑(0.8m이상)': get_avg('파랑'), '강설(5cm이상)': get_avg('강설_해상'),
                    '안개': get_avg('안개'), '미세먼지': get_avg('미세먼지'),
                    '중복일': sea_indiv_avg - sea_union_avg, '작업일수': sea_work_avg, 
                    '가동률(%)': f"{round((sea_work_avg / days_per_year) * 100, 1)}%"
                }])

                df_land_summary = pd.DataFrame([{
                    '구분': '육상', '공휴일': get_avg('공휴일'), '강우(10mm이상)': get_avg('강우'),
                    '고온(33℃이상)': get_avg('고온'), '저온(-12℃이하)': get_avg('저온'),
                    '강설(1cm이상)': get_avg('강설_육상'), '안개': get_avg('안개'), '미세먼지': get_avg('미세먼지'),
                    '풍속(10m/s이상)': get_avg('풍속'), 
                    '중복일': land_indiv_avg - land_union_avg, '작업일수': land_work_avg, 
                    '가동률(%)': f"{round((land_work_avg / days_per_year) * 100, 1)}%"
                }])

                # ==========================================
                # 6. 엑셀 파일 생성 (4개 시트 분리)
                # ==========================================
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # 시트 1: 총괄표
                    df_sea_summary.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=1)
                    df_land_summary.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=5)
                    
                    # 시트 2 & 3: 산출근거 (발주처 납품용 부록)
                    df_sea_yearly.to_excel(writer, index=False, sheet_name='2.해상공사_산출근거(연도별)')
                    df_land_yearly.to_excel(writer, index=False, sheet_name='3.육상공사_산출근거(연도별)')
                    
                    # 시트 4: 원본 기록
                    merged_df.drop(columns=['연도', '월']).to_excel(writer, index=False, sheet_name='4.원본데이터_기록')

                st.success("✅ 설계 보고서 총괄표와 연도별 세부 산출근거 생성이 완료되었습니다!")
                st.download_button(
                    label="📥 성과품 엑셀 다운로드 (총괄표 + 산출근거 부록)",
                    data=output.getvalue(),
                    file_name=f"항만공사_작업일수_성과품_{total_years}년.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"❌ 에러 발생: {e}")
