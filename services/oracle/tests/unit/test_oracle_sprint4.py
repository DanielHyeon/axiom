import pytest
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_react_agent_streaming_endpoint():
    payload = {
        "question": "What were the project revenues last year?",
        "datasource_id": "mock_ds",
        "options": {
            "max_iterations": 3,
            "stream": True
        }
    }
    
    # We use stream requests to read chunked NDJSON outputs securely
    with client.stream("POST", "/text2sql/react", json=payload) as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson"
        
        chunks_read = 0
        has_select = False
        has_generate = False
        has_validate = False
        has_triage = False
        
        for line in response.iter_lines():
            if not line.strip(): continue
            chunks_read += 1
            data = json.loads(line)
            
            # ReAct Loop Checkpoints
            step = data.get("step")
            if step == "select": has_select = True
            elif step == "generate": has_generate = True
            elif step == "validate": has_validate = True
            elif step == "triage": has_triage = True
            
        assert chunks_read >= 4
        assert has_select and has_generate and has_validate and has_triage
