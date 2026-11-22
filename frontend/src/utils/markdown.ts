// Renderizador de Markdown SEGURO para a saída do LLM (texto não confiável):
// - todo HTML é escapado antes de qualquer formatação (não existe HTML cru);
// - imagens nunca são renderizadas (nem remotas nem locais);
// - links viram texto com a URL entre parênteses (sem <a>, sem javascript:).
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

function inline(s: string): string {
  let out = escapeHtml(s)
  out = out.replace(/!\[([^\]]*)\]\([^)]*\)/g, '[imagem removida: $1]')
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)')
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>')
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>')
  return out
}

export function renderMarkdown(src: string): string {
  const lines = src.replace(/\r/g, '').split('\n')
  const html: string[] = []
  let list: 'ul' | 'ol' | null = null
  let code = false
  const close = () => {
    if (list) html.push(`</${list}>`)
    list = null
  }
  for (const raw of lines) {
    if (raw.trim().startsWith('```')) {
      close()
      html.push(code ? '</code></pre>' : '<pre><code>')
      code = !code
      continue
    }
    if (code) {
      html.push(escapeHtml(raw) + '\n')
      continue
    }
    const line = raw.trimEnd()
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    const ul = line.match(/^\s*[-*•]\s+(.*)$/)
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (h) {
      close()
      html.push(`<h4>${inline(h[2])}</h4>`)
    } else if (ul) {
      if (list !== 'ul') { close(); html.push('<ul>'); list = 'ul' }
      html.push(`<li>${inline(ul[1])}</li>`)
    } else if (ol) {
      if (list !== 'ol') { close(); html.push('<ol>'); list = 'ol' }
      html.push(`<li>${inline(ol[1])}</li>`)
    } else if (!line.trim()) {
      close()
    } else {
      close()
      html.push(`<p>${inline(line)}</p>`)
    }
  }
  close()
  if (code) html.push('</code></pre>')
  return html.join('')
}
