import {
  CollectionDto,
  CollectionVM,
} from '../viewmodels';
import { formatDateTime, safeNumber, safeString } from './utils';

const DEFAULT_DISPLAY_NAME = 'Untitled Collection';

export const adaptCollection = (dto: CollectionDto): CollectionVM => {
  const numChunks = safeNumber(dto.num_chunks, 0);
  const capacity = safeNumber(dto.capacity, 0);
  const displayName = safeString(dto.name, DEFAULT_DISPLAY_NAME);

  return {
    id: dto.collection_id,
    name: dto.name,
    description: dto.description,
    numRecords: dto.num_records,
    numChunks: numChunks,
    capacity: capacity,
    embeddingModelId: dto.embedding_model_id,
    embeddingSize: dto.embedding_size,
    status: dto.status,
    metadata: dto.metadata,
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
    key: dto.collection_id,
    capacityText: `${numChunks}/${capacity}`,
    remainingCapacity: Math.max(0, capacity - numChunks),
    displayName,
    createdAt: formatDateTime(dto.created_timestamp),
  };
};

export const adaptCollectionList = (dtos: CollectionDto[]): CollectionVM[] => {
  return dtos.map(adaptCollection);
};
