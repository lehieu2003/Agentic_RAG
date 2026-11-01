import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import EvidenceExpander from './EvidenceExpander';
import type { EvidenceChunk } from '../../types';

describe('EvidenceExpander Component', () => {
  it('returns null if evidence array is empty', () => {
    const { container } = render(<EvidenceExpander evidence={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders evidence and expands on click', () => {
    const onCitationClick = vi.fn();
    const evidence: EvidenceChunk[] = [
      {
        filename: 'iso_9906.pdf',
        page: 7,
        score: 0.954,
        text: 'Nghiệm thu thủy lực cho bơm cấp 1 và cấp 2',
      },
    ];

    render(
      <EvidenceExpander
        evidence={evidence}
        onCitationClick={onCitationClick}
      />
    );

    expect(screen.getByText(/Dữ liệu trích dẫn/i)).toBeInTheDocument();
    expect(screen.getByText(/1 đoạn ngữ cảnh/i)).toBeInTheDocument();

    // Expand
    fireEvent.click(screen.getByRole('button', { name: /Dữ liệu trích dẫn/i }));
    expect(screen.getByText('iso_9906.pdf')).toBeInTheDocument();
    expect(screen.getByText('Trang 7')).toBeInTheDocument();
    expect(screen.getByText(/95.4%/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Nghiệm thu thủy lực cho bơm cấp 1 và cấp 2/i)
    ).toBeInTheDocument();

    // Click "Mở PDF"
    const openPdfBtn = screen.getByRole('button', { name: /Mở PDF/i });
    fireEvent.click(openPdfBtn);
    expect(onCitationClick).toHaveBeenCalledWith('iso_9906.pdf', 7);
  });
});
