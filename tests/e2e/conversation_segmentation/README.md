# Conversation Segmentation E2E Security Model

This test intentionally runs the pull request's Companion image against a real model and HANA after approval through the
protected `e2e` environment. That is the unavoidable repository-level trust decision: an approved PR image can use the
allowlisted model and HANA credentials needed by the production command. It does not receive cluster, Kubernetes,
encryption, Langfuse, or other service credentials. The runtime config is rebuilt by trusted `main` code and contains only
one model deployment, HANA, ephemeral Redis, logging, and segmentation settings.

The PR image and fixture helper run only in a new K3d cluster with a fresh runner-temporary kubeconfig. Pods do not receive
a Kubernetes service account token. Redis is installed inside K3d from a checksum-pinned chart. Raw pod logs are captured
to a temporary file, checked for normalized privacy canaries by trusted code, and reduced to allowlisted count/status
messages before anything is emitted.

The shared image builder publishes a mutable `PR-<number>` tag. The caller waits for the exact head SHA's trusted build
check, rechecks that the PR head is unchanged, pulls the tag once, and uses the resolved registry digest for every Job. If
the image has an OCI revision label, it must match the expected SHA. The residual race between the final head check and
the tag pull cannot be eliminated until the shared build workflow exposes its digest across workflows.

Cleanup runs in a separate `always()` job using a trusted host-side utility, not the PR image or K3d. Forced workflow
cancellation can still prevent any GitHub Actions cleanup job from starting, so the protected manual cleanup workflow can
drop the four tables for one strictly validated run prefix.

## Bootstrap limitation

GitHub loads `pull_request_target` and reusable workflows from the base branch. Consequently, the PR that first adds this
workflow cannot execute it. After the initial merge, orchestration and cleanup come from trusted `main`, while test
fixtures and manifests are checked out at the exact reviewed PR SHA. Changes to orchestration itself take effect only
after merge and therefore require static review and local linting in their introducing PR.
