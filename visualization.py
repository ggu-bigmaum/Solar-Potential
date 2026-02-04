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

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


# =============================================================================
# 1. 공간 데이터 로드 함수
# =============================================================================

def load_spatial_data(grid_shp_path, raw_data_folder="1. Raw Data"):
    """
    공간 데이터(격자, 시도/시군구/동 경계, 1km격자) 로드

    Parameters:
        grid_shp_path: 100m 격자 shp 파일 경로
        raw_data_folder: 경계 파일이 있는 폴더

    Returns:
        dict: gdf(100m격자), boundary_*, grid_1km, id_key_mapping
    """
    print("공간 데이터 로드 시작...")
    start = time.time()

    # 100m 격자 데이터
    gdf = gpd.read_file(grid_shp_path)[['id', 'geometry']]
    gdf = gdf.to_crs(epsg=32652)

    # 시군구 경계
    boundary_sigungu = gpd.read_file(
        os.path.join(raw_data_folder, 'bnd_sigungu_00_2024_2Q.gpkg')
    ).to_crs(epsg=32652)

    # 시도 경계
    boundary_sido = gpd.read_file(
        os.path.join(raw_data_folder, 'bnd_sido_00_2024_2Q.gpkg')
    ).to_crs(epsg=32652)

    # 동 경계
    boundary_dong = gpd.read_file(
        os.path.join(raw_data_folder, 'bnd_dong_00_2024_2Q.gpkg')
    ).to_crs(epsg=32652)

    # 1km 격자 데이터 (gpkg)
    grid_1km_raw = gpd.read_file(
        os.path.join(raw_data_folder, 'a0000000a.gpkg')
    )
    print(f"  - 1km gpkg 원본 좌표계: {grid_1km_raw.crs}")
    print(f"  - 1km gpkg 컬럼: {list(grid_1km_raw.columns)}")
    grid_1km = grid_1km_raw[['Id', 'geometry']].copy()
    grid_1km = grid_1km.to_crs(epsg=32652)
    grid_1km = grid_1km.rename(columns={'Id': 'grid_1km_id'})

    # 100m-1km ID 매핑 테이블
    id_key_mapping = pd.read_csv(
        os.path.join(raw_data_folder, 'id_key_202601291842.csv')
    )

    # ID 형식 진단
    print(f"  - 1km gpkg Id 샘플: {grid_1km['grid_1km_id'].head(3).tolist()}")
    print(f"  - 매핑 테이블 grid_1km_id 샘플: {id_key_mapping['grid_1km_id'].head(3).tolist()}")
    print(f"  - 매핑 테이블 컬럼: {list(id_key_mapping.columns)}")

    print(f"공간 데이터 로드 완료: {time.time() - start:.2f}초")
    print(f"  - 100m 격자: {len(gdf):,}개")
    print(f"  - 1km 격자: {len(grid_1km):,}개")
    print(f"  - ID 매핑: {len(id_key_mapping):,}개")

    return {
        'gdf': gdf,
        'boundary_sido': boundary_sido,
        'boundary_sigungu': boundary_sigungu,
        'boundary_dong': boundary_dong,
        'grid_1km': grid_1km,
        'id_key_mapping': id_key_mapping
    }


