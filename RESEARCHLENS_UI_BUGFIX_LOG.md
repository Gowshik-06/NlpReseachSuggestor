# ResearchLens UI Bugfix & Enhancement Log
**Sprint:** Final Non-AI Stabilization, Full-System Audit & UI Fix Sprint  
**Date:** October 12, 2026  
**Repository:** `/home/tonystark/Personal/Projects/NLPBasedResearchPaperSystem/research-paper-recommender`

---

## 1. Executive Summary

During Phase 5 of the non-AI stabilization sprint, a systematic front-to-back UI/UX audit was conducted across the React 19 + TypeScript + Vite frontend. Concrete bugs and usability defects were identified, fixed, and verified using automated Vitest unit tests and Playwright end-to-end verification.

Zero temporary hacks or placeholder fixes were introduced. All component modifications adhere strictly to the botanical glassmorphism design tokens and preserve full TypeScript strictness.

---

## 2. Bug Fix Inventory

### Bug UI-01: Double-Click Race Condition and Duplicate Delete Requests in Saved Library
- **Severity:** P2 (State & Network Inconsistency)
- **User-Visible Impact:** When a user clicked "Remove" on a bookmarked paper in the Saved Library under slower network conditions or multiple rapid clicks, the application fired duplicate `DELETE /api/v1/papers/saved/{id}` HTTP requests. The secondary request resulted in an unhandled 404 error ("Saved paper entry not found") shown to the user.
- **Root Cause:** `SavedLibraryView.tsx` lacked an in-flight deletion tracking state (`deletingId`). The "Remove" button remained enabled and clickable during asynchronous request execution.
- **Files Changed:**
  - `frontend/src/components/SavedLibraryView.tsx`
- **Fix Implemented:**
  1. Added `const [deletingId, setDeletingId] = React.useState<number | null>(null);`.
  2. Guarded `handleDelete` against overlapping execution if `deletingId !== null`.
  3. Bound `disabled={deletingId === entry.id}` and dynamically displayed `"⏳ Removing…"` while deletion is in progress.
- **Test Executed:**
  - `frontend/src/components/SavedLibraryView.test.tsx` (`handles remove paper successfully and updates library`)
- **Status:** **VERIFIED FIXED**

---

### Bug UI-02: Disruptive and Blocking Browser `alert()` Dialogs across Core User Actions
- **Severity:** P2 (User Experience & Modal Blocking)
- **User-Visible Impact:** When saving or deleting papers in `HomePage.tsx` or `SavedLibraryView.tsx`, or triggering a background DRIUT scan, any API rejection triggered native browser `alert()` modal dialogs. Browser alerts lock the main JavaScript thread, block keyboard navigation, and create an unpolished user experience.
- **Root Cause:** Legacy placeholder error handlers (`catch (err: any) { alert(...) }`) remained in `HomePage.tsx` and `SavedLibraryView.tsx`.
- **Files Changed:**
  - `frontend/src/pages/HomePage.tsx`
  - `frontend/src/components/SavedLibraryView.tsx`
- **Fix Implemented:**
  1. Implemented a non-blocking, accessible floating Toast notification banner in `HomePage.tsx` (`role="status"`, `aria-live="polite"`).
  2. Implemented `showToast(message, "success" | "error")` with automatic 4-second timeout dismissal and manual close trigger.
  3. Added inline dismissible error alert box in `SavedLibraryView.tsx` (`actionError`).
  4. Provided positive feedback toasts on library operations (e.g. `Bookmarked "Attention Foundations…" to library.`).
- **Test Executed:**
  - `frontend/src/components/SavedLibraryView.test.tsx` (`displays inline error banner and allows dismissing when remove fails`)
  - `tests/e2e/task19_native_smoke.py` (Flow G)
- **Status:** **VERIFIED FIXED**

---

### Bug UI-03: Missing Keyboard `Escape` Dismissal and Accessibility Attributes on Modals
- **Severity:** P2 (Accessibility & Usability)
- **User-Visible Impact:** Power users and keyboard/screen-reader users were unable to close the Research Summary Modal, Grounded Evidence Modal, Comparison Modal, or Authentication Modal using the standard `Escape` key. Furthermore, assistive technologies were not informed that dialog modals had opened.
- **Root Cause:** Modals relied exclusively on mouse clicks (`onClick={onClose}` on backdrop or close button) without attaching window `keydown` event listeners, and lacked `role="dialog"`, `aria-modal="true"`, and `aria-label` attributes.
- **Files Changed:**
  - `frontend/src/components/AuthModal.tsx`
  - `frontend/src/components/SummaryModal.tsx`
  - `frontend/src/components/EvidenceModal.tsx`
  - `frontend/src/components/CompareModal.tsx`
