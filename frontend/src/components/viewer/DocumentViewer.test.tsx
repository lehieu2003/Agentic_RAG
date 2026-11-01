import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import DocumentViewer from './DocumentViewer';

describe('DocumentViewer Component', () => {
  it('renders empty state when no document is active', () => {
    render(<DocumentViewer activeDocument={null} onClose={vi.fn()} />);
    expect(screen.getByText(/Chọn hoặc bấm vào một trích dẫn/i)).toBeInTheDocument();
  });

  it('renders document iframe with encoded URL and page anchor', () => {
    render(
      <DocumentViewer
        activeDocument={{ filename: 'tài liệu máy bơm.pdf', page: 11 }}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText('tài liệu máy bơm.pdf')).toBeInTheDocument();
    const iframe = screen.getByTitle('Document Preview') as HTMLIFrameElement;
    expect(iframe.src).toContain(encodeURIComponent('tài liệu máy bơm.pdf'));
    expect(iframe.src).toContain('#page=11');
  });

  it('renders iframe without page anchor if page is undefined', () => {
    render(
      <DocumentViewer
        activeDocument={{ filename: 'document.pdf' }}
        onClose={vi.fn()}
      />
    );
    const iframe = screen.getByTitle('Document Preview') as HTMLIFrameElement;
    expect(iframe.src).toContain('/api/v1/files/document.pdf');
    expect(iframe.src).not.toContain('#page=');
  });

  it('supports page navigation controls (next and previous)', () => {
    const onPageChange = vi.fn();
    render(
      <DocumentViewer
        activeDocument={{ filename: 'test.pdf', page: 5 }}
        onClose={vi.fn()}
        onPageChange={onPageChange}
      />
    );

    const nextBtn = screen.getByLabelText(/next page/i);
    fireEvent.click(nextBtn);
    expect(onPageChange).toHaveBeenCalledWith(6);

    const prevBtn = screen.getByLabelText(/previous page/i);
    fireEvent.click(prevBtn);
    expect(onPageChange).toHaveBeenCalledWith(4);
  });

  it('disables previous button on page 1', () => {
    const onPageChange = vi.fn();
    render(
      <DocumentViewer
        activeDocument={{ filename: 'test.pdf', page: 1 }}
        onClose={vi.fn()}
        onPageChange={onPageChange}
      />
    );

    const prevBtn = screen.getByLabelText(/previous page/i);
    expect(prevBtn).toBeDisabled();
    fireEvent.click(prevBtn);
    expect(onPageChange).not.toHaveBeenCalled();
  });

  it('supports direct page input entry', () => {
    const onPageChange = vi.fn();
    render(
      <DocumentViewer
        activeDocument={{ filename: 'test.pdf', page: 5 }}
        onClose={vi.fn()}
        onPageChange={onPageChange}
      />
    );

    const pageInput = screen.getByLabelText(/page number/i) as HTMLInputElement;
    expect(pageInput.value).toBe('5');

    fireEvent.change(pageInput, { target: { value: '15' } });
    fireEvent.keyDown(pageInput, { key: 'Enter', code: 'Enter' });
    expect(onPageChange).toHaveBeenCalledWith(15);
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <DocumentViewer
        activeDocument={{ filename: 'test.pdf', page: 1 }}
        onClose={onClose}
      />
    );

    const closeBtn = screen.getByLabelText(/close document viewer/i);
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders open in new tab button with encoded file URL', () => {
    render(
      <DocumentViewer
        activeDocument={{ filename: 'tài liệu.pdf', page: 3 }}
        onClose={vi.fn()}
      />
    );

    const externalLink = screen.getByLabelText(/open in new tab/i) as HTMLAnchorElement;
    expect(externalLink).toBeInTheDocument();
    expect(externalLink.target).toBe('_blank');
    expect(externalLink.href).toContain(encodeURIComponent('tài liệu.pdf'));
    expect(externalLink.href).toContain('#page=3');
  });

  it('renders fallback download link/button', () => {
    render(
      <DocumentViewer
        activeDocument={{ filename: 'test.pdf' }}
        onClose={vi.fn()}
      />
    );

    const downloadLink = screen.getByLabelText(/download document/i) as HTMLAnchorElement;
    expect(downloadLink).toBeInTheDocument();
    expect(downloadLink.href).toContain('/api/v1/files/test.pdf');
  });

  it('displays informative banner and download option for non-PDF files', () => {
    render(
      <DocumentViewer
        activeDocument={{ filename: 'bao_cao.docx' }}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText(/không hỗ trợ xem trước trực tiếp/i)).toBeInTheDocument();
    const filenames = screen.getAllByText('bao_cao.docx');
    expect(filenames.length).toBeGreaterThanOrEqual(1);
    const downloadLink = screen.getByLabelText(/download document/i);
    expect(downloadLink).toBeInTheDocument();
  });
});
