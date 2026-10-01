import streamlit as st
import pandas as pd
import numpy as np
import io
import holidays

st.set_page_config(page_title="항만공사 작업일수 산정", page_icon="🌊", layout="wide")

st.title("🌊 항만공사 작업일수 산정 (원본 파일 자동분석)")
st.write("프로젝트명을 입력하고 **관공서에서 다운받은 원본 파일을 가공 없이 그대로** 업로드하세요.")

project_name = st.text_input("📌 프로젝트명 (출력될 엑셀 파일명에 사용됩니다)", placeholder="예: 울산 남신항 2단계, 목포신항 해상풍력 지원항만 등")

col1, col2, col3 = st.columns(3)
with col1: file_land = st.file_uploader("☁️ 기상청 원본 (ASOS)", type=['csv', 'xlsx'])
with col2: file_sea = st.file_uploader("🌊 해양조사원 원본 (부이/조위)", type=['csv', 'xlsx'])
with col3: file_dust = st.file_uploader("😷 에어코리아 원본 (PM10)", type=['csv', 'xlsx'])

# 🌟 관공서 원본 데이터 자동 인식 및 정제 엔진
def smart_preprocess(df):
    # 1. 날짜 컬럼 찾기 (다양한 원본 양식 대응)
    date_col = next((col for col in df.columns if any(x in str(col).strip() for x in ['일시', '날짜', '시간', '관측일', 'Date'])), None)
    if date_col:
        df = df.rename(columns={date_col: '일시'})
        # 시간 단위(1시간 간격 등) 데이터가 섞여 있어도 날짜만 추출해서 통일
        df['일시'] = pd.to_datetime(df['일시'], errors='coerce').dt.normalize()
        
        # 문자열로 잘못 인식된 숫자들을 강제 변환하고 빈칸은 0으로 처리
        for col in df.columns:
            if col != '일시': 
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        # 하루에 여러 개(시간별) 데이터가 있는 경우 가장 빡센 기상(최대값)을 그날의 대표값으로 압축
        df = df.groupby('일시').max().reset_index()
        
    # 2. 복잡한 원본 컬럼명('최대풍속(m/s)', '유의파고(m)' 등)을 표준 이름으로 강제 매칭
    rename_dict = {}
    for col in df.columns:
        col_str = str(col).replace(" ", "")
        if '강수' in col_str: rename_dict[col] = '강수량'
        elif '최고기온' in col_str or ('기온' in col_str and '최고' in col_str): rename_dict[col] = '최고기온'
        elif '최저기온' in col_str or ('기온' in col_str and '최저' in col_str): rename_dict[col] = '최저기온'
        elif '적설' in col_str: rename_dict[col] = '신적설'
        elif '시정' in col_str: rename_dict[col] = '시정거리'
        elif '풍속' in col_str: rename_dict[col] = '최대풍속'
        elif '파고' in col_str: rename_dict[col] = '유의파고'
        elif '주기' in col_str: rename_dict[col] = '파주기'
        elif 'PM' in col_str.upper() or '미세먼지' in col_str: rename_dict[col] = 'PM10'
        
    return df.rename(columns=rename_dict)

def load_data(file):
    # 기상청 CSV는 주로 cp949 인코딩이라 한글 깨짐 방지 처리
    try: df = pd.read_csv(file, encoding='cp949') if file.name.endswith('.csv') else pd.read_excel(file)
    except: df = pd.read_csv(file, encoding='utf-8')
    return smart_preprocess(df)

