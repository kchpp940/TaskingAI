import * as fs from 'fs';
import * as path from 'path';

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');

function checkFileExists(filePath: string): boolean {
  try {
    fs.accessSync(filePath, fs.constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

function readJson(filePath: string): any {
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

function main(): number {
  console.log('Checking TaskingAI contracts consistency...\n');

  let failures = 0;

  const pySchema = path.join(REPO_ROOT, 'contracts', 'python', 'taskingai_contracts', 'artifact', 'schemas', 'v1.0.json');
  const npmSchema = path.join(REPO_ROOT, 'contracts', 'npm', 'src', 'artifact', 'schemas', 'v1.0.json');

  console.log('1. Checking schema files exist...');
  if (!checkFileExists(pySchema)) {
    console.error(`  ✗ Python schema not found: ${pySchema}`);
    failures++;
  } else {
    console.log(`  ✓ Python schema exists`);
  }
  if (!checkFileExists(npmSchema)) {
    console.error(`  ✗ NPM schema not found: ${npmSchema}`);
    failures++;
  } else {
    console.log(`  ✓ NPM schema exists`);
  }

  console.log('\n2. Checking schema consistency...');
  if (checkFileExists(pySchema) && checkFileExists(npmSchema)) {
    const pyContent = JSON.stringify(readJson(pySchema));
    const npmContent = JSON.stringify(readJson(npmSchema));
    if (pyContent === npmContent) {
      console.log('  ✓ Python and NPM schemas are identical');
    } else {
      console.error('  ✗ Python and NPM schemas are NOT identical');
      failures++;
    }
  }

  console.log('\n3. Checking Python package...');
  const pyToml = path.join(REPO_ROOT, 'contracts', 'python', 'pyproject.toml');
  if (checkFileExists(pyToml)) {
    console.log('  ✓ pyproject.toml exists');
  } else {
    console.error('  ✗ pyproject.toml not found');
    failures++;
  }

  const pyInit = path.join(REPO_ROOT, 'contracts', 'python', 'taskingai_contracts', '__init__.py');
  if (checkFileExists(pyInit)) {
    console.log('  ✓ __init__.py exists');
  } else {
    console.error('  ✗ __init__.py not found');
    failures++;
  }

  console.log('\n4. Checking NPM package...');
  const npmPkg = path.join(REPO_ROOT, 'contracts', 'npm', 'package.json');
  if (checkFileExists(npmPkg)) {
    console.log('  ✓ package.json exists');
  } else {
    console.error('  ✗ package.json not found');
    failures++;
  }

  const npmTs = path.join(REPO_ROOT, 'contracts', 'npm', 'src', 'index.ts');
  if (checkFileExists(npmTs)) {
    console.log('  ✓ src/index.ts exists');
  } else {
    console.error('  ✗ src/index.ts not found');
    failures++;
  }

  console.log(`\n${failures === 0 ? '✓ All checks passed!' : `✗ ${failures} check(s) failed`}`);
  return failures === 0 ? 0 : 1;
}

process.exit(main());
