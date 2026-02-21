from abc import ABC, abstractmethod
from typing import Dict, Any, List

class DataSourceAdapter(ABC):
    @abstractmethod
    async def test_connection(self) -> bool:
        pass
        
    @abstractmethod
    async def extract_schema(self) -> Dict[str, Any]:
        pass

class PostgresAdapter(DataSourceAdapter):
    def __init__(self, dsn: str):
        self.dsn = dsn
        
    async def test_connection(self) -> bool:
        # Simulate connection
        return True
        
    async def extract_schema(self) -> Dict[str, Any]:
        # Simulate schema extraction logic for Neo4j loading
        return {"tables": ["users", "orders"]}
