import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ReasoningSteps from './ReasoningSteps';
import type { ReasoningStep } from '../../types';

describe('ReasoningSteps Component', () => {
  it('returns null if steps array is empty', () => {
    const { container } = render(<ReasoningSteps steps={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders reasoning steps and toggles expand/collapse', () => {
    const steps: ReasoningStep[] = [
      { node: 'retrieve', status: 'completed', message: 'Tìm thấy 3 đoạn' },
      { node: 'grade', status: 'in_progress', message: 'Đang chấm điểm' },
    ];

    render(<ReasoningSteps steps={steps} />);
    expect(screen.getByText(/Quy trình suy luận/i)).toBeInTheDocument();
    expect(screen.getByText(/1\/2 bước/i)).toBeInTheDocument();

    // Initially collapsed
    expect(screen.queryByText(/Tìm thấy 3 đoạn/i)).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(screen.getByRole('button', { name: /Quy trình suy luận/i }));
    expect(screen.getByText(/Tìm thấy 3 đoạn/i)).toBeInTheDocument();
    expect(screen.getByText(/Đang chấm điểm/i)).toBeInTheDocument();
  });
});
