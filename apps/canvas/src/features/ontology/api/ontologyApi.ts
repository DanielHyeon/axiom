import { synapseApi } from '@/lib/api/clients';
import type { OntologyNode, OntologyEdge, OntologyLayer, ConceptMapping, SchemaEntity, SuggestResult, ImpactResult, QualityReport, HITLListResponse } from '../types/ontology';

// --- BE response types ---

interface BeNode {
  id: string;
  case_id: string;
  layer: string;
  labels: string[];
  properties: Record<string, unknown>;
}

interface BeRelation {
  id: string;
  case_id: string;
  source_id: string;
  target_id: string;
  type: string;
  properties: Record<string, unknown>;
}

interface CaseOntologyResponse {
  success: boolean;
  data: {
    case_id: string;
    summary: { total_nodes: number; total_relations: number; by_layer: Record<string, number> };
    nodes: BeNode[];
    relations: BeRelation[];
    pagination: Pagination;
  };
}

interface Pagination {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

interface PathResponse {
  success: boolean;
  data: { source_id: string; target_id: string; path: string[]; relations: string[] };
}

// --- Transform: BE → FE ---

export function mapBeNode(node: BeNode): OntologyNode {
  const props: Record<string, string | number> = {};
  for (const [k, v] of Object.entries(node.properties)) {
    if (typeof v === 'string' || typeof v === 'number') props[k] = v;
  }
  return {
    id: node.id,
    label: String(node.properties.name || node.labels[0] || node.id),
    layer: node.layer as OntologyLayer,
    type: node.labels[1] ?? undefined,
    properties: props,
  };
}

export function mapBeRelation(rel: BeRelation): OntologyEdge {
  const props: Record<string, string | number> = {};
  for (const [k, v] of Object.entries(rel.properties)) {
    if (typeof v === 'string' || typeof v === 'number') props[k] = v;
  }
  return {
    source: rel.source_id,
    target: rel.target_id,
    type: rel.type,
    label: String(rel.properties.label || rel.type),
    properties: props,
  };
}

// --- API functions ---

export async function getCaseOntology(
  caseId: string,
  params?: { layer?: string; limit?: number; offset?: number },
): Promise<{ nodes: OntologyNode[]; links: OntologyEdge[]; pagination: Pagination }> {
  const res = (await synapseApi.get(
    `/api/v3/synapse/ontology/cases/${encodeURIComponent(caseId)}/ontology`,
    { params },
  )) as unknown as CaseOntologyResponse;
  return {
    nodes: res.data.nodes.map(mapBeNode),
    links: res.data.relations.map(mapBeRelation),
    pagination: res.data.pagination,
  };
}

export async function getPath(
  sourceId: string,
  targetId: string,
  maxDepth = 6,
): Promise<string[]> {
  const res = (await synapseApi.get(
    `/api/v3/synapse/ontology/nodes/${encodeURIComponent(sourceId)}/path-to/${encodeURIComponent(targetId)}`,
    { params: { max_depth: maxDepth } },
  )) as unknown as PathResponse;
  return res.data.path;
}

// --- Concept Mapping API ---

export async function getConceptMappings(caseId: string): Promise<ConceptMapping[]> {
  const res = (await synapseApi.get('/api/v3/synapse/ontology/concept-mappings', {
    params: { case_id: caseId },
  })) as unknown as { success: boolean; data: ConceptMapping[] };
  return res.data;
}

export async function createConceptMapping(
  sourceId: string,
  targetId: string,
  relType = 'MAPS_TO',
): Promise<{ rel_id: string }> {
  const res = (await synapseApi.post('/api/v3/synapse/ontology/concept-mappings/', {
    source_id: sourceId,
    target_id: targetId,
    rel_type: relType,
  })) as unknown as { success: boolean; data: { rel_id: string } };
  return res.data;
}

export async function deleteConceptMapping(relId: string): Promise<void> {
  await synapseApi.delete(`/api/v3/synapse/ontology/concept-mappings/${relId}`);
}

export async function suggestMappings(query: string): Promise<SuggestResult[]> {
  const res = (await synapseApi.get('/api/v3/synapse/ontology/concept-mappings/suggest', {
    params: { q: query },
  })) as unknown as { success: boolean; data: SuggestResult[] };
  return res.data;
}

export async function getSchemaEntities(datasource?: string): Promise<SchemaEntity[]> {
  const res = (await synapseApi.get('/api/v3/synapse/ontology/concept-mappings/schema-entities', {
    params: datasource ? { datasource } : {},
  })) as unknown as { success: boolean; data: SchemaEntity[] };
  return res.data;
}

// --- Impact Analysis API (O4) ---

export async function getImpactAnalysis(
  nodeId: string,
  caseId: string,
  maxDepth = 3,
): Promise<ImpactResult> {
  const res = (await synapseApi.post('/api/v3/synapse/graph/impact-analysis', {
    node_id: nodeId,
    case_id: caseId,
    max_depth: maxDepth,
  })) as unknown as { success: boolean; data: ImpactResult };
  return res.data;
}

// --- O5-1: OWL/RDF Export ---

export async function exportOntology(
  caseId: string,
  format: 'turtle' | 'jsonld' = 'turtle',
): Promise<Blob> {
  const res = await synapseApi.get(
    `/api/v3/synapse/ontology/cases/${encodeURIComponent(caseId)}/export`,
    { params: { format }, responseType: 'blob' },
  );
  return res as unknown as Blob;
}

// --- O5-2: Quality Dashboard ---

export async function getQualityReport(caseId: string): Promise<QualityReport> {
  const res = (await synapseApi.get(
    `/api/v3/synapse/ontology/cases/${encodeURIComponent(caseId)}/quality`,
  )) as unknown as { success: boolean; data: QualityReport };
  return res.data;
}

// --- O5-3: HITL Review Queue ---

export async function getHITLItems(
  caseId: string,
  status = 'pending',
  limit = 50,
  offset = 0,
): Promise<HITLListResponse> {
  const res = (await synapseApi.get(
    `/api/v3/synapse/ontology/cases/${encodeURIComponent(caseId)}/hitl`,
    { params: { status, limit, offset } },
  )) as unknown as { success: boolean; data: HITLListResponse };
  return res.data;
}

export async function approveHITL(
  itemId: string,
  comment = '',
): Promise<{ id: string; status: string; node_id: string }> {
  const res = (await synapseApi.post(
    `/api/v3/synapse/ontology/hitl/${encodeURIComponent(itemId)}/approve`,
    { comment },
  )) as unknown as { success: boolean; data: { id: string; status: string; node_id: string } };
  return res.data;
}

export async function rejectHITL(
  itemId: string,
  comment = '',
): Promise<{ id: string; status: string; node_id: string }> {
  const res = (await synapseApi.post(
    `/api/v3/synapse/ontology/hitl/${encodeURIComponent(itemId)}/reject`,
    { comment },
  )) as unknown as { success: boolean; data: { id: string; status: string; node_id: string } };
  return res.data;
}
