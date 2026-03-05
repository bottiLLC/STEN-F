import asyncio
import functools
import structlog
from google.genai.errors import APIError as GeminiAPIError
from openai import APIError as OpenAPIError

log = structlog.get_logger()

def resilient_api_call(max_retries=3, base_delay=1.0, exceptions=(GeminiAPIError, OpenAPIError, Exception)):
    """
    Decorator for adding resilience to asynchronous API calls.
    Retries the operation upon encountering specific exceptions using exponential backoff.
    If all retries fail, it logs a stack trace and explicitly fails.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    # Avoid logging stack trace for normal retries, just a warning
                    error_str = str(e)
                    
                    # 429/503 are usually retriable.
                    # Other errors might be terminal but we generalize to catch network hiccups.
                    log.warning(
                        "API call failed, retrying...",
                        function=func.__name__,
                        attempt=attempt,
                        max_retries=max_retries,
                        error=error_str,
                        delay=delay
                    )
                    
                    if attempt < max_retries:
                        await asyncio.sleep(delay)
                        delay *= 2  # Exponential backoff
                        
            # All retries exhausted
            log.error(
                "API call failed after all retries exhausted",
                function=func.__name__,
                max_retries=max_retries,
                error=str(last_exception),
                exc_info=True
            )
            raise last_exception
        return wrapper
    return decorator
