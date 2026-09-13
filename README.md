# Warden

Warden is a self-hosted AI code review and coding agent orchestration system.

See the [architecture and implementation specifications](design/) for the
project design and delivery plan.

Copy [`.env.example`](.env.example) to `.env` when local configuration is
introduced by later specifications.

## Repository scaffold

```text
services/
	api-gateway/
	coding-agent/
	model-gateway/
	review-engine/
	workspace-provisioner/
packages/
	agent-core/
	common/
	datasource-connectors/
	github-integration/
infra/
	compose/
	docker/
```

Each service and package has its own `pyproject.toml` and belongs to the root
`uv` workspace. Each service also has a placeholder Python 3.12 `Dockerfile`.
Business logic, application entry points, and Compose orchestration are added
by later specifications.

## Development

This repository uses `uv` for Python workspace and dependency management.
Install Python 3.12 and the development dependencies with:

```console
uv python install 3.12
uv sync --all-packages
```

Run all unit tests from the repository root with:

```console
uv run --all-packages pytest -m unit
```

Run Docker-backed PostgreSQL integration tests with:

```console
uv run --package warden-common pytest packages/common/tests -m integration
```

Run the `common` package tests with coverage and show uncovered lines with:

```console
uv run --package warden-common --with pytest-cov pytest packages/common/tests -m unit --cov=common --cov-report=term-missing
```

Replace `--cov-report=term-missing` with `--cov-report=html` to generate a
browsable report in `htmlcov/index.html`.

Run the remaining repository checks with:

```console
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pre-commit run --all-files
```

## Docker service scaffolds

Build each placeholder service image from the repository root:

```console
docker build -t warden-review-engine:scaffold services/review-engine
docker build -t warden-coding-agent:scaffold services/coding-agent
docker build -t warden-workspace-provisioner:scaffold services/workspace-provisioner
docker build -t warden-model-gateway:scaffold services/model-gateway
docker build -t warden-api-gateway:scaffold services/api-gateway
```

The scaffold images do not run application servers yet. Run the Python version
command in each container to verify that every image starts successfully:

```console
docker run --rm warden-review-engine:scaffold python --version
docker run --rm warden-coding-agent:scaffold python --version
docker run --rm warden-workspace-provisioner:scaffold python --version
docker run --rm warden-model-gateway:scaffold python --version
docker run --rm warden-api-gateway:scaffold python --version
```
