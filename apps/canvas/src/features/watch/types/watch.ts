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
