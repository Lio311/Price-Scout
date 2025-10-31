import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time

# --- 1. נתוני קונפיגורציה ---

# נתוני קלט מהמשתמש (מותגים)
BRANDS_TO_MONITOR = ["Amouage", "Xerjoff"]

# כתובות האתרים של המתחרים (והמפתח לשימוש בקוד)
COMPETITORS = {
    "KSP": "https://ksp.co.il/",
    "Kol_B_Yehuda": "https://kolboyehuda.co.il/",
}

# הגדרת סף ההתראה (20% כפי שביקשת)
PRICE_GAP_THRESHOLD = 0.20 # 20%

# נתוני המלאי שלך (דוגמה/Mock Data).
# בפרויקט אמיתי: יש לשלוף מ-DB/API/קובץ שלך.
MY_INVENTORY = {
    "Amouage Interlude Man 100ml": 1200,
    "Amouage Reflection Man 100ml": 1100,
    "Xerjoff Naxos 100ml": 1300,
    "Xerjoff Erba Pura 100ml": 1050,
}

# --- 2. פונקציות Scraping מותאמות אישית ---

def search_and_scrape_ksp(query):
    """
    מבצע חיפוש ב-KSP ומנסה לחלץ מחיר.
    *הסלקטורים הם השערה ויש לאמת אותם מול האתר.*
    """
    # החלפת רווחים ל-"+" לחיפוש URL
    search_url = f"{COMPETITORS['KSP']}web/search/index.aspx?search={query.replace(' ', '+')}"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status() # בדיקת שגיאות HTTP
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ניסיון למצוא מחיר מהתוצאה הראשונה
        # סלקטור לדוגמה (צריך אימות): מחפש את המחיר בתוך רשימת המוצרים
        price_tag = soup.find('div', class_='ProductCardPrice').find('div', class_='price-label-text') 
        
        if price_tag:
            # מנקה וממיר למספר (מסיר שקלים, פסיקים וכד')
            price_text = price_tag.text.strip()
            # משתמש ב-Regex כדי למצוא רק מספרים
            clean_price = re.sub(r'[^\d]', '', price_text) 
            return int(clean_price)
        return None # לא נמצא מחיר
        
    except Exception as e:
        st.error(f"שגיאת Scraping ב-KSP עבור {query}: {e}")
        return None


def search_and_scrape_kolboyehuda(query):
    """
    מבצע חיפוש ב-Kol_B_Yehuda ומנסה לחלץ מחיר.
    *הסלקטורים הם השערה ויש לאמת אותם מול האתר.*
    """
    # החלפת רווחים ל-"-" לחיפוש URL
    # הערה: ייתכן שחיפוש באתר זה דורש לוגיקה שונה (כמו שימוש ב-API אם זמין, או סלניום)
    
    # מכיוון שלקול ביהודה אין מנגנון חיפוש ברור ב-URL, נשתמש ב-Mock:
    return None # חזרה על None כי קשה לגשת ללא Scraping מתקדם/Selenium


# מיפוי פונקציות ה-Scraping
SCRAPING_FUNCTIONS = {
    "KSP": search_and_scrape_ksp,
    "Kol_B_Yehuda": search_and_scrape_kolboyehuda
}

# --- 3. לוגיקת השוואה ---

@st.cache_data(ttl=3600) # שמירת התוצאות במטמון לשעה
def run_price_analysis(inventory, competitors_map, brands_to_monitor, threshold):
    results = []

    # סינון המלאי רק לפי המותגים הרצויים
    products_to_check = {name: price for name, price in inventory.items() 
                         if any(brand in name for brand in brands_to_monitor)}

    status_message = st.empty()
    
    for i, (product_name, my_price) in enumerate(products_to_check.items()):
        status_message.text(f"מעבד מוצר {i+1}/{len(products_to_check)}: {product_name}...")
        
        row = {"שם הבושם": product_name, "המחיר שלך": my_price}
        
        for comp_name, scraper_func in SCRAPING_FUNCTIONS.items():
            comp_price = scraper_func(product_name)
            row[f"מחיר {comp_name}"] = comp_price if comp_price else "לא נמצא"

            if comp_price:
                # חישוב פער: (מתחרה - שלי) / שלי
                price_gap = (comp_price - my_price) / my_price
                row[f"פער {comp_name} (%)"] = round(price_gap * 100, 2)
                
                # בדיקת התראה
                if abs(price_gap) >= threshold:
                    if price_gap > 0:
                        row["התראה"] = f"יקר ב-{round(price_gap * 100)}% מ-{comp_name}"
                    else:
                        row["התראה"] = f"זול ב-{round(abs(price_gap) * 100)}% מ-{comp_name}"
                elif "התראה" not in row:
                     row["התראה"] = "בטווח"
            else:
                row[f"פער {comp_name} (%)"] = "אין נתון"
                if "התראה" not in row:
                     row["התראה"] = "אין נתון"
                     
        results.append(row)
        # המתנה קצרה כדי למנוע חסימה
        time.sleep(1) 

    status_message.text("✅ סיום הניתוח.")
    return pd.DataFrame(results)

