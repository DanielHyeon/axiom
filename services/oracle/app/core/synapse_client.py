"""Backward compatibility shim.

기존 import를 깨뜨리지 않기 위한 re-export.
신규 코드는 app.infrastructure.acl.synapse_acl을 직접 import해야 한다.
"""
from app.infrastructure.acl.synapse_acl import (  # noqa: F401
    OracleSynapseACL as SynapseClient,
    oracle_synapse_acl as synapse_client,
)
