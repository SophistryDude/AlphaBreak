"""
Input Validation Module
========================
Decorators and utilities for validating API request inputs.

Provides:
- Schema validation decorators
- Type checking
- Required field validation
- Error response formatting
"""

from functools import wraps
from flask import request, jsonify
from typing import Dict, List, Any, Optional, Callable
import re
from datetime import datetime


class ValidationError(Exception):
    """Custom validation error with field information."""
    def __init__(self, message: str, field: str = None, code: str = 'VALIDATION_ERROR'):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


def validate_request(schema: Dict[str, Any]):
    """
    Decorator to validate JSON request body against a schema.

    Schema format:
        {
            'field_name': {
                'type': str/int/float/bool/list/dict,
                'required': True/False,
                'min': minimum value (for numbers) or min length (for strings),
                'max': maximum value (for numbers) or max length (for strings),
                'pattern': regex pattern (for strings),
                'choices': list of valid values,
                'default': default value if not provided
            }
        }

    Example:
        @validate_request({
            'ticker': {'type': str, 'required': True, 'pattern': r'^[A-Z]{1,5}$'},
            'days': {'type': int, 'required': False, 'min': 1, 'max': 365, 'default': 30}
        })
        def my_endpoint():
            data = request.validated_data
            ...
    """
    def decorator(f: Callable):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get JSON data
            data = request.get_json(silent=True) or {}

            validated_data = {}
            errors = []

            for field_name, rules in schema.items():
                value = data.get(field_name)
                field_type = rules.get('type', str)
                required = rules.get('required', False)
                default = rules.get('default')

                # Handle missing fields
                if value is None:
                    if required:
                        errors.append({
                            'field': field_name,
                            'message': f"'{field_name}' is required",
                            'code': 'REQUIRED_FIELD'
                        })
                        continue
                    elif default is not None:
                        validated_data[field_name] = default
                        continue
                    else:
                        continue

                # Type validation
                try:
                    if field_type == str:
                        value = str(value)
                    elif field_type == int:
                        value = int(value)
                    elif field_type == float:
                        value = float(value)
                    elif field_type == bool:
                        if isinstance(value, bool):
                            pass
                        elif isinstance(value, str):
                            value = value.lower() in ('true', '1', 'yes')
                        else:
                            value = bool(value)
                    elif field_type == list:
                        if not isinstance(value, list):
                            raise ValueError("Expected a list")
                    elif field_type == dict:
                        if not isinstance(value, dict):
                            raise ValueError("Expected an object")
                except (ValueError, TypeError) as e:
                    errors.append({
                        'field': field_name,
                        'message': f"'{field_name}' must be of type {field_type.__name__}",
                        'code': 'INVALID_TYPE'
                    })
                    continue

                # Min/Max validation
                min_val = rules.get('min')
                max_val = rules.get('max')

                if field_type in (int, float):
                    if min_val is not None and value < min_val:
                        errors.append({
                            'field': field_name,
                            'message': f"'{field_name}' must be at least {min_val}",
                            'code': 'MIN_VALUE'
                        })
                        continue
                    if max_val is not None and value > max_val:
                        errors.append({
                            'field': field_name,
                            'message': f"'{field_name}' must be at most {max_val}",
                            'code': 'MAX_VALUE'
                        })
                        continue
                elif field_type == str:
                    if min_val is not None and len(value) < min_val:
                        errors.append({
                            'field': field_name,
                            'message': f"'{field_name}' must be at least {min_val} characters",
                            'code': 'MIN_LENGTH'
                        })
                        continue
                    if max_val is not None and len(value) > max_val:
                        errors.append({
                            'field': field_name,
                            'message': f"'{field_name}' must be at most {max_val} characters",
                            'code': 'MAX_LENGTH'
                        })
                        continue

                # Pattern validation (strings only)
                pattern = rules.get('pattern')
                if pattern and field_type == str:
                    if not re.match(pattern, value):
                        errors.append({
                            'field': field_name,
                            'message': f"'{field_name}' has invalid format",
                            'code': 'INVALID_FORMAT'
                        })
                        continue

                # Choices validation
                choices = rules.get('choices')
                if choices and value not in choices:
                    errors.append({
                        'field': field_name,
                        'message': f"'{field_name}' must be one of: {', '.join(map(str, choices))}",
                        'code': 'INVALID_CHOICE'
                    })
                    continue

                validated_data[field_name] = value

            if errors:
                return jsonify({
                    'error': 'Validation failed',
                    'code': 'VALIDATION_ERROR',
                    'details': errors
                }), 400

            # Attach validated data to request
            request.validated_data = validated_data
            return f(*args, **kwargs)

        return decorated_function
    return decorator


