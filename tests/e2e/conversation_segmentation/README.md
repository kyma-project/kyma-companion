# Conversation Segmentation E2E Security Model

This test intentionally runs the pull request's Companion image against a real model and HANA after approval through the
protected `e2e` environment. That is the unavoidable repository-level trust decision: an approved PR image can use the
allowlisted model and HANA credentials needed by the production command. It does not receive cluster, Kubernetes,
encryption, Langfuse, or other service credentials. The runtime config is rebuilt by trusted `main` code and contains only
one model deployment, a dedicated E2E HANA principal/schema, ephemeral Redis, logging, and segmentation settings.

## Required GitHub configuration

Configure these before enabling the workflow:

1. Keep the existing `e2e` environment approval/codeowner gate.
2. Add these purpose-specific secrets to the `e2e` environment. They are not passed or inherited by the caller; the called
   E2E job receives them from its approved environment:
   - `SEGMENTATION_E2E_MODEL_CONFIG`: JSON with `SEGMENTATION_E2E_PURPOSE` set to
     `conversation-segmentation-e2e-model`, the five `AICORE_*` connection fields, `MODEL_NAME`,
     `MODEL_DEPLOYMENT_ID`, and optional `MODEL_TEMPERATURE`.
   - `SEGMENTATION_E2E_HANA_CONFIG`: JSON with `SEGMENTATION_E2E_PURPOSE` set to
     `conversation-segmentation-e2e-hana`, `SEGMENTATION_E2E_SCHEMA`, and the four `DATABASE_*` connection fields.
3. Create a `segmentation-e2e-cleanup` environment with **no required reviewers** and one environment secret only:
   `SEGMENTATION_E2E_HANA_CLEANUP_CONFIG`. Its JSON purpose must be
   `conversation-segmentation-e2e-cleanup` and it contains `SEGMENTATION_E2E_SCHEMA` plus the cleanup principal's four
   `DATABASE_*` connection fields. Keeping this secret environment-scoped prevents the PR execution job from receiving it.

Both HANA users and the target schema must match `KC_SEG_E2E_*`. The runtime user's name must equal the dedicated schema;
the cleanup user must be different. Provision that schema solely for these run-scoped test tables. The runtime principal
may create/read/write its test tables, while the cleanup principal may inspect and drop only tables in that E2E schema.
Neither principal may have grants on landscape/application schemas or tables. HANA grants cannot be introspected reliably
by this workflow, so this least-privilege setup is mandatory; marker, purpose, schema ownership, and principal separation
are validated and fail closed before any PR code runs.

The PR image and fixture helper run only in a new K3d cluster with a fresh runner-temporary kubeconfig. Pods do not receive
a Kubernetes service account token. Redis is installed inside K3d from a checksum-pinned chart. Raw pod logs are captured
to a temporary file, checked for normalized privacy canaries by trusted code, and reduced to allowlisted count/status
messages before anything is emitted. Log retrieval is mandatory, and each seed/append/segment/validate action must emit
its expected safe completion marker.

Fixture seeding and appending use the production conversation-history helpers rather than writing Redis values directly.
This exercises the atomic Lua write for list-valued history plus hashed instance-metadata keys. HANA validation reads those
opaque instance IDs back from Redis and verifies both assignment hashes and processing checkpoints against them. Seed setup
also uses an isolated synthetic key to verify stable IDs and malformed-history repair, then deletes that key in `finally`.

The shared image builder publishes a mutable `PR-<number>` tag. The caller waits for the exact head SHA's trusted build
check, rechecks that the PR head is unchanged, pulls the tag once, and uses the resolved registry digest for every Job.
The pull-image build workflow must pass `IMAGE_REVISION=<full head SHA>`; the Dockerfile writes it as the OCI
`org.opencontainers.image.revision` label. The E2E workflow requires that label and fails closed unless it matches the
expected SHA. The trusted image builder must continue building the checked SHA's context and preserving this label.

Cleanup runs in a separate `always()` job using a trusted host-side utility, not the PR image or K3d. Its HANA client wheel
is installed with a platform-specific hash recorded in the repository lockfile. Forced workflow
cancellation can still prevent any GitHub Actions cleanup job from starting, so the protected manual cleanup workflow can
drop the four tables for one strictly validated run prefix.

## Bootstrap limitation

GitHub loads `pull_request_target` and reusable workflows from the base branch. Consequently, the PR that first adds this
workflow cannot execute it. After the initial merge, orchestration and cleanup come from trusted `main`, while test
fixtures and manifests are checked out at the exact reviewed PR SHA. Changes to orchestration itself take effect only
after merge and therefore require static review and local linting in their introducing PR.
