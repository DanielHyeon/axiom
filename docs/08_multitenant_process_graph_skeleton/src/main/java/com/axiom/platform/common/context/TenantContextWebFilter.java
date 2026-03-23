package com.axiom.platform.common.context;

import java.util.Optional;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;

import reactor.core.publisher.Mono;

@Component
public class TenantContextWebFilter implements WebFilter {

    @Value("${axiom.tenant.header-name:X-Tenant-Id}")
    private String tenantHeaderName;

    @Value("${axiom.tenant.org-unit-header-name:X-Org-Unit-Id}")
    private String orgUnitHeaderName;

    @Value("${axiom.tenant.workspace-header-name:X-Workspace-Id}")
    private String workspaceHeaderName;

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        try {
            UUID tenantId = UUID.fromString(requiredHeader(exchange, tenantHeaderName));
            UUID orgUnitId = optionalUuid(exchange, orgUnitHeaderName);
            UUID workspaceId = optionalUuid(exchange, workspaceHeaderName);

            TenantContext tenantContext = new TenantContext(
                    tenantId,
                    orgUnitId,
                    workspaceId,
                    exchange.getRequest().getHeaders().getFirst("X-User-Id")
            );

            return chain.filter(exchange)
                    .contextWrite(context -> context.put(TenantContextHolder.CONTEXT_KEY, tenantContext));
        } catch (Exception ex) {
            exchange.getResponse().setStatusCode(HttpStatus.BAD_REQUEST);
            return exchange.getResponse().setComplete();
        }
    }

    private String requiredHeader(ServerWebExchange exchange, String headerName) {
        String value = exchange.getRequest().getHeaders().getFirst(headerName);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing required header: " + headerName);
        }
        return value;
    }

    private UUID optionalUuid(ServerWebExchange exchange, String headerName) {
        return Optional.ofNullable(exchange.getRequest().getHeaders().getFirst(headerName))
                .filter(value -> !value.isBlank())
                .map(UUID::fromString)
                .orElse(null);
    }
}