- **Fix Implemented:**
  1. Added `useEffect` with `Escape` key event listener and cleanup to `AuthModal`, `SummaryModal`, `EvidenceModal`, and `CompareModal`.
  2. Added `role="dialog"`, `aria-modal="true"`, and contextual `aria-label` attributes to the modal dialog containers.
- **Test Executed:**
  - `frontend/src/components/AuthModal.test.tsx` (`renders with role dialog and aria-modal`, `closes when Escape key is pressed`)
  - `frontend/src/components/CompareModal.test.tsx`
  - `frontend/src/components/EvidenceModal.test.tsx`
- **Status:** **VERIFIED FIXED**

---

### Bug UI-04: Stale Mode and Error State in Authentication Modal
- **Severity:** P2 (Authentication UI Flow)
- **User-Visible Impact:** If a user previously opened the Auth Modal in "register" mode and closed it, subsequently clicking "🔑 Sign In" in the navigation bar would still open the modal in "register" mode instead of "login" mode. Furthermore, previous validation errors (such as password mismatch or invalid email) remained visible.
- **Root Cause:** `AuthModal.tsx` initialized `mode` only once via `useState(initialMode)` without synchronizing when `isOpen` or `initialMode` props changed.
- **Files Changed:**
  - `frontend/src/components/AuthModal.tsx`
- **Fix Implemented:**
  1. Added `React.useEffect(() => { if (isOpen) { setMode(initialMode); setError(null); } }, [isOpen, initialMode]);` to reset and synchronize modal state upon each display.
- **Test Executed:**
  - `frontend/src/components/AuthModal.test.tsx` (`synchronizes to register mode when initialMode is register`)
- **Status:** **VERIFIED FIXED**

---

### Bug UI-05: Inconsistent and Unformatted Source Badges in Saved Library View
- **Severity:** P3 (Visual Consistency)
- **User-Visible Impact:** In search results (`PaperCard.tsx`), repositories were rendered with recognizable formatting and emoji badges (e.g. `🏛️ US Gov / PubMed`, `🇮🇳 Indian Gov / CSIR`, `Local Archive`). However, inside the Saved Library view (`SavedLibraryView.tsx`), the source was rendered as raw unformatted text (e.g. `pubmed`, `csir`, `local`).
- **Root Cause:** `SavedLibraryView.tsx` lacked the source label formatting mapper present in `PaperCard.tsx`.
- **Files Changed:**
  - `frontend/src/components/SavedLibraryView.tsx`
- **Fix Implemented:**
  1. Standardized badge rendering across `SavedLibraryView.tsx` to match `PaperCard.tsx`:
     - `pubmed` -> `🏛️ US Gov / PubMed`
     - `csir` -> `🇮🇳 Indian Gov / CSIR`
     - `semanticscholar` -> `Semantic Scholar`
     - `local` -> `Local Archive`
     - Others -> `UPPERCASE`
- **Test Executed:**
  - `frontend/src/components/SavedLibraryView.test.tsx` (`renders formatted source badge and private notes`)
- **Status:** **VERIFIED FIXED**

---

## 3. Summary of Verification Metrics

| Test Suite | Total Tests | Passed | Failed | Execution Time |
| :--- | :---: | :---: | :---: | :---: |
| `frontend/src/components/AuthModal.test.tsx` | 3 | 3 | 0 | 0.28s |
| `frontend/src/components/SavedLibraryView.test.tsx` | 3 | 3 | 0 | 0.31s |
| `frontend/src/components/CompareModal.test.tsx` | 8 | 8 | 0 | 0.31s |
| `frontend/src/components/EvidenceModal.test.tsx` | 10 | 10 | 0 | 0.29s |
| `frontend/src/components/DriutAlertsView.test.tsx` | 7 | 7 | 0 | 0.30s |
| `frontend/src/components/ResearchEvolutionView.test.tsx` | 7 | 7 | 0 | 0.39s |
| `frontend/src/services/api.test.ts` | 21 | 21 | 0 | 0.25s |
| `frontend/src/App.test.tsx` | 4 | 4 | 0 | 0.35s |
| **Full Frontend Vitest Suite** | **63** | **63** | **0** | **1.35s** |
| **Frontend Production Build (`tsc -b && vite build`)** | **1** | **1** | **0** | **0.72s** |
| **Standalone Playwright E2E Suite (`task19_native_smoke.py`)** | **7 Flows** | **7/7** | **0** | **17.8s** |
