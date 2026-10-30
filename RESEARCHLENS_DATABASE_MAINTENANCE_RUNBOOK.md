# ResearchLens — Database & FAISS Maintenance Execution Runbook

**Document ID:** `RESEARCHLENS_DATABASE_MAINTENANCE_RUNBOOK.md`  
**Execution Window:** Scheduled Production Maintenance (Estimated Duration: 15 minutes)  
**Target Environment:** Linux, Podman (`research-paper-recommender-postgres-1`), PostgreSQL 16, FAISS IndexFlatIP  
**Status:** **READY FOR AUTHORIZED EXECUTION**

---

## 1. Maintenance Preconditions & Checklist

Before initiating any maintenance command, release engineers must verify each precondition:

- [ ] **Maintenance Authorization:** Formal approval received for maintenance window.
- [ ] **Application Traffic Paused:** Stop or pause the FastAPI backend to prevent concurrent writes:
  ```bash
  # Check if backend running natively or via systemd
  pkill -f "uvicorn app.main:app" || true
  ```
- [ ] **Container Status Verified:** Confirm the PostgreSQL container is running:
  ```bash
  podman ps --filter "name=research-paper-recommender-postgres-1" --format "{{.ID}} | {{.Names}} | {{.Status}}"
  ```
- [ ] **Disk Space Verified:** Ensure at least 5 GB of free space exists in the backup target partition:
  ```bash
  df -h /var/backups
  ```
- [ ] **Target Directory Created:**
  ```bash
  export MAINT_DATE=$(date +"%Y%m%d_%H%M%S")
  export BACKUP_ROOT="/var/backups/researchlens/${MAINT_DATE}"
  mkdir -p "${BACKUP_ROOT}/postgres" "${BACKUP_ROOT}/faiss"
  ```

---

## 2. Step 1: Pre-Maintenance PostgreSQL Backup & Verification

### 2.1 Failure-Safe Database Dump
Execute `pg_dump` against the verified container `research-paper-recommender-postgres-1` into a temporary file, verifying completion before archiving:

```bash
set -euo pipefail

TEMP_DUMP="${BACKUP_ROOT}/postgres/research_papers_dump.tmp"
FINAL_DUMP="${BACKUP_ROOT}/postgres/research_papers_pre_maint.sql.gz"

echo "Executing pg_dump from container research-paper-recommender-postgres-1..."
podman exec -t research-paper-recommender-postgres-1 pg_dump -U postgres -d research_papers --clean --if-exists > "$TEMP_DUMP"

# Validation 1: Check dump is non-empty and exceeds minimum threshold (100 KB)
DUMP_SIZE=$(stat -c%s "$TEMP_DUMP" 2>/dev/null || echo 0)
if [ "$DUMP_SIZE" -lt 102400 ]; then
    echo "[CRITICAL ERROR] pg_dump failed or produced truncated dump! Size: ${DUMP_SIZE} bytes."
    rm -f "$TEMP_DUMP"
    exit 1
fi

# Validation 2: Check for PostgreSQL completion signature
if ! grep -q "PostgreSQL database dump complete" "$TEMP_DUMP"; then
    echo "[CRITICAL ERROR] Dump missing completion footer signature! Dump may be incomplete."
    rm -f "$TEMP_DUMP"
    exit 1
fi

# Compress and generate cryptographic checksum
gzip -9 < "$TEMP_DUMP" > "$FINAL_DUMP"
rm -f "$TEMP_DUMP"
sha256sum "$FINAL_DUMP" > "${FINAL_DUMP}.sha256"
chmod 600 "$FINAL_DUMP" "${FINAL_DUMP}.sha256"

echo "Database backup verified successfully: $FINAL_DUMP (SHA-256: $(cat "${FINAL_DUMP}.sha256" | cut -d' ' -f1))"
```

### 2.2 Isolated Restoration Test (Mandatory Verification)
Verify that the dump restores completely into a temporary test database inside the container:

```bash
set -euo pipefail

TEST_DB="restore_verify_tmp"
echo "Creating isolated test database: $TEST_DB..."
podman exec -i research-paper-recommender-postgres-1 psql -U postgres -c "DROP DATABASE IF EXISTS $TEST_DB;"
podman exec -i research-paper-recommender-postgres-1 psql -U postgres -c "CREATE DATABASE $TEST_DB;"

echo "Restoring backup into $TEST_DB..."
gunzip -c "$FINAL_DUMP" | podman exec -i research-paper-recommender-postgres-1 psql -U postgres -d "$TEST_DB" > /dev/null

echo "Validating record counts in restored database..."
RESTORED_PAPERS=$(podman exec -i research-paper-recommender-postgres-1 psql -U postgres -d "$TEST_DB" -t -c "SELECT count(*) FROM papers;" | tr -d ' ')
RESTORED_USERS=$(podman exec -i research-paper-recommender-postgres-1 psql -U postgres -d "$TEST_DB" -t -c "SELECT count(*) FROM users;" | tr -d ' ')

if [ "$RESTORED_PAPERS" -ne 162 ] || [ "$RESTORED_USERS" -ne 7 ]; then
    echo "[CRITICAL ERROR] Restored count mismatch! Papers: $RESTORED_PAPERS (expected 162), Users: $RESTORED_USERS (expected 7)."
    podman exec -i research-paper-recommender-postgres-1 psql -U postgres -c "DROP DATABASE $TEST_DB;"
    exit 1
fi

echo "Isolated restore test PASSED: 162 papers, 7 users confirmed."
podman exec -i research-paper-recommender-postgres-1 psql -U postgres -c "DROP DATABASE $TEST_DB;"
echo "Temporary test database cleaned up."
```