def prepare_visualization_data(df, spatial_data):
    """
    시각화를 위한 데이터 준비 (병합 및 집계)

    Parameters:
        df: 시장잠재량 결과 DataFrame (id 컬럼 필요)
        spatial_data: load_spatial_data()의 반환값

    Returns:
        dict: df_with_geo, grid_1km_map, sido_map, sigungu_map, dong_map, capacity_cols
    """
    print("시각화 데이터 준비 중...")
    start = time.time()

    gdf = spatial_data['gdf']
    grid_1km = spatial_data['grid_1km']
    id_key_mapping = spatial_data['id_key_mapping']

    # 설비용량 컬럼 추출
    capacity_cols = [col for col in df.columns if '설비용량' in col]
    print(f"  시각화 대상 컬럼: {len(capacity_cols)}개")

    # =========================================================================
    # 1km 격자 시각화용 데이터 준비 (최적화)
    # =========================================================================
    print("  1km 격자 집계 중...")

    # 100m 결과 + 매핑 테이블 조인
    print(f"    - 원본 df 행 수: {len(df):,}개")
    print(f"    - ID 매핑 테이블 행 수: {len(id_key_mapping):,}개")

    df_with_1km = df.merge(
        id_key_mapping,
        left_on='id',
        right_on='grid_100m_id',
        how='inner'
    )
    print(f"    - 매핑 후 행 수: {len(df_with_1km):,}개 (손실: {len(df) - len(df_with_1km):,}개)")

    # 1km 격자 기준 집계 (합계)
    df_1km_agg = df_with_1km.groupby('grid_1km_id')[capacity_cols].sum().reset_index()
    print(f"    - 1km 집계 후: {len(df_1km_agg):,}개 고유 1km 격자")

    # 0값 → NaN (0인 격자는 지도에 표시 안 함)
    nonzero_before = (df_1km_agg[capacity_cols[0]] > 0).sum() if capacity_cols else 0
    df_1km_agg = df_1km_agg.replace(0, np.nan)
    print(f"    - 유효값(>0) 격자: {nonzero_before:,}개")

    # 1km geometry와 조인 (폴리곤 생성 불필요!)
    print(f"    - 1km gpkg 격자 수: {len(grid_1km):,}개")
    grid_1km_map = grid_1km.merge(df_1km_agg, on='grid_1km_id', how='inner')

    print(f"    → 1km 격자 집계 완료: {len(grid_1km_map):,}개 (geometry 매칭)")

    # =========================================================================
    # 시도/시군구/동 시각화용 데이터 준비
    # =========================================================================
    print("  시도/시군구/동 집계 중...")

    # 100m 격자와 결과 데이터 병합 (geometry 포함)
    df_with_geo = gdf.merge(df, on='id', how='inner')

    # 시도별 집계
    sido_col = 'SIDO_NM' if 'SIDO_NM' in df.columns else 'sido_nm'
    if sido_col in df.columns:
        df_sido_sum = df.groupby(sido_col)[capacity_cols].sum().reset_index()
        sido_map = spatial_data['boundary_sido'].merge(
            df_sido_sum, left_on='SIDO_NM', right_on=sido_col, how='left'
        )
        print(f"    - 시도별: '{sido_col}' 컬럼 사용, {len(df_sido_sum)}개 시도 집계")
    else:
        sido_map = spatial_data['boundary_sido'].copy()
        print(f"    - 시도별: 컬럼 없음 (SIDO_NM/sido_nm)")

    # 시군구별 집계
    sigungu_col = 'SIGUNGU_NM' if 'SIGUNGU_NM' in df.columns else 'sigungu_nm'
    if sigungu_col in df.columns:
        df_sigungu_sum = df.groupby(sigungu_col)[capacity_cols].sum().reset_index()
        sigungu_map = spatial_data['boundary_sigungu'].merge(
            df_sigungu_sum, left_on='SIGUNGU_NM', right_on=sigungu_col, how='left'
        )
        print(f"    - 시군구별: '{sigungu_col}' 컬럼 사용, {len(df_sigungu_sum)}개 시군구 집계")
    else:
        sigungu_map = spatial_data['boundary_sigungu'].copy()
        print(f"    - 시군구별: 컬럼 없음 (SIGUNGU_NM/sigungu_nm)")

    # 동별 집계
    adm_col = 'ADM_NM' if 'ADM_NM' in df.columns else 'adm_nm'
    if adm_col in df.columns:
        df_dong_sum = df.groupby(adm_col)[capacity_cols].sum().reset_index()
        dong_map = spatial_data['boundary_dong'].merge(
            df_dong_sum, left_on='ADM_NM', right_on=adm_col, how='left'
        )
        print(f"    - 동별: '{adm_col}' 컬럼 사용, {len(df_dong_sum)}개 동 집계")
    else:
        dong_map = spatial_data['boundary_dong'].copy()
        print(f"    - 동별: 컬럼 없음 (ADM_NM/adm_nm)")

    print(f"시각화 데이터 준비 완료: {time.time() - start:.2f}초")
    print(f"시각화 대상 컬럼 수: {len(capacity_cols)}개")

    return {
        'df_with_geo': df_with_geo,
        'grid_1km_map': grid_1km_map,
        'sido_map': sido_map,
        'sigungu_map': sigungu_map,
        'dong_map': dong_map,
        'capacity_cols': capacity_cols
    }


