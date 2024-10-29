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
DOCS_PATH=...

# HANA Cloud DB
DATABASE_URL=
DATABASE_PORT=
DATABASE_USER=
DATABASE_PASSWORD=
```

It is important to pay attention that `DOCS_PATH` is the path to the Kyma documentation markdown files.

3. Run the project:
```bash
poetry run python src/main.py
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
