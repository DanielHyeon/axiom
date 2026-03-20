export type AlertSeverity = 'critical' | 'warning' | 'info';

export interface Alert {
    id: string;
    title: string;
    description: string;
    severity: AlertSeverity;
    timestamp: string;
    isRead: boolean;
    sourceNodeId?: string; // Links back to Ontology
    metadata?: Record<string, string>;
}

export interface WatchFilters {
    query: string;
    severity: Set<AlertSeverity>;
}

/** Core CEP rule (domain contract: watch rules API). */
export interface WatchRule {
    rule_id: string;
    name: string;
    event_type: string;
    definition?: Record<string, unknown>;
    active: boolean;
    created_at?: string;
    updated_at?: string;
}

export interface WatchRuleCreatePayload {
    name: string;
    event_type: string;
    definition?: Record<string, unknown>;
    active?: boolean;
}

export interface WatchRuleUpdatePayload {
    name?: string;
    event_type?: string;
    definition?: Record<string, unknown>;
    active?: boolean;
}
