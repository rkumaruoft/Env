import json
from DB_funcs import ClimateDB

if __name__ == "__main__":
    db = ClimateDB("climate_docs.db")

    # Get JSONL object (list of dicts)
    results = db.get_jsonl_object()

    # Optional: preview the first record
    if results:
        print("Sample record:\n", json.dumps(results[0], indent=2, ensure_ascii=False))
    else:
        print("No valid records found.")

    output_path = "nomic_upload.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for record in results:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(results)} records to {output_path}")
