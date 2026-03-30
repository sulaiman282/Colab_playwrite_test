#!/usr/bin/env python3
"""
Colab Data Models
Simplified models for Google Colab environment
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid
import json
import os


class AccountStatus(Enum):
    PENDING = "pending"
    CREATING = "creating"
    CREATED = "created"
    PROCESSING_PHONES = "processing_phones"
    COMPLETED = "completed"
    FAILED = "failed"


class PhoneStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    ADDED = "added"
    RESENT = "resent"
    FAILED = "failed"


@dataclass
class PhoneNumber:
    number: str
    country: str
    country_code: str
    status: PhoneStatus = PhoneStatus.PENDING
    added_at: Optional[datetime] = None
    resent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'number': self.number,
            'country': self.country,
            'country_code': self.country_code,
            'status': self.status.value,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'resent_at': self.resent_at.isoformat() if self.resent_at else None,
            'error_message': self.error_message
        }


@dataclass
class AccountData:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email: str = ""
    password: str = ""
    first_name: str = ""
    last_name: str = ""
    birth_month: int = 1
    birth_year: int = 1990
    mobile_number: str = ""
    address_1: str = ""
    address_2: str = ""
    city: str = ""
    state_address: str = ""
    zip_code: str = ""
    role: str = "Practicing Dental Professional & Support Staff"
    status: AccountStatus = AccountStatus.PENDING
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    phone_numbers: List[PhoneNumber] = field(default_factory=list)
    error_message: Optional[str] = None
    worker_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'email': self.email,
            'password': self.password,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'birth_month': self.birth_month,
            'birth_year': self.birth_year,
            'mobile_number': self.mobile_number,
            'address_1': self.address_1,
            'address_2': self.address_2,
            'city': self.city,
            'state_address': self.state_address,
            'zip_code': self.zip_code,
            'role': self.role,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'phone_numbers': [phone.to_dict() for phone in self.phone_numbers],
            'error_message': self.error_message,
            'worker_id': self.worker_id
        }


@dataclass
class WorkerStats:
    worker_id: str
    accounts_created: int = 0
    accounts_completed: int = 0
    accounts_failed: int = 0
    phones_processed: int = 0
    phones_failed: int = 0
    start_time: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    is_active: bool = False


@dataclass
class SystemStats:
    total_accounts: int = 0
    completed_accounts: int = 0
    failed_accounts: int = 0
    total_phones: int = 0
    successful_phones: int = 0
    failed_phones: int = 0
    active_workers: int = 0
    start_time: Optional[datetime] = None


class DataManager:
    def __init__(self):
        from config import config
        self.data_dir = config.storage.base_dir
        self.accounts_file = os.path.join(self.data_dir, "accounts.json")
        os.makedirs(self.data_dir, exist_ok=True)
    
    def save_accounts(self, accounts: List[AccountData]) -> None:
        try:
            data = [account.to_dict() for account in accounts]
            with open(self.accounts_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving accounts: {e}")
    
    def load_accounts(self) -> List[AccountData]:
        try:
            if os.path.exists(self.accounts_file):
                with open(self.accounts_file, 'r') as f:
                    data = json.load(f)
                return [AccountData(**d) for d in data]
        except Exception as e:
            print(f"Error loading accounts: {e}")
        return []
