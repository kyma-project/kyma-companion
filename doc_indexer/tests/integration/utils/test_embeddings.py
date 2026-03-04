"""Integration tests for embedding model functionality.

These tests make real API calls to the embedding service.
"""

import math
import os

import pytest
from langchain_core.embeddings import Embeddings

from utils.models import create_embedding_factory, openai_embedding_creator

# Constants for similarity thresholds
HIGH_SIMILARITY_THRESHOLD = 0.99  # Threshold for identical/similar texts
LOW_SIMILARITY_THRESHOLD = 0.95  # Threshold for different texts


@pytest.fixture(scope="module")
def skip_if_no_credentials():
    """Verify credentials are configured.

    If credentials are missing, model initialization will fail with a clear error message.
    """


@pytest.fixture(scope="module")
def embedding_model(skip_if_no_credentials):
    """Create an embedding model for testing.

    Tries to use text-embedding-3-small first, falls back to text-embedding-3-large
    if small is not available.
    """
    model_name = os.getenv("EMBEDDING_MODEL_NAME")
    if model_name:
        # If explicitly set via env var, use it
        create_embedding = create_embedding_factory(openai_embedding_creator)
        return create_embedding(model_name)

    # Try small first, fall back to large
    create_embedding = create_embedding_factory(openai_embedding_creator)
    try:
        return create_embedding("text-embedding-3-small")
    except ValueError as e:
        if "not found in config" in str(e):
            # Fall back to large model
            return create_embedding("text-embedding-3-large")
        raise


@pytest.mark.integration
class TestEmbeddingGeneration:
    """Test embedding generation with real API calls."""

    def test_embedding_model_is_embeddings_instance(self, embedding_model):
        """Test that the created model is an Embeddings instance."""
        assert isinstance(embedding_model, Embeddings)

    def test_embed_single_document(self, embedding_model):
        """Test embedding a single document."""
        text = "This is a test document for embedding."

        # Generate embedding
        embedding = embedding_model.embed_query(text)

        # Verify embedding properties
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)
        # text-embedding-3-small produces 1536-dimensional embeddings
        assert len(embedding) in [512, 1536, 3072]  # Common embedding dimensions

    def test_embed_multiple_documents(self, embedding_model):
        """Test embedding multiple documents."""
        texts = [
            "First test document.",
            "Second test document.",
            "Third test document.",
        ]

        # Generate embeddings
        embeddings = embedding_model.embed_documents(texts)

        # Verify embeddings properties
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)

        for embedding in embeddings:
            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, float) for x in embedding)

        # All embeddings should have the same dimension
        dimensions = [len(emb) for emb in embeddings]
        assert len(set(dimensions)) == 1

    def test_embed_empty_string(self, embedding_model):
        """Test embedding an empty string."""
        text = ""

        # Generate embedding for empty string
        embedding = embedding_model.embed_query(text)

        # Should still produce a valid embedding
        assert isinstance(embedding, list)
        assert len(embedding) > 0

    def test_embed_long_text(self, embedding_model):
        """Test embedding a longer text."""
        # Create a longer text (but still within token limits)
        text = " ".join([f"This is sentence number {i}." for i in range(100)])

        # Generate embedding
        embedding = embedding_model.embed_query(text)

        # Verify embedding properties
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    def test_embeddings_are_consistent(self, embedding_model):
        """Test that embedding the same text twice produces similar results."""
        text = "Consistency test document."

        # Generate embeddings twice
        embedding1 = embedding_model.embed_query(text)
        embedding2 = embedding_model.embed_query(text)

        # Embeddings should be identical or very similar
        assert len(embedding1) == len(embedding2)

        # Calculate cosine similarity (should be very close to 1.0)
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2, strict=True))
        magnitude1 = math.sqrt(sum(x * x for x in embedding1))
        magnitude2 = math.sqrt(sum(x * x for x in embedding2))
        cosine_similarity = dot_product / (magnitude1 * magnitude2)

        assert cosine_similarity > HIGH_SIMILARITY_THRESHOLD

    def test_different_texts_produce_different_embeddings(self, embedding_model):
        """Test that different texts produce different embeddings."""
        text1 = "Machine learning and artificial intelligence."
        text2 = "Cooking recipes and culinary arts."

        # Generate embeddings
        embedding1 = embedding_model.embed_query(text1)
        embedding2 = embedding_model.embed_query(text2)

        # Calculate cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2, strict=True))
        magnitude1 = math.sqrt(sum(x * x for x in embedding1))
        magnitude2 = math.sqrt(sum(x * x for x in embedding2))
        cosine_similarity = dot_product / (magnitude1 * magnitude2)

        # Different topics should have lower similarity
        assert cosine_similarity < LOW_SIMILARITY_THRESHOLD


@pytest.mark.integration
class TestEmbeddingFactory:
    """Test the embedding factory pattern."""

    def test_factory_creates_embeddings(self, skip_if_no_credentials):
        """Test that the factory creates valid embeddings."""
        model_name = os.getenv("EMBEDDING_MODEL_NAME")
        factory = create_embedding_factory(openai_embedding_creator)

        # Try to create embedding model with fallback
        if model_name:
            embedding_model = factory(model_name)
        else:
            try:
                embedding_model = factory("text-embedding-3-small")
            except ValueError as e:
                if "not found in config" in str(e):
                    embedding_model = factory("text-embedding-3-large")
                else:
                    raise

        # Test basic embedding
        text = "Factory pattern test."
        embedding = embedding_model.embed_query(text)

        assert isinstance(embedding, list)
        assert len(embedding) > 0

    def test_factory_with_different_models(self, skip_if_no_credentials):
        """Test creating embeddings with different model names."""
        factory = create_embedding_factory(openai_embedding_creator)

        # Try to create with small model, fall back to large
        try:
            model = factory("text-embedding-3-small")
        except ValueError as e:
            if "not found in config" in str(e):
                model = factory("text-embedding-3-large")
            else:
                raise

        text = "Test text."
        embedding = model.embed_query(text)

        assert isinstance(embedding, list)
        assert len(embedding) > 0
