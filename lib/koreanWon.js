// 숫자를 한글 금액 표기로 변환하는 유틸리티
// 예: 3718000 -> "삼백칠십일만팔천"

const DIGITS = ['', '일', '이', '삼', '사', '오', '육', '칠', '팔', '구']
const SMALL_UNITS = ['', '십', '백', '천']
const BIG_UNITS = ['', '만', '억', '조', '경']

function fourDigitsToKorean(n) {
  let result = ''
  const s = String(n).padStart(4, '0')
  for (let i = 0; i < 4; i += 1) {
    const d = Number(s[i])
    if (d !== 0) {
      result += DIGITS[d] + SMALL_UNITS[3 - i]
    }
  }
  return result
}

// 숫자 -> 한글 (단위 "원 정"은 붙이지 않음)
export function numberToKorean(num) {
  const value = Math.floor(Math.abs(Number(num) || 0))
  if (value === 0) return '영'

  const groups = []
  let n = value
  while (n > 0) {
    groups.push(n % 10000)
    n = Math.floor(n / 10000)
  }

  let result = ''
  for (let i = groups.length - 1; i >= 0; i -= 1) {
    if (groups[i] !== 0) {
      result += fourDigitsToKorean(groups[i]) + BIG_UNITS[i]
    }
  }
  return result
}

// 견적서 금액 표기: "삼백칠십일만팔천 원 정"
export function koreanWonPhrase(num) {
  return `${numberToKorean(num)} 원 정`
}

// 천단위 콤마 포맷
export function formatNumber(num) {
  const value = Number(num) || 0
  return value.toLocaleString('en-US')
}
