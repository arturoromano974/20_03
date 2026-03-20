"""
Redis Cache Utilities with Vectorization, Tokenization, and Embedding

This module provides utilities for:
1. Redis caching with TTL management
2. Text vectorization and embedding
3. Token management and optimization
4. Vector similarity search
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
import redis
import numpy as np
from openai import OpenAI
from datetime import datetime
from utils.config_loader import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Initialize OpenAI client for embeddings
_openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

class RedisCache:
    """Redis cache manager with advanced features"""

    def __init__(self):
        self.redis_client = redis.Redis(
            host=config['redis']['host'],
            port=config['redis']['port'],
            db=config['redis']['db'],
            decode_responses=False  # Binary mode for vectors
        )
        self.ttl = config['redis']['ttl']
        self.embedding_model = config['redis']['vectorization']['model']
        self.embedding_dim = config['redis']['vectorization']['dimension']

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache with optional TTL"""
        try:
            serialized = json.dumps(value)
            ttl = ttl or self.ttl
            return self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            return None

    def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """Check if a key exists"""
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {str(e)}")
            return False

    def keys(self, pattern: str) -> List[str]:
        """Get all keys matching a pattern using SCAN (non-blocking)"""
        try:
            result = []
            cursor = 0
            while True:
                cursor, keys = self.redis_client.scan(cursor, match=pattern, count=100)
                result.extend(
                    k.decode('utf-8') if isinstance(k, bytes) else k for k in keys
                )
                if cursor == 0:
                    break
            return result
        except Exception as e:
            logger.error(f"Error getting keys for pattern {pattern}: {str(e)}")
            return []

class VectorizationEngine:
    """Text vectorization and embedding engine"""

    def __init__(self, cache: RedisCache):
        self.cache = cache
        self.client = _openai_client
        self.model = config['redis']['vectorization']['model']
        self.dimension = config['redis']['vectorization']['dimension']

    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding vector for text"""
        try:
            # Check cache first
            cache_key = f'embedding:{hash(text)}'
            cached = self.cache.get(cache_key)
            if cached:
                return np.array(cached)

            # Generate new embedding
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )

            embedding = np.array(response.data[0].embedding)

            # Cache embedding
            self.cache.set(cache_key, embedding.tolist(), ttl=86400 * 7)  # 7 days

            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None

    def generate_batch_embeddings(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Generate embeddings for multiple texts"""
        try:
            # Check cache for each text
            embeddings = []
            texts_to_generate = []
            indices_to_generate = []

            for i, text in enumerate(texts):
                cache_key = f'embedding:{hash(text)}'
                cached = self.cache.get(cache_key)
                if cached:
                    embeddings.append(np.array(cached))
                else:
                    embeddings.append(None)
                    texts_to_generate.append(text)
                    indices_to_generate.append(i)

            # Generate missing embeddings in batch
            if texts_to_generate:
                response = self.client.embeddings.create(
                    input=texts_to_generate,
                    model=self.model
                )

                for i, embedding_data in enumerate(response.data):
                    embedding = np.array(embedding_data.embedding)
                    idx = indices_to_generate[i]
                    embeddings[idx] = embedding

                    # Cache it
                    cache_key = f'embedding:{hash(texts_to_generate[i])}'
                    self.cache.set(cache_key, embedding.tolist(), ttl=86400 * 7)

            return embeddings

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            return [None] * len(texts)

    def store_vector(self, key: str, vector: np.ndarray, metadata: Dict = None):
        """Store a vector with metadata"""
        try:
            vector_data = {
                'vector': vector.tolist(),
                'metadata': metadata or {},
                'timestamp': datetime.now().isoformat()
            }

            self.cache.set(f'vector:{key}', vector_data)

        except Exception as e:
            logger.error(f"Error storing vector {key}: {str(e)}")

    def get_vector(self, key: str) -> Optional[np.ndarray]:
        """Retrieve a vector"""
        try:
            data = self.cache.get(f'vector:{key}')
            if data and 'vector' in data:
                return np.array(data['vector'])
            return None
        except Exception as e:
            logger.error(f"Error getting vector {key}: {str(e)}")
            return None

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(dot_product / (norm1 * norm2))

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0

    def find_similar(self, query_vector: np.ndarray, top_k: int = 5,
                    pattern: str = 'vector:*') -> List[Dict]:
        """Find most similar vectors using cosine similarity"""
        try:
            # Get all vector keys
            keys = self.cache.keys(pattern)

            similarities = []

            for key in keys:
                vector_data = self.cache.get(key)
                if not vector_data or 'vector' not in vector_data:
                    continue

                stored_vector = np.array(vector_data['vector'])
                similarity = self.cosine_similarity(query_vector, stored_vector)

                similarities.append({
                    'key': key.replace('vector:', ''),
                    'similarity': similarity,
                    'metadata': vector_data.get('metadata', {})
                })

            # Sort by similarity and return top k
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:top_k]

        except Exception as e:
            logger.error(f"Error finding similar vectors: {str(e)}")
            return []

class TokenizationManager:
    """Token management and optimization"""

    def __init__(self):
        pass

    def count_tokens(self, text: str, model: str = 'gpt-4') -> int:
        """Count tokens in text"""
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}")
            # Fallback: rough estimate (4 chars per token)
            return len(text) // 4

    def truncate_text(self, text: str, max_tokens: int, model: str = 'gpt-4') -> str:
        """Truncate text to fit within token limit"""
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(model)
            tokens = encoding.encode(text)

            if len(tokens) <= max_tokens:
                return text

            # Truncate and decode
            truncated_tokens = tokens[:max_tokens]
            return encoding.decode(truncated_tokens)

        except Exception as e:
            logger.error(f"Error truncating text: {str(e)}")
            # Fallback: character-based truncation
            return text[:max_tokens * 4]

    def optimize_prompt(self, prompt: str, max_tokens: int = 2000) -> str:
        """Optimize prompt by removing unnecessary content"""
        # Remove extra whitespace
        optimized = ' '.join(prompt.split())

        # Truncate if needed
        if self.count_tokens(optimized) > max_tokens:
            optimized = self.truncate_text(optimized, max_tokens)

        return optimized

# Factory functions
def create_cache() -> RedisCache:
    """Create Redis cache instance"""
    return RedisCache()

def create_vectorization_engine() -> VectorizationEngine:
    """Create vectorization engine instance"""
    cache = create_cache()
    return VectorizationEngine(cache)

def create_tokenization_manager() -> TokenizationManager:
    """Create tokenization manager instance"""
    return TokenizationManager()

if __name__ == '__main__':
    # Test the cache system
    cache = create_cache()
    vec_engine = create_vectorization_engine()
    token_manager = create_tokenization_manager()

    print("✅ Redis cache utilities initialized")
    print(f"   - Cache TTL: {cache.ttl}s")
    print(f"   - Embedding model: {vec_engine.model}")
    print(f"   - Embedding dimension: {vec_engine.dimension}")
