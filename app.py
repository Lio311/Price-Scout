import streamlit as st
import pandas as pd
import re
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- 1. נתוני קונפיגורציה ממוקדים ---
PRODUCT_NAME = "Amouage Interlude Man 100ml"
MY_PRICE = 1200 # המחיר שלך (נניח)

COMPETITORS = {
    "KSP": "https://ksp.co.il/",
    "Kol_B_Yehuda": "https://kolboyehuda.co.il/",
}
PRICE_GAP_THRESHOLD = 0.20 # 20%

# --- 2. ניהול ה-WebDriver (ללא שינוי, קריטי לסביבת ענן) ---

@st.cache_resource
def get_chrome_driver():
    """מגדיר ומחזיר את מנהל הדפדפן של סלניום."""
    CHROMIUM_PATH = "/usr/bin/chromium" 
    
    chrome_options = Options()
    
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # ציון הנתיב ל-Chromium שהותקן
    chrome_options.binary_location = CHROMIUM_PATH 
    
    # הסוואה:
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        st.error(f"❌ שגיאה בהפעלת Chrome Driver: {e}. ודא ש-packages.txt תקין.")
        st.stop()
        
    return None

try:
    DRIVER = get_chrome_driver()
except Exception:
    DRIVER = None
    
# --- 3. פונקציות Scraping ממוקדות ---

def search_and_scrape_ksp(query):
    """מבצע חיפוש ב-KSP באמצעות Selenium."""
    if not DRIVER: return None

    search_query = query.replace(' ', '+')
    search_url = f"{COMPETITORS['KSP']}web/search/index.aspx?search={search_query}"
    
    try:
        DRIVER.get(search_url)
        WebDriverWait(DRIVER, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "ProductCardPrice"))
        )
        
        soup = BeautifulSoup(DRIVER.page_source, 'html.parser')
        
        # סלקטור משוער עבור KSP
        price_tag = soup.select_one('div.ProductCardPrice span.price-label-text') 
        
        if price_tag:
            price_text = price_tag.text.strip()
            clean_price = re.sub(r'[^\d]', '', price_text) 
            return int(clean_price) if clean_price else None
        
        return None 
        
    except TimeoutException:
        st.warning(f"⏳ KSP: פסק זמן עבור {query}.")
        return None
    except Exception as e:
        st.warning(f"❌ שגיאת Scraping ב-KSP עבור {query}: {e}")
        return None


def search_and_scrape_kolboyehuda(query):
    """מבצע חיפוש ב-Kol_B_Yehuda באמצעות Selenium."""
    if not DRIVER: return None
    
    search_url = f"https://kolboyehuda.co.il/?s={query.replace(' ', '+')}"
    
    try:
        DRIVER.get(search_url)
        WebDriverWait(DRIVER, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-item"))
        )
        
        soup = BeautifulSoup(DRIVER.page_source, 'html.parser')
        
        # סלקטור משוער עבור Kol B'Yehuda
        price_tag = soup.select_one('.product-item .price-wrapper span.amount')

        if price_tag:
            price_text = price_tag.text.strip()
            clean_price = re.sub(r'[^\d]', '', price_price)
            return int(clean_price) if clean_price else None
            
        return None
        
    except TimeoutException:
        st.warning(f"⏳ Kol B'Yehuda: פסק זמן עבור {query}.")
        return None
    except Exception as e:
        st.warning(f"❌ שגיאת Scraping ב-Kol B'Yehuda עבור {query}: {e}")
        return None


SCRAPING_FUNCTIONS = {
    "KSP": search_and_scrape_ksp,
    "Kol_B_Yehuda": search_and_scrape_kolboyehuda
}

# --- 4. לוגיקת השוואה (ממוקדת במוצר אחד) ---