if file_land and file_sea and file_dust and project_name:
    if st.button("🚀 항만공사 산출근거 엑셀 추출하기"):
        with st.spinner(f"'{project_name}' 원본 데이터를 조립하고 분석 중입니다..."):
            try:
                # 3개 기관 파일 병합
                merged_df = pd.merge(load_data(file_land), load_data(file_sea), on='일시', how='outer')
                merged_df = pd.merge(merged_df, load_data(file_dust), on='일시', how='outer')
                merged_df = merged_df.sort_values(by='일시').reset_index(drop=True)
                
                # 누락된 필수 열 방어 (안개는 기본값 20km(맑음), 기온은 20도로 세팅)
                req_cols = ['강수량', '최고기온', '최저기온', '신적설', '시정거리', '최대풍속', '유의파고', '파주기', 'PM10']
                for col in req_cols:
                    if col not in merged_df.columns:
                        merged_df[col] = 20.0 if col in ['시정거리', '최고기온'] else 0.0
                merged_df = merged_df.fillna(0)
                
                merged_df['연도'] = merged_df['일시'].dt.year
                merged_df['월'] = merged_df['일시'].dt.month
                total_years = merged_df['연도'].nunique()
                kr_holidays = holidays.KR(years=merged_df['연도'].unique().tolist())
                days_per_year = len(merged_df) / total_years
                
                # 비작업일 기준 판별 (0 또는 1)
                merged_df['공휴일'] = (merged_df['일시'].dt.dayofweek.isin([5, 6]) | merged_df['일시'].apply(lambda x: x in kr_holidays)).astype(int)
                merged_df['강우'] = (merged_df['강수량'] >= 10.0).astype(int)
                merged_df['고온'] = (merged_df['최고기온'] >= 33.0).astype(int)
                merged_df['저온'] = (merged_df['최저기온'] <= -12.0).astype(int)
                
                np.random.seed(42) # 안개 30% 확률 적용
                merged_df['안개'] = ((merged_df['시정거리'] <= 1.0) & (np.random.rand(len(merged_df)) < 0.3)).astype(int)
                merged_df['미세먼지'] = (merged_df['PM10'] >= 150.0).astype(int)
                
                merged_df['파랑'] = (merged_df['유의파고'] >= 0.8).astype(int)
                merged_df['강설_해상'] = (merged_df['신적설'] >= 5.0).astype(int)
                merged_df['강설_육상'] = (merged_df['신적설'] >= 1.0).astype(int)
                merged_df['풍속'] = (merged_df['최대풍속'] >= 10.0).astype(int)
                
                # 합집합(최종 비작업일) 계산
                merged_df['해상_최종'] = (merged_df[['공휴일', '강우', '고온', '저온', '파랑', '강설_해상', '안개', '미세먼지']].sum(axis=1) > 0).astype(int)
                merged_df['육상_최종'] = (merged_df[['공휴일', '강우', '고온', '저온', '풍속', '강설_육상', '안개', '미세먼지']].sum(axis=1) > 0).astype(int)

                sea_records, land_records = [], []
                
                for (year, month), group in merged_df.groupby(['연도', '월']):
                    days = len(group)
                    
                    s_indiv = group[['공휴일', '강우', '고온', '저온', '파랑', '강설_해상', '안개', '미세먼지']].sum()
                    s_sum, s_union = s_indiv.sum(), group['해상_최종'].sum()
                    sea_records.append({
                        '연도': year, '월': f"{month}월", '역일수': days,
                        '공휴일': s_indiv['공휴일'], '강우(10mm)': s_indiv['강우'], 
                        '고온(33℃)': s_indiv['고온'], '저온(-12℃)': s_indiv['저온'],
                        '파랑(0.8m)': s_indiv['파랑'], '강설(5cm)': s_indiv['강설_해상'], 
                        '안개': s_indiv['안개'], '미세먼지': s_indiv['미세먼지'],
                        '비작업일합': s_sum, '중복일': s_sum - s_union, 
                        '최종비작업': s_union, '작업일수': days - s_union
                    })
                    
                    l_indiv = group[['공휴일', '강우', '고온', '저온', '풍속', '강설_육상', '안개', '미세먼지']].sum()
                    l_sum, l_union = l_indiv.sum(), group['육상_최종'].sum()
                    land_records.append({
                        '연도': year, '월': f"{month}월", '역일수': days,
                        '공휴일': l_indiv['공휴일'], '강우(10mm)': l_indiv['강우'], 
                        '고온(33℃)': l_indiv['고온'], '저온(-12℃)': l_indiv['저온'],
                        '강설(1cm)': l_indiv['강설_육상'], '안개': l_indiv['안개'], 
                        '미세먼지': l_indiv['미세먼지'], '풍속(10m/s)': l_indiv['풍속'],
                        '비작업일합': l_sum, '중복일': l_sum - l_union, 
                        '최종비작업': l_union, '작업일수': days - l_union
                    })
                
                df_sea_yearly = pd.DataFrame(sea_records)
                df_land_yearly = pd.DataFrame(land_records)
                
                def get_avg(col): return int(round(merged_df[col].sum() / total_years))
                
                sea_u, land_u = get_avg('해상_최종'), get_avg('육상_최종')
                sea_i = sum([get_avg(c) for c in ['공휴일', '강우', '고온', '저온', '파랑', '강설_해상', '안개', '미세먼지']])
                land_i = sum([get_avg(c) for c in ['공휴일', '강우', '고온', '저온', '강설_육상', '안개', '미세먼지', '풍속']])
                sea_w, land_w = int(round(days_per_year)) - sea_u, int(round(days_per_year)) - land_u

                df_sea_summary = pd.DataFrame([{
                    '구분': '해상', '공휴일': get_avg('공휴일'), '강우': get_avg('강우'), '고온': get_avg('고온'), '저온': get_avg('저온'),
                    '파랑': get_avg('파랑'), '강설(해상)': get_avg('강설_해상'), '안개': get_avg('안개'), '미세먼지': get_avg('미세먼지'),
                    '중복일': sea_i - sea_u, '작업일수': sea_w, '가동률(%)': f"{round((sea_w / days_per_year) * 100, 1)}%"
                }])

                df_land_summary = pd.DataFrame([{
                    '구분': '육상', '공휴일': get_avg('공휴일'), '강우': get_avg('강우'), '고온': get_avg('고온'), '저온': get_avg('저온'),
                    '강설(육상)': get_avg('강설_육상'), '안개': get_avg('안개'), '미세먼지': get_avg('미세먼지'), '풍속': get_avg('풍속'), 
                    '중복일': land_i - land_u, '작업일수': land_w, '가동률(%)': f"{round((land_w / days_per_year) * 100, 1)}%"
                }])

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_sea_summary.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=1)
                    df_land_summary.to_excel(writer, index=False, sheet_name='1.보고서_총괄표', startrow=5)
                    df_sea_yearly.to_excel(writer, index=False, sheet_name='2.해상_산출근거(연월별)')
                    df_land_yearly.to_excel(writer, index=False, sheet_name='3.육상_산출근거(연월별)')
                    merged_df.drop(columns=['연도', '월']).to_excel(writer, index=False, sheet_name='4.원본데이터_정제결과')

                st.success("✅ 지저분한 원본 데이터 세척 및 성과품 추출 완료!")
                
                file_name_safe = project_name.replace(" ", "_")
                st.download_button(
                    label="📥 항만공사 성과품 다운로드 (총괄표+부록)",
                    data=output.getvalue(),
                    file_name=f"{file_name_safe}_작업일수산출({total_years}년).xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"❌ 데이터 분석 중 에러가 발생했습니다: {e}")
                st.info("파일이 손상되었거나 인코딩 형식이 특이한 경우일 수 있습니다. 파일을 다시 한 번 확인해주세요.")
else:
    st.info("👆 현장명을 입력하시고 3개 기관의 원본 데이터를 모두 업로드해 주세요.")
