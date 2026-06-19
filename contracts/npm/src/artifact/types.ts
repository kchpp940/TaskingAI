// AUTO-GENERATED - DO NOT EDIT MANUALLY
// Source: contracts/artifact/v1.0.json
// Package: @taskingai/contracts v1.0.0

/**
 * Artifact Protocol Constants
 * Source: contracts/artifact/v1.0.json#/properties/constants
 */
export const ARTIFACT_CONSTANTS = {
  MAX_ARTIFACT_CONTENT_LENGTH: 4096,
  MAX_ARTIFACT_TITLE_LENGTH: 128,
  MAX_ARTIFACTS_PER_TOOL: 10,
} as const;

export const MAX_ARTIFACT_CONTENT_LENGTH = ARTIFACT_CONSTANTS.MAX_ARTIFACT_CONTENT_LENGTH;
export const MAX_ARTIFACT_TITLE_LENGTH = ARTIFACT_CONSTANTS.MAX_ARTIFACT_TITLE_LENGTH;
export const MAX_ARTIFACTS_PER_TOOL = ARTIFACT_CONSTANTS.MAX_ARTIFACTS_PER_TOOL;

/**
 * Default MIME types for each artifact type
 * Source: contracts/artifact/v1.0.json#/properties/defaultMimeTypes
 */
export const DEFAULT_MIME_TYPES: Record<ArtifactType, string> = {
  text: 'text/plain',
  image: 'image/png',
  file: 'application/octet-stream',
  json: 'application/json',
  table: 'application/json',
};

/**
 * File extension to MIME type mapping
 * Source: contracts/artifact/v1.0.json#/properties/mimeTypeMap
 */
export const MIME_TYPE_MAP: Record<string, string> = {
  'png': 'image/png',
  'jpg': 'image/jpeg',
  'jpeg': 'image/jpeg',
  'gif': 'image/gif',
  'webp': 'image/webp',
  'svg': 'image/svg+xml',
  'pdf': 'application/pdf',
  'txt': 'text/plain',
  'md': 'text/markdown',
  'html': 'text/html',
  'json': 'application/json',
  'csv': 'text/csv',
  'mp3': 'audio/mpeg',
  'wav': 'audio/wav',
  'mp4': 'video/mp4',
  'webm': 'video/webm',
  'zip': 'application/zip',
};

/**
 * The type of the artifact.
 * Only these 5 types are supported across all layers.
 * Source: contracts/artifact/v1.0.json#/definitions/ArtifactType
 */
export type ArtifactType = 'text' | 'image' | 'file' | 'json' | 'table';

export const ARTIFACT_TYPES: readonly ArtifactType[] = [
  'text', 'image', 'file', 'json', 'table',
];

/**
 * Check if a string is a valid ArtifactType.
 */
export function isArtifactType(value: unknown): value is ArtifactType {
  return typeof value === 'string' && (ARTIFACT_TYPES as readonly string[]).includes(value);
}

/**
 * Standard artifact data transfer object (DTO).
 * All layers must use this exact schema.
 * Source: contracts/artifact/v1.0.json#/definitions/Artifact
 */
export interface Artifact {
  /** The type of the artifact. */
  type: ArtifactType;

  /** The MIME type of the artifact. Must be in 'type/subtype' format, lowercase. */
  mime_type: string;

  /** The display title of the artifact. Will be truncated if exceeds max length. */
  title?: string;

  /** The text content of the artifact (for text, json, table, etc.). Will be truncated if exceeds max content length. */
  content?: string;

  /** The preview image URL of the artifact. */
  preview_url?: string;

  /** The download URL of the artifact. */
  download_url?: string;

  /** The size of the artifact in bytes. */
  size?: number;

  /** Additional metadata for the artifact. */
  metadata?: Record<string, any>;
}

/**
 * A list of artifacts with max items constraint.
 */
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

/** Schema version */
export const SCHEMA_VERSION = '1.0.0';
export const PACKAGE_VERSION = '1.0.0';
