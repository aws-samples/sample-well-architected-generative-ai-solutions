import { getToken } from './auth';

export async function sendChat(message, awsAccountId) {
  const body = { message, session_id: `web-session-${Date.now()}` };
  if (awsAccountId) body.aws_account_id = awsAccountId;

  const res = await fetch(window.APP_CONFIG.api.endpoints.chat, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
