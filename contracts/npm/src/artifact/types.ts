import schema from './schemas/v1.0.json';

export const SCHEMA_VERSION = '1.0.0';
export const PACKAGE_VERSION = '1.0.0';

export type ArtifactType = 'text' | 'image' | 'file' | 'json' | 'table';

export const ARTIFACT_TYPES: readonly ArtifactType[] = ['text', 'image', 'file', 'json', 'table'];

export function isArtifactType(value: unknown): value is ArtifactType {
  return typeof value === 'string' && (ARTIFACT_TYPES as readonly string[]).includes(value);
}

export const ARTIFACT_CONSTANTS = {
  MAX_ARTIFACT_CONTENT_LENGTH: schema.properties.constants.properties.MAX_ARTIFACT_CONTENT_LENGTH.const,
  MAX_ARTIFACT_TITLE_LENGTH: schema.properties.constants.properties.MAX_ARTIFACT_TITLE_LENGTH.const,
  MAX_ARTIFACTS_PER_TOOL: schema.properties.constants.properties.MAX_ARTIFACTS_PER_TOOL.const,
} as const;

export const MAX_ARTIFACT_CONTENT_LENGTH = ARTIFACT_CONSTANTS.MAX_ARTIFACT_CONTENT_LENGTH;
export const MAX_ARTIFACT_TITLE_LENGTH = ARTIFACT_CONSTANTS.MAX_ARTIFACT_TITLE_LENGTH;
export const MAX_ARTIFACTS_PER_TOOL = ARTIFACT_CONSTANTS.MAX_ARTIFACTS_PER_TOOL;

export const DEFAULT_MIME_TYPES: Record<ArtifactType, string> = Object.fromEntries(
  Object.entries(schema.properties.defaultMimeTypes.properties).map(([k, v]: [string, any]) => [k, v.const])
) as Record<ArtifactType, string>;

export const MIME_TYPE_MAP: Record<string, string> = schema.properties.mimeTypeMap.properties;

export interface Artifact {
  type: ArtifactType;
  mime_type: string;
  title?: string;
  content?: string;
  preview_url?: string;
  download_url?: string;
  size?: number;
  metadata?: Record<string, any>;
}

export type ArtifactList = Artifact[];

export interface MessageContent {
  text: string;
  artifacts?: Artifact[];
}

export interface Message {
  object: string;
  assistant_id: string;
  chat_id: string;
  message_id: string;
  role: 'user' | 'assistant';
  content: MessageContent;
  num_tokens: number;
  metadata: Record<string, any>;
  created_timestamp: number;
  updated_timestamp: number;
}
