# 🌞 Solar Market Potential Analysis

대한민국 전역의 태양광 설치 가능 용량(시장잠재량)을 계산하는 대규모 지리공간 데이터 분석 시스템입니다.

## 📋 프로젝트 개요

기술적, 규제적, 경제적 제약을 고려하여 여러 태양광 설치 유형별 시장잠재량을 분석합니다:
- 🏠 건물지붕 (Building Rooftop)
- 🏢 건물벽면 (Building Facade)
- 🌊 수상형 (Floating Solar)
- 🌾 영농형 (Agrivoltaics) - 8년/20년/23년 계약기간별
- 🏞️ 토지 (Ground-mounted)
- 🏭 특수: 산업단지, 주차장

## 🗂️ 프로젝트 구조

```bash
Solar-Potential/
├── 01. Market Potential_Data Merge.py    # 데이터 병합 스크립트
├── test1.py                              # 시장잠재량 분석 메인 코드
├── visualization.py                      # 지도 시각화 모듈
├── CLAUDE.md                             # Claude Code 가이드
├── README.md                             # 프로젝트 설명
├── 1. Raw Data/                          # 원본 데이터 (25 CSV + 1 Excel)
│   ├── 시장잠재량 Parameter_4.xlsx       # 경제성 파라미터
│   ├── b_전국격자_100_통합_20250507.csv  # 기준 격자 데이터
│   ├── 격자b_SGIS내륙정보(2025).csv      # 내륙 격자 정보 (행정구역 포함)
│   ├── 격자b_SGIS내륙정보.shp            # 격자 geometry (시각화용)
│   ├── 산업단지.csv                      # 가중치 계산용
│   ├── 주차장(교통시설UQS200210290).csv
│   ├── 경지계-농업진흥구역(UEA110)_v2.csv
│   ├── 1.산지.csv                        # 토지이용 데이터
│   ├── 2.하천호소저수지.csv
│   ├── 28.주택.csv
│   ├── 전체건축물.csv
│   ├── 공시지가_within.csv
│   ├── 전국_GIS건물(주택)_100m버퍼.csv   # 건물 관련
│   ├── 전국_GIS건물(주택)+실폭도로_100m버퍼.csv
│   ├── GRID_100m_bstats_240806_id_added(v1.1).csv
│   ├── GRID_100m_bstats_fa_240806_id_added(v1.1).csv
│   ├── 1km일사량_within.csv              # 태양광 자원
│   ├── 기술영향요인5종_32652.csv         # 계통연계
│   ├── Dist_kepco_IDcorrected_32652.csv
│   ├── 배제21종.csv                      # 배제지역 시나리오
│   ├── 배제24종.csv
│   ├── 배제28종(1-26+6m폭도로100m버퍼+철도).csv  # (선택)
│   ├── 배제29종(실조례안).csv
│   ├── Solar_S1~S4.csv                   # 태양광 시나리오
│   ├── 영농지_S1~S4.csv                  # 영농형 시나리오
│   ├── bnd_sido_00_2024_2Q.gpkg          # 시도 경계 (17개)
│   ├── bnd_sigungu_00_2024_2Q.gpkg       # 시군구 경계 (252개)
│   ├── bnd_dong_00_2024_2Q.gpkg          # 읍면동 경계
│   ├── a0000000a.gpkg                    # 1km 격자 geometry
│   └── id_key_202601291842.csv           # 100m-1km 격자 ID 매핑
├── 2. Output/                            # 분석 결과 저장
│   ├── 시장잠재량연산결과_{scenario}_건물벽면포함.csv
│   ├── 시도별_집계결과_{scenario}_건물벽면포함.csv
│   ├── 시군구별_집계결과_{scenario}_건물벽면포함.csv
│   └── 동별_집계결과_{scenario}_건물벽면포함.csv
├── 3. Image/                             # 시각화 결과
│   ├── 1km격자/                          # 격자별 분포도
│   ├── 시도별/                           # 시도별 합계
│   ├── 시군구별/                         # 시군구별 합계
│   └── 동별/                             # 읍면동별 합계
└── data_merge__{timestamp}.csv           # 병합 데이터 (~4.5GB)
```

## 🚀 시작하기

### 필수 요구사항

- Python 3.8+
- 메모리: 최소 16GB RAM (권장 20GB+)
- 저장공간: 약 10GB 이상

### 설치

1. 저장소 클론
```bash
git clone https://github.com/ggu-bigmaum/Solar-Potential.git
cd Solar-Potential
```

2. 필요한 패키지 설치
```bash
pip install pandas numpy geopandas openpyxl matplotlib contextily
```

3. 데이터 준비
   - `1. Raw Data/` 폴더에 원본 데이터 파일 배치
   - 대용량 파일은 별도 공유 (Google Drive/FTP 예정)

## 📊 사용 방법

### 1단계: 데이터 병합

```bash
python "01. Market Potential_Data Merge.py"
```

