import { describe, expect, it } from 'vitest';
import {
  fmtMontant,
  fmtDevise,
  DEVISE,
  isoToFr,
  isoToFrDateTime,
  dateToIso,
  isoToDate,
  parsePhoneNumber,
  formatE164,
  maskDateFr,
  frToIso,
  monthRange,
  humanize,
  docStatut,
  depenseStatut,
  jobStatut,
  modeLabel,
  parseDents,
  formatWaMeUrl,
} from './format';

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

  describe('parsePhoneNumber', () => {
    it('parses Tunisian numbers', () => {
      expect(parsePhoneNumber('55777766')).toEqual({ prefix: '+216', local: '55777766' });
      expect(parsePhoneNumber('+216 55 777 766')).toEqual({ prefix: '+216', local: '55777766' });
      expect(parsePhoneNumber('0021655777766')).toEqual({ prefix: '+216', local: '55777766' });
    });

    it('parses French numbers and strips leading zero', () => {
      expect(parsePhoneNumber('0612345678', '+33')).toEqual({ prefix: '+33', local: '612345678' });
      expect(parsePhoneNumber('+33 6 12 34 56 78')).toEqual({ prefix: '+33', local: '612345678' });
      expect(parsePhoneNumber('+33 06 12 34 56 78')).toEqual({ prefix: '+33', local: '612345678' });
      expect(parsePhoneNumber('0033612345678')).toEqual({ prefix: '+33', local: '612345678' });
      expect(parsePhoneNumber('00330612345678')).toEqual({ prefix: '+33', local: '612345678' });
    });

    it('falls back to default prefix when no prefix is present', () => {
      expect(parsePhoneNumber('55777766', '+216')).toEqual({ prefix: '+216', local: '55777766' });
      expect(parsePhoneNumber('0612345678', '+216')).toEqual({ prefix: '+216', local: '612345678' });
    });
  });

  describe('formatE164', () => {
    it('combines prefix and local number, stripping leading zero', () => {
      expect(formatE164('+216', '55777766')).toBe('+21655777766');
      expect(formatE164('+33', '0612345678')).toBe('+33612345678');
      expect(formatE164('+33', '612345678')).toBe('+33612345678');
    });
  });

  describe('maskDateFr', () => {
    it('masks digits to date format JJ/MM/AAAA', () => {
      expect(maskDateFr('27101990')).toBe('27/10/1990');
      expect(maskDateFr('27')).toBe('27');
      expect(maskDateFr('2710')).toBe('27/10');
      expect(maskDateFr('27101990123')).toBe('27/10/1990');
      expect(maskDateFr('ab27cd10')).toBe('27/10');
    });
  });

  describe('frToIso', () => {
    it('converts FR date to ISO date', () => {
      expect(frToIso('27/10/1990')).toBe('1990-10-27');
      expect(frToIso('31/02/2020')).toBe(''); // invalid date
      expect(frToIso('invalid')).toBe('');
      expect(frToIso(null)).toBe('');
      expect(frToIso(undefined)).toBe('');
    });
  });

  describe('monthRange', () => {
    it('returns ISO dates bounding current month', () => {
      const range = monthRange();
      expect(range.from).toMatch(/^\d{4}-\d{2}-01$/);
      expect(range.to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      
      const fromDate = new Date(range.from);
      const toDate = new Date(range.to);
      expect(fromDate.getDate()).toBe(1);
      expect(toDate.getMonth()).toBe(fromDate.getMonth());
    });
  });

  describe('humanize', () => {
    it('makes logic names human readable', () => {
      expect(humanize('note_honoraires')).toBe('Note honoraires');
      expect(humanize('devis')).toBe('Devis');
      expect(humanize('')).toBe('');
      expect(humanize(null)).toBe('');
    });
  });

  describe('docStatut', () => {
    it('returns label and variant for document status', () => {
      expect(docStatut('brouillon')).toEqual({ label: 'Brouillon', variant: 'outline' });
      expect(docStatut('erreur')).toEqual({ label: 'Erreur génération', variant: 'danger' });
      expect(docStatut('unknown')).toEqual({ label: 'Unknown', variant: 'muted' });
    });
  });

  describe('depenseStatut', () => {
    it('returns label and variant for depense status', () => {
      expect(depenseStatut('en_attente')).toEqual({ label: 'À régler', variant: 'default' });
      expect(depenseStatut('regle')).toEqual({ label: 'Réglé', variant: 'success' });
      expect(depenseStatut('unknown')).toEqual({ label: 'Unknown', variant: 'muted' });
    });
  });

  describe('jobStatut', () => {
    it('returns label and variant for job status', () => {
      expect(jobStatut('en_cours')).toEqual({ label: 'En cours', variant: 'default' });
      expect(jobStatut('erreur')).toEqual({ label: 'Erreur', variant: 'danger' });
    });
  });

  describe('modeLabel', () => {
    it('returns readable label for payment mode', () => {
      expect(modeLabel('especes')).toBe('Espèces');
      expect(modeLabel('cheque')).toBe('Chèque');
      expect(modeLabel('unknown')).toBe('Unknown');
      expect(modeLabel(null)).toBe('—');
    });
  });

  describe('parseDents', () => {
    it('parses teeth list from string', () => {
      expect(parseDents('26, 27')).toEqual(['26', '27']);
      expect(parseDents('11;12 13')).toEqual(['11', '12', '13']);
      expect(parseDents('')).toEqual([]);
      expect(parseDents(null)).toEqual([]);
    });
  });

  describe('formatWaMeUrl', () => {
    it('generates wa.me urls', () => {
      expect(formatWaMeUrl('55777766', '+216', 'hello')).toBe('https://wa.me/21655777766?text=hello');
      expect(formatWaMeUrl('0612345678', '+33', 'hi')).toBe('https://wa.me/33612345678?text=hi');
      expect(formatWaMeUrl('+33612345678', '+33', 'test')).toBe('https://wa.me/33612345678?text=test');
    });
  });
});
