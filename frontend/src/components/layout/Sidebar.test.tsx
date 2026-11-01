import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import Sidebar from './Sidebar';

describe('Sidebar Component', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockImplementation(() => true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const files = [
    { filename: 'tài liệu máy bơm.pdf', size: 1048576 },
    { filename: 'huong_dan_iso.docx', size: 50000 },
  ];

  it('renders file list and allows deleting file', () => {
    const onDeleteFile = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={onDeleteFile}
      />
    );
    expect(screen.getByText('tài liệu máy bơm.pdf')).toBeInTheDocument();
    expect(screen.getByText('1.0 MB')).toBeInTheDocument();
    expect(screen.getByText('huong_dan_iso.docx')).toBeInTheDocument();
    expect(screen.getByText('48.8 KB')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/delete tài liệu máy bơm.pdf/i));
    expect(onDeleteFile).toHaveBeenCalledWith('tài liệu máy bơm.pdf');
  });

  it('handles topK slider change', () => {
    const onTopKChange = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={onTopKChange}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
      />
    );
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '12' } });
    expect(onTopKChange).toHaveBeenCalledWith(12);
  });

  it('triggers onNewChat when new chat button is clicked', () => {
    const onNewChat = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={onNewChat}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /cuộc trò chuyện mới/i }));
    expect(onNewChat).toHaveBeenCalled();
  });

  it('triggers onFileUpload when file is selected via input', () => {
    const onFileUpload = vi.fn().mockResolvedValue(undefined);
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={onFileUpload}
        onDeleteFile={vi.fn()}
      />
    );
    const file = new File(['sample content'], 'test-document.pdf', { type: 'application/pdf' });
    const input = screen.getByTestId('file-upload-input');
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFileUpload).toHaveBeenCalledWith(file);
  });

  it('triggers onFileUpload on drop', () => {
    const onFileUpload = vi.fn().mockResolvedValue(undefined);
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={onFileUpload}
        onDeleteFile={vi.fn()}
      />
    );
    const dropzone = screen.getByRole('button', { name: /tải lên tài liệu/i });
    const file = new File(['dragged content'], 'dropped-spec.pdf', { type: 'application/pdf' });

    fireEvent.dragOver(dropzone);
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(onFileUpload).toHaveBeenCalledWith(file);
  });

  it('renders empty message when no files exist', () => {
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={[]}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
      />
    );
    expect(screen.getByText(/chưa có tài liệu nào/i)).toBeInTheDocument();
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <Sidebar
        isOpen={false}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('shows uploading spinner / loading state when isUploading is true', () => {
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
        isUploading={true}
      />
    );
    expect(screen.getByText(/đang tải lên/i)).toBeInTheDocument();
  });

  it('calls onClose when close sidebar button is clicked', () => {
    const onClose = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={onClose}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
      />
    );
    fireEvent.click(screen.getByLabelText(/close sidebar/i));
    expect(onClose).toHaveBeenCalled();
  });

  it('prompts window.confirm and aborts deletion if user cancels', () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const onDeleteFile = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={onDeleteFile}
      />
    );
    fireEvent.click(screen.getByLabelText(/delete tài liệu máy bơm.pdf/i));
    expect(confirmSpy).toHaveBeenCalledWith(
      'Bạn có chắc chắn muốn xóa "tài liệu máy bơm.pdf" khỏi hệ thống không?'
    );
    expect(onDeleteFile).not.toHaveBeenCalled();
  });

  it('rejects unsupported file extension on drop with visual feedback', () => {
    const onFileUpload = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={onFileUpload}
        onDeleteFile={vi.fn()}
      />
    );
    const dropzone = screen.getByRole('button', { name: /tải lên tài liệu/i });
    const unsupportedFile = new File(['content'], 'malware.exe', { type: 'application/x-msdownload' });

    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [unsupportedFile],
      },
    });

    expect(onFileUpload).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/không được hỗ trợ/i);
  });

  it('displays external errorMessage and allows dismissing it', () => {
    const onDismissError = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
        errorMessage="Lỗi mạng: Không thể tải danh sách tài liệu"
        onDismissError={onDismissError}
      />
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Lỗi mạng: Không thể tải danh sách tài liệu');
    fireEvent.click(screen.getByLabelText(/dismiss sidebar error/i));
    expect(onDismissError).toHaveBeenCalled();
  });

  it('renders recent chat sessions and allows switching session', () => {
    const onSelectSession = vi.fn();
    const sessions = [{ id: 's1', title: 'Tính Reynolds', created_at: '', updated_at: '' }];
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={[]}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
        sessions={sessions}
        activeSessionId="s1"
        onSelectSession={onSelectSession}
        onDeleteSession={vi.fn()}
      />
    );
    expect(screen.getByText('Tính Reynolds')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Tính Reynolds'));
    expect(onSelectSession).toHaveBeenCalledWith('s1');
  });

  it('renders empty message when no chat sessions exist', () => {
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={[]}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
        sessions={[]}
      />
    );
    expect(screen.getByText(/chưa có cuộc trò chuyện nào/i)).toBeInTheDocument();
  });

  it('allows deleting a session with confirmation', () => {
    const onDeleteSession = vi.fn();
    const sessions = [{ id: 's1', title: 'Tính Reynolds', created_at: '', updated_at: '' }];
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={[]}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
        sessions={sessions}
        activeSessionId="s1"
        onSelectSession={vi.fn()}
        onDeleteSession={onDeleteSession}
      />
    );
    const deleteBtn = screen.getByLabelText(/xóa cuộc trò chuyện/i);
    fireEvent.click(deleteBtn);
    expect(window.confirm).toHaveBeenCalledWith('Bạn có chắc chắn muốn xóa cuộc trò chuyện này không?');
    expect(onDeleteSession).toHaveBeenCalledWith('s1');
  });

  it('renders segmented control tabs and switches active tab on click', () => {
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
      />
    );

    const chatsTab = screen.getByRole('tab', { name: /cuộc trò chuyện/i });
    const docsTab = screen.getByRole('tab', { name: /tài liệu/i });

    expect(chatsTab).toHaveAttribute('aria-selected', 'true');
    expect(docsTab).toHaveAttribute('aria-selected', 'false');

    // Switch to documents tab
    fireEvent.click(docsTab);
    expect(chatsTab).toHaveAttribute('aria-selected', 'false');
    expect(docsTab).toHaveAttribute('aria-selected', 'true');

    // Switch back to chats tab
    fireEvent.click(chatsTab);
    expect(chatsTab).toHaveAttribute('aria-selected', 'true');
    expect(docsTab).toHaveAttribute('aria-selected', 'false');
  });

  it('renders session relative timestamp when provided', () => {
    const recentDate = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    const sessions = [{ id: 's2', title: 'Phiên hỏi gần đây', created_at: recentDate, updated_at: recentDate }];
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={[]}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
        sessions={sessions}
      />
    );

    expect(screen.getByText('Phiên hỏi gần đây')).toBeInTheDocument();
    expect(screen.getByText(/5m trước/i)).toBeInTheDocument();
  });
});