# =============================================================================
# 2. 개별 시각화 함수
# =============================================================================

def plot_1km_grid(grid_1km_map, target_col, boundary_sigungu, output_folder, k=10):
    """1km 격자 단위 시각화 (등분 방식, NaN은 흰색)"""
    from matplotlib.patches import Patch

    gdf = grid_1km_map.copy()
    total_grids = len(gdf)
    nan_count = gdf[target_col].isna().sum()
    valid_count = total_grids - nan_count

    print(f"\n    [진단] 전체: {total_grids:,}개, NaN: {nan_count:,}개, 유효: {valid_count:,}개")

    cmap = plt.cm.YlOrRd
    fig, ax = plt.subplots(figsize=(12, 10))

    if valid_count > 0:
        # 유효값의 최소/최대로 등분 계산
        valid_mask = gdf[target_col].notna()
        valid_values = gdf.loc[valid_mask, target_col]
        vmin, vmax = valid_values.min(), valid_values.max()

        # vmin == vmax인 경우 (모든 값이 동일) 처리
        if vmin == vmax:
            # 단일 값: 모두 같은 색상으로 표시
            colors = np.ones((len(gdf), 4))  # 기본 흰색
            colors[valid_mask.values] = cmap(0.5)  # 유효값은 중간 색상
            gdf.plot(ax=ax, color=colors, linewidth=0, rasterized=True)
            legend_patches = [
                Patch(facecolor=cmap(0.5), label=f'{vmin:.4f} (단일값)'),
                Patch(facecolor='white', edgecolor='gray', label='결측값')
            ]
            ax.legend(handles=legend_patches, loc='lower right', fontsize=8)
        else:
            bins = np.linspace(vmin, vmax, k + 1)
            actual_k = k

            # 전체 데이터에 등분 클래스 할당
            gdf['_class'] = pd.cut(
                gdf[target_col], bins=bins, labels=False, include_lowest=True
            )

            # 색상 매핑: NaN은 흰색, 유효값은 colormap (RGBA 배열)
            colors = np.ones((len(gdf), 4))  # 기본값 흰색 (1,1,1,1)
            for i in range(actual_k):
                mask = (gdf['_class'] == i).values
                colors[mask] = cmap(i / (actual_k - 1) if actual_k > 1 else 0)

            # 시각화
            gdf.plot(ax=ax, color=colors, linewidth=0, rasterized=True)

            # 범례
            legend_patches = [
                Patch(facecolor=cmap(i / (actual_k - 1) if actual_k > 1 else 0),
                      label=f'{bins[i]:.4f}  ~  {bins[i+1]:.4f}')
                for i in range(actual_k)
            ]
            legend_patches.append(Patch(facecolor='white', edgecolor='gray', label='결측값'))
            ax.legend(handles=legend_patches, loc='lower right', fontsize=8)
    else:
        # 유효 데이터 없음 - 모두 흰색
        gdf.plot(ax=ax, color='white', edgecolor='lightgrey', linewidth=0.1, rasterized=True)
        ax.legend(handles=[Patch(facecolor='white', edgecolor='gray', label='결측값')],
                  loc='lower right', fontsize=8)

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


