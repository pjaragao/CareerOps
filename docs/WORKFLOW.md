# 🌊 CareerOps Development Workflow

To maintain high architectural standards and documentation integrity, every improvement, feature, or bug fix MUST follow this workflow.

## 1. Research & Analysis
- **Understand the Goal**: Define what needs to be changed and why.
- **Trace the Data**: Identify which services, API endpoints, and database tables are involved.
- **Identify AI Skills**: If AI is involved, check `backend/app/skills/` for existing templates that can be reused or modified.

## 2. Implementation Planning
- **Create a Plan**: Draft an `implementation_plan.md` artifact.
- **DB First**: Plan any schema changes (e.g., `ALTER TABLE`) before touching business logic.
- **Service Layer**: Define how the logic will be extracted into services to keep API handlers thin.
- **Verification**: Define exact steps to verify the change.

## 3. Implementation Phase
- **Database**: Run migration commands first.
- **Backend Services**: Implement the business logic.
- **API Layer**: Connect services to endpoints.
- **Frontend**: Update UI components to reflect backend changes.

## 4. Documentation & Cleanup (CRITICAL)
- **Update SYSTEM.md**: Update Architecture Diagrams, Project Structure, or Data Flow sections.
- **Update README.md**: Update Features list or Configuration tables.
- **Update task.md**: Mark phases as completed.
- **Cleanup**: Remove any legacy code or unused imports identified during refactoring.

## 5. Verification
- **E2E Testing**: Verify the feature works from the Frontend to the DB.
- **Walkthrough**: Create a `walkthrough.md` to summarize the changes for the next session.

---

> [!IMPORTANT]
> **Documentation is not optional.** A feature is only considered "Done" when `SYSTEM.md` and `README.md` reflect its existence and usage.
