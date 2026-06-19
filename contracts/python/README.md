# taskingai-contracts

Shared contracts and schemas for TaskingAI services.

This package provides:
- Shared JSON Schema definitions (embedded in package)
- Runtime validators for artifact protocol
- Constants and helper utilities
- Code generators for type synchronization

## Installation

```bash
# Install as editable package (development)
pip install -e contracts/python

# Or install from local path in requirements.txt:
# -e ../contracts/python
```

## Usage

```python
# Validate artifacts at runtime
from taskingai_contracts.artifact import validate_artifact, validate_artifact_list

# Load schema and constants
from taskingai_contracts.artifact import (
    load_schema,
    get_schema_version,
    get_constants,
    ArtifactType,
    MAX_ARTIFACT_CONTENT_LENGTH,
    MAX_ARTIFACT_TITLE_LENGTH,
    MAX_ARTIFACTS_PER_TOOL,
)

# Generate type definitions for backend/plugin/frontend
from taskingai_contracts.artifact.generator import generate_all
generate_all()
```
