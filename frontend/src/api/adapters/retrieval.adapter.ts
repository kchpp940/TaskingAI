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
    ...dto,
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

export const adaptCollectionForTable = (vm: CollectionVM): CollectionVM => vm;
