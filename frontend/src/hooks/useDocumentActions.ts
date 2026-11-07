import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { deleteDocument, pollUploadJob, uploadDocumentAsync } from '../api/client';
import type { ActiveDocument } from '../components/viewer/DocumentViewer';

interface DocumentActionsParams {
  activeDocument: ActiveDocument | null;
  setActiveDocument: Dispatch<SetStateAction<ActiveDocument | null>>;
  setIsUploading: Dispatch<SetStateAction<boolean>>;
  setUploadFilename: Dispatch<SetStateAction<string | null>>;
  setSidebarError: Dispatch<SetStateAction<string | null>>;
  refreshState: () => Promise<void>;
}

export interface DocumentActions {
  handleFileUpload: (file: File) => Promise<void>;
  handleDeleteFile: (filename: string) => Promise<void>;
}

/**
 * Document upload and deletion actions, keeping the active viewer document in
 * sync when its file is removed.
 *
 * Uploads run in the background: the file is accepted immediately (job id),
 * heavy OCR/chunking/indexing is tracked by polling the job endpoint, so the
 * sidebar spinner survives long scans instead of a hanging request.
 */
export function useDocumentActions({
  activeDocument,
  setActiveDocument,
  setIsUploading,
  setUploadFilename,
  setSidebarError,
  refreshState,
}: DocumentActionsParams): DocumentActions {
  const handleFileUpload = useCallback(
    async (file: File) => {
      setSidebarError(null);
      try {
        setIsUploading(true);
        setUploadFilename(file.name);
        const job = await uploadDocumentAsync(file);
        await pollUploadJob(job.job_id);
        await refreshState();
      } catch (err: any) {
        console.error('File upload error:', err);
        const msg =
          err?.message ||
          'Tải tệp lên thất bại. Vui lòng kiểm tra định dạng hoặc thử lại.';
        setSidebarError(`Lỗi tải tệp: ${msg}`);
      } finally {
        setIsUploading(false);
        setUploadFilename(null);
      }
    },
    [refreshState, setIsUploading, setUploadFilename, setSidebarError]
  );

  const handleDeleteFile = useCallback(
    async (filename: string) => {
      setSidebarError(null);
      try {
        await deleteDocument(filename);
        if (activeDocument?.filename === filename) {
          setActiveDocument(null);
        }
        await refreshState();
      } catch (err: any) {
        console.error('File delete error:', err);
        const msg =
          err?.message ||
          'Xóa tệp thất bại. Vui lòng thử lại.';
        setSidebarError(`Lỗi xóa tệp: ${msg}`);
      }
    },
    [activeDocument, refreshState, setActiveDocument, setSidebarError]
  );

  return { handleFileUpload, handleDeleteFile };
}
