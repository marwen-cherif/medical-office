import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from './button';

describe('Button component', () => {
  it('renders a button with children', () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole('button', { name: /click me/i });
    expect(button).toBeInTheDocument();
  });

  it('applies default classes', () => {
    render(<Button>Default</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-navy');
  });

  it('applies custom variant classes', () => {
    render(<Button variant="destructive">Destructive</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-red');
  });
});
