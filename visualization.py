"""
visualization.py
지도 시각화 모듈 - 태양광 시장잠재량 결과를 지도로 시각화하고 이미지로 저장

사용법:
    from visualization import create_map_visualizations
    create_map_visualizations(df, grid_shp_path, output_base_folder="3. Image")
"""

import os
import time
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import box

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


# =============================================================================
# 1. 공간 데이터 로드 함수
# =============================================================================

def load_spatial_data(grid_shp_path, raw_data_folder="1. Raw Data"):
    """
    공간 데이터(격자, 시도/시군구/동 경계) 로드

    Parameters:
        grid_shp_path: 격자 shp 파일 경로
        raw_data_folder: 경계 파일이 있는 폴더

    Returns:
        dict: gdf(격자), boundary_sido, boundary_sigungu, boundary_dong
    """
    print("공간 데이터 로드 시작...")
    start = time.time()

    # 격자 데이터
    gdf = gpd.read_file(grid_shp_path)[['id', 'geometry']]
    gdf = gdf.to_crs(epsg=3857)

    # 시군구 경계
    boundary_sigungu = gpd.read_file(
        os.path.join(raw_data_folder, 'bnd_sigungu_00_2023_2Q.shp')
    ).to_crs(epsg=3857)

    # 시도 경계
    boundary_sido = gpd.read_file(
        os.path.join(raw_data_folder, 'bnd_sido_00_2023_2Q.shp')
    ).to_crs(epsg=3857)

    # 동 경계
    boundary_dong = gpd.read_file(
        os.path.join(raw_data_folder, 'bnd_dong_00_2023_2Q.shp')
    ).to_crs(epsg=3857)

    print(f"공간 데이터 로드 완료: {time.time() - start:.2f}초")

    return {
        'gdf': gdf,
        'boundary_sido': boundary_sido,
        'boundary_sigungu': boundary_sigungu,
        'boundary_dong': boundary_dong
    }


