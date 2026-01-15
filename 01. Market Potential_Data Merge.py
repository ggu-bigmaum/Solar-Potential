# 파일명: 01. Market Potential_Data Merge-251113.py
# 여러 원천 데이터를 묶어 최종 통합본 data_merge.csv를 만듭니다.
#%%
## Package Load
import os
import pandas as pd
from dbfread import DBF
import geopandas as gpd
import time
from datetime import datetime
from functools import reduce
import numpy as np
import openpyxl
import re

RAW_FOLDER = "1. Raw Data"  # 입력 경로 고정
OUTPUT_FOLDER = "2. Output"  # 출력 경로 고정


#%%
# =============================================================================
# 데이터 병합
# =============================================================================

### 산업단지, 주차장, 농지 가중치 데이터

# 기본 데이터 확인
df_base = pd.read_csv(RAW_FOLDER + '/격자b_SGIS내륙정보(2025).csv')
print(df_base.head())

#%%
# ### 산업단지, 주차장, 농지 만들기
extra_file = [
    '/산업단지.csv',
    '/주차장(교통시설UQS200210290).csv',
    '/경지계-농업진흥구역(UEA110)_v2.csv'
]

# 병합 실행
df_base = pd.read_csv(RAW_FOLDER + '/격자b_SGIS내륙정보.csv')
df_merged = df_base.copy()  # 원본 유지
area_count = 0  # area 컬럼 개수 추적

for file in extra_file:
    # CSV 파일 불러오기
    df = pd.read_csv(RAW_FOLDER + file)


    # 병합 전 Unnamed 컬럼 제거 (df, df_merged 둘 다)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df_merged = df_merged.loc[:, ~df_merged.columns.str.contains('^Unnamed')]

    print(f"\n 병합할 파일: {file}")
    print(f"    원본 행 수: {len(df)}")

    # ID 컬럼 일치
    df["id"] = df["id"].round().astype(int)

    # area 컬럼 이름 변경
    if "area" in df.columns:
        area_count += 1
        df = df.rename(columns={"area": f"area_{area_count}"})

    # 병합
    prev_rows = len(df_merged)
    df_merged = df_merged.merge(df, on="id", how="left")
    new_rows = len(df_merged)

    # 병합 후 행 수 출력
    print(f"   - 병합 후 행 수: {new_rows}")
    if new_rows > prev_rows:
        print(f"   ※ 행 수 증가: {new_rows - prev_rows}  (중복된 ID 가능성 있음!)")
    elif new_rows < prev_rows:
        print(f"   ※ 행 수 감소: {prev_rows - new_rows}  (병합 오류 가능성 있음!)")

    print("=" * 50)

weight = pd.DataFrame()
weight['id'] = df_merged['id']


# area_1/area_2/area_3 가 inland_area보다 클 경우 inland_area 값으로 대체
df_merged['area_1'] = np.minimum(df_merged['area_1'], df_merged['inland_area'])
df_merged['area_2'] = np.minimum(df_merged['area_2'], df_merged['inland_area'])
df_merged['area_3'] = np.minimum(df_merged['area_3'], df_merged['inland_area'])


weight['weight_산업단지'] = df_merged['area_1'] / df_merged['inland_area']
weight['weight_주차장'] = df_merged['area_2'] / df_merged['inland_area']
weight['weight_영농형'] = df_merged['area_3'] / df_merged['inland_area']
print(weight)

print("weight 데이터 생성 완료")

#%%
# =============================================================================
# 변경 점 제외 데이터 원본
# =============================================================================
start_time = time.time()


# 기준 데이터 불러오기
df_base = pd.read_csv(RAW_FOLDER + '/' + 'b_전국격자_100_통합_20250507.csv', encoding='cp949')
df_base = df_base[['id']]


######### cate로 바꿀수도 있음
df_base["id"] = df_base["id"].round().astype(int)


print(f"\n [초기] df_base 행 수: {len(df_base)}")
print("=" * 50)

