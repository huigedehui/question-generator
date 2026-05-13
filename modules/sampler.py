"""Question sampler with weighted selection support."""
import random
from typing import List, Dict, Optional
from collections import defaultdict
from .logger import setup_logging

logger = setup_logging()


class QuestionSampler:
    """Sampler for selecting questions with various strategies."""
    
    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
    
    def filter_by_type(self, questions: List[Dict], q_type: str) -> List[Dict]:
        """Filter questions by type."""
        return [q for q in questions if q.get("type") == q_type]
    
    def sample_questions(self, questions: List[Dict], 
                        counts: Dict[str, int],
                        strategy: str = "random") -> Dict[str, List[Dict]]:
        """
        Sample questions by type.
        
        Args:
            questions: List of all questions
            counts: Dict of {type: count} for sampling
            strategy: Sampling strategy ("random", "balanced", "weighted")
            
        Returns:
            Dict of {type: [selected_questions]}
        """
        result = {}
        
        for q_type, count in counts.items():
            filtered = self.filter_by_type(questions, q_type)
            
            if len(filtered) < count:
                logger.warning(
                    f"Requested {count} {q_type} but only {len(filtered)} available"
                )
                result[q_type] = filtered
            else:
                if strategy == "random":
                    result[q_type] = random.sample(filtered, count)
                elif strategy == "first":
                    result[q_type] = filtered[:count]
                else:
                    result[q_type] = random.sample(filtered, count)
        
        total = sum(len(v) for v in result.values())
        logger.info(f"Sampled {total} questions: {counts}")
        return result
    
    def sample_with_difficulty(self, questions: List[Dict],
                               counts: Dict[str, int],
                               difficulty_dist: Dict[str, tuple]) -> Dict[str, List[Dict]]:
        """
        Sample questions with difficulty distribution.
        
        Args:
            questions: List of all questions
            counts: Dict of {type: count}
            difficulty_dist: Dict of {type: (easy%, medium%, hard%)}
            
        Returns:
            Dict of sampled questions by type
        """
        result = defaultdict(list)
        
        for q_type, target_count in counts.items():
            filtered = self.filter_by_type(questions, q_type)
            
            if q_type in difficulty_dist:
                easy_pct, med_pct, hard_pct = difficulty_dist[q_type]
                easy_count = int(target_count * easy_pct / 100)
                med_count = int(target_count * med_pct / 100)
                hard_count = target_count - easy_count - med_count
                
                by_difficulty = {"容易": [], "一般": [], "困难": []}
                for q in filtered:
                    difficulty = q.get("difficulty", "一般")
                    by_difficulty.get(difficulty, by_difficulty["一般"]).append(q)
                
                result[q_type].extend(random.sample(by_difficulty["容易"], min(easy_count, len(by_difficulty["容易"]))))
                result[q_type].extend(random.sample(by_difficulty["一般"], min(med_count, len(by_difficulty["一般"]))))
                result[q_type].extend(random.sample(by_difficulty["困难"], min(hard_count, len(by_difficulty["困难"]))))
            else:
                result[q_type] = random.sample(filtered, min(target_count, len(filtered)))
        
        return dict(result)


def sample_questions(cleaned_questions: List[Dict], 
                     counts: Dict[str, int],
                     seed: Optional[int] = None) -> Dict[str, List[Dict]]:
    """
    Convenience function for random sampling.
    
    Args:
        cleaned_questions: List of cleaned questions
        counts: Dict of {type: count}
        
    Returns:
        Dict of {type: [selected_questions]}
    """
    sampler = QuestionSampler(seed=seed)
    
    result = sampler.sample_questions(cleaned_questions, counts)
    
    logger.info(f"Total sampled: {sum(len(v) for v in result.values())} questions")
    return result


def sample_by_source(questions: List[Dict], counts: Dict[str, int],
                     source_weights: Optional[Dict[str, float]] = None) -> Dict[str, List[Dict]]:
    """
    Sample questions with source weighting.
    
    Args:
        questions: List of all questions
        counts: Dict of {type: count}
        source_weights: Optional weights for each source
        
    Returns:
        Dict of sampled questions by type
    """
    by_source = defaultdict(lambda: defaultdict(list))
    
    for q in questions:
        source = q.get("source", "unknown")
        q_type = q.get("type", "unknown")
        by_source[source][q_type].append(q)
    
    result = defaultdict(list)
    
    for q_type, count in counts.items():
        all_from_type = []
        for source, type_questions in by_source.items():
            if q_type in type_questions:
                weight = source_weights.get(source, 1.0) if source_weights else 1.0
                all_from_type.extend(type_questions[q_type] * weight)
        
        if len(all_from_type) >= count:
            result[q_type] = random.sample(all_from_type, count)
        else:
            result[q_type] = all_from_type
    
    return dict(result)