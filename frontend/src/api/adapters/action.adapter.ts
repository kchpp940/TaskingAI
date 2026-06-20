import {
  ActionDto,
  ActionVM,
  ActionMethod,
  ActionEndpointInfo,
} from '../viewmodels';
import {
  formatDateTime,
  safeArray,
  safeObject,
  safeString,
  withTableKey,
} from './utils';

const HTTP_METHOD_LABELS: Record<ActionMethod, string> = {
  GET: 'GET',
  POST: 'POST',
  PUT: 'PUT',
  DELETE: 'DELETE',
  PATCH: 'PATCH',
  NONE: 'NONE',
};

const getHttpMethodLabel = (method: ActionMethod): string => HTTP_METHOD_LABELS[method] || method;

export const extractEndpointFromOpenApi = (
  openapiSchema: Record<string, any>,
): ActionEndpointInfo => {
  if (!openapiSchema || !openapiSchema.servers || !openapiSchema.paths) {
    return { method: 'NONE', endpoint: '' };
  }
  const baseUrl = openapiSchema.servers[0]?.url || '';
  const paths = Object.keys(openapiSchema.paths);
  if (paths.length === 0) {
    return { method: 'NONE', endpoint: baseUrl };
  }
  const firstPath = paths[0];
  const methods = openapiSchema.paths[firstPath];
  const firstMethod = Object.keys(methods)[0]?.toUpperCase() as ActionMethod || 'NONE';
  return {
    method: firstMethod,
    endpoint: baseUrl + firstPath,
  };
};

export const adaptAction = (dto: ActionDto): ActionVM => {
  const openapiSchema = safeObject(dto.openapi_schema, {});
  const endpointInfo = extractEndpointFromOpenApi(openapiSchema);
  const method = dto.method || endpointInfo.method;

  return {
    id: dto.action_id,
    key: dto.action_id,
    actionId: dto.action_id,
    name: safeString(dto.name, 'Untitled Action'),
    operationId: safeString(dto.operation_id),
    description: safeString(dto.description),
    url: safeString(dto.url),
    method,
    methodLabel: getHttpMethodLabel(method),
    bodyType: dto.body_type,
    endpoint: endpointInfo.endpoint || safeString(dto.url),
    endpointInfo,
    hasPathParams: safeArray(Object.keys(dto.path_param_schema || {}), []).length > 0,
    hasQueryParams: safeArray(Object.keys(dto.query_param_schema || {}), []).length > 0,
    hasBodyParams: safeArray(Object.keys(dto.body_param_schema || {}), []).length > 0,
    openapiSchema,
    authentication: safeObject(dto.authentication, { type: 'none' }),
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
  };
};

export const adaptActionList = (dtos: ActionDto[]): ActionVM[] => {
  return dtos.map(adaptAction);
};

export const adaptActionForTable = (vm: ActionVM): ActionVM & { key: string } => withTableKey(vm);
