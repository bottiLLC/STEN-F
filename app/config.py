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

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings managed by Pydantic.
    Reads from environment variables and .env file.
    """

    # Core Paths
    APP_DIR: Path = Path(__file__).parent.resolve()
    PROJECT_ROOT: Path = APP_DIR.parent

    # Database
    DB_NAME: str = "sten_f.db"
    DATABASE_URL: Optional[str] = None

    # External APIs
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_DEFAULT_MODEL: str = "gpt-5.6-terra"
    OPENAI_REASONING_EFFORT: str = "high"

    # App Metadata
    APP_TITLE: str = "STEN-F"
    CURRENCY_SYMBOL: str = "¥"

    # Fonts
    WINDOWS_FONT_PATH: Path = Path("C:/Windows/Fonts/msgothic.ttc")
    FONT_PATH: Optional[Path] = None
    FONT_NAME: str = "HeiseiMin-W3"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="forbid", case_sensitive=True
    )

    def model_post_init(self, __context):
        # Computed properties
        if not self.DATABASE_URL:
            db_path = self.PROJECT_ROOT / "data" / self.DB_NAME
            self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

        if self.WINDOWS_FONT_PATH.exists():
            self.FONT_PATH = self.WINDOWS_FONT_PATH
            self.FONT_NAME = "MSGothic"
        else:
            self.FONT_PATH = None
            self.FONT_NAME = "HeiseiMin-W3"


# Singleton instance
settings = Settings()
