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
    type: OntologyRelation;
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
