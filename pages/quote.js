import Head from 'next/head'
import { useEffect, useMemo, useRef, useState } from 'react'
import styles from '@styles/Quote.module.css'
import { formatNumber, koreanWonPhrase } from '@lib/koreanWon'
import {
  genId,
  loadDraft,
  loadQuotes,
  loadSettings,
  nextSeqForDate,
  saveDraft,
  saveQuotes,
  saveSettings,
  serialString,
} from '@lib/quoteStore'

const VAT_RATE = 0.1

// ===== 고정 정보 (공급자 — 수정 불가) =====
const SUPPLIER_FIXED = {
  bizNo: '216-87-04048',
  company: '(주)브라움',
  ceo: '임종현',
  address: '경기도 부천시 오정구 석천로397 부천테크노파크 쌍용3차 101동 406',
  bizType: '제조',
  bizItem: '전자코일 기타 유도자',
}

// ===== 전역 설정 기본값 (로고/담당자/전화 — 수정 가능) =====
const DEFAULT_SETTINGS = {
  logo: '/braumm-logo.svg',
  manager: '임종현',
  companyTel: '010-3321-5197',
}

// ===== 하단 표준 안내문구 (고정) =====
const FIXED_NOTES =
  '*상기 견적가는 수량(MOQ) 및 사양에 따라 다소 변경될 수 있습니다.\n' +
  '기타: 1. 상기 견적은 운송비를 포함한 금액입니다.\n' +
  '2. 상기 견적은 샘플 제작 기준으로 산정되었으며, 양산 시 단가가 변경될 수 있습니다.'

function todayISO() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function makeEmptyItem() {
  return { name: '', spec: '', qty: 1, unit: 'EA', price: 0, remark: '' }
}

function makeNewQuote(settings) {
  return {
    id: genId(),
    date: todayISO(),
    seq: null, // 저장 시 자동 부여
    recipient: '',
    attn: '',
    recipientTel: '',
    recipientFax: '',
    payment: '선급',
    validity: '1개월',
    items: [makeEmptyItem()],
    extraNotes: '',
    manager: settings.manager,
    companyTel: settings.companyTel,
    savedAt: null,
  }
}

