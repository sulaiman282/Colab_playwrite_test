#!/usr/bin/env python3
"""
Phone Number Service for Colab
Handles phone number API integration and country code matching
"""

import requests
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import time

from config import config
from models import PhoneNumber, PhoneStatus

logger = logging.getLogger(__name__)


class CountryCodeMatcher:
    def __init__(self):
        current_dir = Path(__file__).parent.parent
        self.country_codes_path = current_dir / "data" / "country_codes.json"
        self.country_codes = self._load_country_codes()
        self.phone_to_country_map = self._build_phone_mapping()
    
    def _load_country_codes(self) -> List[Dict[str, str]]:
        try:
            with open(self.country_codes_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Country codes file not found, using default")
            return [{"country_name": "United States", "iso_code": "US", "phone_code": "1", "selection_value": "US1"}]
        except Exception as e:
            logger.error(f"Error loading country codes: {e}")
            return []
    
    def _build_phone_mapping(self) -> Dict[str, List[Dict[str, str]]]:
        mapping = {}
        for country in self.country_codes:
            phone_code = country['phone_code']
            if phone_code not in mapping:
                mapping[phone_code] = []
            mapping[phone_code].append(country)
        return mapping
    
    def match_phone_to_country(self, phone_number: str, country_hint: Optional[str] = None) -> Dict[str, str]:
        try:
            if country_hint and country_hint != 'Unknown':
                for country in self.country_codes:
                    if country_hint.lower() in country['country_name'].lower():
                        return country
            
            clean_phone = phone_number.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            
            for length in [4, 3, 2, 1]:
                if len(clean_phone) >= length:
                    potential_code = clean_phone[:length]
                    if potential_code in self.phone_to_country_map:
                        countries = self.phone_to_country_map[potential_code]
                        if potential_code == '1':
                            for c in countries:
                                if c['iso_code'] == 'US':
                                    return c
                        return countries[0]
            
            return {"country_name": "United States", "iso_code": "US", "phone_code": "1", "selection_value": "US1"}
        except Exception as e:
            logger.error(f"Error matching phone to country: {e}")
            return {"country_name": "United States", "iso_code": "US", "phone_code": "1", "selection_value": "US1"}


class PhoneAPIService:
    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url if api_url is not None else config.api.phone_api_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.browser.user_agent,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'bypass-tunnel-reminder': 'bypass'
        })
    
    def get_phone_number(self, max_retries: int = 5, delay: int = 2) -> Optional[Dict[str, Any]]:
        for attempt in range(max_retries):
            try:
                response = self.session.get(self.api_url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        phone_data = data['data']['data']
                        return {
                            'number': phone_data['number'],
                            'country': phone_data.get('country', 'Unknown'),
                            'full_data': phone_data
                        }
                
            except requests.exceptions.Timeout:
                logger.error(f"Phone API timeout (attempt {attempt + 1})")
            except requests.exceptions.ConnectionError:
                logger.error(f"Phone API connection error (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Phone API error (attempt {attempt + 1}): {e}")
            
            if attempt < max_retries - 1:
                time.sleep(delay)
        
        return None
    
    def test_connection(self) -> bool:
        try:
            response = self.session.get(self.api_url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False


class PhoneService:
    def __init__(self, api_url: Optional[str] = None):
        self.api_service = PhoneAPIService(api_url)
        self.country_matcher = CountryCodeMatcher()
    
    def get_phone_with_country(self) -> Optional[PhoneNumber]:
        try:
            phone_data = self.api_service.get_phone_number()
            if not phone_data:
                return None
            
            phone_number = phone_data['number']
            country_hint = phone_data.get('country')
            country_data = self.country_matcher.match_phone_to_country(phone_number, country_hint=country_hint)
            
            return PhoneNumber(
                number=phone_number,
                country=country_data['country_name'],
                country_code=country_data['phone_code'],
                status=PhoneStatus.PENDING
            )
        except Exception as e:
            logger.error(f"Error getting phone with country: {e}")
            return None
    
    def test_service(self) -> bool:
        if not self.api_service.test_connection():
            logger.error("Phone API connection test failed")
            return False
        
        phone = self.get_phone_with_country()
        if not phone:
            logger.error("Failed to get test phone number")
            return False
        
        logger.info(f"Phone service test successful: {phone.number} ({phone.country})")
        return True
