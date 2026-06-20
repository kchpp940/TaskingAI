export type CollectionStatus = 'ready' | 'processing' | 'error';

export interface CollectionDto {
  object: string;
  collection_id: string;
  name: string;
  description: string;
  num_records: number;
  num_chunks: number;
  capacity: number;
  embedding_model_id: string;
  embedding_size: number;
  status: CollectionStatus;
  metadata: Record<string, any>;
  created_timestamp: number;
  updated_timestamp: number;
}

export interface CollectionVM {
  id: string;
  key: string;
  collectionId: string;
  name: string;
  displayName: string;
  description: string;
  numRecords: number;
  numChunks: number;
  capacity: number;
  capacityText: string;
  remainingCapacity: number;
  embeddingModelId: string;
  embeddingSize: number;
  status: CollectionStatus;
  statusLabel: string;
  createdAt: string;
  updatedAt: string;
  createdTimestamp: number;
  updatedTimestamp: number;
}

export interface CollectionCreateRequest {
  name: string;
  description?: string;
  capacity?: number;
  embedding_model_id: string;
  metadata?: Record<string, any>;
}

export interface CollectionUpdateRequest {
  name?: string;
  description?: string;
  metadata?: Record<string, any>;
}
