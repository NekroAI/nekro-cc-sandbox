import { useEffect, useMemo, useRef, useState } from 'react'
import 'xterm/css/xterm.css'
import { ApiHttpError, api } from './api/client'
import type { SettingsInfoResponse, StatusResponse, ToolsInfoResponse, WorkspacesResponse } from './api/types'
import { MarkdownView } from './components/MarkdownView'
import { ShellPanel } from './components/ShellPanel'

type TabKey = 'chat' | 'workspaces' | 'diagnostics'
type Tone = 'normal' | 'error'

interface UiMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  tone: Tone
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null
}

function formatApiError(e: unknown): string {
  if (e instanceof ApiHttpError) {
    const payload = e.payload
    if (isRecord(payload) && payload.status === 'error' && isRecord(payload.error)) {
      const msg = typeof payload.error.message === 'string' ? payload.error.message : e.message
      const errId = typeof payload.error.err_id === 'string' ? payload.error.err_id : null
      return errId ? `${msg}（err_id=${errId}）` : msg
    }
    return e.message
  }
  if (e instanceof Error) return e.message
  return String(e)
}

export default function App() {
  const [tab, setTab] = useState<TabKey>('chat')
  const [connecting, setConnecting] = useState(true)
  const [apiConnected, setApiConnected] = useState(false)

  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)

  const [workspaces, setWorkspaces] = useState<WorkspacesResponse | null>(null)
  const [workspacesError, setWorkspacesError] = useState<string | null>(null)
  const [activeWorkspaceId, setActiveWorkspaceId] = useState('default')

  const [toolsInfo, setToolsInfo] = useState<ToolsInfoResponse | null>(null)

  const [messages, setMessages] = useState<UiMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)

  const [toast, setToast] = useState<string | null>(null)
  const [shellOpen, setShellOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settings, setSettings] = useState<SettingsInfoResponse | null>(null)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [timeoutMs, setTimeoutMs] = useState<number>(300000)
  const [configForm, setConfigForm] = useState<{ base_url: string; auth_token: string; model: string }>({
    base_url: '',
    auth_token: '',
    model: '',
  })
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')

  const workspaceOptions = useMemo(() => workspaces?.workspaces ?? [], [workspaces])
  const activeWorkspace = useMemo(
    () => workspaceOptions.find((w) => w.id === activeWorkspaceId) ?? null,
    [workspaceOptions, activeWorkspaceId],
  )
  const runtimeAvailable = status?.services.claude_runtime === 'available'
  const tools = toolsInfo?.tools ?? null
  const needsInit = apiConnected && runtimeAvailable && tools === null

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 4500)
    return () => clearTimeout(t)
  }, [toast])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const boot = async () => {
    setConnecting(true)
    try {
      const [s, ws, t] = await Promise.all([api.getStatus(), api.listWorkspaces(), api.getTools()])
      setStatus(s)
      setWorkspaces(ws)
      setToolsInfo(t)
      setStatusError(null)
      setWorkspacesError(null)
      setApiConnected(true)

      const hasDefault = ws.workspaces.some((w) => w.id === 'default')
      setActiveWorkspaceId(hasDefault ? 'default' : (ws.workspaces[0]?.id ?? 'default'))

      setMessages([
        { role: 'assistant', content: '已连接到 nekro-cc-sandbox。', timestamp: Date.now(), tone: 'normal' },
      ])
    } catch (e) {
      setApiConnected(false)
      setStatusError(formatApiError(e))
    } finally {
      setConnecting(false)
    }
  }

  useEffect(() => {
    boot()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!settingsOpen) return
    api
      .getSettings()
      .then((data) => {
        setSettings(data)
        setSettingsError(null)
        setSelectedProvider(data.active_provider)
        setTimeoutMs(data.timeout_ms)
        if (data.current_config) {
          setConfigForm({ base_url: data.current_config.base_url, auth_token: '', model: data.current_config.model })
        }
      })
      .catch((e) => {
        setSettings(null)
        setSettingsError(formatApiError(e))
      })
  }, [settingsOpen])

  const refreshAll = async () => {
    try {
      const [s, ws, t] = await Promise.all([api.getStatus(), api.listWorkspaces(), api.getTools()])
      setStatus(s)
      setWorkspaces(ws)
      setToolsInfo(t)
      setStatusError(null)
      setWorkspacesError(null)
      setApiConnected(true)
      setToast('已刷新')
    } catch (e) {
      setToast(formatApiError(e))
    }
  }

  const syncSessionForWorkspace = (workspaceId: string, sessionId: string) => {
    if (!sessionId) return

    setWorkspaces((prev) => {
      if (!prev) return prev
      return { workspaces: prev.workspaces.map((w) => (w.id === workspaceId ? { ...w, session_id: sessionId } : w)) }
    })
  }

  const initClaude = async () => {
    if (!apiConnected || sending) return
    setSending(true)
    try {
      const info = await api.refreshTools()
      setToolsInfo(info)
      await refreshAll()
      setToast(info.tools ? '工具列表已刷新' : '工具列表为空')
    } catch (e) {
      setToast(`刷新工具失败：${formatApiError(e)}`)
    } finally {
      setSending(false)
    }
  }

  const sendMessage = async () => {
    if (!apiConnected || sending) return
    const content = input.trim()
    if (!content) return

    setMessages((prev) => [...prev, { role: 'user', content, timestamp: Date.now(), tone: 'normal' }])
    setInput('')
    setSending(true)
    try {
      const r = await api.sendMessage({ role: 'user', content, workspace_id: activeWorkspaceId })
      if (r.session_id) syncSessionForWorkspace(activeWorkspaceId, r.session_id)

      if (r.success && r.message.trim()) {
        setMessages((prev) => [...prev, { role: 'assistant', content: r.message, timestamp: Date.now(), tone: 'normal' }])
        return
      }

      const fallback = r.success ? 'Claude 返回了空响应（可能是后端解析失败或 CLI 无输出）。' : r.message || '操作失败'
      const detail = r.error
        ? `${fallback}\n\n- 错误码：\`${r.error.code}\`\n- 追踪ID：\`${r.error.err_id}\`${r.error.retryable ? '\n- 建议：可重试' : ''}`
        : fallback
      setMessages((prev) => [...prev, { role: 'assistant', content: `错误：${detail}`, timestamp: Date.now(), tone: 'error' }])
      setToast(r.error ? `${r.error.message}（${r.error.code}/${r.error.err_id}）` : fallback)
    } catch (e) {
      const msg = formatApiError(e)
      setMessages((prev) => [...prev, { role: 'assistant', content: `错误：发送失败：${msg}`, timestamp: Date.now(), tone: 'error' }])
      setToast(`发送失败：${msg}`)
    } finally {
      setSending(false)
    }
  }

  const resetSession = async () => {
    if (!apiConnected) return
    setSending(true)
    try {
      await api.resetWorkspaceSession(activeWorkspaceId)
      setWorkspaces((prev) => (prev ? { workspaces: prev.workspaces.map((w) => (w.id === activeWorkspaceId ? { ...w, session_id: null } : w)) } : prev))
      setMessages([{ role: 'assistant', content: '会话已重置。', timestamp: Date.now(), tone: 'normal' }])
      setToast('会话已重置')
    } catch (e) {
      setToast(`重置失败：${formatApiError(e)}`)
    } finally {
      setSending(false)
    }
  }

  const saveSettings = async () => {
    setSaving(true)
    setSaveStatus('idle')
    try {
      if (!selectedProvider) throw new Error('未选择提供商')
      await api.updateProvider(selectedProvider, configForm)
      await api.updateSettings({ active_provider: selectedProvider, timeout_ms: timeoutMs })
      const s = await api.getSettings()
      setSettings(s)
      setSelectedProvider(s.active_provider)
      setTimeoutMs(s.timeout_ms)
      if (s.current_config) setConfigForm({ base_url: s.current_config.base_url, auth_token: '', model: s.current_config.model })
      setSaveStatus('success')
      setTimeout(() => setSettingsOpen(false), 800)
    } catch (e) {
      setSaveStatus('error')
      setToast(formatApiError(e))
    } finally {
      setSaving(false)
    }
  }

  if (connecting) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-900 text-gray-200">
        <div className="text-sm">连接中...</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100">
      <header className="flex items-center justify-between px-6 py-4 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-3">
          <div className="text-lg font-semibold">nekro-cc-sandbox</div>
          <span className={`px-2 py-0.5 text-xs rounded-full ${apiConnected ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
            {apiConnected ? '已连接' : '已断开'}
          </span>
          {apiConnected && (
            <span className={`px-2 py-0.5 text-xs rounded-full ${runtimeAvailable ? 'bg-indigo-900 text-indigo-200' : 'bg-yellow-950 text-yellow-200'}`}>
              runtime: {runtimeAvailable ? 'available' : 'unavailable'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <select
            value={activeWorkspaceId}
            onChange={(e) => setActiveWorkspaceId(e.target.value)}
            className="text-sm bg-gray-700 border border-gray-600 rounded px-2 py-2 text-gray-100"
            disabled={!apiConnected || workspaceOptions.length === 0}
          >
            {workspaceOptions.map((w) => (
              <option key={w.id} value={w.id}>
                {w.id}
              </option>
            ))}
          </select>

          <button
            className="px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded disabled:opacity-50"
            disabled={!apiConnected}
            onClick={() => setShellOpen(true)}
          >
            Shell
          </button>
          {needsInit && (
            <button
              className="px-3 py-2 text-sm bg-indigo-700 hover:bg-indigo-600 rounded disabled:opacity-50"
              disabled={!apiConnected || sending}
              onClick={initClaude}
              title="工具列表未就绪，点击刷新工具列表"
            >
              刷新工具列表
            </button>
          )}
          <button
            className="px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded disabled:opacity-50"
            disabled={!apiConnected}
            onClick={refreshAll}
          >
            刷新
          </button>
          <button className="px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded" onClick={() => setSettingsOpen(true)}>
            设置
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-56 bg-gray-900 border-r border-gray-800 p-4 hidden md:block">
          <div className="text-xs text-gray-400 uppercase tracking-wider mb-3">面板</div>
          {([
            ['chat', '聊天'],
            ['workspaces', '工作区'],
            ['diagnostics', '诊断'],
          ] as Array<[TabKey, string]>).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`w-full text-left px-3 py-2 rounded mb-1 text-sm ${tab === k ? 'bg-gray-800 text-white' : 'text-gray-300 hover:bg-gray-800'}`}
            >
              {label}
            </button>
          ))}

          {statusError && <div className="mt-4 text-xs text-red-200 bg-red-950 border border-red-900 rounded p-2">{statusError}</div>}
        </aside>

        <main className="flex-1 flex flex-col">
          {tab === 'chat' && (
            <>
              <div className="px-6 py-3 border-b border-gray-800 text-sm text-gray-300">
                当前工作区：<span className="text-white">{activeWorkspaceId}</span>
                {activeWorkspace?.session_id ? (
                  <span className="ml-3 text-gray-400">session: {activeWorkspace.session_id.slice(0, 8)}...</span>
                ) : (
                  <span className="ml-3 text-yellow-200">（未初始化 session）</span>
                )}
                <button
                  type="button"
                  className="ml-4 px-2 py-1 text-xs rounded bg-gray-800 border border-gray-700 text-gray-200 hover:bg-gray-700 disabled:opacity-50"
                  disabled={!apiConnected || sending}
                  onClick={resetSession}
                  title="清空当前工作区 session_id，开始新的对话上下文"
                >
                  重置会话
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.map((m, idx) => (
                  <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[70%] rounded-lg px-4 py-3 ${
                        m.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : m.tone === 'error'
                            ? 'bg-red-950 text-red-100 border border-red-900'
                            : 'bg-gray-800 text-gray-100'
                      }`}
                    >
                      {m.role === 'user' ? m.content : <MarkdownView content={m.content} tone={m.tone} />}
                    </div>
                  </div>
                ))}

                {sending && (
                  <div className="flex justify-start">
                    <div className="bg-gray-800 rounded-lg px-4 py-3 text-gray-300 text-sm">发送中...</div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              <div className="p-4 bg-gray-800 border-t border-gray-700">
                <div className="flex gap-3">
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        sendMessage()
                      }
                    }}
                    placeholder={apiConnected ? '描述你想做什么...' : '连接中...'}
                    disabled={!apiConnected || sending}
                    className="flex-1 px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!apiConnected || sending || !input.trim()}
                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
                  >
                    发送
                  </button>
                </div>
              </div>
            </>
          )}

          {tab === 'workspaces' && (
            <div className="p-6 space-y-2 overflow-auto">
              {workspacesError && <div className="text-sm text-red-200 bg-red-950 border border-red-900 rounded p-3">{workspacesError}</div>}
              {!workspaces && <div className="text-sm text-gray-400">尚未获取工作区列表</div>}
              {workspaces?.workspaces.map((w) => (
                <div key={w.id} className="border border-gray-800 rounded p-3 bg-gray-900/40">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-white">{w.id}</div>
                    {w.session_id && <div className="text-xs text-gray-400">session: {w.session_id.slice(0, 8)}...</div>}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">{w.path}</div>
                </div>
              ))}
            </div>
          )}

          {tab === 'diagnostics' && (
            <div className="p-6 space-y-4 overflow-auto">
              <div className="flex items-center justify-between">
                <div className="text-lg font-semibold">诊断</div>
                <div className="flex gap-2">
                  {needsInit && (
                    <button className="px-3 py-2 text-sm rounded bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50" disabled={!apiConnected || sending} onClick={initClaude}>
                      刷新工具列表
                    </button>
                  )}
                  <button className="px-3 py-2 text-sm rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50" disabled={!apiConnected} onClick={refreshAll}>
                    刷新
                  </button>
                </div>
              </div>
              {!status && <div className="text-sm text-gray-400">尚未获取状态</div>}
              {status && (
                <>
                  <div className="border border-gray-800 rounded p-4 bg-gray-900/40">
                    <div className="text-sm text-gray-200 mb-2">服务状态</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="bg-gray-800/60 border border-gray-700 rounded p-2">
                        <div className="text-xs text-gray-400">API</div>
                        <div className="text-gray-100">{status.services.api}</div>
                      </div>
                      <div className="bg-gray-800/60 border border-gray-700 rounded p-2">
                        <div className="text-xs text-gray-400">Claude Runtime</div>
                        <div className="text-gray-100">{status.services.claude_runtime}</div>
                      </div>
                    </div>
                  </div>

                  <div className="border border-gray-800 rounded p-4 bg-gray-900/40">
                    <div className="text-sm text-gray-200 mb-2">工具列表</div>
                    {tools ? (
                      <div className="flex flex-wrap gap-2">
                        {tools.map((t) => (
                          <span key={t} className="text-xs px-2 py-1 rounded bg-gray-800 border border-gray-700 text-gray-200">
                            {t}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-yellow-200 bg-yellow-950 border border-yellow-900 rounded p-3">
                        工具列表为空：请点击“刷新工具列表”重新探测。
                      </div>
                    )}
                  </div>

                  {status.capabilities.policy && (
                    <div className="border border-gray-800 rounded p-4 bg-gray-900/40">
                      <div className="text-sm text-gray-200 mb-2">policy</div>
                      <div className="grid grid-cols-3 gap-2 text-sm text-gray-200">
                        <div className="bg-gray-800/60 border border-gray-700 rounded p-2">
                          <div className="text-xs text-gray-400">命令</div>
                          <div>{status.capabilities.policy.allow_command_execution ? '允许' : '禁止'}</div>
                        </div>
                        <div className="bg-gray-800/60 border border-gray-700 rounded p-2">
                          <div className="text-xs text-gray-400">网络</div>
                          <div>{status.capabilities.policy.allow_network ? '允许' : '禁止'}</div>
                        </div>
                        <div className="bg-gray-800/60 border border-gray-700 rounded p-2">
                          <div className="text-xs text-gray-400">写入</div>
                          <div>{status.capabilities.policy.allow_file_modification ? '允许' : '禁止'}</div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </main>
      </div>

      <ShellPanel open={shellOpen} workspaceId={activeWorkspaceId} onClose={() => setShellOpen(false)} />

      {toast && (
        <div className="fixed bottom-24 left-1/2 transform -translate-x-1/2 z-50">
          <div className="bg-gray-800 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-3 max-w-md border border-gray-700">
            <span className="text-sm">{toast}</span>
            <button onClick={() => setToast(null)} className="ml-2 text-white/80 hover:text-white">
              <span className="text-xs">关闭</span>
            </button>
          </div>
        </div>
      )}

      {settingsOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold text-white">设置</h2>
              <button onClick={() => setSettingsOpen(false)} className="text-gray-400 hover:text-white">
                关闭
              </button>
            </div>

            <div className="p-4 space-y-4">
              {settingsError && <div className="text-sm text-red-200 bg-red-950 border border-red-900 rounded p-3">{settingsError}</div>}
              {!settings && !settingsError && <div className="text-sm text-gray-300">加载中...</div>}

              {settings && (
                <div className="space-y-3">
                  <div>
                    <div className="text-sm text-gray-200 mb-2">提供商</div>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.values(settings.providers).map((p) => (
                        <button
                          key={p.id}
                          onClick={() => {
                            setSelectedProvider(p.id)
                            if (p.id === settings.active_provider && settings.current_config) {
                              setConfigForm({ base_url: settings.current_config.base_url, auth_token: '', model: settings.current_config.model })
                            } else {
                              setConfigForm({ base_url: p.base_url, auth_token: '', model: p.model })
                            }
                          }}
                          className={`p-2 text-sm rounded-lg border ${
                            selectedProvider === p.id ? 'border-blue-500 bg-blue-500/20 text-white' : 'border-gray-600 bg-gray-700 text-gray-300 hover:border-gray-500'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span>{p.name}</span>
                            {p.configured && <span className="text-xs text-green-300">已配置</span>}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">{p.model}</div>
                        </button>
                      ))}
                    </div>
                    <div className="text-xs text-gray-400 mt-2">token 在后端会脱敏；输入框留空不显示旧 token。后端支持“留空保持不变”。</div>
                  </div>

                  <div>
                    <label className="block text-sm text-gray-300 mb-1">超时（毫秒）</label>
                    <input
                      type="number"
                      value={timeoutMs}
                      onChange={(e) => setTimeoutMs(Number(e.target.value))}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-300 mb-1">Base URL</label>
                    <input
                      value={configForm.base_url}
                      onChange={(e) => setConfigForm({ ...configForm, base_url: e.target.value })}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-300 mb-1">Token</label>
                    <input
                      type="password"
                      value={configForm.auth_token}
                      onChange={(e) => setConfigForm({ ...configForm, auth_token: e.target.value })}
                      placeholder="留空保持不变"
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-300 mb-1">模型</label>
                    <input
                      value={configForm.model}
                      onChange={(e) => setConfigForm({ ...configForm, model: e.target.value })}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 p-4 border-t border-gray-700">
              {saveStatus === 'success' && <span className="text-green-400 text-sm">已保存！</span>}
              {saveStatus === 'error' && <span className="text-red-400 text-sm">保存失败</span>}
              <button onClick={() => setSettingsOpen(false)} className="px-4 py-2 text-gray-300 hover:text-white">
                取消
              </button>
              <button
                onClick={saveSettings}
                disabled={saving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg"
              >
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

