
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# =====================================================
# [1] 자치구 기준 리스트 변수 정의
# =====================================================
GU_LIST = [
    "강남구", "강동구", "강북구", "강서구", "관악구",
    "광진구", "구로구", "금천구", "노원구", "도봉구",
    "동대문구", "동작구", "마포구", "서대문구", "서초구",
    "성동구", "성북구", "송파구", "양천구", "영등포구",
    "용산구", "은평구", "종로구", "중구", "중랑구"
]

# =====================================================
# [2] 데이터 로드 기능부 (셀 2 검증 완료 로직)
# =====================================================
def load_bus_stop(data_dir):
    path = os.path.join(data_dir, "bus_stop.xlsx")
    df = pd.read_excel(path)
    result = df[["자치구.1", "정류장수"]].dropna(subset=["자치구.1", "정류장수"])
    result = result.rename(columns={"자치구.1": "자치구", "정류장수": "bus_stop"})
    result["자치구"] = result["자치구"].str.strip()
    return result[result["자치구"].isin(GU_LIST)].set_index("자치구")["bus_stop"]

def load_cctv(data_dir):
    path = os.path.join(data_dir, "cctv.xlsx")
    df = pd.read_excel(path, skiprows=2)
    df.columns = df.columns.str.strip()
    df["자치구"] = df["자치구"].fillna("").astype(str).str.replace(" ", "")
    result = df[df["자치구"].isin(GU_LIST)][["자치구", "총 계"]]
    result = result.rename(columns={"총 계": "cctv_count"})
    result["cctv_count"] = pd.to_numeric(result["cctv_count"], errors="coerce").fillna(0).astype(int)
    return result.set_index("자치구")["cctv_count"]

def load_crime(data_dir):
    path = os.path.join(data_dir, "crime.csv")
    df = pd.read_csv(path, skiprows=3)
    df["자치구별(2)"] = df["자치구별(2)"].str.strip()
    result = df[df["자치구별(2)"].isin(GU_LIST)]
    result = result.rename(columns={"자치구별(2)": "자치구", "발생": "crime_count"})
    return result.set_index("자치구")["crime_count"]

def load_park(data_dir):
    path = os.path.join(data_dir, "park.csv")
    df = pd.read_csv(path, skiprows=4)
    df["자치구별(2)"] = df["자치구별(2)"].str.strip()
    result = df[df["자치구별(2)"].isin(GU_LIST)][["자치구별(2)", "공원수 (개소)", "면적 (천㎡)"]]
    result = result.rename(columns={
        "자치구별(2)": "자치구",
        "공원수 (개소)": "park_count",
        "면적 (천㎡)": "park_area"
    })
    result["park_count"] = pd.to_numeric(result["park_count"], errors="coerce").fillna(0).astype(int)
    result["park_area"]  = pd.to_numeric(result["park_area"],  errors="coerce").fillna(0)
    return result.set_index("자치구")[["park_count", "park_area"]]

def load_subway(data_dir):
    path = os.path.join(data_dir, "subway.csv")
    df = pd.read_csv(path, encoding="cp949")
    df["자치구"] = df["자치구"].str.strip()
    result = df[df["자치구"].isin(GU_LIST)][["자치구", "역개수"]]
    return result.rename(columns={"역개수": "subway_count"}).set_index("자치구")["subway_count"]

def load_crawled_economy(data_dir):
    path = os.path.join(data_dir, "zigbang_monthly_rent1.csv")
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
            if {"자치구", "평균_월세(만원)"}.issubset(df.columns):
                return df.set_index("자치구")[["평균_월세(만원)"]].to_dict("index")
        except Exception:
            pass
    return {}

