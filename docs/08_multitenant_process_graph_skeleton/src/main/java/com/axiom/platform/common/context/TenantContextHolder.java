package com.axiom.platform.common.context;

import reactor.core.publisher.Mono;
import reactor.util.context.ContextView;

public final class TenantContextHolder {

    public static final String CONTEXT_KEY = TenantContextHolder.class.getName();

    private TenantContextHolder() {
    }

    public static Mono<TenantContext> getCurrent() {
        return Mono.deferContextual(TenantContextHolder::extract);
    }

    private static Mono<TenantContext> extract(ContextView contextView) {
        if (!contextView.hasKey(CONTEXT_KEY)) {
            return Mono.error(new IllegalStateException("TenantContext is missing"));
        }
        return Mono.just(contextView.get(CONTEXT_KEY));
    }
}
