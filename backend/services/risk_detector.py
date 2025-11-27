"""
Risk Detection Service - Hybrid keyword + LLM approach for safety.
Detects suicidal ideation, self-harm, psychosis, and other safety concerns.
"""

from typing import List, Dict, Optional
import json
import re

from models.schemas import RiskDetectionResult, RiskLevel
from services.llm_service import get_llm_service
from utils.prompts import get_prompts
from config.settings import get_settings


settings = get_settings()
prompts = get_prompts()
llm_service = get_llm_service()


class RiskDetector:
    """Detects risk in user messages using keyword matching + LLM analysis."""

    def __init__(self, llm_service=None):
        self.llm_service = llm_service or get_llm_service()
        self.high_risk_keywords = prompts.get_risk_keywords("high")
        self.medium_risk_keywords = prompts.get_risk_keywords("medium")

    async def detect_risk(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> RiskDetectionResult:
        """
        Detect risk level in a message.

        Args:
            message: User's message to analyze
            conversation_history: Previous messages for context

        Returns:
            RiskDetectionResult with level, reasoning, and actions
        """
        if not settings.risk_detection_enabled:
            return RiskDetectionResult(
                risk_level=RiskLevel.NONE,
                reasoning="Risk detection disabled",
                triggers=[],
                should_escalate=False,
                should_end_session=False
            )

        # Step 1: Keyword-based quick check
        detected_keywords = self._check_keywords(message)

        # Step 2: Determine if LLM analysis is needed
        # Only run LLM if:
        # - High-risk keywords detected OR
        # - Message is long enough (>50 chars) AND medium-risk keywords detected
        has_high_risk_keywords = any("HIGH:" in kw for kw in detected_keywords)
        has_medium_risk_keywords = any("MEDIUM:" in kw for kw in detected_keywords)
        message_long_enough = len(message.strip()) > 50

        # For very short messages without keywords, return NONE
        if not detected_keywords and len(message.strip()) < 20:
            return RiskDetectionResult(
                risk_level=RiskLevel.NONE,
                reasoning="Short conversational message",
                triggers=[],
                should_escalate=False,
                should_end_session=False
            )

        # Only escalate to LLM if keywords detected or message is substantial
        if has_high_risk_keywords:
            # Always analyze high-risk keywords with LLM
            llm_result = await self._llm_risk_analysis(
                message,
                detected_keywords,
                conversation_history
            )
            return llm_result
        elif has_medium_risk_keywords and message_long_enough:
            # Analyze medium-risk with context
            llm_result = await self._llm_risk_analysis(
                message,
                detected_keywords,
                conversation_history
            )
            return llm_result
        elif detected_keywords:
            # Keywords detected but not enough context - return LOW without escalation
            return RiskDetectionResult(
                risk_level=RiskLevel.LOW,
                reasoning="Keywords detected but context insufficient for escalation",
                triggers=[kw.split(":")[1] for kw in detected_keywords],
                should_escalate=False,
                should_end_session=False,
                confidence_score=0.4
            )
        else:
            # No keywords, normal conversation
            return RiskDetectionResult(
                risk_level=RiskLevel.NONE,
                reasoning="No risk indicators detected",
                triggers=[],
                should_escalate=False,
                should_end_session=False
            )

    def _check_keywords(self, message: str) -> List[str]:
        """Check for risk keywords in message (case-insensitive)."""
        message_lower = message.lower()
        detected = []

        # Check high-risk keywords
        for keyword in self.high_risk_keywords:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, message_lower):
                detected.append(f"HIGH:{keyword}")

        # Check medium-risk keywords
        for keyword in self.medium_risk_keywords:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, message_lower):
                detected.append(f"MEDIUM:{keyword}")

        return detected

    async def _llm_risk_analysis(
        self,
        message: str,
        detected_keywords: List[str],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> RiskDetectionResult:
        """Use LLM to analyze risk with context."""

        # Build context from conversation history
        context = ""
        if conversation_history:
            recent_messages = conversation_history[-5:]  # Last 5 messages
            context = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in recent_messages
            ])

        # Create analysis prompt
        system_prompt = prompts.get_risk_system_prompt()

        analysis_prompt = f"""
Detected keywords: {', '.join(detected_keywords)}

Recent conversation context:
{context}

Current user message:
"{message}"

Analyze this message for safety risk. Consider:
1. Intent (is there actual self-harm intent or just distress?)
2. Plan/means/timeline (specificity increases risk)
3. Context from conversation history
4. False positives (metaphors, song lyrics, quoting others)

Return ONLY valid JSON in this exact format:
{{"risk_level": "HIGH|MEDIUM|LOW", "reasoning": "brief explanation", "triggers": ["keyword1", "keyword2"]}}
"""

        try:
            # Use Claude for risk detection (more reliable for safety)
            response = await self.llm_service.risk_detection_response(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            # Parse JSON response
            result_json = self._extract_json(response.content)
            result_data = json.loads(result_json)

            risk_level = RiskLevel(result_data["risk_level"].lower())

            # Determine actions based on risk level
            should_escalate = risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]
            should_end_session = risk_level == RiskLevel.HIGH

            return RiskDetectionResult(
                risk_level=risk_level,
                reasoning=result_data["reasoning"],
                triggers=result_data.get("triggers", detected_keywords),
                should_escalate=should_escalate,
                should_end_session=should_end_session,
                confidence_score=0.9  # High confidence when LLM confirms
            )

        except Exception as e:
            # Fallback to conservative (safe) default if LLM fails
            print(f"Risk detection LLM error: {e}")

            # If high-risk keywords detected, assume HIGH risk (err on side of caution)
            has_high_risk = any("HIGH:" in kw for kw in detected_keywords)

            return RiskDetectionResult(
                risk_level=RiskLevel.HIGH if has_high_risk else RiskLevel.MEDIUM,
                reasoning="Fallback detection: LLM analysis failed, using keyword-based assessment",
                triggers=detected_keywords,
                should_escalate=True,
                should_end_session=has_high_risk,
                confidence_score=0.6
            )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        # Try to find JSON in markdown code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        # Try to find raw JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)

        # If no JSON found, return as-is and let json.loads fail
        return text

    def should_trigger_escalation(self, risk_level: RiskLevel) -> bool:
        """Determine if risk level should trigger escalation flow."""
        return risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]

    def should_end_session(self, risk_level: RiskLevel) -> bool:
        """Determine if risk level should end the session."""
        return risk_level == RiskLevel.HIGH


# Global risk detector instance
risk_detector = RiskDetector()


def get_risk_detector() -> RiskDetector:
    """Get risk detector instance."""
    return risk_detector
