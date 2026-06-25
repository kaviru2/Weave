import os
import pypdf

output_dir = "downloaded_papers"
pdf_files = sorted([f for f in os.listdir(output_dir) if f.endswith(".pdf")])

for filename in pdf_files:
    pdf_path = os.path.join(output_dir, filename)
    txt_path = os.path.join(output_dir, filename.replace(".pdf", "_text.txt"))
    
    if os.path.exists(txt_path):
        print(f"[SKIP] Text already extracted for {filename}")
        continue
        
    print(f"[EXTRACTING] {filename}...")
    try:
        reader = pypdf.PdfReader(pdf_path)
        
        # Extract first 2 pages to capture Title, Authors, Abstract, and Introduction
        num_pages_to_extract = min(2, len(reader.pages))
        extracted_text = []
        for i in range(num_pages_to_extract):
            page_text = reader.pages[i].extract_text()
            if page_text:
                extracted_text.append(f"--- PAGE {i+1} ---\n" + page_text)
                
        full_text = f"=== FILE: {filename} ===\n\n" + "\n\n".join(extracted_text)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"[SUCCESS] Extracted to {txt_path}")
    except Exception as e:
        print(f"[FAILED] Could not extract {filename}: {e}")

print("\nDone extracting text.")
