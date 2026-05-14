import time
import re
import socket
import base64
import requests
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

GITHUB_TOKEN = "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"
REPO = "yamraj0077/telegram-proxy-bot"
FILE_PATH = "mtpro_proxies.txt"

def get_github_file():
    print(f"Fetching existing proxies from GitHub ({REPO})...")
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        content = base64.b64decode(data['content']).decode('utf-8')
        sha = data['sha']
        proxies = [line.strip() for line in content.split('\n') if line.strip()]
        print(f"Found {len(proxies)} existing proxies on GitHub.")
        return proxies, sha
    elif response.status_code == 404:
        print("File not found on GitHub. A new one will be created.")
        return [], None
    else:
        print(f"Error fetching from GitHub: {response.status_code} {response.text}")
        return [], None

def update_github_file(proxies, sha):
    print("Uploading verified proxies back to GitHub...")
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    content = "\n".join(proxies) + "\n"
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": f"Auto-update: {len(proxies)} verified proxies",
        "content": encoded_content
    }
    if sha:
        data["sha"] = sha
        
    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        print(f"Successfully pushed {len(proxies)} proxies to GitHub!")
    else:
        print(f"Failed to push to GitHub: {response.status_code} {response.text}")

def check_proxy(proxy_link):
    try:
        url_part = proxy_link.split('|')[0]
        parsed = urlparse(url_part)
        qs = parse_qs(parsed.query)
        if 'server' in qs and 'port' in qs:
            host = qs['server'][0]
            port = int(qs['port'][0])
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            try:
                s.connect((host, port))
                s.close()
                return proxy_link
            except Exception:
                pass
    except Exception:
        pass
    return None

def verify_proxies(proxies):
    print(f"Verifying {len(proxies)} proxies via TCP Ping...")
    working = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(check_proxy, proxies))
    for r in results:
        if r:
            working.append(r)
    print(f"Verification complete: {len(working)} proxies are online.")
    return working

def scrape_all():
    # Fetch existing proxies first
    existing_proxies, sha = get_github_file()

    print("Starting Headless Chrome...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print("Error starting Chrome:", e)
        return

    scraped_proxies = []

    # 1. Scrape MTProto Proxies from mtpro.xyz
    print("Accessing mtpro.xyz...")
    driver.get('https://mtpro.xyz/mtproto')
    
    print("Waiting 15 seconds for Javascript obfuscation...")
    time.sleep(15)

    print("Extracting MTProto proxies...")
    html = driver.page_source
    
    # Try to extract with country code first
    matches = re.findall(r'href="(tg://proxy\?[^"]+)".*?country:\s*\'([A-Z]{2})\'', html)
    mtproto_proxies = []
    
    if matches:
        for link, country in matches:
            clean_link = link.replace('&amp;', '&')
            mtproto_proxies.append(f"{clean_link}|{country}")
    else:
        links = re.findall(r'(tg://proxy\?[^\x22\x27><]+)', html)
        mtproto_proxies = [link.replace('&amp;', '&') for link in links]
        
    mtproto_proxies = list(set(mtproto_proxies))
    scraped_proxies.extend(mtproto_proxies)
    print(f"Successfully extracted {len(mtproto_proxies)} active MTProto proxies.")

    # 2. Scrape SOCKS5 Proxies from proxyservers.pro
    print("Accessing proxyservers.pro...")
    for page in range(1, 6):
        print(f"Scraping SOCKS5 Page {page}...")
        url = f'https://proxyservers.pro/proxy/list/protocol/socks/order/updated/order_dir/desc/page/{page}'
        driver.get(url)
        time.sleep(5)
        
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, 'tr[valign="top"]')
            for r in rows:
                try:
                    ip = r.find_element(By.CSS_SELECTOR, 'a').text.strip()
                    port = r.find_element(By.CSS_SELECTOR, 'span.port').text.strip()
                    img_src = r.find_element(By.CSS_SELECTOR, 'img.icon-flag').get_attribute('src')
                    
                    country_match = re.search(r'\/([a-z]{2})\.png', img_src)
                    country = country_match.group(1).upper() if country_match else ""
                    
                    if ip and port:
                        socks_link = f"tg://socks?server={ip}&port={port}"
                        if country:
                            socks_link += f"|{country}"
                        scraped_proxies.append(socks_link)
                except Exception as e:
                    continue
        except Exception as e:
            print(f"Error extracting from page {page}")

    driver.quit()
    
    # 3. Merge and deduplicate
    all_unique_proxies = list(set(existing_proxies + scraped_proxies))
    print(f"Total unique proxies combined: {len(all_unique_proxies)}")
    
    # 4. Verify all proxies
    verified_proxies = verify_proxies(all_unique_proxies)
    
    # 5. Save locally and upload
    if len(verified_proxies) > 0:
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            for link in verified_proxies:
                f.write(link + '\n')
        print(f"Local file {FILE_PATH} updated.")
        
        update_github_file(verified_proxies, sha)
    else:
        print("No verified proxies found to upload.")

if __name__ == "__main__":
    scrape_all()
