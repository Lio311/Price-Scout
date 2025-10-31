def search_and_scrape_ksp(query):
    """
    מבצע חיפוש ב-KSP באמצעות Selenium בלבד.
    """
    if not DRIVER:
        return None

    search_query = query.replace(' ', '+')
    search_url = f"{COMPETITORS['KSP']}web/search/index.aspx?search={search_query}"
    
    try:
        # פתיחת הדף באמצעות Selenium (כך עוקפים את 403)
        DRIVER.get(search_url)
        time.sleep(3) # המתנה לטעינת התוכן

        # בדיקה אם האתר הפנה לעמוד חסימה (CAPTCHA)
        if "captcha" in DRIVER.current_url.lower():
            st.warning("⚠️ KSP חסם את הבקשה ודורש אימות CAPTCHA. הניתוח נכשל.")
            return None
        
        # שימוש ב-BeautifulSoup על התוכן ש-Selenium טען
        soup = BeautifulSoup(DRIVER.page_source, 'html.parser')
        
        # *** סלקטורים לדוגמה (צריך לוודא שהם עדיין נכונים): ***
        # ניסיון למצוא מחיר בתוך כרטיס המוצר הראשון
        # זהו הסלקטור הנפוץ ביותר ב-KSP לכרטיס מוצר:
        price_tag = soup.find('div', class_='ProductCardPrice')
        
        if price_tag:
            # מנקה וממיר למספר (מייצרים סלקטור יותר ספציפי למחיר)
            price_element = price_tag.find('div', class_='price-label-text')
            if price_element:
                price_text = price_element.text.strip()
                clean_price = re.sub(r'[^\d]', '', price_text)
                return int(clean_price)
            
        return None # לא נמצא מחיר
        
    except Exception as e:
        # כאן תופיע רק שגיאת סלניום או שגיאה כללית, לא 403 של HTTP.
        st.warning(f"שגיאת Scraping ב-KSP עבור {query}: {e}")
        return None
