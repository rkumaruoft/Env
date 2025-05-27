import os
import hashlib

# ─── Configuration ─────────────────────────────────────────────────────────────
INPUT_PATH  = "/set/your/directory"
OUTPUT_FILE = "existing_hashes.txt"

# ─── Hash computation ───────────────────────────────────────────────────────────
def compute_sha256(path):
    """Compute SHA256 hash of a file at the given path."""
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

# ─── Gather PDF paths ──────────────────────────────────────────────────────────
def gather_pdf_paths(input_path):
    """Collect PDF file paths from a directory, single PDF, or list-file."""
    pdf_paths = []
    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for fname in files:
                if fname.lower().endswith('.pdf'):
                    pdf_paths.append(os.path.join(root, fname))
    elif os.path.isfile(input_path):
        if input_path.lower().endswith('.pdf'):
            pdf_paths.append(input_path)
        else:
            with open(input_path, 'r') as f:
                for line in f:
                    p = line.strip()
                    if p.lower().endswith('.pdf') and os.path.isfile(p):
                        pdf_paths.append(p)
    else:
        raise FileNotFoundError(f"Input '{input_path}' is not a valid file or directory.")
    return pdf_paths

# ─── Main logic ─────────────────────────────────────────────────────────────────
def main():
    pdf_paths = gather_pdf_paths(INPUT_PATH)
    if not pdf_paths:
        print("No PDF files found to hash.")
        return

    with open(OUTPUT_FILE, 'w') as out_f:
        for path in pdf_paths:
            hash_hex = compute_sha256(path)
            out_f.write(hash_hex + "\n")

    print(f"✔️ Computed hashes for {len(pdf_paths)} PDF(s) and wrote to '{OUTPUT_FILE}'")

if __name__ == '__main__':
    main()