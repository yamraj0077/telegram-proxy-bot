import time
import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def scrape_mtpro():
    print("Starting Headless Chrome...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        # webdriver-manager automatically handles Chrome installation/matching for GitHub runners
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print("Error starting Chrome:", e)
        return

    print("Accessing mtpro.xyz...")
    driver.get('https://mtpro.xyz/mtproto')
    
    print("Waiting 15 seconds for Javascript obfuscation...")
    time.sleep(15)

    print("Extracting proxies...")
    html = driver.page_source
    links = re.findall(r'(tg://proxy\?[^\x22\x27>]+)', html)
    clean_links = [link.replace('&amp;', '&') for link in links]
    unique_links = list(set(clean_links))
    print(f"Successfully extracted {len(unique_links)} active proxies.")
    
    driver.quit()
    
    if len(unique_links) > 0:
        filename = "mtpro_proxies.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            for link in unique_links:
                f.write(link + '\n')
        print("Proxies saved.")
    else:
        print("No proxies found today.")

if __name__ == "__main__":
    scrape_mtpro()
