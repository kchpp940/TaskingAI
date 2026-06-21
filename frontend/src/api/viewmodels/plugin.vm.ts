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
  plugins: PluginDto[];
  created_timestamp: number;
  updated_timestamp: number;
  registered?: boolean;
  num_plugins?: number;
  developer?: string;
  credentials_schema?: Record<string, any>;
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
  registered?: boolean;
  numPlugins?: number;
  developer?: string;
  credentialsSchema?: Record<string, any>;
  plugins?: PluginVM[];
}

export interface BundleInstanceVM {
  id: string;
  bundleId: string;
  name: string;
  description: string;
  iconUrl: string;
  displayCredentials: Record<string, any>;
  plugins: PluginVM[];
  metadata: Record<string, any>;
  createdTimestamp: number;
  updatedTimestamp: number;
  key: string;
  displayName: string;
  hasCredentials: boolean;
  pluginCount: number;
  createdAt: string;
  updatedAt: string;
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
