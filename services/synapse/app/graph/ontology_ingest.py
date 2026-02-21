class OntologyIngestor:
    """
    Subscribes to Redis Streams from Core (events) and auto-generates Neo4j nodes.
    """
    async def process_event(self, event_type: str, payload: dict):
        case_id = str((payload or {}).get("case_id") or "").strip()
        if not case_id:
            return {"accepted": False, "reason": "missing_case_id"}

        if event_type == "case.created":
            entity = {"id": f"case:{case_id}", "label": "Case", "properties": {"name": payload.get("name", "")}}
            return {"accepted": True, "case_id": case_id, "entities": [entity], "relations": []}

        if event_type == "case.process.started":
            process_id = str(payload.get("proc_inst_id") or "").strip()
            if not process_id:
                return {"accepted": False, "reason": "missing_proc_inst_id", "case_id": case_id}
            return {
                "accepted": True,
                "case_id": case_id,
                "entities": [
                    {"id": f"case:{case_id}", "label": "Case", "properties": {}},
                    {"id": f"process:{process_id}", "label": "Process", "properties": {"status": "STARTED"}},
                ],
                "relations": [{"from": f"case:{case_id}", "to": f"process:{process_id}", "type": "HAS_PROCESS"}],
            }

        if event_type == "case.asset.registered":
            asset_id = str(payload.get("asset_id") or "").strip()
            if not asset_id:
                return {"accepted": False, "reason": "missing_asset_id", "case_id": case_id}
            return {
                "accepted": True,
                "case_id": case_id,
                "entities": [{"id": f"asset:{asset_id}", "label": "Asset", "properties": {"kind": payload.get("kind")}}],
                "relations": [{"from": f"case:{case_id}", "to": f"asset:{asset_id}", "type": "HAS_ASSET"}],
            }

        if event_type == "case.stakeholder.added":
            stakeholder_id = str(payload.get("stakeholder_id") or "").strip()
            if not stakeholder_id:
                return {"accepted": False, "reason": "missing_stakeholder_id", "case_id": case_id}
            return {
                "accepted": True,
                "case_id": case_id,
                "entities": [
                    {"id": f"stakeholder:{stakeholder_id}", "label": "Stakeholder", "properties": {"role": payload.get("role")}}
                ],
                "relations": [{"from": f"case:{case_id}", "to": f"stakeholder:{stakeholder_id}", "type": "HAS_STAKEHOLDER"}],
            }

        if event_type == "case.metric.updated":
            metric_id = str(payload.get("metric_id") or "").strip()
            if not metric_id:
                return {"accepted": False, "reason": "missing_metric_id", "case_id": case_id}
            return {
                "accepted": True,
                "case_id": case_id,
                "entities": [{"id": f"metric:{metric_id}", "label": "Measure", "properties": {"value": payload.get("value")}}],
                "relations": [{"from": f"case:{case_id}", "to": f"metric:{metric_id}", "type": "HAS_METRIC"}],
            }

        return {"accepted": False, "reason": "unsupported_event_type", "event_type": event_type, "case_id": case_id}
