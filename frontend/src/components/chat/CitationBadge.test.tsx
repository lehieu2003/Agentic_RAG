import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CitationBadge from './CitationBadge';
import type { Citation } from '../../types';

describe('CitationBadge Component', () => {
  it('renders filename and page number and triggers onClick', () => {
    const handleClick = vi.fn();
    const citation: Citation = {
      filename: 'tcvn_maybom.pdf',
      page: 15,
    };

    render(<CitationBadge citation={citation} onClick={handleClick} />);
    expect(screen.getByText('tcvn_maybom.pdf')).toBeInTheDocument();
    expect(screen.getByText(/Trang 15/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledWith('tcvn_maybom.pdf', 15);
  });

  it('handles doc_name and page_number fallbacks', () => {
    const handleClick = vi.fn();
    const citation: Citation = {
      doc_name: 'tcvn_iso.pdf',
      page_number: 42,
    };

    render(<CitationBadge citation={citation} onClick={handleClick} />);
    expect(screen.getByText('tcvn_iso.pdf')).toBeInTheDocument();
    expect(screen.getByText(/Trang 42/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledWith('tcvn_iso.pdf', 42);
  });

  it('renders without page number when page is undefined', () => {
    const handleClick = vi.fn();
    const citation: Citation = {
      filename: 'general_standard.pdf',
    };

    render(<CitationBadge citation={citation} onClick={handleClick} />);
    expect(screen.getByText('general_standard.pdf')).toBeInTheDocument();
    expect(screen.queryByText(/Trang/i)).not.toBeInTheDocument();
  });
});
