import {
  CollectionDto,
  CollectionVM,
  CollectionStatus,
} from '../viewmodels';
import {
  formatDateTime,
  safeNumber,
  safeString,
  withTableKey,
} from './utils';

const COLLECTION_STATUS_LABELS: Record<CollectionStatus, string> = {
  ready: 'Ready',
  processing: 'Processing',
  error: 'Error',
};

const getCollectionStatusLabel = (status: CollectionStatus): string =>
  COLLECTION_STATUS_LABELS[status] || status;

const DEFAULT_DISPLAY_NAME = 'Untitled Collection';

export const adaptCollection = (dto: CollectionDto): CollectionVM => {
  const numChunks = safeNumber(dto.num_chunks, 0);
  const capacity = safeNumber(dto.capacity, 0);
  const displayName = safeString(dto.name, DEFAULT_DISPLAY_NAME);

  return {
    id: dto.collection_id,
    key: dto.collection_id,
    collectionId: dto.collection_id,
    name: dto.name,
    displayName,
    description: safeString(dto.description),
    numRecords: safeNumber(dto.num_records, 0),
    numChunks,
    capacity,
    capacityText: `${numChunks}/${capacity}`,
    remainingCapacity: Math.max(0, capacity - numChunks),
    embeddingModelId: dto.embedding_model_id,
    embeddingSize: safeNumber(dto.embedding_size, 0),
    status: dto.status,
    statusLabel: getCollectionStatusLabel(dto.status),
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
  };
};

export const adaptCollectionList = (dtos: CollectionDto[]): CollectionVM[] => {
  return dtos.map(adaptCollection);
};

export const adaptCollectionForTable = (vm: CollectionVM): CollectionVM & { key: string } =>
  withTableKey(vm);
