# Git Workflow Rules Design

**Goal:** Establish a standardized Git branching strategy to protect the `master` branch and organize feature development and bug fixes.

**Scope:** Updates to project documentation (`GEMINI.md`) and initialization of the `dev` branch.

## 1. Branching Strategy

The project will follow a simplified Git Flow model:
- **`master`**: Protected branch. Represents the stable production state. No direct commits allowed.
- **`dev`**: The main development branch. All feature branches and bug fixes branch off from here and merge back here.
- **Feature Branches (`feat/xxxx`)**: Created from `dev` for new features.
- **Bug Fix Branches (`fix/xxxx`)**: Created from `dev` for bug fixes.

## 2. Implementation Steps

1. **Update `GEMINI.md`**: Add a new section detailing these Git workflow rules so that the AI and developers strictly follow them in future tasks.
2. **Initialize Git State**: Create the `dev` branch locally from the current `master` state and switch to it, setting up the foundation for the next tasks.

## 3. Ambiguity & Constraints
- The merge process back to `dev` will be done locally for now, unless PRs are specifically requested in future workflows.
- This rule applies immediately to all future AI actions in this workspace.