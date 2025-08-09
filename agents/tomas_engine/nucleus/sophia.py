import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

# memory
from .shared_memory import SharedMemory

# services
from agents.services.gemini_service import GeminiService


class RuleType(Enum):
    MOVEMENT = "movement"
    INTERACTION = "interaction"
    STATE_CHANGE = "state_change"
    WIN_CONDITION = "win_condition"
    CONSTRAINT = "constraint"


@dataclass
class GameRule:
    """Represents a discovered game rule"""

    rule_id: str
    rule_type: RuleType
    description: str
    confidence: float
    evidence_count: int
    last_confirmed: str
    supporting_evidence: List[str]
    contradicting_evidence: List[str]


@dataclass
class Hypothesis:
    """Represents an active hypothesis about game mechanics"""

    hypothesis_id: str
    rule_type: RuleType
    description: str
    confidence: float
    evidence_count: int
    needs_testing: str


@dataclass
class GameObjective:
    """Represents theory about game objectives"""

    primary_goal: str
    secondary_requirements: List[str]
    constraints: List[str]
    confidence: float


class NucleiSophia:
    """Game Rules Discovery System"""

    def __init__(self):
        self.gemini_service = GeminiService()

        # Rule discovery system
        self.confirmed_rules: Dict[str, GameRule] = {}
        self.active_hypotheses: Dict[str, Hypothesis] = {}
        self.contradicted_theories: List[Dict] = []
        self.game_objective: Optional[GameObjective] = None

        # Evidence tracking
        self.observations: List[Dict] = []
        self.turn_counter = 0

        # Load previous knowledge from memory
        self._load_previous_knowledge()

    def process(
        self, action_executed: str, aisthesis_analysis: str, game_context: Dict = None
    ) -> str:
        """
        Discover game rules based on action-effect observations

        Args:
            action_executed: The action that was taken (e.g., "up", "click [30,40]")
            aisthesis_analysis: AISTHESIS's objective analysis of what happened
            game_context: Additional context about game state

        Returns:
            JSON string with current rule understanding
        """
        print(f"🧠 SOPHIA is analyzing turn {self.turn_counter + 1}...")
        self.turn_counter += 1

        # Record this observation
        observation = {
            "turn": self.turn_counter,
            "action": action_executed,
            "effect": aisthesis_analysis,
            "context": game_context,
            "timestamp": time.time(),
        }
        self.observations.append(observation)

        # Analyze this new evidence
        self._analyze_new_evidence(observation)

        # Check for hypothesis promotions
        self._check_hypothesis_promotions()
        
        # Generate insights and recommendations
        insights = self._generate_insights()
        recommendations = self._generate_recommendations()

        # Build response
        response_data = {
            "confirmed_rules": [
                self._rule_to_dict(rule) for rule in self.confirmed_rules.values()
            ],
            "active_hypotheses": [
                self._hypothesis_to_dict(hyp) for hyp in self.active_hypotheses.values()
            ],
            "game_objective_theory": (
                self._objective_to_dict() if self.game_objective else None
            ),
            "contradicted_theories": self.contradicted_theories,
            "immediate_insights": insights,
            "recommendations_for_logos": recommendations,
        }

        # Save to memory for persistence
        self._save_knowledge_to_memory()

        # Convert structured data to text summary for Logos
        return self._generate_text_summary(response_data)

    def _analyze_new_evidence(self, observation: Dict):
        """Analyze new observation and update rule knowledge"""
        action = observation["action"]
        effect = observation["effect"]

        # Check if this confirms existing rules
        self._check_existing_rules(action, effect)

        # Look for new patterns
        self._discover_new_patterns(observation)

        # Update game objective theories
        self._update_objective_theories(observation)

    def _check_existing_rules(self, action: str, effect: str):
        """Check if new evidence confirms or contradicts existing rules and hypotheses"""
        
        # Check confirmed rules
        for rule_id, rule in self.confirmed_rules.items():
            if self._action_matches_rule(action, rule):
                if self._effect_supports_rule(effect, rule):
                    # Confirm the rule
                    rule.evidence_count += 1
                    rule.confidence = min(1.0, rule.confidence + 0.05)
                    rule.last_confirmed = f"Turn {self.turn_counter}"
                    rule.supporting_evidence.append(
                        f"Turn {self.turn_counter}: {action} → {effect[:100]}"
                    )
                    print(
                        f"✅ Confirmed rule {rule_id}: confidence now {rule.confidence:.2f}"
                    )
                else:
                    # Contradiction - investigate
                    rule.contradicting_evidence.append(
                        f"Turn {self.turn_counter}: {action} → {effect[:100]}"
                    )
                    rule.confidence = max(0.1, rule.confidence - 0.1)
                    print(
                        f"❌ Rule {rule_id} contradicted: confidence now {rule.confidence:.2f}"
                    )
        
        # Check active hypotheses
        for hyp_id, hypothesis in self.active_hypotheses.items():
            if self._action_matches_hypothesis(action, hypothesis):
                if self._effect_supports_hypothesis(effect, hypothesis):
                    # Support the hypothesis
                    hypothesis.evidence_count += 1
                    hypothesis.confidence = min(1.0, hypothesis.confidence + 0.1)
                    print(
                        f"✅ Supported hypothesis {hyp_id}: confidence now {hypothesis.confidence:.2f}"
                    )
                else:
                    # Weaken the hypothesis
                    hypothesis.confidence = max(0.1, hypothesis.confidence - 0.1)
                    print(
                        f"❌ Hypothesis {hyp_id} weakened: confidence now {hypothesis.confidence:.2f}"
                    )

    def _discover_new_patterns(self, observation: Dict):
        """Look for new patterns in the observation"""
        action = observation["action"]
        effect = observation["effect"].lower()

        # Pattern: Movement actions
        if action in ["up", "down", "left", "right"]:
            if "moved" in effect or "position" in effect:
                self._create_movement_hypothesis(action, effect)
            elif "no effect" in effect or "blocked" in effect:
                self._create_constraint_hypothesis(action, effect)

        # Pattern: Space/Click actions
        elif action in ["space"] or "click" in action:
            if "changed" in effect or "activated" in effect:
                self._create_interaction_hypothesis(action, effect)

        # Pattern: Score/Progress changes
        if "score" in effect or "level" in effect or "progress" in effect:
            self._create_progress_hypothesis(action, effect)

    def _create_movement_hypothesis(self, action: str, effect: str):
        """Create hypothesis about movement mechanics"""
        # Check if we already have a similar hypothesis
        existing_hyp = self._find_similar_hypothesis(action, RuleType.MOVEMENT)
        if existing_hyp:
            # Update existing hypothesis instead of creating new one
            existing_hyp.evidence_count += 1
            existing_hyp.confidence = min(1.0, existing_hyp.confidence + 0.05)
            print(f"🔄 Updated existing movement hypothesis for {action}: confidence now {existing_hyp.confidence:.2f}")
            return

        rule_id = f"MOVEMENT_{action.upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"
        hypothesis = Hypothesis(
            hypothesis_id=rule_id,
            rule_type=RuleType.MOVEMENT,
            description=f"{action.upper()} action moves player when path is clear",
            confidence=0.4,
            evidence_count=1,
            needs_testing=f"Test {action} in different contexts to confirm movement rules",
        )
        self.active_hypotheses[rule_id] = hypothesis
        print(f"🔬 New movement hypothesis: {hypothesis.description}")

    def _create_constraint_hypothesis(self, action: str, effect: str):
        """Create hypothesis about movement constraints"""
        rule_id = f"CONSTRAINT_{action.upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.CONSTRAINT,
                description=f"{action.upper()} blocked by obstacles (walls, boundaries)",
                confidence=0.5,
                evidence_count=1,
                needs_testing=f"Identify what specific obstacles block {action} movement",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"🚧 New constraint hypothesis: {hypothesis.description}")

    def _create_interaction_hypothesis(self, action: str, effect: str):
        """Create hypothesis about interaction mechanics"""
        rule_id = f"INTERACTION_{action.replace(' ', '_').upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.INTERACTION,
                description=f"{action} activates objects or changes game state",
                confidence=0.6,
                evidence_count=1,
                needs_testing=f"Test {action} with different objects to understand interaction range/conditions",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"🔗 New interaction hypothesis: {hypothesis.description}")

    def _create_progress_hypothesis(self, action: str, effect: str):
        """Create hypothesis about progress/winning mechanics"""
        rule_id = f"PROGRESS_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.WIN_CONDITION,
                description=f"Actions can trigger score/level progression",
                confidence=0.7,
                evidence_count=1,
                needs_testing="Identify what specific conditions trigger progression",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"🏆 New progress hypothesis: {hypothesis.description}")

    def _promote_hypothesis_to_rule(self, hypothesis: Hypothesis):
        """Promote a well-evidenced hypothesis to a confirmed rule"""
        rule = GameRule(
            rule_id=hypothesis.hypothesis_id,
            rule_type=hypothesis.rule_type,
            description=hypothesis.description,
            confidence=hypothesis.confidence,
            evidence_count=hypothesis.evidence_count,
            last_confirmed=f"Turn {self.turn_counter}",
            supporting_evidence=[
                f"Promoted from hypothesis at turn {self.turn_counter}"
            ],
            contradicting_evidence=[],
        )

        self.confirmed_rules[hypothesis.hypothesis_id] = rule
        del self.active_hypotheses[hypothesis.hypothesis_id]
        print(f"📈 Promoted hypothesis to confirmed rule: {rule.description}")

    def _check_hypothesis_promotions(self):
        """Check if any hypotheses should be promoted to confirmed rules"""
        hypotheses_to_promote = []
        
        for hyp in self.active_hypotheses.values():
            # Promote if confidence > 0.8 and evidence_count >= 3
            if hyp.confidence >= 0.8 and hyp.evidence_count >= 3:
                hypotheses_to_promote.append(hyp)
        
        # Promote eligible hypotheses
        for hyp in hypotheses_to_promote:
            self._promote_hypothesis_to_rule(hyp)

    def _update_objective_theories(self, observation: Dict):
        """Update theories about game objectives based on new evidence"""
        effect = observation["effect"].lower()

        # Look for win condition clues
        if any(
            keyword in effect
            for keyword in ["level", "score", "complete", "exit", "goal"]
        ):
            if not self.game_objective:
                self.game_objective = GameObjective(
                    primary_goal="Reach specific game state or location",
                    secondary_requirements=["Fulfill certain conditions"],
                    constraints=["Limited moves", "Avoid obstacles"],
                    confidence=0.4,
                )
            else:
                self.game_objective.confidence = min(
                    1.0, self.game_objective.confidence + 0.05
                )

    def _generate_insights(self) -> List[str]:
        """Generate immediate insights from recent observations"""
        insights = []

        # Check recent patterns
        if len(self.observations) >= 2:
            recent = self.observations[-2:]
            if recent[0]["action"] == recent[1]["action"]:
                insights.append(
                    f"Repeated {recent[0]['action']} action - investigating consistency"
                )

        # Check hypothesis promotion candidates
        for hyp in self.active_hypotheses.values():
            if hyp.confidence > 0.8 and hyp.evidence_count >= 3:
                insights.append(
                    f"Hypothesis '{hyp.description}' ready for promotion to confirmed rule"
                )

        return insights

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations for LOGOS based on current knowledge"""
        recommendations = []

        # Recommend testing hypotheses
        for hyp in self.active_hypotheses.values():
            if hyp.confidence < 0.6:
                recommendations.append(hyp.needs_testing)

        # Recommend using confirmed rules
        for rule in self.confirmed_rules.values():
            if rule.confidence > 0.8 and rule.rule_type == RuleType.MOVEMENT:
                action = rule.description.split()[0].lower()
                recommendations.append(
                    f"Use {action} movement - confirmed to work reliably"
                )

        return recommendations[:5]  # Limit to top 5 recommendations

    # Helper methods for data conversion
    def _rule_to_dict(self, rule: GameRule) -> Dict:
        return {
            "rule_id": rule.rule_id,
            "rule_type": rule.rule_type.value,
            "description": rule.description,
            "confidence": round(rule.confidence, 2),
            "evidence_count": rule.evidence_count,
            "last_confirmed": rule.last_confirmed,
        }

    def _hypothesis_to_dict(self, hypothesis: Hypothesis) -> Dict:
        return {
            "hypothesis_id": hypothesis.hypothesis_id,
            "rule_type": hypothesis.rule_type.value,
            "description": hypothesis.description,
            "confidence": round(hypothesis.confidence, 2),
            "evidence_count": hypothesis.evidence_count,
            "needs_testing": hypothesis.needs_testing,
        }

    def _objective_to_dict(self) -> Dict:
        if not self.game_objective:
            return None
        return {
            "primary_goal": self.game_objective.primary_goal,
            "secondary_requirements": self.game_objective.secondary_requirements,
            "constraints": self.game_objective.constraints,
            "confidence": round(self.game_objective.confidence, 2),
        }

    # Utility methods for rule checking
    def _action_matches_rule(self, action: str, rule: GameRule) -> bool:
        """Check if an action is relevant to a rule"""
        action_word = action.split()[0].lower()
        return action_word in rule.description.lower()

    def _effect_supports_rule(self, effect: str, rule: GameRule) -> bool:
        """Check if an effect supports a rule"""
        # Simple keyword matching - could be made more sophisticated
        if rule.rule_type == RuleType.MOVEMENT:
            return "moved" in effect.lower() or "position" in effect.lower()
        elif rule.rule_type == RuleType.INTERACTION:
            return "changed" in effect.lower() or "activated" in effect.lower()
        return True  # Default to supporting

    def _action_matches_hypothesis(self, action: str, hypothesis: Hypothesis) -> bool:
        """Check if an action is relevant to a hypothesis"""
        action_word = action.split()[0].lower()
        return action_word in hypothesis.description.lower()

    def _effect_supports_hypothesis(self, effect: str, hypothesis: Hypothesis) -> bool:
        """Check if an effect supports a hypothesis"""
        # Same logic as rules for now
        if hypothesis.rule_type == RuleType.MOVEMENT:
            return "moved" in effect.lower() or "position" in effect.lower()
        elif hypothesis.rule_type == RuleType.INTERACTION:
            return "changed" in effect.lower() or "activated" in effect.lower()
        elif hypothesis.rule_type == RuleType.WIN_CONDITION:
            return "score" in effect.lower() or "level" in effect.lower() or "progress" in effect.lower()
        elif hypothesis.rule_type == RuleType.CONSTRAINT:
            return "no effect" in effect.lower() or "blocked" in effect.lower()
        return True  # Default to supporting

    def _find_similar_hypothesis(self, action: str, rule_type: RuleType) -> Optional[Hypothesis]:
        """Find existing hypothesis that covers the same action and rule type"""
        action_word = action.split()[0].lower()
        
        for hypothesis in self.active_hypotheses.values():
            if hypothesis.rule_type == rule_type and action_word in hypothesis.description.lower():
                return hypothesis
        return None

    def _generate_text_summary(self, response_data: Dict) -> str:
        """Convert structured rule data to text summary for Logos"""
        
        summary = f"Here is SOPHIA's current understanding of the game (Turn {self.turn_counter}):\n\n"
        
        # Confirmed rules section
        confirmed_rules = response_data.get("confirmed_rules", [])
        if confirmed_rules:
            summary += "CONFIRMED RULES (high confidence):\n"
            for rule in confirmed_rules:
                confidence = rule.get("confidence", 0.0)
                desc = rule.get("description", "Unknown rule")
                summary += f"• {desc} (confidence: {confidence:.2f})\n"
            summary += "\n"
        
        # Active hypotheses section  
        active_hypotheses = response_data.get("active_hypotheses", [])
        if active_hypotheses:
            summary += "ACTIVE THEORIES (being tested):\n"
            for hyp in active_hypotheses:
                confidence = hyp.get("confidence", 0.0)
                desc = hyp.get("description", "Unknown hypothesis")
                summary += f"• {desc} (confidence: {confidence:.2f})\n"
            summary += "\n"
        
        # Game objective theory
        objective = response_data.get("game_objective_theory")
        if objective:
            summary += "GAME OBJECTIVE THEORY:\n"
            summary += f"• Primary goal: {objective.get('primary_goal', 'Unknown')}\n"
            requirements = objective.get("secondary_requirements", [])
            if requirements:
                summary += f"• Requirements: {', '.join(requirements)}\n"
            constraints = objective.get("constraints", [])
            if constraints:
                summary += f"• Constraints: {', '.join(constraints)}\n"
            obj_confidence = objective.get("confidence", 0.0)
            summary += f"• Confidence in objective: {obj_confidence:.2f}\n\n"
        
        # Immediate insights
        insights = response_data.get("immediate_insights", [])
        if insights:
            summary += "RECENT INSIGHTS:\n"
            for insight in insights:
                summary += f"• {insight}\n"
            summary += "\n"
        
        # Recommendations for Logos
        recommendations = response_data.get("recommendations_for_logos", [])
        if recommendations:
            summary += "RECOMMENDATIONS FOR LOGOS:\n"
            for rec in recommendations:
                summary += f"• {rec}\n"
            summary += "\n"
        
        # Contradicted theories
        contradicted = response_data.get("contradicted_theories", [])
        if contradicted:
            summary += "CONTRADICTED THEORIES (abandoned):\n"
            for theory in contradicted[-3:]:  # Only show last 3
                theory_desc = theory.get("theory", "Unknown theory")
                contradiction = theory.get("contradiction", "No details")
                summary += f"• REJECTED: {theory_desc} - {contradiction}\n"
            summary += "\n"
        
        # Summary stats
        total_rules = len(confirmed_rules)
        total_hypotheses = len(active_hypotheses)
        
        if total_rules == 0 and total_hypotheses == 0:
            summary += "STATUS: Still learning basic game mechanics. More observations needed.\n"
        elif total_rules > 0:
            summary += f"STATUS: Discovered {total_rules} confirmed rules, {total_hypotheses} active theories. Knowledge building!\n"
        else:
            summary += f"STATUS: Exploring game mechanics. {total_hypotheses} theories under investigation.\n"
            
        return summary

    # Memory persistence
    def _load_previous_knowledge(self):
        """Load previously discovered rules from shared memory"""
        memory = SharedMemory.get_instance()

        # Try to load previous rule discoveries
        # This is a simplified approach - in practice might want more sophisticated storage
        previous_rules = memory.get_relevant_experience("sophia rules discovered")
        if previous_rules:
            print(f"📚 Loaded previous rule knowledge: {len(previous_rules)} items")

    def _save_knowledge_to_memory(self):
        """Save current rule knowledge to shared memory"""
        memory = SharedMemory.get_instance()

        # Save key insights to memory
        if self.confirmed_rules:
            rule_summary = f"Discovered {len(self.confirmed_rules)} confirmed rules"
            memory.remember_success(
                "sophia rules discovered", "rule_discovery", rule_summary
            )

        if self.active_hypotheses:
            hyp_summary = f"Generated {len(self.active_hypotheses)} active hypotheses"
            memory.remember_success(
                "sophia hypotheses active", "hypothesis_generation", hyp_summary
            )