def load_data():
    data_dir = "./data"
    df = pd.DataFrame({"자치구": GU_LIST})

    if os.path.exists(data_dir):
        try: df["bus_stop"] = df["자치구"].map(load_bus_stop(data_dir)).astype(int)
        except Exception as e: st.sidebar.warning(f"bus_stop.xlsx 로드 오류: {e}")

        try: df["cctv_count"] = df["자치구"].map(load_cctv(data_dir)).astype(int)
        except Exception as e: st.sidebar.warning(f"cctv.xlsx 로드 오류: {e}")

        try: df["crime_count"] = df["자치구"].map(load_crime(data_dir)).astype(int)
        except Exception as e: st.sidebar.warning(f"crime.csv 로드 오류: {e}")

        try:
            park = load_park(data_dir)
            df["park_count"] = df["자치구"].map(park["park_count"]).astype(int)
            df["park_area"]  = df["자치구"].map(park["park_area"])
        except Exception as e: st.sidebar.warning(f"park.csv 로드 오류: {e}")

        try: df["subway_count"] = df["자치구"].map(load_subway(data_dir)).astype(int)
        except Exception as e: st.sidebar.warning(f"subway.csv 로드 오류: {e}")

        # 경제 데이터 (월세 단일화)
        df["monthly_rent"] = 0
        crawled = load_crawled_economy(data_dir)
        if crawled:
            st.sidebar.success("✅ 크롤링 월세 데이터 연동 완료!")
            for idx, row in df.iterrows():
                gu = row["자치구"]
                if gu in crawled:
                    r = crawled[gu].get("평균_월세(만원)", 0)
                    if r > 0: df.at[idx, "monthly_rent"] = r
        else:
            st.sidebar.info("💡 경제 데이터: 크롤링 파일 없음 (0원 초기화)")
    else:
        st.sidebar.warning("⚠️ ./data 폴더를 찾을 수 없습니다.")

    return df

# =====================================================
# [3] 연산 엔진부 (셀 3 검증 완료 로직)
# =====================================================
def normalize(series, higher_is_better=True):
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([50.0] * len(series), index=series.index)
    norm = (series - mn) / (mx - mn) * 100
    return norm if higher_is_better else 100 - norm

def calculate_scores(df, w_safety, w_transport, w_economy, w_green):
    df = df.copy()
    df["score_safety"]    = (normalize(df["cctv_count"],    True)  + normalize(df["crime_count"],   False)) / 2
    df["score_transport"] = (normalize(df["bus_stop"],      True)  + normalize(df["subway_count"],  True))  / 2
    df["score_economy"]   = normalize(df["monthly_rent"],  False) # 월세 낮을수록 만점
    df["score_green"]     = (normalize(df["park_count"],    True)  + normalize(df["park_area"],     True))  / 2

    total_w = w_safety + w_transport + w_economy + w_green or 1
    df["score_total"] = (
        df["score_safety"]    * w_safety    +
        df["score_transport"] * w_transport +
        df["score_economy"]   * w_economy   +
        df["score_green"]     * w_green
    ) / total_w
    return df

# =====================================================
# [4] 화면 UI 뷰 레이어 (셀 4 시각화 결합 부)
# =====================================================
def page_home(df):
    st.title("🏙️ 서울시 최적 거주지 선택 가이드")
    st.write("""
    이사나 독립을 준비 중인 분들을 위해,  
    **치안·교통·경제(월세)·녹지** 4가지 기준으로 서울시 25개 자치구를 분석하고  
    나만의 가중치로 최적의 동네를 추천해드립니다.
    """)
    st.markdown("---")

    st.subheader("📊 서울시 25개 자치구 평균 지표 요약")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔒 평균 CCTV 수",      f"{int(df['cctv_count'].mean()):,}대")
    col2.metric("🚌 평균 버스정류장 수", f"{int(df['bus_stop'].mean()):,}개")
    col3.metric("🌳 평균 공원 수",       f"{int(df['park_count'].mean()):,}개")
    col4.metric("🏠 평균 월세 시세",     f"{int(df['monthly_rent'].mean()):,}만원")
    st.markdown("---")
    
    st.subheader("📂 프로젝트 분석 데이터 출처 안내")
    st.write("본 가이드 대시보드는 공공데이터포털 및 웹 크롤링을 통해 수집한 신뢰도 높은 최신 지표 데이터를 기반으로 연산됩니다.")
    
    src_col1, src_col2 = st.columns(2)
    
    with src_col1:
        st.markdown("""
        #### 🔒 치안 (Safety)
        * **CCTV 보유 현황**: [서울 열린데이터 광장] (https://data.seoul.go.kr/dataList/OA-2734/F/1/datasetView.do)
        * **5대 범죄 발생 건수**: [서울 열린데이터 광장] (https://data.seoul.go.kr/dataList/316/S/2/datasetView.do)
        
        #### 🚌 교통 (Transportation)
        * **시내버스 정류장 현황**: [서울 열린데이터 광장] (https://data.seoul.go.kr/dataList/OA-22187/F/1/datasetView.do)
        * **지하철역 주소 및 개수**: [공공데이터포털] (https://www.data.go.kr/data/15081868/fileData.do)
        """)
        
    with src_col2:
        st.markdown("""
        #### 🏠 경제 (Economy)
        * **자치구별 평균 월세 시세**: [직방(Zigbang)] 웹사이트 실시간 매물 데이터 자체 파이썬 크롤링 연동 수집
        
        #### 🌳 녹지 (Greenery)
        * **도시공원 보유 수 및 총 면적**: [서울 열린데이터 광장] (https://data.seoul.go.kr/dataList/10052/S/2/datasetView.do)
        """)
    st.caption("⚠️ 모든 지표 점수는 자치구별 최소/최대 편차를 고려하여 0~100점 사이로 정규화(Normalization) 가공 후 계산에 반영됩니다.")

