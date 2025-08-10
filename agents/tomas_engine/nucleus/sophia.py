import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

# memory
from .shared_memory import SharedMemory

# services
from agents.services.gemini_service import GeminiService

# structured data
from .data_structures import StructuredRule, SophiaStructuredData, RuleConfidenceLevel


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
    level_proven: bool = False  # NEW: Marks rules proven by successful level completion


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
        # Initialize Gemini with safe fallback if not available
        try:
            self.gemini_service = GeminiService()
        except Exception as init_error:
            print(
                f"⚠️ SOPHIA: GeminiService not available, using local summary. Reason: {init_error}"
            )
            self.gemini_service = None

        # Rule discovery system with enhanced tracking
        self.confirmed_rules: Dict[str, GameRule] = {}
        self.active_hypotheses: Dict[str, Hypothesis] = {}
        self.contradicted_theories: List[Dict] = []
        self.game_objective: Optional[GameObjective] = None

        # NEW: Enhanced rule tracking
        self.rule_success_history: Dict[str, List[bool]] = (
            {}
        )  # Track success/failure of each rule
        self.rule_performance_metrics: Dict[str, Dict[str, float]] = (
            {}
        )  # Precision, recall, etc.
        self.cross_validation_results: Dict[str, Dict] = {}  # Cross-validation scores
        self.rule_degradation_schedule: Dict[str, float] = (
            {}
        )  # Gradual confidence decay

        # Evidence tracking
        self.observations: List[Dict] = []
        self.turn_counter = 0

        # Performance tracking
        self.prediction_accuracy_history: List[float] = []
        self.rule_consistency_scores: Dict[str, float] = {}

        # Load previous knowledge from memory
        self._load_previous_knowledge()

    def process(
        self, action_executed: str, aisthesis_analysis: str, game_context: Dict = None
    ) -> Tuple[str, SophiaStructuredData]:
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

        # Perform robustness analysis and updates
        self._update_rule_performance_metrics()
        self._apply_gradual_degradation()
        self._cross_validate_rules()

        # Create structured data for LOGOS
        structured_data = self._create_structured_sophia_data(response_data)

        # Convert structured data to text summary for Logos
        text_summary = self._generate_text_summary(response_data)

        # Optionally enhance Sophia reasoning with Gemini for more useful guidance to LOGOS
        enhanced_summary = self._enhance_summary_with_gemini(
            action_executed=action_executed,
            aisthesis_analysis=aisthesis_analysis,
            response_data=response_data,
            fallback_summary=text_summary,
        )

        return enhanced_summary, structured_data

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
        
        # NEW: Check for level completion and consolidate proven rules
        self._check_for_level_completion_and_consolidate(observation)

    def _check_existing_rules(self, action: str, effect: str):
        """Check if new evidence confirms or contradicts existing rules and hypotheses"""

        # Check confirmed rules
        for rule_id, rule in self.confirmed_rules.items():
            if self._action_matches_rule(action, rule):
                if self._effect_supports_rule(effect, rule):
                    # ENHANCED RULE REINFORCEMENT - Successful rules get stronger
                    rule.evidence_count += 1
                    
                    # Progressive confidence boost based on current confidence
                    if rule.confidence >= 0.8:
                        # Already high confidence rules get smaller boosts to avoid over-confidence
                        confidence_boost = 0.02
                    elif rule.confidence >= 0.6:
                        # Medium confidence rules get standard boosts
                        confidence_boost = 0.05
                    else:
                        # Low confidence rules get larger boosts to help them establish
                        confidence_boost = 0.08
                    
                    rule.confidence = min(1.0, rule.confidence + confidence_boost)
                    rule.last_confirmed = f"Turn {self.turn_counter}"
                    rule.supporting_evidence.append(
                        f"Turn {self.turn_counter}: {action} → {effect[:100]}"
                    )
                    
                    # REINFORCEMENT BONUS: Extra confidence for consecutive successes
                    if len(rule.supporting_evidence) >= 3:
                        recent_evidence = rule.supporting_evidence[-3:]
                        recent_turns = []
                        for evidence in recent_evidence:
                            try:
                                turn_num = int(evidence.split("Turn ")[1].split(":")[0])
                                recent_turns.append(turn_num)
                            except:
                                continue
                        
                        # If recent confirmations are close together, give bonus
                        if len(recent_turns) >= 2 and (recent_turns[-1] - recent_turns[-2]) <= 3:
                            rule.confidence = min(1.0, rule.confidence + 0.03)
                            print(f"🔥 REINFORCEMENT BONUS for {rule_id}: consecutive successes!")
                    
                    print(
                        f"✅ Confirmed rule {rule_id}: confidence now {rule.confidence:.2f} (boost: +{confidence_boost:.2f})"
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
        """Look for new patterns in the observation - AGGRESSIVE LEARNING MODE"""
        action = observation["action"]
        effect = observation["effect"].lower()

        # ENHANCED: Much more aggressive pattern detection
        
        # Pattern: Movement actions (EXPANDED DETECTION)
        if action in ["up", "down", "left", "right"]:
            # Movement success patterns
            if any(keyword in effect for keyword in ["moved", "position", "translation", "shifted", "displaced"]):
                self._create_movement_hypothesis(action, effect)
            # Constraint/blocking patterns  
            elif any(keyword in effect for keyword in ["no effect", "blocked", "wall", "obstacle", "boundary", "constraint"]):
                self._create_constraint_hypothesis(action, effect)
            # Even if no clear effect, create exploratory hypothesis
            else:
                self._create_exploratory_hypothesis(action, effect, "movement")

        # Pattern: Space/Click actions (EXPANDED DETECTION)
        elif action in ["space"] or "click" in action:
            # Interaction success patterns
            if any(keyword in effect for keyword in ["changed", "activated", "triggered", "switched", "toggled", "opened", "closed"]):
                self._create_interaction_hypothesis(action, effect)
            # Object transformation patterns
            elif any(keyword in effect for keyword in ["color", "shape", "appeared", "disappeared", "transformed"]):
                self._create_transformation_hypothesis(action, effect)
            # Even if no clear effect, create exploratory hypothesis
            else:
                self._create_exploratory_hypothesis(action, effect, "interaction")

        # Pattern: ANY action with object changes (NEW)
        if any(keyword in effect for keyword in ["object", "entity", "item", "piece", "block"]):
            self._create_object_manipulation_hypothesis(action, effect)
            
        # Pattern: ANY action with environmental changes (NEW)
        if any(keyword in effect for keyword in ["water", "fire", "door", "key", "button", "lever", "platform"]):
            self._create_environment_hypothesis(action, effect)

        # Pattern: Score/Progress changes (EXPANDED)
        if any(keyword in effect for keyword in ["score", "level", "progress", "point", "win", "complete", "finish", "goal"]):
            self._create_progress_hypothesis(action, effect)
            
        # Pattern: Level transitions (EXPANDED)
        if any(keyword in effect for keyword in ["level up", "level lost", "game reset", "new level", "restart", "game over"]):
            self._create_level_transition_hypothesis(action, effect)
            
        # Pattern: Timing/sequence effects (NEW)
        if any(keyword in effect for keyword in ["sequence", "timing", "order", "delay", "repeat"]):
            self._create_timing_hypothesis(action, effect)
            
        # Pattern: Spatial relationships (NEW)  
        if any(keyword in effect for keyword in ["region", "area", "zone", "grid", "row", "column", "center", "corner"]):
            self._create_spatial_hypothesis(action, effect)
            
        # CATCH-ALL: If we haven't created any hypothesis but there was an effect, create a general one
        if len(effect.strip()) > 10 and "no effect" not in effect:  # Meaningful effect
            if not any(hyp.description.lower().find(action.lower()) >= 0 for hyp in list(self.active_hypotheses.values())[-5:]):
                print(f"🔬 Creating catch-all hypothesis for unmapped pattern: {action} → {effect[:50]}")
                self._create_general_hypothesis(action, effect)

    def _create_movement_hypothesis(self, action: str, effect: str):
        """Create hypothesis about movement mechanics"""
        # Check if we already have a similar hypothesis
        existing_hyp = self._find_similar_hypothesis(action, RuleType.MOVEMENT)
        if existing_hyp:
            # Update existing hypothesis instead of creating new one
            existing_hyp.evidence_count += 1
            existing_hyp.confidence = min(1.0, existing_hyp.confidence + 0.05)
            print(
                f"🔄 Updated existing movement hypothesis for {action}: confidence now {existing_hyp.confidence:.2f}"
            )
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

    def _create_level_transition_hypothesis(self, action: str, effect: str):
        """Create hypothesis about level transition mechanics"""
        rule_id = f"LEVEL_TRANSITION_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            if "level up" in effect.lower():
                description = f"Action '{action}' can trigger successful level completion"
                confidence = 0.8  # High confidence for level up
            elif "level lost" in effect.lower():
                description = f"Action '{action}' can cause level failure/game over"
                confidence = 0.7  # Medium-high confidence for level lost
            elif "game reset" in effect.lower():
                description = f"Action '{action}' can trigger game reset after failure"
                confidence = 0.6  # Medium confidence for reset
            else:
                description = f"Action '{action}' affects level/game state transitions"
                confidence = 0.5

            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.STATE_CHANGE,
                description=description,
                confidence=confidence,
                evidence_count=1,
                needs_testing=f"Monitor conditions that lead to level transitions with {action}",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"🎮 New level transition hypothesis: {hypothesis.description}")

    def _create_exploratory_hypothesis(self, action: str, effect: str, category: str):
        """Create exploratory hypothesis for unclear effects - AGGRESSIVE LEARNING"""
        rule_id = f"EXPLORATORY_{category.upper()}_{action.upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.MOVEMENT if category == "movement" else RuleType.INTERACTION,
                description=f"{action.upper()} action might have {category} effects under specific conditions",
                confidence=0.4,  # Lower confidence for exploratory
                evidence_count=1,
                needs_testing=f"Test {action} in different game contexts to identify {category} conditions",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"🔍 New exploratory {category} hypothesis: {hypothesis.description}")

    def _create_transformation_hypothesis(self, action: str, effect: str):
        """Create hypothesis about object transformation mechanics"""
        rule_id = f"TRANSFORMATION_{action.replace(' ', '_').upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.STATE_CHANGE,
                description=f"{action} can transform objects (color, shape, state changes)",
                confidence=0.6,
                evidence_count=1,
                needs_testing=f"Test {action} with different objects to understand transformation patterns",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"🔄 New transformation hypothesis: {hypothesis.description}")

    def _create_object_manipulation_hypothesis(self, action: str, effect: str):
        """Create hypothesis about object manipulation mechanics"""
        rule_id = f"OBJECT_MANIP_{action.replace(' ', '_').upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.INTERACTION,
                description=f"{action} can manipulate or interact with game objects",
                confidence=0.7,
                evidence_count=1,
                needs_testing=f"Experiment with {action} on different types of objects",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"🎯 New object manipulation hypothesis: {hypothesis.description}")

    def _create_environment_hypothesis(self, action: str, effect: str):
        """Create hypothesis about environmental interaction mechanics"""
        rule_id = f"ENVIRONMENT_{action.replace(' ', '_').upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.INTERACTION,
                description=f"{action} interacts with environmental elements (doors, keys, buttons, etc.)",
                confidence=0.65,
                evidence_count=1,
                needs_testing=f"Test {action} with various environmental objects",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"🏗️ New environment interaction hypothesis: {hypothesis.description}")

    def _create_timing_hypothesis(self, action: str, effect: str):
        """Create hypothesis about timing and sequence mechanics"""
        rule_id = f"TIMING_{action.replace(' ', '_').upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.STATE_CHANGE,
                description=f"{action} has timing-dependent or sequence-dependent effects",
                confidence=0.55,
                evidence_count=1,
                needs_testing=f"Test {action} timing variations and action sequences",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"⏱️ New timing/sequence hypothesis: {hypothesis.description}")

    def _create_spatial_hypothesis(self, action: str, effect: str):
        """Create hypothesis about spatial relationship mechanics"""
        rule_id = f"SPATIAL_{action.replace(' ', '_').upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.MOVEMENT,
                description=f"{action} affects spatial relationships and positioning",
                confidence=0.6,
                evidence_count=1,
                needs_testing=f"Test {action} in different spatial contexts and positions",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"📍 New spatial relationship hypothesis: {hypothesis.description}")

    def _create_general_hypothesis(self, action: str, effect: str):
        """Create general hypothesis for unmapped patterns - CATCH-ALL"""
        rule_id = f"GENERAL_{action.replace(' ', '_').upper()}_{len(self.confirmed_rules) + len(self.active_hypotheses)}"

        if rule_id not in self.active_hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=rule_id,
                rule_type=RuleType.STATE_CHANGE,
                description=f"{action} has observable effects requiring further investigation",
                confidence=0.3,  # Low confidence for general catch-all
                evidence_count=1,
                needs_testing=f"Investigate specific conditions and contexts for {action} effects",
            )
            self.active_hypotheses[rule_id] = hypothesis
            print(f"❓ New general hypothesis: {hypothesis.description}")

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
        """Check if any hypotheses should be promoted to confirmed rules - RELAXED CRITERIA"""
        hypotheses_to_promote = []

        for hyp in self.active_hypotheses.values():
            # RELAXED PROMOTION CRITERIA: Make it easier to promote hypotheses
            # OLD: confidence >= 0.8 and evidence_count >= 3 (too strict)
            # NEW: Multiple pathways for promotion
            promote = False
            
            # Path 1: High confidence with moderate evidence
            if hyp.confidence >= 0.7 and hyp.evidence_count >= 2:
                promote = True
                print(f"🚀 Promoting {hyp.hypothesis_id}: High confidence pathway (conf={hyp.confidence:.2f}, evidence={hyp.evidence_count})")
                
            # Path 2: Moderate confidence with strong evidence  
            elif hyp.confidence >= 0.6 and hyp.evidence_count >= 4:
                promote = True
                print(f"🚀 Promoting {hyp.hypothesis_id}: Strong evidence pathway (conf={hyp.confidence:.2f}, evidence={hyp.evidence_count})")
                
            # Path 3: Consistent performance over time
            elif hyp.confidence >= 0.5 and hyp.evidence_count >= 6:
                promote = True
                print(f"🚀 Promoting {hyp.hypothesis_id}: Consistency pathway (conf={hyp.confidence:.2f}, evidence={hyp.evidence_count})")
            
            if promote:
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
        """Generate AGGRESSIVE recommendations for LOGOS - EXPERIMENTAL APPROACH"""
        recommendations = []

        # HIGH PRIORITY: Test ALL active hypotheses (not just low confidence ones)
        hypothesis_tests = []
        for hyp in self.active_hypotheses.values():
            hypothesis_tests.append(hyp.needs_testing)
        
        # Add top 3 hypothesis tests
        recommendations.extend(hypothesis_tests[:3])

        # AGGRESSIVE EXPERIMENTATION: Suggest untested action combinations
        all_actions = ["up", "down", "left", "right", "space", "click"]
        tested_actions = set()
        
        # Extract tested actions from existing rules/hypotheses
        for rule in list(self.confirmed_rules.values()) + list(self.active_hypotheses.values()):
            for action in all_actions:
                if action.lower() in rule.description.lower():
                    tested_actions.add(action)
        
        # Recommend testing unexplored actions
        untested_actions = [action for action in all_actions if action not in tested_actions]
        for action in untested_actions:
            recommendations.append(f"EXPERIMENT: Try {action} action in current context - unexplored potential")

        # EXPLOIT confirmed high-confidence rules
        for rule in self.confirmed_rules.values():
            if rule.confidence > 0.7:  # Lowered from 0.8
                if rule.rule_type == RuleType.MOVEMENT:
                    action = rule.description.split()[0].lower()
                    recommendations.append(f"EXPLOIT: Use {action} movement (confidence {rule.confidence:.2f})")
                elif rule.rule_type == RuleType.INTERACTION:
                    recommendations.append(f"EXPLOIT: {rule.description[:50]} (proven effective)")
                
        # EXPLORE promising medium-confidence rules
        for rule in self.confirmed_rules.values():
            if 0.5 <= rule.confidence <= 0.7:
                recommendations.append(f"EXPLORE: Test {rule.description[:40]} (needs more evidence)")

        # SEQUENCE EXPERIMENTATION: Suggest action sequences
        if len(self.confirmed_rules) >= 2:
            reliable_actions = []
            for rule in self.confirmed_rules.values():
                if rule.confidence > 0.6 and rule.rule_type in [RuleType.MOVEMENT, RuleType.INTERACTION]:
                    action_words = rule.description.split()
                    for action in all_actions:
                        if action.lower() in " ".join(action_words[:3]).lower():
                            reliable_actions.append(action)
                            break
            
            if len(reliable_actions) >= 2:
                recommendations.append(f"SEQUENCE: Try combining {reliable_actions[0]} + {reliable_actions[1]} for compound effects")

        # PATTERN BREAKING: If too many failed attempts recently
        recent_failed = sum(1 for rule in self.confirmed_rules.values() if rule.confidence < 0.5)
        if recent_failed > 2:
            recommendations.append("BREAK PATTERN: Try completely different approach - current strategy may be stuck")

        # CURIOSITY DRIVEN: Always suggest at least one experimental action
        if len(recommendations) < 8:
            recommendations.append("CURIOSITY: Try the action you've used least recently")
            recommendations.append("BOLD MOVE: Attempt a high-risk action for potential breakthrough")

        return recommendations[:10]  # Increased from 5 to 10 recommendations

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
            return (
                "score" in effect.lower()
                or "level" in effect.lower()
                or "progress" in effect.lower()
            )
        elif hypothesis.rule_type == RuleType.CONSTRAINT:
            return "no effect" in effect.lower() or "blocked" in effect.lower()
        return True  # Default to supporting

    def _find_similar_hypothesis(
        self, action: str, rule_type: RuleType
    ) -> Optional[Hypothesis]:
        """Find existing hypothesis that covers the same action and rule type"""
        action_word = action.split()[0].lower()

        for hypothesis in self.active_hypotheses.values():
            if (
                hypothesis.rule_type == rule_type
                and action_word in hypothesis.description.lower()
            ):
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

    # ENHANCED ROBUSTNESS METHODS

    def _update_rule_performance_metrics(self):
        """Update performance metrics for all rules based on recent performance"""
        for rule_id, rule in self.confirmed_rules.items():
            if rule_id not in self.rule_success_history:
                self.rule_success_history[rule_id] = []

            # Calculate precision: successes / total attempts
            if len(self.rule_success_history[rule_id]) > 0:
                precision = sum(self.rule_success_history[rule_id]) / len(
                    self.rule_success_history[rule_id]
                )
            else:
                precision = 0.5  # Neutral if no data

            # Calculate consistency: how stable the rule performance is
            if len(self.rule_success_history[rule_id]) >= 3:
                recent_results = self.rule_success_history[rule_id][
                    -5:
                ]  # Last 5 results
                consistency = 1.0 - (
                    sum([abs(r - precision) for r in recent_results])
                    / len(recent_results)
                )
            else:
                consistency = 0.5

            # Update rule's actual success rate
            rule.success_rate = precision

            # Store performance metrics
            self.rule_performance_metrics[rule_id] = {
                "precision": precision,
                "consistency": consistency,
                "total_tests": len(self.rule_success_history[rule_id]),
                "recent_trend": "stable",  # Could be enhanced with trend analysis
            }

            print(
                f"📊 Rule {rule_id} performance: precision={precision:.2f}, consistency={consistency:.2f}"
            )

    def _apply_gradual_degradation(self):
        """Apply GENTLE confidence degradation to rules - PRESERVE LEARNED KNOWLEDGE"""
        current_turn = self.turn_counter

        for rule_id, rule in self.confirmed_rules.items():
            # LEVEL-PROVEN RULES: Highly resistant to degradation
            if rule.level_proven:
                # Extract turn number from last_confirmed string
                try:
                    last_confirmed_turn = (
                        int(rule.last_confirmed.split()[-1]) if rule.last_confirmed else 0
                    )
                except (ValueError, IndexError):
                    last_confirmed_turn = 0

                turns_since_confirmation = current_turn - last_confirmed_turn
                
                # Level-proven rules are EXTREMELY resistant to degradation
                if turns_since_confirmation > 25:  # Much longer grace period for proven rules
                    # MINIMAL degradation for level-proven rules
                    degradation_rate = 0.001 * (turns_since_confirmation - 25)  # 0.1% per turn
                    max_degradation = 0.01  # Max 1% degradation per turn
                    degradation_amount = min(max_degradation, degradation_rate)

                    # Apply minimal degradation with very high minimum threshold
                    old_confidence = rule.confidence
                    rule.confidence = max(
                        0.7, rule.confidence - degradation_amount  # Level-proven rules never go below 0.7
                    )

                    if old_confidence != rule.confidence:
                        print(
                            f"🔥 LEVEL-PROVEN Rule {rule_id} barely degraded: {old_confidence:.2f} -> {rule.confidence:.2f} (etched in memory!)"
                        )
                continue  # Skip normal degradation for level-proven rules
            
            # NORMAL RULES: Standard gentle degradation
            # Extract turn number from last_confirmed string
            try:
                last_confirmed_turn = (
                    int(rule.last_confirmed.split()[-1]) if rule.last_confirmed else 0
                )
            except (ValueError, IndexError):
                last_confirmed_turn = 0

            turns_since_confirmation = current_turn - last_confirmed_turn

            # MUCH MORE GENTLE DEGRADATION - Rules should persist longer
            # OLD: Started degrading after 5 turns at 2% per turn
            # NEW: Start degrading after 10 turns at much lower rates
            
            if turns_since_confirmation > 10:  # Wait longer before degrading
                # Much gentler degradation rates based on rule strength
                if rule.confidence >= 0.8:
                    # High confidence rules degrade very slowly
                    degradation_rate = 0.005 * (turns_since_confirmation - 10)  # 0.5% per turn
                    max_degradation = 0.03  # Max 3% degradation
                elif rule.confidence >= 0.6:
                    # Medium confidence rules degrade slowly
                    degradation_rate = 0.01 * (turns_since_confirmation - 10)  # 1% per turn  
                    max_degradation = 0.05  # Max 5% degradation
                else:
                    # Lower confidence rules can degrade more
                    degradation_rate = 0.015 * (turns_since_confirmation - 10)  # 1.5% per turn
                    max_degradation = 0.08  # Max 8% degradation
                
                degradation_amount = min(max_degradation, degradation_rate)

                # Apply degradation with higher minimum threshold
                old_confidence = rule.confidence
                rule.confidence = max(
                    0.4, rule.confidence - degradation_amount  # Don't go below 0.4 (was 0.3)
                )

                if old_confidence != rule.confidence:
                    print(
                        f"📉 Rule {rule_id} gently degraded: {old_confidence:.2f} -> {rule.confidence:.2f} (no confirmation for {turns_since_confirmation} turns)"
                    )

    def _cross_validate_rules(self):
        """Perform cross-validation of rules against each other for consistency"""
        rule_ids = list(self.confirmed_rules.keys())

        for i, rule_a_id in enumerate(rule_ids):
            for rule_b_id in rule_ids[i + 1 :]:
                rule_a = self.confirmed_rules[rule_a_id]
                rule_b = self.confirmed_rules[rule_b_id]

                # Check for logical consistency between rules
                consistency_score = self._check_rule_consistency(rule_a, rule_b)

                # Store cross-validation result
                if rule_a_id not in self.cross_validation_results:
                    self.cross_validation_results[rule_a_id] = {}
                self.cross_validation_results[rule_a_id][rule_b_id] = {
                    "consistency_score": consistency_score,
                    "last_checked": f"Turn {self.turn_counter}",
                }

                # If rules are highly inconsistent, reduce confidence in the weaker rule
                if consistency_score < 0.3:  # Low consistency threshold
                    weaker_rule = (
                        rule_a if rule_a.confidence < rule_b.confidence else rule_b
                    )
                    weaker_rule_id = (
                        rule_a_id
                        if rule_a.confidence < rule_b.confidence
                        else rule_b_id
                    )

                    old_confidence = weaker_rule.confidence
                    weaker_rule.confidence = max(0.2, weaker_rule.confidence - 0.05)

                    print(
                        f"⚠️ Rule inconsistency detected between {rule_a_id} and {rule_b_id}"
                    )
                    print(
                        f"   Reduced confidence in {weaker_rule_id}: {old_confidence:.2f} -> {weaker_rule.confidence:.2f}"
                    )

    def _check_rule_consistency(self, rule_a: GameRule, rule_b: GameRule) -> float:
        """Check logical consistency between two rules"""
        # Simplified consistency check based on rule types and descriptions

        # Same type rules should be compatible
        if rule_a.rule_type == rule_b.rule_type:
            # Check for contradictory descriptions (simplified)
            desc_a = rule_a.description.lower()
            desc_b = rule_b.description.lower()

            # Look for contradictory statements
            contradictory_pairs = [
                ("can", "cannot"),
                ("always", "never"),
                ("increase", "decrease"),
                ("move", "blocked"),
                ("activate", "deactivate"),
            ]

            contradiction_found = False
            for pos_word, neg_word in contradictory_pairs:
                if pos_word in desc_a and neg_word in desc_b:
                    contradiction_found = True
                    break
                if neg_word in desc_a and pos_word in desc_b:
                    contradiction_found = True
                    break

            return 0.2 if contradiction_found else 0.8

        # Different types are generally compatible
        return 0.7

    def _create_structured_sophia_data(
        self, response_data: Dict
    ) -> SophiaStructuredData:
        """Create structured data for LOGOS consumption"""

        # Convert rules to structured format
        structured_confirmed_rules = []
        for rule_dict in response_data.get("confirmed_rules", []):
            rule_id = rule_dict.get("rule_id", "")
            original_rule = self.confirmed_rules.get(rule_id)

            if original_rule:
                # Get performance metrics
                metrics = self.rule_performance_metrics.get(rule_id, {})

                structured_rule = StructuredRule(
                    rule_id=rule_id,
                    rule_type=original_rule.rule_type.value,
                    description=original_rule.description,
                    confidence=original_rule.confidence,
                    evidence_count=original_rule.evidence_count,
                    success_rate=metrics.get("precision", 0.5),
                    last_confirmed=original_rule.last_confirmed,
                    supporting_evidence=original_rule.supporting_evidence,
                    contradicting_evidence=original_rule.contradicting_evidence,
                    context_conditions=[],  # Could be enhanced
                )
                structured_confirmed_rules.append(structured_rule)

        # Similar conversion for hypotheses
        structured_hypotheses = []
        for hyp_dict in response_data.get("active_hypotheses", []):
            hyp_id = hyp_dict.get("hypothesis_id", "")
            original_hyp = self.active_hypotheses.get(hyp_id)

            if original_hyp:
                structured_rule = StructuredRule(
                    rule_id=hyp_id,
                    rule_type=original_hyp.rule_type.value,
                    description=original_hyp.description,
                    confidence=original_hyp.confidence,
                    evidence_count=original_hyp.evidence_count,
                    success_rate=0.5,  # Neutral for hypotheses
                    last_confirmed="Never (hypothesis)",
                    supporting_evidence=[],
                    contradicting_evidence=[],
                    context_conditions=[],
                )
                structured_hypotheses.append(structured_rule)

        # Extract most reliable actions
        most_reliable_actions = []
        for rule in structured_confirmed_rules:
            if rule.confidence > 0.8 and rule.success_rate > 0.7:
                # Extract action from rule description
                action_words = ["up", "down", "left", "right", "space", "click"]
                for word in action_words:
                    if word.lower() in rule.description.lower():
                        most_reliable_actions.append(word)
                        break

        # Get game objective confidence
        objective_confidence = 0.5
        if self.game_objective:
            objective_confidence = self.game_objective.confidence

        return SophiaStructuredData(
            confirmed_rules=structured_confirmed_rules,
            active_hypotheses=structured_hypotheses,
            most_reliable_actions=list(set(most_reliable_actions)),  # Remove duplicates
            recommended_tests=response_data.get("recommendations_for_logos", [])[
                :3
            ],  # Top 3
            game_objective_confidence=objective_confidence,
            turn_analysis={
                "total_rules": len(structured_confirmed_rules),
                "total_hypotheses": len(structured_hypotheses),
                "avg_rule_confidence": sum(
                    r.confidence for r in structured_confirmed_rules
                )
                / max(1, len(structured_confirmed_rules)),
                "performance_trend": "stable",  # Could be enhanced
            },
        )

    # --- Gemini integration helpers ---
    def _build_sophia_prompt(
        self, action_executed: str, aisthesis_analysis: str, response_data: Dict
    ) -> str:
        """Build Sophia's prompt by reading sophia.md and adding current context.
        Mirrors the approach used in LOGOS, but tailored for Sophia's reasoning output.
        """
        # Load Sophia guidance content
        sophia_content = ""
        try:
            with open(
                "agents/tomas_engine/nucleus/sophia.md", "r", encoding="utf-8"
            ) as f:
                sophia_content = f.read()
        except FileNotFoundError:
            print("⚠️ Warning: sophia.md file not found")
            sophia_content = "SOPHIA - Game Rules Scientist"
        except Exception as e:
            print(f"⚠️ Error reading sophia.md: {e}")
            sophia_content = "SOPHIA - Game Rules Scientist"

        # Compact snapshot from current knowledge
        confirmed_rules = response_data.get("confirmed_rules", [])[:5]
        active_hypotheses = response_data.get("active_hypotheses", [])[:5]
        recommendations = response_data.get("recommendations_for_logos", [])[:5]
        objective = response_data.get("game_objective_theory") or {}
        insights = response_data.get("immediate_insights", [])[:3]
        contradicted = response_data.get("contradicted_theories", [])[-2:]

        snapshot = {
            "turn": self.turn_counter,
            "confirmed_rules": [
                {"desc": r.get("description"), "conf": r.get("confidence")}
                for r in confirmed_rules
            ],
            "active_hypotheses": [
                {
                    "desc": h.get("description"),
                    "conf": h.get("confidence"),
                    "needs_testing": h.get("needs_testing"),
                }
                for h in active_hypotheses
            ],
            "objective": {
                "primary_goal": objective.get("primary_goal"),
                "confidence": objective.get("confidence"),
            },
            "insights": insights,
            "recommendations": recommendations,
            "contradicted": [
                {"theory": c.get("theory"), "why": c.get("contradiction")}
                for c in contradicted
            ],
        }

        snapshot_str = json.dumps(snapshot, ensure_ascii=False)

        # Add memory context (relevant experiences)
        memory = SharedMemory.get_instance()
        relevant_exp = memory.get_relevant_experience(aisthesis_analysis[:120])
        memory_section = (
            f"\n\n**Shared Memory:**\n{relevant_exp}\n" if relevant_exp else ""
        )

        # Compose final prompt combining the guide + current observation + compact knowledge
        prompt = f"""
{sophia_content}

**Turn Observation:**
- Action: {action_executed}
- Effect: {aisthesis_analysis[:400]}

**Current Knowledge (compact JSON):**
{snapshot_str}
{memory_section}

Now, as SOPHIA, produce a very concise reasoning to guide LOGOS next turn:
- Highlight the key observation from this turn (action -> effect)
- State which rules were reinforced or contradicted
- Propose 1-2 concrete hypothesis tests with exact conditions
- Give 1-2 immediate, high-value recommendations

Constraints:
- Under 120 words
- Use bullet points only (no headers)
- Return only the reasoning text
"""

        return prompt

    def _enhance_summary_with_gemini(
        self,
        action_executed: str,
        aisthesis_analysis: str,
        response_data: Dict,
        fallback_summary: str,
    ) -> str:
        """Use Gemini to produce a more useful, concise reasoning for LOGOS.
        Falls back to the local summary on any error or if Gemini is unavailable.
        """
        if not self.gemini_service:
            return fallback_summary

        try:
            prompt = self._build_sophia_prompt(
                action_executed, aisthesis_analysis, response_data
            )
            gemini_resp = self.gemini_service.generate_text_sync(
                prompt=prompt,
                nuclei="sophia",
            )

            content = (gemini_resp.content or "").strip()
            # Basic sanity check: avoid returning empty or extremely long output
            if not content:
                return fallback_summary
            if len(content) > 1200:  # defensive cap
                return content[:1200]
            return content
        except Exception as error:
            print(
                f"⚠️ SOPHIA: Gemini enhancement failed, using fallback. Reason: {error}"
            )
            return fallback_summary

    def _check_for_level_completion_and_consolidate(self, observation: Dict):
        """Check for level completion by comparing scores and consolidate successful rules"""
        if len(self.observations) < 2:
            return  # Need at least 2 observations to compare
        
        current_effect = observation.get("effect", "").lower()
        previous_obs = self.observations[-2]
        previous_effect = previous_obs.get("effect", "").lower()
        
        # Look for score increase or explicit level-up indicators
        level_up_detected = False
        
        # ONLY trust AISTHESIS explicit level-up notifications
        # Do NOT try to detect level-up from score changes - AISTHESIS handles that correctly
        if any(keyword in current_effect for keyword in [
            "🎉 level up", "level up!", "level completed", "next level", "level won",
            "🎉 level_up", "level_up detected", "successfully completed level"
        ]):
            level_up_detected = True
            print("🎉 LEVEL UP detected by AISTHESIS keywords!")
        else:
            # No level-up detected - score increases during gameplay are normal
            level_up_detected = False
        
        # Method 3: Environment reset indicators (new level started)
        if not level_up_detected:
            if any(keyword in current_effect for keyword in ["reset", "new level", "fresh start", "level began"]):
                # Check if this follows a successful action sequence
                recent_successful_actions = self._count_recent_successful_actions()
                if recent_successful_actions >= 2:  # At least 2 successful actions recently
                    level_up_detected = True
                    print("🎉 LEVEL UP detected by environment reset after successful actions!")
        
        if level_up_detected:
            self._consolidate_proven_rules()
    
    def _count_recent_successful_actions(self) -> int:
        """Count recent actions that had positive effects"""
        if len(self.observations) < 3:
            return 0
        
        recent_obs = self.observations[-3:]  # Last 3 observations
        successful_count = 0
        
        for obs in recent_obs:
            effect = obs.get("effect", "").lower()
            # Consider action successful if it caused meaningful change
            if any(keyword in effect for keyword in [
                "moved", "changed", "activated", "triggered", "opened", "closed",
                "score", "progress", "unlocked", "collected", "completed"
            ]) and "no effect" not in effect:
                successful_count += 1
        
        return successful_count
    
    def _consolidate_proven_rules(self):
        """Mark recently successful rules as level-proven and boost their confidence"""
        print("🔥 CONSOLIDATING PROVEN RULES - Level completed successfully!")
        
        # Look at rules that were confirmed in recent turns (last 10 turns)
        current_turn = self.turn_counter
        consolidation_window = 10
        
        consolidated_count = 0
        
        for rule_id, rule in self.confirmed_rules.items():
            # Check if rule was confirmed recently
            try:
                last_confirmed_turn = (
                    int(rule.last_confirmed.split()[-1]) if rule.last_confirmed else 0
                )
            except (ValueError, IndexError):
                last_confirmed_turn = 0
            
            turns_since_confirmation = current_turn - last_confirmed_turn
            
            # If rule was confirmed recently and has decent confidence, consolidate it
            if turns_since_confirmation <= consolidation_window and rule.confidence >= 0.5:
                # Mark as level-proven
                rule.level_proven = True
                
                # Boost confidence significantly
                old_confidence = rule.confidence
                rule.confidence = min(1.0, rule.confidence + 0.15)  # Big boost for proven rules
                
                # Add special evidence
                rule.supporting_evidence.append(
                    f"Turn {current_turn}: LEVEL COMPLETED - Rule proven effective for level progression"
                )
                
                consolidated_count += 1
                print(f"🏆 Rule {rule_id} CONSOLIDATED: confidence {old_confidence:.2f} → {rule.confidence:.2f}")
        
        # Also promote high-performing hypotheses when level is completed
        hypotheses_to_consolidate = []
        for hyp_id, hyp in self.active_hypotheses.items():
            if hyp.confidence >= 0.6 and hyp.evidence_count >= 2:
                hypotheses_to_consolidate.append(hyp)
        
        for hyp in hypotheses_to_consolidate:
            # Promote to rule and immediately mark as level-proven
            self._promote_hypothesis_to_rule(hyp)
            if hyp.hypothesis_id in self.confirmed_rules:
                self.confirmed_rules[hyp.hypothesis_id].level_proven = True
                self.confirmed_rules[hyp.hypothesis_id].confidence = min(1.0, self.confirmed_rules[hyp.hypothesis_id].confidence + 0.1)
                print(f"🚀 Hypothesis {hyp.hypothesis_id} PROMOTED and CONSOLIDATED!")
                consolidated_count += 1
        
        if consolidated_count > 0:
            print(f"✨ SUCCESS! {consolidated_count} rules consolidated and etched into memory!")
        else:
            print("⚠️ No rules met consolidation criteria - need more evidence for future level completions")
