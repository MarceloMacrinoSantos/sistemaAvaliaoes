import { reactive } from 'vue'

// Em produção o frontend é servido pelo próprio backend (mesma origem).
// Se hospedar o frontend separado, defina VITE_API_URL no build.
const BASE = import.meta.env.VITE_API_URL || ''

function lerSessao() {
  try { return JSON.parse(localStorage.getItem('sessao') || 'null') } catch { return null }
}

export const sessao = reactive({ token: null, usuario: null, ...(lerSessao() || {}) })

export function salvarSessao(token, usuario) {
  sessao.token = token
  sessao.usuario = usuario
  try { localStorage.setItem('sessao', JSON.stringify({ token, usuario })) } catch {}
}

export function sair() {
  sessao.token = null
  sessao.usuario = null
  try { localStorage.removeItem('sessao') } catch {}
}

export async function api(caminho, { method = 'GET', body, bruto = false } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (sessao.token) headers.Authorization = `Bearer ${sessao.token}`
  let resp
  try {
    resp = await fetch(BASE + caminho, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  } catch {
    const e = new Error('Sem conexão com o servidor. Verifique sua internet.')
    e.offline = true
    throw e
  }
  if (resp.status === 401 && !caminho.includes('/auth/login')) {
    sair()
    window.location.href = '/login'
    throw new Error('Sessão expirada')
  }
  if (bruto) return resp
  const dados = resp.headers.get('content-type')?.includes('json') ? await resp.json() : null
  if (!resp.ok) {
    const e = new Error(dados?.detail || `Erro ${resp.status}`)
    e.status = resp.status
    throw e
  }
  return dados
}

// envio de arquivo (multipart). campos: { arquivo: File } ou { texto: '...' }
export async function enviarArquivo(caminho, campos) {
  const fd = new FormData()
  for (const [k, v] of Object.entries(campos)) if (v != null && v !== '') fd.append(k, v)
  let resp
  try {
    resp = await fetch(BASE + caminho, { method: 'POST', body: fd, headers: sessao.token ? { Authorization: `Bearer ${sessao.token}` } : {} })
  } catch {
    throw new Error('Sem conexão com o servidor.')
  }
  const dados = resp.headers.get('content-type')?.includes('json') ? await resp.json() : null
  if (!resp.ok) throw new Error(dados?.detail || `Erro ${resp.status}`)
  return dados
}

export async function baixar(caminho, nome) {
  const resp = await api(caminho, { bruto: true })
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: nome })
  a.click()
  URL.revokeObjectURL(url)
}

// ---------- utilidades de data ----------
export function fmtData(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

// ISO (UTC) -> valor para <input type="datetime-local"> no fuso do navegador
export function paraInputLocal(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

export function deInputLocal(valor) {
  return valor ? new Date(valor).toISOString() : null
}

export const ROTULO_SITUACAO = {
  certa: 'Correta', errada: 'Incorreta', parcial: 'Parcialmente correta', em_branco: 'Em branco', pendente: 'Aguardando correção'
}

export function fmtDuracao(seg) {
  if (seg == null) return '—'
  const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60), s = seg % 60
  if (h) return `${h} h ${String(m).padStart(2, '0')} min`
  return m ? `${m} min ${String(s).padStart(2, '0')} s` : `${s} s`
}
