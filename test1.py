# 파일명: 사용중_cal_251113.py
# 통합 시장잠재량 분석 (건물벽면 포함)
## Package Load

#%%
import os
import re
import glob
import time
from datetime import datetime
from functools import reduce

import numpy as np
import pandas as pd
import geopandas as gpd
from dbfread import DBF
import openpyxl

# 시각화 
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.colors import LogNorm
import matplotlib.ticker as mticker
from shapely.geometry import box

import folium
from branca.colormap import linear
import contextily as ctx


#%%
# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

##입출력 고정 
RAW_FOLDER = "1. Raw Data"  # 입력 경로 고정
OUTPUT_FOLDER = "2. Output"  # 출력 경로 고정


### 사용 함수들
# 시장잠재량 공통 
def calculate_potential(df, lcoe_col1, lcoe_col2, threshold, area_factor):
    """
    시장잠재량 계산 함수 (건물지붕 제외)
    - df: 데이터프레임
    - lcoe_col1: 기준 LCOE 컬럼명
    - lcoe_col2: 비교할 LCOE 컬럼명
    - threshold: 임계값 (SMP + REC * REC가중치)
    - area_factor: 해당 부문의 태양광 면적 비율
    """
    land = df['inland_area(km2)'].fillna(0)
    exclusion_area_raw = df['(기술적_지원+규제)_배제지역(km2)'].fillna(0)   #이것도 바꿔야되는거 아님감?
    exclusion_area = np.minimum(exclusion_area_raw, land)
    exclusion_codition_area = df['(기술적_지원+규제)_배제지역_조건(km2)'].fillna(0)
    building_area = np.minimum(df['건물면적(km2)'].fillna(0), df['inland_area(km2)'].fillna(0))
    
    return np.where(
        df[lcoe_col2].isna(), 0,
        np.where(
            (df[lcoe_col2] > threshold) | 
            (exclusion_codition_area != 0) |
            (exclusion_codition_area > land) ,
            0,
            ((land - exclusion_area) / land) *
            df['이론적잠재량_발전량(TWh/년)'] *
            (parameter_dict['모듈효율'] * parameter_dict['system_efficiency']) *
            ((land - building_area) / land) * area_factor
        )
    )


def calculate_potential_sample(df, lcoe_col1, lcoe_col2, threshold, area_factor):
    """
    시장잠재량 계산 함수 (건물지붕 제외)
    - df: 데이터프레임
    - lcoe_col1: 기준 LCOE 컬럼명
    - lcoe_col2: 비교할 LCOE 컬럼명
    - threshold: 임계값 (SMP + REC * REC가중치)
    - area_factor: 해당 부문의 태양광 면적 비율
    """
    land = df['inland_area(km2)'].fillna(0)
    exclusion_area_raw = df['(기술적_지원+규제)_배제지역(km2)'].fillna(0)
    exclusion_area = np.minimum(exclusion_area_raw, land)
    exclusion_codition_area = df['(기술적_지원+규제)_배제지역_조건(km2)'].fillna(0)
    building_area = np.minimum(df['건물면적(km2)'].fillna(0), df['inland_area(km2)'].fillna(0))
    
    return np.where(
        df[lcoe_col2].isna(), 0,
        np.where(
            (df[lcoe_col2] > threshold) | 
            (exclusion_codition_area != 0) |
            (exclusion_codition_area > land) ,
            0,
            ((exclusion_area) / land) *
            df['이론적잠재량_발전량(TWh/년)'] *
            (parameter_dict['모듈효율'] * parameter_dict['system_efficiency']) *
            ((land - building_area) / land) * area_factor
        )
    )


def calculate_weighted_potential(df, base_col, usage_type):
    """
    특정 용도에 대해 가중치를 곱한 시장잠재량을 계산
    """
    weight_col = f'weight_{usage_type}'
    result_col = f"{base_col.replace('발전량', usage_type + '_발전량')}"
    
    if weight_col not in df.columns:
        raise ValueError(f"'{weight_col}' 컬럼이 weight_df에 없습니다.")
    
    return df[base_col] * df[weight_col]

def calculate_capacity(df, power_columns, capacity_factor_col='CapacityFactor'):
    """
    발전량을 기반으로 설비용량(GW) 계산
    """
    for col in power_columns:
        new_col_name = col.replace('발전량(TWh/년)', '설비용량(GW)')
        df[new_col_name] = np.where(
            df[capacity_factor_col] == 0, 0,
            df[col] / (365 * 24 * df[capacity_factor_col]) * (10 ** 3)
        )
    return df

# ======= 새로 추가: 건물벽면 관련 함수들 =======
def calculate_grid_connection_cost_facade(df, parameter_dict):
    """건물벽면 계통연계비 계산"""
    df['계통_기본시설비(원/kW)'] = 24000  # parameter 파일에 설정 필요
    df['계통_거리부담금(원/100m)'] = 1200000  # parameter 파일에 설정 필요    
    df['계통_거리부담금(원)'] = df['계통_거리부담금(원/100m)'] * np.floor(np.maximum((df['dist'] - 200)/100, 0))
    df['계통_거리부담금(원/kW)'] = df['계통_거리부담금(원)'] / 1000
    
    df['설치비_계통연계비_(원/kW)'] = (
        df['계통_기본시설비(원/kW)'] + df['계통_거리부담금(원/kW)']        
    ) * 1.1
    
    return df

