import time
import re
import socket
import base64
import requests
import json
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

GITHUB_TOKEN = "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"
REPO = "yamraj0077/telegram-proxy-bot"
FILE_PATH = "mtpro_proxies.txt"

def get_github_file():
    print(f"Fetching existing proxies from GitHub ({REPO})...")
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
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
    except Exception as e:
        print(f"Network error fetching from GitHub: {e}")
        return [], None

def update_github_file(proxies, sha_ignored):
    print("Uploading verified proxies back to GitHub...")
    
    # Re-fetch SHA to avoid 409 Conflict
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        current_sha = None
        get_res = requests.get(url, headers=headers, timeout=15)
        if get_res.status_code == 200:
            current_sha = get_res.json().get('sha')
        
        content = "\n".join(proxies) + "\n"
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        data = {
            "message": f"Auto-update: {len(proxies)} verified proxies",
            "content": encoded_content
        }
        if current_sha:
            data["sha"] = current_sha
            
        response = requests.put(url, headers=headers, json=data, timeout=15)
        if response.status_code in [200, 201]:
            print(f"Successfully pushed {len(proxies)} proxies to GitHub!")
        else:
            print(f"Failed to push to GitHub: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Network error pushing to GitHub: {e}")

def check_proxy(proxy_link):
    """
    Improved proxy check function:
    1. Uses socket.getaddrinfo for better DNS/IP resolution.
    2. Averages latency over 2 samples if stable.
    3. Faster failure detection.
    """
    try:
        url_part = proxy_link.split('|')[0]
        country_part = proxy_link.split('|')[1] if '|' in proxy_link else ""
        
        # Filter out Iran proxies as they are often national intranet honeypots returning false positive TCP pings
        if country_part == 'IR':
            return (proxy_link, 9999)
            
        parsed = urlparse(url_part)
        qs = parse_qs(parsed.query)
        if 'server' not in qs or 'port' not in qs:
            return (proxy_link, 9999)
            
        host = qs['server'][0]
        port = int(qs['port'][0])
        
        latencies = []
        for _ in range(2): # Sample 2 times for stability
            start = time.time()
            try:
                # Use getaddrinfo to handle IPv4/IPv6 and DNS more robustly
                addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                for res in addr_info:
                    af, socktype, proto, canonname, sa = res
                    s = socket.socket(af, socktype, proto)
                    s.settimeout(4.0) 
                    try:
                        s.connect(sa)
                        s.close()
                        latencies.append(int((time.time() - start) * 1000))
                        break # Success on this attempt
                    except:
                        s.close()
                        continue
            except Exception:
                pass
            
            if not latencies: # If even one attempt fails, wait and retry or fail
                time.sleep(0.5)
        
        if latencies:
            avg_latency = sum(latencies) // len(latencies)
            return (proxy_link, avg_latency)
            
    except Exception as e:
        pass
    return (proxy_link, 9999)

def verify_proxies(proxies):
    print(f"Verifying {len(proxies)} proxies via TCP Ping...")
    working = {} # Use dict to store proxy_link: latency
    with ThreadPoolExecutor(max_workers=100) as executor:
        results = list(executor.map(check_proxy, proxies))
    for link, latency in results:
        if latency < 9999:
            working[link] = latency
    print(f"Verification complete: {len(working)} proxies are online.")
    return working

