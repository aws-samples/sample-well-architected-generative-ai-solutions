import { marked } from 'marked';

marked.setOptions({ breaks: true, gfm: true });

/**
 * Generate a human-readable HTML summary from structured JSON data.
 */
export function generateJSONSummary(data) {
  try {
    if (data.service_statuses) {
      const services = Object.keys(data.service_statuses);
      const enabled = services.filter((s) => data.service_statuses[s].enabled).length;
      return `<h3>🛡️ Security Services Status</h3>
        <p><strong>Enabled:</strong> ${enabled}/${services.length}</p>
        <ul>${services
          .map((s) => {
            const st = data.service_statuses[s];
            return `<li>${st.enabled ? '✅' : '❌'} <strong>${s}:</strong> ${st.status}</li>`;
          })
          .join('')}</ul>
        ${data.recommendations ? `<p><strong>🔧 Recommendations:</strong></p><ul>${data.recommendations.map((r) => `<li>${r}</li>`).join('')}</ul>` : ''}`;
    }
    if (data.findings) {
      const sev = {};
      data.findings.forEach((f) => (sev[f.severity] = (sev[f.severity] || 0) + 1));
      return `<h3>🔍 Security Findings</h3>
        <p><strong>Total:</strong> ${data.findings.length}</p>
        <ul>${Object.entries(sev)
          .map(([s, c]) => `<li>${s === 'HIGH' ? '🔴' : s === 'MEDIUM' ? '🟡' : '🟢'} ${s}: ${c}</li>`)
          .join('')}</ul>
        <p><strong>Top Findings:</strong></p>
        <ul>${data.findings.slice(0, 3).map((f) => `<li><strong>${f.title}:</strong> ${f.description}</li>`).join('')}</ul>`;
    }
    if (data.compliance_by_service) {
      const c = data.compliant_resources || 0;
      const nc = data.non_compliant_resources || 0;
      const t = c + nc;
      return `<h3>🔐 Storage Encryption Status</h3>
        <p><strong>Compliance:</strong> ${t > 0 ? Math.round((c / t) * 100) : 0}% (${c}/${t})</p>
        <ul>${Object.entries(data.compliance_by_service)
          .map(([svc, st]) => {
            const rate = st.total > 0 ? Math.round((st.encrypted / st.total) * 100) : 0;
            return `<li>${st.unencrypted === 0 ? '✅' : '⚠️'} <strong>${svc.toUpperCase()}:</strong> ${rate}% (${st.encrypted}/${st.total})</li>`;
          })
          .join('')}</ul>
        ${data.recommendations ? `<p><strong>🔧 Recommendations:</strong></p><ul>${data.recommendations.map((r) => `<li>${r}</li>`).join('')}</ul>` : ''}`;
    }
    // Generic fallback
    const keys = Object.keys(data).slice(0, 5);
    return `<h3>📋 Analysis Results</h3><ul>${keys.map((k) => `<li><strong>${k}:</strong> ${JSON.stringify(data[k]).substring(0, 100)}</li>`).join('')}</ul>`;
  } catch {
    return '<h3>📋 Analysis Results</h3><p>View raw data below for details.</p>';
  }
}

/**
 * Parse message content: render markdown and extract inline JSON blocks
 * into collapsible-friendly structures.
 */
export function parseMessageContent(content) {
  let clean = content.replace(/\\n/g, '\n');
  const jsonSections = [];
  const jsonRe = /```json\n([\s\S]*?)\n```/g;
  let m;

  while ((m = jsonRe.exec(clean)) !== null) {
    try {
      const parsed = JSON.parse(m[1]);
      const placeholder = `__JSON_${jsonSections.length}__`;
      jsonSections.push({ data: parsed, summary: generateJSONSummary(parsed) });
      clean = clean.replace(m[0], placeholder);
    } catch {
      /* leave as code block */
    }
  }

  let html = marked.parse(clean);

  // Restore placeholders with a marker the component can split on
  jsonSections.forEach((_, i) => {
    html = html.replace(`__JSON_${i}__`, `<!--JSON_SECTION_${i}-->`);
  });

  return { html, jsonSections };
}
