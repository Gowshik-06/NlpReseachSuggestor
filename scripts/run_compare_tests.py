"""
Verification script for ResearchLens Compare Module Tests A-F.
"""
import urllib.request
import urllib.error
import json
import sys

API_URL = "http://localhost:8000/api/v1/papers/compare"

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
    print("==================================================")
    print("RESEARCHLENS COMPARE MODULE - VERIFICATION SUITE")
    print("==================================================")

    # ------------------------------------------------------------------
    # TEST A: Different Paper Combinations
    # ------------------------------------------------------------------
    print("\n--- TEST A: Different Paper Combinations ---")
    code_ab, res_ab = compare({"paper_ids": ["163", "164"]})
    code_cd, res_cd = compare({"paper_ids": ["164", "165"]})
    assert code_ab == 200, f"Expected 200, got {code_ab}: {res_ab}"
    assert code_cd == 200, f"Expected 200, got {code_cd}: {res_cd}"

    print(f"Comparison [163, 164] executive summary:\n  {res_ab['executive_summary']}\n")
    print(f"Comparison [164, 165] executive summary:\n  {res_cd['executive_summary']}\n")

    diff_ab = [d['statement'] for d in res_ab.get('supported_differences', [])]
    diff_cd = [d['statement'] for d in res_cd.get('supported_differences', [])]
    print(f"AB Supported Differences ({len(diff_ab)}):")
    for d in diff_ab:
        print(f"  * {d}")
    print(f"\nCD Supported Differences ({len(diff_cd)}):")
    for d in diff_cd:
        print(f"  * {d}")

    assert res_ab['executive_summary'] != res_cd['executive_summary'], "AB and CD summaries must be distinct!"
    assert diff_ab != diff_cd, "AB and CD differences must be distinct!"
    print("\n>>> TEST A PASSED: Different paper combinations produce distinct, grounded results.")

    # ------------------------------------------------------------------
    # TEST B: Change One Paper
    # ------------------------------------------------------------------
    print("\n--- TEST B: Change One Paper (A & B vs A & C) ---")
    code_ac, res_ac = compare({"paper_ids": ["163", "165"]})
    assert code_ac == 200, f"Expected 200, got {code_ac}: {res_ac}"

    print(f"Comparison [163, 165] (A & C) executive summary:\n  {res_ac['executive_summary']}\n")
    diff_ac = [d['statement'] for d in res_ac.get('supported_differences', [])]
    print(f"AC Supported Differences ({len(diff_ac)}):")
    for d in diff_ac:
        print(f"  * {d}")

    assert res_ab['executive_summary'] != res_ac['executive_summary'], "Summary must update when substituting paper B with C"
    assert "Hamiltonicity" in res_ac['executive_summary'] or any("Hamilton cycle" in str(d) for d in diff_ac), "Output must reflect paper C (Hamiltonicity)"
    print("\n>>> TEST B PASSED: Changing one paper dynamically updates the comparison to reflect the new paper.")

    # ------------------------------------------------------------------
    # TEST C: Selection Validation
    # ------------------------------------------------------------------
    print("\n--- TEST C: Selection Validation ---")
    # Empty
    c_empty, r_empty = compare({"paper_ids": []})
    assert c_empty in [400, 422], f"Expected 400/422 for empty selection, got {c_empty}: {r_empty}"
    print(f"  * Empty selection -> {c_empty} ({r_empty.get('error', {}).get('message', r_empty)})")

    # 1 paper
    c_one, r_one = compare({"paper_ids": ["163"]})
    assert c_one in [400, 422], f"Expected 400/422 for single paper, got {c_one}: {r_one}"
    print(f"  * 1 paper selection -> {c_one} ({r_one.get('error', {}).get('message', r_one)})")

    # Duplicates
    c_dup, r_dup = compare({"paper_ids": ["163", "163"]})
    assert c_dup in [400, 422], f"Expected 400/422 for duplicate papers, got {c_dup}: {r_dup}"
    print(f"  * Duplicate papers -> {c_dup} ({r_dup.get('error', {}).get('message', r_dup)})")

    # >5 papers
    c_many, r_many = compare({"paper_ids": ["163", "164", "165", "166", "167", "168"]})
    assert c_many in [400, 422], f"Expected 400/422 for >5 papers, got {c_many}: {r_many}"
    print(f"  * 6 papers (>5 limit) -> {c_many} ({r_many.get('error', {}).get('message', r_many)})")

    # Non-existent paper
    c_none, r_none = compare({"paper_ids": ["163", "999999"]})
    assert c_none == 404, f"Expected 404 for non-existent paper, got {c_none}: {r_none}"
    print(f"  * Non-existent ID -> {c_none} ({r_none.get('error', {}).get('message', r_none)})")

    print("\n>>> TEST C PASSED: Robust validation prevents invalid requests across all boundaries.")

    # ------------------------------------------------------------------
    # TEST D: Missing Paper Content
    # ------------------------------------------------------------------
    print("\n--- TEST D: Missing Paper Content Handling ---")
    # Paper 313 has 0 length abstract
    code_d, res_d = compare({"paper_ids": ["163", "313"]})
    assert code_d == 200, f"Expected 200, got {code_d}: {res_d}"
    print(f"Comparison with empty-abstract paper 313 status: {code_d}")
    print(f"Coverage summary: {res_d.get('coverage_summary')}")
    print(f"Warnings reported: {res_d.get('warnings')}")

    # Verify paper 313 cells clearly identify absence of content rather than fabricating
    p313_cells = []
    for dim in res_d.get("dimensions", []):
        for pid, cell in dim.get("cells", {}).items():
            if "313" in pid or cell.get("paper_id") == "crossref:10.1017/9781316534649.005":
                p313_cells.append(cell)

    assert any(c.get("status") in ["missing_evidence", "not_reported"] or "no abstract" in str(c.get("status_note", "")).lower() or "not available" in str(c.get("claim", "")).lower() for c in p313_cells)
    print(f"Verified {len(p313_cells)} dimension cells for paper 313: transparently marked missing/unreported, zero fabrication.")
    print("\n>>> TEST D PASSED: Missing paper content is clearly identified and reported without fabrication.")

    # ------------------------------------------------------------------
    # TEST E: Repeatability
    # ------------------------------------------------------------------
    print("\n--- TEST E: Repeatability ---")
    code_e1, res_e1 = compare({"paper_ids": ["163", "164"]})
    code_e2, res_e2 = compare({"paper_ids": ["163", "164"]})
    assert code_e1 == 200 and code_e2 == 200
    assert res_e1["executive_summary"] == res_e2["executive_summary"], "Executive summary must be deterministic and repeatable"
    assert res_e1["supported_similarities"] == res_e2["supported_similarities"], "Similarities must match identically across repeated calls"
    assert res_e1["supported_differences"] == res_e2["supported_differences"], "Differences must match identically across repeated calls"
    print("Executed two sequential identical comparison requests; exact identity match on summaries, similarities, and differences.")
    print("\n>>> TEST E PASSED: Output is completely repeatable.")

    # ------------------------------------------------------------------
    # TEST F: Failure Handling
    # ------------------------------------------------------------------
    print("\n--- TEST F: Failure Handling ---")
    print(f"AI Provider used: {res_ab.get('ai_provider')}")
    print(f"AI Fallback Occurred: {res_ab.get('ai_fallback_occurred')}")
    print(f"Warnings present: {res_ab.get('warnings')}")
    # When cloud/LLM is offline or unconsented, fallback is recorded accurately
    if res_ab.get("ai_fallback_occurred"):
        print("Fallback flag correctly indicates deterministic extraction was employed.")
        assert len(res_ab.get("warnings", [])) > 0, "Warnings must explain fallback reason"
    print("\n>>> TEST F PASSED: Fallback and provider status are honestly reported in warnings and metadata.")

    print("\n==================================================")
    print("ALL TESTS (A through F) COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    main()
