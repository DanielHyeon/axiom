import { coreApi } from './clients';

export interface AgentFeedbackRequest {
  workitem_id: string;
  feedback_type?: string;
  content: string;
  corrected_output?: Record<string, unknown>;
  priority?: string;
}

export async function submitAgentFeedback(
  body: AgentFeedbackRequest
): Promise<unknown> {
  return coreApi.post('/api/v1/agents/feedback', body);
}

export async function getAgentFeedback(workitemId: string): Promise<unknown> {
  return coreApi.get(`/api/v1/agents/feedback/${workitemId}`);
}

export async function configureMcp(
  payload: Record<string, unknown>
): Promise<unknown> {
  return coreApi.post('/api/v1/mcp/config', payload ?? {});
}

export async function listMcpTools(): Promise<unknown> {
  return coreApi.get('/api/v1/mcp/tools');
}

export async function executeMcpTool(
  payload: Record<string, unknown>
): Promise<unknown> {
  return coreApi.post('/api/v1/mcp/execute-tool', payload ?? {});
}

export async function completionComplete(
  payload: Record<string, unknown>
): Promise<unknown> {
  return coreApi.post('/api/v1/completion/complete', payload ?? {});
}

export async function completionVisionComplete(
  payload: Record<string, unknown>
): Promise<unknown> {
  return coreApi.post('/api/v1/completion/vision-complete', payload ?? {});
}

export interface AgentChatRequest {
  message: string;
  context?: Record<string, unknown>;
  stream?: boolean;
  agent_config?: Record<string, unknown>;
}

export async function agentChat(
  body: AgentChatRequest
): Promise<unknown> {
  return coreApi.post('/api/v1/agents/chat', { ...body, stream: false });
}

export async function listKnowledge(params?: {
  limit?: number;
  offset?: number;
}): Promise<unknown> {
  return coreApi.get('/api/v1/agents/knowledge', {
    params: { limit: params?.limit ?? 20, offset: params?.offset ?? 0 },
  });
}

export async function deleteKnowledge(knowledgeId: string): Promise<unknown> {
  return coreApi.delete(`/api/v1/agents/knowledge/${knowledgeId}`);
}
