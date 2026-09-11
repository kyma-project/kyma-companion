# Snapshot Fixture Sources

This directory contains representative markdown fixture files used by the chunk snapshot tests
(`tests/unit/indexing/test_chunk_snapshots.py`). Each file is a realistic but synthetic document
modeled after the real upstream sources listed below. No verbatim content from the upstream repos
is included.

## Files

| File | Module | Intended upstream source |
|---|---|---|
| `istio/troubleshooting-istio-sidecar-injection.md` | `istio` | `https://github.com/kyma-project/istio` -- `docs/user/` troubleshooting page |
| `api-gateway/api-rule-cr.md` | `api-gateway` | `https://github.com/kyma-project/api-gateway` -- `docs/user/` custom-resource reference page |
| `btp-foundation/cp-kyma-redis-function.md` | `btp-foundation` | `https://github.com/sap-tutorials/btp-foundation` -- tutorial with YAML frontmatter |
| `btp-cloud-platform/configure-kyma-runtime.md` | `btp-cloud-platform` | `https://github.com/SAP-docs/btp-cloud-platform` -- page with `<!-- loio -->` comment markers |
| `busola/custom-resource-extensions.md` | `busola` | `https://github.com/kyma-project/busola` -- page with VitePress tabs (`<!-- tabs:start -->` / `#### **Tab title**` / `<!-- tabs:end -->`) |

## Updating the Snapshot

After changing any fixture or the chunking logic, regenerate the snapshot:

```bash
cd doc_indexer
UPDATE_SNAPSHOTS=1 poetry run pytest tests/unit/indexing/test_chunk_snapshots.py -v
```

Review the diff in `tests/unit/fixtures/snapshots/chunks.json` before committing.
