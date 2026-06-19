// AUTO-GENERATED RE-EXPORT — DO NOT EDIT MANUALLY
//
// Source package: @taskingai/contracts v1.0.0
// Canonical schema: contracts/artifact/v1.0.json
//
// This file re-exports types from the shared @taskingai/contracts npm package.
// The actual definitions live in contracts/npm/src/artifact/types.ts and are
// embedded inside the published package. This keeps frontend independent —
// no Python or external contracts/ directory access is required for build.
//
// To regenerate: cd ../contracts/npm && npm run build

export {
  isArtifactType,
  ARTIFACT_TYPES,
  ARTIFACT_CONSTANTS,
  MAX_ARTIFACT_CONTENT_LENGTH,
  MAX_ARTIFACT_TITLE_LENGTH,
  MAX_ARTIFACTS_PER_TOOL,
  DEFAULT_MIME_TYPES,
  MIME_TYPE_MAP,
  SCHEMA_VERSION,
  PACKAGE_VERSION,
  validateArtifact,
  validateArtifactList,
  loadSchema,
  getSchemaVersion,
} from '@taskingai/contracts';

export type {
  ArtifactType,
  Artifact,
  ArtifactList,
  MessageContent,
  Message,
  ValidationResult,
} from '@taskingai/contracts';
