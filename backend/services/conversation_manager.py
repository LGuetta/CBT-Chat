"""
Conversation Manager - Adaptive conversation orchestration for Opzione C.

Replaces the rigid state machine with a flexible, context-aware conversation system
that adapts to patient needs based on distress level, therapist brief, and clinical context.
"""

import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from models.schemas import (
    TherapistBrief,
    DistressLevel,
    AlertLevel,
    RiskLevel,
    ConversationDecision,
    AdaptiveConversationContext,
    DistressAssessment,
    RiskDetectionResult,
    DisclaimerType,
)
from services.llm_service import LLMService
from services.risk_detector import RiskDetector
from services.distress_assessor import DistressAssessor


class ConversationManager:
    """
    Manages adaptive CBT conversations that respond to patient state rather than
    following fixed steps.

    Core responsibilities:
    1. Assess patient distress and risk
    2. Decide response mode (grounding, CBT work, clarification, crisis protocol)
    3. Build context-aware prompts using therapist brief
    4. Coordinate between services (LLM, risk detection, grounding)
    5. Track disclaimer/boundary reminders
    """

    # Disclaimer thresholds
    DISCLAIMER_MESSAGE_THRESHOLD = 20  # Show reminder every 20 messages
    DISCLAIMER_DEPENDENCY_THRESHOLD = 3  # Show if 3+ sessions in 24h

    def __init__(
        self,
        llm_service: LLMService,
        risk_detector: RiskDetector,
        distress_assessor: DistressAssessor,
        base_prompt: str
    ):
        """
        Initialize ConversationManager.

        Args:
            llm_service: LLM service for generating responses
            risk_detector: Risk detection service
            distress_assessor: Distress assessment service
            base_prompt: Base system prompt from prompt.txt
        """
        self.llm = llm_service
        self.risk_detector = risk_detector
        self.distress_assessor = distress_assessor
        self.base_prompt = base_prompt

    async def handle_message(
        self,
        message: str,
        context: AdaptiveConversationContext,
        therapist_brief: Optional[TherapistBrief] = None
    ) -> Dict:
        """
        Main entry point: handle patient message and generate response.

        Args:
            message: Patient's message
            context: Current conversation context
            therapist_brief: Patient-specific therapist brief

        Returns:
            Dict with response, risk_info, distress_info, disclaimer_shown, etc.
        """
        # 1. SAFETY FIRST - Risk detection
        risk_result = await self.risk_detector.detect_risk(
            message=message,
            conversation_history=context.history
        )

        # If HIGH or CRITICAL risk, activate crisis protocol
        if risk_result.risk_level in [RiskLevel.HIGH]:
            return await self._handle_crisis_protocol(
                message=message,
                context=context,
                risk_result=risk_result
            )

        # 2. ASSESS DISTRESS
        distress_assessment = self.distress_assessor.assess_distress(
            message=message,
            conversation_history=context.history,
            therapist_brief=therapist_brief
        )

        # Update context with distress level
        context.distress_level = distress_assessment.distress_level

        # 3. CHECK FOR GROUNDING NEED
        if distress_assessment.requires_grounding:
            should_ground, ground_message = self.distress_assessor.should_offer_grounding(
                distress_assessment=distress_assessment,
                grounding_count_this_session=context.grounding_count
            )

            if should_ground:
                return await self._offer_grounding(
                    message=message,
                    context=context,
                    distress_assessment=distress_assessment,
                    ground_message=ground_message,
                    therapist_brief=therapist_brief
                )

        # 4. CHECK FOR DISCLAIMER REMINDER
        disclaimer_to_show = self._should_show_disclaimer(context)
        disclaimer_content = None
        if disclaimer_to_show:
            disclaimer_content = self._get_disclaimer_content(disclaimer_to_show)

        # 5. DECIDE RESPONSE MODE
        decision = self._make_conversation_decision(
            message=message,
            context=context,
            distress_assessment=distress_assessment,
            therapist_brief=therapist_brief
        )

        # 6. BUILD ADAPTIVE PROMPT
        system_prompt = self._build_adaptive_prompt(
            therapist_brief=therapist_brief,
            context=context,
            distress_level=distress_assessment.distress_level,
            decision=decision
        )

        # 7. GENERATE RESPONSE
        messages = [{"role": "system", "content": system_prompt}] + context.history + [{"role": "user", "content": message}]
        llm_response = await self.llm.generate_response(
            messages=messages,
            provider="deepseek"  # Primary LLM
        )

        # 8. PREPARE RESPONSE
        response_content = llm_response.content

        # Prepend disclaimer if needed
        if disclaimer_content:
            response_content = disclaimer_content + "\n\n---\n\n" + response_content
            context.disclaimer_shown_count += 1
            context.last_disclaimer_at = datetime.now()

        # Update context history
        context.history.append({"role": "user", "content": message})
        context.history.append({"role": "assistant", "content": response_content})

        return {
            "response": response_content,
            "risk_detection": {
                "level": risk_result.risk_level.value,
                "reasoning": risk_result.reasoning,
                "should_escalate": risk_result.should_escalate,
                "triggers": risk_result.triggers
            },
            "distress_assessment": {
                "level": distress_assessment.distress_level.value,
                "reasoning": distress_assessment.reasoning,
                "signals_detected": distress_assessment.signals_detected
            },
            "conversation_decision": {
                "mode": decision.response_mode,
                "technique": decision.technique_to_apply,
                "reasoning": decision.reasoning
            },
            "disclaimer_shown": disclaimer_to_show is not None,
            "disclaimer_type": disclaimer_to_show.value if disclaimer_to_show else None,
            "should_end_session": risk_result.should_end_session,
            "model_used": llm_response.model_used,
            "tokens_used": llm_response.tokens_used
        }

    async def _handle_crisis_protocol(
        self,
        message: str,
        context: AdaptiveConversationContext,
        risk_result: RiskDetectionResult
    ) -> Dict:
        """
        Handle HIGH risk situation with crisis protocol.

        Returns immediate response with resources and session termination.
        """
        # Get country-specific crisis resources
        resources = self._get_crisis_resources(context.country_code)
        emergency_number = self._get_emergency_number(context.country_code)

        crisis_response = f"""I'm really concerned about what you've shared. Your safety is the most important thing right now.

**I need you to know:**
- I'm not equipped to handle crisis situations
- You need immediate support from trained professionals
- This is not something to handle alone

**Please contact one of these resources right now:**

{resources}

If you're in immediate danger, please call emergency services ({emergency_number}) or go to your nearest emergency room.

If you have a therapist, please reach out to them as soon as possible.

I'm going to pause our session here because your safety comes first. This is the right step."""

        context.history.append({"role": "user", "content": message})
        context.history.append({"role": "assistant", "content": crisis_response})

        return {
            "response": crisis_response,
            "risk_detection": {
                "level": risk_result.risk_level.value,
                "reasoning": risk_result.reasoning,
                "should_escalate": True,
                "triggers": risk_result.triggers
            },
            "distress_assessment": {
                "level": DistressLevel.CRISIS.value,
                "reasoning": "Crisis protocol activated due to high risk",
                "signals_detected": risk_result.triggers
            },
            "conversation_decision": {
                "mode": "crisis_protocol",
                "technique": None,
                "reasoning": "High risk detected - immediate intervention required"
            },
            "disclaimer_shown": False,
            "disclaimer_type": None,
            "should_end_session": True,
            "crisis_resources": resources,
            "alert_level": AlertLevel.CRITICAL.value
        }

    async def _offer_grounding(
        self,
        message: str,
        context: AdaptiveConversationContext,
        distress_assessment: DistressAssessment,
        ground_message: str,
        therapist_brief: Optional[TherapistBrief]
    ) -> Dict:
        """
        Offer grounding exercise before continuing conversation.

        Returns response that offers grounding in a gentle, collaborative way.
        """
        # Get suggested grounding exercise
        technique = distress_assessment.grounding_technique_suggested or "breathing"
        grounding_exercise = self.distress_assessor.get_grounding_exercise(
            technique=technique,
            therapist_brief=therapist_brief
        )

        # Format the offer
        response = f"""{ground_message}

{grounding_exercise.instructions}"""

        context.history.append({"role": "user", "content": message})
        context.history.append({"role": "assistant", "content": response})

        # Increment grounding count
        context.grounding_count += 1

        return {
            "response": response,
            "risk_detection": {
                "level": RiskLevel.NONE.value,
                "reasoning": "No risk detected",
                "should_escalate": False,
                "triggers": []
            },
            "distress_assessment": {
                "level": distress_assessment.distress_level.value,
                "reasoning": distress_assessment.reasoning,
                "signals_detected": distress_assessment.signals_detected
            },
            "conversation_decision": {
                "mode": "grounding",
                "technique": technique,
                "reasoning": "Grounding offered due to elevated distress"
            },
            "disclaimer_shown": False,
            "disclaimer_type": None,
            "should_end_session": False,
            "grounding_offered": True,
            "grounding_technique": technique
        }

    def _make_conversation_decision(
        self,
        message: str,
        context: AdaptiveConversationContext,
        distress_assessment: DistressAssessment,
        therapist_brief: Optional[TherapistBrief]
    ) -> ConversationDecision:
        """
        Decide how to respond based on message, context, and patient state.

        Returns:
            ConversationDecision with response mode and technique
        """
        message_lower = message.lower()

        # If patient is asking for specific CBT skill
        if any(keyword in message_lower for keyword in ["thought record", "challenge", "evidence"]):
            return ConversationDecision(
                response_mode="cbt_skill",
                distress_level=distress_assessment.distress_level,
                technique_to_apply="cognitive_restructuring",
                reasoning="Patient requesting cognitive restructuring"
            )

        if any(keyword in message_lower for keyword in ["activity", "do something", "action"]):
            return ConversationDecision(
                response_mode="cbt_skill",
                distress_level=distress_assessment.distress_level,
                technique_to_apply="behavioral_activation",
                reasoning="Patient interested in behavioral activation"
            )

        if any(keyword in message_lower for keyword in ["exposure", "face", "confront"]):
            # Check if exposure is contraindicated
            if therapist_brief and "exposure" in therapist_brief.contraindications:
                return ConversationDecision(
                    response_mode="gentle_redirect",
                    distress_level=distress_assessment.distress_level,
                    technique_to_apply=None,
                    reasoning="Exposure contraindicated by therapist brief"
                )
            return ConversationDecision(
                response_mode="cbt_skill",
                distress_level=distress_assessment.distress_level,
                technique_to_apply="exposure",
                reasoning="Patient exploring exposure work"
            )

        # If patient is sharing a triggering situation
        if any(keyword in message_lower for keyword in ["happened", "today", "this morning", "just now", "triggered"]):
            return ConversationDecision(
                response_mode="clarification",
                distress_level=distress_assessment.distress_level,
                technique_to_apply="situation_exploration",
                reasoning="Patient describing triggering event - explore before choosing skill"
            )

        # If moderate/low distress and no specific request, offer collaborative options
        if distress_assessment.distress_level in [DistressLevel.NONE, DistressLevel.MILD]:
            return ConversationDecision(
                response_mode="collaborative_menu",
                distress_level=distress_assessment.distress_level,
                technique_to_apply=None,
                reasoning="Low distress - offer collaborative skill selection"
            )

        # Default: clarify what the patient needs
        return ConversationDecision(
            response_mode="clarification",
            distress_level=distress_assessment.distress_level,
            technique_to_apply=None,
            reasoning="Unclear request - gentle exploration needed"
        )

    def _build_adaptive_prompt(
        self,
        therapist_brief: Optional[TherapistBrief],
        context: AdaptiveConversationContext,
        distress_level: DistressLevel,
        decision: ConversationDecision
    ) -> str:
        """
        Build context-aware system prompt incorporating therapist brief and patient state.

        This is where the magic happens - the prompt adapts to:
        - Therapist's preferred techniques and language
        - Patient's current distress level
        - Clinical sensitivities and contraindications
        - Current conversation focus
        """
        # Start with base prompt from prompt.txt
        prompt = self.base_prompt + "\n\n"

        # Add THERAPIST_BRIEF section if available
        if therapist_brief:
            prompt += self._format_therapist_brief_section(therapist_brief)

        # Get country-specific resources for LLM context
        emergency_number = self._get_emergency_number(context.country_code)
        crisis_resources = self._get_crisis_resources(context.country_code)

        # Add CURRENT PATIENT STATE section
        prompt += f"""
---

CURRENT PATIENT STATE:

**Distress Level:** {distress_level.value}
**Patient Name:** {context.user_name or "the patient"}
**Patient Country:** {context.country_code.upper() if context.country_code else "US"}
**Session Goal:** {context.session_goal or "Not specified"}
**Messages This Session:** {len(context.history) // 2}
**Grounding Used:** {context.grounding_count} times

**IMPORTANT - Use these EXACT crisis resources for this patient's country:**
{crisis_resources}
Emergency Number: {emergency_number}

When mentioning crisis resources or emergency numbers, ALWAYS use the resources listed above, NOT generic US numbers.

"""

        # Add conversation mode guidance
        if decision.response_mode == "grounding":
            prompt += """
**CURRENT MODE: GROUNDING**
Focus on guiding the patient through the grounding exercise. Be gentle, paced, and non-rushed.
"""
        elif decision.response_mode == "cbt_skill":
            prompt += f"""
**CURRENT MODE: CBT SKILL - {decision.technique_to_apply}**
The patient is ready for active CBT work. Use the technique: {decision.technique_to_apply}.
Stay aligned with the therapist's preferred approach.
"""
        elif decision.response_mode == "clarification":
            prompt += """
**CURRENT MODE: EXPLORATION**
The patient is describing a situation. Listen, clarify, and help identify thoughts/emotions/behaviors
before choosing a specific skill.
"""
        elif decision.response_mode == "collaborative_menu":
            prompt += """
**CURRENT MODE: COLLABORATIVE SKILL SELECTION**
The patient is regulated. Offer a few CBT options that match the therapist's preferences
and let them choose what feels most helpful right now.
"""

        # Add clinical reminders
        prompt += """
**REMEMBER:**
- You are a skills coach, NOT a therapist
- Encourage bringing insights back to their therapist
- If unsure, ask clarifying questions
- Validate feelings, then gently guide toward skills
"""

        return prompt

    def _format_therapist_brief_section(self, brief: TherapistBrief) -> str:
        """Format therapist brief into prompt section."""
        section = "THERAPIST_BRIEF:\n\n"

        if brief.case_formulation:
            section += f"**Case Formulation:**\n{brief.case_formulation}\n\n"

        if brief.presenting_problems:
            section += f"**Presenting Problems:** {', '.join(brief.presenting_problems)}\n\n"

        if brief.treatment_goals:
            section += f"**Treatment Goals:**\n"
            for goal in brief.treatment_goals:
                section += f"- {goal}\n"
            section += "\n"

        section += f"**Therapy Stage:** {brief.therapy_stage.value}\n\n"

        # Preferred techniques
        techniques = [k for k, v in brief.preferred_techniques.dict().items() if v]
        if techniques:
            section += f"**Preferred Techniques:** {', '.join(techniques)}\n\n"

        # Sensitivities
        if brief.sensitivities.trauma_history or brief.sensitivities.topics_to_avoid:
            section += "**Clinical Sensitivities:**\n"
            if brief.sensitivities.trauma_history:
                section += f"- Trauma History: {brief.sensitivities.trauma_history}\n"
            if brief.sensitivities.pacing:
                section += f"- Pacing: {brief.sensitivities.pacing}\n"
            if brief.sensitivities.topics_to_avoid:
                section += f"- Topics to Avoid: {', '.join(brief.sensitivities.topics_to_avoid)}\n"
            section += "\n"

        # Therapist language
        if brief.therapist_language.metaphors or brief.therapist_language.coping_statements:
            section += "**Therapist's Language (use these with patient):**\n"
            if brief.therapist_language.metaphors:
                section += f"- Metaphors: {', '.join(brief.therapist_language.metaphors)}\n"
            if brief.therapist_language.coping_statements:
                section += f"- Coping Statements: {', '.join(brief.therapist_language.coping_statements)}\n"
            section += "\n"

        # Contraindications
        if brief.contraindications:
            section += f"**DO NOT:**\n"
            for item in brief.contraindications:
                section += f"- {item}\n"
            section += "\n"

        return section

    def _should_show_disclaimer(self, context: AdaptiveConversationContext) -> Optional[DisclaimerType]:
        """
        Determine if a boundary reminder/disclaimer should be shown.

        Returns DisclaimerType if reminder needed, None otherwise.
        """
        message_count = len(context.history) // 2

        # Show periodic reminder every N messages
        if message_count > 0 and message_count % self.DISCLAIMER_MESSAGE_THRESHOLD == 0:
            # Don't show if we just showed one recently
            if context.last_disclaimer_at:
                minutes_since = (datetime.now() - context.last_disclaimer_at).seconds / 60
                if minutes_since < 10:
                    return None
            return DisclaimerType.PERIODIC_REMINDER

        # Show therapy referral reminder if patient seems very engaged/dependent
        # (This would be enhanced with more sophisticated detection)
        if message_count > 30 and context.disclaimer_shown_count < 2:
            return DisclaimerType.THERAPY_REFERRAL

        return None

    def _get_disclaimer_content(self, disclaimer_type: DisclaimerType) -> str:
        """Get disclaimer message content by type."""
        if disclaimer_type == DisclaimerType.PERIODIC_REMINDER:
            return """**Reminder:** I'm here to help you practice CBT skills between therapy sessions. I'm not a replacement for your therapist or for professional treatment. If you're working on something important or confusing, please bring it up with your therapist."""

        elif disclaimer_type == DisclaimerType.THERAPY_REFERRAL:
            return """**Important Note:** I'm glad this is helpful! Remember that I'm a skills practice tool, not a therapist. The insights and patterns you're discovering here are valuable to discuss with your therapist, who can provide the clinical guidance and deeper work you need."""

        elif disclaimer_type == DisclaimerType.CRISIS_BOUNDARY:
            return """**Important:** If you're in crisis or having thoughts of harming yourself or others, please contact a crisis helpline or emergency services immediately. I'm not equipped to provide crisis support."""

        return ""

    def _get_crisis_resources(self, country_code: str) -> str:
        """Get country-specific crisis resources."""
        code = country_code.upper() if country_code else "US"
        
        resources_map = {
            "US": """
**US Crisis Resources:**
- **988 Suicide & Crisis Lifeline:** Call or text 988
- **Crisis Text Line:** Text "HELLO" to 741741
- **Emergency Services:** 911
""",
            "UK": """
**UK Crisis Resources:**
- **Samaritans:** 116 123 (24/7)
- **Crisis Text Line:** Text "SHOUT" to 85258
- **Emergency Services:** 999
""",
            "IT": """
**Risorse di Crisi Italia:**
- **Telefono Amico Italia:** 800 86 00 22 (gratuito, 24/7)
- **Telefono Azzurro:** 19696
- **WhatsApp Telefono Amico:** 324 011 72 52
- **Emergenze:** 112
""",
            "DE": """
**Deutsche Krisenressourcen:**
- **Telefonseelsorge:** 0800 111 0 111 (kostenlos, 24/7)
- **Kinder & Jugendliche:** 116 111
- **Notruf:** 112
""",
            "FR": """
**Ressources de Crise France:**
- **SOS Amitié:** 09 72 39 40 50
- **Fil Santé Jeunes:** 0 800 235 236
- **Urgences:** 15 ou 112
""",
            "ES": """
**Recursos de Crisis España:**
- **Teléfono de la Esperanza:** 717 003 717
- **Emergencias:** 112
""",
            "CH": """
**Schweizer Krisenressourcen:**
- **Die Dargebotene Hand:** 143
- **Pro Juventute (Jugendliche):** 147
- **Notruf:** 112
""",
            "AT": """
**Österreichische Krisenressourcen:**
- **Telefonseelsorge:** 142 (24/7)
- **Rat auf Draht (Jugendliche):** 147
- **Notruf:** 112
""",
            "NL": """
**Nederlandse Crisislijnen:**
- **113 Zelfmoordpreventie:** 113 of 0800-0113
- **Chat:** 113.nl
- **Noodnummer:** 112
""",
            "BE": """
**Belgische Crisisdiensten:**
- **Zelfmoordlijn:** 1813
- **Centre de Prévention du Suicide:** 0800 32 123
- **Noodnummer:** 112
""",
        }

        return resources_map.get(code, resources_map["US"])
    
    def _get_emergency_number(self, country_code: str) -> str:
        """Get the primary emergency number for a country."""
        code = country_code.upper() if country_code else "US"
        numbers = {
            "US": "911",
            "UK": "999",
            "IT": "112",
            "DE": "112",
            "FR": "15 o 112",
            "ES": "112",
            "CH": "112",
            "AT": "112",
            "NL": "112",
            "BE": "112",
        }
        return numbers.get(code, "112")
