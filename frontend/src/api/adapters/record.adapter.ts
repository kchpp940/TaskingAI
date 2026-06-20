import {
  RecordDto,
  RecordVM,
  RecordType,
  RecordStatus,
  FileContent,
  WebContent,
} from '../viewmodels';
import {
  formatDateTime,
  safeNumber,
  safeString,
  parseJsonSafe,
  withTableKey,
} from './utils';

const RECORD_TYPE_LABELS: Record<RecordType, string> = {
  text: 'Text',
  file: 'File',
  web: 'Website',
};

const RECORD_STATUS_LABELS: Record<RecordStatus, string> = {
  ready: 'Ready',
  processing: 'Processing',
  error: 'Error',
  indexing: 'Indexing',
};

const getRecordTypeLabel = (type: RecordType): string => RECORD_TYPE_LABELS[type] || type;
const getRecordStatusLabel = (status: RecordStatus): string => RECORD_STATUS_LABELS[status] || status;
const getRecordStatusClass = (status: RecordStatus): string => `status-${status}`;

const DEFAULT_DISPLAY_TITLE = 'Untitled';

const parseContentByType = (
  type: RecordType,
  content: string,
): { textContent?: string; fileContent?: FileContent; webContent?: WebContent; displayContent: string } => {
  switch (type) {
    case 'text':
      return {
        textContent: content,
        displayContent: content,
      };
    case 'file': {
      const fileContent = parseJsonSafe<FileContent>(content, {
        file_id: '',
        file_name: '',
        file_size: 0,
      });
      return {
        fileContent,
        displayContent: fileContent.file_name || 'File',
      };
    }
    case 'web': {
      const webContent = parseJsonSafe<WebContent>(content, { url: '' });
      return {
        webContent,
        displayContent: webContent.url || 'Website',
      };
    }
    default:
      return { displayContent: content };
  }
};

export const adaptRecord = (dto: RecordDto): RecordVM => {
  const content = safeString(dto.content);
  const parsedContent = parseContentByType(dto.type, content);
  const displayTitle = safeString(dto.title, DEFAULT_DISPLAY_TITLE);

  return {
    id: dto.record_id,
    key: dto.record_id,
    recordId: dto.record_id,
    collectionId: dto.collection_id,
    title: dto.title,
    displayTitle,
    status: dto.status,
    statusLabel: getRecordStatusLabel(dto.status),
    statusClass: getRecordStatusClass(dto.status),
    numChunks: safeNumber(dto.num_chunks, 0),
    type: dto.type,
    typeLabel: getRecordTypeLabel(dto.type),
    isTextType: dto.type === 'text',
    isFileType: dto.type === 'file',
    isWebType: dto.type === 'web',
    content,
    textContent: parsedContent.textContent,
    fileContent: parsedContent.fileContent,
    webContent: parsedContent.webContent,
    displayContent: parsedContent.displayContent,
    metadata: dto.metadata || {},
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
  };
};

export const adaptRecordList = (dtos: RecordDto[]): RecordVM[] => {
  return dtos.map(adaptRecord);
};

export const adaptRecordForTable = (vm: RecordVM): RecordVM & { key: string } => withTableKey(vm);