function formatSavedAt(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export default function Quote() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [quotes, setQuotes] = useState([]) // 보관된 견적서 목록
  const [quote, setQuote] = useState(null) // 현재 편집 중
  const [loaded, setLoaded] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [showList, setShowList] = useState(false)

  const fileInputRef = useRef(null)
  const logoInputRef = useRef(null)

  // ===== 초기 로드 =====
  useEffect(() => {
    const s = loadSettings(DEFAULT_SETTINGS)
    const list = loadQuotes()
    const draft = loadDraft()
    setSettings(s)
    setQuotes(list)
    setQuote(draft && draft.id ? draft : makeNewQuote(s))
    setLoaded(true)
  }, [])

  // ===== 자동 저장 (설정 / 목록 / 편집중 초안) =====
  useEffect(() => {
    if (loaded) saveSettings(settings)
  }, [settings, loaded])
  useEffect(() => {
    if (loaded) saveQuotes(quotes)
  }, [quotes, loaded])
  useEffect(() => {
    if (loaded && quote) saveDraft(quote)
  }, [quote, loaded])

  // ===== 헬퍼 =====
  const patchQuote = (patch) => {
    setQuote((prev) => ({ ...prev, ...patch }))
    setDirty(true)
  }
  const patchSettings = (patch) => setSettings((prev) => ({ ...prev, ...patch }))

  const updateItem = (index, patch) => {
    setQuote((prev) => ({
      ...prev,
      items: prev.items.map((it, i) => (i === index ? { ...it, ...patch } : it)),
    }))
    setDirty(true)
  }
  const addItem = () => {
    setQuote((prev) => ({ ...prev, items: [...prev.items, makeEmptyItem()] }))
    setDirty(true)
  }
  const removeItem = (index) => {
    setQuote((prev) => {
      const items = prev.items.filter((_, i) => i !== index)
      return { ...prev, items: items.length ? items : [makeEmptyItem()] }
    })
    setDirty(true)
  }

  // ===== 계산 =====
  const rows = useMemo(
    () =>
      (quote?.items || []).map((it) => {
        const qty = Number(it.qty) || 0
        const price = Number(it.price) || 0
        const supply = qty * price
        const vat = Math.round(supply * VAT_RATE)
        return { ...it, qty, price, supply, vat }
      }),
    [quote]
  )
  const totalQty = rows.reduce((s, r) => s + r.qty, 0)
  const totalSupply = rows.reduce((s, r) => s + r.supply, 0)
  const totalVat = rows.reduce((s, r) => s + r.vat, 0)
  const grandTotal = totalSupply + totalVat

  const displaySeq = quote
    ? quote.seq ?? nextSeqForDate(quotes, quote.date, quote.id)
    : 1
  const serialNo = quote ? serialString(quote.date, displaySeq) : ''

  // ===== 액션 =====
  const handleSave = () => {
    setQuote((prevQuote) => {
      const seq = prevQuote.seq ?? nextSeqForDate(quotes, prevQuote.date, prevQuote.id)
      const saved = { ...prevQuote, seq, savedAt: Date.now() }
      setQuotes((prev) => {
        const idx = prev.findIndex((q) => q.id === saved.id)
        if (idx >= 0) {
          const next = [...prev]
          next[idx] = saved
          return next
        }
        return [...prev, saved]
      })
      return saved
    })
    setDirty(false)
  }

  const handleNew = () => {
    if (dirty && !window.confirm('저장하지 않은 변경사항이 있습니다. 새 견적서를 시작할까요?')) return
    setQuote(makeNewQuote(settings))
    setDirty(false)
    setShowList(false)
  }

  const handleOpen = (id) => {
    const found = quotes.find((q) => q.id === id)
    if (!found) return
    if (dirty && !window.confirm('저장하지 않은 변경사항이 있습니다. 다른 견적서를 열까요?')) return
    setQuote({ ...found })
    setDirty(false)
    setShowList(false)
  }

  const handleDelete = (id) => {
    if (!window.confirm('이 견적서를 목록에서 삭제할까요?')) return
    setQuotes((prev) => prev.filter((q) => q.id !== id))
  }

  const handleDuplicate = (id) => {
    const found = quotes.find((q) => q.id === id)
    if (!found) return
    const copy = {
      ...found,
      id: genId(),
      date: todayISO(),
      seq: null,
      savedAt: null,
    }
    setQuote(copy)
    setDirty(true)
    setShowList(false)
  }

  const handlePrint = () => window.print()

  // 로고 업로드
  const handleLogoClick = () => logoInputRef.current?.click()
  const handleLogoFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => patchSettings({ logo: ev.target.result })
    reader.readAsDataURL(file)
    e.target.value = ''
  }
  const handleLogoRemove = () => patchSettings({ logo: '' })

  // 전체 백업 / 복원 (서버 이전용)
  const handleBackup = () => {
    const data = { settings, quotes, exportedAt: new Date().toISOString() }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `braumm_견적서백업_${todayISO()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }
  const handleRestoreClick = () => fileInputRef.current?.click()
  const handleRestoreFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result)
        if (Array.isArray(data.quotes)) setQuotes(data.quotes)
        if (data.settings) setSettings((prev) => ({ ...prev, ...data.settings }))
        window.alert('백업을 불러왔습니다.')
      } catch (err) {
        window.alert('불러오기에 실패했습니다. 올바른 백업 파일이 아닙니다.')
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  if (!loaded || !quote) {
    return (
      <div className={styles.page}>
        <Head>
          <title>견적서 만들기</title>
        </Head>
        <p style={{ padding: 40 }}>불러오는 중…</p>
      </div>
    )
  }

  const sortedQuotes = [...quotes].sort((a, b) => (b.savedAt || 0) - (a.savedAt || 0))

  return (
    <div className={styles.page}>
      <Head>
        <title>{`견적서 만들기 · ${SUPPLIER_FIXED.company}`}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className={styles.topbar}>
        <h1>📄 견적서 만들기</h1>
        <div className={styles.topActions}>
          <button className={styles.btn} onClick={() => setShowList(true)}>
            📋 견적서 목록 ({quotes.length})
          </button>
          <button className={`${styles.btn} ${styles.btnPrimary}`} onClick={handleSave}>
            💾 저장{dirty ? ' *' : ''}
          </button>
          <button className={styles.btn} onClick={handleNew}>🆕 새 견적서</button>
          <button className={`${styles.btn} ${styles.btnPrimary}`} onClick={handlePrint}>🖨 인쇄 / PDF</button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json"
            onChange={handleRestoreFile}
            style={{ display: 'none' }}
          />
        </div>
      </div>

      <div className={styles.layout}>
        {/* ===== 입력 폼 ===== */}
        <div className={styles.form}>
          <div className={styles.statusBar}>
            <span>일련번호 <strong>{serialNo}</strong></span>
            <span className={dirty ? styles.dirty : styles.saved}>
              {dirty ? '● 저장 안 됨' : quote.savedAt ? `저장됨 · ${formatSavedAt(quote.savedAt)}` : '새 견적서'}
            </span>
          </div>

          <div className={styles.section}>
            <h2>견적 정보</h2>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>견적일자</label>
                <input type="date" value={quote.date} onChange={(e) => patchQuote({ date: e.target.value, seq: null })} />
              </div>
              <div className={styles.field}>
                <label>일련번호 (자동)</label>
                <input value={serialNo} disabled />
              </div>
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>결제조건</label>
                <input value={quote.payment} onChange={(e) => patchQuote({ payment: e.target.value })} />
              </div>
              <div className={styles.field}>
                <label>유효기간</label>
                <input value={quote.validity} onChange={(e) => patchQuote({ validity: e.target.value })} />
              </div>
            </div>
            <p className={styles.hint}>순번은 같은 날짜에 만든 견적서 수에 따라 자동으로 매겨집니다.</p>
          </div>

          <div className={styles.section}>
            <h2>수신처</h2>
            <div className={styles.field}>
              <label>수신 (회사명)</label>
              <input value={quote.recipient} onChange={(e) => patchQuote({ recipient: e.target.value })} placeholder="예: (주)한국전력" />
            </div>
            <div className={styles.field}>
              <label>참조 (담당자)</label>
              <input value={quote.attn} onChange={(e) => patchQuote({ attn: e.target.value })} placeholder="예: 홍길동 과장님" />
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>수신 TEL</label>
                <input value={quote.recipientTel} onChange={(e) => patchQuote({ recipientTel: e.target.value })} />
              </div>
              <div className={styles.field}>
                <label>수신 FAX</label>
                <input value={quote.recipientFax} onChange={(e) => patchQuote({ recipientFax: e.target.value })} />
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <h2>품목 ({rows.length})</h2>
            {quote.items.map((it, i) => {
              const r = rows[i]
              return (
                <div className={styles.itemCard} key={i}>
                  <div className={styles.itemCardHead}>
                    <span>품목 {i + 1}</span>
                    <button className={styles.removeBtn} onClick={() => removeItem(i)}>삭제</button>
                  </div>
                  <div className={styles.field}>
                    <label>품목명</label>
                    <input value={it.name} onChange={(e) => updateItem(i, { name: e.target.value })} placeholder="예: Shunt Reactor" />
                  </div>
                  <div className={styles.field}>
                    <label>규격</label>
                    <textarea rows={2} value={it.spec} onChange={(e) => updateItem(i, { spec: e.target.value })} placeholder="예: 3상, AC380V_AC220V-5.5A(허용전류 10A)_92.06mH" />
                  </div>
                  <div className={styles.row2}>
                    <div className={styles.field}>
                      <label>수량</label>
                      <input type="number" min="0" value={it.qty} onChange={(e) => updateItem(i, { qty: e.target.value })} />
                    </div>
                    <div className={styles.field}>
                      <label>단위</label>
                      <input value={it.unit} onChange={(e) => updateItem(i, { unit: e.target.value })} placeholder="EA" />
                    </div>
                  </div>
                  <div className={styles.field}>
                    <label>단가 (원)</label>
                    <input type="number" min="0" value={it.price} onChange={(e) => updateItem(i, { price: e.target.value })} />
                  </div>
                  <div className={styles.field}>
                    <label>적요 (비고)</label>
                    <input value={it.remark} onChange={(e) => updateItem(i, { remark: e.target.value })} placeholder="예: 13% 직렬리액터 5.5A 후단에 사용" />
                  </div>
                  <div className={styles.itemCalc}>
                    <span>공급가액 <strong>{formatNumber(r.supply)}</strong></span>
                    <span>부가세 <strong>{formatNumber(r.vat)}</strong></span>
                  </div>
                </div>
              )
            })}
            <button className={styles.addBtn} onClick={addItem}>+ 품목 추가</button>
          </div>

          <div className={styles.section}>
            <h2>기타 추가내용</h2>
            <div className={styles.field}>
              <textarea rows={3} value={quote.extraNotes} onChange={(e) => patchQuote({ extraNotes: e.target.value })} placeholder="이 견적서에만 넣을 추가 문구를 입력하세요. (표준 안내문구 아래에 표시됩니다)" />
            </div>
            <p className={styles.hint}>표준 안내문구는 자동으로 고정 표시됩니다.</p>
          </div>

          <div className={styles.section}>
            <h2>내 회사 정보</h2>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>담당자 이름</label>
                <input
                  value={quote.manager}
                  onChange={(e) => { patchQuote({ manager: e.target.value }); patchSettings({ manager: e.target.value }) }}
                />
              </div>
              <div className={styles.field}>
                <label>회사 전화번호</label>
                <input
                  value={quote.companyTel}
                  onChange={(e) => { patchQuote({ companyTel: e.target.value }); patchSettings({ companyTel: e.target.value }) }}
                />
              </div>
            </div>
            <div className={styles.fixedBox}>
              <div>{SUPPLIER_FIXED.company} · 대표 {SUPPLIER_FIXED.ceo}</div>
              <div>사업자등록번호 {SUPPLIER_FIXED.bizNo}</div>
              <div>{SUPPLIER_FIXED.address}</div>
              <div>업태/종목: {SUPPLIER_FIXED.bizType} / {SUPPLIER_FIXED.bizItem}</div>
              <span className={styles.fixedTag}>고정 (수정 불가)</span>
            </div>
          </div>

          <div className={styles.section}>
            <h2>로고</h2>
            <div className={styles.logoRow}>
              <div className={styles.logoPreview}>
                {settings.logo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={settings.logo} alt="로고 미리보기" />
                ) : (
                  <span className={styles.logoEmpty}>로고 없음</span>
                )}
              </div>
              <div className={styles.logoBtns}>
                <button className={styles.btnSmall} onClick={handleLogoClick}>이미지 업로드</button>
                {settings.logo ? (
                  <button className={`${styles.btnSmall} ${styles.btnSmallGhost}`} onClick={handleLogoRemove}>제거</button>
                ) : null}
                <input ref={logoInputRef} type="file" accept="image/*" onChange={handleLogoFile} style={{ display: 'none' }} />
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <h2>데이터 백업</h2>
            <div className={styles.row2}>
              <button className={styles.btnSmall} onClick={handleBackup}>전체 백업 저장</button>
              <button className={`${styles.btnSmall} ${styles.btnSmallGhost}`} onClick={handleRestoreClick}>백업 불러오기</button>
            </div>
            <p className={styles.hint}>모든 견적서를 파일 하나로 백업합니다. 나중에 서버로 옮길 때 이 파일을 사용하세요.</p>
          </div>
        </div>

        {/* ===== 미리보기 (인쇄되는 견적서) ===== */}
        <div className={styles.previewWrap}>
          <div className={styles.sheet}>
            {settings.logo ? (
              <div className={styles.sheetLogo}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={settings.logo} alt="회사 로고" />
              </div>
            ) : null}
            <div className={styles.docTitle}>견 적 서</div>
            <div className={styles.serial}>일련번호 {serialNo} [ 1 / 1 ]</div>

            <div className={styles.headGrid}>
              <table className={styles.metaTable}>
                <tbody>
                  <tr><th>수 신</th><td>{quote.recipient || ' '}</td></tr>
                  <tr><th>참 조</th><td>{quote.attn || ' '}</td></tr>
                  <tr><th>TEL / FAX</th><td>{[quote.recipientTel, quote.recipientFax].filter(Boolean).join(' / ') || ' '}</td></tr>
                  <tr><th>결제조건</th><td>{quote.payment}</td></tr>
                  <tr><th>유효기간</th><td>{quote.validity}</td></tr>
                </tbody>
              </table>

              <table className={`${styles.metaTable} ${styles.supplierTable}`}>
                <tbody>
                  <tr><th>사업자등록번호</th><td>{SUPPLIER_FIXED.bizNo}</td></tr>
                  <tr>
                    <th>회사명 / 대표</th>
                    <td>{SUPPLIER_FIXED.company} / {SUPPLIER_FIXED.ceo}<span className={styles.stamp}>인</span></td>
                  </tr>
                  <tr><th>주 소</th><td>{SUPPLIER_FIXED.address}</td></tr>
                  <tr><th>업태 / 종목</th><td>{SUPPLIER_FIXED.bizType} / {SUPPLIER_FIXED.bizItem}</td></tr>
                  <tr><th>담당자 (TEL)</th><td>{quote.manager} ({quote.companyTel})</td></tr>
                </tbody>
              </table>
            </div>

            <p className={styles.greeting}>
              1. 귀사의 일익 번창하심을 기원합니다.<br />
              2. 하기와 같이 견적드리오니 검토하기 바랍니다.
            </p>

            <div className={styles.amountBox}>
              <span className={styles.krw}>금 액 : {koreanWonPhrase(grandTotal)}</span>
              <span>
                <span className={styles.num}>(￦ {formatNumber(grandTotal)} 원)</span>{' '}
                <span className={styles.vat}>/ VAT포함</span>
              </span>
            </div>

            <table className={styles.itemsTable}>
              <thead>
                <tr>
                  <th style={{ width: '32px' }}>No</th>
                  <th>품목명 [규격]</th>
                  <th style={{ width: '56px' }}>수량</th>
                  <th style={{ width: '78px' }}>단가</th>
                  <th style={{ width: '82px' }}>공급가액</th>
                  <th style={{ width: '72px' }}>부가세</th>
                  <th style={{ width: '110px' }}>적요</th>
                </tr>
              </thead>
              <tbody>
                {rows.filter((r) => r.name || r.spec || r.supply).length === 0 && (
                  <tr><td className={styles.emptyItems} colSpan={7}>왼쪽에서 품목을 입력하세요.</td></tr>
                )}
                {rows.filter((r) => r.name || r.spec || r.supply).map((r, i) => (
                  <tr key={i}>
                    <td style={{ textAlign: 'center' }}>{i + 1}</td>
                    <td>
                      <span className={styles.itemName}>{r.name}</span>
                      {r.spec ? <div className={styles.itemSpec}>[{r.spec}]</div> : null}
                    </td>
                    <td style={{ textAlign: 'center' }}>{formatNumber(r.qty)} {r.unit}</td>
                    <td style={{ textAlign: 'right' }}>{formatNumber(r.price)}</td>
                    <td style={{ textAlign: 'right' }}>{formatNumber(r.supply)}</td>
                    <td style={{ textAlign: 'right' }}>{formatNumber(r.vat)}</td>
                    <td>{r.remark}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className={styles.totalsRow}>
                  <td style={{ textAlign: 'center' }} colSpan={2}>합 계</td>
                  <td style={{ textAlign: 'center' }}>{formatNumber(totalQty)}</td>
                  <td>&nbsp;</td>
                  <td style={{ textAlign: 'right' }}>{formatNumber(totalSupply)}</td>
                  <td style={{ textAlign: 'right' }}>{formatNumber(totalVat)}</td>
                  <td style={{ textAlign: 'right' }}>{formatNumber(grandTotal)}</td>
                </tr>
              </tfoot>
            </table>

            <div className={styles.footNotes}>{FIXED_NOTES}</div>
            {quote.extraNotes ? <div className={styles.footNotes}>{quote.extraNotes}</div> : null}
          </div>
        </div>
      </div>

      {/* ===== 견적서 목록 모달 ===== */}
      {showList && (
        <div className={styles.modalOverlay} onClick={() => setShowList(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2>📋 견적서 목록 ({quotes.length})</h2>
              <button className={styles.btn} onClick={() => setShowList(false)}>닫기</button>
            </div>
            {sortedQuotes.length === 0 ? (
              <p className={styles.emptyList}>저장된 견적서가 없습니다. 견적서를 작성하고 [💾 저장]을 누르세요.</p>
            ) : (
              <table className={styles.listTable}>
                <thead>
                  <tr>
                    <th>일련번호</th>
                    <th>수신처</th>
                    <th>합계금액</th>
                    <th>저장일시</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {sortedQuotes.map((q) => {
                    const total = (q.items || []).reduce((s, it) => {
                      const supply = (Number(it.qty) || 0) * (Number(it.price) || 0)
                      return s + supply + Math.round(supply * VAT_RATE)
                    }, 0)
                    return (
                      <tr key={q.id} className={q.id === quote.id ? styles.activeRow : ''}>
                        <td>{serialString(q.date, q.seq)}</td>
                        <td>{q.recipient || '(수신처 없음)'}</td>
                        <td style={{ textAlign: 'right' }}>￦ {formatNumber(total)}</td>
                        <td>{formatSavedAt(q.savedAt)}</td>
                        <td className={styles.listActions}>
                          <button onClick={() => handleOpen(q.id)}>열기</button>
                          <button onClick={() => handleDuplicate(q.id)}>복제</button>
                          <button className={styles.listDelete} onClick={() => handleDelete(q.id)}>삭제</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
