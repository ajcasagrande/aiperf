import numpy as np
from typing import Any, Dict, List, Optional, Tuple, Union

def calculate_percentiles(values: List[float], percentiles: List[float]) -> Dict[float, float]:
    """Calculate percentiles for a list of values.
    
    Args:
        values: List of values
        percentiles: List of percentiles to calculate (0-100)
        
    Returns:
        Dictionary mapping percentiles to values
    """
    if not values:
        return {}
        
    result = {}
    for p in percentiles:
        result[p] = float(np.percentile(values, p))
    return result

def calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of values.
    
    Args:
        values: List of values
        
    Returns:
        Dictionary with statistics
    """
    if not values:
        return {
            "count": 0,
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "std": 0.0
        }
        
    return {
        "count": len(values),
        "mean": float(np.mean(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "std": float(np.std(values))
    }

def calculate_complete_stats(values: List[float]) -> Dict[str, float]:
    """Calculate complete statistics for a list of values.
    
    Args:
        values: List of values
        
    Returns:
        Dictionary with statistics including percentiles
    """
    stats = calculate_stats(values)
    percentiles = calculate_percentiles(values, [25, 50, 75, 90, 95, 99])
    
    result = stats.copy()
    for p, value in percentiles.items():
        result[f"p{p}"] = value
        
    return result

def calculate_throughput(count: int, duration: float) -> float:
    """Calculate throughput.
    
    Args:
        count: Number of items
        duration: Duration in seconds
        
    Returns:
        Throughput in items per second
    """
    if duration == 0:
        return 0.0
    return count / duration

def calculate_moving_average(values: List[float], window_size: int) -> List[float]:
    """Calculate moving average for a list of values.
    
    Args:
        values: List of values
        window_size: Window size
        
    Returns:
        List of moving averages
    """
    if not values or window_size <= 0:
        return []
        
    result = []
    for i in range(len(values)):
        start = max(0, i - window_size + 1)
        window = values[start:i+1]
        result.append(float(np.mean(window)))
    return result 