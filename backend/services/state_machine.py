"""
CBT State Machine - Manages conversation flows for CBT skills.
Implements state transitions and skill-specific logic.
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from models.schemas import (
    ConversationContext,
    ConversationState,
    SkillType,
    RiskLevel
)
from services.llm_service import get_llm_service
from utils.prompts import get_prompts
from utils.database import get_db


llm_service = get_llm_service()
prompts = get_prompts()
db = get_db()


class StateMachine:
    """Manages conversation state and skill flows."""

    def __init__(self):
        self.state_handlers = {
            ConversationState.CONSENT: self._handle_consent,
            ConversationState.INTAKE: self._handle_intake,
            ConversationState.MENU: self._handle_menu,
            ConversationState.THOUGHT_RECORD: self._handle_thought_record,
            ConversationState.BEHAVIORAL_ACTIVATION: self._handle_behavioral_activation,
            ConversationState.EXPOSURE: self._handle_exposure,
            ConversationState.COPING: self._handle_coping,
            ConversationState.LEARN: self._handle_learn,
        }

    async def process_message(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """
        Process a user message based on current state.

        Args:
            context: Current conversation context
            user_message: User's message

        Returns:
            Tuple of (assistant_response, updated_context)
        """
        handler = self.state_handlers.get(context.current_state)

        if not handler:
            # Default fallback
            return await self._handle_unknown_state(context, user_message)

        return await handler(context, user_message)

    # ========================================================================
    # STATE HANDLERS
    # ========================================================================

    async def _handle_consent(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Handle consent/disclaimer state."""

        # Check if this is the first message (show consent)
        if len(context.history) == 0:
            consent_message = prompts.get_consent_message(context.country_code)
            context.history.append({"role": "assistant", "content": consent_message})
            return consent_message, context

        # Check for agreement
        user_lower = user_message.lower().strip()

        if any(word in user_lower for word in ["yes", "agree", "i do", "understand", "ok", "sure"]):
            # Move to intake
            context.current_state = ConversationState.INTAKE
            context.state_data["consent_given"] = True
            context.state_data["intake_step"] = 0

            intake_questions = prompts.prompts["conversation_flow"]["intake"]["questions"]
            first_question = intake_questions[0]

            return first_question, context

        elif any(word in user_lower for word in ["no", "disagree", "don't agree"]):
            # User declined
            response = (
                "I understand. This tool isn't right for everyone. "
                "If you need support, please contact a licensed therapist or crisis line. "
                "Take care! 👋"
            )
            context.current_state = ConversationState.ENDED
            return response, context

        else:
            # Ask for clarification
            response = "Please respond with 'Yes' if you understand and agree, or 'No' if you don't wish to continue."
            return response, context

    async def _handle_intake(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Handle intake questions."""

        intake_questions = prompts.prompts["conversation_flow"]["intake"]["questions"]
        current_step = context.state_data.get("intake_step", 0)

        # Store the answer
        if current_step == 0:
            context.session_goal = user_message
            context.state_data["session_goal"] = user_message
        elif current_step == 1:
            context.state_data["communication_style"] = user_message
        elif current_step == 2:
            context.state_data["country"] = user_message
            context.country_code = user_message[:2].upper()  # Simple country code extraction

        # Move to next question or finish intake
        next_step = current_step + 1

        if next_step < len(intake_questions):
            context.state_data["intake_step"] = next_step
            return intake_questions[next_step], context
        else:
            # Intake complete, move to menu
            context.current_state = ConversationState.MENU

            response = (
                f"Great! I'm here to help you work on: {context.session_goal}\n\n"
                + prompts.get_menu_message()
            )

            return response, context

    async def _handle_menu(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Handle main menu navigation."""

        user_lower = user_message.lower()

        # Detect skill selection
        if any(word in user_lower for word in ["thought", "record", "thinking", "1"]):
            context.current_state = ConversationState.THOUGHT_RECORD
            context.current_skill = SkillType.THOUGHT_RECORD
            context.current_step = "situation"
            context.state_data["tr_data"] = {}

            prompt = prompts.get_skill_step_prompt("thought_record", "situation")
            return prompt, context

        elif any(word in user_lower for word in ["behavior", "activation", "activity", "2"]):
            context.current_state = ConversationState.BEHAVIORAL_ACTIVATION
            context.current_skill = SkillType.BEHAVIORAL_ACTIVATION
            context.current_step = "identify"
            context.state_data["ba_data"] = {}

            prompt = prompts.get_skill_step_prompt("behavioral_activation", "identify")
            return prompt, context

        elif any(word in user_lower for word in ["exposure", "fear", "anxiety", "3"]):
            context.current_state = ConversationState.EXPOSURE
            context.current_skill = SkillType.EXPOSURE
            context.current_step = "check_suitability"
            context.state_data["exp_data"] = {}

            prompt = prompts.get_skill_step_prompt("exposure", "check_suitability")
            return prompt, context

        elif any(word in user_lower for word in ["coping", "grounding", "breathing", "4"]):
            context.current_state = ConversationState.COPING
            context.current_skill = SkillType.COPING
            context.current_step = "select"

            response = (
                "**Choose a coping skill:**\n\n"
                "1. 🫁 **Breathing** (4-7-8 technique)\n"
                "2. 🧘 **Grounding** (5-4-3-2-1 senses)\n"
                "3. 💪 **Muscle Relaxation** (progressive)\n"
                "4. 🌊 **Urge Surfing** (ride the wave)\n\n"
                "Which one would help right now?"
            )
            return response, context

        elif any(word in user_lower for word in ["learn", "education", "5"]):
            context.current_state = ConversationState.LEARN
            context.current_step = "select"

            response = (
                "**Learn about CBT concepts:**\n\n"
                "1. CBT Basics\n"
                "2. Thought-Feeling Connection\n"
                "3. Cognitive Distortions\n"
                "4. Why Behavioral Activation Works\n"
                "5. How Exposure Works\n\n"
                "Pick a number or topic."
            )
            return response, context

        elif any(word in user_lower for word in ["review", "progress", "6"]):
            # Show recent progress
            return await self._show_progress(context)

        else:
            # Use LLM to interpret ambiguous input
            return await self._llm_menu_navigation(context, user_message)

    async def _handle_thought_record(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Handle thought record flow."""

        tr_data = context.state_data.get("tr_data", {})
        current_step = context.current_step

        # Define step order
        steps = [
            "situation",
            "automatic_thought",
            "emotions",
            "evidence_for",
            "evidence_against",
            "alternative_thought",
            "rerate"
        ]

        # Store current step data
        tr_data[current_step] = user_message

        # Move to next step
        current_index = steps.index(current_step)

        if current_index < len(steps) - 1:
            # More steps remaining
            next_step = steps[current_index + 1]
            context.current_step = next_step
            context.state_data["tr_data"] = tr_data

            prompt = prompts.get_skill_step_prompt("thought_record", next_step)
            return prompt, context

        else:
            # Thought record complete! Generate summary
            context.state_data["tr_data"] = tr_data

            # Save to database
            await db.create_skill_completion(
                session_id=context.session_id,
                patient_id=context.patient_id,
                skill_type="thought_record",
                data=tr_data,
                completion_status="completed"
            )

            # Generate summary with LLM
            summary = await self._generate_thought_record_summary(tr_data)

            response = (
                f"**Thought Record Complete!** ✅\n\n"
                f"{summary}\n\n"
                f"Would you like to:\n"
                f"1. Do another thought record\n"
                f"2. Try a different skill\n"
                f"3. End session"
            )

            # Return to menu
            context.current_state = ConversationState.MENU
            context.current_skill = None
            context.current_step = None

            return response, context

    async def _handle_behavioral_activation(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Handle behavioral activation flow."""

        ba_data = context.state_data.get("ba_data", {})
        current_step = context.current_step

        steps = ["identify", "break_down", "schedule", "if_then", "confirm"]

        # Store current step data
        ba_data[current_step] = user_message

        current_index = steps.index(current_step)

        if current_index < len(steps) - 1:
            next_step = steps[current_index + 1]
            context.current_step = next_step
            context.state_data["ba_data"] = ba_data

            prompt = prompts.get_skill_step_prompt("behavioral_activation", next_step)

            # Format with scheduled time if needed
            if next_step == "confirm" and "schedule" in ba_data:
                prompt = prompt.format(scheduled_time=ba_data["schedule"])

            return prompt, context

        else:
            # BA complete!
            context.state_data["ba_data"] = ba_data

            await db.create_skill_completion(
                session_id=context.session_id,
                patient_id=context.patient_id,
                skill_type="behavioral_activation",
                data=ba_data,
                completion_status="completed"
            )

            response = (
                f"**Activity Planned!** 🎯\n\n"
                f"**Activity:** {ba_data.get('identify', 'N/A')}\n"
                f"**When:** {ba_data.get('schedule', 'N/A')}\n"
                f"**If-Then Plan:** {ba_data.get('if_then', 'N/A')}\n\n"
                f"I'll check in with you after your scheduled time. "
                f"You've got this! 💪\n\n"
                + prompts.get_menu_message()
            )

            context.current_state = ConversationState.MENU
            context.current_skill = None

            return response, context

    async def _handle_exposure(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Handle exposure therapy flow."""

        exp_data = context.state_data.get("exp_data", {})
        current_step = context.current_step

        steps = [
            "check_suitability",
            "build_hierarchy",
            "select_target",
            "prediction",
            "debrief"
        ]

        # Special handling for suitability check
        if current_step == "check_suitability":
            user_lower = user_message.lower()

            if any(word in user_lower for word in ["trauma", "ptsd", "abuse", "assault"]):
                response = (
                    "I appreciate you sharing that. Exposure therapy for trauma "
                    "requires specialized trauma-focused therapy with a trained clinician. "
                    "Please discuss this with your therapist.\n\n"
                    "For now, I can help with other CBT skills. "
                    + prompts.get_menu_message()
                )
                context.current_state = ConversationState.MENU
                return response, context

        # Store data
        exp_data[current_step] = user_message

        current_index = steps.index(current_step)

        if current_index < len(steps) - 1:
            next_step = steps[current_index + 1]
            context.current_step = next_step
            context.state_data["exp_data"] = exp_data

            prompt = prompts.get_skill_step_prompt("exposure", next_step)
            return prompt, context

        else:
            # Exposure complete!
            context.state_data["exp_data"] = exp_data

            await db.create_skill_completion(
                session_id=context.session_id,
                patient_id=context.patient_id,
                skill_type="exposure",
                data=exp_data,
                completion_status="completed"
            )

            response = (
                f"**Exposure Complete!** 🌟\n\n"
                f"You faced your fear and gathered real data. That takes courage!\n\n"
                f"**Prediction:** {exp_data.get('prediction', 'N/A')}\n"
                f"**What actually happened:** {exp_data.get('debrief', 'N/A')}\n\n"
                f"Notice any difference? This is how we learn our fears are often bigger than reality.\n\n"
                + prompts.get_menu_message()
            )

            context.current_state = ConversationState.MENU
            context.current_skill = None

            return response, context

    async def _handle_coping(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Handle coping skills selection and guidance."""

        if context.current_step == "select":
            # Parse technique selection
            user_lower = user_message.lower()

            if "1" in user_lower or "breath" in user_lower:
                technique = "breathing"
            elif "2" in user_lower or "ground" in user_lower:
                technique = "grounding"
            elif "3" in user_lower or "muscle" in user_lower or "relax" in user_lower:
                technique = "muscle_relaxation"
            elif "4" in user_lower or "urge" in user_lower or "surf" in user_lower:
                technique = "urge_surfing"
            else:
                return "Please choose 1, 2, 3, or 4.", context

            # Get technique instructions
            instructions = prompts.get_coping_technique(technique)

            context.state_data["coping_technique"] = technique
            context.current_step = "guided"

            return instructions, context

        elif context.current_step == "guided":
            # After technique, ask for feedback
            response = (
                "How do you feel now (0-10, where 10 is best)?\n\n"
                "Or if you'd like, we can try another coping skill."
            )

            context.current_step = "feedback"
            return response, context

        elif context.current_step == "feedback":
            # Record feedback and return to menu
            technique = context.state_data.get("coping_technique", "unknown")

            await db.create_skill_completion(
                session_id=context.session_id,
                patient_id=context.patient_id,
                skill_type="coping",
                data={
                    "technique": technique,
                    "feedback": user_message
                },
                completion_status="completed"
            )

            response = (
                "Thanks for trying that coping skill! 🧘\n\n"
                + prompts.get_menu_message()
            )

            context.current_state = ConversationState.MENU
            context.current_skill = None

            return response, context

        return "Let's try a coping skill.", context

    async def _handle_learn(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Handle psychoeducation."""

        user_lower = user_message.lower()

        # Map selection to topic
        topic_map = {
            "1": "cbt_basics",
            "cbt": "cbt_basics",
            "basic": "cbt_basics",
            "2": "thought_feeling_connection",
            "thought": "thought_feeling_connection",
            "feeling": "thought_feeling_connection",
            "3": "cognitive_distortions",
            "distortion": "cognitive_distortions",
            "4": "behavioral_activation_why",
            "activation": "behavioral_activation_why",
            "5": "exposure_science",
            "exposure": "exposure_science",
        }

        topic = None
        for key, value in topic_map.items():
            if key in user_lower:
                topic = value
                break

        if not topic:
            return "Please choose 1-5 or name a topic.", context

        # Get psychoeducation content
        content = prompts.get_psychoeducation_card(topic)

        response = (
            f"{content}\n\n"
            f"Want to learn about another topic, or try a CBT skill?\n\n"
            + prompts.get_menu_message()
        )

        context.current_state = ConversationState.MENU

        return response, context

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    async def _handle_unknown_state(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Fallback handler for unknown states."""

        response = (
            "I'm not sure what to do here. Let's go back to the main menu.\n\n"
            + prompts.get_menu_message()
        )

        context.current_state = ConversationState.MENU

        return response, context

    async def _llm_menu_navigation(
        self,
        context: ConversationContext,
        user_message: str
    ) -> Tuple[str, ConversationContext]:
        """Use LLM to interpret ambiguous menu input."""

        system_prompt = prompts.get_system_prompt({
            "state": "menu",
            "user_name": context.user_name or "there",
            "session_goal": context.session_goal or "practice CBT skills"
        })

        menu_help = (
            "The user is at the main menu. They said: \"{user_message}\"\n\n"
            "Interpret their intent and either:\n"
            "1. Clarify which skill they want (thought record, BA, exposure, coping, learn)\n"
            "2. If unclear, ask them to choose from the menu\n\n"
            "Keep response brief and warm."
        )

        response = await llm_service.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": menu_help.format(user_message=user_message)}
            ],
            temperature=0.7,
            max_tokens=300
        )

        return response.content, context

    async def _generate_thought_record_summary(
        self,
        tr_data: Dict[str, Any]
    ) -> str:
        """Generate AI summary of thought record."""

        summary_prompt = f"""
Briefly summarize this thought record in 2-3 sentences:

Situation: {tr_data.get('situation', 'N/A')}
Thought: {tr_data.get('automatic_thought', 'N/A')}
Emotions before: {tr_data.get('emotions', 'N/A')}
Alternative thought: {tr_data.get('alternative_thought', 'N/A')}
Emotions after: {tr_data.get('rerate', 'N/A')}

Focus on: (1) the cognitive shift and (2) one micro-action they could take.
"""

        response = await llm_service.generate_response(
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.7,
            max_tokens=200
        )

        return response.content

    async def _show_progress(
        self,
        context: ConversationContext
    ) -> Tuple[str, ConversationContext]:
        """Show user their recent progress."""

        skills = await db.get_patient_skill_completions(
            patient_id=context.patient_id,
            limit=5
        )

        if not skills:
            response = (
                "You haven't completed any skills yet in this session. "
                "Let's get started!\n\n"
                + prompts.get_menu_message()
            )
        else:
            skill_list = "\n".join([
                f"• {skill['skill_type'].replace('_', ' ').title()} - {skill['completed_at'][:10]}"
                for skill in skills
            ])

            response = (
                f"**Your Recent Progress** 📊\n\n"
                f"{skill_list}\n\n"
                f"Great work! 🌟\n\n"
                + prompts.get_menu_message()
            )

        return response, context


# Global state machine instance
state_machine = StateMachine()


def get_state_machine() -> StateMachine:
    """Get state machine instance."""
    return state_machine
