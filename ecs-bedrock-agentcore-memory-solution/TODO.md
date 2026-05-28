# Remediation TODO — sandbox-cloudops-xacct-0526

Stack: `sandbox-cloudops-xacct-0526`
URL: https://d44uvol1phu4p.cloudfront.net
Date: 2026-05-28

---

## Immediate (before public demo)

- [ ] **Enforce Cognito auth** on all `/api/*` and `/ws` routes — backend middleware
- [ ] **Fix cross-account CFN link** — update HTML to reference `sandbox-cloudops-xacct-0526` instead of deleted `sandbox-longrun-0426`
- [ ] **Add rate limiting** — per-IP or per-user throttle on ALB or backend
- [ ] **Enable DEMO_MASK_OUTPUT=true** — mask account IDs/resource names in responses
- [ ] **Clear task history** — purge DynamoDB of old tasks containing real billing/infra data

## Short-term (stability)

- [ ] **Fix WebSocket race condition** — guard against `websocket.send` after `websocket.close`
- [ ] **ECS desired count ≥ 2** — backend redundancy
- [ ] **AgentCore Runtime keep-warm** — scheduled warmup or provisioned concurrency
- [ ] **Per-user task isolation** — use Cognito user ID as DynamoDB partition key instead of "default"
- [ ] **Run agent as non-root** — add USER directive in Dockerfile

## Long-term (production-ready)

- [ ] **WAF on CloudFront** — geo-restrict, bot protection, request size limits
- [ ] **HTTPS-only ALB** — ACM certificate + redirect HTTP→HTTPS
- [ ] **Audit logging** — log all agent invocations to CloudTrail/S3
- [ ] **Cost guardrails** — budget alarm + auto-disable if spend exceeds threshold
- [ ] **Scope down agent permissions** — replace ReadOnlyAccess with specific service permissions

## Bugs Found

- [ ] Cross-account CFN quick-create link references deleted stack (`sandbox-longrun-0426`)
- [ ] WebSocket error: `Unexpected ASGI message 'websocket.send', after sending 'websocket.close'`
- [ ] All tasks stored under user "default" — no user isolation
- [ ] Agent cold start ~90s — first request after idle always returns "(agent not ready)"

## Security Exposures (if public)

- No authentication on API endpoints
- Account ID `256358067059` visible in config.js and responses
- IAM role ARNs exposed in task error messages
- Full billing breakdown and resource inventory accessible without auth
- No rate limiting — Bedrock/Kiro API cost abuse possible
- Agent has ReadOnlyAccess to entire account
