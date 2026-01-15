# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

대한민국 전역의 태양광 설치 가능 용량을 계산하는 대규모 지리공간 데이터 분석 시스템입니다. 기술적, 규제적, 경제적 제약을 고려하여 여러 태양광 설치 유형(건물지붕, 건물벽면, 수상형, 영농형, 토지)을 분석합니다.

## 핵심 아키텍처

### 데이터 파이프라인 흐름
1. **데이터 병합 단계** (`01. Market Potential_Data Merge.py`)
   - `1. Raw Data/` 폴더의 25개 원본 CSV 파일 병합
   - 중간 파일 생성: `data_merge_except_exclusion.csv`
   - 배제 시나리오 적용하여 최종 `data_merge__{timestamp}.csv` 생성 (~4.5GB)
   - 격자 기반 데이터 구조: 100m x 100m 격자셀 약 1,920만 행
   - 타임스탬프 기반 파일명으로 버전 관리

2. **분석 단계** (`test1.py`)
   - 병합된 데이터와 파라미터 파일(`시장잠재량 Parameter_4.xlsx`) 로드
   - 각 설치 유형별 LCOE(균등화 발전원가) 계산
   - 경제성 임계값 기반 시장잠재량 산출
   - `2. Output/` 폴더에 결과 출력

### 주요 데이터 구조

**격자셀 컬럼** (병합 데이터 기준):
- 행정구역: `id`, `SIDO_CD`, `SIDO_NM`, `SIGUNGU_CD`, `SIGUNGU_NM`, `ADM_CD`, `ADM_NM`
- 지리정보: `inland_area` (면적 m²), `dist` (계통연계 거리)
- 태양광 자원: `일사량(kWh/m2/day)`
- 토지이용: `산지_Area_(m2)`, `하천호소저수지_Area(m2)`, `건물면적(m2)`, 건물 벽면 면적
- 배제지역: 규제 시나리오별 `calc_reject_*` 및 `cond_reject_*` 컬럼들
- 가중치: `weight_산업단지`, `weight_주차장`, `weight_영농형`

**분석 대상 설치 유형**:
- `건물지붕` (건물 옥상)
- `건물벽면` (건물 외벽) - 신규 추가 기능
- `수상형` (수면 부유식)
- `영농형_8년/20년/23년` (계약기간별 영농형)
- `토지` (지상형)
- 특수 범주: 산업단지, 주차장

### Main 함수 인터페이스

```python
main(scenario_name: str,
     print_summary: bool = False,
     create_viz: bool = False,
     summarize_area: bool = False,
     return_lcoe: bool = False) -> pd.DataFrame
```

**매개변수**:
- `scenario_name`: 배제 시나리오 컬럼명 (예: `'calc_reject_영농지_S1'`)
- `return_lcoe`: `True`면 LCOE 컬럼 포함 전체 DataFrame 반환, `False`(기본값)면 시장잠재량 컬럼만 반환

**주요 함수**:
- `calculate_potential()`: 건물 면적 제외한 핵심 시장잠재량 계산
- `calculate_potential_sample()`: 배제지역 처리 방식이 다른 대체 계산 함수
- `run_scenario_with_facade()`: 주어진 배제 시나리오에 대한 전체 분석 파이프라인 실행
- `calculate_facade_*()`: 건물벽면 분석 함수군 (LCOE, 일사량, 이용률)

## 분석 실행

### 필수 요구사항
`1. Raw Data/` 폴더에 필요한 파일:
- `시장잠재량 Parameter_4.xlsx` - 경제성 파라미터 (가격, 요율, 비용)
- 격자 데이터 파일 (격자b_SGIS내륙정보.csv 등)
- 배제지역 파일 (배제21종, 배제24종, 배제28종 등)
- 건물/토지이용 데이터셋

### 실행 패턴
```python
# 기본 실행 - 시장잠재량 결과만 반환
scenario_name = 'calc_reject_영농지_S1'
df_result = main(scenario_name)

# LCOE 데이터 반환
df_lcoe = main(scenario_name, return_lcoe=True)

# 요약 포함 전체 분석
df_result = main(scenario_name,
                 print_summary=True,
                 summarize_area=True)
```

### 데이터 병합 실행
원본 데이터 변경 시 `01. Market Potential_Data Merge.py` 실행:
- 전체 병합 소요시간: 10-15분
- 필요 메모리: 약 20GB RAM
- 중간 파일: `data_merge_except_exclusion.csv`
- 최종 출력: `data_merge__{YYYYMMDDHHMM}.csv` (타임스탬프 자동 생성)

## 주요 규칙

### 파일 명명법
- 대용량 CSV 파일(>100MB)은 `.gitignore`에 포함 - 저장소에 커밋하지 않음
- 백업 파일 패턴: `{파일명}_backup_YYYYMMDD_HHMMSS.py`
- 병합 데이터 파일: `data_merge__{YYYYMMDDHHMM}.csv` (타임스탬프 자동)
- 출력 파일에 시나리오명 포함: `시장잠재량연산결과_{scenario}_건물벽면포함.csv`

### 한글 변수명
이 코드베이스는 한글 변수명을 광범위하게 사용:
- `시장잠재량` = market potential (설치 가능한 시장 규모)
- `설비용량` = installed capacity (GW 단위)
- `발전량` = power generation (TWh/년 단위)
- `배제지역` = exclusion zone (설치 불가 지역)
- `건물지붕/벽면` = building rooftop/facade

### 전역 변수
`main()` 함수에서 사용하는 전역 변수:
- `parameter_dict`: Excel 파일의 경제성 파라미터
- `df_lcoe`: LCOE 계산 결과가 담긴 DataFrame
- `smp_rec_values`: SMP(계통한계가격) + REC(신재생에너지공급인증서) 임계값

## 데이터 크기 고려사항

- 입력 병합 데이터: 약 4.5GB (`data_merge__{timestamp}.csv`)
- 격자 해상도: 대한민국 전역 100m x 100m 셀 (약 1,920만 셀)
- 메모리 사용량: 전체 분석 시 10-20GB RAM 예상
- 처리 시간: 일반 하드웨어 기준 시나리오당 10-15분
- 원본 데이터 파일: 총 25개 CSV + 1개 Excel (1. Raw Data/ 폴더)

## 출력 구조

`2. Output/` 폴더에 저장되는 결과:
- 주요 결과: `시장잠재량연산결과_{scenario}_건물벽면포함.csv`
- 지역별 집계: `시도별_집계결과_건물벽면포함.csv`, `시군구별_집계결과_건물벽면포함.csv`
- 발전량(TWh/년) 및 설비용량(GW) 지표 모두 포함
