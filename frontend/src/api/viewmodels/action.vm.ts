export type ActionMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | 'NONE';
export type ActionBodyType = 'JSON' | 'FORM' | 'NONE';

export interface ActionParam {
  type: string;
  description: string;
  enum?: string[];
  required: boolean;
}

export interface ActionAuthentication {
  type: string;
  content?: Record<string, string>;
  secret?: string;
}

export interface ActionDto {
  object: string;
  action_id: string;
  name: string;
  operation_id: string;
  description: string;
  url: string;
  method: ActionMethod;
  path_param_schema?: Record<string, ActionParam>;
  query_param_schema?: Record<string, ActionParam>;
  body_param_schema?: Record<string, ActionParam>;
  body_type: ActionBodyType;
  function_def: Record<string, any>;
  openapi_schema: Record<string, any>;
  authentication: ActionAuthentication;
  created_timestamp: number;
  updated_timestamp: number;
}

export interface ActionEndpointInfo {
  method: ActionMethod;
  endpoint: string;
}

export type ActionVM = ActionDto & {
  key: string;
  methodLabel: string;
  endpointInfo: ActionEndpointInfo;
  hasPathParams: boolean;
  hasQueryParams: boolean;
  hasBodyParams: boolean;
  createdAt: string;
  updatedAt: string;
};

export interface ActionBulkCreateRequest {
  openapi_schema: Record<string, any>;
  authentication?: ActionAuthentication;
}

export interface ActionUpdateRequest {
  openapi_schema?: Record<string, any>;
  authentication?: ActionAuthentication;
}
