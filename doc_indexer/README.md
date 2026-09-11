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

### Chunk snapshot tests

`tests/unit/indexing/test_chunk_snapshots.py` runs the full chunking pipeline over a set of
realistic fixture documents (under `tests/unit/fixtures/snapshot_docs/`) and compares the output
against a committed JSON file (`tests/unit/fixtures/snapshots/chunks.json`).

**Any change to the chunking logic or the fixture files must be followed by a snapshot update.**
Review the diff carefully before committing -- the snapshot is the source of truth for what the
indexer produces.

To regenerate the snapshot:

```bash
cd doc_indexer
UPDATE_SNAPSHOTS=1 poetry run pytest tests/unit/indexing/test_chunk_snapshots.py -v
```

Then review and commit `tests/unit/fixtures/snapshots/chunks.json`.

## Retrieval Evaluation

`evaluation/` contains a labelled query set and a script to measure how well the vector index retrieves the expected documents.

### Query set

`evaluation/queries.jsonl` -- 40 queries covering concept, howto, and troubleshooting scenarios.
Each entry has the form:

```json
{"id": "ts-apirule-accessstrategies", "kind": "troubleshooting",
 "query": "APIRule status Error: accessStrategies handler allow is deprecated in v1beta1, migrate to v2",
 "expected": ["api-gateway/docs/user/apirule-migration/01-82-migrate-allow-noop-no_auth-v1beta1-to-v2.md"]}
```

`expected` is a list of path suffixes -- a retrieved chunk is considered a hit when its `source`
metadata field ends with (or contains) any of the listed suffixes.

### Running locally against an existing table

Prerequisites: a populated HANA table and a `config/config.json` with HANA credentials
(same format as for the indexer itself).

```bash
# From the doc_indexer/ directory:
poetry install
poetry run python evaluation/run_retrieval_eval.py \
    --table kyma_docs \
    --k 10 \
    --mode vector
```

To write results to a file and check against the committed baseline:

```bash
poetry run python evaluation/run_retrieval_eval.py \
    --table kyma_docs \
    --k 10 \
    --mode vector \
    --baseline evaluation/baseline.json \
    --out evaluation/results.json
```

The script exits with code 1 if `recall@5` drops more than 0.05 compared to the baseline.
It prints a Markdown table and writes it to `$GITHUB_STEP_SUMMARY` when that variable is set.

### Updating the baseline

After verifying a run against the production table looks healthy, copy `results.json`
metrics into `baseline.json`:

```bash
# Extract only the metrics block (not per-query details) for the baseline:
python -c "
import json, sys
r = json.load(open('evaluation/results.json'))
json.dump(r['metrics'], open('evaluation/baseline.json', 'w'), indent=2)
print('baseline.json updated')
"
```

Commit `evaluation/baseline.json` so future CI runs can catch regressions.

### CI

The workflow `.github/workflows/pull-retrieval-eval-doc-indexer.yaml` runs the evaluation:

- **On PRs** when the label `run-retrieval-eval` is applied.
- **Weekly** every Monday at 06:00 UTC against the production `kyma_docs` table.

Results are uploaded as the `retrieval-eval-results` artifact and a summary table is written
to the GitHub Actions run summary.

## Static Code Analysis
```bash
poetry run poe codecheck
```
