import os
import time
import argparse
import shutil
import base64
import logging
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfWriter

# -------------------- LOGGING --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# -------------------- ARGUMENTS --------------------
parser = argparse.ArgumentParser(description="Web Scraper + PDF Generator")
parser.add_argument("url", help="Website URL")
parser.add_argument("--threads", type=int, default=2, help="Max threads (recommended: 2)")
args = parser.parse_args()

BASE_URL = args.url
MAX_THREADS = args.threads
BASE_DOMAIN = urlparse(BASE_URL).netloc

# -------------------- BLOCKED SOCIAL DOMAINS --------------------
BLOCKED_DOMAINS = [
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "wa.me",
    "t.me"
]

# -------------------- HELPERS --------------------
def clean_url(u: str) -> str:
    return u.split("?")[0].rstrip("/")

def same_domain(u: str) -> bool:
    return urlparse(u).netloc == BASE_DOMAIN

def is_blocked_domain(u: str) -> bool:
    domain = urlparse(u).netloc.lower()
    return any(b in domain for b in BLOCKED_DOMAINS)

# -------------------- FETCH LINKS --------------------
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36"
}

logging.info(f"Base domain detected: {BASE_DOMAIN}")

try:
    response = requests.get(BASE_URL, headers=headers, timeout=15)
    response.raise_for_status()
except Exception as e:
    logging.error(f"Failed to fetch site: {e}")
    exit(1)

soup = BeautifulSoup(response.text, "html.parser")

links = set()
for a in soup.find_all("a", href=True):
    full_url = clean_url(urljoin(BASE_URL, a["href"]))

    if not full_url.startswith("http"):
        continue
    if not same_domain(full_url):
        continue
    if is_blocked_domain(full_url):
        continue

    links.add(full_url)

if not links:
    logging.error("No valid internal links found")
    exit(1)

links = sorted(links)
logging.info(f"Total pages found: {len(links)}")

# -------------------- SELENIUM SETUP --------------------
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

PDF_DIR = "pdf_pages"
os.makedirs(PDF_DIR, exist_ok=True)

# -------------------- PAGE TO PDF --------------------
def save_page_as_pdf(index, link):
    pdf_path = os.path.join(PDF_DIR, f"page_{index}.pdf")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        logging.info(f"[{index}] Opening: {link}")
        driver.get(link)

        if is_blocked_domain(driver.current_url):
            logging.warning(f"[{index}] Redirected to blocked domain")
            return None

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # -------- FIX TEXT OVERLAP --------
        driver.execute_script("""
            document.body.style.zoom = '100%';

            var style = document.createElement('style');
            style.innerHTML = `
                * {
                    animation: none !important;
                    transition: none !important;
                }
                header, footer, nav, aside {
                    display: none !important;
                }
                * {
                    position: static !important;
                }
            `;
            document.head.appendChild(style);
        """)

        # Infinite scroll
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # -------- PRINT TO PDF (A4 SAFE SETTINGS) --------
        pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "preferCSSPageSize": False,
            "paperWidth": 8.27,      # A4
            "paperHeight": 11.69,    # A4
            "marginTop": 0.4,
            "marginBottom": 0.4,
            "marginLeft": 0.4,
            "marginRight": 0.4,
            "scale": 0.9,
            "transferMode": "ReturnAsBase64"
        })

        with open(pdf_path, "wb") as f:
            f.write(base64.b64decode(pdf_data["data"]))

        logging.info(f"[{index}] PDF saved successfully")
        return pdf_path

    except Exception as e:
        logging.error(f"[{index}] Failed: {e}")
        return None

    finally:
        driver.quit()

# -------------------- MULTITHREADING --------------------
pdf_files = []

with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
    futures = [
        executor.submit(save_page_as_pdf, i + 1, link)
        for i, link in enumerate(links)
    ]

    for future in futures:
        result = future.result()
        if result:
            pdf_files.append(result)

# -------------------- MERGE PDFs --------------------
if not pdf_files:
    logging.error("No PDFs generated")
    exit(1)

pdf_files.sort(key=lambda x: int(os.path.basename(x).split("_")[1].split(".")[0]))

writer = PdfWriter()
for pdf in pdf_files:
    try:
        writer.append(pdf)
    except Exception:
        logging.warning(f"Skipping corrupt PDF: {pdf}")

output_pdf = "merged.pdf"
writer.write(output_pdf)
writer.close()

logging.info(f"Merged PDF created: {output_pdf}")

# -------------------- CLEANUP --------------------
shutil.rmtree(PDF_DIR, ignore_errors=True)
logging.info("Temporary PDF files deleted")

logging.info("✅ PROCESS COMPLETED SUCCESSFULLY")
