import requests
from bs4 import BeautifulSoup
import re
import time
from collections import defaultdict
import concurrent.futures
import threading

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Thread-local storage for proxy
thread_local = threading.local()

def get_session(proxy=None):
    if not hasattr(thread_local, "session"):
        if proxy:
            proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
            thread_local.session = requests.Session()
            thread_local.session.proxies.update(proxies)
        else:
            thread_local.session = requests.Session()
    return thread_local.session

def update_progress(progress_bar, status_text, current, total, message):
    progress = float(current) / float(total)
    progress_bar.progress(progress)
    status_text.text(message)

def get_total_pages(address, proxy=None):
    session = get_session(proxy)
    url = f"https://etherscan.io/tokentxns?a={address}&ps=100&p=1"
    
    try:
        response = session.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"❌ Failed to fetch total pages for {address}.")
            return 1

        soup = BeautifulSoup(response.text, "html.parser")
        pagination = soup.find("span", class_="page-link text-nowrap")

        if pagination:
            match = re.search(r"Page \d+ of (\d+)", pagination.text)
            if match:
                return int(match.group(1))
    except Exception as e:
        print(f"Error fetching pages for {address}: {e}")
    
    return 1

def scrape_page(address, page, max_transactions, proxy=None):
    session = get_session(proxy)
    url = f"https://etherscan.io/tokentxns?a={address}&ps=100&p={page}"
    
    try:
        response = session.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"⚠ Failed to fetch page {page} for {address}. Skipping.")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")

        if not table:
            print(f"⚠ No transaction table found on page {page}.")
            return []

        rows = table.find_all("tr")[1:]
        transactions = []
        unique_from_addresses = set()

        for row in rows:
            if len(transactions) >= max_transactions:
                break

            cols = row.find_all("td")
            if len(cols) < 9:
                continue

            txn_link_elem = cols[1].find("a")
            txn_hash = txn_link_elem.text.strip() if txn_link_elem else "N/A"
            txn_link = f"https://etherscan.io{txn_link_elem['href']}" if txn_link_elem else "N/A"

            in_out_status_elem = cols[8].find("span")
            in_out_status = in_out_status_elem.text.strip() if in_out_status_elem else "N/A"

            from_addr_elem = cols[7].find("a")
            from_address = from_addr_elem["href"].split("/")[-1] if from_addr_elem else "N/A"
            from_address = from_address.replace("#tokentxns", "")
            
            if from_address in unique_from_addresses:
                continue
            unique_from_addresses.add(from_address)

            method_elem = cols[6].find("span")
            method = method_elem.text.strip() if method_elem else "N/A"
            
            if method.lower() == "execute":
                continue

            transactions.append({
                "Wallet Address": address,
                "Txn Hash": txn_hash,
                "Txn Link": txn_link,
                "Status": in_out_status,
                "From Address": from_address,
                "Method": method
            })

        return transactions
    except Exception as e:
        print(f"Error scraping page {page} for {address}: {e}")
        return []

def scrape_transactions_for_wallet(address, max_transactions, progress_bar, status_text, proxy=None):
    total_pages = get_total_pages(address, proxy)
    # update_progress(progress_bar, status_text, 0, total_pages, 
    #                f"🔍 {address}: Found {total_pages} pages")

    transactions = []
    unique_from_addresses = set()

    # Determine max concurrent threads (adjust as needed)
    max_threads = min(50, 60)  # Limit to 10 concurrent threads

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        # Scrape pages from latest to earliest
        future_to_page = {
            executor.submit(scrape_page, address, page, max_transactions, proxy): page 
            for page in range(total_pages, 0, -1)
        }

        for future in concurrent.futures.as_completed(future_to_page):
            page = future_to_page[future]
            try:
                page_transactions = future.result()
                
                for txn in page_transactions:
                    # Avoid duplicates
                    if txn['From Address'] not in unique_from_addresses and len(transactions) < max_transactions:
                        transactions.append(txn)
                        unique_from_addresses.add(txn['From Address'])

                # update_progress(progress_bar, status_text, total_pages - page + 1, total_pages,
                #                f"📄 Processed Page {page} for {address}")
                
                if len(transactions) >= max_transactions:
                    break
            except Exception as e:
                print(f"Error processing page {page}: {e}")

    return transactions

def scrape_multiple_wallets(wallet_addresses, max_transactions, progress_bar, status_text, proxy=None):
    wallet_from_addresses = defaultdict(set)
    all_transactions = []

    for idx, wallet in enumerate(wallet_addresses):
        update_progress(progress_bar, status_text, idx + 1, len(wallet_addresses),
                        f"Processing wallet {idx + 1} of {len(wallet_addresses)}: {wallet}")
        
        wallet_transactions = scrape_transactions_for_wallet(
            wallet, max_transactions, progress_bar, status_text, proxy
        )
        all_transactions.extend(wallet_transactions)

        for txn in wallet_transactions:
            wallet_from_addresses[txn["From Address"]].add(wallet)

    # Filter common_from_addresses
    common_from_addresses = {addr: wallets for addr, wallets in wallet_from_addresses.items() if len(wallets) > 1}

    # Drop the first row from common_from_addresses
    if common_from_addresses:
        common_from_addresses = dict(list(common_from_addresses.items())[1:])

    return all_transactions, common_from_addresses
