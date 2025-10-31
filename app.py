import streamlit as st
import pandas as pd
# יבוא הספריות החדשות
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import time

# --- 1. נתוני קונפיגורציה ---
# ... (שאר ההגדרות כמו קודם) ...

COMPETITORS = {
    "KSP": "https://ksp.co.il/",
    "Kol_B_Yehuda": "https://kolboyehuda.co.il/",
}

# ... (MY_INVENTORY ושאר ההגדרות) ...

# --- הוספת ניהול ה-WebDriver גלובלית (עבור Streamlit) ---

@st.cache_resource
def get_chrome_driver():
    """מגדיר ומחזיר את מנהל הדפדפן של סלניום."""
    # הגדרת אופציות לכרום (Headless: ללא ממשק גרפי, כדי שירוץ מהר יותר)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # User-Agent חדש כדי להיראות יותר כמו אדם אמיתי
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')

    # שימוש ב-webdriver_manager כדי לנהל את הדרייבר
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30) # הגבלת זמן טעינת עמוד
    return driver

# קריאה לדרייבר בתחילת הריצה
try:
    DRIVER = get_chrome_driver()
except Exception as e:
    st.error(f"שגיאה בהפעלת Chrome Driver: {e}. ודא שהתקנת Selenium ו-Chrome.")
    DRIVER = None


def search_and_scrape_ksp(query):
    """
    מבצע חיפוש ב-KSP באמצעות Selenium כדי לעקוף את שגיאת 403.
    """
    if not DRIVER:
        return None

    # הקידוד לחיפוש URL
    search_query = query.replace(' ', '+')
    search_url = f"{COMPETITORS['KSP']}web/search/index.aspx?search={search_query}"
    
    try:
        # פתיחת הדף באמצעות Selenium
        DRIVER.get(search_url)
        time.sleep(3) # המתנה לטעינת התוכן (במיוחד אם יש JS)
        
        # שימוש ב-BeautifulSoup על התוכן ש-Selenium טען
        soup = BeautifulSoup(DRIVER.page_source, 'html.parser')
        
        # *** חשוב: סלקטורים מעודכנים שצריך לאמת ***
        # מחפש את המחיר בתוך כרטיס המוצר
        price_tag = soup.find('div', class_='ProductCardPrice') 
        
        if price_tag:
            # מנקה וממיר למספר (מסיר שקלים, פסיקים וכד')
            price_text = price_tag.text.strip()
            # משתמש ב-Regex כדי למצוא רק מספרים
            clean_price = re.sub(r'[^\d]', '', price_text) 
            return int(clean_price)
        return None # לא נמצא מחיר
        
    except Exception as e:
        # הודעת שגיאה פחות חמורה, מאחר ש-403 נפתרה
        st.warning(f"שגיאת Scraping ב-KSP עבור {query}: {e}")
        return None


def search_and_scrape_kolboyehuda(query):
    # נשאיר את הפונקציה הזו כרגע כפי שהיא, או שנשנה גם אותה ל-Selenium אם יהיו חסימות.
    # כרגע נשתמש ב-Mock Data כיוון שהגישה לאתר זה מורכבת
    return None # חזרה על None כי קשה לגשת ללא Scraping מתקדם/Selenium

# ... (שאר הקוד של run_price_analysis ושל ממשק Streamlit נשאר כמעט זהה) ...
