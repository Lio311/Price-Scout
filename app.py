import streamlit as st
import pandas as pd
import re
import time
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

# --- ייבוא הכלי החדש ---
import undetected_chromedriver as uc

# --- 1. נתוני קונפיגורציה ממוקדים ---
PRODUCT_NAME = "Amouage Interlude Man 100ml"
MY_PRICE = 1200 

COMPETITORS = {
    "KSP": "https://ksp.co.il/",
    "Kol_B_Yehuda": "https://kolboyehuda.co.il/",
}
PRICE_GAP_THRESHOLD = 0.20 

# --- 2. ניהול ה-WebDriver (משודרג ל-Undetected) ---

@st.cache_resource
def get_chrome_driver():
    """מגדיר ומחזיר את מנהל הדפדפן של סלניום (גרסה בלתי ניתנת לזיהוי)."""
    CHROMIUM_PATH = "/usr/bin/chromium" 
    
    options = uc.ChromeOptions()
    
    # הגדרות Headless (עדיין נחוצות לענן)
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # ציון הנתיב ל-Chromium שהותקן
    options.binary_location = CHROMIUM_PATH 
    
    # הסוואה (הספרייה עושה את רוב העבודה לבד)
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    options.add_argument(f'user-agent={user_agent}')

    try:
        # --- שימוש ב-uc.Chrome במקום ב-webdriver.Chrome ---
        driver = uc.Chrome(options=options, use_subprocess=True) 
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        st.error(f"❌ שגיאה בהפעלת Undetected Chrome Driver: {e}.")
        st.stop()
    return None

try:
    DRIVER = get_chrome_driver()
except Exception:
    DRIVER = None
    
# --- 3. פונקציות Scraping (עם סלקטורים מתוקנים) ---

def search_and_scrape_ksp(query):
    """מבצע חיפוש ב-KSP באמצעות Undetected-Chromedriver."""
    if not DRIVER: return None

    search_query = query.replace(' ', '+')
    search_url = f"https://ksp.co.il/web/search/index.aspx?search={search_query}"
    
    try:
        DRIVER.get(search_url)
        
        # אם קיבלנו 403, הכותרת תהיה "KSP Forbidden 403"
        if "403" in DRIVER.title:
             st.warning(f"❌ KSP עדיין חוסם אותנו (403).")
             return None

        WebDriverWait(DRIVER, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".ProductCardPrice, .SearchResults-list"))
        )
        
        soup = BeautifulSoup(DRIVER.page_source, 'html.parser')
        
        # ⚠️ סלקטור משוער (נשאר זהה בינתיים, הבעיה הייתה החסימה)
        price_tag = soup.select_one('div.ProductCardPrice span.price-label-text') 
        
        if price_tag:
            price_text = price_tag.text.strip()
            clean_price = re.sub(r'[^\d]', '', price_text) 
            return int(clean_price) if clean_price else None
        
        st.warning(f"KSP: המחיר לא נמצא (החסימה הוסרה, אך הסלקטור שגוי).")
        return None 
        
    except TimeoutException:
        st.warning(f"⏳ KSP: פסק זמן (Timeout).")
        return None
    except Exception as e:
        st.warning(f"❌ שגיאת Scraping ב-KSP עבור {query}: {e}")
        return None


def search_and_scrape_kolboyehuda(query):
    """מבצע חיפוש ב-Kol_B_Yehuda (עם סלקטור מתוקן)."""
    if not DRIVER: return None
    
    search_url = f"https://kolboyehuda.co.il/?s={query.replace(' ', '+')}"
    
    try:
        DRIVER.get(search_url)
        WebDriverWait(DRIVER, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".products, .no-products-found")) # המתנה לרשימת המוצרים
        )
        
        soup = BeautifulSoup(DRIVER.page_source, 'html.parser')
        
        # ⚠️ --- תיקון סלקטור (ניחוש מושכל) ---
        # אתרי WooCommerce משתמשים בדרך כלל ב-CSS class הזה:
        price_tag = soup.select_one('.product-item .woocommerce-Price-amount.amount bdi')

        if price_tag:
            price_text = price_tag.text.strip()
            clean_price = re.sub(r'[^\d]', '', price_text)
            # המחיר עשוי להיות עם .00, אז ננקה גם את זה
            clean_price = clean_price.split('00')[0] 
            return int(clean_price) if clean_price else None
            
        st.warning(f"Kol B'Yehuda: המחיר לא נמצא עם הסלקטור המתוקן.")
        return None
        
    except TimeoutException:
        st.warning(f"⏳ Kol B'Yehuda: פסק זמן (Timeout).")
        return None
    except Exception as e:
        st.warning(f"❌ שגיאת Scraping ב-Kol B'Yehuda עבור {query}: {e}")
        return None


SCRAPING_FUNCTIONS = {
    "KSP": search_and_scrape_ksp,
    "Kol_B_Yehuda": search_and_scrape_kolboyehuda
}

# --- 4. לוגיקת השוואה (ללא שינוי) ---

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
                if price_gap > 0: row["התראה"] = f"יקר ב-{round(price_gap * 100)}% מ-{comp_name}"
                else: row["התראה"] = f"זול ב-{round(abs(price_gap) * 100)}% מ-{comp_name}"
                is_alert = True
        else:
            row[f"פער {comp_name} (%)"] = "אין נתון"
        
        time.sleep(1) 

    if not is_alert: row["התראה"] = "בטווח"
    results.append(row)
    status_message.text("✅ סיום הניתוח.")
    return pd.DataFrame(results)

# --- 5. ממשק Streamlit (ללא שינוי) ---

st.set_page_config(page_title="💸 PriceScout: Amouage Interlude", layout="wide")

st.title(f"💸 PriceScout: ניתוח מחיר - {PRODUCT_NAME}")
st.markdown("כלי זה מנטר את המחיר שלך מול מתחרים ומאתר פערים משמעותיים.")

with st.sidebar:
    st.header("הגדרות ניתוח")
    my_price_input = st.number_input(
        f"המחיר שלך ל-{PRODUCT_NAME}:", min_value=100, value=MY_PRICE, step=50
    )
    alert_threshold_percent = st.slider(
        "סף התראה (%)", min_value=5, max_value=50, value=int(PRICE_GAP_THRESHOLD * 100), step=1
    )
    current_threshold = alert_threshold_percent / 100.0
    current_price = my_price_input
    st.info(f"מנטר כעת את {PRODUCT_NAME} מול {len(COMPETITORS)} מתחרים.")

if st.button("🔄 הפעל ניתוח מחירים"):
    st.cache_data.clear() 
    
    with st.spinner('מבצע Web Scraping ואוסף נתונים (גרסה משודרגת)...'):
        df_results = run_price_analysis(PRODUCT_NAME, current_price, current_threshold)
        st.success("ניתוח הושלם בהצלחה!")
        st.session_state['df_results'] = df_results
        st.session_state['current_threshold'] = current_threshold

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
            if row['התראה'].startswith('יקר'): style = ['background-color: #ffcccc'] * len(row) 
            elif row['התראה'].startswith('זול'): style = ['background-color: #ccffcc'] * len(row)
            return style
        st.dataframe(df_alerts.style.apply(highlight_alerts, axis=1), use_container_width=True)
    else:
        st.success("המחיר בטווח התחרותי! אין התראות חדשות.")

st.markdown("---")
st.caption("משתמש כעת ב-Undetected Chromedriver כדי לנסות לעקוף חסימות.")