# 병합할 파일 리스트
file_list = [
    '/1.산지.csv',
    '/2.하천호소저수지.csv',
    '/28.주택.csv',
    '/공시지가_within.csv',     ##공시지가 원본확인
    '/전국_GIS건물(주택)_100m버퍼.csv',
    '/전국_GIS건물(주택)+실폭도로_100m버퍼.csv',
    '/1km일사량_within.csv',
    '/전체건축물.csv',
    '/격자b_SGIS내륙정보.csv',
    '/기술영향요인5종_32652.csv',
    './Dist_kepco_IDcorrected_32652.csv',
    './GRID_100m_bstats_240806_id_added(v1.1).csv',
    './GRID_100m_bstats_fa_240806_id_added(v1.1).csv',
    # './영농지_S1.csv',
    # './영농지_S2.csv',
    # './영농지_S3.csv',
    # './영농지_S4.csv',
]


# 병합 실행
df_merged = df_base.copy()  # 원본 유지
area_count = 0  # area 컬럼 개수 추적

for file in file_list:
    # CSV 파일 불러오기
    df = pd.read_csv(RAW_FOLDER + file)

    # 병합 전 Unnamed 컬럼 제거 (df, df_merged 둘 다)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df_merged = df_merged.loc[:, ~df_merged.columns.str.contains('^Unnamed')]

    print(f"\n 병합할 파일: {file}")
    print(f"    원본 행 수: {len(df)}")

    # ID 컬럼 일치
    df["id"] = df["id"].round().astype(int)

    # area 컬럼 이름 변경
    if "area" in df.columns:
        area_count += 1
        df = df.rename(columns={"area": f"area_{area_count}"})

    # 병합
    prev_rows = len(df_merged)
    df_merged = df_merged.merge(df, on="id", how="left")
    new_rows = len(df_merged)

    # 병합 후 행 수 출력
    print(f"   - 병합 후 행 수: {new_rows}")
    if new_rows > prev_rows:
        print(f"   ※ 행 수 증가: {new_rows - prev_rows}  (중복된 ID 가능성 있음!)")
    elif new_rows < prev_rows:
        print(f"   ※ 행 수 감소: {prev_rows - new_rows}  (병합 오류 가능성 있음!)")

    print("=" * 50)

#가중치
df_merged = df_merged.merge(weight, on = 'id', how = 'left')

print("=" * 50)
print("weight 병합 완료")


#id_x 가 없음;;
df = df_merged[['id', 'area_1', 'area_2', 'area_3',
       'g_value', 'area_4', 'area_5', '일사량(kWh/m2/day)',
       'area_6', 'dist', 'SIDO_CD','SIDO_NM', 'SIGUNGU_CD','SIGUNGU_NM', 'ADM_CD','ADM_NM', 'inland_area', 'area_7',
          'weight_산업단지', 'weight_주차장', 'weight_영농형',
        'SCo', 'BD', 'MeH', 'StH', 'StS', 'Cex', 'FaS',
       'NoB', 'FAN', 'FAE', 'FAS', 'FAW', 'FA_all', 'FA_s135', 'FA_s45',
       'FA_0.0',
       'FA_22.5', 'FA_45.0', 'FA_67.5', 'FA_90.0', 'FA_112.5', 'FA_135.0',
       'FA_157.5', 'FA_180.0', 'FA_202.5', 'FA_225.0', 'FA_247.5', 'FA_270.0',
       'FA_292.5', 'FA_315.0', 'FA_337.5']]





df.columns = ['id', '산지_Area_(m2)', '하천호소저수지_Area(m2)', '주택_Area(m2)', '개별공시지가(원/m2)',
                '100m버퍼_주택', '100m버퍼_주택_실폭도로', '일사량(kWh/m2/day)',
               '건물면적(m2)', 'dist','SIDO_CD','SIDO_NM', 'SIGUNGU_CD','SIGUNGU_NM', 'ADM_CD','ADM_NM', 'inland_area','5종_area',  'weight_산업단지', 'weight_주차장', 'weight_영농형',
               'SCo', 'BD', 'MeH', 'StH', 'StS', 'Cex', 'FaS',
       'NoB', 'FAN', 'FAE', 'FAS', 'FAW', 'FA_all', 'FA_s135', 'FA_s45','FA_0.0',
       'FA_22.5', 'FA_45.0', 'FA_67.5', 'FA_90.0', 'FA_112.5', 'FA_135.0',
       'FA_157.5', 'FA_180.0', 'FA_202.5', 'FA_225.0', 'FA_247.5', 'FA_270.0',
       'FA_292.5', 'FA_315.0', 'FA_337.5']




