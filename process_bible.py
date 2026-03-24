import os
import zipfile
import json
import re
import argparse
import html
from pathlib import Path

def clean_text(text):
    # Remove HTML tags, unescape entities, and clean whitespace
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    # Remove things like "1 ", "2 " at beginning
    text = re.sub(r'^\d+\s+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def process_bible(zip_filename):
    bible_id = os.path.splitext(zip_filename)[0]

    # Paths
    script_dir = Path(__file__).parent.resolve()
    zipped_dir = script_dir / "zipped-bibles"
    unzipped_root = script_dir / "unzipped-bibles"
    json_root = script_dir / "json-bibles"

    zip_path = zipped_dir / zip_filename
    if not zip_path.exists():
        print(f"Error: {zip_path} does not exist.")
        return

    # Ensure directories exist
    unzipped_root.mkdir(exist_ok=True)
    json_root.mkdir(exist_ok=True)

    # 1. Unzip
    print(f"Unzipping {zip_path} to {unzipped_root}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(unzipped_root)

    # Looking for extracted folder: if zip contains a root folder, use it
    extracted_dir = unzipped_root / bible_id
    if not extracted_dir.exists():
        # Fallback for filenames with (1) etc.
        folders = [d for d in unzipped_root.iterdir() if d.is_dir() and d.name in zip_ref.namelist()[0].split('/')[0]]
        if folders:
            extracted_dir = folders[0]
        else:
            # Check for index.htm in unzipped_root
            if (unzipped_root / "index.htm").exists():
                extracted_dir = unzipped_root
            else:
                print(f"Warning: Extracted dir {extracted_dir} not found.")

    # 2. Extract book names from index.htm
    book_names = {}
    index_file = extracted_dir / "index.htm"
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # href="01/1.htm">Mwanzo</a>
            matches = re.findall(r'href="(\d+)/1\.htm"[^>]*>(.*?)</a>', content)
            for m_num, m_name in matches:
                book_names[m_num] = clean_text(m_name)

    # 3. Process books
    bible_collection = []

    # Get sorted book directories (01, 02...)
    book_dirs = sorted([d for d in extracted_dir.iterdir() if d.is_dir() and d.name.isdigit()])

    for b_dir in book_dirs:
        book_num_str = b_dir.name
        book_num = str(int(book_num_str)) # "01" -> "1"

        book_name = book_names.get(book_num_str)

        chapters = []
        # Get sorted chapter files (1.htm, 2.htm...)
        chapter_files = sorted([f for f in b_dir.glob("*.htm*") if f.stem.isdigit()],
                               key=lambda x: int(x.stem))

        for c_file in chapter_files:
            c_num = c_file.stem

            with open(c_file, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()

            # If book name wasn't in index, try getting it from <h1>
            if not book_name:
                h1_match = re.search(r'<h1>(.*?)</h1>', html_content)
                if h1_match:
                    book_name = clean_text(h1_match.group(1))

            verses = []

            # Use regex to find verses. Looking at example structure:
            # <span class="verse" id="1">1 </span>Hapo mwanzo...
            # The next verse is after <br /> or next <span class="verse"

            # Find all verse spans
            v_matches = re.findall(r'<span class="verse" id="(\d+)">.*?</span>(.*?)(?=<span class="verse"|<br />|</p>|</div>)', html_content, re.DOTALL)

            for v_id, v_text in v_matches:
                v_text_clean = clean_text(v_text)
                if v_text_clean:
                    verses.append({
                        "verse_number": v_id,
                        "verse_text": v_text_clean
                    })

            if chapters or verses: # Keep chapter if it has verses
                chapters.append({
                    "chapter_number": c_num,
                    "verses": verses
                })

        if chapters:
            bible_collection.append({
                "book_number": book_num,
                "book_name": book_name or f"Book {book_num}",
                "chapters": chapters
            })

    # The expected output should have the bible_id as the top level key
    # but based on prompt example: "bible_name" is a key containing an array.
    # Actually prompt says: i need each bible json file to be like: { "bible_name": [ ... ] }
    # where "bible_name" is actually the literal name of the bible like "sw_new"

    final_output = {bible_id: bible_collection}

    output_json_path = json_root / f"{bible_id}.json"
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)

    print(f"DONE! Output in: {output_json_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process Bible ZIP files into JSON.')
    parser.add_argument('file', help='The bible filename.zip in zipped-bibles/')
    args = parser.parse_args()

    process_bible(args.file)
