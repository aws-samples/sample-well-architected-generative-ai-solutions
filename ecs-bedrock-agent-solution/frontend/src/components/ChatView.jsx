import React, { useState, useRef, useEffect } from 'react';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Button from '@cloudscape-design/components/button';
import Input from '@cloudscape-design/components/input';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import Box from '@cloudscape-design/components/box';
import Grid from '@cloudscape-design/components/grid';
import Link from '@cloudscape-design/components/link';
import Alert from '@cloudscape-design/components/alert';
import ChatMessage from './ChatMessage';
import { sendChatMessage } from '../services/chat';

const WELCOME_MESSAGE = `# Welcome to the AWS Well-Architected Security Assistant! 🛡️

I can help you analyze your AWS security posture with **comprehensive markdown support**!

## Quick Actions:
- **"Check my security services"** — Verify enabled security services
- **"What are my security findings?"** — Review security issues
- **"Analyze my storage encryption"** — Check data protection at rest
- **"Review my network security"** — Examine data protection in transit

### Features:
- **Rich markdown formatting** with tables, lists, and code blocks
- **Interactive JSON data** with collapsible sections
- **Real-time security analysis** powered by AWS Well-Architected Framework
- **Structured recommendations** for security improvements

Try the quick action buttons above or ask me anything about your AWS security!`;

export default function ChatView({ user, onError }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: WELCOME_MESSAGE },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [awsAccountId, setAwsAccountId] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg) return;
    setInput('');

    setMessages((prev) => [...prev, { role: 'user', content: msg }]);
    setSending(true);

    try {
      const data = await sendChatMessage(msg, user.token, awsAccountId);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.response || 'Analysis completed.',
          structuredData: data.structured_data || null,
          humanSummary: data.human_summary || null,
        },
      ]);
    } catch (err) {
      onError({ type: 'error', content: 'Failed to send message. Please try again.' });
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
    } finally {
      setSending(false);
    }
  };

  const clearMessages = () => {
    setMessages([
      { role: 'assistant', content: '🧹 **Chat cleared.** Ready for new conversation with full markdown support!' },
    ]);
  };

  const handleKeyDown = (e) => {
    if (e.detail.key === 'Enter' && !sending) send();
  };

  return (
    <SpaceBetween size="m">
      {/* Connection & controls bar */}
      <Container>
        <SpaceBetween size="xs">
          <Grid
            gridDefinition={[
              { colspan: { default: 12, s: 3 } },
              { colspan: { default: 12, s: 3 } },
              { colspan: { default: 12, s: 6 } },
            ]}
          >
            <StatusIndicator type="success">Connected to AWS Security Assistant</StatusIndicator>
            <Input
              placeholder="AWS Account ID"
              value={awsAccountId}
              onChange={({ detail }) => setAwsAccountId(detail.value.replace(/\D/g, '').slice(0, 12))}
              inputMode="numeric"
            />
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => send('Check my security services')}>Security Services</Button>
              <Button onClick={() => send('What are my security findings?')}>Security Findings</Button>
              <Button onClick={() => send('Analyze my storage encryption')}>Storage Encryption</Button>
              <Button onClick={clearMessages} iconName="remove" variant="normal">
                Clear Chat
              </Button>
            </SpaceBetween>
          </Grid>
        </SpaceBetween>
      </Container>

      {/* Messages area */}
      <Container
        header={<Header variant="h2">Conversation</Header>}
        fitHeight
      >
        <div style={{ maxHeight: 'calc(100vh - 380px)', overflowY: 'auto', padding: '4px 0' }}>
          <SpaceBetween size="m">
            {messages.map((m, i) => (
              <ChatMessage key={i} role={m.role} content={m.content} structuredData={m.structuredData} humanSummary={m.humanSummary} />
            ))}
            <div ref={bottomRef} />
          </SpaceBetween>
        </div>
      </Container>

      {/* Input bar */}
      <Container>
        <Grid gridDefinition={[{ colspan: { default: 10 } }, { colspan: { default: 2 } }]}>
          <Input
            placeholder="Ask about your AWS security posture..."
            value={input}
            onChange={({ detail }) => setInput(detail.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
          />
          <Button variant="primary" loading={sending} onClick={() => send()} fullWidth>
            Send
          </Button>
        </Grid>
      </Container>

      {/* Info banners */}
      <Alert type="info">
        <Link
          href="https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review?templateURL=https://workshop-data-public.s3.ap-northeast-1.amazonaws.com/remote-role-mcpreadonlyall-20250831_134154.yaml&stackName=remote-mcp-readonly-role&capabilities=CAPABILITY_IAM"
          external
        >
          Click here
        </Link>{' '}
        to deploy a <em>ReadOnly IAM Role</em> in the target AWS account to allow Cloud Optimization Assistant to scan
        your environment.
      </Alert>
      <Alert type="info">
        📊{' '}
        <Link href="architecture_diagram.html" external>
          View Architecture Diagram
        </Link>{' '}
        to understand the complete Cloud Optimization Assistant stack and component interactions.
      </Alert>
    </SpaceBetween>
  );
}
