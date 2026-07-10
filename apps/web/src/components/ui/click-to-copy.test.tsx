import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, act } from '@testing-library/react';
import { ClickToCopy } from './click-to-copy';

describe('ClickToCopy component', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockImplementation(() => Promise.resolve()),
      },
    });
  });

  it('renders text content correctly', () => {
    render(<ClickToCopy text="hello-world" />);
    expect(screen.getByText('hello-world')).toBeInTheDocument();
  });

  it('calls clipboard writeText on click', async () => {
    render(<ClickToCopy text="test-copy-text" />);
    const button = screen.getByRole('button');
    
    await act(async () => {
      await fireEvent.click(button);
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('test-copy-text');
  });

  it('toggles copied status and resets after timeout', async () => {
    render(<ClickToCopy text="timeout-test" />);
    const button = screen.getByRole('button');
    
    await act(async () => {
      await fireEvent.click(button);
    });

    expect(button.querySelector('svg')).toHaveClass('text-green');

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(button.querySelector('svg')).not.toHaveClass('text-green');
  });

  it('applies multiline classes when multiline is true', () => {
    render(<ClickToCopy text="multiline-text" multiline />);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('items-start');
    
    const textSpan = button.querySelector('span');
    expect(textSpan).toHaveClass('whitespace-pre-wrap');
    expect(textSpan).toHaveClass('break-words');
  });
});
