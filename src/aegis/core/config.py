from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    root: str = "."


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["anthropic"] = "anthropic"
    models: dict[str, str] = Field(
        default_factory=lambda: {
            "pm": "claude-opus-4-6",
            "dev": "claude-sonnet-4-6",
            "qa": "claude-sonnet-4-6",
            "reviewer": "claude-opus-4-6",
            "docs": "claude-haiku-4-5",
        }
    )


class TaskBudgetDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usd: float = 2.00
    minutes: int = 30


class ParallelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max: int = 3


class BudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: TaskBudgetDefaults = Field(default_factory=TaskBudgetDefaults)
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["merge_only"] = "merge_only"
    auto_approve_docs: bool = True


class PMAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_subtasks: int = 8


class DevAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retries_on_qa_fail: int = 2


class QAAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fail_fast: bool = False


class ReviewerAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retries_on_rework: int = 1
    checklist_path: str | None = None


class DocsAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(
        default_factory=lambda: ["README.md", "CHANGELOG.md", "docs/"]
    )


class AgentsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pm: PMAgentConfig = Field(default_factory=PMAgentConfig)
    dev: DevAgentConfig = Field(default_factory=DevAgentConfig)
    qa: QAAgentConfig = Field(default_factory=QAAgentConfig)
    reviewer: ReviewerAgentConfig = Field(default_factory=ReviewerAgentConfig)
    docs: DocsAgentConfig = Field(default_factory=DocsAgentConfig)


class LangSmithConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    project: str | None = None


class LangfuseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    url: str = "http://localhost:3000"


class OtelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = "aegis"


class ObservabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    langsmith: LangSmithConfig = Field(default_factory=LangSmithConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
    otel: OtelConfig = Field(default_factory=OtelConfig)


class MCPServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    command: str
    env: dict[str, str] = Field(default_factory=dict)


class MCPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    servers: list[MCPServerConfig] = Field(
        default_factory=lambda: [
            MCPServerConfig(name="git", command="aegis-git-mcp"),
            MCPServerConfig(name="fs", command="aegis-fs-mcp"),
            MCPServerConfig(name="project-index", command="aegis-project-index-mcp"),
            MCPServerConfig(
                name="shell",
                command="aegis-shell-mcp",
                env={"ALLOW_CMDS": "pytest,python,pip,npm,pnpm,node,ruff,mypy"},
            ),
        ]
    )


class AegisConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    project: ProjectConfig
    llm: LLMConfig = Field(default_factory=LLMConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    gates: GatesConfig = Field(default_factory=GatesConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)


def default_config(project_name: str) -> AegisConfig:
    return AegisConfig(project=ProjectConfig(name=project_name))


def load_config(path: Path) -> AegisConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AegisConfig.model_validate(data)


def dump_config(config: AegisConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="python")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
