import { ApikeyDto, ApikeyVM } from '../viewmodels';
import { formatDateTime, safeString, withTableKey } from './utils';

export const adaptApikey = (dto: ApikeyDto): ApikeyVM => {
  return {
    id: dto.apikey_id,
    key: dto.apikey_id,
    apikeyId: dto.apikey_id,
    name: safeString(dto.name, 'Untitled API Key'),
    apikey: safeString(dto.apikey),
    maskedApikey: safeString(dto.apikey, '****'),
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
  };
};

export const adaptApikeyList = (dtos: ApikeyDto[]): ApikeyVM[] => {
  return dtos.map(adaptApikey);
};

export const adaptApikeyForTable = (vm: ApikeyVM): ApikeyVM & { key: string } => withTableKey(vm);
