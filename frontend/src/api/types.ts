// 前端严格对齐后端 schemas.py 的类型定义（用于接口契约）

export type ClaudeRuntimeAvailability = 'available' | 'unavailable'

export interface ServicesInfo {
  api: 'running'
  claude_runtime: ClaudeRuntimeAvailability
}

export interface WorkspacesSummary {
  count: number
  ids: string[]
}

export interface PolicySummary {
  allowed_tools: string[]
  blocked_tools: string[]
  allow_network: boolean
  allow_file_modification: boolean
  allow_command_execution: boolean
}

export interface CapabilitiesInfo {
  tools: string[] | null
  policy: PolicySummary | null
}

export interface StatusResponse {
  status: 'healthy'
  services: ServicesInfo
  capabilities: CapabilitiesInfo
  workspaces: WorkspacesSummary
  version: string
}

export interface WorkspaceInfo {
  id: string
  name: string
  path: string
  created_at: string
  updated_at: string
  session_id: string | null
  metadata: Record<string, unknown>
}

export interface WorkspacesResponse {
  workspaces: WorkspaceInfo[]
}

export interface SessionInfo {
  workspace_id: string
  session_id: string
}

export interface SessionsResponse {
  sessions: SessionInfo[]
}

export interface SessionResetResponse {
  status: 'ok'
  workspace_id: string
  old_session_id: string | null
  new_session_id: string | null
}

export type ErrorCode =
  | 'RUNTIME_UNAVAILABLE'
  | 'INTERNAL_ERROR'
  | 'WORKSPACE_NOT_FOUND'
  | 'CLAUDE_CLI_ERROR_RESULT'
  | 'CLAUDE_CLI_NO_PARSEABLE_OUTPUT'
  | 'SHELL_MANAGER_UNAVAILABLE'
  | 'SHELL_SESSION_NOT_FOUND'

export interface ErrorInfo {
  err_id: string
  code: ErrorCode
  message: string
  retryable: boolean
  details?: Record<string, unknown>
}

export interface MessageResponse {
  session_id: string
  message: string
  success: boolean
  error: ErrorInfo | null
}

export interface ProviderInfo {
  id: string
  name: string
  base_url: string
  model: string
  configured: boolean
  is_active: boolean
}

export interface CurrentProviderConfig {
  base_url: string
  auth_token: string
  model: string
}

export interface SettingsInfoResponse {
  active_provider: string
  timeout_ms: number
  providers: Record<string, ProviderInfo>
  current_config: CurrentProviderConfig | null
}

export interface ToolsInfoResponse {
  status: 'ok'
  tools: string[] | null
  source: 'cache' | 'probe'
}

export interface ProviderUpdatedResponse {
  status: 'ok'
  provider: string
}

export interface OkResponse {
  status: 'ok'
}

