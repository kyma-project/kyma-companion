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

2. Create .env file in the root of the project and add the following variables:
```yaml
LOG_LEVEL=INFO # Set the log level to INFO, DEBUG, WARNING, or ERROR

# AI Core credentials
AICORE_AUTH_URL=
AICORE_CLIENT_ID=
AICORE_CLIENT_SECRET=
AICORE_RESOURCE_GROUP=
AICORE_BASE_URL=

# Embedding Model
EMBEDDING_MODEL_DEPLOYMENT_ID=
EMBEDDING_MODEL_NAME=

# Kyma docs path
DOCS_SOURCES_FILE_PATH=  # Path to the file with the list of documentation sources. Default: "docs_sources.json"
DOCS_PATH=...

# HANA Cloud DB
DATABASE_URL=
DATABASE_PORT=
DATABASE_USER=
DATABASE_PASSWORD=
```

It is important to pay attention that `DOCS_PATH` is the path to the Kyma documentation markdown files.

3. Run the fetcher to pull documents from the specified sources in the `DOCS_SOURCES_FILE_PATH` file:
```bash
poetry run python src/main.py fetch
```

4. Run the indexer to create embeddings for the fetched documents:
```bash
poetry run python src/main.py index
```

## Testing

The `.env` file can also be used for testing. You can create a separate `.env.test` file with similar content to `.env`.
To run the unit and integration tests, use the following command:

```bash
poetry run poe test
```

To run the unit tests, use the following command:

```bash
poetry run poe test-unit
```

To run the integration tests, use the following command:

```bash
poetry run poe test-integration
```

## Static Code Analysis
```bash
poetry run poe codecheck
```
