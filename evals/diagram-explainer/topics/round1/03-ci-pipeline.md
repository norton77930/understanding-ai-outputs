- Language: en
- Expected diagram type: `flowchart LR`

## Source

A CI/CD pipeline turns a code push into a running release. When a developer pushes a commit, the CI server starts a pipeline run. First, the build step compiles the code and installs its dependencies. Next, the test step runs the automated tests. If the build or any test fails, the pipeline stops at once, nothing is deployed, and the author gets a failure notice. If both pass, the package step builds a deployable artifact, such as a container image, and gives it a version. The deploy step then releases that artifact to the target environment. Many teams release to a staging environment first and to production after a check. If a health check fails after the deploy, the pipeline rolls back to the previous version. Each step runs only if the one before it passed, so a broken change stops early.

## Reader should understand

- Every push starts a run of fixed steps: build, test, package, deploy.
- A step runs only if the step before it passed.
- A failed build or test stops the run, deploys nothing and notifies the author.
- A failed health check after deploy rolls back to the previous version.

## Diagram hints

- Expected type: `flowchart LR` (work moves left to right through stages).
- Key nodes (about 8): Push, Build, Test, Package, Deploy, Live, Notify author, Roll back.
- Main path: Push to Build to Test to Package to Deploy to Live. Failure path: Build and Test each go to Notify author; Deploy goes to Roll back when the health check fails.
- Mark failure edges with short labels such as "fails" and keep them visually distinct from the main path.
- The caption should point at the main path as one line, and at the failure edges that leave before anything is deployed (the rollback is the one exception).
