"""
Prompt loader and manager.
Loads prompts from YAML configuration and provides formatting utilities.
"""

import yaml
from typing import Dict, Any, Optional
from pathlib import Path

from config.settings import get_settings


settings = get_settings()


class PromptsManager:
    """Manages loading and formatting of prompts from YAML config."""

    def __init__(self, prompts_file: Optional[str] = None):
        self.prompts_file = prompts_file or settings.prompts_file
        self.prompts: Dict[str, Any] = {}
        self.load_prompts()

    def load_prompts(self):
        """Load prompts from YAML file."""
        prompts_path = Path(self.prompts_file)

        if not prompts_path.exists():
            raise FileNotFoundError(f"Prompts file not found: {self.prompts_file}")

        with open(prompts_path, 'r', encoding='utf-8') as f:
            self.prompts = yaml.safe_load(f)

    def reload(self):
        """Reload prompts from file (for hot-reloading)."""
        self.load_prompts()

    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        """Get formatted base system prompt."""
        template = self.prompts["system_prompts"]["base"]
        return template.format(**context)

    def get_skill_prompt(self, skill: str, context: Dict[str, Any]) -> str:
        """Get formatted skill-specific system prompt."""
        skill_prompts = self.prompts["skill_prompts"]

        if skill not in skill_prompts:
            raise ValueError(f"Unknown skill: {skill}")

        template = skill_prompts[skill]["system"]
        return template.format(**context)

    def get_skill_step_prompt(self, skill: str, step: str) -> str:
        """Get prompt for a specific step in a skill."""
        skill_prompts = self.prompts["skill_prompts"]

        if skill not in skill_prompts:
            raise ValueError(f"Unknown skill: {skill}")

        steps = skill_prompts[skill].get("steps", {})
        if step not in steps:
            raise ValueError(f"Unknown step '{step}' for skill '{skill}'")

        return steps[step]

    def get_coping_technique(self, technique: str) -> str:
        """Get coping technique instructions."""
        techniques = self.prompts["skill_prompts"]["coping"]["techniques"]

        if technique not in techniques:
            raise ValueError(f"Unknown coping technique: {technique}")

        return techniques[technique]

    def get_psychoeducation_card(self, topic: str) -> str:
        """Get psychoeducation content."""
        cards = self.prompts["skill_prompts"]["psychoeducation"]["cards"]

        if topic not in cards:
            raise ValueError(f"Unknown psychoeducation topic: {topic}")

        return cards[topic]

    def get_refusal_template(self, refusal_type: str) -> str:
        """Get refusal message template."""
        templates = self.prompts["refusal_templates"]

        if refusal_type not in templates:
            raise ValueError(f"Unknown refusal type: {refusal_type}")

        return templates[refusal_type]

    def get_risk_keywords(self, level: str) -> list:
        """Get risk detection keywords for a level."""
        keywords = self.prompts["risk_detection"]["keywords"]

        if level not in keywords:
            raise ValueError(f"Unknown risk level: {level}")

        return keywords[level]

    def get_risk_escalation_message(self, message_type: str) -> str:
        """Get risk escalation flow message."""
        flow = self.prompts["risk_detection"]["escalation_flow"]

        if message_type not in flow:
            raise ValueError(f"Unknown escalation message: {message_type}")

        return flow[message_type]

    def get_crisis_resources(self, country_code: str = "default") -> Dict[str, str]:
        """Get crisis resources for a country."""
        resources = self.prompts["resources"]

        if country_code.lower() in resources:
            return resources[country_code.lower()]

        return resources["default"]

    def get_consent_message(self, country_code: str = "US") -> str:
        """Get consent/disclaimer message with localized resources."""
        template = self.prompts["conversation_flow"]["consent"]["message"]
        resources = self.get_crisis_resources(country_code)

        return template.format(**resources)

    def get_menu_message(self) -> str:
        """Get main menu message."""
        return self.prompts["conversation_flow"]["menu"]["message"]

    def get_risk_system_prompt(self) -> str:
        """Get system prompt for risk detection."""
        return self.prompts["risk_detection"]["system_prompt"]

    def format_with_resources(self, template: str, country_code: str) -> str:
        """Format a template with crisis resources."""
        resources = self.get_crisis_resources(country_code)
        return template.format(**resources)


# Global prompts manager instance
prompts_manager = PromptsManager()


def get_prompts() -> PromptsManager:
    """Get prompts manager instance."""
    return prompts_manager
