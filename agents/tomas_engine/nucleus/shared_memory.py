import time
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import math


@dataclass
class MemoryExperience:
    """Enhanced experience structure with clustering and temporal data"""
    context: str
    action: str
    outcome: str
    success: bool
    timestamp: float
    turn_number: int
    confidence: float
    similarity_cluster: Optional[int] = None
    relevance_score: float = 0.0
    usage_count: int = 0
    last_accessed: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def get_age_hours(self) -> float:
        """Get age of experience in hours"""
        return (time.time() - self.timestamp) / 3600
    
    def get_age_turns(self, current_turn: int) -> int:
        """Get age of experience in turns"""
        return max(0, current_turn - self.turn_number)


@dataclass 
class ExperienceCluster:
    """Cluster of similar experiences"""
    cluster_id: int
    center_keywords: List[str]
    experiences: List[MemoryExperience]
    success_rate: float
    last_updated: float
    confidence: float
    
    def update_metrics(self):
        """Update cluster metrics based on contained experiences"""
        if not self.experiences:
            self.success_rate = 0.5
            self.confidence = 0.0
            return
        
        # Calculate success rate
        successes = sum(1 for exp in self.experiences if exp.success)
        self.success_rate = successes / len(self.experiences)
        
        # Calculate confidence based on experience count and recency
        recent_experiences = [exp for exp in self.experiences if exp.get_age_hours() < 24]
        self.confidence = min(1.0, (len(self.experiences) * 0.1) + (len(recent_experiences) * 0.2))
        
        self.last_updated = time.time()


