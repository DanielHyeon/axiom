import pytest
from app.core.graph_search import graph_search_service, SearchResult
from app.core.value_mapping import value_mapping_extractor

def test_reciprocal_rank_fusion_math():
    results = {
        "axis1": [
            SearchResult(id="T1", name="sales", type="table"), 
            SearchResult(id="T2", name="users", type="table")
        ],
        "axis2": [
            SearchResult(id="T2", name="users", type="table"), 
            SearchResult(id="T1", name="sales", type="table")
        ],
        "axis3": [
            SearchResult(id="T2", name="users", type="table")
        ]
    }
    
    fused = graph_search_service.reciprocal_rank_fusion(results, k=60)
    
    # T2 is rank 2 in axis1, rank 1 in axis2, rank 1 in axis3
    # T1 is rank 1 in axis1, rank 2 in axis2, missing in axis3
    # Result should favor T2
    assert fused[0].id == "T2"
    assert fused[1].id == "T1"
    
    # Verify exact math (1/62 + 1/61 + 1/61) vs (1/61 + 1/62)
    t2_score = (1/62) + (1/61) + (1/61)
    t1_score = (1/61) + (1/62)
    assert round(fused[0].rrf_score, 4) == round(t2_score, 4)
    assert round(fused[1].rrf_score, 4) == round(t1_score, 4)

@pytest.mark.asyncio
async def test_pseudo_relevance_feedback():
    q_vec = [1.0, 1.0]
    initial = [[2.0, 0.0], [0.0, 2.0]] # mean is [1.0, 1.0]
    
    prf = await graph_search_service.pseudo_relevance_feedback(initial, q_vec, alpha=0.5)
    
    assert prf == [1.0, 1.0] # 0.5 * 1.0 + 0.5 * 1.0 = 1.0

@pytest.mark.asyncio
async def test_value_mapping_extraction():
    q = "본사의 2024년 프로세스 성공 건수"
    sql = "SELECT * FROM metrics WHERE status = 'SUCCESS'"
    mappings = await value_mapping_extractor.extract_value_mappings(q, sql)
    
    assert len(mappings) == 1
    assert mappings[0].natural_value == "성공"
    assert mappings[0].db_value == "SUCCESS"
    assert mappings[0].confidence == 0.95