def validate_ticker(ticker: str) -> bool:
    """
    Validate a stock ticker symbol.

    Args:
        ticker: Ticker symbol to validate

    Returns:
        True if valid, False otherwise
    """
    if not ticker:
        return False
    # Standard ticker: 1-5 uppercase letters
    # Crypto ticker: letters-letters (e.g., BTC-USD)
    pattern = r'^[A-Z]{1,5}(-[A-Z]{1,5})?$'
    return bool(re.match(pattern, ticker.upper()))


def validate_date(date_str: str, format: str = '%Y-%m-%d') -> Optional[datetime]:
    """
    Validate and parse a date string.

    Args:
        date_str: Date string to validate
        format: Expected date format

    Returns:
        datetime object if valid, None otherwise
    """
    try:
        return datetime.strptime(date_str, format)
    except (ValueError, TypeError):
        return None


def validate_date_range(start_date: str, end_date: str) -> tuple:
    """
    Validate a date range.

    Args:
        start_date: Start date string
        end_date: End date string

    Returns:
        Tuple of (is_valid, error_message)
    """
    start = validate_date(start_date)
    end = validate_date(end_date)

    if not start:
        return False, "Invalid start_date format. Use YYYY-MM-DD"
    if not end:
        return False, "Invalid end_date format. Use YYYY-MM-DD"
    if start > end:
        return False, "start_date must be before end_date"
    if end > datetime.now():
        return False, "end_date cannot be in the future"

    return True, None


# Common validation schemas
TICKER_SCHEMA = {
    'ticker': {
        'type': str,
        'required': True,
        'min': 1,
        'max': 10,
        'pattern': r'^[A-Z]{1,5}(-[A-Z]{1,5})?$'
    }
}

PREDICTION_SCHEMA = {
    'ticker': {
        'type': str,
        'required': True,
        'min': 1,
        'max': 10
    },
    'start_date': {
        'type': str,
        'required': False,
        'pattern': r'^\d{4}-\d{2}-\d{2}$'
    },
    'end_date': {
        'type': str,
        'required': False,
        'pattern': r'^\d{4}-\d{2}-\d{2}$'
    },
    'model_type': {
        'type': str,
        'required': False,
        'choices': ['xgboost', 'lightgbm', 'lstm', 'meta'],
        'default': 'xgboost'
    }
}

OPTIONS_SCHEMA = {
    'ticker': {
        'type': str,
        'required': True,
        'min': 1,
        'max': 10
    },
    'expiry_date': {
        'type': str,
        'required': False,
        'pattern': r'^\d{4}-\d{2}-\d{2}$'
    },
    'strike_price': {
        'type': float,
        'required': False,
        'min': 0.01
    },
    'option_type': {
        'type': str,
        'required': False,
        'choices': ['call', 'put', 'both'],
        'default': 'both'
    },
    'pricing_model': {
        'type': str,
        'required': False,
        'choices': ['american', 'european'],
        'default': 'american'
    },
    'trend_direction': {
        'type': str,
        'required': False,
        'choices': ['bullish', 'bearish', 'both'],
        'default': 'both'
    }
}

INDICATOR_ANALYSIS_SCHEMA = {
    'ticker': {
        'type': str,
        'required': True,
        'min': 1,
        'max': 10
    },
    'start_date': {
        'type': str,
        'required': True,
        'pattern': r'^\d{4}-\d{2}-\d{2}$'
    },
    'end_date': {
        'type': str,
        'required': True,
        'pattern': r'^\d{4}-\d{2}-\d{2}$'
    },
    'indicators': {
        'type': list,
        'required': False
    }
}
