import Head from 'next/head'
import { useEffect, useRef, useState } from 'react'
import styles from '@styles/Quote.module.css'
import { formatNumber, koreanWonPhrase } from '@lib/koreanWon'

const VAT_RATE = 0.1
const STORAGE_KEY = 'braum-quote-v1'

// 기본 공급자 정보 (PDF 견적서 기준 — 한 번 입력해두면 계속 재사용)
const DEFAULT_SUPPLIER = {
  bizNo: '216-87-04048',
  company: '(주)브라움',
  ceo: '임종현',
  address: '경기도 부천시 오정구 석천로397 부천테크노파크 쌍용3차 101동 406',
  bizType: '제조',
  bizItem: '전자코일 기타 유도자',
  manager: '임종현',
  tel: '010-3321-5197',
  fax: '',
}

function todayISO() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function makeEmptyItem() {
  return { name: '', spec: '', qty: 1, unit: 'EA', price: 0, remark: '' }
}

const DEFAULT_STATE = {
  supplier: DEFAULT_SUPPLIER,
  date: todayISO(),
  serialSeq: 1,
  payment: '선급',
  validity: '1개월',
  recipient: '',
  attn: '',
  recipientTel: '',
  recipientFax: '',
  items: [makeEmptyItem()],
  notes:
    '*상기 견적가는 수량(MOQ) 및 사양에 따라 다소 변경될 수 있습니다.\n' +
    '기타: 1. 상기 견적은 운송비를 포함한 금액입니다.\n' +
    '2. 상기 견적은 샘플 제작 기준으로 산정되었으며, 양산 시 단가가 변경될 수 있습니다.',
}

