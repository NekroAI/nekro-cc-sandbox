import { useEffect, useMemo, useRef, useState } from 'react'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'

type ShellCreateResponse = { id: string }

export function ShellPanel(props: { open: boolean; workspaceId: string; onClose: () => void }) {
  const { open, workspaceId, onClose } = props
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<Terminal | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pendingSendsRef = useRef<string[]>([])
  const warnedConnectingRef = useRef(false)

  const [shellId, setShellId] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'starting' | 'running' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  const wsUrl = useMemo(() => {
    if (!shellId) return null
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/api/v1/shells/${shellId}/ws`
  }, [shellId])

  useEffect(() => {
    if (!open) return

    let disposed = false
    setStatus('starting')
    setError(null)

    const start = async () => {
      const res = await fetch('/api/v1/shells', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId }),
      })
      if (!res.ok) {
        const text = await res.text().catch((e) => `读取响应失败：${e instanceof Error ? e.message : String(e)}`)
        throw new Error(`创建 shell 失败（HTTP ${res.status}）：${text || res.statusText}`)
      }
      const data = (await res.json()) as ShellCreateResponse
      if (disposed) return
      setShellId(data.id)
      setStatus('running')
    }

    start().catch((e) => {
      if (disposed) return
      setStatus('error')
      setError(e instanceof Error ? e.message : String(e))
    })

    return () => {
      disposed = true
    }
  }, [open, workspaceId])

  useEffect(() => {
    if (!open || !shellId) return
    const el = containerRef.current
    if (!el) return

    const term = new Terminal({
      cursorBlink: true,
      convertEol: true,
      fontSize: 13,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
      theme: {
        background: '#0b1220',
        foreground: '#e5e7eb',
      },
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(el)
    fit.fit()

    termRef.current = term
    fitRef.current = fit

    const ws = new WebSocket(wsUrl!)
    wsRef.current = ws
    warnedConnectingRef.current = false
    pendingSendsRef.current = []

    const writeSystem = (msg: string) => {
      term.writeln(`\r\n[system] ${msg}`)
    }

    const fail = (msg: string, err?: unknown) => {
      const detail = err instanceof Error ? err.message : err ? String(err) : ''
      const full = detail ? `${msg}：${detail}` : msg
      setStatus('error')
      setError(full)
      term.writeln(`\r\n[error] ${full}`)
    }

    const safeSend = (payload: string) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(payload)
        return
      }
      // 连接尚未建立：缓存输入，避免刷屏报错
      pendingSendsRef.current.push(payload)
      if (!warnedConnectingRef.current) {
        warnedConnectingRef.current = true
        writeSystem('连接尚未建立，输入已缓存，等待 WebSocket 建立后发送…')
      }
    }

    const sendResize = () => {
      const cols = term.cols
      const rows = term.rows
      try {
        safeSend(JSON.stringify({ type: 'resize', cols, rows }))
      } catch (e) {
        fail('发送 resize 失败', e)
      }
    }

    ws.addEventListener('open', () => {
      writeSystem('已连接')
      sendResize()
      // flush cached payloads
      const pending = pendingSendsRef.current
      pendingSendsRef.current = []
      for (const p of pending) {
        try {
          ws.send(p)
        } catch (e) {
          fail('发送缓存数据失败', e)
          break
        }
      }
    })

    ws.addEventListener('message', (evt) => {
      try {
        const obj = JSON.parse(String(evt.data)) as { type: string; data?: string; message?: string }
        if (obj.type === 'output' && obj.data) {
          term.write(obj.data)
        } else if (obj.type === 'error') {
          term.writeln(`\r\n[error] ${obj.message ?? 'unknown'}`)
        } else if (obj.type === 'exit') {
          term.writeln('\r\n[process exited]')
        }
      } catch (e) {
        // 不静默：保留原始输出并提示解析失败
        term.writeln(`\r\n[warn] ws message parse failed: ${e instanceof Error ? e.message : String(e)}`)
        term.write(String(evt.data))
      }
    })

    ws.addEventListener('error', () => {
      // 浏览器不会给出太多细节，这里给出可操作提示
      fail('WebSocket 连接失败（可能是 Vite 代理未转发 ws 或后端未启动）')
    })

    ws.addEventListener('close', () => {
      writeSystem('已断开')
    })

    const connectTimeout = window.setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN && status !== 'error') {
        fail('WebSocket 连接超时（10s）')
      }
    }, 10000)

    const disposeAll = async () => {
      try {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'close' }))
        }
      } catch (e) {
        writeSystem(`关闭 ws 发送失败：${e instanceof Error ? e.message : String(e)}`)
      }
      try {
        ws.close()
      } catch (e) {
        writeSystem(`关闭 ws 失败：${e instanceof Error ? e.message : String(e)}`)
      }
      try {
        const res = await fetch(`/api/v1/shells/${shellId}`, { method: 'DELETE' })
        if (!res.ok) {
          const text = await res.text().catch(() => '')
          writeSystem(`销毁 shell 失败（HTTP ${res.status}）${text ? `: ${text}` : ''}`)
        }
      } catch (e) {
        writeSystem(`销毁 shell 请求失败：${e instanceof Error ? e.message : String(e)}`)
      }
      try {
        term.dispose()
      } catch (e) {
        // 兜底：dispose 失败不应阻塞清理
        // eslint-disable-next-line no-console
        console.error('term.dispose failed', e)
      }
    }

    const onData = term.onData((data) => {
      try {
        safeSend(JSON.stringify({ type: 'input', data }))
      } catch (e) {
        fail('发送输入失败', e)
      }
    })

    const onResize = () => {
      fit.fit()
      try {
        sendResize()
      } catch (e) {
        fail('处理 resize 失败', e)
      }
    }

    window.addEventListener('resize', onResize)
    const onBeforeUnload = () => {
      // 尽力而为的清理：页面关闭时通知后端销毁会话
      disposeAll()
    }
    window.addEventListener('beforeunload', onBeforeUnload)

    return () => {
      window.clearTimeout(connectTimeout)
      onData.dispose()
      window.removeEventListener('resize', onResize)
      window.removeEventListener('beforeunload', onBeforeUnload)
      disposeAll()
      termRef.current = null
      fitRef.current = null
      wsRef.current = null
      setShellId(null)
      setStatus('idle')
      setError(null)
    }
  }, [open, shellId, wsUrl])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center">
      <div className="w-[95vw] h-[85vh] bg-gray-900 border border-gray-700 rounded-lg shadow-xl overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="text-sm font-semibold text-white">Shell 面板</div>
            <div className="text-xs text-gray-400">
              {status === 'starting' && '启动中...'}
              {status === 'running' && `会话 ${shellId}`}
              {status === 'error' && '启动失败'}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {shellId && (
              <button
                className="px-3 py-1 text-xs rounded bg-red-700 hover:bg-red-600 text-white"
                onClick={onClose}
                title="关闭并销毁 shell"
              >
                关闭
              </button>
            )}
            {!shellId && (
              <button className="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-gray-600 text-white" onClick={onClose}>
                关闭
              </button>
            )}
          </div>
        </div>

        {status === 'error' && (
          <div className="p-4 text-sm text-red-200 bg-red-950 border-b border-red-900">
            {error ?? '未知错误'}
          </div>
        )}

        <div className="flex-1 p-2">
          <div ref={containerRef} className="w-full h-full" />
        </div>
      </div>
    </div>
  )
}

