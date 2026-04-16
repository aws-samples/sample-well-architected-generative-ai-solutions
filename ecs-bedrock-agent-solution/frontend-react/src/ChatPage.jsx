import React, { useState, useRef, useEffect } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Input,
  Button,
  Box,
  ExpandableSection,
  StatusIndicator,
  Alert,
  ButtonDropdown,
} from '@cloudscape-design/components';
import { sendChat } from './api';
import { parseMessageContent, generateJSONSummary } from './markdown';

const WELCOME = `# Welcome to the AWS Well-Architected Security Assistant! 🛡️

I can help you analyze your AWS security posture.

## Quick Actions:
- **"Check my security services"** — Verify enabled security services
- **"What are my security findings?"** — Review security issues
- **"Analyze my storage encryption"** — Check data protection at rest
- **"Review my network security"** — Examine data protection in transit`;

function Message({ role, content, structuredData, humanSummary }) {
  const { html, jsonSections } = parseMessageContent(content);

  // Split html on JSON section markers and interleave expandable sections
  const parts = html.split(/<!--JSON_SECTION_(\d+)-->/);

  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: '50%',
          background: role === 'user' ? '#FF9900' : '#232F3E',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontSize: 16,
        }}
      >
        {role === 'user' ? '👤' : '🛡️'}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Container
          variant={role === 'user' ? 'default' : 'stacked'}
        >
          {parts.map((part, i) =>
            i % 2 === 0 ? (
              <div key={i} dangerouslySetInnerHTML={{ __html: part }} />
            ) : (
              <ExpandableSection
                key={`json-${part}`}
                headerText="📊 Analysis Results"
                variant="footer"
              >
                <div
                  dangerouslySetInnerHTML={{
                    __html: jsonSections[Number(part)]?.summary || '',
                  }}
                />
                <Box margin={{ top: 's' }}>
                  <ExpandableSection headerText="Raw JSON" variant="footer">
                    <pre style={{ fontSize: 12, overflow: 'auto' }}>
                      {JSON.stringify(jsonSections[Number(part)]?.data, null, 2)}
                    </pre>
                  </ExpandableSection>
                </Box>
              </ExpandableSection>
            )
          )}

          {structuredData && (
            <Box margin={{ top: 's' }}>
              <ExpandableSection headerText="📊 Detailed Results" variant="footer">
                <div
                  dangerouslySetInnerHTML={{
                    __html: humanSummary || generateJSONSummary(structuredData),
                  }}
                />
                <Box margin={{ top: 's' }}>
                  <ExpandableSection headerText="Raw JSON" variant="footer">
                    <pre style={{ fontSize: 12, overflow: 'auto' }}>
                      {JSON.stringify(structuredData, null, 2)}
                    </pre>
                  </ExpandableSection>
                </Box>
              </ExpandableSection>
            </Box>
          )}
        </Container>
      </div>
    </div>
  );
}

export default function ChatPage({ user, onLogout }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: WELCOME },
  ]);
  const [input, setInput] = useState('');
  const [awsAccountId, setAwsAccountId] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async (text) => {
    const msg = (text || input).trim();
    if (!msg) return;
    setInput('');
    setError('');
    setMessages((prev) => [...prev, { role: 'user', content: msg }]);
    setSending(true);
    try {
      const data = await sendChat(msg, awsAccountId);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.response || 'Analysis completed.',
          structuredData: data.structured_data,
          humanSummary: data.human_summary,
        },
      ]);
    } catch (err) {
      setError('Failed to send message. Please try again.');
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
    } finally {
      setSending(false);
    }
  };

  const quickActions = [
    { id: '1', text: 'Security Services' },
    { id: '2', text: 'Security Findings' },
    { id: '3', text: 'Storage Encryption' },
  ];
  const quickMap = {
    '1': 'Check my security services',
    '2': 'What are my security findings?',
    '3': 'Analyze my storage encryption',
  };

  return (
    <SpaceBetween size="m">
      {/* Toolbar */}
      <Container>
        <SpaceBetween direction="horizontal" size="m" alignItems="center">
          <StatusIndicator type="success">Connected</StatusIndicator>
          <Input
            value={awsAccountId}
            onChange={({ detail }) => setAwsAccountId(detail.value)}
            placeholder="AWS Account ID"
            type="text"
            inputMode="numeric"
          />
          <ButtonDropdown
            items={quickActions}
            onItemClick={({ detail }) => send(quickMap[detail.id])}
          >
            Quick Actions
          </ButtonDropdown>
          <Button onClick={() => setMessages([])}>Clear Chat</Button>
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs" alignItems="center">
              <Box fontWeight="bold">{user.email}</Box>
              <Button variant="normal" onClick={onLogout}>
                Logout
              </Button>
            </SpaceBetween>
          </Box>
        </SpaceBetween>
      </Container>

      {/* Messages */}
      <div
        style={{
          height: 'calc(100vh - 280px)',
          overflowY: 'auto',
          padding: '0 4px',
        }}
      >
        {messages.map((m, i) => (
          <Message key={i} {...m} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <SpaceBetween direction="horizontal" size="xs">
        <div style={{ flex: 1 }}>
          <Input
            value={input}
            onChange={({ detail }) => setInput(detail.value)}
            placeholder="Ask about your AWS security posture..."
            onKeyDown={({ detail }) => {
              if (detail.key === 'Enter') send();
            }}
            disabled={sending}
          />
        </div>
        <Button variant="primary" loading={sending} onClick={() => send()}>
          Send
        </Button>
      </SpaceBetween>

      {error && <Alert type="error" dismissible onDismiss={() => setError('')}>{error}</Alert>}

      {/* Info banners */}
      <Alert type="info">
        <a
          href="https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?templateURL=https://workshop-data-public.s3.ap-northeast-1.amazonaws.com/remote-role-mcpreadonlyall-20250831_134154.yaml&stackName=remote-mcp-readonly-role&capabilities=CAPABILITY_IAM"
          target="_blank"
          rel="noreferrer"
        >
          Deploy a ReadOnly IAM Role
        </a>{' '}
        to allow the assistant to scan your AWS environment.
      </Alert>
    </SpaceBetween>
  );
}