def page_stats(df):
    st.title("📊 동네 통계 분석")
    st.write("서울시 25개 자치구의 지표를 시각화하고 비교합니다.")
    st.markdown("---")

    indicator_options = {
        "🔒 CCTV 수 (치안)":        ("cctv_count",    "CCTV 수 (대)"),
        "🚨 범죄 발생 건수 (치안)":  ("crime_count",   "범죄 발생 건수 (건)"),
        "🚌 버스정류장 수 (교통)":   ("bus_stop",      "버스정류장 수 (개)"),
        "🚇 지하철역 수 (교통)":     ("subway_count",  "지하철역 수 (개)"),
        "🏠 평균 월세 (경제)":       ("monthly_rent",  "월세 (만원)"),
        "🌳 공원 수 (녹지)":         ("park_count",    "공원 수 (개소)"),
        "🌿 공원 면적 (녹지)":       ("park_area",     "공원 면적 (천㎡)"),
    }

    selected = st.selectbox("정렬하여 볼 지표를 선택하세요", list(indicator_options.keys()))
    col_name, y_label = indicator_options[selected]

    df_sorted = df.sort_values(col_name, ascending=False)
    fig = px.bar(
        df_sorted, x="자치구", y=col_name,
        color=col_name, color_continuous_scale="Blues",
        title=f"자치구별 {selected} 순위 현황",
        labels={col_name: y_label}
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("⚖️ 관심 자치구 1:1 레이더 비교")
    col_a, col_b = st.columns(2)
    with col_a: gu_a = st.selectbox("첫 번째 자치구", GU_LIST, index=0)
    with col_b: gu_b = st.selectbox("두 번째 자치구", GU_LIST, index=1)

    row_a = df[df["자치구"] == gu_a].iloc[0]
    row_b = df[df["자치구"] == gu_b].iloc[0]

    df_scored = calculate_scores(df, 25, 25, 25, 25)
    ra = df_scored[df_scored["자치구"] == gu_a].iloc[0]
    rb = df_scored[df_scored["자치구"] == gu_b].iloc[0]

    cats   = ["치안", "교통", "경제(월세)", "녹지"]
    vals_a = [ra["score_safety"], ra["score_transport"], ra["score_economy"], ra["score_green"]]
    vals_b = [rb["score_safety"], rb["score_transport"], rb["score_economy"], rb["score_green"]]

    fig_r = go.Figure()
    fig_r.add_trace(go.Scatterpolar(r=vals_a+[vals_a[0]], theta=cats+[cats[0]], fill='toself', name=gu_a, line_color='royalblue'))
    fig_r.add_trace(go.Scatterpolar(r=vals_b+[vals_b[0]], theta=cats+[cats[0]], fill='toself', name=gu_b, line_color='tomato'))
    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), title=f"{gu_a} vs {gu_b} 종합 요소 균형 점수")
    st.plotly_chart(fig_r, use_container_width=True)

    st.subheader("📋 파일 데이터 수치 대조")
    compare_df = pd.DataFrame({
        "분석 지표 항목": ["CCTV 보유량 (대)", "범죄 발생 (건)", "버스정류장 (개)", "지하철역 (개)", "평균 월세 시세 (만원)", "도시공원 (개소)", "공원 총 면적 (천㎡)"],
        gu_a: [row_a["cctv_count"], row_a["crime_count"], row_a["bus_stop"], row_a["subway_count"], row_a["monthly_rent"], row_a["park_count"], row_a["park_area"]],
        gu_b: [row_b["cctv_count"], row_b["crime_count"], row_b["bus_stop"], row_b["subway_count"], row_b["monthly_rent"], row_b["park_count"], row_b["park_area"]],
    })
    st.dataframe(compare_df, use_container_width=True)

