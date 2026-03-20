export type OntologyLayer = 'kpi' | 'measure' | 'process' | 'resource';
export type OntologyRelation = '달성' | '측정' | '참여' | '매핑';

export interface OntologyNode {
    id: string;
    label: string;
    layer: OntologyLayer;
    type?: string;
    properties: Record<string, string | number>;
    // Client-side visual properties for force-graph
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
    color?: string;
    val?: number; // Size weight
}

export interface OntologyEdge {
    source: string | OntologyNode;
    target: string | OntologyNode;
    type: string;
    label: string;
    properties?: Record<string, string | number>;
}

export interface OntologyGraphData {
    nodes: OntologyNode[];
    links: OntologyEdge[];
}

export interface OntologyFilters {
    query: string;
    layers: Set<OntologyLayer>;
    depth: number;
}

export type ViewMode = 'graph' | 'conceptMap' | 'table';

export interface ConceptMapping {
    rel_id: string;
    source_id: string;
    source_layer: string;
    source_name: string;
    target_table: string;
    target_schema?: string;
    rel_type: string;
    created_at: string;
}

export interface SchemaEntity {
    name: string;
    schema: string;
    datasource: string;
}

export interface SuggestResult {
    name: string;
    type: string;
    schema?: string;
    datasource?: string;
    score: number;
}

// O2-B: Concept map sub-view toggle
export type ConceptMapSubView = 'table' | 'visual';

// O4: Impact Analysis types
export interface ImpactPathStep {
    node_id: string;
    node_label: string;
    rel_type?: string;
}

export interface ImpactNode {
    id: string;
    label: string;
    labels: string[];
    layer: string;
    depth: number;
    path: ImpactPathStep[];
}

export interface ImpactResult {
    root: { id: string; label: string; layer: string };
    affected_nodes: ImpactNode[];
    total_affected: number;
    max_depth_reached: number;
    analysis_time_ms: number;
}

// O5-2: Quality Dashboard types
export interface QualityReport {
    orphan_count: number;
    low_confidence_count: number;
    missing_description: number;
    duplicate_names: number;
    duplicate_details: Record<string, number>;
    total_nodes: number;
    total_relations: number;
    coverage_by_layer: Record<string, { total: number; verified: number; orphan: number }>;
}

// O5-3: HITL Review Queue types
export interface HITLItem {
    id: string;
    node_id: string;
    case_id: string;
    tenant_id: string;
    status: 'pending' | 'approved' | 'rejected';
    reviewer_id?: string;
    submitted_at: string;
    reviewed_at?: string;
    review_comment?: string;
    node_name?: string;
    node_layer?: string;
}

export interface HITLListResponse {
    items: HITLItem[];
    pagination: { total: number; limit: number; offset: number };
}
