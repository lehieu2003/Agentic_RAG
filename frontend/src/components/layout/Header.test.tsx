import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Header from './Header';

describe('Header Component', () => {
  it('renders title and triggers sidebar toggle', () => {
    const onToggleSidebar = vi.fn();
    render(
      <Header
        isViewerOpen={false}
        onToggleViewer={vi.fn()}
        isSidebarOpen={true}
        onToggleSidebar={onToggleSidebar}
        health={{ status: 'ok', vector_store_count: 5 }}
      />
    );
    expect(screen.getByText(/Document Intelligence/i)).toBeInTheDocument();
    expect(screen.getByText(/TCVN & ISO Grounded/i)).toBeInTheDocument();
    expect(screen.getByText(/5 chunks/i)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    expect(onToggleSidebar).toHaveBeenCalled();
  });

  it('triggers viewer toggle when viewer button is clicked', () => {
    const onToggleViewer = vi.fn();
    render(
      <Header
        isViewerOpen={false}
        onToggleViewer={onToggleViewer}
        isSidebarOpen={false}
        onToggleSidebar={vi.fn()}
        health={{ status: 'ok', vector_store_count: 10 }}
      />
    );
    fireEvent.click(screen.getByLabelText(/toggle document viewer/i));
    expect(onToggleViewer).toHaveBeenCalled();
  });

  it('displays connecting or offline status when health is null or error', () => {
    const { rerender } = render(
      <Header
        isViewerOpen={false}
        onToggleViewer={vi.fn()}
        isSidebarOpen={false}
        onToggleSidebar={vi.fn()}
        health={null}
      />
    );
    expect(screen.getByText(/Đang kết nối/i)).toBeInTheDocument();

    rerender(
      <Header
        isViewerOpen={false}
        onToggleViewer={vi.fn()}
        isSidebarOpen={false}
        onToggleSidebar={vi.fn()}
        health={{ status: 'error' }}
      />
    );
    expect(screen.getByText(/Mất kết nối/i)).toBeInTheDocument();
  });

  it('formats large chunk count with toLocaleString', () => {
    render(
      <Header
        isViewerOpen={false}
        onToggleViewer={vi.fn()}
        isSidebarOpen={false}
        onToggleSidebar={vi.fn()}
        health={{ status: 'ok', vector_store_count: 12500 }}
      />
    );
    expect(screen.getByText(new RegExp(`${(12500).toLocaleString()} chunks`))).toBeInTheDocument();
  });

  it('toggles between dark and light theme and remembers the choice', () => {
    localStorage.removeItem('theme');
    document.documentElement.dataset.theme = 'dark';
    render(
      <Header
        isViewerOpen={false}
        onToggleViewer={vi.fn()}
        isSidebarOpen={false}
        onToggleSidebar={vi.fn()}
        health={null}
      />
    );
    fireEvent.click(screen.getByLabelText('Chuyển sang giao diện sáng'));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem('theme')).toBe('light');

    fireEvent.click(screen.getByLabelText('Chuyển sang giao diện tối'));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem('theme')).toBe('dark');
  });
});
