"""
Shared data structures for communication between nuclei
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum


@dataclass
class StructuredObjectInfo:
    """Enhanced object information for inter-nuclei communication"""
    object_id: str
    shape: str
    color: str
    positions: List[Tuple[int, int]]
    bounds: Tuple[int, int, int, int]  # (min_row, max_row, min_col, max_col)
    region: str
    size: int
    center: Tuple[int, int]
    is_player: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "shape": self.shape,
            "color": self.color,
            "positions": self.positions,
            "bounds": self.bounds,
            "region": self.region,
            "size": self.size,
            "center": self.center,
            "is_player": self.is_player
        }


@dataclass
class AisthesisStructuredData:
    """Structured data from AISTHESIS analysis"""
    objects_before: List[StructuredObjectInfo]
    objects_after: List[StructuredObjectInfo]
    changed_objects: List[StructuredObjectInfo]
    unchanged_objects: List[StructuredObjectInfo]
    transformation_type: str  # "TRANSLATION", "ROTATION", "MATERIALIZATION", etc.
    progress_detected: bool
    is_level_transition: bool
    clickable_coordinates: List[Tuple[int, int]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "objects_before": [obj.to_dict() for obj in self.objects_before],
            "objects_after": [obj.to_dict() for obj in self.objects_after],
            "changed_objects": [obj.to_dict() for obj in self.changed_objects],
            "unchanged_objects": [obj.to_dict() for obj in self.unchanged_objects],
            "transformation_type": self.transformation_type,
            "progress_detected": self.progress_detected,
            "is_level_transition": self.is_level_transition,
            "clickable_coordinates": self.clickable_coordinates
        }


class RuleConfidenceLevel(Enum):
    HIGHLY_CONFIDENT = 0.9  # 5+ confirmations
    CONFIDENT = 0.7         # 3+ confirmations
    UNCERTAIN = 0.5         # 1-2 confirmations
    SPECULATIVE = 0.3       # hypothesis
    CONTRADICTED = 0.1      # evidence against


@dataclass
class StructuredRule:
    """Enhanced rule structure with validation metrics"""
    rule_id: str
    rule_type: str
    description: str
    confidence: float
    evidence_count: int
    success_rate: float  # New: Track actual success rate
    last_confirmed: str
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    context_conditions: List[str]  # New: When this rule applies
    
    def get_confidence_level(self) -> RuleConfidenceLevel:
        """Get categorical confidence level"""
        if self.confidence >= 0.9:
            return RuleConfidenceLevel.HIGHLY_CONFIDENT
        elif self.confidence >= 0.7:
            return RuleConfidenceLevel.CONFIDENT
        elif self.confidence >= 0.5:
            return RuleConfidenceLevel.UNCERTAIN
        elif self.confidence >= 0.3:
            return RuleConfidenceLevel.SPECULATIVE
        else:
            return RuleConfidenceLevel.CONTRADICTED


@dataclass
class SophiaStructuredData:
    """Structured data from SOPHIA analysis"""
    confirmed_rules: List[StructuredRule]
    active_hypotheses: List[StructuredRule]
    most_reliable_actions: List[str]  # Actions with highest success rate
    recommended_tests: List[str]
    game_objective_confidence: float
    turn_analysis: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "confirmed_rules": [rule.__dict__ for rule in self.confirmed_rules],
            "active_hypotheses": [hyp.__dict__ for hyp in self.active_hypotheses],
            "most_reliable_actions": self.most_reliable_actions,
            "recommended_tests": self.recommended_tests,
            "game_objective_confidence": self.game_objective_confidence,
            "turn_analysis": self.turn_analysis
        }


@dataclass
class PsychologyState:
    """Enhanced psychology state with memory"""
    # Current state
    current_state: str
    frustration: float
    confidence: float
    curiosity_level: float
    patience: float
    
    # Memory and history
    state_history: List[str]  # Last 10 states
    emotion_history: List[Dict[str, float]]  # Last 10 emotional states
    successful_patterns: List[str]  # Patterns that worked
    failed_patterns: List[str]  # Patterns that failed
    
    # Performance metrics
    recent_success_rate: float
    confidence_trend: str  # "increasing", "stable", "decreasing"
    
    def add_to_history(self, new_state: str, emotions: Dict[str, float]):
        """Add new state and emotions to history"""
        self.state_history.append(new_state)
        self.emotion_history.append(emotions)
        
        # Keep only last 10
        if len(self.state_history) > 10:
            self.state_history = self.state_history[-10:]
        if len(self.emotion_history) > 10:
            self.emotion_history = self.emotion_history[-10:]
    
    def get_emotional_stability(self) -> float:
        """Calculate emotional stability based on recent history"""
        if len(self.emotion_history) < 3:
            return 0.5
        
        # Calculate variance in recent emotions
        recent_frustrations = [e.get("frustration", 0.5) for e in self.emotion_history[-5:]]
        recent_confidences = [e.get("confidence", 0.5) for e in self.emotion_history[-5:]]
        
        frustration_variance = sum((f - sum(recent_frustrations)/len(recent_frustrations))**2 for f in recent_frustrations) / len(recent_frustrations)
        confidence_variance = sum((c - sum(recent_confidences)/len(recent_confidences))**2 for c in recent_confidences) / len(recent_confidences)
        
        # Lower variance = higher stability
        stability = 1.0 - min(1.0, (frustration_variance + confidence_variance) / 2)
        return stability


@dataclass
class ProgressAnalysis:
    """Multi-dimensional progress analysis"""
    progress_type: str  # MAJOR, MINOR, VALID_ACTION, NO_EFFECT
    
    # Spatial progress
    new_areas_discovered: bool
    player_position_change: bool
    object_positions_changed: int
    
    # Mechanical progress  
    new_interactions_discovered: bool
    rules_confirmed: int
    hypotheses_generated: int
    
    # Conceptual progress
    understanding_improved: bool
    objective_clarity_increased: bool
    strategy_refined: bool
    
    # Strategic progress
    sequence_effectiveness: float
    action_precision: float
    goal_proximity: float
    
    def get_overall_progress_score(self) -> float:
        """Calculate overall progress score (0-1)"""
        spatial_score = (
            (0.3 if self.new_areas_discovered else 0) +
            (0.2 if self.player_position_change else 0) +
            (min(0.2, self.object_positions_changed * 0.05))
        )
        
        mechanical_score = (
            (0.3 if self.new_interactions_discovered else 0) +
            (min(0.3, self.rules_confirmed * 0.1)) +
            (min(0.2, self.hypotheses_generated * 0.05))
        )
        
        conceptual_score = (
            (0.3 if self.understanding_improved else 0) +
            (0.3 if self.objective_clarity_increased else 0) +
            (0.2 if self.strategy_refined else 0)
        )
        
        strategic_score = (
            self.sequence_effectiveness * 0.4 +
            self.action_precision * 0.3 +
            self.goal_proximity * 0.3
        )
        
        # Weighted average
        total_score = (
            spatial_score * 0.25 +
            mechanical_score * 0.3 +
            conceptual_score * 0.25 +
            strategic_score * 0.2
        )
        
        return min(1.0, total_score)