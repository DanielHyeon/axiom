import pytest
from app.engines.etl_pipeline import etl_pipeline
from app.engines.scenario_solver import scenario_solver
from app.engines.nl_to_pivot import nl_to_pivot

@pytest.mark.asyncio
async def test_etl_pipeline_extracts_and_caches():
    cache_key = await etl_pipeline.extract_and_cache("ds_1", "SELECT *")
    assert cache_key.startswith("etl_cache_")
    
    cube = await etl_pipeline.get_cached_cube(cache_key)
    assert cube["rows"] == 100
    assert "revenue" in cube["metrics"]

@pytest.mark.asyncio
async def test_scenario_solver_simulations():
    mods = [{"metric": "price", "adjustment": "+20%"}]
    res = await scenario_solver.evaluate_what_if("cache_999", modifications=mods)
    
    assert res["solver_status"] == "complete"
    assert "Simulated adjusting price" in res["impacts"]["price"]

@pytest.mark.asyncio
async def test_nl_to_pivot_translations():
    # Test base constraint translation
    pivot = await nl_to_pivot.translate("Show me region sales")
    assert "region" in pivot["dimensions"]
    assert "sales" in pivot["metrics"]
    
    # Test metric overwriting
    pivot2 = await nl_to_pivot.translate("What is the profit by region?")
    assert "profit" in pivot2["metrics"]
