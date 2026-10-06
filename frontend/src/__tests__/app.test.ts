import { describe, it, expect } from 'vitest'
import { money, pct } from '../lib/format'
import { num, pmLabel } from '../lib/types'

describe('Formatting Utilities', () => {
  it('formats INR money using Indian grouping system', () => {
    expect(money(0, 'INR')).toBe('₹0')
    expect(money(500, 'INR')).toBe('₹500')
    expect(money(1500, 'INR')).toBe('₹1,500')
    expect(money(123456, 'INR')).toBe('₹1,23,456')
    expect(money(10000000, 'INR')).toBe('₹1,00,00,000')
    expect(money(-2500, 'INR')).toBe('-₹2,500')
  })

  it('formats foreign currency amounts', () => {
    expect(money(1234.5, 'USD')).toBe('$1,235')
    expect(money(1000000, 'EUR')).toBe('€1,000,000')
    expect(money(null)).toBe('—')
    expect(money(undefined)).toBe('—')
  })

  it('formats percentages correctly', () => {
    expect(pct(null)).toBe('—')
    expect(pct(undefined)).toBe('—')
    expect(pct(25.4)).toBe('25%')
    expect(pct(25.6)).toBe('26%')
    expect(pct(100)).toBe('100%')
  })

  it('parses numeric values correctly with num()', () => {
    expect(num(100)).toBe(100)
    expect(num('250.75')).toBe(250.75)
    expect(num(null)).toBe(0)
    expect(num(undefined)).toBe(0)
  })

  it('maps payment method labels', () => {
    expect(pmLabel('upi')).toBe('UPI')
    expect(pmLabel('credit_card')).toBe('Credit card')
    expect(pmLabel('debit_card')).toBe('Debit card')
    expect(pmLabel('bank_transfer')).toBe('Bank transfer')
    expect(pmLabel('cash')).toBe('Cash')
    expect(pmLabel('custom_method')).toBe('custom_method')
  })
})
