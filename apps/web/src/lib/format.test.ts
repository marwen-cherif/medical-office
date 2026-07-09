import { describe, expect, it } from 'vitest';
import { fmtMontant, fmtDevise, DEVISE, isoToFr, isoToFrDateTime, dateToIso, isoToDate } from './format';

describe('format.ts helper functions', () => {
  describe('fmtMontant', () => {
    it('formats numbers with French locale structure', () => {
      if (DEVISE.code === 'TND') {
        expect(fmtMontant(1250.5)).toBe('1 250,500');
        expect(fmtMontant(0)).toBe('0,000');
        expect(fmtMontant(null)).toBe('0,000');
        expect(fmtMontant(undefined)).toBe('0,000');
      } else {
        expect(fmtMontant(1250.5)).toBe('1 250,50');
        expect(fmtMontant(0)).toBe('0,00');
        expect(fmtMontant(null)).toBe('0,00');
        expect(fmtMontant(undefined)).toBe('0,00');
      }
    });
  });

  describe('fmtDevise', () => {
    it('appends the currency symbol', () => {
      if (DEVISE.code === 'TND') {
        expect(fmtDevise(1250.5)).toBe('1 250,500 DT');
        expect(fmtDevise(0)).toBe('0,000 DT');
      } else {
        expect(fmtDevise(1250.5)).toBe('1 250,50 €');
        expect(fmtDevise(0)).toBe('0,00 €');
      }
    });
  });

  describe('isoToFr', () => {
    it('converts YYYY-MM-DD to DD/MM/YYYY', () => {
      expect(isoToFr('2026-07-09')).toBe('09/07/2026');
      expect(isoToFr('')).toBe('');
      expect(isoToFr(null)).toBe('');
      expect(isoToFr('invalid-date')).toBe('invalid-date');
    });
  });

  describe('isoToFrDateTime', () => {
    it('converts ISO date time to French format', () => {
      expect(isoToFrDateTime('2026-07-09T20:47:00')).toBe('09/07/2026 20:47');
      expect(isoToFrDateTime('2026-07-09 20:47')).toBe('09/07/2026 20:47');
      expect(isoToFrDateTime('2026-07-09')).toBe('09/07/2026');
    });
  });

  describe('dateToIso', () => {
    it('converts a Date object to YYYY-MM-DD', () => {
      const date = new Date(2026, 6, 9); // Month is 0-indexed (6 = July)
      expect(dateToIso(date)).toBe('2026-07-09');
    });
  });

  describe('isoToDate', () => {
    it('converts YYYY-MM-DD to a Date object in local time zone', () => {
      const date = isoToDate('2026-07-09');
      expect(date).toBeInstanceOf(Date);
      expect(date?.getFullYear()).toBe(2026);
      expect(date?.getMonth()).toBe(6); // July
      expect(date?.getDate()).toBe(9);
    });

    it('returns undefined for invalid format or empty input', () => {
      expect(isoToDate('')).toBeUndefined();
      expect(isoToDate(null)).toBeUndefined();
      expect(isoToDate('invalid')).toBeUndefined();
    });
  });
});
