import streamlit as st
import pandas as pd
import numpy as np
import io
import holidays
import os

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🏗", layout="wide")

st.title("🏗️ 항만공사 작업일수 산정 (DB 내장 & 성과품 산출)")
st.write("지역을 선택하거나 데이터를 직접 업로드하면 **보고서 총괄표와 연도별 세부 산출근거**를 엑셀로 추출합니다.")

# 1. 지역 선택 메뉴
locations = ["직접 파일 업로드", "울산 남신항", "부산 신항", "인천 신항"]
selected_loc = st.selectbox("📌 대상 항만(현장)을 선택하세요", locations)

file_land, file_sea, file_dust = None, None, None
ready_to_calc = False

# 2. 선택에 따른 UI 표시
if selected_loc == "직접 파일 업로드":
    st.info("기상청, 해양조사원, 에어코리아 원본 데이터를 각각 업로드해주세요.")
    col1, col2, col3 = st.columns(3)
    with col1: file_land = st.file_uploader("☁️ 기상청 (육상)", type=['csv', 'xlsx'])
    with col2: file_sea = st.file_uploader("🌊 해양조사원 (해상)", type=['csv', 'xlsx'])
    with col3: file_dust = st.file_uploader("😷 에어코리아 (PM10)", type=['csv', 'xlsx'])
    
    if file_land and file_sea and file_dust:
        ready_to_calc = True
else:
    # GitHub의 data 폴더에 있는 파일 경로
    file_land = f"data/{selected_loc}_육상.xlsx"
    file_sea = f"data/{selected_loc}_해상.xlsx"
    file_dust = f"data/{selected_loc}_미세먼지.xlsx"
    
    if os.path.exists(file_land) and os.path.exists(file_sea) and os.path.exists(file_dust):
        st.success(f"✅ '{selected_loc}' 지역의 10년 치 내장 데이터가 준비되었습니다.")
        ready_to_calc = True
    else:
        st.error(f"❌ '{selected_loc}'의 기초 데이터가 서버에 없습니다. GitHub 'data' 폴더에 파일을 추가해주세요.")
        st.caption(f"필요한 파일명: {selected_loc}_육상.xlsx, {selected_loc}_해상.xlsx, {selected_loc}_미세먼지.xlsx")
        ready_to_calc = False

# 3. 스마트 전처리 함수
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

# 4. 데이터 로드 함수 (업로드 파일 객체와 로컬 파일 경로 모두 지원)
def load_data(file_or_path):
    if isinstance(file_or_path, str):  # 내장 DB (경로)일 때
        if file_or_path.endswith('.csv'):
            try: df = pd.read_csv(file_or_path, encoding='cp949')
            except: df = pd.read_csv(file_or_path, encoding='utf-8')
        else:
            df = pd.read_excel(file_or_path)
    else:  # 직접 파일 업로드 객체일 때
        if file_or_path.name.endswith('.csv'):
            try: df = pd.read_csv(file_or_path, encoding='cp949')
            except: df = pd.read_csv(file_or_path, encoding='utf-8')
        else:
            df = pd.read_excel(file_or_path)
    return smart_preprocess(df)

# 5. 산정 및 엑셀 추출 로직
if ready_to_calc:
    if st.button("🚀 성과품 엑셀 추출하기 (산출근거 포함)"):
        with st.spinner('데이터를 분석하고 성과품 양식을 생성 중입니다...'):
            try:
                # 데이터 병합
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
                
                # 항목별 마스크 (0과 1)
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
                
                merged_df['해상_최종'] = (merged_df[['공휴일', '강우', '고온', '저온', '파랑', '강설_해상', '안개', '미세먼지']].sum(axis=1) > 0).astype(int)
                merged_df['육상_최종'] = (merged_df[['공휴일', '강우', '고온', '저온', '풍속', '강설_육상', '안개', '미세먼지']].sum(axis=1) > 0).astype(int)

                # 연도별/월별 상세 산출근거
                sea_records, land_records = [], []
                
                for (year, month), group in merged_df.groupby(['연도', '월']):
                    days = len(group)
                    
                    s_indiv = group[['공휴일', '강우', '고온', '저온', '파랑', '강설_해상', '안개', '미세먼지']].sum()
                    s_sum = s_indiv.sum()
                    s_union = group['해상_최종'].sum()
                    
                    sea_records.append({
                        '연도': year, '월': f"{month}월", '역일수': days,
                        '공휴일': s_indiv['공휴일'], '강우(10mm)': s_indiv['강우'], 
                        '고온(33℃)': s_indiv['고온'], '저온(-12℃)': s_indiv['저온'],
                        '파랑(0.8m)': s_indiv['파랑'], '강설(5cm)': s_indiv['강설_해상'], 
                        '안개': s_indiv['안개'], '미세먼지': s_indiv['미세먼지'],
                        '비작업일(단순합)': s_sum, '중복일': s_sum - s_union, 
                        '최종 비작업일': s_union, '최종 작업일수': days - s_union
                    })
                    
                    l_indiv = group[['공휴일', '강우', '고온', '저온', '풍속', '강설_육상', '안개', '미세먼지']].sum()
                    l_sum = l_indiv.sum()
                    l_union = group['육상_최종'].sum()
                    
                    land_records.append({
                        '연도': year, '월': f"{month}월", '역일수': days,
                        '공휴일': l_indiv['공휴일'], '강우(10mm)': l_indiv['강우'], 
                        '고온(33℃)': l_indiv['고온'], '저온(-12℃)': l_indiv['저온'],
                        '강설(1cm)': l_indiv['강설_육상'], '안개': l_indiv['안개'], 
                        '미세먼지': l_indiv['미세먼지'], '풍속(10m/s)': l_indiv['풍속'],
                        '비작업일(단순합)': l_sum, '중복일': l_sum - l_union, 
                        '최종 비작업일': l_union, '최종 작업일수': days - l_union
                    })
                
                df_sea_yearly = pd.DataFrame(sea_records)
                df_land_yearly = pd.DataFrame(land_records)
                
                # 보고서용 총괄표
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

                # 엑셀 파일 생성
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_sea_summary.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=1)
                    df_land_summary.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=5)
                    df_sea_yearly.to_excel(writer, index=False, sheet_name='2.해상공사_산출근거(연도별)')
                    df_land_yearly.to_excel(writer, index=False, sheet_name='3.육상공사_산출근거(연도별)')
                    merged_df.drop(columns=['연도', '월']).to_excel(writer, index=False, sheet_name='4.원본데이터_기록')

                st.success("✅ 설계 보고서 총괄표와 연도별 세부 산출근거 생성이 완료되었습니다!")
                file_name_prefix = selected_loc if selected_loc != "직접 파일 업로드" else "업로드"
                st.download_button(
                    label="📥 성과품 엑셀 다운로드",
                    data=output.getvalue(),
                    file_name=f"{file_name_prefix}_작업일수_성과품({total_years}년).xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"❌ 데이터 처리 중 에러가 발생했습니다: {e}")
