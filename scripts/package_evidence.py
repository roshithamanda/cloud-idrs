#!/usr/bin/env python3
import os
import sys
import zipfile
import hashlib
from pathlib import Path

BASE_DIR = Path('/home/roshith/Desktop/cloud-idrs-main')
SUBMISSION_DIR = BASE_DIR / 'assesments' / 'final-submission'
ZIP_PATH = SUBMISSION_DIR / 'CIDRS_FINAL_PROJECT_EVIDENCE.zip'
CHECKSUMS_PATH = SUBMISSION_DIR / 'CHECKSUMS.txt'

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def package():
    print(f"Creating master submission package at {ZIP_PATH}...")
    
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
        # Include all files in final-submission except the zip itself
        for root, dirs, files in os.walk(SUBMISSION_DIR):
            for file in files:
                fpath = Path(root) / file
                if fpath.name == 'CIDRS_FINAL_PROJECT_EVIDENCE.zip':
                    continue
                arcname = fpath.relative_to(SUBMISSION_DIR)
                z.write(fpath, arcname=f"final-submission/{arcname}")
                
        # Include source code
        for src_item in ['src', 'scripts', 'tests', 'data', 'models']:
            src_path = BASE_DIR / src_item
            if src_path.exists():
                for root, dirs, files in os.walk(src_path):
                    for file in files:
                        if '__pycache__' in root or file.endswith('.pyc'):
                            continue
                        fpath = Path(root) / file
                        arcname = fpath.relative_to(BASE_DIR)
                        z.write(fpath, arcname=f"codebase/{arcname}")
                        
        # Include root configs
        for root_file in ['README.md', 'requirements.txt', 'Dockerfile', 'docker-compose.yml', 'pytest.ini']:
            rf = BASE_DIR / root_file
            if rf.exists():
                z.write(rf, arcname=f"codebase/{root_file}")

    print("ZIP package created successfully.")
    
    # Generate SHA-256 Checksums
    print(f"Generating checksums manifest at {CHECKSUMS_PATH}...")
    checksum_lines = []
    for root, dirs, files in os.walk(SUBMISSION_DIR):
        for file in sorted(files):
            fpath = Path(root) / file
            rel = fpath.relative_to(SUBMISSION_DIR)
            checksum = sha256_file(fpath)
            checksum_lines.append(f"{checksum}  final-submission/{rel}")
            
    with open(CHECKSUMS_PATH, 'w') as f:
        f.write("\n".join(checksum_lines) + "\n")
        
    print(f"Checksums saved ({len(checksum_lines)} entries).")

if __name__ == '__main__':
    package()