def plot_sido_map(sido_map, target_col, output_folder, k=10):
    """시도별 합계 시각화 (등분 범례, NaN은 흰색)"""
    from matplotlib.patches import Patch

    gdf = sido_map.copy()
    valid_count = gdf[target_col].notna().sum()

    cmap = plt.cm.YlOrRd
    fig, ax = plt.subplots(figsize=(8, 8))

    if valid_count > 0:
        # 유효값의 최소/최대로 등분 계산
        valid_values = gdf.loc[gdf[target_col].notna(), target_col]
        valid_mask = gdf[target_col].notna()
        vmin, vmax = valid_values.min(), valid_values.max()

        # vmin == vmax인 경우 (모든 값이 동일) 처리
        if vmin == vmax:
            colors = np.ones((len(gdf), 4))
            colors[valid_mask.values] = cmap(0.5)
            gdf.plot(ax=ax, color=colors, edgecolor='white', linewidth=0.5)
            legend_patches = [
                Patch(facecolor=cmap(0.5), label=f'{vmin:.4f} (단일값)'),
                Patch(facecolor='white', edgecolor='gray', label='결측값')
            ]
            ax.legend(handles=legend_patches, loc='lower right', fontsize=8)
        else:
            bins = np.linspace(vmin, vmax, k + 1)
            actual_k = k

            # 전체 데이터에 등분 클래스 할당
            gdf['_class'] = pd.cut(
                gdf[target_col], bins=bins, labels=False, include_lowest=True
            )

            # 색상 매핑
            colors = np.ones((len(gdf), 4))
            for i in range(actual_k):
                mask = (gdf['_class'] == i).values
                colors[mask] = cmap(i / (actual_k - 1) if actual_k > 1 else 0)

            gdf.plot(ax=ax, color=colors, edgecolor='white', linewidth=0.5)

            # 범례
            legend_patches = [
                Patch(facecolor=cmap(i / (actual_k - 1) if actual_k > 1 else 0),
                      label=f'{bins[i]:.4f}  ~  {bins[i+1]:.4f}')
                for i in range(actual_k)
            ]
            legend_patches.append(Patch(facecolor='white', edgecolor='gray', label='결측값'))
            ax.legend(handles=legend_patches, loc='lower right', fontsize=8)
    else:
        gdf.plot(ax=ax, color='white', edgecolor='lightgrey', linewidth=0.5)
        ax.legend(handles=[Patch(facecolor='white', edgecolor='gray', label='결측값')],
                  loc='lower right', fontsize=8)

    ax.set_title(f"{target_col}", fontsize=13)
    ax.axis('off')
    plt.tight_layout()

    # 저장
    safe_name = target_col.replace('/', '_').replace('\\', '_')
    filepath = os.path.join(output_folder, f"시도별합계_{safe_name}.png")
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


def plot_sigungu_map(sigungu_map, target_col, output_folder, k=10):
    """시군구별 합계 시각화 (등분 범례, NaN은 흰색)"""
    from matplotlib.patches import Patch

    gdf = sigungu_map.copy()
    valid_count = gdf[target_col].notna().sum()

    cmap = plt.cm.YlOrRd
    fig, ax = plt.subplots(figsize=(10, 10))

    if valid_count > 0:
        # 유효값의 최소/최대로 등분 계산
        valid_values = gdf.loc[gdf[target_col].notna(), target_col]
        valid_mask = gdf[target_col].notna()
        vmin, vmax = valid_values.min(), valid_values.max()

        # vmin == vmax인 경우 (모든 값이 동일) 처리
        if vmin == vmax:
            colors = np.ones((len(gdf), 4))
            colors[valid_mask.values] = cmap(0.5)
            gdf.plot(ax=ax, color=colors, edgecolor='white', linewidth=0.3)
            legend_patches = [
                Patch(facecolor=cmap(0.5), label=f'{vmin:.4f} (단일값)'),
                Patch(facecolor='white', edgecolor='gray', label='결측값')
            ]
            ax.legend(handles=legend_patches, loc='lower right', fontsize=8)
        else:
            bins = np.linspace(vmin, vmax, k + 1)
            actual_k = k

            # 전체 데이터에 등분 클래스 할당
            gdf['_class'] = pd.cut(
                gdf[target_col], bins=bins, labels=False, include_lowest=True
            )

            # 색상 매핑
            colors = np.ones((len(gdf), 4))
            for i in range(actual_k):
                mask = (gdf['_class'] == i).values
                colors[mask] = cmap(i / (actual_k - 1) if actual_k > 1 else 0)

            gdf.plot(ax=ax, color=colors, edgecolor='white', linewidth=0.3)

            # 범례
            legend_patches = [
                Patch(facecolor=cmap(i / (actual_k - 1) if actual_k > 1 else 0),
                      label=f'{bins[i]:.4f}  ~  {bins[i+1]:.4f}')
                for i in range(actual_k)
            ]
            legend_patches.append(Patch(facecolor='white', edgecolor='gray', label='결측값'))
            ax.legend(handles=legend_patches, loc='lower right', fontsize=8)
    else:
        gdf.plot(ax=ax, color='white', edgecolor='lightgrey', linewidth=0.3)
        ax.legend(handles=[Patch(facecolor='white', edgecolor='gray', label='결측값')],
                  loc='lower right', fontsize=8)

    ax.set_title(f"{target_col}", fontsize=13)
    ax.axis('off')
    plt.tight_layout()

    # 저장
    safe_name = target_col.replace('/', '_').replace('\\', '_')
    filepath = os.path.join(output_folder, f"시군구별합계_{safe_name}.png")
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()

    return filepath


