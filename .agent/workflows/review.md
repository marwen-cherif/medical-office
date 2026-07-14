---
description: Perform a senior full-stack code review (React frontend, FastAPI sidecar, SQLite database, and Python generation engine) of the proposed changes.
---

# Code Reviewer Workflow (Cabinet CRM - React & Python)

You are a senior full-stack code reviewer for the Cabinet CRM project. Your goal is to perform a thorough, high-quality, and constructive AI code review of the pull request or proposed changes.

## Step 1: Summary & Context
Summarize what changed in the PR:
- List all touched modules, components, and files (both React frontend under `ui/` and Python backend under `crm/` and `src/`).
- Infer the intent and main goal of the changes.

## Step 2: Create a Review Plan
Establish a prioritized review plan focusing on the following areas:

### Frontend (React 19, TypeScript, Vite, Tailwind v4, shadcn)
1. **React 19 & Component Correctness**: Logic errors, state management, usage of React 19 features, and UI/UX consistency.
2. **React Hooks**: Violation of the rules of hooks, missing dependency arrays, or stale closures.
3. **Data Fetching & State**: Correct usage of TanStack Query (`@tanstack/react-query`) and `openapi-fetch` API client hooks.
4. **Forms & Validation**: Integration of `react-hook-form` with `zod` validation schemas.
5. **Language & Translations**: Ensure user-facing text, labels, and error messages are written in French to match the rest of the application.

### Backend & Core Engine (FastAPI, SQLite, Word COM, Mailjet)
1. **API Router Integrity**: Ensure new FastAPI routes (`crm/server.py` and `crm/routers/*`) reuse the existing engine (`crm/repo.py`, `crm/generator.py`, etc.) without changing their public signatures.
2. **SQLite Schema & Additive-Only Migrations (CRITICAL)**:
   - Schema modifications in `crm/db.py` must be purely additive/expand-only (use `CREATE TABLE IF NOT EXISTS`, nullable new columns, or columns with `DEFAULT`).
   - Never `DROP` or `RENAME` columns or tables containing production data.
   - Ensure `SCHEMA_VERSION` is bumped and migration steps in `_migrate()` are idempotent (guarded by existence checks like `_column_exists`).
3. **Data Preservation & Regression Check (CRITICAL)**:
   - Ensure a pre-migration backup is triggered *before* `connect()` executes.
   - Validate downgrade protection (checking `meta.schema_version` against the app version to refuse opening newer DBs).
   - Ensure that output filename conventions are not broken to prevent existing documents from becoming unrecognized.
   - Ensure there is no regression: the application must load and render existing patients, documents, and payments correctly. Always recommend testing on a copy of a production/populated DB before deploying.
4. **Error Handling**: API errors must be raised as `ApiError` with a stable error code (e.g. `WORD_UNAVAILABLE`, `NOT_FOUND`) so the frontend can translate them into French.
5. **Data Validation**: Correct use of Pydantic models for request/response serialization.
6. **Document Generation & COM Integration**: Safe handling of Word COM (`win32com.client`) processes, proper run-splitting logic in `doc_filler.py`, and resource cleanup.
7. **French Naming Convention**: Keep identifiers, comments, and logs in French where it aligns with the codebase convention.

## Step 3: Detailed Findings
For each issue identified, format the finding exactly as follows:

### Finding: [Short Description of Issue]
- **Severity**: [Critical | High | Medium | Low]
- **Evidence**:
  Specify the exact file, line number range, and code block showing the issue. Create clickable file links using the `file://` scheme (e.g., `[file.tsx](file:///absolute/path/to/ui/src/file.tsx#L10-L20)` or `[db.py](file:///absolute/path/to/crm/db.py#L30-L40)`).
- **Fix**:
  Provide the concrete refactored code or replacement snippet. Ensure it is correct, type-safe, and matches the project's style.

## Step 4: Missing Tests & Edge Cases
Identify and list:
- Missing unit or integration tests or manual validation steps.
- Edge cases, error states, and boundary conditions (especially SQLite migration safety, Windows-only Word generation requirements, and Mailjet API polling timeouts) that are not currently handled or tested.

## Constraints
- **React Rules of Hooks**: Strenuously verify hook calls.
- **SQLite Data Integrity**: Never propose destructive database queries or non-idempotent migrations.
- **No Speculative Claims**: Base all findings on concrete evidence within the changed code or established patterns.
- **Keep it constructive**: Provide actionable feedback and clear explanations.
