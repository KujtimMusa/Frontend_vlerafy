"""
Feature Confidence Analyzer

Analyzes feature availability and provides detailed confidence breakdown
with explanations for missing data, legitimate zeros, and unimplemented features.
"""

from typing import Dict, List, Optional
from app.config.feature_metadata import (
    FEATURE_CATEGORIES,
    CATEGORY_NAMES,
    get_status
)
import logging

logger = logging.getLogger(__name__)


class FeatureConfidenceAnalyzer:
    """
    Analyzes feature availability and provides detailed confidence breakdown.
    
    Distinguishes between:
    - MISSING_DATA_IF_ZERO: Critical missing data
    - LEGITIMATE_ZERO: Valid calculated zero result
    - NOT_IMPLEMENTED: Hardcoded placeholder (code bug)
    - ALWAYS_AVAILABLE: Feature always has a value
    """
    
    def analyze_confidence(
        self,
        features: Dict[str, float],
        include_explanations: bool = True
    ) -> Dict:
        """
        Analyze feature availability and return detailed confidence.
        
        Args:
            features: Dictionary of feature_name -> feature_value
            include_explanations: Whether to include detailed explanations
            
        Returns:
            {
                'overall_confidence': 75.0,
                'total_features': 80,
                'available_features': 60,
                'categories': {
                    'SALES': {
                        'available': 15,
                        'total': 19,
                        'percentage': 78.9,
                        'status': 'good',
                        'missing_critical': ['sales_velocity_30d'],
                        'missing_non_critical': [],
                        'legitimate_zeros': ['demand_growth_7d_vs_30d'],
                        'not_implemented': []
                    },
                    ...
                },
                'warnings': [...],
                'recommendations': [...]
            }
        """
        total_features = len(features)
        available_features = 0
        
        # Group features by category
        category_stats = {}
        warnings = []
        recommendations = []
        
        # Initialize category stats
        for category in CATEGORY_NAMES.keys():
            category_stats[category] = {
                'available': 0,
                'total': 0,
                'missing_critical': [],
                'missing_non_critical': [],
                'legitimate_zeros': [],
                'not_implemented': []
            }
        
        # Analyze each feature
        for feature_name, feature_value in features.items():
            if feature_name not in FEATURE_CATEGORIES:
                # Unknown feature - skip
                continue
            
            metadata = FEATURE_CATEGORIES[feature_name]
            category = metadata['category']
            
            category_stats[category]['total'] += 1
            
            # Categorize feature
            feature_status = self.categorize_missing_feature(
                feature_name,
                feature_value
            )
            
            if feature_status['is_available']:
                category_stats[category]['available'] += 1
                available_features += 1
                
                if feature_status['type'] == 'LEGITIMATE_ZERO':
                    category_stats[category]['legitimate_zeros'].append(feature_name)
            else:
                # Feature is missing/not available
                if feature_status['type'] == 'NOT_IMPLEMENTED':
                    category_stats[category]['not_implemented'].append(feature_name)
                elif metadata['critical']:
                    category_stats[category]['missing_critical'].append(feature_name)
                else:
                    category_stats[category]['missing_non_critical'].append(feature_name)
        
        # Calculate percentages and status for each category
        category_results = {}
        for category, stats in category_stats.items():
            total = stats['total']
            available = stats['available']
            percentage = (available / total * 100) if total > 0 else 0.0
            
            category_results[category] = {
                'available': available,
                'total': total,
                'percentage': round(percentage, 1),
                'status': get_status(percentage),
                'missing_critical': stats['missing_critical'],
                'missing_non_critical': stats['missing_non_critical'],
                'legitimate_zeros': stats['legitimate_zeros'],
                'not_implemented': stats['not_implemented']
            }
        
        # Generate warnings and recommendations
        if include_explanations:
            warnings, recommendations = self._generate_warnings_and_recommendations(
                category_results
            )
        
        # Calculate overall confidence (weighted by category importance)
        overall_confidence = self._calculate_overall_confidence(category_results)
        
        return {
            'overall_confidence': round(overall_confidence, 1),
            'total_features': total_features,
            'available_features': available_features,
            'categories': category_results,
            'warnings': warnings,
            'recommendations': recommendations
        }
    
    def categorize_missing_feature(
        self,
        feature_name: str,
        feature_value: float
    ) -> Dict:
        """
        Determine if a zero/missing feature is:
        - Critical missing data
        - Legitimate zero
        - Not implemented
        
        Returns:
            {
                'is_available': bool,
                'type': 'MISSING_DATA_IF_ZERO' | 'LEGITIMATE_ZERO' | 'NOT_IMPLEMENTED' | 'ALWAYS_AVAILABLE',
                'explanation': str
            }
        """
        if feature_name not in FEATURE_CATEGORIES:
            return {
                'is_available': False,
                'type': 'UNKNOWN',
                'explanation': 'Unknown feature'
            }
        
        metadata = FEATURE_CATEGORIES[feature_name]
        feature_type = metadata['type']
        
        # Special handling for days_since_last_sale (999 means no sales)
        if feature_name == 'days_since_last_sale' and feature_value >= 999:
            return {
                'is_available': False,
                'type': 'MISSING_DATA_IF_ZERO',
                'explanation': metadata['explanation']
            }
        
        # Special handling for days_of_stock (999 means cannot calculate)
        if feature_name.startswith('days_of_stock') and feature_value >= 999:
            return {
                'is_available': False,
                'type': 'MISSING_DATA_IF_ZERO',
                'explanation': metadata['explanation']
            }
        
        # Check if feature is available
        if feature_type == 'ALWAYS_AVAILABLE':
            return {
                'is_available': True,
                'type': 'ALWAYS_AVAILABLE',
                'explanation': metadata['explanation']
            }
        
        # For zero values, check type
        if feature_value == 0.0 or feature_value is None:
            if feature_type == 'MISSING_DATA_IF_ZERO':
                return {
                    'is_available': False,
                    'type': 'MISSING_DATA_IF_ZERO',
                    'explanation': metadata['explanation']
                }
            elif feature_type == 'LEGITIMATE_ZERO':
                return {
                    'is_available': True,  # Zero is valid
                    'type': 'LEGITIMATE_ZERO',
                    'explanation': metadata['explanation']
                }
            elif feature_type == 'NOT_IMPLEMENTED':
                return {
                    'is_available': False,
                    'type': 'NOT_IMPLEMENTED',
                    'explanation': metadata['explanation']
                }
        
        # Non-zero value - feature is available
        return {
            'is_available': True,
            'type': feature_type,
            'explanation': metadata['explanation']
        }
    
    def get_feature_explanation(
        self,
        feature_name: str,
        feature_value: float
    ) -> str:
        """
        Return human-readable explanation for feature status.
        """
        if feature_name not in FEATURE_CATEGORIES:
            return f"Unknown feature: {feature_name}"
        
        metadata = FEATURE_CATEGORIES[feature_name]
        status = self.categorize_missing_feature(feature_name, feature_value)
        
        if status['is_available']:
            if status['type'] == 'LEGITIMATE_ZERO':
                return f"{metadata['zero_meaning']} - {metadata['explanation']}"
            else:
                return f"Available: {metadata['explanation']}"
        else:
            return f"Missing: {metadata['explanation']}"
    
    def _calculate_overall_confidence(
        self,
        category_results: Dict[str, Dict]
    ) -> float:
        """
        Calculate weighted overall confidence.
        
        Weights:
        - SALES: 25% (most important for pricing)
        - COMPETITOR: 20% (market positioning)
        - COST: 15% (margin calculations)
        - INVENTORY: 15% (stock management)
        - PRICE: 10% (price history)
        - SEASONAL: 5% (temporal factors)
        - ADVANCED: 10% (advanced analytics)
        """
        weights = {
            'SALES': 0.25,
            'COMPETITOR': 0.20,
            'COST': 0.15,
            'INVENTORY': 0.15,
            'PRICE': 0.10,
            'SEASONAL': 0.05,
            'ADVANCED': 0.10
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for category, percentage in category_results.items():
            if category in weights:
                weight = weights[category]
                weighted_sum += percentage['percentage'] * weight
                total_weight += weight
        
        if total_weight > 0:
            return weighted_sum / total_weight
        return 0.0
    
    def _generate_warnings_and_recommendations(
        self,
        category_results: Dict[str, Dict]
    ) -> tuple[List[str], List[str]]:
        """
        Generate warnings and recommendations based on missing features.
        """
        warnings = []
        recommendations = []
        
        # Check each category
        for category, stats in category_results.items():
            category_name = CATEGORY_NAMES.get(category, category)
            percentage = stats['percentage']
            
            # Critical missing features
            if stats['missing_critical']:
                critical_count = len(stats['missing_critical'])
                warnings.append(
                    f"Missing {critical_count} critical {category_name.lower()} feature(s): "
                    f"{', '.join(stats['missing_critical'][:3])}"
                    + (f" and {critical_count - 3} more" if critical_count > 3 else "")
                )
            
            # Low percentage warnings
            if percentage < 50.0 and stats['total'] > 0:
                warnings.append(
                    f"Low {category_name.lower()} data coverage ({percentage:.1f}%) - "
                    f"recommendations may be less accurate"
                )
            
            # Not implemented features
            if stats['not_implemented']:
                not_impl_count = len(stats['not_implemented'])
                warnings.append(
                    f"{not_impl_count} {category_name.lower()} feature(s) not yet implemented: "
                    f"{', '.join(stats['not_implemented'][:2])}"
                    + (f" and {not_impl_count - 2} more" if not_impl_count > 2 else "")
                )
            
            # Recommendations
            if category == 'SALES' and percentage < 50:
                recommendations.append(
                    "Collect more sales history data to improve pricing accuracy"
                )
            
            if category == 'COMPETITOR' and percentage < 50:
                recommendations.append(
                    "Ensure competitor price search is working correctly"
                )
            
            if category == 'COST' and stats['missing_critical']:
                recommendations.append(
                    "Add product cost data to enable margin calculations"
                )
            
            if category == 'PRICE' and percentage < 50:
                recommendations.append(
                    "Track price changes over time to improve price trend analysis"
                )
        
        # Remove duplicates
        warnings = list(dict.fromkeys(warnings))
        recommendations = list(dict.fromkeys(recommendations))
        
        return warnings, recommendations
