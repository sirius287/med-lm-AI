"""Local/operator diagnostics. Never include setting values or contact a provider."""

import json
from dataclasses import dataclass

from medlm_api.config import Settings


@dataclass(frozen=True)
class ConfigurationIssue:
    code: str
    variables: tuple[str, ...]
    capability: str

    def as_dict(self):
        return {"code": self.code, "variables": self.variables, "capability": self.capability}


def configuration_issues(settings: Settings) -> list[ConfigurationIssue]:
    groups = {
        "browser_authentication": (
            "database_url",
            "supabase_url",
            "supabase_publishable_key",
            "session_encryption_key",
            "auth_rate_limit_key",
        ),
        "manual_medications": ("database_url", "medication_encryption_key"),
    }
    issues = []
    for capability, names in groups.items():
        missing = tuple("MEDLM_" + name.upper() for name in names if not getattr(settings, name))
        if missing:
            issues.append(ConfigurationIssue("configuration_missing", missing, capability))
    if (
        settings.session_encryption_key
        and settings.medication_encryption_key
        and settings.session_encryption_key == settings.medication_encryption_key
    ):
        issues.append(
            ConfigurationIssue(
                "encryption_keys_must_differ",
                ("MEDLM_SESSION_ENCRYPTION_KEY", "MEDLM_MEDICATION_ENCRYPTION_KEY"),
                "manual_medications",
            )
        )
    return issues


def log_configuration(settings: Settings, logger) -> None:
    for issue in configuration_issues(settings):
        logger.warning(json.dumps({"event": "configuration", **issue.as_dict()}))