@st.cache_data(ttl=3600) 
def run_price_analysis(product_name, my_price, threshold):
    results = []
    row = {"שם הבושם": product_name, "המחיר שלך": my_price}
    is_alert = False
    status_message = st.empty()
    
    for comp_name, scraper_func in SCRAPING_FUNCTIONS.items():
        status_message.text(f"מעבד נתונים מ: {comp_name} עבור {product_name}...")
        
        comp_price = scraper_func(product_name)
        
        row[f"מחיר {comp_name}"] = comp_price if comp_price else "לא נמצא"

        if comp_price:
            price_gap = (comp_price - my_price) / my_price
            row[f"פער {comp_name} (%)"] = round(price_gap * 100, 2)
            
            if abs(price_gap) >= threshold:
                if price_gap > 0:
                    row["התראה"] = f"יקר ב-{round(price_gap * 100)}% מ-{comp_name}"
                    is_alert = True
                else:
                    row["התראה"] = f"זול ב-{round(abs(price_gap) * 100)}% מ-{comp_name}"
                    is_alert = True
            
        else:
            row[f"פער {comp_name} (%)"] = "אין נתון"
            
        time.sleep(2) 

    if not is_alert:
        row["התראה"] = "בטווח"
        
    results.append(row)
    status_message.text("✅ סיום הניתוח.")
    return pd.DataFrame(results)

# --- 5. ממשק Streamlit ---

st.set_page_config(page_title="💸 PriceScout: Amouage Interlude", layout="wide")

st.title(f"💸 PriceScout: ניתוח מחיר - {PRODUCT_NAME}")
st.markdown("כלי זה מנטר את המחיר שלך מול מתחרים ומאתר פערים משמעותיים.")

with st.sidebar:
    st.header("הגדרות ניתוח")
    
    my_price_input = st.number_input(
        f"המחיר שלך ל-{PRODUCT_NAME}:",
        min_value=100,
        value=MY_PRICE,
        step=50
    )
    
    alert_threshold_percent = st.slider(
        "סף התראה (%)",
        min_value=5, max_value=50, value=int(PRICE_GAP_THRESHOLD * 100), step=1
    )
    
    current_threshold = alert_threshold_percent / 100.0
    current_price = my_price_input

    st.info(f"מנטר כעת את {PRODUCT_NAME} מול {len(COMPETITORS)} מתחרים.")

if st.button("🔄 הפעל ניתוח מחירים"):
    st.cache_data.clear() 
    
    with st.spinner('מבצע Web Scraping ואוסף נתונים...'):
        df_results = run_price_analysis(
            PRODUCT_NAME, 
            current_price, 
            current_threshold
        )
        
        st.success("ניתוח הושלם בהצלחה!")
        
        st.session_state['df_results'] = df_results
        st.session_state['current_threshold'] = current_threshold

# הצגת התוצאות
if 'df_results' in st.session_state:
    df_results = st.session_state['df_results']
    current_threshold = st.session_state['current_threshold']
    
    st.header("💡 סיכום כללי")
    st.dataframe(df_results, use_container_width=True)
    
    df_alerts = df_results[df_results['התראה'] != "בטווח"]
    
    st.header("🚨 התראות פער מחיר משמעותי")
    
    if not df_alerts.empty:
        st.warning(f"נמצאה התראה שחצתה את סף ה-{int(current_threshold*100)}%:")
        
        def highlight_alerts(row):
            style = [''] * len(row)
            if row['התראה'].startswith('יקר'):
                style = ['background-color: #ffcccc'] * len(row) 
            elif row['התראה'].startswith('זול'):
                style = ['background-color: #ccffcc'] * len(row)
            return style

        st.dataframe(
            df_alerts.style.apply(highlight_alerts, axis=1),
            use_container_width=True
        )
    else:
        st.success("המחיר בטווח התחרותי! אין התראות חדשות.")

st.markdown("---")
st.caption("שים לב: Scraping מתקדם כרוך בסיכון חסימה. יש לוודא ש-packages.txt תקין.")
