# 🔍 Extensive Investigation & Debugging Guide

To ensure high reliability and avoid "blind fixes," every bug investigation in CareerOps MUST follow this extensive investigation methodology.

## 1. Context Acquisition (Context First)
- **Architectural Review**: Always start by reading `README.md` and `docs/SYSTEM.md` to understand the overall architecture and how the specific feature is supposed to work.
- **Data Flow Mapping**: Identify the path of the data:
  `Frontend Component` -> `Frontend Service (Axios)` -> `Vite Proxy` -> `FastAPI Endpoint` -> `Backend Service` -> `Database / AI Skill`.

## 2. Evidence Gathering
- **Visual Evidence**: Analyze screenshots or UI error messages carefully.
- **Frontend Inspection**: Check browser console logs or network tab (if accessible).
- **Backend Log Audit (MANDATORY)**: Run `docker logs careerops-backend --tail 50` to find the actual Python traceback. Do not guess the error if you can see it in the logs.

## 3. Systematic Tracing
- **Grep Search**: Search for the exact error message or UI string in the codebase to find the source.
- **Dependency Check**: Verify if all services (DB, AI Provider, Gotenberg) are running and responding.
- **Input Validation**: Check the payload being sent to the AI skills or DB. Use `print` logs or audit logs if necessary.

## 4. AI Skill Analysis
- **Template Verification**: If the error occurs in an AI task, check the Jinja2 template in `backend/app/skills/`.
- **Syntax Check**: Ensure standard Jinja2 syntax is used. Avoid non-standard tags (like `try/catch`).
- **Context Injection**: Verify that the correct variables are being passed to the template.

## 5. The "No Blind Fixes" Rule
- **CRITICAL**: Never modify code without first identifying the exact line causing the failure and the specific reason for it (SyntaxError, NameError, FileNotFoundError, etc.).
- **Verify Assumptions**: If you suspect a path is wrong, verify it using `ls` or `os.path.exists()` before changing it.

## 6. Verification
- **Test Scripts**: Create a small script in `scratch/` to test the failing service method in isolation.
- **API Call Simulation**: Use `curl` to simulate the frontend request and verify the backend response.

---

> [!IMPORTANT]
> **Always document the findings.** Every bug fix must include a summary of the root cause in the `walkthrough.md`.
