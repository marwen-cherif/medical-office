import { describe, expect, it } from 'vitest';
import { cn } from './utils';

describe('cn helper utility', () => {
  it('combines class names correctly', () => {
    expect(cn('bg-red-500', 'text-white')).toBe('bg-red-500 text-white');
  });

  it('handles conditional classes', () => {
    expect(cn('px-2 py-1', true && 'bg-blue-500', false && 'text-red-500')).toBe('px-2 py-1 bg-blue-500');
  });

  it('merges tailwind classes overriding duplicates', () => {
    expect(cn('p-4 p-2')).toBe('p-2');
    expect(cn('bg-red-500 bg-blue-500')).toBe('bg-blue-500');
  });
});