def page_recommend(df):
    st.title("🔍 가중치 맞춤형 동네 찾기")
    st.write("나의 주거 성향 슬라이더를 실시간으로 조정해 맞춤 자치구 랭킹을 확인하세요.")
    st.markdown("---")

    st.subheader("🎚️ 나의 주거 가치관 가중치 설정 (합산 비율 자동 계산)")
    col1, col2 = st.columns(2)
    with col1:
        w_safety    = st.slider("🔒 치안 수준 (CCTV 많고 범죄 적은 곳)",  0, 100, 25)
        w_economy   = st.slider("💰 경제적 부담 (낮고 합리적인 월세 선호)",  0, 100, 25)
    with col2:
        w_transport = st.slider("🚌 대중교통 인프라 (버스·지하철 인접)",  0, 100, 25)
        w_green     = st.slider("🌳 친환경 녹지 공간 (공원 면적·수)", 0, 100, 25)

    total_w = w_safety + w_transport + w_economy + w_green
    if total_w == 0:
        st.warning("⚠️ 최소 하나 이상의 주거 항목에 가중치를 부여해야 연산이 가능합니다.")
        return

    df_scored = calculate_scores(df, w_safety, w_transport, w_economy, w_green)
    df_ranked = df_scored.sort_values("score_total", ascending=False).reset_index(drop=True)
    df_ranked["순위"] = df_ranked.index + 1

    st.subheader("🏆 추천 자치구 TOP 5 결과")
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, (_, row) in enumerate(df_ranked.head(5).iterrows()):
        st.markdown(
            f"{medals[i]} **{row['자치구']}** — 종합 가중 점수 `{row['score_total']:.1f}점`  "
            f"(치안 {row['score_safety']:.0f}점 / 교통 {row['score_transport']:.0f}점 / "
            f"경제 {row['score_economy']:.0f}점 / 녹지 {row['score_green']:.0f}점)"
        )
    st.markdown("---")

    st.subheader("📊 전체 25개 자치구 종합 추천 스코어 분포")
    fig = px.bar(
        df_ranked, x="자치구", y="score_total",
        color="score_total", color_continuous_scale="Oranges",
        title="나의 주거 성향 맞춤형 점수 결과 그래프"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 분석 상세 테이블")
    display_df = df_ranked[[
        "순위", "자치구", "score_total", "score_safety", "score_transport", "score_economy", "score_green"
    ]].rename(columns={
        "score_total":     "종합 스코어",
        "score_safety":    "치안 평가 점수",
        "score_transport": "교통 인프라 점수",
        "score_economy":   "경제성(낮은월세) 점수",
        "score_green":     "녹지 환경 점수",
    }).round(1)
    st.dataframe(display_df, use_container_width=True)

# =====================================================
# [5] 메인 루프 관제탑
# =====================================================
def main():
    st.set_page_config(page_title="서울시 거주지 가이드", page_icon="🏙️", layout="wide")
    menu = st.sidebar.radio("🧭 내비게이션 메뉴", ["🏠 홈 화면", "📊 동네별 지표 통계", "🔍 나만의 최적 동네 매칭"])
    df = load_data()

    if   menu == "🏠 홈 화면":               page_home(df)
    elif menu == "📊 동네별 지표 통계":          page_stats(df)
    elif menu == "🔍 나만의 최적 동네 매칭":   page_recommend(df)

if __name__ == "__main__":
    main()
