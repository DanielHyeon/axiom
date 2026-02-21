import logging
import json
from datetime import datetime
from app.core.middleware import get_current_tenant_id, get_current_request_id

class JSONContextFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
            "filename": record.filename,
            "tenant_id": get_current_tenant_id() or "system",
            "request_id": get_current_request_id() or "-"
        }
        
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONContextFormatter())
    
    root_logger = logging.getLogger("axiom")
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    # Disable uvicorn default to prevent duplicates
    logging.getLogger("uvicorn.access").handlers = [handler]
