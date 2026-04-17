import React, { useState, useMemo } from 'react';
import Box from '@cloudscape-design/components/box';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import { marked } from 'marked';

marked.setOptions({ breaks: true, gfm: true });

/**
 * Render a single chat message (user or assistant) with markdown + collapsible JSON sections.
 */
export default function ChatMessage({ role, content, structuredData, humanSummary }) {
  const isUser = role === 'user';

  const renderedHTML = useMemo(() => {
    let clean = (content || '').replace(/\\n/g, '\n');

    // Extract JSON code blocks and replace with placeholders
    const jsonBlocks = [];
    clean = clean.replace(/```json\n([\s\S]*?)\n```/g, (_match, jsonStr) => {
      try {
        const data = JSON.parse(jsonStr);
        const idx = jsonBlocks.length;
        jsonBlocks.push(data);
        return `__JSON_BLOCK_${idx}__`;
      } catch {
        return _match; // leave as-is if invalid JSON
      }
    });

    let html;
    try {
      html = marked.parse(clean);
    } catch {
      html = clean.replace(/\n/g, '<br>');
    }

    // Restore JSON block placeholders as formatted pre blocks (collapsible handled below)
    jsonBlocks.forEach((data, i) => {
      html = html.replace(
        `__JSON_BLOCK_${i}__`,
        `<div class="json-placeholder" data-index="${i}"></div>`
      );
    });

    return { html, jsonBlocks };
  }, [content]);

  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        alignItems: 'flex-start',
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 18,
          flexShrink: 0,
          background: isUser
            ? 'linear-gradient(135deg, #FF9900 0%, #FF6600 100%)'
            : 'linear-gradient(135deg, #232F3E 0%, #4A5568 100%)',
          color: '#fff',
        }}
      >
        {isUser ? '👤' : '🛡️'}
      </div>

      {/* Bubble */}
      <div
        style={{
          flex: 1,
          maxWidth: '80%',
          background: isUser ? 'linear-gradient(135deg,#FF9900,#FF6600)' : '#fff',
          color: isUser ? '#fff' : '#16191f',
          borderRadius: 12,
          padding: '12px 16px',
          border: isUser ? 'none' : '1px solid #eaeded',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          lineHeight: 1.6,
        }}
      >
        {/* Markdown content */}
        <div
          className="chat-markdown"
          dangerouslySetInnerHTML={{ __html: renderedHTML.html }}
        />

        {/* Inline JSON blocks from markdown */}
        {renderedHTML.jsonBlocks.map((data, i) => (
          <JSONSection key={`inline-${i}`} title="📊 Analysis Results" data={data} />
        ))}

        {/* Structured data from backend response */}
        {structuredData && (
          <JSONSection
            title="📊 Detailed Results"
            data={structuredData}
            summaryHTML={humanSummary}
          />
        )}
      </div>
    </div>
  );
}

function JSONSection({ title, data, summaryHTML }) {
  const summary = summaryHTML || generateJSONSummary(data);
  return (
    <div style={{ marginTop: 12 }}>
      <ExpandableSection headerText={title} variant="footer">
        <Box margin={{ bottom: 's' }}>
          <div dangerouslySetInnerHTML={{ __html: summary }} />
        </Box>
        <Box variant="code">
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12 }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </Box>
      </ExpandableSection>
    </div>
  );
}

// ----- JSON summary generator (ported from original) -----

function generateJSONSummary(data) {
  try {
    if (data.service_statuses) {
      const services = Object.keys(data.service_statuses);
      const enabled = services.filter((s) => data.service_statuses[s].enabled).length;
      return `
        <h4>🛡️ Security Services Status</h4>
        <p><strong>Services Checked:</strong> ${services.length}</p>
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
      return `
        <h4>🔍 Security Findings</h4>
        <p><strong>Total:</strong> ${data.findings.length}</p>
        <ul>${Object.entries(sev)
          .map(([k, v]) => `<li>${k === 'HIGH' ? '🔴' : k === 'MEDIUM' ? '🟡' : '🟢'} ${k}: ${v}</li>`)
          .join('')}</ul>
        <p><strong>Top Findings:</strong></p>
        <ul>${data.findings
          .slice(0, 3)
          .map((f) => `<li><strong>${f.title}:</strong> ${f.description}</li>`)
          .join('')}</ul>`;
    }

    if (data.compliance_by_service) {
      const compliant = data.compliant_resources || 0;
      const nonCompliant = data.non_compliant_resources || 0;
      const total = compliant + nonCompliant;
      return `
        <h4>🔐 Storage Encryption Status</h4>
        <p><strong>Compliance Rate:</strong> ${total > 0 ? Math.round((compliant / total) * 100) : 0}% (${compliant}/${total})</p>
        <ul>${Object.entries(data.compliance_by_service)
          .map(([svc, s]) => {
            const rate = s.total > 0 ? Math.round((s.encrypted / s.total) * 100) : 0;
            return `<li>${s.unencrypted === 0 ? '✅' : '⚠️'} <strong>${svc.toUpperCase()}:</strong> ${rate}% (${s.encrypted}/${s.total})</li>`;
          })
          .join('')}</ul>
        ${data.recommendations ? `<p><strong>🔧 Recommendations:</strong></p><ul>${data.recommendations.map((r) => `<li>${r}</li>`).join('')}</ul>` : ''}`;
    }

    // Generic
    const keys = Object.keys(data).slice(0, 5);
    return `<h4>📋 Analysis Results</h4><ul>${keys
      .map((k) => `<li><strong>${k}:</strong> ${JSON.stringify(data[k]).substring(0, 100)}</li>`)
      .join('')}</ul>`;
  } catch {
    return '<h4>📋 Analysis Results</h4><p>View raw data below for details.</p>';
  }
}
