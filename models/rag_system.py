"""
RAG (Retrieval-Augmented Generation) System

This module provides RAG functionality for retrieving historical campaign data
by CAMPAIGN_ID, ADSET_ID, and ADS_ID to provide context for decision-making.
"""

import os
import json
import logging
from typing import Dict, List, Optional
import numpy as np
from datetime import datetime
from utils.config_loader import load_config

from cache.redis_utils import create_cache, create_vectorization_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

class RAGSystem:
    """RAG system for historical campaign data retrieval"""

    def __init__(self):
        self.cache = create_cache()
        self.vec_engine = create_vectorization_engine()
        self.chunk_size = config['rag']['chunk_size']
        self.overlap = config['rag']['overlap']
        self.top_k = config['rag']['top_k']
        self.similarity_threshold = config['rag']['similarity_threshold']

    def index_document(self, document: Dict) -> bool:
        """Index a document for RAG retrieval"""
        try:
            doc_id = document.get('id')
            content = document.get('content', '')
            metadata = document.get('metadata', {})

            # Create chunks
            chunks = self._create_chunks(content)

            # Generate embeddings for chunks
            embeddings = self.vec_engine.generate_batch_embeddings(chunks)

            # Store chunks with embeddings
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                if embedding is None:
                    continue

                chunk_id = f"{doc_id}_chunk_{i}"

                chunk_data = {
                    'id': chunk_id,
                    'document_id': doc_id,
                    'content': chunk,
                    'metadata': metadata,
                    'chunk_index': i,
                    'timestamp': datetime.now().isoformat()
                }

                # Store vector
                self.vec_engine.store_vector(chunk_id, embedding, chunk_data)

                # Store in searchable index
                self._index_by_metadata(chunk_id, metadata)

            logger.info(f"Indexed document: {doc_id} ({len(chunks)} chunks)")
            return True

        except Exception as e:
            logger.error(f"Error indexing document: {str(e)}")
            return False

    def query(self, query_text: str, filters: Optional[Dict] = None) -> List[Dict]:
        """Query the RAG system with optional metadata filters"""
        try:
            # Generate query embedding
            query_embedding = self.vec_engine.generate_embedding(query_text)
            if query_embedding is None:
                return []

            # Get candidate chunks based on filters
            candidates = self._get_filtered_candidates(filters)

            # Calculate similarities
            results = []

            for candidate_key in candidates:
                vector_data = self.cache.get(f'vector:{candidate_key}')
                if not vector_data or 'vector' not in vector_data:
                    continue

                candidate_vector = np.array(vector_data['vector'])
                similarity = self.vec_engine.cosine_similarity(
                    query_embedding,
                    candidate_vector
                )

                if similarity >= self.similarity_threshold:
                    results.append({
                        'chunk_id': candidate_key,
                        'similarity': float(similarity),
                        'content': vector_data.get('metadata', {}).get('content', ''),
                        'metadata': vector_data.get('metadata', {})
                    })

            # Sort by similarity and return top k
            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:self.top_k]

        except Exception as e:
            logger.error(f"Error querying RAG system: {str(e)}")
            return []

    def query_by_campaign(self, campaign_id: str, query_text: str = None) -> List[Dict]:
        """Query historical data for a specific campaign"""
        filters = {'campaign_id': campaign_id}

        if query_text:
            return self.query(query_text, filters)
        else:
            # Return all data for campaign
            return self._get_all_for_filter(filters)

    def query_by_adset(self, adset_id: str, query_text: str = None) -> List[Dict]:
        """Query historical data for a specific adset"""
        filters = {'adset_id': adset_id}

        if query_text:
            return self.query(query_text, filters)
        else:
            return self._get_all_for_filter(filters)

    def query_by_ad(self, ad_id: str, query_text: str = None) -> List[Dict]:
        """Query historical data for a specific ad"""
        filters = {'ad_id': ad_id}

        if query_text:
            return self.query(query_text, filters)
        else:
            return self._get_all_for_filter(filters)

    def get_similar_campaigns(self, campaign_data: Dict, top_k: int = 5) -> List[Dict]:
        """Find similar campaigns based on characteristics"""
        try:
            # Create description from campaign data
            description = self._create_campaign_description(campaign_data)

            # Query with description
            results = self.query(description)

            # Filter to only campaigns
            campaign_results = [
                r for r in results
                if r['metadata'].get('entity_type') == 'campaign'
            ]

            return campaign_results[:top_k]

        except Exception as e:
            logger.error(f"Error finding similar campaigns: {str(e)}")
            return []

    def _create_chunks(self, text: str) -> List[str]:
        """Create overlapping chunks from text"""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.overlap

        return chunks

    def _index_by_metadata(self, chunk_id: str, metadata: Dict):
        """Index chunk by metadata for filtering"""
        try:
            # Index by campaign_id
            if 'campaign_id' in metadata:
                self.cache.redis_client.sadd(
                    f'rag:campaign:{metadata["campaign_id"]}',
                    chunk_id
                )

            # Index by adset_id
            if 'adset_id' in metadata:
                self.cache.redis_client.sadd(
                    f'rag:adset:{metadata["adset_id"]}',
                    chunk_id
                )

            # Index by ad_id
            if 'ad_id' in metadata:
                self.cache.redis_client.sadd(
                    f'rag:ad:{metadata["ad_id"]}',
                    chunk_id
                )

            # Index by timestamp
            timestamp = metadata.get('timestamp', datetime.now().isoformat())
            self.cache.redis_client.zadd(
                'rag:timeline',
                {chunk_id: datetime.fromisoformat(timestamp).timestamp()}
            )

        except Exception as e:
            logger.error(f"Error indexing by metadata: {str(e)}")

    def _get_filtered_candidates(self, filters: Optional[Dict]) -> List[str]:
        """Get candidate chunks based on metadata filters"""
        if not filters:
            # Return all chunks
            return self.cache.keys('vector:*')

        candidates = set()

        # Apply filters
        if 'campaign_id' in filters:
            campaign_chunks = self.cache.redis_client.smembers(
                f'rag:campaign:{filters["campaign_id"]}'
            )
            candidates.update(campaign_chunks)

        if 'adset_id' in filters:
            adset_chunks = self.cache.redis_client.smembers(
                f'rag:adset:{filters["adset_id"]}'
            )
            if candidates:
                candidates &= set(adset_chunks)
            else:
                candidates.update(adset_chunks)

        if 'ad_id' in filters:
            ad_chunks = self.cache.redis_client.smembers(
                f'rag:ad:{filters["ad_id"]}'
            )
            if candidates:
                candidates &= set(ad_chunks)
            else:
                candidates.update(ad_chunks)

        return list(candidates) if candidates else self.cache.keys('vector:*')

    def _get_all_for_filter(self, filters: Dict) -> List[Dict]:
        """Get all data for a specific filter"""
        candidates = self._get_filtered_candidates(filters)

        results = []
        for candidate_key in candidates[:self.top_k * 2]:  # Get more for filtering
            vector_data = self.cache.get(f'vector:{candidate_key}')
            if vector_data:
                results.append({
                    'chunk_id': candidate_key,
                    'content': vector_data.get('metadata', {}).get('content', ''),
                    'metadata': vector_data.get('metadata', {})
                })

        return results[:self.top_k]

    def _create_campaign_description(self, campaign_data: Dict) -> str:
        """Create a text description of campaign for similarity search"""
        parts = []

        if 'name' in campaign_data:
            parts.append(f"Campaign: {campaign_data['name']}")

        if 'objective' in campaign_data:
            parts.append(f"Objective: {campaign_data['objective']}")

        if 'target_audience' in campaign_data:
            audience = campaign_data['target_audience']
            parts.append(f"Audience: {json.dumps(audience)}")

        if 'budget' in campaign_data:
            parts.append(f"Budget: ${campaign_data['budget']}")

        return ' '.join(parts)

def create_rag_system() -> RAGSystem:
    """Factory function to create RAG system"""
    return RAGSystem()

if __name__ == '__main__':
    # Test the RAG system
    rag = create_rag_system()

    # Test document indexing
    test_doc = {
        'id': 'test_campaign_1',
        'content': 'High performing campaign with 5% CTR and $2 CPC targeting young professionals',
        'metadata': {
            'campaign_id': 'campaign_123',
            'entity_type': 'campaign',
            'timestamp': datetime.now().isoformat()
        }
    }

    success = rag.index_document(test_doc)
    print(f"✅ RAG system initialized and tested: {success}")
