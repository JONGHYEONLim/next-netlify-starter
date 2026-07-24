// 견적서 보관소 (브라우저 localStorage 기반)
// 나중에 서버로 옮길 수 있도록 순수 데이터(JSON)만 다룬다.

export const QUOTES_KEY = 'braum-quotes-v2' // 저장된 견적서 목록
export const DRAFT_KEY = 'braum-draft-v2' // 현재 편집 중인 견적서
export const SETTINGS_KEY = 'braum-settings-v2' // 로고/담당자/전화 등 전역 설정

function readJSON(key, fallback) {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch (e) {
    return fallback
  }
}

function writeJSON(key, value) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (e) {
    // 저장 실패(용량 초과 등)는 조용히 무시
  }
}

export const loadQuotes = () => readJSON(QUOTES_KEY, [])
export const saveQuotes = (list) => writeJSON(QUOTES_KEY, list)

export const loadDraft = () => readJSON(DRAFT_KEY, null)
export const saveDraft = (draft) => writeJSON(DRAFT_KEY, draft)

export const loadSettings = (defaults) => ({ ...defaults, ...readJSON(SETTINGS_KEY, {}) })
export const saveSettings = (s) => writeJSON(SETTINGS_KEY, s)

// 간단한 고유 ID
export function genId() {
  const rand = Math.floor(Math.random() * 1e6).toString(36)
  return `q_${Date.now().toString(36)}_${rand}`
}

// 같은 날짜에 저장된 견적서 수 + 1 = 그 날짜의 다음 순번
export function nextSeqForDate(quotes, date, excludeId) {
  return 1 + quotes.filter((q) => q.date === date && q.id !== excludeId).length
}

// 일련번호 문자열: 2026/07/16-1
export function serialString(date, seq) {
  return `${String(date).replace(/-/g, '/')}-${seq}`
}
