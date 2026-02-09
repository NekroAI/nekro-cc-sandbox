import type {
  MessageResponse,
  OkResponse,
  ProviderUpdatedResponse,
  SessionResetResponse,
  SettingsInfoResponse,
  SessionsResponse,
  StatusResponse,
  ToolsInfoResponse,
  WorkspacesResponse,
} from './types'

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null
}

export class ApiHttpError extends Error {
  readonly status: number
  readonly payload: unknown

  constructor(status: number, message: string, payload: unknown) {
    super(message)
    this.name = 'ApiHttpError'
    this.status = status
    this.payload = payload
  }
}

async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init)
  const text = await res.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text) as unknown
    } catch {
      parsed = text
    }
  }
  if (!res.ok) {
    // 优先从结构化错误里提取 message（避免把整段 JSON 甩到 UI 上）
    const messageFromPayload = (() => {
      if (!isRecord(parsed)) return null
      if (parsed.status === 'error' && isRecord(parsed.error) && typeof parsed.error.message === 'string') {
        return parsed.error.message
      }
      if (typeof parsed.detail === 'string') return parsed.detail
      if (typeof parsed.error === 'string') return parsed.error
      return null
    })()
    throw new ApiHttpError(res.status, messageFromPayload ?? `HTTP ${res.status}`, parsed ?? text ?? res.statusText)
  }
  return (parsed ?? null) as T
}

export const api = {
  getStatus: () => requestJson<StatusResponse>('/api/v1/status'),
  listWorkspaces: () => requestJson<WorkspacesResponse>('/api/v1/workspaces'),
  listSessions: () => requestJson<SessionsResponse>('/api/v1/sessions'),
  getSettings: () => requestJson<SettingsInfoResponse>('/api/v1/settings/'),
  resetWorkspaceSession: (workspaceId: string) =>
    requestJson<SessionResetResponse>(`/api/v1/workspaces/${workspaceId}/session/reset`, { method: 'POST' }),
  getTools: () => requestJson<ToolsInfoResponse>('/api/v1/capabilities/tools'),
  refreshTools: () => requestJson<ToolsInfoResponse>('/api/v1/capabilities/tools/refresh', { method: 'POST' }),

  sendMessage: (body: { role: 'user' | 'assistant'; content: string; workspace_id: string }) =>
    requestJson<MessageResponse>('/api/v1/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateProvider: (providerId: string, body: { base_url: string; auth_token: string; model: string }) =>
    requestJson<ProviderUpdatedResponse>(`/api/v1/settings/provider/${providerId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateSettings: (body: { active_provider: string; timeout_ms: number }) =>
    requestJson<OkResponse>('/api/v1/settings/', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}

