# Kyma Documentation Indexer

Kyma Documentation Indexer
This project implements a documentation indexing system for Kyma that stores the indexed content in SAP HANA Cloud DB. 
The system processes Markdown files, splits them into meaningful chunks based on headers, and creates searchable vector embeddings.

## Concepts
The indexer splits the documentation content into chunks based on the provided headers and creates vector embeddings for each chunk. 
It uses GPT embedding models to create the embeddings. 
The embeddings are stored in SAP HANA Cloud DB, which allows for fast and efficient search queries.

## Development

To run the project locally, follow these steps:

1. Install the dependencies:

```bash
poetry install
```

2. Prepare the `config-doc-indexer.json` file based on the [template](../config/config-example.json).

3. Run the fetcher to pull documents from the specified sources in the `docs_sources.json` [file](./docs_sources.json):

```bash
poetry run python src/main.py fetch
```

4. Run the indexer to create embeddings for the fetched documents:
```bash
poetry run python src/main.py index
```

## Demo: the HANA builder on the curated corpus

This indexer (stage **b**, "the builder") can also consume the corpus curated by
[pinakes](https://github.com/friedrichwilken/pinakes) (stage **a**, "the curator") instead of the Python
`fetch` step: `manifest.json`, `pinakes.yaml` and the `resolvers/` scripts committed in this directory are
enough to reproduce the exact same artifact directory anywhere, without re-resolving the sources.

### 1. Materialize the artifact

```bash
export PINAKES_BIN=/path/to/pinakes/target/release/pinakes   # built from friedrichwilken/pinakes
export DOCS_PATH=/tmp/kyma-docs-artifact                     # any empty directory

poetry run python src/main.py materialize
```

This runs `pinakes resolve --from-manifest manifest.json --config pinakes.yaml --artifact "$DOCS_PATH"`,
which re-fetches each source at the commit pinned in `manifest.json` (network required) and writes the
artifact layout `<source>/<path>.md` plus `<source>/meta.json` into `$DOCS_PATH`. It logs the page count
declared by the manifest before running pinakes.

### 2. Index to a file (no HANA, no SAP AI Core)

```bash
export INDEX_TO_FILE=true
export DOCS_PATH=/tmp/kyma-docs-artifact                     # same directory as above

poetry run python src/main.py index
```

`AdaptiveSplitMarkdownIndexer.index()` detects the `manifest.json` in `DOCS_PATH` and indexes exactly the
pages it lists (never `_residue/`, and skipping any page with a still-valid `exclude` decision in
`decisions.jsonl`), attaching `module`, `repo`, `commit`, `url`, `title`, `doc_type`, `section`, `path`,
`page_id` and `sha256` metadata to every chunk from the source's `meta.json` and manifest entry. With
`INDEX_TO_FILE=true` neither an embedding model nor a HANA connection is created — chunks are written
straight to a `Kyma_Documentation_chunks_*.json` file in the current directory.

A real run against the full curated corpus (788 pages, 29 sources) produced:

| Metric | Value |
|---|---|
| Pages indexed | 788 (all pages in the manifest) |
| Chunks produced | 2759 |
| `concept` chunks | 1310 |
| `tutorial` chunks | 831 |
| `reference` chunks | 247 |
| `troubleshooting` chunks | 171 |
| (no `doc_type`, e.g. `kyma`/`lifecycle-manager` glob sources) | 200 |

Three sample chunk metadata records from that run, one per kind of source:

**A module page** (VitePress-resolved, `istio`):
```json
{
  "title": "Istio Service Mesh",
  "module": "istio",
  "repo": "kyma-project/istio",
  "commit": "4427d7ba863973c2cea9da74ed8675c5c74aee77",
  "url": "https://github.com/kyma-project/istio/blob/4427d7ba863973c2cea9da74ed8675c5c74aee77/docs/user/00-00-istio-sidecar-proxies.md",
  "doc_type": "concept",
  "section": "",
  "path": "docs/user/00-00-istio-sidecar-proxies.md",
  "page_id": "istio::docs/user/00-00-istio-sidecar-proxies.md",
  "sha256": "a8ad00de00d0007f177ca9f2c4170b14e05a764c814095a97447e8564c1fbff4"
}
```

**An SAP Help page** (`external` resolver, `btp-cloud-platform`):
```json
{
  "title": "Availability Zones in the Kyma Environment",
  "module": "btp-cloud-platform",
  "repo": "SAP-docs/btp-cloud-platform",
  "commit": "4e400647e176c8f0540993e114ed8fb8f940d214",
  "url": "https://github.com/SAP-docs/btp-cloud-platform/blob/4e400647e176c8f0540993e114ed8fb8f940d214/docs/10-concepts/availability-zones-in-the-kyma-environment-a649bd9.md",
  "doc_type": "concept",
  "section": "Basic Platform Concepts > Environments > Kyma Environment",
  "path": "docs/10-concepts/availability-zones-in-the-kyma-environment-a649bd9.md",
  "page_id": "btp-cloud-platform::docs/10-concepts/availability-zones-in-the-kyma-environment-a649bd9.md",
  "sha256": "a860bb154f11df65c65a2dd3fdfcb61abc1089600bcb177d8634d898e1a04619"
}
```

**A rendered CRD reference page** (`openapi` renderer, `istio-crds`):
```json
{
  "title": "Istio (operator.kyma-project.io/v1alpha2) - Istio - Istio",
  "module": "istio-crds",
  "repo": "kyma-project/istio",
  "commit": "4427d7ba863973c2cea9da74ed8675c5c74aee77",
  "url": "https://github.com/kyma-project/istio/blob/4427d7ba863973c2cea9da74ed8675c5c74aee77/reference/operator.kyma-project.io/istio-v1alpha2.md",
  "doc_type": "reference",
  "section": "operator.kyma-project.io",
  "path": "reference/operator.kyma-project.io/istio-v1alpha2.md",
  "page_id": "istio-crds::reference/operator.kyma-project.io/istio-v1alpha2.md",
  "sha256": "5ec93eb98fc8f7229b92db74aea20217546c4a4b5321dc7b5c6ee50a6bd2d448"
}
```

### 3. Inspect the output

```bash
python3 -c "
import json, glob
path = sorted(glob.glob('Kyma_Documentation_chunks_*.json'))[-1]
data = json.load(open(path))['kyma_docs']
print(len(data), 'chunks from', len({c['metadata']['page_id'] for c in data}), 'pages')
"
```

### Targeting HANA instead of a file

Drop `INDEX_TO_FILE` (or set it to `false`) and provide the usual database settings
(`DATABASE_URL`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASSWORD`, plus the SAP AI Core config that
backs `EMBEDDING_MODEL_NAME`) in `config/config.json` — the same artifact from step 1 is indexed into HANA
with the atomic staging-table swap described below:

```bash
export INDEX_TO_FILE=false
export DOCS_PATH=/tmp/kyma-docs-artifact

poetry run python src/main.py index
```

## Testing

The `config.json` file must be present for integration tests (see [template](../config/config-example.json)).

### Test structure

| Layer | Location | Description |
|---|---|---|
| Unit | `tests/unit/` | Fast tests with no external dependencies. All external calls are mocked. |
| Integration | `tests/integration/` | Tests that make real API calls to the embedding service and SAP AI Core, including a full end-to-end test that writes to a temporary Hana DB table. |

A missing config is a hard failure — there are no silent skips.

In CI, the e2e table is named `kc_pr_<PR number>_e2e` so orphaned tables can be traced back to the PR that created them. Locally a UUID is used (`test_e2e_<uuid>_e2e`).

### Running tests

Run unit tests:
```bash
poetry run poe test-unit
```

Run integration tests:
```bash
poetry run poe test-integration
```

Run all tests:
```bash
poetry run poe test
```

### Key regression tests

- **`tests/unit/test_main.py::test_run_indexer_passes_model_name_not_deployment_id`** — verifies that `run_indexer()` passes the model name (not the deployment ID) to the embedding factory.
- **`tests/integration/test_main.py::test_run_indexer_embedding_model_creation`** — positive check: model creation via the exact production sequence produces a working embeddings model.
- **`tests/integration/test_main.py::test_run_indexer_fails_when_deployment_id_passed_as_model_name`** — negative check: passing a deployment ID instead of a model name raises `ValueError`.
- **`tests/integration/test_main.py::test_run_indexer_e2e`** — full end-to-end: indexes real documents into a temporary Hana DB table and verifies chunks were stored.

## Static Code Analysis
```bash
poetry run poe codecheck
```