**실행 결과:**
- 소요시간: 10-15분
- 생성파일: `data_merge__{YYYYMMDDHHMM}.csv` (약 4.5GB)
- 중간파일: `data_merge_except_exclusion.csv`

### 2단계: 파일명 업데이트

`test1.py`에서 병합 데이터 파일명을 생성된 타임스탬프에 맞게 수정:
```python
df = pd.read_csv('data_merge__{생성된timestamp}.csv', low_memory=False, encoding='euc-kr')
```

### 3단계: 시장잠재량 분석

```python
# 기본 실행 - 시장잠재량 결과만 반환
scenario_name = 'calc_reject_배제29종(실조례안)'
df_result = main(scenario_name)

# 지도 시각화 포함 실행
df_result = main(scenario_name, create_map_viz=True)

# 전체 옵션 실행
df_result = main(scenario_name,
                 print_summary=True,
                 create_viz=True,
                 create_map_viz=True,
                 summarize_area=True)
```

**main() 매개변수:**
| 매개변수 | 기본값 | 설명 |
|----------|--------|------|
| `scenario_name` | (필수) | 배제 시나리오 컬럼명 |
| `print_summary` | False | 시장잠재량 결과 요약 출력 |
| `create_viz` | False | 건물벽면 히스토그램 생성 |
| `create_map_viz` | False | 지도 시각화 생성 (3. Image/) |
| `summarize_area` | False | 시도/시군구/동별 집계 및 저장 |
| `return_lcoe` | False | LCOE 컬럼 포함 전체 DataFrame 반환 |

## 📈 데이터 구조

### 격자 기반 분석
- 해상도: 100m × 100m
- 총 격자 수: 약 1,920만 개
- 커버리지: 대한민국 전역 내륙 지역

### 주요 컬럼
- **행정구역**: SIDO_CD, SIDO_NM, SIGUNGU_CD, SIGUNGU_NM, ADM_CD, ADM_NM
- **지리정보**: inland_area (면적 m²), dist (계통거리)
- **태양광 자원**: 일사량(kWh/m²/day)
- **토지이용**: 산지, 하천, 건물, 주택 면적
- **배제지역**: calc_reject_*, cond_reject_*
- **가중치**: weight_산업단지, weight_주차장, weight_영농형

## 💡 주요 기능

### LCOE 계산
균등화 발전원가(Levelized Cost of Energy)를 각 설치 유형별로 계산:
- 건물지붕/벽면
- 수상형
- 영농형 (8년/20년/23년 계약)
- 토지 (계통반영 포함)

### 시나리오 분석
다양한 배제 시나리오 기반 시장잠재량 산출:
- 배제21종, 24종, 28종, 29종(실조례안)
- Solar S1~S4 (태양광 시나리오)
- 영농지 S1~S4 (영농형 시나리오)

### 지도 시각화
`visualization.py` 모듈을 통한 전국 분포도 생성:
- **1km격자**: 격자 단위 전국 분포도
- **시도별**: 시도 단위 합계 choropleth (17개)
- **시군구별**: 시군구 단위 합계 choropleth (252개)
- **동별**: 읍면동 단위 합계 choropleth

경계 파일: 2024년 2분기 기준 gpkg 형식, 등분(Equal Interval) 분류 방식

### 출력 결과
- 발전량 (TWh/년) 및 설비용량 (GW)
- 시도별/시군구별/동별 집계
- LCOE 상세 데이터

## ⚙️ 설정

### 경제성 파라미터
`1. Raw Data/시장잠재량 Parameter_4.xlsx` 파일에서 관리:
- SMP (계통한계가격)
- REC (신재생에너지공급인증서) 가격
- 설치비용, 운영비용
- 모듈효율, 시스템효율

## 📝 참고사항

### 파일 명명 규칙
- 병합 데이터: `data_merge__{YYYYMMDDHHMM}.csv`
- 백업 파일: `{파일명}_backup_YYYYMMDD_HHMMSS.py`
- 결과 파일: `시장잠재량연산결과_{scenario}_건물벽면포함.csv`

### 성능 고려사항
- 처리 시간: 시나리오당 10-15분
- 메모리 사용: 10-20GB RAM
- 병합 데이터: 약 4.5GB

### Git 관리
- 대용량 CSV 파일(>100MB)은 `.gitignore` 처리
- 원본 데이터는 별도 공유 (Google Drive/FTP)
- 중간 결과물도 Git에서 제외

## 🤝 기여

이 프로젝트는 태양광 시장잠재량 분석을 위한 연구 프로젝트입니다.

## 📄 라이선스

이 프로젝트의 라이선스 정보는 별도로 문의해주세요.

## 📧 문의

프로젝트 관련 문의사항은 이슈를 등록해주세요.

---

**⚠️ 주의사항**
- 원본 데이터 파일은 용량이 크므로 별도 공유 예정
- 분석 실행 전 충분한 메모리와 저장공간 확보 필요
- 한글 변수명이 광범위하게 사용됨 (도메인 특성 반영)
- 데이터의 시군구 수(230개)와 경계 파일(252개)은 행정구역 변경으로 차이 있음
