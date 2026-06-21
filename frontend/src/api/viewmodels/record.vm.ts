export type RecordType = 'text' | 'file' | 'web';
export type RecordStatus = 'ready' | 'processing' | 'error' | 'indexing';

export interface FileContent {
  file_id: string;
  file_name: string;
  file_size: number;
}

export interface WebContent {
  url: string;
}

export interface RecordDto {
  object: string;
  record_id: string;
  collection_id: string;
  title: string;
  status: RecordStatus;
  num_chunks: number;
  type: RecordType;
  content: string;
  metadata: Record<string, string>;
  created_timestamp: number;
  updated_timestamp: number;
}

export type RecordVM = RecordDto & {
  key: string;
  displayTitle: string;
  statusLabel: string;
  statusClass: string;
  typeLabel: string;
  isTextType: boolean;
  isFileType: boolean;
  isWebType: boolean;
  textContent?: string;
  fileContent?: FileContent;
  webContent?: WebContent;
  displayContent: string;
  createdAt: string;
  updatedAt: string;
};

export interface RecordCreateRequest {
  type: RecordType;
  title?: string;
  content?: string;
  file_id?: string;
  url?: string;
  text_splitter?: {
    type: string;
    chunk_size: number;
    chunk_overlap: number;
  };
  metadata?: Record<string, string>;
}

export interface RecordUpdateRequest extends Partial<RecordCreateRequest> {}
