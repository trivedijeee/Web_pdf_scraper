from pypdf import PdfReader, PdfWriter

def manipulate_pdfs():
    writer = PdfWriter()

    # 1. Pehli file ko handle karein safely
    try:
        reader1 = PdfReader("divine1.pdf")
        total_pages = len(reader1.pages)
        
        # Agar file mein 16 se kam pages hain, toh crash hone ki jagah 
        # ye sirf available pages lega (min function use karke)
        pages_to_extract = min(16, total_pages)
        
        print(f"Extracting {pages_to_extract} pages from file1.pdf...")
        for page_num in range(0, pages_to_extract): 
            writer.add_page(reader1.pages[page_num])
    except FileNotFoundError:
        print("Error: file1.pdf nahi mili!")
        return

    # 2. Baki files ko add karein
    for file_name in ["divine2.pdf", "divine3.pdf"]:
        try:
            reader = PdfReader(file_name)
            print(f"Merging {file_name}...")
            for page in reader.pages:
                writer.add_page(page)
        except FileNotFoundError:
            print(f"Warning: {file_name} missing, skipping...")

    # Final result save karein
    output_filename = "final_automation.pdf"
    with open(output_filename, "wb") as output_pdf:
        writer.write(output_pdf)
    
    print(f"\nSuccess! File saved as: {output_filename}")

if __name__ == "__main__":
    manipulate_pdfs()
