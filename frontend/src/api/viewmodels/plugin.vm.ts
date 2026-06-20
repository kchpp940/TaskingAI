export type ParameterType =
  | 'string'
  | 'integer'
  | 'number'
  | 'boolean'
  | 'string_array'
  | 'integer_array'
  | 'number_array'
  | 'boolean_array'
  | 'image_url'
  | 'file_url';

export interface ParameterSchema {
  type: ParameterType;
  name: string;
  description: string;
  required: boolean;
}

export interface PluginDto {
  object: string;
  bundle_id: string;
  plugin_id: string;
  name: string;
  description: string;
  input_schema: Record<string, ParameterSchema>;
  output_schema: Record<string, ParameterSchema>;
  function_def: Record<string, any>;
}

export interface BundleDto {
  bundle_id: string;
  name: string;
  description: string;
  icon_url: string;
  credentials_schema: Record<string, any>;
  plugins: PluginDto[];
  created_timestamp: number;
  updated_timestamp: number;
}

export interface BundleInstanceDto {
  object: string;
  bundle_instance_id: string;
  bundle_id: string;
  name: string;
  description: string;
  icon_url: string;
  display_credentials: Record<string, any>;
  plugins: PluginDto[];
  metadata: Record<string, any>;
  created_timestamp: number;
  updated_timestamp: number;
}

export interface PluginVM {
  id: string;
  pluginId: string;
  bundleId: string;
  name: string;
  description: string;
  inputSchema: ParameterSchema[];
  outputSchema: ParameterSchema[];
  fullId: string;
}

export interface BundleVM {
  id: string;
  bundleId: string;
  name: string;
  description: string;
  iconUrl: string;
}

export interface BundleInstanceVM {
  id: string;
  key: string;
  bundleInstanceId: string;
  bundleId: string;
  name: string;
  displayName: string;
  description: string;
  iconUrl: string;
  displayCredentials: Record<string, any>;
  hasCredentials: boolean;
  plugins: PluginVM[];
  pluginCount: number;
  createdAt: string;
  updatedAt: string;
  createdTimestamp: number;
  updatedTimestamp: number;
}

export interface PluginParameterVM {
  key: string;
  type: ParameterType;
  name: string;
  description: string;
  required: boolean;
}

export interface BundleInstanceCreateRequest {
  bundle_id: string;
  name?: string;
  credentials: Record<string, any>;
}

export interface BundleInstanceUpdateRequest {
  name: string;
  credentials: Record<string, any>;
}
