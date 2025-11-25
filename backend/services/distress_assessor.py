"""
Distress Assessor Service - Evaluates patient distress level and provides grounding support.

Part of Opzione C: Trauma-informed, grounding-first approach.
"""

import re
from typing import List, Dict, Optional, Tuple
from models.schemas import (
    DistressLevel,
    DistressAssessment,
    GroundingExerciseResponse,
    TherapistBrief
)


class DistressAssessor:
    """
    Assesses patient distress level from message content and conversation history.
    Provides grounding exercises when distress is elevated.
    """

    # Distress signals organized by severity
    CRISIS_SIGNALS = [
        r"\bcan'?t breathe\b",
        r"\bcan'?t handle\b",
        r"\blosing control\b",
        r"\bdissociat",
        r"\bpanic attack\b",
        r"\bheart racing\b",
        r"\bgoing to die\b",
        r"\bneed help now\b",
        r"\bemergency\b",
        r"\bcrisis\b",
    ]

    SEVERE_SIGNALS = [
        r"\boverwhelm",
        r"\bcan'?t think\b",
        r"\bcan'?t focus\b",
        r"\bspinning\b",
        r"\bshaking\b",
        r"\bfreaking out\b",
        r"\bterrified\b",
        r"\bextremely anxious\b",
        r"\bvery scared\b",
    ]

    MODERATE_SIGNALS = [
        r"\banxious\b",
        r"\bworried\b",
        r"\bstressed\b",
        r"\bupset\b",
        r"\btriggered\b",
        r"\buncomfortable\b",
        r"\bnervous\b",
        r"\buneasy\b",
        r"\bagitated\b",
    ]

    MILD_SIGNALS = [
        r"\ba bit worried\b",
        r"\bslightly anxious\b",
        r"\ba little stressed\b",
        r"\bunsure\b",
        r"\bconcerned\b",
    ]

    # Grounding exercises database
    GROUNDING_EXERCISES = {
        "5-4-3-2-1": {
            "name": "5-4-3-2-1 Sensory Grounding",
            "duration": 300,  # 5 minutes
            "instructions": """Let's bring you back to the present moment. Take your time with this.

**Look around you right now and notice:**
- **5 things you can see** (describe them to yourself - colors, shapes, details)
- **4 things you can touch** (notice textures - smooth, rough, warm, cold)
- **3 things you can hear** (listen carefully - near and far sounds)
- **2 things you can smell** (or think of your 2 favorite scents)
- **1 thing you can taste** (or think of your favorite taste)

Take slow, gentle breaths as you do this. There's no rush.

Tell me when you're ready to continue, or if you'd like to stop here.""",
            "follow_up": "How do you feel now? Even a small shift is meaningful.",
        },
        "breathing": {
            "name": "Paced Breathing",
            "duration": 180,  # 3 minutes
            "instructions": """Let's slow things down with some paced breathing.

**Here's what to do:**
1. Breathe in slowly through your nose for **4 counts** (1... 2... 3... 4...)
2. Hold gently for **4 counts**
3. Breathe out slowly through your mouth for **6 counts** (1... 2... 3... 4... 5... 6...)
4. Pause for **2 counts**
5. Repeat 5-10 times

You can place one hand on your chest and one on your belly if that helps.

The exhale being longer than the inhale helps activate your calm-down system.

Let me know when you've done a few cycles, or if you need to adjust the pace.""",
            "follow_up": "Did the breathing help at all? Sometimes it takes a few minutes to notice a shift.",
        },
        "body_scan": {
            "name": "Quick Body Scan",
            "duration": 240,  # 4 minutes
            "instructions": """Let's check in with your body, gently and without judgment.

**Starting from your head, slowly move your attention down:**
- Notice your **face** - any tension in your jaw, forehead, or around your eyes?
- Your **shoulders** - are they tight? Can you let them drop a little?
- Your **chest** - what does your breathing feel like right now?
- Your **stomach** - any tightness or butterflies?
- Your **hands** - are they clenched? Can you loosen them?
- Your **legs and feet** - notice where they're touching the ground or chair

You don't have to change anything - just notice. Breathe gently.

If you find tension, imagine breathing into that spot and letting it soften a little.

Tell me what you notice, or just let me know when you're done.""",
            "follow_up": "What did you notice? Sometimes just paying attention helps.",
        },
        "orientation": {
            "name": "Present Moment Orientation",
            "duration": 120,  # 2 minutes
            "instructions": """Let's orient to the present moment.

**Answer these questions (out loud or in your mind):**
- What is today's date?
- Where are you right now? (Describe the room/place)
- What are you sitting or standing on?
- What time of day is it?
- Name 3 objects you can see right now

**Remind yourself:**
"Right now, in this moment, I am safe."
"This feeling is uncomfortable, but I am not in danger."
"I am here, in [current location], and I am OK."

Take a slow breath.

Let me know when you're ready.""",
            "follow_up": "Does it help to remember where and when you are right now?",
        },
        "temperature": {
            "name": "Temperature Shift",
            "duration": 60,  # 1 minute
            "instructions": """Sometimes a quick physical sensation can help reset.

**Try one of these:**
- Hold an ice cube or run cold water on your wrists
- Splash cold water on your face
- Hold a warm cup of tea or coffee
- Wrap yourself in a soft blanket

Physical temperature changes can interrupt the distress cycle.

Pick what feels doable right now, and notice how it feels.

Let me know how it goes.""",
            "follow_up": "Did the temperature change help shift your focus at all?",
        },
    }

    def __init__(self, llm_service=None):
        """
        Initialize DistressAssessor.

        Args:
            llm_service: Optional LLM service for advanced assessment
        """
        self.llm = llm_service

    def assess_distress(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        therapist_brief: Optional[TherapistBrief] = None
    ) -> DistressAssessment:
        """
        Assess patient's distress level from message and context.

        Args:
            message: Current patient message
            conversation_history: Recent conversation for context
            therapist_brief: Patient-specific clinical information

        Returns:
            DistressAssessment with level, reasoning, and grounding recommendation
        """
        message_lower = message.lower()
        signals_detected = []

        # Check for crisis signals
        crisis_matches = self._check_patterns(message_lower, self.CRISIS_SIGNALS)
        if crisis_matches:
            signals_detected.extend(crisis_matches)
            return DistressAssessment(
                distress_level=DistressLevel.CRISIS,
                reasoning="Crisis-level distress indicators detected (panic, dissociation, overwhelming fear)",
                signals_detected=signals_detected,
                requires_grounding=True,
                grounding_technique_suggested="breathing"
            )

        # Check for severe signals
        severe_matches = self._check_patterns(message_lower, self.SEVERE_SIGNALS)
        if severe_matches:
            signals_detected.extend(severe_matches)

            # Check for multiple severe signals or context
            if len(severe_matches) >= 2 or self._has_escalation_pattern(conversation_history):
                return DistressAssessment(
                    distress_level=DistressLevel.SEVERE,
                    reasoning="Multiple severe distress indicators detected",
                    signals_detected=signals_detected,
                    requires_grounding=True,
                    grounding_technique_suggested="5-4-3-2-1"
                )
            else:
                return DistressAssessment(
                    distress_level=DistressLevel.SEVERE,
                    reasoning="Severe distress indicators present",
                    signals_detected=signals_detected,
                    requires_grounding=True,
                    grounding_technique_suggested="breathing"
                )

        # Check for moderate signals
        moderate_matches = self._check_patterns(message_lower, self.MODERATE_SIGNALS)
        if moderate_matches:
            signals_detected.extend(moderate_matches)

            # Consider therapist brief sensitivities
            if therapist_brief and therapist_brief.sensitivities.pacing == "slow":
                # Be more proactive with grounding for sensitive patients
                return DistressAssessment(
                    distress_level=DistressLevel.MODERATE,
                    reasoning="Moderate distress detected; patient requires gentle pacing",
                    signals_detected=signals_detected,
                    requires_grounding=True,
                    grounding_technique_suggested="body_scan"
                )
            else:
                return DistressAssessment(
                    distress_level=DistressLevel.MODERATE,
                    reasoning="Moderate distress detected",
                    signals_detected=signals_detected,
                    requires_grounding=len(moderate_matches) >= 2,
                    grounding_technique_suggested="breathing" if len(moderate_matches) >= 2 else None
                )

        # Check for mild signals
        mild_matches = self._check_patterns(message_lower, self.MILD_SIGNALS)
        if mild_matches:
            signals_detected.extend(mild_matches)
            return DistressAssessment(
                distress_level=DistressLevel.MILD,
                reasoning="Mild distress indicators present",
                signals_detected=signals_detected,
                requires_grounding=False,
                grounding_technique_suggested=None
            )

        # No distress signals detected
        return DistressAssessment(
            distress_level=DistressLevel.NONE,
            reasoning="No significant distress indicators detected",
            signals_detected=[],
            requires_grounding=False,
            grounding_technique_suggested=None
        )

    def _check_patterns(self, text: str, patterns: List[str]) -> List[str]:
        """Check text against regex patterns and return matches."""
        matches = []
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Extract the matched text for clarity
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    matches.append(match.group(0))
        return matches

    def _has_escalation_pattern(self, conversation_history: Optional[List[Dict[str, str]]]) -> bool:
        """
        Check if distress is escalating over recent messages.

        Returns True if patient messages show increasing distress.
        """
        if not conversation_history or len(conversation_history) < 3:
            return False

        # Check last 5 patient messages for escalation
        recent_patient_messages = [
            msg["content"] for msg in conversation_history[-10:]
            if msg.get("role") == "user"
        ][-5:]

        if len(recent_patient_messages) < 3:
            return False

        # Count distress signals in recent messages
        distress_counts = []
        for msg in recent_patient_messages:
            msg_lower = msg.lower()
            count = (
                len(self._check_patterns(msg_lower, self.CRISIS_SIGNALS)) * 3 +
                len(self._check_patterns(msg_lower, self.SEVERE_SIGNALS)) * 2 +
                len(self._check_patterns(msg_lower, self.MODERATE_SIGNALS))
            )
            distress_counts.append(count)

        # Check if trend is increasing
        if len(distress_counts) >= 3:
            # Simple escalation check: most recent > earlier messages
            return distress_counts[-1] > distress_counts[0]

        return False

    def get_grounding_exercise(
        self,
        technique: str = "5-4-3-2-1",
        therapist_brief: Optional[TherapistBrief] = None
    ) -> GroundingExerciseResponse:
        """
        Get a grounding exercise by name.

        Args:
            technique: Exercise name (5-4-3-2-1, breathing, body_scan, etc.)
            therapist_brief: Patient-specific information to customize exercise

        Returns:
            GroundingExerciseResponse with instructions
        """
        # Default to 5-4-3-2-1 if technique not found
        exercise = self.GROUNDING_EXERCISES.get(technique, self.GROUNDING_EXERCISES["5-4-3-2-1"])

        instructions = exercise["instructions"]

        # Customize based on therapist brief if available
        if therapist_brief and therapist_brief.therapist_language.coping_statements:
            # Add therapist's coping statements to follow-up
            coping_statement = therapist_brief.therapist_language.coping_statements[0]
            follow_up = exercise["follow_up"] + f"\n\nRemember: {coping_statement}"
        else:
            follow_up = exercise["follow_up"]

        return GroundingExerciseResponse(
            technique_name=exercise["name"],
            instructions=instructions,
            estimated_duration_seconds=exercise["duration"],
            follow_up_message=follow_up
        )

    def should_offer_grounding(
        self,
        distress_assessment: DistressAssessment,
        grounding_count_this_session: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Decide if grounding should be offered based on assessment and session history.

        Args:
            distress_assessment: Current distress assessment
            grounding_count_this_session: How many times grounding was already used

        Returns:
            (should_offer, message_to_patient)
        """
        if distress_assessment.distress_level == DistressLevel.CRISIS:
            return (
                True,
                "I notice you're feeling very overwhelmed right now. Let's pause and do a quick grounding exercise together before we continue. This will help."
            )

        if distress_assessment.distress_level == DistressLevel.SEVERE:
            if grounding_count_this_session == 0:
                return (
                    True,
                    "I can see you're feeling quite activated right now. Would you like to try a quick grounding exercise together? It might help us work through this more effectively."
                )
            else:
                return (
                    True,
                    "You're still feeling pretty overwhelmed. Let's do another brief grounding exercise to help settle things down."
                )

        if distress_assessment.distress_level == DistressLevel.MODERATE:
            if distress_assessment.requires_grounding and grounding_count_this_session == 0:
                return (
                    True,
                    "I notice you're feeling quite distressed. Before we dive into the CBT work, would it help to do a quick grounding exercise? Sometimes that makes the work easier."
                )
            elif grounding_count_this_session >= 2:
                # Too much grounding, may need different approach
                return (
                    False,
                    None
                )

        return (False, None)

    def format_grounding_offer(
        self,
        distress_level: DistressLevel,
        technique: str = "breathing"
    ) -> str:
        """
        Format a gentle offer to do grounding, appropriate to distress level.

        Args:
            distress_level: Current distress level
            technique: Suggested technique

        Returns:
            Message text offering grounding
        """
        if distress_level == DistressLevel.CRISIS:
            return f"""I notice you're feeling very overwhelmed right now. Let's pause and do a quick grounding exercise together.

This will help - it just takes a minute or two. Type 'yes' when you're ready, or 'skip' if you'd rather not."""

        elif distress_level == DistressLevel.SEVERE:
            return f"""I can see you're feeling quite activated. Would you like to try a quick {technique} exercise together? It might help us work through this more effectively.

Type 'yes' to try it, or 'no' to continue without it."""

        else:  # MODERATE
            return f"""I notice you're feeling distressed. Sometimes a quick {technique} exercise can make the CBT work easier.

Would you like to try it? (yes/no)"""
