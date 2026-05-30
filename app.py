import streamlit as st
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# 1. 網頁基本設定
st.set_page_config(page_title="馬高午餐小拉屎", page_icon="🍱", layout="centered")
st.title("🍱 馬高午餐小拉屎")

# 強制設定為台灣台北時區 (UTC+8)
tz_taiwan = timezone(timedelta(hours=8))

# 2. 檔案路徑與雲端連結讀取
menu_file = "lunch_menu.csv"

try:
    cloud_post_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    cloud_read_url = st.secrets["connections"]["gsheets"]["csv_url"]
except:
    cloud_post_url = ""
    cloud_read_url = ""

# 3. 防作弊核心：初始化瀏覽器記憶體
if "voted_dishes" not in st.session_state:
    st.session_state.voted_dishes = set()

# 4. 檢查主菜單是否存在
if os.path.exists(menu_file):
    df_menu = pd.read_csv(menu_file, encoding="utf-8-sig", dtype={"date": str})
    
    # 建立網頁分頁
    tab1, tab2 = st.tabs(["📱 學生專屬評分區", "📊 歷史評分總覽"])
    
    # ================= 頁籤一：學生專屬評分區 =================
    with tab1:
        # 💡 關鍵修正：精準抓取台灣當下的日期，徹底解決國外伺服器時差問題
        today_str = datetime.now(tz_taiwan).strftime("%Y-%m-%d")
        available_dates = df_menu['date'].unique()
        
        if today_str in available_dates:
            active_date = today_str
            st.info(f"✨ 系統已自動切換至今日菜單 ({active_date})")
        else:
            active_date = available_dates[-1]
            st.warning(f"❌ 找不到今日菜單，顯示最新一日的菜單 ({active_date})")
            
        st.write("請為今日菜色進行評分：")
        
        df_today_menu = df_menu[df_menu['date'] == active_date]
        categories = df_today_menu['category'].unique()
        
        for cat in categories:
            st.markdown(f"### 🔹 {cat}")
            dishes = df_today_menu[df_today_menu['category'] == cat]['dish_name'].tolist()
            
            for dish in dishes:
                col1, col2, col3 = st.columns([3, 2, 2])
                vote_key = f"{active_date}_{dish}"
                has_voted = vote_key in st.session_state.voted_dishes
                
                with col1:
                    if has_voted:
                        st.write(f"~~{dish} (已評分)~~")
                    else:
                        st.write(f"**{dish}**")
                        
                with col2:
                    score = st.selectbox(
                        "分數", [5, 4, 3, 2, 1], 
                        format_func=lambda x: f"{x} ⭐", 
                        key=f"score_{dish}", 
                        label_visibility="collapsed",
                        disabled=has_voted
                    )
                    
                with col3:
                    if has_voted:
                        st.button("已送出", key=f"btn_{dish}", disabled=True)
                    else:
                        if st.button("送出", key=f"btn_{dish}"):
                            if not cloud_post_url or "macros/s" not in cloud_post_url:
                                st.error("❌ 請聯繫管理員(錯誤：請確認secrets.toml內填入的是Google Apps Script的網頁應用程式網址)")
                            else:
                                # 寫入雲端的時間也同步改為台灣時間
                                now_time = datetime.now(tz_taiwan).strftime("%Y-%m-%d %H:%M:%S")
                                
                                payload = {
                                    "timestamp": now_time,
                                    "menu_date": active_date,
                                    "category": cat,
                                    "dish_name": dish,
                                    "rating": int(score)
                                }
                                
                                try:
                                    res = requests.post(cloud_post_url, data=payload)
                                    if "Success" in res.text or res.status_code == 200:
                                        st.session_state.voted_dishes.add(vote_key)
                                        st.toast(f"🎉 {dish} 評分雲端同步成功！")
                                        st.balloons()
                                        st.rerun()
                                    else:
                                        st.error("❌ 請聯繫管理員(雲端拒絕接收 請檢查Apps Script的『誰有存取權』是否設定為『任何人』)")
                                except Exception as e:
                                    st.error(f"❌ 連線失敗: {e}")
            st.write("---")
            
    # ================= 頁籤二：排餐參考大看板 =================
    with tab2:
        st.subheader("📈 歷史評分榜")
        
        if not cloud_read_url:
            st.info("❌ 請聯繫管理員(請至secrets.toml設定csv_url即可啟用雲端看板功能)")
        else:
            try:
                # 透過加上 timestamp 參數，強迫 Streamlit 每次都去撈最新的 Google 試算表資料
                current_ts = datetime.now(tz_taiwan).timestamp()
                df_ratings = pd.read_csv(f"{cloud_read_url}&timestamp={current_ts}", encoding="utf-8")
            except Exception as e:
                df_ratings = pd.DataFrame()
                st.error(f"❌ 請聯繫管理員(讀取雲端資料失敗 請確認試算表有『發布到網路』並選擇CSV格式)")
                
            if df_ratings.empty or len(df_ratings) == 0:
                st.info("☁️ 目前雲端資料庫還是空的 正在等待第一筆學生投票數據")
            else:
                df_ratings.columns = ["timestamp", "menu_date", "category", "dish_name", "rating"]
                df_ratings["menu_date"] = df_ratings["menu_date"].astype(str)
                df_ratings["rating"] = pd.to_numeric(df_ratings["rating"])
                
                date_options = ["所有歷史紀錄"] + list(df_menu['date'].unique())
                selected_date = st.selectbox("📅 選擇特定日期的排行榜：", date_options)
                
                if selected_date != "所有歷史紀錄":
                    df_date_filtered = df_ratings[df_ratings["menu_date"] == selected_date]
                else:
                    df_date_filtered = df_ratings
                    
                filter_options = ["全部菜色"] + list(df_menu['category'].unique())
                selected_filter = st.selectbox("🔍 依菜色分類篩選：", filter_options)
                
                if df_date_filtered.empty:
                    st.warning(f"目前還沒有人評分過 {selected_date} 的菜色喔")
                else:
                    df_stats = df_date_filtered.groupby("dish_name").agg(
                        平均分數=("rating", "mean"),
                        總投票次數=("rating", "count"),
                        分類=("category", "first")
                    ).reset_index()
                    
                    df_stats["平均分數"] = df_stats["平均分數"].round(2)
                    df_stats = df_stats.sort_values(by="平均分數", ascending=False)
                    df_stats = df_stats[["分類", "dish_name", "平均分數", "總投票次數"]]
                    
                    if selected_filter != "全部菜色":
                        df_final = df_stats[df_stats["分類"] == selected_filter]
                    else:
                        df_final = df_stats
                    
                    st.write(f"### 🏆 {selected_date} - {selected_filter} 五星排行榜")
                    
                    st.markdown("""
                    <style>
                    .star-container {
                        display: flex; align-items: center; justify-content: space-between; 
                        background-color: #f8f9fa; padding: 10px 15px; border-radius: 8px; margin-bottom: 8px;
                        border-left: 5px solid #ffc107; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    if not df_final.empty:
                        for idx, row in df_final.iterrows():
                            dish_name = row["dish_name"]
                            score_val = row["平均分數"]
                            votes_val = row["總投票次數"]
                            percentage = (score_val / 5.0) * 100
                            
                            star_html = f"""
                            <div class="star-container">
                                <div style="font-weight: bold; font-size: 16px; color: #333;">{dish_name}</div>
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <div style="position: relative; width: 120px; font-size: 26px; user-select: none; line-height: 1;">
                                        <div style="display: flex; justify-content: space-between; color: #e0e0e0;">
                                            <span>★</span><span>★</span><span>★</span><span>★</span><span>★</span>
                                        </div>
                                        <div style="position: absolute; top: 0; left: 0; width: {percentage}%; overflow: hidden; color: #ffc107; white-space: nowrap; line-height: 1;">
                                            <div style="display: flex; justify-content: space-between; width: 120px;">
                                                <span>★</span><span>★</span><span>★</span><span>★</span><span>★</span>
                                            </div>
                                        </div>
                                    </div>
                                    <span style="font-weight: bold; color: #ff9800; font-size: 16px; width: 45px; text-align: right;">{score_val:.2f}</span>
                                    <span style="color: #6c757d; font-size: 12px;">({votes_val}票)</span>
                                </div>
                            </div>
                            """
                            st.markdown(star_html, unsafe_allow_html=True)
                    
                    st.write("---")
                    st.write("### 📋 詳細數據明細表")
                    st.dataframe(df_final, use_container_width=True, hide_index=True)
                    
                    csv_data = df_final.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📥 點此下載統計報表 (CSV格式)",
                        data=csv_data,
                        file_name=f"馬高午餐統計_{selected_date}_{selected_filter}.csv",
                        mime="text/csv",
                        key="download_report"
                    )
                    
                   if not df_final.empty:
                   st.write("---")
                   st.markdown("### ⚠️ 需盡快改善：")
    
                   # 抓取最後 5 筆，並反轉順序（讓分數最低的排在最上面）
                   df_worst_five = df_final.iloc[-5:].iloc[::-1]
    
                   # 用迴圈把每一道菜列出來
                   for idx, row in df_worst_five.iterrows():
                   st.markdown(f"❌ `{row['dish_name']}` ({row['平均分數']} ⭐)")
        
                    st.write("---")
                    st.write("### 📈 菜色滿意度歷史趨勢")
                    all_dishes_in_history = sorted(df_ratings["dish_name"].unique())
                    
                    if all_dishes_in_history:
                        selected_trend_dish = st.selectbox("🔍 選擇想追蹤歷史趨勢的菜色：", all_dishes_in_history)
                        df_dish_trend = df_ratings[df_ratings["dish_name"] == selected_trend_dish]
                        df_trend_chart = df_dish_trend.groupby("menu_date")["rating"].mean().reset_index()
                        df_trend_chart = df_trend_chart.sort_values(by="menu_date")
                        df_trend_chart.columns = ["日期", "當日平均分數"]
                        df_trend_chart = df_trend_chart.set_index("日期")
                        st.line_chart(df_trend_chart, y="當日平均分數")
else:
    st.error(f"❌ 請聯繫管理員(找不到lunch_menu.csv 請確保菜單檔案在同一個資料夾內)")