def calculate_wall_irradiance(df):
    """벽면일사량 계산"""
    # 1. 벽면일사량 계산
    df['벽면일사량(kWh/m2/day)'] = ((-56.62) * np.log(df['벽면면적'].clip(lower=1e-6)) + 1287.5) / 365

    # 2. 필터링된 벽면일사량 계산
    df['벽면일사량(kWh/m2/day)_filtered'] = np.minimum(
        df['벽면일사량(kWh/m2/day)'],
        df['일사량(kWh/m2/day)'] * 0.333
    ) * 48.4 / 33.3
    
    return df

def calculate_facade_operation_cost(df, parameter_dict):
    """건물벽면 운영비 계산"""
    parameter_dict['운영비_건물벽면(원/kW/년)'] = 22800  # parameter 파일에 설정 필요
    
    # 20년간 운영비 현재가치 계산
    df['운영비_건물벽면_20년(원/kW)'] = sum(
        (parameter_dict['운영비_건물벽면(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / 
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    return df

def calculate_facade_capacity_factor_and_generation(df, parameter_dict):
    """건물벽면 이용률 및 발전량 계산"""
    df['CapacityFactor_평균_2024'] = 0.1538
    df['일사량평균(kWh/m2/day)'] = 3.786215554
    
    # 건물벽면 이용률 계산
    df['CapacityFactor_건물벽면'] = (
        df['벽면일사량(kWh/m2/day)_filtered'] / 
        df['일사량평균(kWh/m2/day)'] * df['CapacityFactor_평균_2024']
    )
    
    # 20년간 발전량 현재가치 계산
    df['발전량_건물벽면_20년(Wh)'] = sum(
        (df['CapacityFactor_건물벽면'] * 8760 * 1000 * (1 - parameter_dict['Discount_rate']) ** i) /
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    return df

def calculate_facade_lcoe(df):
    """건물벽면 LCOE 계산"""
    df['설치비_건물벽면(원/kW)'] = 1090000
    
    # LCOE 계산 (발전량이 0인 경우 NaN 처리)
    df['LCOE_건물벽면(원/kWh)'] = np.where(
        df['발전량_건물벽면_20년(Wh)'] == 0, 
        np.nan,
        (df['설치비_건물벽면(원/kW)'] + df['운영비_건물벽면_20년(원/kW)']) * 1000 / df['발전량_건물벽면_20년(Wh)']
    )
    
    return df

def calculate_facade_market_potential(df, parameter_dict, smp_rec_values):
    """건물벽면 시장잠재량 계산"""
    # 벽면면적이 있는 경우에만 계산
    df['벽면면적'] = df.get('벽면면적', 0)  # 벽면면적 컬럼이 없으면 0으로 설정
    
    # 벽면 시장잠재량 계산 (건물지붕과 유사한 로직)
    land = df['inland_area(km2)'].fillna(0)
    exclusion_area_raw = df['(기술적_지원+규제)_배제지역(km2)'].fillna(0)
    exclusion_area = np.minimum(exclusion_area_raw, land)
    exclusion_codition_area = df['(기술적_지원+규제)_배제지역_조건(km2)'].fillna(0)
    
    df['시장잠재량_건물벽면_발전량(TWh/년)'] = np.where(
        df['LCOE_건물벽면(원/kWh)'].isna(), 0,
        np.where(
            df['LCOE_건물벽면(원/kWh)'] > smp_rec_values['건물지붕'], 0,  # 건물지붕과 동일한 임계값 사용
            ((0.01 - exclusion_area) / 0.01) *
            df['이론적잠재량_발전량(TWh/년)'] *
            (parameter_dict['모듈효율'] * parameter_dict['system_efficiency']) *
            ((df['벽면면적'] / 1e6) / 0.01) * parameter_dict.get('태양광_건물벽면_면적비율', 0.1)  # 벽면 면적비율
        )
    )
    
    return df

def create_histogram(df, column, title, xlabel, bins=50, figsize=(10, 6)):
    """히스토그램 생성 함수 (건물벽면용)"""
    plt.figure(figsize=figsize)
    plt.hist(df[column].dropna(), bins=bins, alpha=0.7, edgecolor='black')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel('빈도')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

def plot_wall_area_vs_irradiance(df):
    """벽면면적과 벽면일사량 관계 시각화"""
    plt.figure(figsize=(10, 6))
    plt.scatter(df['벽면면적'], df['벽면일사량(kWh/m2/day)'], s=10, alpha=0.5, color='darkorange')
    
    plt.title("벽면면적에 따른 벽면일사량 함수 관계")
    plt.xlabel("벽면면적 (m²)")
    plt.ylabel("벽면일사량 (kWh/m²/day)")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

# ======= 기존 함수들 (수정됨) =======
def print_market_potential_summary(df, return_df=False):
    """
    시장잠재량 발전량 및 설비용량 요약을 출력하는 함수 (건물벽면 추가)
    return_df=True 시 DataFrame으로도 반환
    """
    category_mapping = {
        '시장잠재량_건물지붕': ['시장잠재량_건물지붕_발전량(TWh/년)', '시장잠재량_건물지붕_설비용량(GW)'],
        '시장잠재량_건물벽면': ['시장잠재량_건물벽면_발전량(TWh/년)', '시장잠재량_건물벽면_설비용량(GW)'],
        '시장잠재량_수상형': ['시장잠재량_수상형_발전량(TWh/년)', '시장잠재량_수상형_설비용량(GW)'],
        '시장잠재량_영농형_20년': ['시장잠재량_영농형_20년_발전량(TWh/년)', '시장잠재량_영농형_20년_설비용량(GW)'],
        '시장잠재량_영농형_20년_고정가계약': ['시장잠재량_영농형_20년_발전량(TWh/년)_고정가계약', '시장잠재량_영농형_20년_설비용량(GW)_고정가계약'],
        '시장잠재량_영농형_8년': ['시장잠재량_영농형_8년_발전량(TWh/년)', '시장잠재량_영농형_8년_설비용량(GW)'],
        '시장잠재량_영농형_23년': ['시장잠재량_영농형_23년_발전량(TWh/년)', '시장잠재량_영농형_23년_설비용량(GW)'],
        '시장잠재량_토지': ['시장잠재량_토지_발전량(TWh/년)', '시장잠재량_토지_설비용량(GW)'],
        '시장잠재량_토지_계통반영': ['시장잠재량_토지_계통반영_발전량(TWh/년)', '시장잠재량_토지_계통반영_설비용량(GW)'],
        '시장잠재량_산업단지_토지' : ['시장잠재량_토지_산업단지_발전량(TWh/년)', '시장잠재량_토지_산업단지_설비용량(GW)'],
        '시장잠재량_산업단지_건물지붕' : ['시장잠재량_건물지붕_산업단지_발전량(TWh/년)', '시장잠재량_건물지붕_산업단지_설비용량(GW)'],
        '시장잠재량_주차장_토지' : ['시장잠재량_토지_주차장_발전량(TWh/년)', '시장잠재량_토지_주차장_설비용량(GW)'],
        '시장잠재량_주차장_건물지붕' : ['시장잠재량_건물지붕_주차장_발전량(TWh/년)', '시장잠재량_건물지붕_주차장_설비용량(GW)'],
        '시장잠재량_영농형_토지' : ['시장잠재량_토지_영농형_발전량(TWh/년)', '시장잠재량_토지_영농형_설비용량(GW)'],
        '시장잠재량_영농형_건물지붕' :['시장잠재량_건물지붕_영농형_발전량(TWh/년)', '시장잠재량_건물지붕_영농형_설비용량(GW)']
    }

    # DataFrame 결과 저장용
    summary_data = []

    for category, columns in category_mapping.items():
        if columns[0] in df.columns and columns[1] in df.columns:
            발전량 = df[columns[0]].sum()
            설비용량 = df[columns[1]].sum()
            summary_data.append({
                '구분': category,
                '발전량(TWh/년)': round(발전량, 4),
                '설비용량(GW)': round(설비용량, 4)
            })

    summary_df = pd.DataFrame(summary_data)

    if return_df:
        return summary_df
    else:
        # 전체 출력을 위한 pandas 옵션 설정
        with pd.option_context('display.max_rows', None, 'display.width', None):
            print("\n" + "=" * 60)
            print("시장잠재량 요약 (전국 합계)")
            print("=" * 60)
            print(summary_df.to_string(index=False))
            print("=" * 60)
        return summary_df


#여기서 시나리오 맞춰서 지정이 되는거잖아??
#인자가 실제로 3개인데??
def run_scenario_with_facade(df_base, calcul_col, condition_col='cond_reject_배제21종'):  
    """
    배제 시나리오별 전체 태양광 시장잠재량 분석 로직을 실행하여 결과 DataFrame 반환 (건물벽면 포함)
    """
    df_scenario = df_base.copy()

    # ▣ 배제 지역 면적 계산
    df_scenario['(기술적_지원+규제)_배제지역_조건(m2)'] = df_scenario[condition_col]
    df_scenario['(기술적_지원+규제)_배제지역(m2)'] = df_scenario[calcul_col]
    df_scenario['(기술적_지원+규제)_배제지역(km2)'] = df_scenario['(기술적_지원+규제)_배제지역(m2)'] / 1e6
    df_scenario['(기술적_지원+규제)_배제지역_조건(km2)'] = df_scenario['(기술적_지원+규제)_배제지역_조건(m2)'] / 1e6


    # ▣ 건물지붕 발전량
    df_scenario['시장잠재량_건물지붕_발전량(TWh/년)'] = np.where(
        df_scenario['LCOE_건물지붕(원/kWh)'].isna(), 0,
        np.where(
            df_scenario['LCOE_건물지붕(원/kWh)'] > smp_rec_values['건물지붕'], 0,
            ((0.01 - df_scenario['(기술적_지원+규제)_배제지역(km2)'].fillna(0)) / 0.01) *
            df_scenario['이론적잠재량_발전량(TWh/년)'] *
            (parameter_dict['모듈효율'] * parameter_dict['system_efficiency']) *
            ((df_scenario['건물면적(km2)'].fillna(0) / 0.01) * parameter_dict['태양광_건물지붕_면적비율'])
        )
    )

    # ▣ 건물벽면 발전량 (새로 추가)
    if '벽면면적' in df_scenario.columns:
        df_scenario = calculate_facade_market_potential(df_scenario, parameter_dict, smp_rec_values)

    # ▣ 수상형 발전량
    df_scenario['하천호소저수지_Area_(km2)_correct'] = np.where(
        df_scenario['하천호소저수지_Area_(km2)'] > df_scenario['inland_area(km2)'],
        df_scenario['inland_area(km2)'],
        df_scenario['하천호소저수지_Area_(km2)']
    )

    df_scenario['시장잠재량_수상형_발전량(TWh/년)'] = np.where(
        df_scenario['LCOE_수상형(원/kWh)'].isna(), 0,
        np.where(
            df_scenario['LCOE_수상형(원/kWh)'] > smp_rec_values['수상형'], 0,
            (df_scenario['하천호소저수지_Area_(km2)_correct'].fillna(0) / df_scenario['inland_area(km2)']) *
            df_scenario['이론적잠재량_발전량_수상형(TWh/년)'].fillna(0) *
            (parameter_dict['모듈효율'] * parameter_dict['system_efficiency']) *
            parameter_dict['태양광_수상형_면적비율']
        )
    )

    # ▣ 영농형 발전량 (공통 함수 활용)
    df_scenario['시장잠재량_영농형_20년_발전량(TWh/년)'] = calculate_potential(
        df_scenario, 'LCOE_토지(원/kWh)', 'LCOE_영농형_20년(원/kWh)',
        smp_rec_values['토지'], parameter_dict['태양광_영농형_20년_면적비율']
    ) * df_scenario['weight_영농형']

    df_scenario['시장잠재량_영농형_20년_발전량(TWh/년)_고정가계약'] = calculate_potential(
        df_scenario, 'LCOE_토지(원/kWh)', 'LCOE_영농형_20년(원/kWh)',
        smp_rec_values['토지_고정가계약'], parameter_dict['태양광_영농형_20년_면적비율']
    ) * df_scenario['weight_영농형']

    df_scenario['시장잠재량_영농형_8년_발전량(TWh/년)'] = calculate_potential(
        df_scenario, 'LCOE_토지(원/kWh)', 'LCOE_영농형_8년(원/kWh)',
        smp_rec_values['토지'], parameter_dict['태양광_영농형_8년_면적비율']
    ) * df_scenario['weight_영농형']

    df_scenario['시장잠재량_영농형_23년_발전량(TWh/년)'] = calculate_potential(
        df_scenario, 'LCOE_토지(원/kWh)', 'LCOE_영농형_23년(원/kWh)',
        smp_rec_values['토지'], parameter_dict['태양광_영농형_20년_면적비율']
    ) * df_scenario['weight_영농형'] 

    # ▣ 토지 발전량
    df_scenario['시장잠재량_토지_발전량(TWh/년)'] = calculate_potential(
        df_scenario, 'LCOE_토지(원/kWh)', 'LCOE_토지(원/kWh)',
        smp_rec_values['토지'], parameter_dict['태양광_토지_면적비율']
    )

    # ▣ 발전량 → 설비용량 계산
    power_columns = [
        '시장잠재량_건물지붕_발전량(TWh/년)', '시장잠재량_수상형_발전량(TWh/년)',
        '시장잠재량_영농형_20년_발전량(TWh/년)', '시장잠재량_영농형_20년_발전량(TWh/년)_고정가계약',
        '시장잠재량_영농형_8년_발전량(TWh/년)', '시장잠재량_토지_발전량(TWh/년)',
        '시장잠재량_영농형_23년_발전량(TWh/년)'
    ]
    
    # 건물벽면 컬럼이 있으면 추가
    if '시장잠재량_건물벽면_발전량(TWh/년)' in df_scenario.columns:
        power_columns.append('시장잠재량_건물벽면_발전량(TWh/년)')
    
    df_scenario = calculate_capacity(df_scenario, power_columns)

    # ▣ 계통연계비 및 계통반영 LCOE
    df_scenario['설치비_계통연계비_(원/kW)'] = (
        parameter_dict['계통_기본시설비(원/kW)'] * (df_scenario['시장잠재량_토지_설비용량(GW)'] * 1e6) +
        parameter_dict['계통_거리부담금(원/100m)'] * np.maximum(df_scenario['dist'] / 100 - 200, 0)
    ) * 1.1

    # NOTE: 아래 LCOE 계산 부분에서 사용되는 df_lcoe 변수는 이 함수 내에서 정의되지 않았으며, 
    # 원본 노트북에서 전역 변수로 사용되었을 가능성이 높습니다.
    df_scenario['LCOE_토지_계통반영(원/kWh)'] = np.where(
        df_lcoe['발전량_토지_20년(Wh)'] == 0, np.nan,
        (
            parameter_dict['설치비_토지(원/kW)'] + df_scenario['설치비_계통연계비_(원/kW)'] +
            df_scenario['운영비_토지_20년(원/kW)'] + df_scenario['토지임대료_20년(원/kW)']
        ) * 1000 / df_lcoe['발전량_토지_20년(Wh)']
    )

    df_scenario['시장잠재량_토지_계통반영_발전량(TWh/년)'] = calculate_potential(
        df_scenario, 'LCOE_토지_계통반영(원/kWh)', 'LCOE_토지_계통반영(원/kWh)',
        smp_rec_values['토지'], parameter_dict['태양광_토지_면적비율']
    )
    df_scenario = calculate_capacity(df_scenario, ['시장잠재량_토지_계통반영_발전량(TWh/년)'])

    # ▣ 용도별 가중치 적용
    usage_types = ['산업단지', '주차장', '영농형']

    for usage in usage_types:
        base_col = '시장잠재량_토지_발전량(TWh/년)'
        result_col = f'시장잠재량_토지_{usage}_발전량(TWh/년)'
        df_scenario[result_col] = calculate_weighted_potential(df_scenario, base_col, usage)
        calculate_capacity(df_scenario, [result_col])

    for usage in usage_types:
        base_col = '시장잠재량_건물지붕_발전량(TWh/년)'
        result_col = f'시장잠재량_건물지붕_{usage}_발전량(TWh/년)'
        df_scenario[result_col] = calculate_weighted_potential(df_scenario, base_col, usage)
        calculate_capacity(df_scenario, [result_col])

    # ▣ 결과 컬럼 필터링
    id_cols = ['id', 'SIDO_NM', 'SIGUNGU_NM', 'SIGUNGU_CD', 'ADM_NM', 'ADM_CD']
    result_cols = id_cols + [col for col in df_scenario.columns if '시장잠재량' in col]
    return df_scenario[result_cols]

# 기존 함수들 참조
def safe_filename(text):
    text = text.replace(" ", "_")
    text = re.sub(r'[^\w가-힣]', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')

def save_result_csv(df, filename, output_folder="2. Output"):
    start_time = time.time()
    if not filename.lower().endswith('.csv'):
        filename += '.csv'
    os.makedirs(output_folder, exist_ok=True)
    file_path = os.path.join(output_folder, filename)
    df.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"[CSV 저장 완료] {file_path}")
    elapsed_time = time.time() - start_time
    print(f"총 소요 시간: {elapsed_time:.2f}초")

def summarize_by_sido(df):
    columns_to_sum = [col for col in df.columns if '시장잠재량' in col and ('설비용량' in col or '발전량' in col)]
    result = df.groupby('SIDO_NM')[columns_to_sum].sum().reset_index()
    return result

def summarize_by_sigungu(df):
    columns_to_sum = [col for col in df.columns if '시장잠재량' in col and ('설비용량' in col or '발전량' in col)]
    result = df.groupby(['SIDO_NM', 'SIGUNGU_NM', 'SIGUNGU_CD'])[columns_to_sum].sum().reset_index()
    return result

def summarize_by_dong(df):
    columns_to_sum = [col for col in df.columns if '시장잠재량' in col and ('설비용량' in col or '발전량' in col)]
    result = df.groupby(['SIDO_NM', 'SIGUNGU_NM', 'SIGUNGU_CD', 'ADM_NM', 'ADM_CD'])[columns_to_sum].sum().reset_index()
    return result

def summarize_sigungu_by_sido(df, selected_sido):
    df_filtered = df[df['SIDO_NM'] == selected_sido]
    columns_to_sum = [col for col in df.columns if '시장잠재량' in col and '설비용량' in col]
    result = df_filtered.groupby('SIGUNGU_NM')[columns_to_sum].sum().reset_index()
    return result


# 전역 변수 (함수 외부에 정의되어 있다고 가정)
# parameter_dict, df_lcoe, smp_rec_values 변수는 main 함수 외부에서
# 초기화되었거나 main 함수 내에서 글로벌 선언 후 사용됨을 가정합니다.
# run_scenario_with_facade, calculate_potential, calculate_capacity, 
# calculate_grid_connection_cost_facade, calculate_wall_irradiance, 
# calculate_facade_operation_cost, calculate_facade_capacity_factor_and_generation, 
# calculate_facade_lcoe, print_market_potential_summary, 
# create_histogram, plot_wall_area_vs_irradiance, summarize_by_sido, 
# summarize_by_sigungu, save_result_csv 함수는 정의되어 있다고 가정합니다.

def main(scenario_name: str,
         print_summary: bool = False,
         create_viz: bool = False,
         create_map_viz: bool = False,
         summarize_area: bool = False,
         return_lcoe: bool = False) -> pd.DataFrame:
    """
    메인 실행 함수 (건물벽면 포함)

    scenario_name: 실행할 시나리오의 컬럼명.
    print_summary: 시장잠재량 결과 요약 출력 여부. (7번)
    create_viz: 건물벽면 시각화 생성 여부. (8번)
    create_map_viz: 지도 시각화 생성 및 3. Image 폴더 저장 여부. (8-1번)
    summarize_area: 시도/시군구별 집계 실행 여부. (9번)
    return_lcoe: LCOE 컬럼 포함한 전체 데이터 반환 여부. (기본값: False, 시장잠재량만 반환)
    """
    global parameter_dict, df_lcoe, smp_rec_values
    print(f"=== 통합 시장잠재량 분석 시작 (시나리오: {scenario_name}) ===")
    
    # 1. 데이터 불러오기
    print("데이터 로딩 중...")
    parameter = pd.read_excel('./1. Raw Data/시장잠재량 Parameter_4.xlsx')
    parameter_dict = parameter.iloc[0].to_dict()
    
    
    
    ### 여기 - 병합 데이터 파일명을 data_merge__{YYYYMMDDHHMM}.csv 형식으로 수정 필요
    ##  ***
    ##  ***
    
    df = pd.read_csv('data_merge__202603171907.csv', low_memory=False, encoding = 'euc-kr')
    
    ## ***
    ## ***





    # 2. 연산 전 기초 계산
    print("기초 데이터 처리 중...")
    start_time = time.time()
    df = df[df['inland_area'] > 0].copy()

    df['개별공시지가(원/m2)'] = df['개별공시지가(원/m2)'].astype(str).str.replace(",", "").astype(float)
    df['inland_area(km2)'] = df['inland_area'] / 10 ** 6
    
    # 변수 처리
    df['산지_Area_(km2)'] = df['산지_Area_(m2)'] / 10 ** 6
    df['하천호소저수지_Area_(km2)'] = df['하천호소저수지_Area(m2)'] / 10 ** 6
    df['건물면적(km2)'] = df['건물면적(m2)'] / 10 ** 6
    
    df['CapacityFactor'] = (
        df['일사량(kWh/m2/day)'] / parameter_dict['일사량평균(kWh/m2/day)'] * parameter_dict['CapacityFactor_평균_2024']
    )
    df['일사량_수상형(kWh/m2/day)'] = df['일사량(kWh/m2/day)'] * parameter_dict['일사량_상승분_수상형']
    df['수상형_임대료_20년(원/kW)'] = 0
    
    # 이론적 잠재량
    land = df['inland_area(km2)'].fillna(0) * 10**6
    df['이론적잠재량_발전량(TWh/년)'] = df['일사량(kWh/m2/day)'] * 365 * land / 10**9
    df['이론적잠재량_발전량_수상형(TWh/년)'] = df['일사량_수상형(kWh/m2/day)'] * 365 * 10**4 / 10**9
    df['이론적잠재량_설비용량(GW)'] = df['이론적잠재량_발전량(TWh/년)'] / 8760 / df['CapacityFactor'] * 10**3
    df['이론적잠재량_설비용량_수상형(GW)'] = df['이론적잠재량_발전량_수상형(TWh/년)'] / 8760 / df['CapacityFactor'] * 10**3
    
    # 임대료 계산
    df['임대료_기준가(원/kW/년)'] = df['개별공시지가(원/m2)'] / parameter_dict['현실화율(공시지가/실거래가)'] * parameter_dict['소요면적(m2/kW)'] * parameter_dict['임대요율']
    df['토지임대료_20년(원/kW)'] = sum(
        (df['임대료_기준가(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    df['토지임대료_8년(원/kW)'] = sum(
        (df['임대료_기준가(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(8)
    )
    df['토지임대료_23년(원/kW)'] = sum(
        (df['임대료_기준가(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(23)
    )
    
    # 운영비 계산
    df['운영비_건물지붕_20년(원/kW)'] = sum(
        (parameter_dict['운영비_건물지붕(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / 
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    df['운영비_수상형_20년(원/kW)'] = sum(
        (parameter_dict['운영비_수상형(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / 
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    df['운영비_영농형_20년(원/kW)'] = sum(
        (parameter_dict['운영비_영농형_20년(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / 
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    df['운영비_토지_20년(원/kW)'] = sum(
        (parameter_dict['운영비_토지(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / 
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    df['운영비_영농형_8년(원/kW)'] = sum(
        (parameter_dict['운영비_영농형_8년(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / 
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(8)
    )
    
    df['운영비_영농형_23년(원/kW)'] = sum(
        (parameter_dict['운영비_영농형_20년(원/kW/년)'] * (1 + parameter_dict['O&M_inflation']) ** i) / 
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(23)
    )
    
    # 발전량 계산
    df['발전량_토지_20년(Wh)'] = sum(
        (df['CapacityFactor'] * 8760 * 1000 * (1 - parameter_dict['Discount_rate']) ** i) /
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    df['발전량_수상형_20년(Wh)'] = sum(
        (df['CapacityFactor'] * 8760 * 1000 * (1 - parameter_dict['Discount_rate']) ** i) /
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    df['발전량_건물지붕_20년(Wh)'] = sum(
        (df['CapacityFactor'] * 8760 * 1000 * (1 - parameter_dict['Discount_rate']) ** i) /
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    df['발전량_영농형_20년(Wh)'] = sum(
        (df['CapacityFactor'] * 8760 * 1000 * (1 - parameter_dict['Discount_rate']) ** i) /
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(20)
    )
    
    df['발전량_영농형_8년(Wh)'] = sum(
        (df['CapacityFactor'] * 8760 * 1000 * (1 - parameter_dict['Discount_rate']) ** i) /
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(8)
    )
    
    df['발전량_영농형_23년(Wh)'] = sum(
        (df['CapacityFactor'] * 8760 * 1000 * (1 - parameter_dict['Discount_rate']) ** i) /
        (1 + parameter_dict['Discount_rate']) ** (i + 1)
        for i in range(23)
    )
    
    # 3. 건물벽면 관련 계산 (새로 추가)
    print("건물벽면 관련 계산 중...")
    
    # 벽면면적이 있는지 확인하고 없으면 임시로 생성 (실제로는 데이터에서 가져와야 함)
    if '벽면면적' not in df.columns:
        # 예시: 건물면적 기반으로 벽면면적 추정 (실제 데이터로 교체 필요)
        df['벽면면적'] = df['건물면적(m2)'] * 0.1  # 임시 계산식
    
    # 건물벽면 전용 계산
    df = calculate_grid_connection_cost_facade(df, parameter_dict)
    df = calculate_wall_irradiance(df)
    df = calculate_facade_operation_cost(df, parameter_dict)
    df = calculate_facade_capacity_factor_and_generation(df, parameter_dict)
    df = calculate_facade_lcoe(df)

    
    # 4. 기존 LCOE 계산
    print("기존 LCOE 계산 중...")
    df_lcoe = df.copy() # df_lcoe 변수에 LCOE 계산 결과를 담을 DataFrame 생성
    
    df_lcoe['LCOE_수상형(원/kWh)'] = np.where(
        df_lcoe['발전량_수상형_20년(Wh)'] == 0, np.nan,
        (parameter_dict['설치비_수상형(원/kW)'] + df_lcoe['운영비_수상형_20년(원/kW)'] + df_lcoe['수상형_임대료_20년(원/kW)']) * 1000 / df_lcoe['발전량_수상형_20년(Wh)']
    )
    
    df_lcoe['LCOE_건물지붕(원/kWh)'] = np.where(
        df_lcoe['발전량_건물지붕_20년(Wh)'] == 0, np.nan,
        (parameter_dict['설치비_건물지붕(원/kW)'] + df_lcoe['운영비_건물지붕_20년(원/kW)'] + df_lcoe['토지임대료_20년(원/kW)']) * 1000 / df_lcoe['발전량_건물지붕_20년(Wh)']
    )
    
    df_lcoe['LCOE_영농형_20년(원/kWh)'] = np.where(
        df_lcoe['발전량_영농형_20년(Wh)'] == 0, np.nan,
        (parameter_dict['설치비_영농형_20년(원/kW)'] + parameter_dict['운영비_영농형_20년(원/kW/년)'] + df_lcoe['토지임대료_20년(원/kW)']) * 1000 / df_lcoe['발전량_영농형_20년(Wh)']
    )
    
    df_lcoe['LCOE_영농형_8년(원/kWh)'] = np.where(
        df_lcoe['발전량_영농형_8년(Wh)'] == 0, np.nan,
        (parameter_dict['설치비_영농형_8년(원/kW)'] + df_lcoe['운영비_영농형_8년(원/kW)'] + df_lcoe['토지임대료_8년(원/kW)']) * 1000 / df_lcoe['발전량_영농형_8년(Wh)']
    )
    
    df_lcoe['LCOE_영농형_23년(원/kWh)'] = np.where(
        df_lcoe['발전량_영농형_23년(Wh)'] == 0, np.nan,
        (parameter_dict['설치비_영농형_20년(원/kW)'] + df_lcoe['운영비_영농형_23년(원/kW)'] + df_lcoe['토지임대료_23년(원/kW)']) * 1000 / df_lcoe['발전량_영농형_23년(Wh)']
    )
    
    df_lcoe['LCOE_토지(원/kWh)'] = np.where(
        df_lcoe['발전량_토지_20년(Wh)'] == 0, np.nan,
        (parameter_dict['설치비_토지(원/kW)'] + df_lcoe['운영비_토지_20년(원/kW)'] + df_lcoe['토지임대료_20년(원/kW)']) * 1000 / df_lcoe['발전량_토지_20년(Wh)']
    )
    
    # 원본 df에 LCOE 컬럼 병합
    df = df.assign(**df_lcoe[['LCOE_수상형(원/kWh)', 'LCOE_건물지붕(원/kWh)', 
                             'LCOE_영농형_20년(원/kWh)', 'LCOE_영농형_8년(원/kWh)', 
                             'LCOE_영농형_23년(원/kWh)', 'LCOE_토지(원/kWh)']])
    ##### LOCE 관련 인자를 만들수없나??
    
    # 5. smp_rec_values 계산
    print("SMP/REC 값 계산 중...")
    # 임계값 사전 정의 (키 이름 수정 반영)
    smp_rec_values = {
        '건물지붕': parameter_dict['SMP_2024(원/kWh)'] + (parameter_dict['REC_2024(원/kWh)'] * parameter_dict['REC가중치_건물지붕']),
        '수상형': parameter_dict['SMP_2024(원/kWh)'] + (parameter_dict['REC_2024(원/kWh)'] * parameter_dict['REC가중치_수상형']),
        '토지': parameter_dict['SMP_2024(원/kWh)'] + (parameter_dict['REC_2024(원/kWh)'] * parameter_dict['REC가중치_토지']),
        '토지_고정가계약': parameter_dict['SMP_2023(원/kWh)_고정가계약'] + (parameter_dict['REC_2023(원/kWh)_고정가계약'] * parameter_dict['REC가중치_토지'])
    }    
    print(f"SMP/REC 값: {smp_rec_values}")


    # 6. 시나리오 실행 (이전 #5 단계 복구)
    print(f"시나리오 실행 중: {scenario_name}...")
    # run_scenario_with_facade 함수 호출. 
    # NOTE: df_lcoe 대신 df_scenario를 사용하도록 run_scenario_with_facade 내부 함수 수정이 필요함!
    df_result = run_scenario_with_facade(df, scenario_name)
    print(f"시나리오 {scenario_name} 실행 시간: {time.time() - start_time:.2f}초")


    # 7. 결과 출력 (Conditional)
    if print_summary:
        print("\n# 7. 시장잠재량 결과 요약 출력 중...")
        # df_result는 현재 실행된 시나리오 결과 (예: df27)입니다.
        print_market_potential_summary(df_result)
        
    
    # 8. 건물벽면 히스토그램 생성 (Conditional)
    if create_viz and 'LCOE_건물벽면(원/kWh)' in df.columns:
        print("\n# 8. 건물벽면 시각화 생성 중...")
        # LCOE/일사량/이용률 히스토그램은 LCOE가 병합된 원본 df를 사용
        
        # LCOE 히스토그램
        create_histogram(df, 'LCOE_건물벽면(원/kWh)', '건물벽면 태양광 LCOE 분포', 'LCOE (원/kWh)')
        # 벽면일사량 히스토그램
        create_histogram(df, '벽면일사량(kWh/m2/day)_filtered', '필터링된 벽면일사량 분포', '벽면일사량 (kWh/m²/day)')
        # 이용률 히스토그램
        create_histogram(df, 'CapacityFactor_건물벽면', '건물벽면 태양광 이용률 분포', '이용률')
        # 벽면면적-일사량 관계 그래프
        plot_wall_area_vs_irradiance(df)

    # 8-1. 지도 시각화 (Conditional)
    # visualiztion 모듈의 create_map_visualizations 함수 사용
    # viz=types 는 None으로 설정해둔 상태(visualizion)
    if create_map_viz:
        print("\n# 8-1. 지도 시각화 생성 중...")
        from visualization import create_map_visualizations
        create_map_visualizations(
            df=df_result,
            grid_shp_path="1. Raw Data/격자b_SGIS내륙정보.shp",
            raw_data_folder="1. Raw Data",
            output_base_folder="3. Image"
        )

    # 9. 지역별 집계 (Conditional)
    sido_summary = None
    sigungu_summary = None
    dong_summary = None
    if summarize_area:
        print("\n# 9. 지역별 집계 중...")
        # 현재 시나리오 결과인 df_result를 사용하여 집계
        sido_summary = summarize_by_sido(df_result)
        sigungu_summary = summarize_by_sigungu(df_result)
        dong_summary = summarize_by_dong(df_result)
        print("지역별 집계 완료 (시도/시군구/동별).")
        
    
# 10. 결과 저장 (CSV)
    print("\n# 10. 결과 CSV 저장 중...")
    
    # 📌 시나리오 결과 파일명 수정 로직 적용
    # 예: 'calc_reject_배제28종(...)' -> '시장잠재량연산결과_배제28종(...)'
    name_parts = scenario_name.split('_', 1)
    if len(name_parts) > 1:
        new_prefix = "시장잠재량연산결과"
        # 'calc_reject' 부분이 제거되고 '시장잠재량연산결과'가 추가됨
        result_filename_base = f"{new_prefix}_{name_parts[1]}" 
    else:
        # '_'가 없는 경우를 대비
        result_filename_base = f"시장잠재량연산결과_{scenario_name}"
        
    result_filename = f"{result_filename_base}_건물벽면포함.csv"
    
    # 최종 결과 df_result 저장 (save_result_csv 내부에서 성공 메시지 1회 출력됨)
    # save_result_csv(df_result, result_filename)
    # 테스트할대는 잠궛는데 다시 풀어주자 저장기능

    
    # 지역별 집계 결과 저장 (집계가 실행된 경우에만)
    # 시나리오명에서 'calc_reject_' 제거하여 파일명에 사용
    scenario_short = scenario_name.replace('calc_reject_', '')

    if sido_summary is not None:
        save_result_csv(sido_summary, f"시도별_집계결과_{scenario_short}_건물벽면포함.csv")

    if sigungu_summary is not None:
        save_result_csv(sigungu_summary, f"시군구별_집계결과_{scenario_short}_건물벽면포함.csv")

    if dong_summary is not None:
        save_result_csv(dong_summary, f"동별_집계결과_{scenario_short}_건물벽면포함.csv")


    end_time = time.time()
    print(f"총 소요 시간: {end_time - start_time:.2f}초")
    print("=== 시나리오 분석 완료! ===")

    # 11. 결과 반환
    if return_lcoe:
        # LCOE 컬럼 포함한 전체 데이터 반환
        return df_lcoe
    else:
        # 기본: 시장잠재량 결과만 반환
        return df_result
    
#%%
# 실행
# 시나리오 연산
# 기존 시나리오 컬럼명 중 하나를 인자로 전달
scenario_name = 'calc_reject_r_1_25_진흥구역_rail_orid_rdres'   #실조례안 도로주택 지상형
# scenario_name = 'calc_reject_r_1_25_진흥지역_rail_orid_rdres' #실조례안 도로주택 영농혈
# scenario_name = 'calc_reject_r_1_26_rail_rd100_res200'       #도로,주택 조례안기준 상한선 적용 
# scenario_name = 'calc_reject_r_1_26_rail_rd200_res300'       #도로,주택 조례안기준 상한선 적용 



# df_result = main(scenario_name)  # main 함수 실행
df_result = main(scenario_name, summarize_area=True)
# df_result = main(scenario_name, print_summary=True, create_viz=True, create_map_viz=True,summarize_area=True)
    # print_summary: 시장잠재량 결과 요약 출력 여부. (7번)
    # create_viz: 건물벽면 시각화 생성 여부. (8번)
    # create_map_viz: 지도 시각화 생성 및 3. Image 폴더 저장 여부. (8-1번)
    # summarize_area: 시도/시군구별/동별 집계 실행 여부. (9번)
print(df_result.head()) # 결과 DataFrame 확인

# 7번 출력 별도 확인용
# summary_df = print_market_potential_summary(df_result, return_df=True)
# summary_df





#%%
def summarize_market_potential(df):
    """
    시장잠재량 연도별 설비용량(GW) / 발전량(TWh/년) 합계를 표로 만들어주는 함수
    df : 입력 데이터프레임
    """
    # 합계 계산
    sum_8_gw  = df['시장잠재량_영농형_8년_설비용량(GW)'].sum()

    sum_20_gw = df['시장잠재량_영농형_20년_설비용량(GW)'].sum()
    sum_23_gw = df['시장잠재량_영농형_23년_설비용량(GW)'].sum()

    sum_8_twh  = df['시장잠재량_영농형_8년_발전량(TWh/년)'].sum()
    sum_20_twh = df['시장잠재량_영농형_20년_발전량(TWh/년)'].sum()
    sum_23_twh = df['시장잠재량_영농형_23년_발전량(TWh/년)'].sum()

    # 표로 정리
    df_summary = pd.DataFrame({
        '구분': [ '시장 잠재량(8년)','시장 잠재량(20년)','시장 잠재량(23년)'],
        '설비용량(GW)': [ sum_8_gw, sum_20_gw, sum_23_gw],
        '발전량(TWh/년)': [sum_8_twh, sum_20_twh , sum_23_twh]
    })
    # 보기 좋게 반올림
    df_summary = df_summary.round(2)
    return df_summary
result = summarize_market_potential(df_result)
result
#%%


