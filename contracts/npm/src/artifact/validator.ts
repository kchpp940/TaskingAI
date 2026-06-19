// AUTO-GENERATED - DO NOT EDIT MANUALLY
// Package: @taskingai/contracts v1.0.0

import Ajv, { ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';
import artifactSchema from './schemas/v1.0.json';
import type { Artifact, ArtifactList } from './types';
import { ARTIFACT_CONSTANTS } from './types';

let ajv: Ajv | null = null;
let artifactValidator: ValidateFunction | null = null;
let artifactListValidator: ValidateFunction | null = null;

function getAjv(): Ajv {
  if (!ajv) {
    // strict = false allows non-schema properties like mimeTypeMap which has string values
    ajv = new Ajv({ allErrors: true, strict: false, strictSchema: false, strictTypes: false, strictTuples: false });
    addFormats(ajv);
  }
  return ajv;
}

function getArtifactValidator(): ValidateFunction {
  if (!artifactValidator) {
    const schema = artifactSchema as any;
    // Directly compile the Artifact definition with definitions injected to resolve $ref
    const artifactDef = JSON.parse(JSON.stringify(schema.definitions.Artifact));
    artifactDef.definitions = schema.definitions;
    artifactValidator = getAjv().compile(artifactDef);
  }
  return artifactValidator;
}

function getArtifactListValidator(): ValidateFunction {
  if (!artifactListValidator) {
    const schema = artifactSchema as any;
    const listDef = JSON.parse(JSON.stringify(schema.definitions.ArtifactList));
    listDef.definitions = schema.definitions;
    artifactListValidator = getAjv().compile(listDef);
  }
  return artifactListValidator;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Validate a single artifact object against the embedded JSON Schema.
 * Returns { valid, errors } tuple.
 */
export function validateArtifact(artifact: unknown): ValidationResult {
  const validator = getArtifactValidator();
  const valid = validator(artifact) as boolean;
  return {
    valid,
    errors: valid ? [] : validator.errors?.map((e: any) => e.message || JSON.stringify(e)) || [],
  };
}

/**
 * Validate a list of artifacts against the embedded JSON Schema.
 * Also checks the max items constraint (10 by default).
 */
export function validateArtifactList(artifacts: unknown[]): ValidationResult {
  const allErrors: string[] = [];

  // Validate each artifact individually first (gives better error messages)
  artifacts.forEach((art, i) => {
    const result = validateArtifact(art);
    if (!result.valid) {
      result.errors.forEach((err) => allErrors.push(`Artifact[${i}]: ${err}`));
    }
  });

  // Also validate as a list (enforces maxItems)
  const listValidator = getArtifactListValidator();
  const listValid = listValidator(artifacts) as boolean;
  if (!listValid) {
    listValidator.errors?.forEach((e: any) => {
      if (e.message && e.keyword === 'maxItems') {
        allErrors.push(
          `Too many artifacts: ${artifacts.length} > ${ARTIFACT_CONSTANTS.MAX_ARTIFACTS_PER_TOOL}. ` +
          `Only first ${ARTIFACT_CONSTANTS.MAX_ARTIFACTS_PER_TOOL} will be kept.`
        );
      }
    });
  }

  return {
    valid: allErrors.length === 0,
    errors: allErrors,
  };
}

/**
 * Load and return the full embedded JSON Schema object.
 */
export function loadSchema(): any {
  return artifactSchema;
}

/**
 * Get the schema version string.
 */
export function getSchemaVersion(): string {
  return (artifactSchema as any).version || 'unknown';
}
