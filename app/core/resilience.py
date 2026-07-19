# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import functools
import structlog
import tenacity
from tenacity import wait_exponential, stop_after_attempt, retry_if_exception_type
from openai import APIError as OpenAPIError

log = structlog.get_logger()


def resilient_api_call(
    max_retries=3, base_delay=1.0, exceptions=(OpenAPIError, Exception)
):
    """
    Decorator for adding resilience to asynchronous API calls.
    Retries the operation upon encountering specific exceptions using exponential backoff (via tenacity).
    If all retries fail, it logs a stack trace and explicitly fails.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:

                def before_sleep(retry_state):
                    log.warning(
                        "API call failed, retrying...",
                        function=func.__name__,
                        attempt=retry_state.attempt_number,
                        max_retries=max_retries,
                        error=str(retry_state.outcome.exception()),
                        delay=retry_state.next_action.sleep,
                    )

                async for attempt in tenacity.AsyncRetrying(
                    wait=wait_exponential(multiplier=base_delay, min=2, max=10),
                    stop=stop_after_attempt(max_retries),
                    reraise=True,
                    retry=retry_if_exception_type(exceptions),
                    before_sleep=before_sleep,
                ):
                    with attempt:
                        return await func(*args, **kwargs)
            except Exception as e:
                # All retries exhausted
                log.error(
                    "API call failed after all retries exhausted",
                    function=func.__name__,
                    max_retries=max_retries,
                    error=str(e),
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator
