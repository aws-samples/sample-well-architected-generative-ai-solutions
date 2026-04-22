import React, { useState, useRef, useEffect, useMemo } from 'react'
import AppLayout from '@cloudscape-design/components/app-layout'
import Container from '@cloudscape-design/components/container'
import Header from '@cloudscape-design/components/header'
import SpaceBetween from '@cloudscape-design/components/space-between'
import Button from '@cloudscape-design/components/button'
import Textarea from '@cloudscape-design/components/textarea'
import Box from '@cloudscape-design/components/box'
import StatusIndicator from '@cloudscape-design/components/status-indicator'

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const chatRef = useRef(null)

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [])

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight
  }, [messages])

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = window.APP_CONFIG?.api?.wsEndpoint || `${proto}//${location.host}/ws`
    const ws = new WebSocket(wsUrl)
    ws.onopen = () => setConnected(true)
    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      setMessages(prev => [...prev, { role: 'ai', type: msg.type, text: msg.message || '', data: msg.data }])
    }
    wsRef.current = ws
  }

  function send() {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== 1) return
    setMessages(prev => [...prev, { role: 'user', text: input }])
    wsRef.current.send(JSON.stringify({ text: input }))
    setInput('')
  }

  return (
    <AppLayout
      navigationHide
      toolsHide
      content={
        <SpaceBetween size="l">
          <Header variant="h1" description="Async task dispatch via Bedrock AgentCore Runtime">
            AgentCore Long-Running Orchestrator
          </Header>
          <Container header={<Header variant="h2" actions={
            <StatusIndicator type={connected ? 'success' : 'error'}>{connected ? 'Connected' : 'Disconnected'}</StatusIndicator>
          }>Chat</Header>}>
            <SpaceBetween size="s">
              <div ref={chatRef} style={{ height: '400px', overflowY: 'auto', padding: '8px' }}>
                <SpaceBetween size="xs">
                  {messages.map((m, i) => (
                    <ChatMessage key={i} message={m} />
                  ))}
                </SpaceBetween>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
                <div style={{ flex: 1 }}>
                  <Textarea
                    value={input}
                    onChange={({ detail }) => setInput(detail.value)}
                    onKeyDown={(e) => { if (e.detail.key === 'Enter' && !e.detail.shiftKey) { e.preventDefault(); send() } }}
                    placeholder="Ask about your AWS environment..."
                    rows={2}
                  />
                </div>
                <Button variant="primary" onClick={send}>Send</Button>
              </div>
            </SpaceBetween>
          </Container>
        </SpaceBetween>
      }
    />
  )
}

function renderMarkdown(text) {
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre style="background:#0f1b2d;padding:10px;border-radius:6px;margin:8px 0;overflow-x:auto;font-size:12px"><code>$2</code></pre>')
    // inline code
    .replace(/`([^`]+)`/g, '<code style="background:#0f1b2d;padding:2px 5px;border-radius:3px;font-size:12px">$1</code>')
    // bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // headers
    .replace(/^### (.+)$/gm, '<div style="font-size:15px;font-weight:700;margin:10px 0 4px">$1</div>')
    .replace(/^## (.+)$/gm, '<div style="font-size:16px;font-weight:700;margin:12px 0 4px">$1</div>')
    .replace(/^# (.+)$/gm, '<div style="font-size:18px;font-weight:700;margin:14px 0 6px">$1</div>')
    // unordered lists
    .replace(/^[*-] (.+)$/gm, '<li style="margin-left:16px">$1</li>')
    // ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li style="margin-left:16px;list-style-type:decimal">$1</li>')
    // horizontal rule
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #555;margin:8px 0">')
    // line breaks (double newline = paragraph)
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
  return html
}

function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  const bgColor = isUser ? '#0073bb' : message.type === 'task_error' ? '#1a0000' : '#232f3e'
  const borderLeft = message.type === 'task_complete' ? '3px solid #1d8102' : message.type === 'task_error' ? '3px solid #d13212' : 'none'

  const rendered = useMemo(() => {
    if (isUser) return null
    return renderMarkdown(message.text || '')
  }, [message.text, isUser])

  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      <div style={{ maxWidth: '75%', padding: '10px 14px', borderRadius: '8px', background: bgColor, color: '#fff', borderLeft, fontSize: '14px', lineHeight: '1.6' }}>
        {isUser ? message.text : <div dangerouslySetInnerHTML={{ __html: rendered }} />}
        {message.data && <pre style={{ marginTop: '8px', padding: '8px', background: '#0f1b2d', borderRadius: '4px', fontSize: '12px', overflow: 'auto' }}>{JSON.stringify(message.data, null, 2)}</pre>}
      </div>
    </div>
  )
}
