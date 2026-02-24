# Default recipe - list available commands
default:
    @just --list

# Run all tests
test *args:
    PYTHONPATH=shared python3 -m pytest tests/ {{args}}

# Lint code
lint:
    python3 -m ruff check shared/cli/ tests/

# Format code
format:
    python3 -m ruff format shared/cli/ tests/

# Type check
typecheck:
    python3 -m mypy shared/cli/

# Run all checks
check: format lint typecheck test

# List all specs
spec-list root='.do':
    PYTHONPATH=shared python3 -m cli spec list --root {{root}}

# Register a spec contract
spec-register root='.do' id='' type='execute' json='':
    PYTHONPATH=shared python3 -m cli spec register --root {{root}} --id {{id}} --type {{type}} --json '{{json}}'

# Run spec preflight
preflight root='.do':
    PYTHONPATH=shared python3 -m cli spec preflight --root {{root}}

# Archive ephemeral state
archive root='.do':
    PYTHONPATH=shared python3 -m cli archive --root {{root}}

# Count specs
spec-count root='.do':
    PYTHONPATH=shared python3 -m cli spec count --root {{root}}

# Check spec divergence against a document
divergence root='.do' spec_doc='spec.md':
    PYTHONPATH=shared python3 -m cli spec divergence --root {{root}} --spec-doc {{spec_doc}}

# Spec coverage analysis for given IDs
spec-coverage root='.do' ids='':
    PYTHONPATH=shared python3 -m cli spec coverage --root {{root}} --ids {{ids}}

# Execution coverage analysis
execution-coverage plan_json='' spec_json='':
    PYTHONPATH=shared python3 -m cli plan execution-coverage --plan-json {{plan_json}} --spec-json {{spec_json}}

# Resolve a reflection
reflection-resolve root='.do' id='' resolution='':
    PYTHONPATH=shared python3 -m cli reflection resolve --root {{root}} --id {{id}} --resolution '{{resolution}}'
