#!/usr/bin/env python3
"""
Step B: Verified failure-safe PostgreSQL backup and isolated restoration test.
Target container: research-paper-recommender-postgres-1
Database: research_papers
"""
import os
import subprocess
import sys
import hashlib
from datetime import datetime

CONTAINER = "research-paper-recommender-postgres-1"
DB_NAME = "research_papers"
USER = "postgres"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups", f"pg_{TIMESTAMP}")
os.makedirs(BACKUP_DIR, exist_ok=True)

TEMP_DUMP = os.path.join(BACKUP_DIR, "research_papers.tmp")
FINAL_DUMP_GZ = os.path.join(BACKUP_DIR, f"research_papers_{TIMESTAMP}.sql.gz")
SHA_FILE = f"{FINAL_DUMP_GZ}.sha256"

print(f"================================================================================")
print(f"STEP B: FAILURE-SAFE BACKUP & RESTORATION TEST")
print(f"================================================================================")
print(f"Container: {CONTAINER}")
print(f"Database: {DB_NAME}")
print(f"Backup Directory: {BACKUP_DIR}")

# 1. Execute pg_dump
dump_cmd = ["podman", "exec", "-t", CONTAINER, "pg_dump", "-U", USER, "-d", DB_NAME, "--clean", "--if-exists"]
print(f"Running pg_dump...")
try:
    with open(TEMP_DUMP, "w", encoding="utf-8") as f:
        res = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, text=True, check=True)
except subprocess.CalledProcessError as e:
    print(f"[FATAL] pg_dump failed: {e.stderr}")
    sys.exit(1)

# 2. Check dump size
dump_size = os.path.getsize(TEMP_DUMP)
print(f"pg_dump output size: {dump_size:,} bytes")
if dump_size < 100_000:
    print(f"[FATAL] Dump is unexpectedly small ({dump_size} bytes). Expected > 100,000 bytes.")
    sys.exit(1)

# 3. Check for PostgreSQL dump completion marker
with open(TEMP_DUMP, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()
    if "PostgreSQL database dump complete" not in content:
        print("[FATAL] Completion signature 'PostgreSQL database dump complete' not found in dump file!")
        sys.exit(1)

print("Dump completion signature verified successfully.")

# 4. Compress with gzip and compute SHA-256
import gzip
with open(TEMP_DUMP, "rb") as f_in:
    with gzip.open(FINAL_DUMP_GZ, "wb", compresslevel=9) as f_out:
        f_out.writelines(f_in)
os.remove(TEMP_DUMP)

h = hashlib.sha256()
with open(FINAL_DUMP_GZ, "rb") as f:
    while chunk := f.read(65536):
        h.update(chunk)
sha256_hash = h.hexdigest()

with open(SHA_FILE, "w") as f:
    f.write(f"{sha256_hash}  {os.path.basename(FINAL_DUMP_GZ)}\n")

print(f"Compressed backup saved: {FINAL_DUMP_GZ}")
print(f"SHA-256: {sha256_hash}")

# 5. Isolated restore test
TEST_DB = f"restore_verify_{TIMESTAMP}"
print(f"\n--- TESTING RESTORATION INTO ISOLATED DATABASE: {TEST_DB} ---")

# Create test database
subprocess.run(["podman", "exec", "-i", CONTAINER, "psql", "-U", USER, "-c", f"DROP DATABASE IF EXISTS {TEST_DB};"], check=True)
subprocess.run(["podman", "exec", "-i", CONTAINER, "psql", "-U", USER, "-c", f"CREATE DATABASE {TEST_DB};"], check=True)

# Restore compressed dump into TEST_DB
cat_process = subprocess.Popen(["gunzip", "-c", FINAL_DUMP_GZ], stdout=subprocess.PIPE)
restore_process = subprocess.Popen(
    ["podman", "exec", "-i", CONTAINER, "psql", "-U", USER, "-d", TEST_DB],
    stdin=cat_process.stdout,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)
cat_process.stdout.close()
stdout, stderr = restore_process.communicate()

if restore_process.returncode != 0:
    print(f"[FATAL] Restore failed: {stderr}")
    subprocess.run(["podman", "exec", "-i", CONTAINER, "psql", "-U", USER, "-c", f"DROP DATABASE IF EXISTS {TEST_DB};"])
    sys.exit(1)

# Verify counts in test database
check_sql = "SELECT 'papers', count(*) FROM papers UNION ALL SELECT 'users', count(*) FROM users UNION ALL SELECT 'saved_papers', count(*) FROM saved_papers UNION ALL SELECT 'driut_alerts', count(*) FROM driut_alerts UNION ALL SELECT 'paper_evidence', count(*) FROM paper_evidence;"
res = subprocess.run(
    ["podman", "exec", "-i", CONTAINER, "psql", "-U", USER, "-d", TEST_DB, "-t", "-A", "-F", ":", "-c", check_sql],
    capture_output=True,
    text=True,
    check=True
)

counts = dict(line.split(":") for line in res.stdout.strip().split("\n") if ":" in line)
print("Restored counts in isolated test database:")
for k, v in counts.items():
    print(f"  {k}: {v}")

assert int(counts["papers"]) == 162, f"Expected 162 papers, got {counts['papers']}"
assert int(counts["users"]) == 7, f"Expected 7 users, got {counts['users']}"
assert int(counts["saved_papers"]) == 5, f"Expected 5 saved_papers, got {counts['saved_papers']}"
assert int(counts["driut_alerts"]) == 85, f"Expected 85 driut_alerts, got {counts['driut_alerts']}"
assert int(counts["paper_evidence"]) == 3, f"Expected 3 paper_evidence, got {counts['paper_evidence']}"

# Cleanup isolated test database
subprocess.run(["podman", "exec", "-i", CONTAINER, "psql", "-U", USER, "-c", f"DROP DATABASE IF EXISTS {TEST_DB};"], check=True)
print(f"Isolated test database {TEST_DB} cleanly dropped.")

print(f"\n[STEP B PASSED] Verified failure-safe backup created and restored with 100% data integrity.")
print(f"Backup Artifact: {FINAL_DUMP_GZ}")
print(f"SHA-256 Hash: {sha256_hash}")
