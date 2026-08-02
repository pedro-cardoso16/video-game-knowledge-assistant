import glob
import json
import os
import re

def diagnose_parts(base_file_path: str):
    print(f"\n=========================================")
    print(f" Diagnosing: {base_file_path}")
    print(f"=========================================")

    parts = sorted(glob.glob(f"{base_file_path}*.part"))
    if not parts:
        print(f"❌ No matching part files found for '{base_file_path}*.part'")
        return

    print(f"Found {len(parts)} part files.\n")

    # 1. Check sequence and numbering continuity
    pattern = re.compile(r"(\d+)\.part$")
    indices = []
    for part in parts:
        match = pattern.search(part)
        if match:
            indices.append((int(match.group(1)), part))
        else:
            print(f"⚠️ Warning: Filename does not match standard digit pattern: {part}")

    if indices:
        indices.sort(key=lambda x: x[0])
        expected_next = 0
        for idx, filename in indices:
            if idx != expected_next:
                print(f"❌ SEQUENCE ERROR: Expected part index {expected_next:02d}, but found {filename} (Index {idx})")
            expected_next = idx + 1

    # 2. Check individual file sizes
    total_bytes = 0
    file_sizes = []

    for part in parts:
        size = os.path.getsize(part)
        total_bytes += size
        file_sizes.append(size)
        
        if size == 0:
            print(f"❌ CORRUPTED PART: {part} is 0 bytes (Empty file)!")
        elif size > 100 * 1024 * 1024:
            print(f"⚠️ OVERSIZED PART: {part} is {size / (1024*1024):.2f}MB (Exceeds GitHub 100MB limit)!")

    print(f"Total reassembled size would be: {total_bytes / (1024*1024):.2f} MB")

    # 3. Check JSON / line integrity across part boundaries
    print("\n--- Checking Part Boundaries & JSON Line Validity ---")
    
    for i, part in enumerate(parts):
        with open(part, "rb") as f:
            lines = f.readlines()
        
        if not lines:
            continue
            
        first_line = lines[0].strip()
        last_line = lines[-1].strip()

        # Try parsing first and last lines as JSON if base_file_path ends in .jsonl
        if base_file_path.endswith(".jsonl"):
            # Validate first line
            try:
                json.loads(first_line)
            except json.JSONDecodeError as e:
                print(f"❌ Part {i:02d} ({os.path.basename(part)}) FIRST line is invalid JSON:")
                print(f"   Error: {e}")
                print(f"   Line excerpt: {first_line[:100]}...")

            # Validate last line
            try:
                json.loads(last_line)
            except json.JSONDecodeError as e:
                print(f"❌ Part {i:02d} ({os.path.basename(part)}) LAST line is invalid JSON:")
                print(f"   Error: {e}")
                print(f"   Line excerpt: {last_line[:100]}...")

    print("\nDiagnosis complete.")

if __name__ == "__main__":
    # Add target files to check
    targets = [
        "data/wikipedia_index.jsonl",
        # "data/igdb.jsonl",  # Uncomment if applicable
    ]
    
    for target in targets:
        diagnose_parts(target)