#!/usr/bin/env python3
"""
Colab Configuration Management
Simplified config for Google Colab environment
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class APIConfig:
    phone_api_url: str = "https://hot-friends-study.loca.lt/get-number"
    dentalcare_base_url: str = "https://account.dentalcare.com"
    dentalcare_signup_url: str = "https://www.dentalcare.com/en-us?iss=https%3A%2F%2Faccount.dentalcare.com%2F"


@dataclass
class AccountConfig:
    numbers_per_account: int = 5
    resends_per_number: int = 1
    parallel_workers: int = 50  # 90% efficiency: ~12.9GB RAM / 180MB per instance ≈ 70, use 50 for stability
    worker_batch_size: int = 5
    worker_batch_delay: int = 1
    account_creation_timeout: int = 350
    phone_processing_timeout: int = 180
    register_via_api: bool = True
    keep_browser_open: bool = True


@dataclass
class BrowserConfig:
    headless: bool = True
    timeout: int = 15000  # Reduced for faster failure detection
    viewport_width: int = 1280  # Smaller for Colab
    viewport_height: int = 720
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_enabled: bool = True
    console_enabled: bool = True
    max_file_size: int = 10 * 1024 * 1024
    backup_count: int = 5


@dataclass
class StorageConfig:
    base_dir: str = ""
    profiles_dir: str = ""
    logs_dir: str = ""
    temp_dir: str = ""
    auto_cleanup: bool = True


class ColabConfig:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    
    def __init__(self):
        self.api = APIConfig()
        self.account = AccountConfig()
        self.browser = BrowserConfig()
        self.browser.headless = True
        self.logging = LoggingConfig()
        self.storage = StorageConfig()
        self._init_storage()
    
    def _init_storage(self):
        self.storage.base_dir = os.path.join(self.APP_DIR, "data")
        self.storage.profiles_dir = os.path.join(self.storage.base_dir, "profiles")
        self.storage.logs_dir = os.path.join(self.APP_DIR, "logs")
        self.storage.temp_dir = os.path.join(self.storage.base_dir, "temp")
        
        os.makedirs(self.storage.base_dir, exist_ok=True)
        os.makedirs(self.storage.profiles_dir, exist_ok=True)
        os.makedirs(self.storage.logs_dir, exist_ok=True)
        os.makedirs(self.storage.temp_dir, exist_ok=True)
    
    def cleanup_profiles(self):
        import shutil
        if os.path.exists(self.storage.profiles_dir):
            for item in os.listdir(self.storage.profiles_dir):
                item_path = os.path.join(self.storage.profiles_dir, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception:
                    pass
    
    def update_phone_api(self, url: str):
        self.api.phone_api_url = url
        print(f"Phone API URL updated to: {url}")
    
    def update_parallel_workers(self, count: int):
        self.account.parallel_workers = max(1, min(count, 50))
        print(f"Parallel workers set to: {self.account.parallel_workers}")
    
    def update_batch_delay(self, delay: int):
        self.account.worker_batch_delay = max(0, delay)
        print(f"Batch delay set to: {self.account.worker_batch_delay}s")


config = ColabConfig()
