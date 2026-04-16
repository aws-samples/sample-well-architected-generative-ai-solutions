/** Send a chat message to the backend API */
export async function sendChatMessage(message, token, awsAccountId) {
  const body = {
    message,
    session_id: `web-session-${Date.now()}`,
  };
  if (awsAccountId) body.aws_account_id = awsAccountId;

  const res = await fetch(window.APP_CONFIG.api.endpoints.chat, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
