import os
import time
import argparse
import requests
import shutil
import base64  # Added for decoding PDF data
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin
from pypdf import PdfWriter
from concurrent.futures import ThreadPoolExecutor

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Webpage scraper and PDF generator")
parser.add_argument("url", type=str, help="Website URL to scrape")
parser.add_argument("--threads", type=int, default=5, help="Number of threads (default: 5)")
args = parser.parse_args()

# Website URL from command-line
url = args.url
num_threads = args.threads  # Number of threads for parallel processing

# Set headers to mimic a browser
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Fetch the webpage
try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    print("✅ Website fetched successfully!")

    # Parse the HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract unique absolute URLs
    links = {urljoin(url, a['href']) for a in soup.find_all('a', href=True)}

    if not links:
        print("❌ No links found. Exiting.")
        exit()

    # Save links to a text file in sorted order
    text_file = "website_links.txt"
    with open(text_file, "w", encoding="utf-8") as file:
        file.write("\n".join(sorted(links)))

    print(f"🔗 Links saved to '{text_file}'")

except requests.exceptions.RequestException as e:
    print(f"❌ Error fetching website: {e}")
    exit()

# Read links from the text file into a sorted list
with open(text_file, "r", encoding="utf-8") as file:
    links = [line.strip() for line in file.readlines() if line.strip()]

print(f"📄 Extracted {len(links)} links from '{text_file}'.")

# Folder for PDFs
pdf_folder = "pdf_pages"
os.makedirs(pdf_folder, exist_ok=True)

# Configure Chrome in headless mode
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")

# Function to process each webpage and save as PDF
def process_page(index, link):
    """Processes a single webpage and saves it as a PDF."""
    pdf_file = os.path.join(pdf_folder, f"page_{index}.pdf")

    try:
        print(f"📄 Processing ({index}/{len(links)}): {link}")

        # Start a new WebDriver instance
        driver = webdriver.Chrome(options=chrome_options)
        # driver = uc.Chrome(headless=True)
        driver.get(link)

        # Wait until page fully loads
        try:
            WebDriverWait(driver, 10).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)  # Extra buffer for lazy-loaded content

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        except Exception as e:
            print(f"⚠️ Timeout waiting for page to load: {link} - {e}")
            driver.quit()
            return None

        # Use Chrome DevTools Protocol to print to PDF
        try:
            pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {
                "printBackground": True,
                "transferMode": "ReturnAsBase64",
                "preferCSSPageSize": True, # Use the page’s CSS-defined size
                "scale": 1.0
            })
        except Exception as e:
            print(f"❌ Failed to generate PDF for {link}: {e}")
            driver.quit()
            return None

        # Decode and save the PDF content
        try:
            pdf_content = base64.b64decode(pdf_data['data'])
            with open(pdf_file, 'wb') as f:
                f.write(pdf_content)
        except Exception as e:
            print(f"❌ Failed to save PDF for {link}: {e}")
            driver.quit()
            return None

        # Verify PDF was saved
        if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 0:
            print(f"✅ PDF saved: {pdf_file}")
            driver.quit()
            return pdf_file
        else:
            print(f"❌ Empty PDF file for {link}")
            driver.quit()
            return None

    except Exception as e:
        print(f"❌ Error processing {link}: {e}")
        return None

# Process all links using multithreading
pdf_files = []
with ThreadPoolExecutor(max_workers=num_threads) as executor:
    # Submit tasks with index and link, preserving order
    futures = [executor.submit(process_page, index + 1, link) for index, link in enumerate(links)]
    for future in futures:
        result = future.result()
        if result:
            pdf_files.append(result)

# Get all PDF files sorted by index
pdf_files = sorted(pdf_files, key=lambda x: int(os.path.splitext(os.path.basename(x))[0].split('_')[1]))

# Merge PDFs if any were generated
if pdf_files:
    try:
        writer = PdfWriter()
        for pdf in pdf_files:
            writer.append(pdf)

        output_file = "merged.pdf"
        writer.write(output_file)
        writer.close()

        print(f"✅ Merged PDF saved as: {output_file}")

        # Cleanup individual PDFs
        shutil.rmtree(pdf_folder, ignore_errors=True)
        print(f"🗑️ Deleted folder: {pdf_folder}")

    except Exception as e:
        print(f"❌ Error merging PDFs: {e}")
else:
    print("❌ No PDFs found to merge.")

# Delete the links file
if os.path.exists(text_file):
    os.remove(text_file)
    print("🗑️ Deleted website_links.txt")

print("\n✅ Process completed!")