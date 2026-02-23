import { coreApi } from './clients';

export interface ProcessDefinitionListItem {
  proc_def_id: string;
  name: string;
  version: number;
  type: string;
  source: string;
  created_at: string | null;
}

export interface ListProcessDefinitionsResponse {
  data: ProcessDefinitionListItem[];
  cursor: { next: string | null; has_more: boolean };
  total_count: number;
}

export interface CreateProcessDefinitionRequest {
  name: string;
  description?: string;
  type?: string;
  source: 'natural_language' | 'bpmn_upload';
  activities_hint?: string[];
  bpmn_xml?: string;
}

export interface CreateProcessDefinitionResponse {
  proc_def_id: string;
  name: string;
  version: number;
  activities_count?: number;
  gateways_count?: number;
  definition?: unknown;
  bpmn_xml?: string;
  confidence?: number;
  needs_review?: boolean;
}

const MINIMAL_BPMN_XML =
  '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"/>';

export async function listProcessDefinitions(params?: {
  cursor?: string;
  limit?: number;
  sort?: string;
}): Promise<ListProcessDefinitionsResponse> {
  const response = await coreApi.get('/api/v1/process/definitions', {
    params: {
      cursor: params?.cursor,
      limit: params?.limit ?? 20,
      sort: params?.sort ?? 'created_at:desc',
    },
  });
  return response as ListProcessDefinitionsResponse;
}

export async function createProcessDefinition(
  payload: CreateProcessDefinitionRequest
): Promise<CreateProcessDefinitionResponse> {
  const body =
    payload.source === 'bpmn_upload'
      ? { ...payload, bpmn_xml: payload.bpmn_xml ?? MINIMAL_BPMN_XML }
      : payload;
  const response = await coreApi.post('/api/v1/process/definitions', body);
  return response as CreateProcessDefinitionResponse;
}

export interface ProcessDefinitionDetailResponse {
  proc_def_id: string;
  name: string;
  description: string | null;
  version: number;
  type: string;
  source: string;
  definition: Record<string, unknown>;
  bpmn_xml: string | null;
  confidence?: number;
  needs_review?: boolean;
  created_at?: string | null;
}

export async function getProcessDefinition(
  procDefId: string
): Promise<ProcessDefinitionDetailResponse> {
  const response = await coreApi.get(`/api/v1/process/definitions/${procDefId}`);
  return response as ProcessDefinitionDetailResponse;
}

export interface InitiateProcessRequest {
  proc_def_id: string;
  input_data?: Record<string, unknown>;
  role_bindings: Array<{ role_name: string; user_id?: string | null }>;
}

export interface WorkItemSummary {
  workitem_id: string;
  activity_name: string;
  activity_type: string;
  assignee_id?: string | null;
  agent_mode?: string;
  status: string;
  created_at?: string | null;
}

export interface InitiateProcessResponse {
  proc_inst_id: string;
  status: string;
  current_workitems: WorkItemSummary[];
}

export async function initiateProcess(
  body: InitiateProcessRequest
): Promise<InitiateProcessResponse> {
  const response = await coreApi.post('/api/v1/process/initiate', body);
  return response as InitiateProcessResponse;
}

export interface SubmitWorkitemRequest {
  workitem_id?: string;
  item_id?: string;
  result_data: Record<string, unknown>;
  force_complete?: boolean;
}

export interface SubmitWorkitemResponse {
  workitem_id: string;
  status: string;
  next_workitems: WorkItemSummary[];
  process_status: string;
  is_process_completed: boolean;
}

export async function submitWorkitem(
  body: SubmitWorkitemRequest
): Promise<SubmitWorkitemResponse> {
  const response = await coreApi.post('/api/v1/process/submit', body);
  return response as SubmitWorkitemResponse;
}

export interface RoleBindingRequest {
  proc_inst_id: string;
  role_bindings: Array<{ role_name: string; user_id?: string | null }>;
}

export interface RoleBindingResponse {
  proc_inst_id: string;
  role_bindings: Array<{ role_name: string; user_id?: string | null }>;
}

export async function roleBinding(body: RoleBindingRequest): Promise<RoleBindingResponse> {
  const response = await coreApi.post('/api/v1/process/role-binding', body);
  return response as RoleBindingResponse;
}

export interface ProcessStatusResponse {
  proc_inst_id: string;
  status: string;
  workitems: Array<{
    workitem_id: string;
    activity_name: string;
    status: string;
    assignee_id?: string | null;
  }>;
}

export async function getProcessStatus(
  procInstId: string
): Promise<ProcessStatusResponse> {
  const response = await coreApi.get(`/api/v1/process/${procInstId}/status`);
  return response as ProcessStatusResponse;
}

export interface GetWorkitemsResponse {
  data: WorkItemSummary[];
}

export async function getWorkitems(
  procInstId: string,
  params?: { status?: string; agent_mode?: string }
): Promise<GetWorkitemsResponse> {
  const response = await coreApi.get(`/api/v1/process/${procInstId}/workitems`, {
    params,
  });
  return response as GetWorkitemsResponse;
}

/** Tenant-scoped workitem list (dashboard: ApprovalQueue, MyWorkitems). */
export interface WorkitemListItem {
  workitem_id: string;
  proc_inst_id: string | null;
  activity_name: string | null;
  activity_type: string | null;
  assignee_id: string | null;
  agent_mode: string | null;
  status: string;
  created_at: string | null;
}

export interface ListWorkitemsResponse {
  items: WorkitemListItem[];
  total: number;
}

export interface ListWorkitemsParams {
  status?: string;
  assignee?: 'me' | string;
  limit?: number;
  offset?: number;
}

export async function listWorkitems(
  params?: ListWorkitemsParams
): Promise<ListWorkitemsResponse> {
  const response = await coreApi.get<{ items: WorkitemListItem[]; total: number }>(
    '/api/v1/process/workitems',
    {
      params: {
        status: params?.status,
        assignee: params?.assignee,
        limit: params?.limit ?? 20,
        offset: params?.offset ?? 0,
      },
    }
  );
  return (response as ListWorkitemsResponse) ?? { items: [], total: 0 };
}

export interface ProcessFeedbackResponse {
  workitem_id: string;
  feedback: unknown;
  status: string;
}

export async function getProcessFeedback(
  workitemId: string
): Promise<ProcessFeedbackResponse> {
  const response = await coreApi.get(`/api/v1/process/feedback/${workitemId}`);
  return response as ProcessFeedbackResponse;
}

export interface ReworkRequest {
  workitem_id: string;
  reason: string;
  revert_to_activity_id?: string | null;
}

export async function reworkWorkitem(body: ReworkRequest): Promise<unknown> {
  return coreApi.post('/api/v1/process/rework', body);
}

export interface ApproveHitlRequest {
  workitem_id: string;
  approved: boolean;
  modifications?: { feedback?: string };
}

export async function approveHitl(body: ApproveHitlRequest): Promise<unknown> {
  return coreApi.post('/api/v1/process/approve-hitl', body);
}
