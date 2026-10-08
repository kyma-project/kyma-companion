# Snapshot Fixture Sources

`../snapshot_docs/` contains the markdown fixture files used by the chunk snapshot tests
(`tests/unit/indexing/test_chunk_snapshots.py`). This file lives outside that directory so that it is
not chunked itself. Verbatim fixtures are byte-for-byte copies of the upstream file at the listed
commit; do not edit them. Fixtures marked synthetic are made-up documents modeled after the upstream
source, because the upstream licence is not Apache-2.0.

## Files

| Fixture | Module | Upstream repo | Upstream path | Commit | Licence |
|---|---|---|---|---|---|
| `istio/03-30-istio-no-sidecar.md` | `istio` | `kyma-project/istio` | `docs/user/troubleshooting/03-30-istio-no-sidecar.md` | `575b81f75969c2620badb54cb9ebd9dd0a830b78` | Apache-2.0 |
| `api-gateway/04-10-apirule-custom-resource.md` | `api-gateway` | `kyma-project/api-gateway` | `docs/user/custom-resources/apirule/04-10-apirule-custom-resource.md` | `20ddf43870c93fc45a39f264b14e15d086847e74` | Apache-2.0 |
| `busola/01-40-deploy-access-kubernetes.md` | `busola` | `kyma-project/busola` | `docs/user/01-40-deploy-access-kubernetes.md` | `542380e6780a3678a0531a0d9b0d209fa68839da` | Apache-2.0 |
| `btp-foundation/cp-kyma-redis-function.md` | `btp-foundation` | `sap-tutorials/btp-foundation` | synthetic -- modeled after a tutorial with YAML frontmatter | -- | upstream is CC-BY-4.0, not copied |
| `btp-cloud-platform/configure-kyma-runtime.md` | `btp-cloud-platform` | `SAP-docs/btp-cloud-platform` | synthetic -- modeled after a page with `<!-- loio -->` comment markers | -- | upstream is CC-BY-4.0, not copied |

## Updating the Snapshot

After changing any fixture or the chunking logic, regenerate the snapshot:

```bash
cd doc_indexer
UPDATE_SNAPSHOTS=1 poetry run pytest tests/unit/indexing/test_chunk_snapshots.py -v
```

Review the diff in `chunks.json` before committing.