df.to_csv('data_merge_except_exclusion.csv', encoding = 'utf-8')
# 배제요인 제외하고 csv파일로 1차 저장
print("=" * 50)
print("병합 데이터 저장 완료")
elapsed_time = time.time() - start_time
print(f"\n 총 소요 시간: {elapsed_time:.4f}초")

#%%
# =============================================================================
# 배제요인 저장
# =============================================================================
start_time = time.time()

# 병합 대상 데이터 불러오기
df_merged = pd.read_csv('data_merge_except_exclusion.csv', encoding='utf-8', low_memory=False)

# Unnamed 컬럼 제거 및 ID 정리
df_merged = df_merged.loc[:, ~df_merged.columns.str.contains('^Unnamed')]

###### cate로 바꿀수도 있음
df_merged['id'] = df_merged['id'].round().astype(int)

# 배제 파일 목록
cond_reject = ['배제21종', '배제24종']  #조건에 해당하는
calc_reject = ['배제28종(1-26+6m폭도로100m버퍼+철도)'
              ,'영농지_S1','영농지_S2','영농지_S3','영농지_S4'
              ,'S3_area_solar__202511131509'
              ,'영농지_S2_area_수정본__202511131819'
              ,'_영농지_S2_area_수정본_6m__202511141044'
              , '배제29종(실조례안)']


# 병합 함수
def merge_reject_files(df_merged, file_list, prefix, area_count):
    for file in file_list:
        filename = f"{RAW_FOLDER}/{file}.csv"
        print(f"\n병합할 파일: {file}")

        try:
            df = pd.read_csv(filename, encoding='utf-8', low_memory=False)
        except Exception as e:
            print(f"※ 파일 불러오기 실패: {e}")
            continue

        # Unnamed 컬럼 제거 및 ID 정리
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df['id'] = df['id'].round().astype(int)

        # area 컬럼 이름 변경
        if 'area' in df.columns:
            new_area_col = f"{prefix}_{file}"
            df = df.rename(columns={'area': new_area_col})
            area_count += 1
        else:
            print("※ 'area' 컬럼이 존재하지 않습니다.")

        # 병합
        prev_rows = len(df_merged)
        df_merged = df_merged.merge(df, on='id', how='left')
        new_rows = len(df_merged)

        print(f"   원본 행 수: {prev_rows}")
        print(f"   병합 후 행 수: {new_rows}")
        if new_rows > prev_rows:
            print(f"   ※ 행 수 증가: {new_rows - prev_rows} (중복된 ID 가능성 있음!)")
        elif new_rows < prev_rows:
            print(f"   ※ 행 수 감소: {prev_rows - new_rows} (병합 오류 가능성 있음!)")

        print("=" * 50)

    return df_merged, area_count

# 병합 실행
area_count = 0
df_merged, area_count = merge_reject_files(df_merged, cond_reject, 'cond_reject', area_count)
df_merged, area_count = merge_reject_files(df_merged, calc_reject, 'calc_reject', area_count)

# 소요 시간 출력
elapsed_time = time.time() - start_time
print(f"\n병합 소요 시간: {elapsed_time:.2f}초")

# 저장
timestamp = datetime.now().strftime('%Y%m%d%H%M')
df_merged.to_csv(f'data_merge__{timestamp}.csv', encoding='utf-8', index=False)

# 소요 시간 출력
elapsed_time = time.time() - start_time
print(f"\n총 소요 시간: {elapsed_time:.2f}초")

#%%
# 최종 컬럼 리스트 확인
print(df_merged.columns.to_list())
