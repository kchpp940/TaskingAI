#!/usr/bin/env node
/**
 * Artifact Contract Consistency Check (Node.js / Frontend version)
 *
 * Validates that:
 *   1. Types in src/artifact/types.ts match the embedded JSON Schema
 *   2. Constants match the Schema
 *   3. ArtifactType enum values match the Schema
 *
 * This script runs WITHOUT Python or external contracts directory access.
 * Everything is self-contained within @taskingai/contracts npm package.
 *
 * Usage:
 *   node dist/check-contracts.js
 *   npm run check-contracts
 */

import { loadSchema, ARTIFACT_CONSTANTS, ARTIFACT_TYPES, SCHEMA_VERSION } from './index.js';

async function run(): Promise<void> {
  let allOk = true;

  function check(label: string, ok: boolean, detail?: string) {
    if (ok) {
      console.log(`  ✓ ${label}`);
    } else {
      console.log(`  ✗ ${label}${detail ? `: ${detail}` : ''}`);
      allOk = false;
    }
  }

  console.log('=== Artifact Contract Consistency Check (@taskingai/contracts) ===');
  console.log();

  // 1. Schema loads correctly
  console.log('--- Schema Loading ---');
  const schema = loadSchema();
  check('Embedded JSON Schema loads', !!schema && typeof schema === 'object');
  check(`Schema version matches (${SCHEMA_VERSION})`, schema?.version === SCHEMA_VERSION);
  console.log();

  // 2. Constants consistency
  console.log('--- Constants ---');
  const schemaConstants = schema?.properties?.constants?.properties || {};
  check(
    `MAX_ARTIFACT_CONTENT_LENGTH = ${ARTIFACT_CONSTANTS.MAX_ARTIFACT_CONTENT_LENGTH}`,
    schemaConstants.MAX_ARTIFACT_CONTENT_LENGTH?.const === ARTIFACT_CONSTANTS.MAX_ARTIFACT_CONTENT_LENGTH
  );
  check(
    `MAX_ARTIFACT_TITLE_LENGTH = ${ARTIFACT_CONSTANTS.MAX_ARTIFACT_TITLE_LENGTH}`,
    schemaConstants.MAX_ARTIFACT_TITLE_LENGTH?.const === ARTIFACT_CONSTANTS.MAX_ARTIFACT_TITLE_LENGTH
  );
  check(
    `MAX_ARTIFACTS_PER_TOOL = ${ARTIFACT_CONSTANTS.MAX_ARTIFACTS_PER_TOOL}`,
    schemaConstants.MAX_ARTIFACTS_PER_TOOL?.const === ARTIFACT_CONSTANTS.MAX_ARTIFACTS_PER_TOOL
  );
  console.log();

  // 3. ArtifactType enum consistency
  console.log('--- ArtifactType Enum ---');
  const schemaTypes: string[] = schema?.definitions?.ArtifactType?.enum || [];
  const schemaTypesSet = new Set(schemaTypes);
  const exportedTypesSet = new Set(ARTIFACT_TYPES);

  check(`Enum has ${schemaTypes.length} types`, schemaTypes.length === ARTIFACT_TYPES.length);
  schemaTypes.forEach((t: string) => {
    check(`Type '${t}' present in exports`, exportedTypesSet.has(t as any));
  });
  ARTIFACT_TYPES.forEach((t) => {
    check(`Exported type '${t}' present in schema`, schemaTypesSet.has(t));
  });
  console.log();

  // 4. Artifact schema required fields
  console.log('--- Artifact Schema Structure ---');
  const artifactSchema = schema?.definitions?.Artifact || {};
  const required = artifactSchema.required || [];
  check("Artifact has required fields: ['type', 'mime_type']",
    required.includes('type') && required.includes('mime_type'));
  const props = artifactSchema.properties || {};
  const expectedProps = ['type', 'mime_type', 'title', 'content', 'preview_url', 'download_url', 'size', 'metadata'];
  expectedProps.forEach((p) => {
    check(`Artifact property '${p}' defined`, !!props[p]);
  });
  console.log();

  // 5. Runtime validator smoke test
  console.log('--- Runtime Validator ---');
  try {
    const { validateArtifact, validateArtifactList } = await import('./index.js');

    const validArt = { type: 'text', mime_type: 'text/plain', title: 'OK' };
    const r1 = validateArtifact(validArt);
    check('Valid artifact passes validation', r1.valid);

    const invalidArt = { type: 'audio', mime_type: 'bad-mime' };
    const r2 = validateArtifact(invalidArt);
    check('Invalid artifact is rejected', !r2.valid && r2.errors.length > 0);

    const tooMany = Array.from({ length: 15 }, () => ({ type: 'text', mime_type: 'text/plain' }));
    const r3 = validateArtifactList(tooMany);
    check('Too many artifacts generates warning', !r3.valid && r3.errors.some((e: string) => e.includes('> 10')));
  } catch (e: any) {
    check('Runtime validator smoke test', false, String(e));
  }
  console.log();

  // Final result
  if (allOk) {
    console.log('✅ ALL CHECKS PASSED — @taskingai/contracts is internally consistent');
    process.exit(0);
  } else {
    console.log('❌ CHECKS FAILED — regenerate the package from the canonical JSON Schema');
    process.exit(1);
  }
}

run().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
