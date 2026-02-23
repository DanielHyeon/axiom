from app.services.vision_runtime import VisionRuntime
from app.services.vision_state_store import VisionStateStore


def test_vision_runtime_persists_state_across_restarts(tmp_path) -> None:
    db_path = tmp_path / "vision-state.db"
    store = VisionStateStore(str(db_path))
    runtime = VisionRuntime(store=store)
    runtime.clear()

    scenario = runtime.create_scenario(
        case_id="case-1",
        payload={
            "scenario_name": "baseline",
            "scenario_type": "BASELINE",
            "parameters": {"interest_rate": 4.2},
            "constraints": [],
        },
        created_by="tester",
    )
    runtime.run_scenario_solver("case-1", scenario["id"])
    runtime.create_cube("BusinessAnalysisCube", "mv_business_fact", ["Region"], ["CaseCount"])
    job = runtime.queue_etl_job({"source": "dw"})
    runtime.complete_etl_job_if_queued(job["job_id"])

    runtime_restarted = VisionRuntime(store=VisionStateStore(str(db_path)))
    loaded_scenario = runtime_restarted.get_scenario("case-1", scenario["id"])
    assert loaded_scenario is not None
    assert loaded_scenario["status"] == "COMPLETED"
    assert loaded_scenario["result"] is not None
    assert "BusinessAnalysisCube" in runtime_restarted.cubes
    assert job["job_id"] in runtime_restarted.etl_jobs
    assert runtime_restarted.etl_jobs[job["job_id"]]["status"] == "completed"
