from typing import List, Dict, Any
from collections import defaultdict
from pydantic import BaseModel
import asyncio
import numpy as np

class SearchResult(BaseModel):
    id: str
    name: str
    type: str # 'table', 'column', 'query'
    rrf_score: float = 0.0

class GraphSearchService:
    def reciprocal_rank_fusion(self, results_by_axis: Dict[str, List[SearchResult]], k: int = 60) -> List[SearchResult]:
        fused_scores = defaultdict(float)
        items = {}
        
        for axis, results in results_by_axis.items():
            for rank, result in enumerate(results, start=1):
                fused_scores[result.id] += 1.0 / (k + rank)
                items[result.id] = result
                
        sorted_results = sorted(
            fused_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        final_results = []
        for id, score in sorted_results:
            res = items[id]
            res.rrf_score = score
            final_results.append(res)
            
        return final_results

    async def pseudo_relevance_feedback(self, initial_vectors: List[List[float]], question_vector: List[float], alpha: float = 0.7) -> List[float]:
        if not initial_vectors:
            return question_vector
        mean_vector = np.mean(initial_vectors, axis=0)
        prf_vector = alpha * np.array(question_vector) + (1 - alpha) * mean_vector
        return prf_vector.tolist()
        
    async def search_relevant_schema(self, question: str, question_vector: List[float], datasource_id: str, top_k: int = 10, max_fk_hops: int = 3) -> Dict[str, Any]:
        """
        Orchestrates 5-axis concurrent search (Mocked backend logic connecting to Synapse)
        """
        # Axis 1: Question Vector Match
        r1 = [SearchResult(id="table1", name="sales_records", type="table")]
        # Axis 2: HyDE Vector Match
        r2 = [SearchResult(id="table2", name="employees", type="table"), SearchResult(id="table1", name="sales_records", type="table")]
        # Axis 3: Keyword Match
        r3 = [SearchResult(id="table1", name="sales_records", type="table"), SearchResult(id="table3", name="products", type="table")]
        # Axis 4: Intent Match
        r4 = []
        # Axis 5: PRF Match
        prf_vec = await self.pseudo_relevance_feedback([[0.1, 0.2]], question_vector)
        r5 = [SearchResult(id="table3", name="products", type="table")]
        
        results_by_axis = {
            "vector": r1,
            "hyde": r2,
            "keyword": r3,
            "intent": r4,
            "prf": r5
        }
        
        fused_results = self.reciprocal_rank_fusion(results_by_axis)
        
        # Resolve FK Hops (Mock)
        fk_paths = [
            {
                "start_table": "sales_records",
                "paths": [
                    {"hop1": "employees", "join_columns": [{"from": "public.sales_records.emp_id", "to": "public.employees.id"}]}
                ]
            }
        ]
        
        return {
            "tables": fused_results,
            "columns": [],
            "fk_paths": fk_paths,
            "cached_queries": [],
            "value_mappings": []
        }

graph_search_service = GraphSearchService()