def scrape_all():
    # Fetch existing proxies first
    existing_proxies, sha = get_github_file()

    print("Starting Headless Chrome...")
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        print("Starting Chrome Browser natively (relying on Selenium Manager)...")
        driver = webdriver.Chrome(options=options)
        print("Chrome started successfully.")
    except Exception as e:
        print("Error starting Chrome:", e)
        import traceback
        traceback.print_exc()
        return

    scraped_proxies = []

    # 1. Scrape MTProto Proxies from mtpro.xyz
    try:
        print("Accessing mtpro.xyz...")
        driver.get('https://mtpro.xyz/mtproto')
        
        print("Waiting 15 seconds for Javascript obfuscation...")
        time.sleep(15)

        print("Extracting MTProto proxies...")
        html = driver.page_source
        
        # Try to extract with country code first
        matches = re.findall(r'href="(tg://proxy\?[^"]+)".*?country:\s*\'([A-Z]{2})\'', html)
        mtproto_proxies = []
        
        promo_params = "&bot=@yamproxybot&channel=@yamproxy"
        
        if matches:
            for link, country in matches:
                clean_link = link.replace('&amp;', '&')
                if "@yamproxy" not in clean_link:
                    clean_link += promo_params
                mtproto_proxies.append(f"{clean_link}|{country}")
        else:
            links = re.findall(r'(tg://proxy\?[^\x22\x27><]+)', html)
            for link in links:
                clean_link = link.replace('&amp;', '&')
                if "@yamproxy" not in clean_link:
                    clean_link += promo_params
                mtproto_proxies.append(clean_link)
            
        mtproto_proxies = list(set(mtproto_proxies))
        scraped_proxies.extend(mtproto_proxies)
        print(f"Successfully extracted {len(mtproto_proxies)} active MTProto proxies.")
    except Exception as e:
        print("Error scraping mtpro.xyz:", e)

    # 2. Scrape SOCKS5 Proxies from proxyservers.pro
    print("Accessing proxyservers.pro...")
    for page in range(1, 6):
        print(f"Scraping SOCKS5 Page {page}...")
        url = f'https://proxyservers.pro/proxy/list/protocol/socks/order/updated/order_dir/desc/page/{page}'
        try:
            driver.get(url)
            time.sleep(5)
        except Exception as e:
            print(f"Error loading proxyservers.pro page {page}: {e}")
            continue
        
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

    try:
        driver.quit()
        print("Chrome closed successfully.")
    except Exception as e:
        print("Error closing Chrome:", e)
    
    # 3. Merge, deduplicate, and apply promotional parameters
    raw_proxies = list(set(existing_proxies + scraped_proxies))
    all_unique_proxies = []
    
    for proxy in raw_proxies:
        if "tg://proxy" in proxy:
            # Handle both formats: link|CC and just link
            cc = ""
            link = proxy
            if "|" in proxy:
                link, cc = proxy.split('|', 1)
            
            # Remove any existing bot/channel params
            clean_link = re.sub(r'[&?]bot=[^&]*', '', link)
            clean_link = re.sub(r'[&?]channel=[^&]*', '', clean_link)
            
            # Append our params
            # If there's no ? (unlikely for tg://proxy), add it
            if "?" not in clean_link:
                clean_link += "?"
            
            # Ensure it ends correctly
            if not clean_link.endswith("?") and not clean_link.endswith("&"):
                clean_link += "&"
            
            final_link = f"{clean_link}bot=yamproxybot&channel=yamproxy"
            
            if cc:
                all_unique_proxies.append(f"{final_link}|{cc}")
            else:
                all_unique_proxies.append(final_link)
        else:
            all_unique_proxies.append(proxy)
            
    print(f"Total unique proxies combined and rebranded: {len(all_unique_proxies)}")
    
    # 4. Verify all proxies
    verified_proxies = verify_proxies(all_unique_proxies)
    
    # 5. Save locally and upload
    if len(verified_proxies) > 0:
        links_only = sorted(verified_proxies.keys(), key=lambda x: verified_proxies[x])
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            for link in links_only:
                f.write(link + '\n')
        print(f"Local file {FILE_PATH} updated.")
        
        update_github_file(links_only, sha)
        
        # 6. Generate proxies_cache.json for the frontend
        print("Generating proxies_cache.json...")
        json_proxies = []
        for link, latency in verified_proxies.items():
            try:
                parts = link.split('|')
                url_part = parts[0]
                country = parts[1] if len(parts) > 1 else 'UN'
                
                parsed = urlparse(url_part)
                qs = parse_qs(parsed.query)
                
                proxy_type = 'mtproto' if (parsed.scheme == 'proxy' or 'proxy' in parsed.netloc or (not parsed.scheme and 'socks' not in parsed.netloc)) else 'socks'
                # Better detection based on URL prefix or query params
                if 'tg://proxy' in link or 't.me/proxy' in link:
                    proxy_type = 'mtproto'
                elif 'tg://socks' in link:
                    proxy_type = 'socks'
                
                host = qs.get('server', [''])[0]
                port = int(qs.get('port', [0])[0])
                secret = qs.get('secret', [''])[0]
                
                # Final check: MTProto must have a secret
                if proxy_type == 'mtproto' and not secret:
                    proxy_type = 'socks'
                bot = qs.get('bot', [''])[0]
                channel = qs.get('channel', [''])[0]
                
                if host and port:
                    json_proxies.append({
                        'country': country,
                        'host': host,
                        'port': port,
                        'secret': secret,
                        'ping': latency,
                        'type': proxy_type,
                        'bot': bot,
                        'channel': channel
                    })
            except:
                continue
        
        # Sort by latency for the JSON as well
        json_proxies.sort(key=lambda x: x['ping'])
        
        with open('proxies_cache.json', 'w', encoding='utf-8') as f:
            json.dump(json_proxies, f, indent=2)
        print("proxies_cache.json generated successfully.")
    else:
        print("No verified proxies found to upload.")

if __name__ == "__main__":
    try:
        scrape_all()
    except Exception as e:
        print("An unexpected fatal error occurred:")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
