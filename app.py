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

# --- 1. נתוני קונפיגורציה ---
BRANDS_TO_MONITOR = ["Amouage", "Xerjoff"]
COMPETITORS = {
    "KSP": "https://ksp.co.il/",
    "Kol_B_Yehuda": "https://kolboyehuda.co.il/",
}
PRICE_GAP_THRESHOLD = 0.20 

# נתוני המלאי שלך (דוגמה)
MY_INVENTORY = {
    "Amouage Interlude Man 100ml": 1200,
    "Amouage Reflection Man 100ml": 1100,
    "Xerjoff Naxos 100ml": 1300,
    "Xerjoff Erba Pura 105ml": 1050, 
}

# --- 2. ניהול ה-WebDriver (תיקון גרסאות קריטי) ---

@st.cache_resource
def get_chrome_driver():
    """
    מגדיר ומחזיר את מנהל הדפדפן של סלניום, תוך ציון הנתיב ל-Chromium שהותקן.
    """
    # הנתיב הסטנדרטי לקובץ הבינארי של Chromium בסביבת Streamlit Cloud
    CHROMIUM_PATH = "/usr/bin/chromium" 
    
    chrome_options = Options()
    
    # הגדרות Headless סטנדרטיות (חובה בסביבת ענן)
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # *** התיקון הקריטי: ציון הנתיב ל-Chromium ***
    # כך הדרייבר ידע להשתמש בדפדפן שהותקן.
    chrome_options.binary_location = CHROMIUM_PATH
    
    # הסוואה: הסרת דגלים שמזהים את סלניום
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User-Agent חזק
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')

    try:
        # בגרסאות Selenium חדשות, ה-Service אינו דורש דרייבר אם ה-binary_location נכון.
        # SeleniumManager המובנה ינסה למצוא דרייבר תואם או להתאים את עצמו.
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        st.error(f"❌ שגיאה בהפעלת Chrome Driver: {e}. ודא שהתקנת Chromium באמצעות packages.txt.")
        st.stop()
        
    return None

try:
    # טעינת הדרייבר פעם אחת בלבד
    DRIVER = get_chrome_driver()
except Exception:
    DRIVER = None
    
# --- 3. פונקציות Scraping מותאמות אישית ---

def search_and_scrape_ksp(query):
    """מבצע חיפוש ב-KSP באמצעות Selenium."""
    if not DRIVER: return None

    search_query = query.replace(' ', '+')
    search_url = f"{COMPETITORS['KSP']}web/search/index.aspx?search={search_query}"
    
    try:
        DRIVER.get(search_url)
        
        # המתנה לטעינת התוכן הרלוונטי
        WebDriverWait(DRIVER, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "ProductCardPrice"))
        )
        
        soup = BeautifulSoup(DRIVER.page_source, 'html.parser')
        
        # סלקטור משוער ומעודכן עבור KSP
        price_tag = soup.select_one('div.ProductCardPrice span.price-label-text') 
        
        if price_tag:
            price_text = price_tag.text.strip()
            clean_price = re.sub(r'[^\d]', '', price_text) 
            return int(clean_price) if clean_price else None
        
        return None 
        
    except TimeoutException:
        st.warning(f"⏳ KSP: פסק זמן עבור {query}. המוצר לא נמצא.")
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
            clean_price = re.sub(r'[^\d]', '', price_text)
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

# --- 4. לוגיקת השוואה והממשק ---

@st.cache_data(ttl=3600) 
def run_price_analysis(inventory, competitors_map, brands_to_monitor, threshold):
    # לוגיקת הניתוח נשארה זהה
    results = []

    products_to_check = {name: price for name, price in inventory.items() 
                         if any(brand.lower() in name.lower() for brand in brands_to_monitor)}

    status_message = st.empty()
    
    for i, (product_name, my_price) in enumerate(products_to_check.items()):
        status_message.text(f"מעבד מוצר {i+1}/{len(products_to_check)}: {product_name}...")
        
        row = {"שם הבושם": product_name, "המחיר שלך": my_price}
        is_alert = False
        
        for comp_name, scraper_func in SCRAPING_FUNCTIONS.items():
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
        
        if not is_alert:
            row["התראה"] = "בטווח"
            
        results.append(row)
        time.sleep(2) 

    status_message.text("✅ סיום הניתוח.")
    return pd.DataFrame(results)

# --- 5. ממשק Streamlit ---

st.set_page_config(page_title="💸 PriceScout: ניתוח פער מחירי בשמים", layout="wide")

st.title("💸 PriceScout: ניתוח פער מחירי בשמים")
st.markdown("כלי זה מנטר את מחירי הבשמים שלך מול מתחרים ומאתר פערים משמעותיים.")

with st.sidebar:
    st.header("הגדרות ניתוח")
    
    alert_threshold_percent = st.slider(
        "סף התראה (%)",
        min_value=5, max_value=50, value=int(PRICE_GAP_THRESHOLD * 100), step=1,
        help="אם פער המחיר למעלה או למטה עובר סף זה, תקבל התראה."
    )
    
    brands_input = st.text_area(
        "מותגים לניטור (מופרדים בפסיקים)",
        ", ".join(BRANDS_TO_MONITOR)
    )
    
    current_threshold = alert_threshold_percent / 100.0
    current_brands = [b.strip() for b in brands_input.split(',') if b.strip()]

    st.info(f"מנטר כעת: {', '.join(current_brands)}. נתונים נשלפים באמצעות Selenium.")

if st.button("🔄 הפעל ניתוח מחירים"):
    if not current_brands:
        st.error("אנא הזן לפחות מותג אחד לניטור.")
    else:
        st.cache_data.clear() 
        
        with st.spinner('מבצע Web Scraping ואוסף נתונים... (זה יכול לקחת זמן)'):
            df_results = run_price_analysis(
                MY_INVENTORY, 
                COMPETITORS, 
                current_brands, 
                current_threshold
            )
            
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
        st.warning(f"נמצאו {len(df_alerts)} התראות שחצו את סף ה-{int(current_threshold*100)}%:")
        
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
        st.success("כל המחירים בטווח התחרותי! אין התראות חדשות.")

st.markdown("---")
st.caption("שים לב: Scraping מתקדם כרוך בסיכון חסימה. יש לוודא ש-packages.txt תקין.")
