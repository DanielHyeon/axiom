"""Backward compatibility shim.

기존 import를 깨뜨리지 않기 위한 re-export.
신규 코드는 app.infrastructure.external.synapse_acl을 직접 import해야 한다.
"""
from app.infrastructure.external.synapse_acl import (  # noqa: F401
    SynapseACL as SynapseGatewayService,
    SynapseACLError as GatewayProxyError,
    synapse_acl as synapse_gateway_service,
)