---

## 3. Step 2: Pre-Maintenance FAISS Index Backup

Back up both index files concurrently and compute cryptographic hashes:

```bash
set -euo pipefail

FAISS_DIR="/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender/backend/data/processed/faiss"
FAISS_BAK_DIR="${BACKUP_ROOT}/faiss"

cp -p "${FAISS_DIR}/research_index.faiss" "${FAISS_BAK_DIR}/"
cp -p "${FAISS_DIR}/papers_meta.json" "${FAISS_BAK_DIR}/"

(cd "$FAISS_BAK_DIR" && sha256sum research_index.faiss papers_meta.json > checksums.sha256)
(cd "$FAISS_BAK_DIR" && sha256sum -c checksums.sha256)

echo "FAISS backup verified successfully in $FAISS_BAK_DIR."
```

---

## 4. Step 3: Execute FAISS Orphan Vector Reconciliation

Run `scripts/reconcile_faiss_postgres.py` with `--execute` and the verified backup directory:

```bash
cd /home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender

./backend/venv/bin/python scripts/reconcile_faiss_postgres.py \
    --execute \
    --backup-dir "${BACKUP_ROOT}/faiss_reconcile_bak"
```

### Expected Output:
```text
Executing reconciliation with pre-maintenance backup...
Reconciliation completed successfully!
Purged orphans: ['test:t15:cand_ext']
Original ntotal: 163 -> New ntotal: 162
Index consistency: CONSISTENT
```

---

## 5. Step 4: Execute Historical PubMed Date Migration

Run `backend/app/db/migrate_pubmed_dates.py` with `--execute`:

```bash
cd /home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender

./backend/venv/bin/python backend/app/db/migrate_pubmed_dates.py --execute
```

### Expected Output:
```text
Target count to update: 25 records
Protected forthcoming record: pubmed:42635983 (Preserved at year 2028)
Executing forward migration within transaction...
Migration completed successfully. Rows updated: 25
```

---

## 6. Step 5: Post-Maintenance Integrity Verification

Run the comprehensive post-maintenance verification suite:

```bash
set -euo pipefail

echo "=== 1. Check PostgreSQL Record Counts ==="
./backend/venv/bin/python -c '
from sqlalchemy import create_engine, text
engine = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/research_papers")
with engine.connect() as conn:
    total_papers = conn.execute(text("SELECT count(*) FROM papers;")).scalar()
    year_2028 = conn.execute(text("SELECT year FROM papers WHERE paper_id = '\''pubmed:42635983'\'';")).scalar()
    future_papers = conn.execute(text("SELECT count(*) FROM papers WHERE year >= 2027;")).scalar()
    assert total_papers == 162, f"Expected 162 papers, got {total_papers}"
    assert year_2028 == 2028, f"Expected pubmed:42635983 year 2028, got {year_2028}"
    assert future_papers == 1, f"Expected exactly 1 paper with year >= 2027, got {future_papers}"
    print("PostgreSQL assertions PASSED: 162 papers, exactly 1 forthcoming paper (2028).")
'

echo "=== 2. Check FAISS Index Consistency ==="
./backend/venv/bin/python scripts/reconcile_faiss_postgres.py

echo "=== 3. Run Targeted Remediation Regression Tests ==="
./backend/venv/bin/pytest backend/tests/test_targeted_remediations.py

echo "=== 4. Check Backend Health Endpoint ==="
curl -s http://127.0.0.1:8000/api/v1/health | grep '"status":"ok"'
```

---

## 7. Emergency Rollback Procedures

If an unexpected failure or invariant breach occurs during execution:

### 7.1 Database Rollback
1. **Option A (Transaction Rollback Script):**
   ```bash
   ./backend/venv/bin/python backend/app/db/migrate_pubmed_dates.py --rollback
   ```
2. **Option B (Full Snapshot Restoration):**
   ```bash
   gunzip -c "${BACKUP_ROOT}/postgres/research_papers_pre_maint.sql.gz" | \
       podman exec -i research-paper-recommender-postgres-1 psql -U postgres -d research_papers
   ```

### 7.2 FAISS Vector Store Rollback
Restore active index and metadata files from the pre-maintenance backup:
```bash
cp -p "${BACKUP_ROOT}/faiss/research_index.faiss" "${FAISS_DIR}/"
cp -p "${BACKUP_ROOT}/faiss/papers_meta.json" "${FAISS_DIR}/"
```

### 7.3 Verification Post-Rollback
```bash
./backend/venv/bin/python scripts/reconcile_faiss_postgres.py
# Confirms return to baseline state (162 DB papers, 163 FAISS vectors, 1 orphan)
```
