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
solar-test/
├── 01. Market Potential_Data Merge.py    # 데이터 병합 스크립트
├── test1.py                              # 시장잠재량 분석 메인 코드
├── CLAUDE.md                             # Claude Code 가이드
├── README.md                             # 프로젝트 설명
├── 1. Raw Data/                          # 원본 데이터 (25 CSV + 1 Excel)
│   ├── 시장잠재량 Parameter_4.xlsx       # 경제성 파라미터
│   ├── b_전국격자_100_통합_20250507.csv  # 기준 격자 데이터
│   ├── 격자b_SGIS내륙정보.csv            # 내륙 격자 정보
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
│   ├── 배제28종(1-26+6m폭도로100m버퍼+철도).csv
│   ├── 배제29종(실조례안).csv
│   ├── 영농지_S1.csv                     # 영농형 시나리오
│   ├── 영농지_S2.csv
│   ├── 영농지_S3.csv
│   ├── 영농지_S4.csv
│   └── ... (기타 배제지역 파일)
├── 2. Output/                            # 분석 결과 저장
│   ├── 시장잠재량연산결과_{scenario}_건물벽면포함.csv
│   ├── 시도별_집계결과_건물벽면포함.csv
│   └── 시군구별_집계결과_건물벽면포함.csv
└── data_merge__{timestamp}.csv          # 병합 데이터 (~4.5GB)
```

## 🚀 시작하기

### 필수 요구사항

- Python 3.8+
- 메모리: 최소 16GB RAM (권장 20GB+)
- 저장공간: 약 10GB 이상

### 설치

1. 저장소 클론
```bash
git clone https://github.com/ggu-bigmaum/solar-test.git
cd solar-test
```

2. 필요한 패키지 설치
```bash
pip install pandas numpy geopandas openpyxl matplotlib folium contextily dbfread
```

3. 데이터 준비
   - `1. Raw Data/` 폴더에 25개 CSV + 1개 Excel 파일 배치
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

`test1.py` 파일의 484번 라인 수정:
```python
df = pd.read_csv('data_merge__{생성된timestamp}.csv', low_memory=False)
```

### 3단계: 시장잠재량 분석

```python
from test1 import main

# 기본 분석
scenario_name = 'calc_reject_영농지_S1'
df_result = main(scenario_name)

# LCOE 포함 전체 데이터 반환
df_lcoe = main(scenario_name, return_lcoe=True)

# 요약 출력 포함
df_result = main(scenario_name,
                 print_summary=True,
                 summarize_area=True)
```

## 📈 데이터 구조

### 격자 기반 분석
- 해상도: 100m × 100m
- 총 격자 수: 약 1,920만 개
- 커버리지: 대한민국 전역 내륙 지역

### 주요 컬럼
- **행정구역**: SIDO_NM, SIGUNGU_NM, ADM_NM
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
- 토지
- 산업단지, 주차장

### 시나리오 분석
다양한 배제 시나리오 기반 시장잠재량 산출:
- 배제21종, 24종, 28종, 29종
- 영농지 S1~S4 시나리오

### 출력 결과
- 설비용량 (GW)
- 발전량 (TWh/년)
- 시도별/시군구별 집계
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
