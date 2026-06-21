import {
  BundleInstanceDto,
  BundleInstanceVM,
  PluginDto,
  PluginVM,
  BundleDto,
  BundleVM,
  ParameterSchema,
  PluginParameterVM,
} from '../viewmodels';
import {
  formatDateTime,
  safeArray,
  safeNumber,
  safeObject,
  safeString,
} from './utils';

const DEFAULT_DISPLAY_NAME = 'Untitled Plugin';

export const adaptPluginParameter = (
  key: string,
  schema: ParameterSchema,
): PluginParameterVM => {
  return {
    key,
    type: schema.type,
    name: safeString(schema.name),
    description: safeString(schema.description),
    required: !!schema.required,
  };
};

export const adaptPluginParameterList = (
  inputSchema: Record<string, ParameterSchema>,
): PluginParameterVM[] => {
  return Object.entries(safeObject(inputSchema, {})).map(([key, schema]) =>
    adaptPluginParameter(key, schema),
  );
};

export const adaptPlugin = (dto: PluginDto): PluginVM => {
  const inputSchema = safeObject(dto.input_schema, {});
  const outputSchema = safeObject(dto.output_schema, {});
  return {
    id: `${dto.bundle_id}/${dto.plugin_id}`,
    pluginId: dto.plugin_id,
    bundleId: dto.bundle_id,
    name: safeString(dto.name),
    description: safeString(dto.description),
    inputSchema: Object.values(inputSchema),
    outputSchema: Object.values(outputSchema),
    fullId: `${dto.bundle_id}/${dto.plugin_id}`,
  };
};

export const adaptPluginList = (dtos: PluginDto[]): PluginVM[] => {
  return safeArray(dtos, []).map(adaptPlugin);
};

export const adaptBundle = (dto: BundleDto): BundleVM => {
  return {
    id: dto.bundle_id,
    bundleId: dto.bundle_id,
    name: safeString(dto.name),
    description: safeString(dto.description),
    iconUrl: safeString(dto.icon_url),
    registered: dto.registered,
    numPlugins: dto.num_plugins,
    developer: safeString(dto.developer),
    credentialsSchema: safeObject(dto.credentials_schema, {}),
    plugins: dto.plugins ? adaptPluginList(dto.plugins) : undefined,
  };
};

export const adaptBundleList = (dtos: BundleDto[]): BundleVM[] => {
  return dtos.map(adaptBundle);
};

export const adaptBundleInstance = (dto: BundleInstanceDto): BundleInstanceVM => {
  const displayCredentials = safeObject(dto.display_credentials, {});
  return {
    id: dto.bundle_instance_id,
    bundleId: dto.bundle_id,
    name: dto.name,
    description: dto.description,
    iconUrl: dto.icon_url,
    displayCredentials: displayCredentials,
    plugins: adaptPluginList(dto.plugins),
    metadata: dto.metadata,
    createdTimestamp: dto.created_timestamp,
    updatedTimestamp: dto.updated_timestamp,
    key: dto.bundle_instance_id,
    displayName: safeString(dto.name, DEFAULT_DISPLAY_NAME),
    hasCredentials: Object.keys(displayCredentials).length > 0,
    pluginCount: safeNumber(dto.plugins.length, 0),
    createdAt: formatDateTime(dto.created_timestamp),
    updatedAt: formatDateTime(dto.updated_timestamp),
  };
};

export const adaptBundleInstanceList = (dtos: BundleInstanceDto[]): BundleInstanceVM[] => {
  return dtos.map(adaptBundleInstance);
};