class AdvancedSharedMemory:
    """Advanced shared memory system with clustering, contextual relevance, and temporal prioritization"""

    _instance = None

    def __init__(self):
        if AdvancedSharedMemory._instance is None:
            # Core memory storage
            self.experiences: List[MemoryExperience] = []
            self.experience_clusters: Dict[int, ExperienceCluster] = {}
            self.next_cluster_id = 0
            
            # Enhanced tracking
            self.keyword_frequency: Dict[str, int] = defaultdict(int)
            self.action_success_rates: Dict[str, List[bool]] = defaultdict(list)
            self.context_patterns: Dict[str, List[str]] = defaultdict(list)  # context -> successful actions
            
            # Temporal management
            self.current_turn = 0
            self.last_cleanup = time.time()
            self.cleanup_interval = 300  # 5 minutes
            
            # Configuration
            self.max_experiences = 200  # Increased from 50
            self.max_failures = 50      # Increased from 20
            self.clustering_threshold = 0.6
            self.temporal_decay_factor = 0.95  # Per hour
            
            AdvancedSharedMemory._instance = self

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls()
        return cls._instance

    def set_current_turn(self, turn_number: int):
        """Update current turn number for temporal tracking"""
        self.current_turn = turn_number

    def remember_success(self, context: str, action: str, outcome: str, confidence: float = 1.0):
        """Enhanced success memory with clustering and temporal data"""
        experience = MemoryExperience(
            context=context,
            action=action,
            outcome=outcome,
            success=True,
            timestamp=time.time(),
            turn_number=self.current_turn,
            confidence=confidence
        )
        
        self._add_experience(experience)
        self._update_action_success_rates(action, True)
        self._update_context_patterns(context, action)
        
        print(f"📝 Recorded successful experience: {action} in context '{context[:50]}...'")

    def remember_failure(self, context: str, action: str, reason: str, confidence: float = 1.0):
        """Enhanced failure memory with clustering"""
        experience = MemoryExperience(
            context=f"FAILURE: {context}",
            action=action,
            outcome=f"Failed: {reason}",
            success=False,
            timestamp=time.time(),
            turn_number=self.current_turn,
            confidence=confidence
        )
        
        self._add_experience(experience)
        self._update_action_success_rates(action, False)
        
        print(f"❌ Recorded failed experience: {action} failed because {reason}")

    def _add_experience(self, experience: MemoryExperience):
        """Add experience with clustering and size management"""
        # Find or create cluster
        cluster_id = self._find_or_create_cluster(experience)
        experience.similarity_cluster = cluster_id
        
        # Add to experiences
        self.experiences.append(experience)
        
        # Update keyword frequency
        self._update_keyword_frequency(experience.context)
        
        # Manage memory size
        self._manage_memory_size()
        
        # Periodic cleanup
        self._periodic_cleanup()

    def _find_or_create_cluster(self, experience: MemoryExperience) -> int:
        """Find similar cluster or create new one"""
        keywords = self._extract_keywords(experience.context)
        best_cluster_id = None
        best_similarity = 0.0
        
        # Find most similar cluster
        for cluster_id, cluster in self.experience_clusters.items():
            similarity = self._calculate_keyword_similarity(keywords, cluster.center_keywords)
            if similarity > best_similarity and similarity >= self.clustering_threshold:
                best_similarity = similarity
                best_cluster_id = cluster_id
        
        if best_cluster_id is not None:
            # Add to existing cluster
            self.experience_clusters[best_cluster_id].experiences.append(experience)
            self.experience_clusters[best_cluster_id].update_metrics()
            return best_cluster_id
        else:
            # Create new cluster
            new_cluster = ExperienceCluster(
                cluster_id=self.next_cluster_id,
                center_keywords=keywords,
                experiences=[experience],
                success_rate=1.0 if experience.success else 0.0,
                last_updated=time.time(),
                confidence=0.1  # Start with low confidence
            )
            self.experience_clusters[self.next_cluster_id] = new_cluster
            cluster_id = self.next_cluster_id
            self.next_cluster_id += 1
            return cluster_id

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        # Simple keyword extraction - could be enhanced with NLP
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had'}
        
        words = text.lower().split()
        keywords = []
        
        for word in words[:10]:  # Limit to first 10 words
            # Clean word
            clean_word = ''.join(c for c in word if c.isalnum())
            
            if len(clean_word) >= 3 and clean_word not in stopwords:
                keywords.append(clean_word)
        
        return keywords[:5]  # Top 5 keywords

    def _calculate_keyword_similarity(self, keywords1: List[str], keywords2: List[str]) -> float:
        """Calculate Jaccard similarity between keyword sets"""
        if not keywords1 or not keywords2:
            return 0.0
        
        set1 = set(keywords1)
        set2 = set(keywords2)
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0

    def _update_keyword_frequency(self, context: str):
        """Update keyword frequency tracking"""
        keywords = self._extract_keywords(context)
        for keyword in keywords:
            self.keyword_frequency[keyword] += 1

    def _update_action_success_rates(self, action: str, success: bool):
        """Track success rates for different actions"""
        self.action_success_rates[action].append(success)
        # Keep only recent results
        if len(self.action_success_rates[action]) > 20:
            self.action_success_rates[action] = self.action_success_rates[action][-20:]

    def _update_context_patterns(self, context: str, action: str):
        """Track which actions work in which contexts"""
        context_signature = ' '.join(self._extract_keywords(context))
        self.context_patterns[context_signature].append(action)

    def get_relevant_experience(self, current_context: str, limit: int = 5) -> str:
        """Get contextually relevant experiences with advanced scoring"""
        if not current_context or not self.experiences:
            return ""
        
        # Calculate relevance scores for all experiences
        scored_experiences = []
        current_keywords = self._extract_keywords(current_context)
        
        for exp in self.experiences:
            relevance_score = self._calculate_contextual_relevance(exp, current_keywords)
            temporal_weight = self._calculate_temporal_weight(exp)
            cluster_weight = self._calculate_cluster_weight(exp)
            
            # Combined score
            final_score = (relevance_score * 0.5) + (temporal_weight * 0.3) + (cluster_weight * 0.2)
            
            if final_score > 0.1:  # Minimum relevance threshold
                scored_experiences.append((exp, final_score))
        
        # Sort by relevance and get top experiences
        scored_experiences.sort(key=lambda x: x[1], reverse=True)
        top_experiences = scored_experiences[:limit]
        
        # Format results
        result_lines = []
        for exp, score in top_experiences:
            # Mark recently accessed experiences
            exp.last_accessed = time.time()
            exp.usage_count += 1
            
            success_marker = "✅" if exp.success else "❌"
            confidence_indicator = f"({exp.confidence:.1f})" if exp.confidence < 1.0 else ""
            
            result_lines.append(
                f"{success_marker} {exp.action} → {exp.outcome[:60]}{'...' if len(exp.outcome) > 60 else ''} {confidence_indicator}"
            )
        
        if result_lines:
            return f"🧠 RELEVANT PAST EXPERIENCES (top {len(result_lines)}):\n" + "\n".join(result_lines)
        else:
            return ""

    def _calculate_contextual_relevance(self, experience: MemoryExperience, current_keywords: List[str]) -> float:
        """Calculate how contextually relevant an experience is"""
        exp_keywords = self._extract_keywords(experience.context)
        keyword_similarity = self._calculate_keyword_similarity(current_keywords, exp_keywords)
        
        # Boost based on keyword frequency (rarer keywords are more meaningful)
        rarity_boost = 1.0
        for keyword in current_keywords:
            if keyword in exp_keywords:
                frequency = self.keyword_frequency.get(keyword, 1)
                # Inverse frequency weighting
                rarity_boost += 1.0 / math.log(frequency + 1)
        
        return keyword_similarity * min(2.0, rarity_boost)

    def _calculate_temporal_weight(self, experience: MemoryExperience) -> float:
        """Calculate temporal relevance weight (more recent = higher weight)"""
        age_hours = experience.get_age_hours()
        age_turns = experience.get_age_turns(self.current_turn)
        
        # Exponential decay based on time
        time_weight = self.temporal_decay_factor ** age_hours
        
        # Exponential decay based on turns
        turn_weight = 0.95 ** age_turns
        
        return (time_weight + turn_weight) / 2

    def _calculate_cluster_weight(self, experience: MemoryExperience) -> float:
        """Calculate weight based on cluster performance"""
        if experience.similarity_cluster is None:
            return 0.5
        
        cluster = self.experience_clusters.get(experience.similarity_cluster)
        if not cluster:
            return 0.5
        
        # Weight based on cluster success rate and confidence
        return (cluster.success_rate * 0.7) + (cluster.confidence * 0.3)

    def get_failure_warnings(self, current_context: str, limit: int = 3) -> str:
        """Get contextually relevant failure warnings"""
        if not current_context:
            return ""
        
        current_keywords = self._extract_keywords(current_context)
        relevant_failures = []
        
        # Find relevant failures
        for exp in self.experiences:
            if not exp.success:
                relevance = self._calculate_contextual_relevance(exp, current_keywords)
                temporal_weight = self._calculate_temporal_weight(exp)
                
                if relevance > 0.3:  # Higher threshold for failures
                    combined_score = (relevance * 0.7) + (temporal_weight * 0.3)
                    relevant_failures.append((exp, combined_score))
        
        # Sort and format
        relevant_failures.sort(key=lambda x: x[1], reverse=True)
        
        if relevant_failures:
            warning_lines = []
            for exp, score in relevant_failures[:limit]:
                warning_lines.append(f"⚠️ Avoid {exp.action}: {exp.outcome}")
            
            return "🚨 FAILURE WARNINGS:\n" + "\n".join(warning_lines)
        
        return ""

    def get_action_recommendations(self, current_context: str, limit: int = 3) -> List[str]:
        """Get action recommendations based on context patterns and success rates"""
        current_keywords = self._extract_keywords(current_context)
        context_signature = ' '.join(current_keywords)
        
        action_scores = defaultdict(float)
        
        # Score actions based on context patterns
        for pattern_context, actions in self.context_patterns.items():
            pattern_keywords = pattern_context.split()
            similarity = self._calculate_keyword_similarity(current_keywords, pattern_keywords)
            
            if similarity > 0.3:
                for action in actions:
                    action_scores[action] += similarity
        
        # Boost scores based on overall action success rates
        for action, score in action_scores.items():
            if action in self.action_success_rates:
                success_rate = sum(self.action_success_rates[action]) / len(self.action_success_rates[action])
                action_scores[action] = score * (0.5 + success_rate * 0.5)
        
        # Sort and return top recommendations
        sorted_actions = sorted(action_scores.items(), key=lambda x: x[1], reverse=True)
        return [action for action, score in sorted_actions[:limit]]

    def _manage_memory_size(self):
        """Manage memory size by removing least relevant experiences"""
        if len(self.experiences) <= self.max_experiences:
            return
        
        # Score all experiences for removal (lower score = more likely to remove)
        removal_scores = []
        
        for i, exp in enumerate(self.experiences):
            # Factor in age, usage, and success
            age_penalty = exp.get_age_hours() * 0.1
            usage_bonus = exp.usage_count * 0.2
            success_bonus = 0.5 if exp.success else 0.0
            
            removal_score = age_penalty - usage_bonus - success_bonus
            removal_scores.append((i, removal_score, exp))
        
        # Sort by removal score (highest first = most likely to remove)
        removal_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Remove excess experiences
        to_remove = len(self.experiences) - self.max_experiences
        for i in range(to_remove):
            idx, score, exp = removal_scores[i]
            
            # Remove from cluster
            if exp.similarity_cluster is not None:
                cluster = self.experience_clusters.get(exp.similarity_cluster)
                if cluster and exp in cluster.experiences:
                    cluster.experiences.remove(exp)
                    cluster.update_metrics()
        
        # Remove from main list
        indices_to_remove = [removal_scores[i][0] for i in range(to_remove)]
        indices_to_remove.sort(reverse=True)  # Remove from end to avoid index shifting
        
        for idx in indices_to_remove:
            del self.experiences[idx]
        
        print(f"🧹 Cleaned up memory: removed {to_remove} old experiences")

    def _periodic_cleanup(self):
        """Perform periodic cleanup of clusters and data structures"""
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        # Remove empty clusters
        empty_clusters = [cid for cid, cluster in self.experience_clusters.items() if not cluster.experiences]
        for cid in empty_clusters:
            del self.experience_clusters[cid]
        
        # Clean up keyword frequency (remove very rare keywords)
        min_frequency = 2
        rare_keywords = [kw for kw, freq in self.keyword_frequency.items() if freq < min_frequency]
        for kw in rare_keywords:
            del self.keyword_frequency[kw]
        
        self.last_cleanup = current_time
        
        if empty_clusters or rare_keywords:
            print(f"🧹 Periodic cleanup: removed {len(empty_clusters)} empty clusters, {len(rare_keywords)} rare keywords")

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        successful_experiences = sum(1 for exp in self.experiences if exp.success)
        failed_experiences = len(self.experiences) - successful_experiences
        
        cluster_stats = []
        for cluster in self.experience_clusters.values():
            cluster_stats.append({
                "id": cluster.cluster_id,
                "size": len(cluster.experiences),
                "success_rate": cluster.success_rate,
                "confidence": cluster.confidence,
                "keywords": cluster.center_keywords
            })
        
        return {
            "total_experiences": len(self.experiences),
            "successful_experiences": successful_experiences,
            "failed_experiences": failed_experiences,
            "success_rate": successful_experiences / max(1, len(self.experiences)),
            "total_clusters": len(self.experience_clusters),
            "unique_keywords": len(self.keyword_frequency),
            "most_common_keywords": sorted(self.keyword_frequency.items(), key=lambda x: x[1], reverse=True)[:5],
            "action_success_rates": {action: sum(results)/len(results) for action, results in self.action_success_rates.items() if results},
            "cluster_details": cluster_stats[:5]  # Top 5 clusters
        }


# Maintain backwards compatibility
SharedMemory = AdvancedSharedMemory