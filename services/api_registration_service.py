#!/usr/bin/env python3
"""
API-based Registration Service for Colab
Uses direct API calls for faster registration
"""

import base64
import json
import logging
import random
import re
import string
import time
from typing import Optional, Tuple, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import parse_qs, urlparse

from config import config
from models import AccountData, AccountStatus

logger = logging.getLogger(__name__)


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def get_context_token_from_html(html: str) -> Optional[str]:
    pattern = r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+'
    matches = re.findall(pattern, html)
    for token in matches:
        try:
            header = base64.b64decode(token.split('.')[0] + '==')
            if b'HS256' in header or b'JWT' in header:
                return token
        except:
            pass
    return None


FIRST_NAMES = ["alex", "jordan", "taylor", "morgan", "casey", "riley", "quinn", "avery",
               "reese", "parker", "sage", "blake", "drew", "emery", "finley", "harper",
               "jesse", "kendall", "logan", "mason", "noah", "owen", "peyton", "skyler"]

LAST_NAMES = ["smith", "johnson", "williams", "brown", "jones", "garcia", "miller", "davis",
              "rodriguez", "martinez", "hernandez", "lopez", "wilson", "anderson", "thomas",
              "taylor", "moore", "jackson", "martin", "lee", "perez", "thompson", "white"]


class APIGenerator:
    CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
              "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville"]

    STATES = ["California", "Texas", "Florida", "New York", "Pennsylvania", "Illinois",
             "Ohio", "Georgia", "North Carolina", "Michigan", "New Jersey", "Virginia"]

    STREET_NAMES = ["Main St", "Oak Ave", "Pine Rd", "Maple Dr", "Cedar Ln", "Elm St",
                   "Park Ave", "Washington St", "Lincoln Ave", "Jefferson Rd"]

    @staticmethod
    def generate_account() -> AccountData:
        ts = int(time.time())
        rand_num = random.randint(10000000, 99999999)
        rand_name = random.choice(FIRST_NAMES) + random.choice(LAST_NAMES)
        domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        domain = random.choice(domains)
        email = f"{rand_name}{rand_num}@{domain}"

        pass_chars = string.ascii_letters + string.digits + "!@#$%"
        password = ''.join(random.choices(pass_chars, k=12))

        first_name = random.choice(FIRST_NAMES).capitalize()
        last_name = random.choice(LAST_NAMES).capitalize()

        return AccountData(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            birth_month=random.randint(1, 12),
            birth_year=random.randint(1970, 2000),
            mobile_number=f"+1555{random.randint(1000000, 9999999)}",
            address_1=f"{random.randint(100, 9999)} {random.choice(APIGenerator.STREET_NAMES)}",
            address_2=f"Apt {random.randint(1, 999)}" if random.choice([True, False]) else "",
            city=random.choice(APIGenerator.CITIES),
            state_address=random.choice(APIGenerator.STATES),
            zip_code=f"{random.randint(10000, 99999)}",
            role="Practicing Dental Professional & Support Staff"
        )


