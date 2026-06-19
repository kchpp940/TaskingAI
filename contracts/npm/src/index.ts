// @taskingai/contracts
// Shared contracts for TaskingAI frontend
// This package is self-contained - no Python or external repo dependencies required.

export {
  // Types
  ArtifactType,
  Artifact,
  ArtifactList,
  MessageContent,
  Message,
  isArtifactType,
  ARTIFACT_TYPES,

  // Constants
  ARTIFACT_CONSTANTS,
  MAX_ARTIFACT_CONTENT_LENGTH,
  MAX_ARTIFACT_TITLE_LENGTH,
  MAX_ARTIFACTS_PER_TOOL,
  DEFAULT_MIME_TYPES,
  MIME_TYPE_MAP,

  // Schema info
  SCHEMA_VERSION,
  PACKAGE_VERSION,
} from './artifact/types';

// Runtime validators
export {
  validateArtifact,
  validateArtifactList,
  loadSchema,
  getSchemaVersion,
  ValidationResult,
} from './artifact/validator';

export { validateArtifact as validate_artifact } from './artifact/validator';
export { validateArtifactList as validate_artifact_list } from './artifact/validator';
export { loadSchema as load_schema } from './artifact/validator';
export { getSchemaVersion as get_schema_version } from './artifact/validator';

import * as ArtifactTypes from './artifact/types';
import * as ArtifactValidator from './artifact/validator';

export { ArtifactTypes, ArtifactValidator };
