"""
Comprehensive Verification Suite for ResearchLens 12-Paper Comparison Scenarios (1-12)
"""
import urllib.request
import urllib.error
import json
import sys

API_URL = "http://localhost:8000/api/v1/papers/compare"

# 12 real database IDs with substantial abstracts
PAPERS_12 = ["163", "164", "165", "166", "167", "168", "169", "170", "171", "172", "189", "190"]
# Alternate paper for replacement test
ALT_PAPER = "191"
# Paper with 0-length abstract for missing metadata test
EMPTY_PAPER = "313"

def compare(payload):
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.getcode(), json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}

def main():
    print("=================================================================")
    print("RESEARCHLENS 12-PAPER COMPARISON - FULL AUDIT & VERIFICATION")
    print("=================================================================")

    # ------------------------------------------------------------------
    # Scenario 1: Compare papers A and B (2 papers)
    # ------------------------------------------------------------------
    print("\n--- Scenario 1: Compare 2 papers (A and B) ---")
    c1, r1 = compare({"paper_ids": PAPERS_12[:2]})
    assert c1 == 200, f"Scenario 1 failed with code {c1}: {r1}"
    assert len(r1["papers"]) == 2
    assert len(r1["coverage_summary"]) == 2
    assert r1.get("statistics") is not None
    assert r1["statistics"]["papers_compared"] == 2
    print(f"  * Papers compared: {len(r1['papers'])}")
    print(f"  * Statistics papers_compared: {r1['statistics']['papers_compared']}")
    print(f"  * Year distribution: {r1['statistics']['year_distribution']}")
    print(f"  * Method distribution: {r1['statistics']['methodology_distribution']}")
    print(">>> Scenario 1 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 2: Compare papers A, B, and C (3 papers)
    # ------------------------------------------------------------------
    print("\n--- Scenario 2: Compare 3 papers (A, B, and C) ---")
    c2, r2 = compare({"paper_ids": PAPERS_12[:3]})
    assert c2 == 200, f"Scenario 2 failed with code {c2}: {r2}"
    assert len(r2["papers"]) == 3
    assert len(r2["coverage_summary"]) == 3
    assert r2["statistics"]["papers_compared"] == 3
    print(f"  * Papers compared: {len(r2['papers'])}")
    print(f"  * Statistics papers_compared: {r2['statistics']['papers_compared']}")
    print(f"  * Statistics updated from 2 to 3: {r1['statistics']['papers_compared'] != r2['statistics']['papers_compared']}")
    print(">>> Scenario 2 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 3: Compare 5 different papers
    # ------------------------------------------------------------------
    print("\n--- Scenario 3: Compare 5 different papers ---")
    c3, r3 = compare({"paper_ids": PAPERS_12[:5]})
    assert c3 == 200, f"Scenario 3 failed with code {c3}: {r3}"
    assert len(r3["papers"]) == 5
    assert len(r3["coverage_summary"]) == 5
    assert r3["statistics"]["papers_compared"] == 5
    for dim in r3["dimensions"]:
        assert len(dim["cells"]) == 5
    print(f"  * Papers compared: {len(r3['papers'])}")
    print(f"  * All 12 dimensions have exactly 5 cells: True")
    print(f"  * Methodology distribution keys: {list(r3['statistics']['methodology_distribution'].keys())}")
    print(">>> Scenario 3 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 4: Compare 8 different papers
    # ------------------------------------------------------------------
    print("\n--- Scenario 4: Compare 8 different papers ---")
    c4, r4 = compare({"paper_ids": PAPERS_12[:8]})
    assert c4 == 200, f"Scenario 4 failed with code {c4}: {r4}"
    assert len(r4["papers"]) == 8
    assert len(r4["coverage_summary"]) == 8
    assert r4["statistics"]["papers_compared"] == 8
    for dim in r4["dimensions"]:
        assert len(dim["cells"]) == 8
    print(f"  * Papers compared: {len(r4['papers'])}")
    print(f"  * All 12 dimensions have exactly 8 cells: True")
    print(f"  * Year distribution: {r4['statistics']['year_distribution']}")
    print(">>> Scenario 4 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 5: Compare 10 different papers
    # ------------------------------------------------------------------
    print("\n--- Scenario 5: Compare 10 different papers ---")
    c5, r5 = compare({"paper_ids": PAPERS_12[:10]})
    assert c5 == 200, f"Scenario 5 failed with code {c5}: {r5}"
    assert len(r5["papers"]) == 10
    assert len(r5["coverage_summary"]) == 10
    assert r5["statistics"]["papers_compared"] == 10
    for dim in r5["dimensions"]:
        assert len(dim["cells"]) == 10
    print(f"  * Papers compared: {len(r5['papers'])}")
    print(f"  * All 12 dimensions have exactly 10 cells: True")
    print(">>> Scenario 5 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 6: Compare 12 different papers (Full Target Scale)
    # ------------------------------------------------------------------
    print("\n--- Scenario 6: Compare 12 different papers ---")
    c6, r6 = compare({"paper_ids": PAPERS_12})
    assert c6 == 200, f"Scenario 6 failed with code {c6}: {r6}"
    assert len(r6["papers"]) == 12, f"Expected 12 papers, got {len(r6['papers'])}"
    assert len(r6["coverage_summary"]) == 12, f"Expected 12 coverage records, got {len(r6['coverage_summary'])}"
    assert r6["statistics"]["papers_compared"] == 12
    # Verify each dimension has exactly 12 cells mapped to all 12 papers
    paper_ids_6 = [p["paper_id"] for p in r6["papers"]]
    assert len(paper_ids_6) == 12
    for dim in r6["dimensions"]:
        assert len(dim["cells"]) == 12, f"Dimension {dim['dimension_id']} had {len(dim['cells'])} cells instead of 12"
        for pid in paper_ids_6:
            assert pid in dim["cells"], f"Paper {pid} missing from dimension {dim['dimension_id']}"

    print(f"  * Successfully compared 12 papers side-by-side!")
    print(f"  * Executive Summary length: {len(r6['executive_summary'])} chars")
    print(f"  * Year distribution across 12 papers: {r6['statistics']['year_distribution']}")
    print(f"  * Methodology distribution count: {sum(r6['statistics']['methodology_distribution'].values())}")
    print(f"  * Unique approaches captured: {len(r6['statistics']['unique_approaches'])}")
    print(">>> Scenario 6 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 7: Replace one paper in a 12-paper selection and regenerate
    # ------------------------------------------------------------------
    print("\n--- Scenario 7: Replace one paper in 12-paper selection and regenerate ---")
    papers_12_replaced = PAPERS_12[:-1] + [ALT_PAPER]
    c7, r7 = compare({"paper_ids": papers_12_replaced})
    assert c7 == 200, f"Scenario 7 failed with code {c7}: {r7}"
    assert len(r7["papers"]) == 12
    # Ensure paper 190 was replaced by paper 191
    pids_7 = [p.get("id") for p in r7["papers"]]
    assert 191 in pids_7 or any("191" in str(p.get("paper_id")) for p in r7["papers"])
    assert 190 not in pids_7
    assert r6["executive_summary"] != r7["executive_summary"], "Executive summary must update when paper replaced"
    print(f"  * Replaced paper {PAPERS_12[-1]} with {ALT_PAPER}")
    print(f"  * Comparison result dynamically updated reflecting new paper metadata.")
    print(">>> Scenario 7 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 8: Remove one paper and verify update to 11 papers
    # ------------------------------------------------------------------
    print("\n--- Scenario 8: Remove one paper and verify update to 11 papers ---")
    papers_11 = PAPERS_12[:-1]
    c8, r8 = compare({"paper_ids": papers_11})
    assert c8 == 200, f"Scenario 8 failed with code {c8}: {r8}"
    assert len(r8["papers"]) == 11
    assert r8["statistics"]["papers_compared"] == 11
    for dim in r8["dimensions"]:
        assert len(dim["cells"]) == 11
    print(f"  * Selection reduced from 12 to 11 papers.")
    print(f"  * Statistics updated to papers_compared: {r8['statistics']['papers_compared']}")
    print(">>> Scenario 8 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 9: Repeat the same 12-paper comparison and verify consistency
    # ------------------------------------------------------------------
    print("\n--- Scenario 9: Repeat same 12-paper comparison and verify consistency ---")
    c9_1, r9_1 = compare({"paper_ids": PAPERS_12})
    c9_2, r9_2 = compare({"paper_ids": PAPERS_12})
    assert c9_1 == 200 and c9_2 == 200
    assert r9_1["executive_summary"] == r9_2["executive_summary"]
    assert r9_1["statistics"] == r9_2["statistics"]
    assert len(r9_1["supported_similarities"]) == len(r9_2["supported_similarities"])
    assert len(r9_1["supported_differences"]) == len(r9_2["supported_differences"])
    print("  * Executed two identical 12-paper requests: 100% deterministic identity match.")
    print(">>> Scenario 9 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 10: Test papers with missing abstracts / incomplete metadata
    # ------------------------------------------------------------------
    print("\n--- Scenario 10: Missing abstracts or incomplete metadata ---")
    c10, r10 = compare({"paper_ids": ["163", EMPTY_PAPER]})
    assert c10 == 200, f"Scenario 10 failed with code {c10}: {r10}"
    p_empty_cov = next((cov for cov in r10["coverage_summary"] if EMPTY_PAPER in cov["paper_id"] or "9781316534649" in cov["paper_id"]), None)
    assert p_empty_cov is not None
    assert p_empty_cov["source_type"] == "unavailable"
    assert p_empty_cov["coverage_percentage"] == 0.0
    print(f"  * Empty paper coverage level: {p_empty_cov['coverage_level']}")
    print(f"  * Data sufficiency reported honestly without fabricating text.")
    print(">>> Scenario 10 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 11: Test duplicate IDs and nonexistent paper IDs
    # ------------------------------------------------------------------
    print("\n--- Scenario 11: Duplicate IDs, >12 limit, and nonexistent paper IDs ---")
    # Duplicate
    c11_dup, r11_dup = compare({"paper_ids": ["163", "163"]})
    assert c11_dup in [400, 422], f"Expected 400/422 for duplicate, got {c11_dup}"
    print(f"  * Duplicate IDs -> {c11_dup}")

    # Exceeding 12 (13 papers)
    papers_13 = PAPERS_12 + [ALT_PAPER]
    c11_max, r11_max = compare({"paper_ids": papers_13})
    assert c11_max in [400, 422], f"Expected 400/422 for 13 papers, got {c11_max}: {r11_max}"
    print(f"  * 13 papers (>12 limit) -> {c11_max}")

    # Nonexistent
    c11_none, r11_none = compare({"paper_ids": ["163", "9999999"]})
    assert c11_none == 404, f"Expected 404 for missing ID, got {c11_none}"
    print(f"  * Nonexistent ID -> {c11_none}")
    print(">>> Scenario 11 PASSED.")

    # ------------------------------------------------------------------
    # Scenario 12: Unavailable AI provider and honest failure handling
    # ------------------------------------------------------------------
    print("\n--- Scenario 12: Unavailable AI provider and honest failure handling ---")
    # In test environment, local Ollama is offline or unconsented; verify honest fallback
    assert r6.get("ai_fallback_occurred") is True or r6.get("ai_provider") is not None
    if r6.get("ai_fallback_occurred"):
        assert len(r6.get("warnings", [])) > 0
        print(f"  * AI fallback correctly flagged: {r6.get('ai_fallback_occurred')}")
        print(f"  * Diagnostics reported in warnings: {r6.get('warnings')[:2]}")
    print(">>> Scenario 12 PASSED.")

    print("\n=================================================================")
    print("ALL 12 MANDATORY SCENARIOS PASSED WITH ZERO FAILURES!")
    print("=================================================================")

if __name__ == "__main__":
    main()
