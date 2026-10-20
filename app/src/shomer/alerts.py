"""Alertmanager webhook payload (https://prometheus.io/docs/alerting/latest/configuration/#webhook_config)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Alert(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["firing", "resolved"]
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    starts_at: datetime = Field(alias="startsAt")
    ends_at: datetime | None = Field(default=None, alias="endsAt")
    generator_url: str = Field(default="", alias="generatorURL")
    fingerprint: str = ""

    @property
    def name(self) -> str:
        return self.labels.get("alertname", "UnknownAlert")

    @property
    def namespace(self) -> str | None:
        return self.labels.get("namespace")


class AlertmanagerPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str = "4"
    status: Literal["firing", "resolved"]
    receiver: str = ""
    group_key: str = Field(default="", alias="groupKey")
    alerts: list[Alert]