def prepare_visualization_data(df, gdf, spatial_data):
    """
    시각화를 위한 데이터 준비 (병합 및 좌표 계산)

    Parameters:
        df: 시장잠재량 결과 DataFrame (id 컬럼 필요)
        gdf: 격자 GeoDataFrame
        spatial_data: load_spatial_data()의 반환값

    Returns:
        dict: df_3857, sido_map, sigungu_map, dong_map, capacity_cols
    """
    print("시각화 데이터 준비 중...")
    start = time.time()

    # 격자와 결과 데이터 병합
    df_3857 = gdf.merge(df, on='id', how='inner')

    # 설비용량 컬럼 추출
    capacity_cols = [col for col in df_3857.columns if '설비용량' in col]

    # 빈 행 제거
    exclude_cols = ['id', 'geometry', 'SIDO_NM', 'SIGUNGU_NM', 'ADM_NM']
    data_cols = [col for col in df_3857.columns if col not in exclude_cols]
    df_3857 = df_3857.dropna(subset=[c for c in data_cols if c in df_3857.columns], how='all')

    # 1km 격자 좌표 생성 (1km격자 시각화용)
    df_3857['centroid'] = df_3857.geometry.centroid
    df_3857['x'] = df_3857['centroid'].x
    df_3857['y'] = df_3857['centroid'].y
    df_3857['x_1km'] = (df_3857['x'] // 1000).astype(int)
    df_3857['y_1km'] = (df_3857['y'] // 1000).astype(int)

    # 시도별 집계
    sido_col = 'SIDO_NM' if 'SIDO_NM' in df_3857.columns else 'sido_nm'
    df_sido_sum = df_3857.groupby(sido_col)[capacity_cols].sum().reset_index()
    sido_map = spatial_data['boundary_sido'].merge(
        df_sido_sum, left_on='SIDO_NM', right_on=sido_col, how='left'
    )

    # 시군구별 집계
    sigungu_col = 'SIGUNGU_NM' if 'SIGUNGU_NM' in df_3857.columns else 'sigungu_nm'
    df_sigungu_sum = df_3857.groupby(sigungu_col)[capacity_cols].sum().reset_index()
    sigungu_map = spatial_data['boundary_sigungu'].merge(
        df_sigungu_sum, left_on='SIGUNGU_NM', right_on=sigungu_col, how='left'
    )

    # 동별 집계
    adm_col = 'ADM_NM' if 'ADM_NM' in df_3857.columns else 'adm_nm'
    df_dong_sum = df_3857.groupby(adm_col)[capacity_cols].sum().reset_index()
    dong_map = spatial_data['boundary_dong'].merge(
        df_dong_sum, left_on='ADM_NM', right_on=adm_col, how='left'
    )

    print(f"시각화 데이터 준비 완료: {time.time() - start:.2f}초")
    print(f"시각화 대상 컬럼 수: {len(capacity_cols)}개")

    return {
        'df_3857': df_3857,
        'sido_map': sido_map,
        'sigungu_map': sigungu_map,
        'dong_map': dong_map,
        'capacity_cols': capacity_cols
    }


# =============================================================================
# 2. 개별 시각화 함수
# =============================================================================

def plot_1km_grid(df_3857, target_col, boundary_sigungu, output_folder):
    """1km 격자 단위 시각화"""

    # 격자 단위 집계 (합계 기준)
    agg_df = df_3857.groupby(['x_1km', 'y_1km'])[target_col].sum().reset_index()
    agg_df = agg_df.replace(0, np.nan)

    # 격자 Polygon 생성
    def create_grid_polygon(row):
        x, y = row['x_1km'] * 1000, row['y_1km'] * 1000
        return box(x, y, x + 1000, y + 1000)

    agg_df['geometry'] = agg_df.apply(create_grid_polygon, axis=1)

    # GeoDataFrame 생성
    agg_gdf = gpd.GeoDataFrame(agg_df, geometry='geometry', crs='EPSG:3857')

    # 시각화
    fig, ax = plt.subplots(figsize=(12, 10))

    agg_gdf.plot(
        column=target_col,
        ax=ax,
        cmap='YlOrRd',
        alpha=0.6,
        scheme='quantiles',
        k=20,
        legend=True,
        legend_kwds={
            'loc': 'lower right',
            'fontsize': 8
        },
        missing_kwds={
            'color': '#ffffff',
            'edgecolor': None,
            'label': '결측값'
        }
    )

    boundary_sigungu.boundary.plot(ax=ax, color='lightgrey', linewidth=0.5)

    ax.set_title(f"{target_col} (1km 전국 격자)", fontsize=15)
    ax.axis('off')
    plt.tight_layout()

    # 저장
    safe_name = target_col.replace('/', '_').replace('\\', '_')
    filepath = os.path.join(output_folder, f"격자별분포_{safe_name}.png")
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


def plot_sido_map(sido_map, target_col, output_folder):
    """시도별 합계 시각화"""

    gdf_filtered = sido_map.dropna(subset=[target_col])
    if gdf_filtered.empty:
        print(f"  {target_col} - 유효 데이터 없음. 건너뜀.")
        return None

    fig, ax = plt.subplots(figsize=(8, 8))
    gdf_filtered.plot(
        column=target_col,
        ax=ax,
        cmap='YlOrRd',
        alpha=0.6,
        scheme='quantiles',
        k=20,
        edgecolor='white',
        linewidth=0.5,
        legend=True,
        legend_kwds={
            'loc': 'lower right',
            'fontsize': 8
        },
        missing_kwds={
            'color': '#ffffff',
            'edgecolor': None,
            'label': '결측값'
        }
    )

    ax.set_title(f"{target_col}", fontsize=13)
    ax.axis('off')
    plt.tight_layout()

    # 저장
    safe_name = target_col.replace('/', '_').replace('\\', '_')
    filepath = os.path.join(output_folder, f"시도별합계_{safe_name}.png")
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


def plot_sigungu_map(sigungu_map, target_col, output_folder):
    """시군구별 합계 시각화"""

    gdf_filtered = sigungu_map.dropna(subset=[target_col])
    if gdf_filtered.empty:
        print(f"  {target_col} - 유효 데이터 없음. 건너뜀.")
        return None

    fig, ax = plt.subplots(figsize=(10, 10))
    gdf_filtered.plot(
        column=target_col,
        ax=ax,
        cmap='YlOrRd',
        alpha=0.6,
        scheme='quantiles',
        k=20,
        edgecolor='white',
        linewidth=0.3,
        legend=True,
        legend_kwds={
            'loc': 'lower right',
            'fontsize': 8
        },
        missing_kwds={
            'color': '#ffffff',
            'edgecolor': None,
            'label': '결측값'
        }
    )

    ax.set_title(f"{target_col}", fontsize=13)
    ax.axis('off')
    plt.tight_layout()

    # 저장
    safe_name = target_col.replace('/', '_').replace('\\', '_')
    filepath = os.path.join(output_folder, f"시군구별합계_{safe_name}.png")
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


def plot_dong_map(dong_map, target_col, output_folder):
    """동별 합계 시각화"""

    gdf_filtered = dong_map.dropna(subset=[target_col])
    if gdf_filtered.empty:
        print(f"  {target_col} - 유효 데이터 없음. 건너뜀.")
        return None

    fig, ax = plt.subplots(figsize=(12, 10))
    gdf_filtered.plot(
        column=target_col,
        ax=ax,
        cmap='YlOrRd',
        alpha=0.6,
        scheme='quantiles',
        k=20,
        edgecolor='white',
        linewidth=0.1,
        legend=True,
        legend_kwds={
            'loc': 'lower right',
            'fontsize': 8
        },
        missing_kwds={
            'color': '#ffffff',
            'edgecolor': None,
            'label': '결측값'
        }
    )

    ax.set_title(f"{target_col} (동 단위)", fontsize=13)
    ax.axis('off')
    plt.tight_layout()

    # 저장
    safe_name = target_col.replace('/', '_').replace('\\', '_')
    filepath = os.path.join(output_folder, f"동별합계_{safe_name}.png")
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


# =============================================================================
# 3. 메인 시각화 함수 (test1.py에서 호출)
# =============================================================================

def create_map_visualizations(
    df,
    grid_shp_path="1. Raw Data/격자b_SGIS내륙정보.shp",
    raw_data_folder="1. Raw Data",
    output_base_folder="3. Image",
    viz_types=None
):
    """
    전체 지도 시각화 실행 및 이미지 저장

    Parameters:
        df: 시장잠재량 결과 DataFrame (id 컬럼 필요)
        grid_shp_path: 격자 shp 파일 경로
        raw_data_folder: 경계 파일이 있는 폴더 경로
        output_base_folder: 이미지 저장 기본 폴더 (기본값: "3. Image")
        viz_types: 시각화 유형 리스트 (기본값: 전체)
                   ['1km격자', '시도별', '시군구별', '동별'] 중 선택

    Returns:
        dict: 각 시각화 유형별 저장된 파일 경로 리스트
    """

    if viz_types is None:
        viz_types = ['1km격자', '시도별', '시군구별', '동별']

    print("\n" + "="*60)
    print("지도 시각화 시작")
    print("="*60)

    total_start = time.time()

    # 1. 공간 데이터 로드
    spatial_data = load_spatial_data(grid_shp_path, raw_data_folder)

    # 2. 시각화 데이터 준비
    viz_data = prepare_visualization_data(df, spatial_data['gdf'], spatial_data)

    capacity_cols = viz_data['capacity_cols']
    results = {}

    # 3. 1km 격자 시각화
    if '1km격자' in viz_types:
        print("\n[1km격자 시각화]")
        output_folder = os.path.join(output_base_folder, "1km격자")
        os.makedirs(output_folder, exist_ok=True)

        results['1km격자'] = []
        for i, target_col in enumerate(capacity_cols, 1):
            start = time.time()
            print(f"  ({i}/{len(capacity_cols)}) {target_col}...", end=" ")

            filepath = plot_1km_grid(
                viz_data['df_3857'],
                target_col,
                spatial_data['boundary_sigungu'],
                output_folder
            )
            results['1km격자'].append(filepath)
            print(f"{time.time() - start:.1f}초")

    # 4. 시도별 시각화
    if '시도별' in viz_types:
        print("\n[시도별 시각화]")
        output_folder = os.path.join(output_base_folder, "시도별")
        os.makedirs(output_folder, exist_ok=True)

        results['시도별'] = []
        for i, target_col in enumerate(capacity_cols, 1):
            start = time.time()
            print(f"  ({i}/{len(capacity_cols)}) {target_col}...", end=" ")

            filepath = plot_sido_map(viz_data['sido_map'], target_col, output_folder)
            if filepath:
                results['시도별'].append(filepath)
            print(f"{time.time() - start:.1f}초")

    # 5. 시군구별 시각화
    if '시군구별' in viz_types:
        print("\n[시군구별 시각화]")
        output_folder = os.path.join(output_base_folder, "시군구별")
        os.makedirs(output_folder, exist_ok=True)

        results['시군구별'] = []
        for i, target_col in enumerate(capacity_cols, 1):
            start = time.time()
            print(f"  ({i}/{len(capacity_cols)}) {target_col}...", end=" ")

            filepath = plot_sigungu_map(viz_data['sigungu_map'], target_col, output_folder)
            if filepath:
                results['시군구별'].append(filepath)
            print(f"{time.time() - start:.1f}초")

    # 6. 동별 시각화
    if '동별' in viz_types:
        print("\n[동별 시각화]")
        output_folder = os.path.join(output_base_folder, "동별")
        os.makedirs(output_folder, exist_ok=True)

        results['동별'] = []
        for i, target_col in enumerate(capacity_cols, 1):
            start = time.time()
            print(f"  ({i}/{len(capacity_cols)}) {target_col}...", end=" ")

            filepath = plot_dong_map(viz_data['dong_map'], target_col, output_folder)
            if filepath:
                results['동별'].append(filepath)
            print(f"{time.time() - start:.1f}초")

    # 완료 메시지
    total_time = time.time() - total_start
    total_images = sum(len(v) for v in results.values())

    print("\n" + "="*60)
    print(f"지도 시각화 완료!")
    print(f"총 소요 시간: {total_time:.1f}초")
    print(f"생성된 이미지: {total_images}개")
    print(f"저장 위치: {output_base_folder}/")
    print("="*60)

    return results


# =============================================================================
# 테스트용 실행
# =============================================================================

if __name__ == "__main__":
    print("visualization.py - 단독 실행 테스트")
    print("test1.py의 main() 함수에서 create_map_visualizations()를 호출하세요.")
