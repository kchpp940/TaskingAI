import Ajv, { ValidateFunction } from 'ajv';
import schema from './schemas/v1.0.json';

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

let ajvInstance: Ajv | null = null;
let validateArtifactFn: ValidateFunction | null = null;
let validateArtifactListFn: ValidateFunction | null = null;

function getAjv(): Ajv {
  if (!ajvInstance) {
    ajvInstance = new Ajv({ allErrors: true });
  }
  return ajvInstance;
}

function getArtifactValidator(): ValidateFunction {
  if (!validateArtifactFn) {
    const ajv = getAjv();
    validateArtifactFn = ajv.compile((schema as any).definitions.Artifact);
  }
  return validateArtifactFn;
}

function getArtifactListValidator(): ValidateFunction {
  if (!validateArtifactListFn) {
    const ajv = getAjv();
    validateArtifactListFn = ajv.compile((schema as any).definitions.ArtifactList);
  }
  return validateArtifactListFn;
}

export function loadSchema(): any {
  return schema;
}

export function getSchemaVersion(): string {
  return (schema as any).version || 'unknown';
}

export function validateArtifact(artifact: unknown): ValidationResult {
  const validate = getArtifactValidator();
  const valid = validate(artifact);
  const errors = validate.errors
    ? validate.errors.map((e: any) => e.message || 'Unknown validation error')
    : [];
  return { valid: !!valid, errors };
}

export function validateArtifactList(artifacts: unknown[]): ValidationResult {
  const listValidate = getArtifactListValidator();
  const listValid = listValidate(artifacts);
  const allErrors: string[] = [];

  if (listValidate.errors) {
    listValidate.errors.forEach((e: any) => {
      allErrors.push(e.message || 'Unknown validation error');
    });
  }

  artifacts.forEach((artifact, i) => {
    const result = validateArtifact(artifact);
    if (!result.valid) {
      result.errors.forEach(error => {
        allErrors.push(`Artifact[${i}]: ${error}`);
      });
    }
  });

  return { valid: allErrors.length === 0, errors: allErrors };
}