export default function Quote() {
  const [state, setState] = useState(DEFAULT_STATE)
  const [loaded, setLoaded] = useState(false)
  const fileInputRef = useRef(null)

  // 최초 로드 시 localStorage에서 복원
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        setState((prev) => ({ ...prev, ...parsed }))
      }
    } catch (e) {
      // 무시하고 기본값 사용
    }
    setLoaded(true)
  }, [])

  // 변경될 때마다 자동 저장
  useEffect(() => {
    if (!loaded) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch (e) {
      // 저장 실패 무시
    }
  }, [state, loaded])

  const update = (patch) => setState((prev) => ({ ...prev, ...patch }))
  const updateSupplier = (patch) =>
    setState((prev) => ({ ...prev, supplier: { ...prev.supplier, ...patch } }))

  const updateItem = (index, patch) =>
    setState((prev) => {
      const items = prev.items.map((it, i) => (i === index ? { ...it, ...patch } : it))
      return { ...prev, items }
    })

  const addItem = () =>
    setState((prev) => ({ ...prev, items: [...prev.items, makeEmptyItem()] }))

  const removeItem = (index) =>
    setState((prev) => {
      const items = prev.items.filter((_, i) => i !== index)
      return { ...prev, items: items.length ? items : [makeEmptyItem()] }
    })

  // ===== 계산 =====
  const rows = state.items.map((it) => {
    const qty = Number(it.qty) || 0
    const price = Number(it.price) || 0
    const supply = qty * price
    const vat = Math.round(supply * VAT_RATE)
    return { ...it, qty, price, supply, vat }
  })
  const totalQty = rows.reduce((s, r) => s + r.qty, 0)
  const totalSupply = rows.reduce((s, r) => s + r.supply, 0)
  const totalVat = rows.reduce((s, r) => s + r.vat, 0)
  const grandTotal = totalSupply + totalVat

  const serialNo = `${state.date.replace(/-/g, '/')}-${state.serialSeq}`

  // ===== 액션 =====
  const handlePrint = () => window.print()

  const handleReset = () => {
    if (typeof window !== 'undefined' && window.confirm('입력한 내용을 모두 지우고 새 견적서를 시작할까요? (공급자 정보는 유지됩니다)')) {
      setState((prev) => ({
        ...DEFAULT_STATE,
        supplier: prev.supplier,
        date: todayISO(),
        serialSeq: (Number(prev.serialSeq) || 0) + 1,
      }))
    }
  }

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `견적서_${serialNo.replace(/\//g, '')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImportClick = () => fileInputRef.current?.click()

  const handleImportFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target.result)
        setState((prev) => ({ ...prev, ...parsed }))
      } catch (err) {
        window.alert('불러오기에 실패했습니다. 올바른 견적서 파일이 아닙니다.')
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  return (
    <div className={styles.page}>
      <Head>
        <title>견적서 만들기 · {state.supplier.company}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className={styles.topbar}>
        <h1>📄 견적서 만들기</h1>
        <div className={styles.topActions}>
          <button className={styles.btn} onClick={handleImportClick}>불러오기</button>
          <button className={styles.btn} onClick={handleExport}>파일로 저장</button>
          <button className={`${styles.btn} ${styles.btnDanger}`} onClick={handleReset}>새 견적서</button>
          <button className={`${styles.btn} ${styles.btnPrimary}`} onClick={handlePrint}>인쇄 / PDF 저장</button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json"
            onChange={handleImportFile}
            style={{ display: 'none' }}
          />
        </div>
      </div>

      <div className={styles.layout}>
        {/* ===== 입력 폼 ===== */}
        <div className={styles.form}>
          <div className={styles.section}>
            <h2>견적 정보</h2>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>견적일자</label>
                <input
                  type="date"
                  value={state.date}
                  onChange={(e) => update({ date: e.target.value })}
                />
              </div>
              <div className={styles.field}>
                <label>일련번호(순번)</label>
                <input
                  type="number"
                  min="1"
                  value={state.serialSeq}
                  onChange={(e) => update({ serialSeq: e.target.value })}
                />
              </div>
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>결제조건</label>
                <input
                  value={state.payment}
                  onChange={(e) => update({ payment: e.target.value })}
                />
              </div>
              <div className={styles.field}>
                <label>유효기간</label>
                <input
                  value={state.validity}
                  onChange={(e) => update({ validity: e.target.value })}
                />
              </div>
            </div>
            <p className={styles.hint}>일련번호: {serialNo}</p>
          </div>

          <div className={styles.section}>
            <h2>수신처</h2>
            <div className={styles.field}>
              <label>수신 (회사명)</label>
              <input
                value={state.recipient}
                onChange={(e) => update({ recipient: e.target.value })}
                placeholder="예: (주)한국전력"
              />
            </div>
            <div className={styles.field}>
              <label>참조 (담당자)</label>
              <input
                value={state.attn}
                onChange={(e) => update({ attn: e.target.value })}
                placeholder="예: 홍길동 과장님"
              />
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>수신 TEL</label>
                <input
                  value={state.recipientTel}
                  onChange={(e) => update({ recipientTel: e.target.value })}
                />
              </div>
              <div className={styles.field}>
                <label>수신 FAX</label>
                <input
                  value={state.recipientFax}
                  onChange={(e) => update({ recipientFax: e.target.value })}
                />
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <h2>품목 ({rows.length})</h2>
            {state.items.map((it, i) => {
              const r = rows[i]
              return (
                <div className={styles.itemCard} key={i}>
                  <div className={styles.itemCardHead}>
                    <span>품목 {i + 1}</span>
                    <button className={styles.removeBtn} onClick={() => removeItem(i)}>삭제</button>
                  </div>
                  <div className={styles.field}>
                    <label>품목명</label>
                    <input
                      value={it.name}
                      onChange={(e) => updateItem(i, { name: e.target.value })}
                      placeholder="예: Shunt Reactor"
                    />
                  </div>
                  <div className={styles.field}>
                    <label>규격</label>
                    <textarea
                      rows={2}
                      value={it.spec}
                      onChange={(e) => updateItem(i, { spec: e.target.value })}
                      placeholder="예: 3상, AC380V_AC220V-5.5A(허용전류 10A)_92.06mH"
                    />
                  </div>
                  <div className={styles.row2}>
                    <div className={styles.field}>
                      <label>수량</label>
                      <input
                        type="number"
                        min="0"
                        value={it.qty}
                        onChange={(e) => updateItem(i, { qty: e.target.value })}
                      />
                    </div>
                    <div className={styles.field}>
                      <label>단위</label>
                      <input
                        value={it.unit}
                        onChange={(e) => updateItem(i, { unit: e.target.value })}
                        placeholder="EA"
                      />
                    </div>
                  </div>
                  <div className={styles.field}>
                    <label>단가 (원)</label>
                    <input
                      type="number"
                      min="0"
                      value={it.price}
                      onChange={(e) => updateItem(i, { price: e.target.value })}
                    />
                  </div>
                  <div className={styles.field}>
                    <label>적요 (비고)</label>
                    <input
                      value={it.remark}
                      onChange={(e) => updateItem(i, { remark: e.target.value })}
                      placeholder="예: 13% 직렬리액터 5.5A 후단에 사용"
                    />
                  </div>
                  <div className={styles.itemCalc}>
                    <span>공급가액 <strong>{formatNumber(r.supply)}</strong></span>
                    <span>VAT <strong>{formatNumber(r.vat)}</strong></span>
                  </div>
                </div>
              )
            })}
            <button className={styles.addBtn} onClick={addItem}>+ 품목 추가</button>
          </div>

          <div className={styles.section}>
            <h2>하단 안내 문구</h2>
            <div className={styles.field}>
              <textarea
                rows={4}
                value={state.notes}
                onChange={(e) => update({ notes: e.target.value })}
              />
            </div>
          </div>

          <div className={styles.section}>
            <h2>공급자 정보 (내 회사)</h2>
            <div className={styles.field}>
              <label>사업자등록번호</label>
              <input value={state.supplier.bizNo} onChange={(e) => updateSupplier({ bizNo: e.target.value })} />
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>회사명</label>
                <input value={state.supplier.company} onChange={(e) => updateSupplier({ company: e.target.value })} />
              </div>
              <div className={styles.field}>
                <label>대표</label>
                <input value={state.supplier.ceo} onChange={(e) => updateSupplier({ ceo: e.target.value })} />
              </div>
            </div>
            <div className={styles.field}>
              <label>주소</label>
              <textarea rows={2} value={state.supplier.address} onChange={(e) => updateSupplier({ address: e.target.value })} />
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>업태</label>
                <input value={state.supplier.bizType} onChange={(e) => updateSupplier({ bizType: e.target.value })} />
              </div>
              <div className={styles.field}>
                <label>종목</label>
                <input value={state.supplier.bizItem} onChange={(e) => updateSupplier({ bizItem: e.target.value })} />
              </div>
            </div>
            <div className={styles.field}>
              <label>담당자</label>
              <input value={state.supplier.manager} onChange={(e) => updateSupplier({ manager: e.target.value })} />
            </div>
            <div className={styles.row2}>
              <div className={styles.field}>
                <label>TEL</label>
                <input value={state.supplier.tel} onChange={(e) => updateSupplier({ tel: e.target.value })} />
              </div>
              <div className={styles.field}>
                <label>FAX</label>
                <input value={state.supplier.fax} onChange={(e) => updateSupplier({ fax: e.target.value })} />
              </div>
            </div>
            <p className={styles.hint}>공급자 정보는 브라우저에 저장되어 다음에도 자동으로 채워집니다.</p>
          </div>
        </div>

        {/* ===== 미리보기 (인쇄되는 견적서) ===== */}
        <div className={styles.previewWrap}>
          <div className={styles.sheet}>
            <div className={styles.docTitle}>견 적 서</div>
            <div className={styles.serial}>일련번호 {serialNo} [ 1 / 1 ]</div>

            <div className={styles.headGrid}>
              {/* 좌: 수신처 & 견적조건 */}
              <table className={styles.metaTable}>
                <tbody>
                  <tr>
                    <th>수 신</th>
                    <td>{state.recipient || ' '}</td>
                  </tr>
                  <tr>
                    <th>참 조</th>
                    <td>{state.attn || ' '}</td>
                  </tr>
                  <tr>
                    <th>TEL / FAX</th>
                    <td>{[state.recipientTel, state.recipientFax].filter(Boolean).join(' / ') || ' '}</td>
                  </tr>
                  <tr>
                    <th>결제조건</th>
                    <td>{state.payment}</td>
                  </tr>
                  <tr>
                    <th>유효기간</th>
                    <td>{state.validity}</td>
                  </tr>
                </tbody>
              </table>

              {/* 우: 공급자 */}
              <table className={`${styles.metaTable} ${styles.supplierTable}`}>
                <tbody>
                  <tr>
                    <th>사업자등록번호</th>
                    <td>{state.supplier.bizNo}</td>
                  </tr>
                  <tr>
                    <th>회사명 / 대표</th>
                    <td>
                      {state.supplier.company} / {state.supplier.ceo}
                      <span className={styles.stamp}>인</span>
                    </td>
                  </tr>
                  <tr>
                    <th>주 소</th>
                    <td>{state.supplier.address}</td>
                  </tr>
                  <tr>
                    <th>업태 / 종목</th>
                    <td>{state.supplier.bizType} / {state.supplier.bizItem}</td>
                  </tr>
                  <tr>
                    <th>담당자 (TEL/FAX)</th>
                    <td>
                      {state.supplier.manager} ({[state.supplier.tel, state.supplier.fax].filter(Boolean).join(' / ')})
                    </td>
                  </tr>
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
                  <tr>
                    <td className={styles.emptyItems} colSpan={7}>
                      왼쪽에서 품목을 입력하세요.
                    </td>
                  </tr>
                )}
                {rows
                  .filter((r) => r.name || r.spec || r.supply)
                  .map((r, i) => (
                    <tr key={i}>
                      <td className="center" style={{ textAlign: 'center' }}>{i + 1}</td>
                      <td>
                        <span className={styles.itemName}>{r.name}</span>
                        {r.spec ? <div className={styles.itemSpec}>[{r.spec}]</div> : null}
                      </td>
                      <td className={styles.center} style={{ textAlign: 'center' }}>
                        {formatNumber(r.qty)} {r.unit}
                      </td>
                      <td className={styles.num} style={{ textAlign: 'right' }}>{formatNumber(r.price)}</td>
                      <td className={styles.num} style={{ textAlign: 'right' }}>{formatNumber(r.supply)}</td>
                      <td className={styles.num} style={{ textAlign: 'right' }}>{formatNumber(r.vat)}</td>
                      <td>{r.remark}</td>
                    </tr>
                  ))}
              </tbody>
              <tfoot>
                <tr className={styles.totalsRow}>
                  <td className={styles.label} style={{ textAlign: 'center' }} colSpan={2}>합 계</td>
                  <td style={{ textAlign: 'center' }}>{formatNumber(totalQty)}</td>
                  <td>&nbsp;</td>
                  <td style={{ textAlign: 'right' }}>{formatNumber(totalSupply)}</td>
                  <td style={{ textAlign: 'right' }}>{formatNumber(totalVat)}</td>
                  <td style={{ textAlign: 'right' }}>{formatNumber(grandTotal)}</td>
                </tr>
              </tfoot>
            </table>

            <div className={styles.footNotes}>{state.notes}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