class APIRegistrationFlow:
    BASE_URL = "https://account.dentalcare.com"
    FORM_ID = "ap_ihsoSrVEUkeAJKAdyD8dGa"
    STEP_CONTACT = "step_4iwC"
    STEP_PROFESSIONAL = "step_bnhU"

    def __init__(self):
        self.session = create_session()
        self.state = None
        self.resume_state = None
        self.custom_prompt_state = None
        self.beat_signature = None
        self.context_token = None
        self.email: Optional[str] = None
        self.password: Optional[str] = None

    def register(self, account: AccountData) -> Tuple[bool, Optional[str]]:
        try:
            ts = int(time.time())
            rand_num = random.randint(10000000, 99999999)
            rand_name = random.choice(FIRST_NAMES) + random.choice(LAST_NAMES)
            domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
            domain = random.choice(domains)
            self.email = f"{rand_name}{rand_num}@{domain}"

            pass_chars = string.ascii_letters + string.digits + "!@#$%"
            self.password = ''.join(random.choices(pass_chars, k=12))

            logger.info(f"[API] Starting registration: {self.email}")

            if not self.step1_5():
                return False, "Steps 1-5 failed"

            if not self.step6_7():
                return False, "Steps 6-7 failed"

            if not self.step8_contact():
                return False, "Step 8 failed"

            if not self.step9_professional():
                return False, "Step 9 failed"

            if not self.step10_submit():
                return False, "Step 10 failed"

            account.email = self.email
            account.password = self.password

            logger.info(f"[API] Registration completed: {self.email}")
            return True, None

        except Exception as e:
            logger.error(f"[API] Registration error: {e}")
            return False, str(e)

    def step1_5(self) -> bool:
        try:
            self.session.get("https://www.dentalcare.com/en-us",
                           headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

            r = self.session.get(
                f"{self.BASE_URL}/authorize",
                params={
                    "response_type": "code",
                    "client_id": "R2QwFfemhq1Gvsps0ilaH6a82AmHWjq0",
                    "redirect_uri": "https://www.dentalcare.com/en-us/auth",
                    "state": "",
                    "audience": "CGW",
                    "scope": "offline_access openid",
                    "screen_hint": "signup",
                    "ui_locales": "en-US"
                },
                allow_redirects=False
            )

            if r.status_code in [301, 302]:
                parsed = urlparse(r.headers.get("Location", ""))
                params = parse_qs(parsed.query)
                self.state = params.get("state", [""])[0]
            else:
                return False

            r = self.session.get(
                f"{self.BASE_URL}/u/signup",
                params={"state": self.state, "ui_locales": "en-US"}
            )

            time.sleep(0.2)  # Reduced from 0.5
            r = self.session.post(
                f"{self.BASE_URL}/u/signup",
                params={"state": self.state, "ui_locales": "en-US"},
                data={
                    "state": self.state,
                    "ulp-name-prefix": "Mr.",
                    "ulp-first-name": "Jordan",
                    "ulp-last-name": "Smith",
                    "ulp-month": "6",
                    "ulp-year": "1992",
                    "ulp-country": "USA",
                    "passwordPolicy.isFlexible": "false",
                    "strengthPolicy": "good",
                    "complexityOptions.minLength": "8",
                    "email": self.email,
                    "password": self.password,
                    "ulp-verify-email": self.email,
                    "ulp-verify-password": self.password,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://account.dentalcare.com",
                    "Referer": f"{self.BASE_URL}/u/signup?state={self.state}",
                },
                allow_redirects=False
            )

            if r.status_code in [301, 302]:
                parsed = urlparse(r.headers.get("Location", ""))
                params = parse_qs(parsed.query)
                self.resume_state = params.get("state", [""])[0]
            else:
                logger.error(f"[API-4] Failed: {r.status_code}")
                return False

            r = self.session.get(
                f"{self.BASE_URL}/authorize/resume",
                params={"state": self.resume_state}
            )

            if "/custom-prompt/" in r.url:
                parsed = urlparse(r.url)
                params = parse_qs(parsed.query)
                self.custom_prompt_state = params.get("state", [""])[0]

            self.context_token = get_context_token_from_html(r.text)
            if not self.context_token:
                logger.error("[API-5] No context_token found")
                return False

            return True

        except Exception as e:
            logger.error(f"[API-1-5] Error: {e}")
            return False

    def step6_7(self) -> bool:
        try:
            url = f"{self.BASE_URL}/forms/api/forms/{self.FORM_ID}?state={self.custom_prompt_state}"
            r = self.session.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Referer": f"{self.BASE_URL}/u/custom-prompt/{self.FORM_ID}",
                }
            )

            for name, value in r.headers.items():
                if 'checkpoint' in name.lower():
                    self.beat_signature = value

            url = f"{self.BASE_URL}/forms/api/forms/{self.FORM_ID}/validations/$start"

            payload = {
                "formData": {
                    "state": self.custom_prompt_state,
                    "context_token": self.context_token,
                },
                "metaData": {
                    "navigator": {
                        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "language": "en-US"
                    },
                    "navigation": {
                        "referer": f"{self.BASE_URL}/u/signup?state={self.state}&ui_locales=en-US",
                        "location": {
                            "protocol": "https:",
                            "hostname": "account.dentalcare.com",
                            "pathname": f"/u/custom-prompt/{self.FORM_ID}",
                            "search": f"?state={self.custom_prompt_state}&ui_locales=en-US",
                        }
                    }
                }
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://account.dentalcare.com",
                "Referer": f"{self.BASE_URL}/u/custom-prompt/{self.FORM_ID}?state={self.custom_prompt_state}&ui_locales=en-US",
                "auth0-forms-sdk-version": "undefined",
                "auth0-forms-language-hint": "en,en",
                "auth0-forms-location": f"{self.BASE_URL}/u/custom-prompt/{self.FORM_ID}",
            }

            if self.beat_signature:
                headers["Authorization"] = f"Bearer {self.beat_signature}"

            r = self.session.post(url, json=payload, headers=headers)

            if r.status_code == 200:
                data = r.json()
                if data.get("checkpoint"):
                    self.beat_signature = data["checkpoint"]
                return True

            logger.error(f"[API-7] Failed: {r.status_code}")
            return False

        except Exception as e:
            logger.error(f"[API-6-7] Error: {e}")
            return False

    def step8_contact(self) -> bool:
        try:
            url = f"{self.BASE_URL}/forms/api/forms/{self.FORM_ID}/validations/{self.STEP_CONTACT}"

            payload = {
                "formData": {
                    "mobile_number": "+8801856077645",
                    "address_1": "123 Main Street",
                    "city": "New York",
                    "state_address": "New York",
                    "zip_code": "10001",
                    "role": "Practicing Dental Professional & Support Staff",
                    "state": self.custom_prompt_state,
                    "context_token": self.context_token,
                },
                "metaData": {
                    "navigator": {"userAgent": "Mozilla/5.0", "language": "en-US"},
                }
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://account.dentalcare.com",
                "Referer": f"{self.BASE_URL}/u/custom-prompt/{self.FORM_ID}?state={self.custom_prompt_state}",
            }

            if self.beat_signature:
                headers["Authorization"] = f"Bearer {self.beat_signature}"

            r = self.session.post(url, json=payload, headers=headers)

            if r.status_code == 200:
                data = r.json()
                if data.get("checkpoint"):
                    self.beat_signature = data["checkpoint"]
                return True

            return False

        except Exception as e:
            logger.error(f"[API-8] Error: {e}")
            return False

    def step9_professional(self) -> bool:
        try:
            url = f"{self.BASE_URL}/forms/api/forms/{self.FORM_ID}/validations/{self.STEP_PROFESSIONAL}"

            payload = {
                "formData": {
                    "mobile_number": "+8801856077645",
                    "address_1": "123 Main Street",
                    "city": "New York",
                    "state_address": "New York",
                    "zip_code": "10001",
                    "role": "Practicing Dental Professional & Support Staff",
                    "dental_office_phone_number_dental_professional": "+8801856077645",
                    "role_type_dental_professional": "Dentist",
                    "speciality": "General Dentistry",
                    "dentalPracticeVisitDentalProffesional": "Yes",
                    "recommend_electric_toothbrush_dental_professional": "Do not recommend one specific brand",
                    "recommend_manual_toothbrush_dental_professional": "Do not recommend specific brand",
                    "recommend_toothpaste_dental_professional": "Do not recommend one specific brand",
                    "recommend_whitestrips_dental_professional": "Do not use one specific brand",
                    "state": self.custom_prompt_state,
                    "context_token": self.context_token,
                },
                "metaData": {
                    "navigator": {"userAgent": "Mozilla/5.0", "language": "en-US"},
                }
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://account.dentalcare.com",
                "Referer": f"{self.BASE_URL}/u/custom-prompt/{self.FORM_ID}?state={self.custom_prompt_state}",
            }

            if self.beat_signature:
                headers["Authorization"] = f"Bearer {self.beat_signature}"

            r = self.session.post(url, json=payload, headers=headers)

            if r.status_code == 200:
                data = r.json()
                if data.get("checkpoint"):
                    self.beat_signature = data["checkpoint"]
                return True

            return False

        except Exception as e:
            logger.error(f"[API-9] Error: {e}")
            return False

    def step10_submit(self) -> bool:
        try:
            url = f"{self.BASE_URL}/forms/api/forms/{self.FORM_ID}/submissions/"

            payload = {
                "formData": {
                    "mobile_number": "+8801856077645",
                    "address_1": "123 Main Street",
                    "city": "New York",
                    "state_address": "New York",
                    "zip_code": "10001",
                    "role": "Practicing Dental Professional & Support Staff",
                    "dental_office_phone_number_dental_professional": "+8801856077645",
                    "role_type_dental_professional": "Dentist",
                    "speciality": "General Dentistry",
                    "dentalPracticeVisitDentalProffesional": "Yes",
                    "recommend_electric_toothbrush_dental_professional": "Do not recommend one specific brand",
                    "recommend_manual_toothbrush_dental_professional": "Do not recommend specific brand",
                    "recommend_toothpaste_dental_professional": "Do not recommend one specific brand",
                    "recommend_whitestrips_dental_professional": "Do not use one specific brand",
                    "state": self.custom_prompt_state,
                    "context_token": self.context_token,
                },
                "metaData": {
                    "navigator": {"userAgent": "Mozilla/5.0", "language": "en-US"},
                }
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://account.dentalcare.com",
                "Referer": f"{self.BASE_URL}/u/custom-prompt/{self.FORM_ID}?state={self.custom_prompt_state}",
            }

            if self.beat_signature:
                headers["Authorization"] = f"Bearer {self.beat_signature}"

            r = self.session.post(url, json=payload, headers=headers)

            if r.status_code == 200:
                data = r.json()
                effect_type = data.get("effect", {}).get("type")
                if effect_type == "ENDING_SCREEN":
                    logger.info("[API-10] Registration successful - received ENDING_SCREEN")
                    return True
                return True

            return False

        except Exception as e:
            logger.error(f"[API-10] Error: {e}")
            return False

    def close(self):
        try:
            self.session.close()
        except:
            pass


class APIRegistrationService:
    def __init__(self, worker_id: str = "default"):
        self.worker_id = worker_id
        self._flow = None

    def register_account(self, account: AccountData) -> Tuple[bool, Optional[str], Optional[dict]]:
        logger.info(f"[API-SERVICE] Starting registration for: {account.email}")

        try:
            self._flow = APIRegistrationFlow()
            success, error = self._flow.register(account)

            if not success:
                self._flow.close()
                return False, error, None

            cookies = self._flow.session.cookies.get_dict()
            self._flow.close()
            self._flow = None

            logger.info(f"[API-SERVICE] Registration successful: {account.email}")
            return True, None, cookies

        except Exception as e:
            logger.error(f"[API-SERVICE] Registration error: {e}")
            return False, str(e), None

    def close(self):
        if self._flow:
            self._flow.close()
            self._flow = None