def plot_dong_map(dong_map, target_col, output_folder, k=10):
    """동별 합계 시각화 (등분 범례, NaN은 흰색)"""
    from matplotlib.patches import Patch

    gdf = dong_map.copy()
    valid_count = gdf[target_col].notna().sum()

    cmap = plt.cm.YlOrRd
    fig, ax = plt.subplots(figsize=(12, 10))

    if valid_count > 0:
        # 유효값의 최소/최대로 등분 계산
        valid_values = gdf.loc[gdf[target_col].notna(), target_col]
        valid_mask = gdf[target_col].notna()
        vmin, vmax = valid_values.min(), valid_values.max()

        # vmin == vmax인 경우 (모든 값이 동일) 처리
        if vmin == vmax:
            colors = np.ones((len(gdf), 4))
            colors[valid_mask.values] = cmap(0.5)
            gdf.plot(ax=ax, color=colors, edgecolor='gray', linewidth=0.1)
            legend_patches = [
                Patch(facecolor=cmap(0.5), label=f'{vmin:.4f} (단일값)'),
                Patch(facecolor='white', edgecolor='gray', label='결측값')
            ]
            ax.legend(handles=legend_patches, loc='lower right', fontsize=8)
        else:
            bins = np.linspace(vmin, vmax, k + 1)
            actual_k = k

            # 전체 데이터에 등분 클래스 할당
            gdf['_class'] = pd.cut(
                gdf[target_col], bins=bins, labels=False, include_lowest=True
            )

            # 색상 매핑
            colors = np.ones((len(gdf), 4))
            for i in range(actual_k):
                mask = (gdf['_class'] == i).values
                colors[mask] = cmap(i / (actual_k - 1) if actual_k > 1 else 0)

            gdf.plot(ax=ax, color=colors, edgecolor='gray', linewidth=0.1)

            # 범례
            legend_patches = [
                Patch(facecolor=cmap(i / (actual_k - 1) if actual_k > 1 else 0),
                      label=f'{bins[i]:.4f}  ~  {bins[i+1]:.4f}')
                for i in range(actual_k)
            ]
            legend_patches.append(Patch(facecolor='white', edgecolor='gray', label='결측값'))
            ax.legend(handles=legend_patches, loc='lower right', fontsize=8)
    else:
        gdf.plot(ax=ax, color='white', edgecolor='gray', linewidth=0.1)
        ax.legend(handles=[Patch(facecolor='white', edgecolor='gray', label='결측값')],
                  loc='lower right', fontsize=8)

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
    viz_types=None,
    test_mode=False  # 테스트 모드: 각 유형별 1개만 생성
):
    """
    전체 지도 시각화 실행 및 이미지 저장

    Parameters:
        df: 시장잠재량 결과 DataFrame (id 컬럼 필요)
        grid_shp_path: 100m 격자 shp 파일 경로
        raw_data_folder: 경계 파일이 있는 폴더 경로
        output_base_folder: 이미지 저장 기본 폴더 (기본값: "3. Image")
        viz_types: 시각화 유형 리스트 (기본값: 전체)
                   ['1km격자', '시도별', '시군구별', '동별'] 중 선택
        test_mode: True이면 각 유형별 첫 번째 컬럼만 시각화 (기본값: False)

    Returns:
        dict: 각 시각화 유형별 저장된 파일 경로 리스트
    """

    if viz_types is None:
        viz_types = ['1km격자', '시도별', '시군구별', '동별']

    print("\n" + "="*60)
    print("지도 시각화 시작" + (" [테스트 모드]" if test_mode else ""))
    print("="*60)

    total_start = time.time()

    # 1. 공간 데이터 로드 (1km 격자 포함)
    spatial_data = load_spatial_data(grid_shp_path, raw_data_folder)

    # 2. 시각화 데이터 준비
    viz_data = prepare_visualization_data(df, spatial_data)

    capacity_cols = viz_data['capacity_cols']

    # 테스트 모드: 첫 번째 컬럼만 사용
    if test_mode:
        capacity_cols = capacity_cols[:1]
        print(f"  [테스트 모드] 대상 컬럼: {capacity_cols}")

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
                viz_data['grid_1km_map'],
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