# --- 4. ממשק Streamlit ---

st.set_page_config(page_title="כלי לניתוח פער מחירי בשמים", layout="wide")

st.title("💸 כלי לניתוח פער מחירי בשמים")
st.markdown("כלי זה מנטר את מחירי הבשמים שלך מול מתחרים ומאתר פערים משמעותיים.")

# הגדרות משתמש
with st.sidebar:
    st.header("הגדרות ניתוח")
    
    # סף התראה
    alert_threshold_percent = st.slider(
        "סף התראה (%)",
        min_value=5,
        max_value=50,
        value=int(PRICE_GAP_THRESHOLD * 100),
        step=1,
        help="אם פער המחיר למעלה או למטה עובר סף זה, תקבל התראה."
    )
    
    # רשימת מותגים (ניתן לשנות)
    brands_input = st.text_area(
        "מותגים לניטור (מופרדים בפסיקים)",
        ", ".join(BRANDS_TO_MONITOR)
    )
    
    # עדכון המשתנים
    current_threshold = alert_threshold_percent / 100.0
    current_brands = [b.strip() for b in brands_input.split(',') if b.strip()]

    st.info(f"מנטר כעת: {', '.join(current_brands)}")
    st.caption("הנתונים שלך נטענים כרגע כנתוני דמה (Mock Data).")

# כפתור הפעלה
if st.button("🔄 הפעל ניתוח מחירים"):
    if not current_brands:
        st.error("אנא הזן לפחות מותג אחד לניטור.")
    else:
        with st.spinner('מבצע Web Scraping ואוסף נתונים... (זה יכול לקחת דקה)'):
            # הפעלת הלוגיקה
            df_results = run_price_analysis(
                MY_INVENTORY, 
                COMPETITORS, 
                current_brands, 
                current_threshold
            )
            
            st.success("ניתוח הושלם בהצלחה!")
            
            # שמירת התוצאה ב-session_state כדי שלא ייעלם
            st.session_state['df_results'] = df_results
            st.session_state['current_threshold'] = current_threshold

# הצגת התוצאות לאחר הריצה
if 'df_results' in st.session_state:
    df_results = st.session_state['df_results']
    current_threshold = st.session_state['current_threshold']
    
    st.header("💡 סיכום כללי")
    st.dataframe(df_results, use_container_width=True)
    
    # סינון התראות
    alert_cols = [col for col in df_results.columns if 'התראה' in col]
    
    # מסנן את השורות שבהן יש התראה (שאינה "בטווח" או "אין נתון")
    df_alerts = df_results[~df_results['התראה'].isin(["בטווח", "אין נתון"])]

    
    st.header("🚨 התראות פער מחיר משמעותי")
    
    if not df_alerts.empty:
        st.warning(f"נמצאו {len(df_alerts)} התראות שחצו את סף ה-{int(current_threshold*100)}%:")
        
        # הדגשת שורות ב-DataFrame של ההתראות
        def highlight_alerts(row):
            style = [''] * len(row)
            if row['התראה'].startswith('יקר'):
                # המחיר שלנו יקר מדי (מצריך הורדת מחיר אצלנו)
                style = ['background-color: #ffcccc'] * len(row) 
            elif row['התראה'].startswith('זול'):
                # המחיר שלנו זול מדי (מצריך העלאת מחיר אצלנו)
                style = ['background-color: #ccffcc'] * len(row)
            return style

        st.dataframe(
            df_alerts.style.apply(highlight_alerts, axis=1),
            use_container_width=True
        )
    else:
        st.success("כל המחירים בטווח התחרותי! אין התראות חדשות.")

# רגל דף
st.markdown("---")
st.caption("שים לב: פרויקט זה דורש תחזוקה והתאמה מתמדת של פונקציות ה-Scraping בהתאם לשינויים באתרי המתחרים.")

# --- סיום קוד app.py ---
