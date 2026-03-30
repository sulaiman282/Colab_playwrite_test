#!/usr/bin/env python3
"""
MFA Service for Colab
Handles phone number addition and MFA enrollment
"""

import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from playwright.async_api import Page

from config import config
from models import AccountData, PhoneNumber, PhoneStatus
from services.phone_service import PhoneService
from services.navigation_helpers import is_view_profile_url

logger = logging.getLogger(__name__)


class MFAService:
    def __init__(self, phone_callback=None, phone_api_url: Optional[str] = None):
        self.phone_service = PhoneService(phone_api_url)
        self.attempt_count = 0
        self.max_attempts_per_session = 10
        self.country_codes = self._load_country_codes()
        self.phone_callback = phone_callback

    def _load_country_codes(self) -> List[Dict[str, str]]:
        try:
            current_dir = Path(__file__).parent.parent
            country_codes_path = current_dir / "data" / "country_codes.json"
            with open(country_codes_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Country codes file not found, using fallback")
            return [
                {"country_name": "Central African Republic", "iso_code": "CF", "phone_code": "236", "selection_value": "CF236"},
                {"country_name": "United States", "iso_code": "US", "phone_code": "1", "selection_value": "US1"}
            ]
        except Exception as e:
            logger.error(f"Error loading country codes: {e}")
            return [
                {"country_name": "Central African Republic", "iso_code": "CF", "phone_code": "236", "selection_value": "CF236"},
                {"country_name": "United States", "iso_code": "US", "phone_code": "1", "selection_value": "US1"}
            ]

    async def process_account_phones(self, account: AccountData, page: Page) -> bool:
        logger.info(f"Processing phones for account: {account.email}")

        try:
            if not self._is_mfa_page(page.url):
                logger.info("Navigating to MFA via Edit button")
                edit_reached = await self._navigate_to_mfa_via_edit(page)
                if not edit_reached:
                    logger.error("Could not reach MFA enrollment page")
                    return False

            phones_needed = config.account.numbers_per_account
            successful_phones = 0

            for i in range(phones_needed):
                logger.info(f"Processing phone {i+1}/{phones_needed}")

                if self.attempt_count >= self.max_attempts_per_session:
                    logger.warning(f"Exceeded max attempts ({self.max_attempts_per_session})")
                    return False

                phone = self.phone_service.get_phone_with_country()
                if not phone:
                    logger.error(f"Failed to get phone number {i+1}")
                    self.attempt_count += 1
                    continue

                logger.info(f"Got phone: {phone.number} ({phone.country} +{phone.country_code})")
                account.phone_numbers.append(phone)

                if not self._is_mfa_page(page.url):
                    reached = await self._navigate_to_mfa_via_edit(page)
                    if not reached:
                        phone.status = PhoneStatus.FAILED
                        return False

                success = False
                for retry in range(3):
                    await self._handle_survey_popup(page)
                    success = await self._fill_phone_on_mfa_page(page, phone)
                    if success:
                        break
                    await asyncio.sleep(3)

                if success:
                    phone.status = PhoneStatus.ADDED
                    phone.added_at = datetime.now()
                    successful_phones += 1

                    if self.phone_callback:
                        await self.phone_callback("phone_submitted", account)

                    resend_success = await self._resend_exact_flow(page)
                    if resend_success:
                        phone.status = PhoneStatus.RESENT
                        phone.resent_at = datetime.now()
                        logger.info(f"Phone {phone.number} added and resent successfully")

                        if self.phone_callback:
                            await self.phone_callback("phone_resent", account)
                    else:
                        logger.warning(f"Phone {phone.number} added but resend failed")

                    if i < phones_needed - 1:
                        await self._click_edit_on_mfa_page(page)
                        await asyncio.sleep(2)
                else:
                    phone.status = PhoneStatus.FAILED
                    logger.error(f"Failed to add phone {phone.number}")
                    return False

                self.attempt_count += 1
                await asyncio.sleep(1)

            logger.info(f"Phone processing completed: {successful_phones}/{len(account.phone_numbers)} successful")
            return successful_phones > 0

        except Exception as e:
            logger.error(f"Error processing phones for {account.email}: {e}")
            return False

    def _is_mfa_page(self, url: str) -> bool:
        return 'mfa' in url and ('sms-enrollment' in url or 'sms_enrollment' in url)

    async def _navigate_to_mfa_via_edit(self, page: Page) -> bool:
        # First check if we're already on MFA page
        if self._is_mfa_page(page.url):
            logger.info("Already on MFA page")
            # Wait for page to fully load
            try:
                await page.wait_for_selector('#phone, button[value="pick-country-code"]', timeout=5000)
            except:
                # Page might need reload
                logger.info("Page elements not ready, reloading...")
                await page.reload()
                await page.wait_for_timeout(2000)
            return True
        
        # Handle verification page - need to go back to enrollment
        if 'mfa-sms-enrollment-verify' in page.url:
            logger.info("On verification page, trying to get back to enrollment")
            try:
                # Look for Edit or Back button
                edit_selectors = [
                    'a:has-text("Edit")', 'button:has-text("Edit")',
                    'a:has-text("Back")', 'button:has-text("Back")',
                    'a[href*="mfa-sms-enrollment"]',
                ]
                for selector in edit_selectors:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(force=True)
                        await page.wait_for_timeout(2000)
                        logger.info(f"Clicked {selector} to go back to enrollment")
                        if self._is_mfa_page(page.url):
                            return True
                        break
                
                # Try JS navigation back
                await page.evaluate("""
                    () => {
                        // Find Edit link
                        const editLink = Array.from(document.querySelectorAll('a, button')).find(el => 
                            el.textContent && el.textContent.trim().toLowerCase().includes('edit')
                        );
                        if (editLink) {
                            editLink.click();
                            return 'edit-clicked';
                        }
                        // Try going back
                        history.back();
                        return 'back-called';
                    }
                """)
                await page.wait_for_timeout(2000)
                
                if self._is_mfa_page(page.url):
                    return True
            except Exception as e:
                logger.warning(f"Verification page handling error: {e}")
        
        # Check if we're on custom-prompt (profile setup required)
        if 'custom-prompt' in page.url:
            logger.info("On custom-prompt page, trying to find Continue/Skip button")
            try:
                # Try to find Continue or Skip button to complete profile setup
                continue_selectors = [
                    'button:has-text("Continue")',
                    'button:has-text("Skip")',
                    'button:has-text("Submit")',
                    'button[type="submit"]',
                    'button[name="action"]',
                ]
                for selector in continue_selectors:
                    btn = page.locator(selector).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(force=True)
                        await page.wait_for_timeout(2000)
                        logger.info(f"Clicked {selector} on custom-prompt")
                        if self._is_mfa_page(page.url):
                            return True
                        break
                
                # Try JS click
                await page.evaluate("""
                    () => {
                        const btn = Array.from(document.querySelectorAll('button')).find(b => 
                            b.textContent.includes('Continue') || b.textContent.includes('Skip') || b.textContent.includes('Submit')
                        );
                        if (btn) btn.click();
                    }
                """)
                await page.wait_for_timeout(2000)
            except Exception as e:
                logger.warning(f"Custom-prompt handling error: {e}")
        
        # First try direct MFA link (most reliable)
        try:
            mfa_link = page.locator('a[href*="mfa-sms-enrollment"]').first
            if await mfa_link.count() > 0 and await mfa_link.is_visible():
                await mfa_link.click(force=True)
                await page.wait_for_timeout(1500)
                if self._is_mfa_page(page.url):
                    logger.info("Reached MFA via direct link")
                    return True
        except:
            pass
        
        # Try to find Edit button
        edit_selectors = [
            'a[href*="mfa-sms-enrollment"]',
            'a[aria-label*="Edit"]',
            'a:has-text("Edit")',
            'button:has-text("Edit")',
        ]
        for selector in edit_selectors:
            try:
                el = page.locator(selector).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click(force=True)
                    await page.wait_for_timeout(1500)
                    if self._is_mfa_page(page.url):
                        logger.info(f"Reached MFA page: {page.url}")
                        return True
            except:
                continue

        if self._is_mfa_page(page.url):
            return True

        # Navigate directly to MFA page as fallback
        try:
            await page.goto('https://account.dentalcare.com/u/mfa-sms-enrollment',
                          wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(1500)
            if self._is_mfa_page(page.url):
                logger.info("Direct navigation to MFA page successful")
                return True
        except Exception as e:
            logger.warning(f"Direct MFA navigation failed: {e}")

        # Navigate to view-profile and try Edit again
        try:
            if not is_view_profile_url(page.url):
                await page.goto('https://www.dentalcare.com/en-us/user-account/view-profile',
                              wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"view-profile navigation failed: {e}")

        clicked = await self._click_edit_on_mfa_page(page)
        if clicked:
            await page.wait_for_timeout(1500)
            if self._is_mfa_page(page.url):
                return True

        logger.error("Could not reach MFA enrollment")
        return False

    async def _click_edit_on_mfa_page(self, page: Page) -> bool:
        logger.info(f"On page: {page.url}")
        
        # Handle verification page - look for Edit button to go back
        if 'mfa-sms-enrollment-verify' in page.url:
            logger.info("On verification page, looking for Edit button")
            
            # First scroll to top
            await page.evaluate("window.scrollTo(0, 0);")
            await page.wait_for_timeout(500)
            
            # Try multiple selectors
            edit_selectors = [
                'a:has-text("Edit")',
                'button:has-text("Edit")',
                'a[href*="mfa-sms-enrollment"]:not([href*="verify"])',
                'button[aria-label*="Edit"]',
                '[role="button"]:has-text("Edit")',
                '.ulp-page-actions a',
                'a.back-link',
            ]
            
            for selector in edit_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        is_visible = await el.is_visible()
                        text = (await el.text_content() or '')[:50] if hasattr(el, 'text_content') else ''
                        logger.info(f"Found {selector}: visible={is_visible}, text={text}")
                        if is_visible:
                            await el.click(force=True)
                            await page.wait_for_timeout(2000)
                            logger.info(f"Clicked Edit via: {selector}")
                            return True
                except Exception as e:
                    logger.debug(f"Selector {selector} error: {e}")
                    pass

            # Try JavaScript to find Edit button
            try:
                result = await page.evaluate("""
                    () => {
                        // Find any element with "Edit" text
                        const all = document.querySelectorAll('a, button, [role="button"]');
                        for (const el of all) {
                            const text = (el.textContent || '').trim();
                            if (text.toLowerCase().includes('edit')) {
                                el.scrollIntoView({behavior: 'instant', block: 'center'});
                                el.click();
                                return 'found:' + text;
                            }
                        }
                        
                        // Try history back
                        if (window.location.href.includes('verify')) {
                            history.back();
                            return 'back';
                        }
                        return 'not-found';
                    }
                """)
                logger.info(f"JS result: {result}")
                if result != 'not-found':
                    await page.wait_for_timeout(2000)
                    return True
            except Exception as e:
                logger.error(f"JS error: {e}")
        
        return False

    async def _fill_phone_on_mfa_page(self, page: Page, phone: PhoneNumber) -> bool:
        """
        Fill phone on MFA enrollment page with robust country selection.
        Real DOM (observed):
          • Picker  : <button value="pick-country-code" aria-label="Select country code,
                        currently set to {name}, {ISO}, +{code}">
          • Phone   : <input id="phone" name="phone">
          • Continue: <button value="default" name="action">
        """
        try:
            # Check if we're on verification page - click Edit to go back
            if 'mfa-sms-enrollment-verify' in page.url:
                logger.info("On verify page, clicking Edit to go back to enrollment")
                if await self._click_edit_on_mfa_page(page):
                    await page.wait_for_timeout(2000)
                    if self._is_mfa_page(page.url):
                        logger.info("Successfully returned to enrollment page")
                    else:
                        try:
                            await page.goto('https://account.dentalcare.com/u/mfa-sms-enrollment', timeout=20000)
                            await page.wait_for_timeout(2000)
                        except:
                            pass
                        if not self._is_mfa_page(page.url):
                            logger.error("Could not return to enrollment page")
                            return False
                else:
                    logger.error("Could not click Edit on verify page")
                    return False
            
            # Wait for MFA page to fully load
            try:
                await page.wait_for_selector('#phone, button[value="pick-country-code"]', timeout=10000)
            except:
                pass

            # Build the exact selectors from JSON data
            selection_value = self._get_country_selection_value(phone)
            aria_label      = self._get_country_button_name(phone)
            country_text    = aria_label.split(' (+')[0]
            logger.info(f"Targeting country: aria='{aria_label}'  value='{selection_value}'")

            # Pre-check: read the picker button's aria-label to see what country is currently set
            country_already_selected = False
            try:
                picker_btn = page.locator('button[value="pick-country-code"]').first
                if await picker_btn.count() > 0:
                    current_label = (await picker_btn.get_attribute('aria-label') or '').strip()
                    if current_label:
                        marker = 'currently set to'
                        idx = current_label.lower().find(marker)
                        if idx != -1:
                            current_country_str = current_label[idx + len(marker):].strip().lower()
                        else:
                            current_country_str = current_label.lower()

                        target_lower = country_text.lower()
                        logger.info(f"Picker currently set to: '{current_country_str}' | target: '{target_lower}'")

                        if target_lower in current_country_str or current_country_str.startswith(target_lower):
                            country_already_selected = True
                            logger.info(f"Country already correct ('{current_country_str}'), skipping picker")
                        else:
                            logger.info(f"Country mismatch - need to select '{country_text}' (currently '{current_country_str}')")
            except Exception as e:
                logger.debug(f"Pre-check for current country failed: {e}")

            if not country_already_selected:
                # Step 1: Submit the pick-country-code form to navigate to country selection page
                logger.info("Clicking pick-country-code button...")
                picker_clicked = False
                try:
                    picker_btn = page.locator('button[value="pick-country-code"]').first
                    if await picker_btn.count() > 0 and await picker_btn.is_visible():
                        await picker_btn.click(force=True)
                        picker_clicked = True
                        logger.debug("Clicked picker via button[value='pick-country-code']")
                except Exception as e:
                    logger.debug(f"Picker click failed: {e}")

                if not picker_clicked:
                    try:
                        clicked = await page.evaluate("""
                            () => {
                                const btn = document.querySelector('button[value="pick-country-code"]');
                                if (btn) { btn.click(); return true; }
                                const form = Array.from(document.querySelectorAll('form')).find(f =>
                                    f.querySelector('button[value="pick-country-code"]')
                                );
                                if (form) { form.submit(); return true; }
                                return false;
                            }
                        """)
                        if clicked:
                            picker_clicked = True
                            logger.debug("Clicked picker via JS fallback")
                    except Exception as e:
                        logger.debug(f"JS picker fallback failed: {e}")

                if not picker_clicked:
                    logger.error("Could not click country picker button")
                    return False

                # Wait for the country list page to load
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(1500)

                # Step 2: On the country list page, find and click the target country
                selected = False

                # 2a. Search input
                try:
                    search_input = page.locator(
                        '#with-search, '
                        'input[aria-controls="with-selector-list"], '
                        'input[placeholder*="Search"], '
                        'input[type="search"]'
                    ).first
                    if await search_input.count() > 0:
                        await search_input.click(force=True)
                        await search_input.fill('')
                        await search_input.type(country_text, delay=40)
                        await page.wait_for_timeout(600)

                        try:
                            await page.wait_for_selector(f'button[value="{selection_value}"]', timeout=5000, state='visible')
                        except Exception:
                            await page.wait_for_timeout(800)

                        el = page.locator(f'button[value="{selection_value}"]').first
                        if await el.count() > 0 and await el.is_visible():
                            await el.click(force=True)
                            await page.wait_for_timeout(800)
                            selected = True
                            logger.info(f"Selected country via search+value: {aria_label}")
                except Exception as e:
                    logger.debug(f"Search-based selection failed: {e}")

                # 2b. Direct value click (no search)
                if not selected:
                    try:
                        el = page.locator(f'button[value="{selection_value}"]').first
                        if await el.count() > 0:
                            await el.scroll_into_view_if_needed()
                            await el.click(force=True)
                            await page.wait_for_timeout(800)
                            selected = True
                            logger.info(f"Selected country by direct value: {selection_value}")
                    except Exception as e:
                        logger.debug(f"Direct value click failed: {e}")

                # 2c. JS search + click
                if not selected:
                    try:
                        js_result = await page.evaluate("""
                            ([selVal, countryTxt]) => {
                                const inp = document.querySelector(
                                    '#with-search, input[aria-controls="with-selector-list"], input[type="search"]'
                                );
                                if (inp) {
                                    inp.value = countryTxt;
                                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                                    inp.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
                                }
                                const btn = document.querySelector(`button[value="${selVal}"]`);
                                if (btn) { btn.click(); return 'clicked'; }
                                return null;
                            }
                        """, [selection_value, country_text])
                        if js_result:
                            await page.wait_for_timeout(800)
                            selected = True
                            logger.info(f"Selected country via JS search: {selection_value}")
                    except Exception as e:
                        logger.debug(f"JS search fallback failed: {e}")

                # 2d. Scroll-scan fallback
                if not selected:
                    logger.info(f"Trying scroll-scan for: {aria_label}")
                    try:
                        search_input = page.locator(
                            '#with-search, input[aria-controls="with-selector-list"], input[type="search"]'
                        ).first
                        if await search_input.count() > 0:
                            await search_input.fill('')
                            await page.wait_for_timeout(400)

                        SCROLL_STEP = 300
                        MAX_SCROLLS = 60
                        for scroll_idx in range(MAX_SCROLLS):
                            el = page.locator(f'button[value="{selection_value}"]').first
                            if await el.count() > 0:
                                try:
                                    await el.scroll_into_view_if_needed()
                                    await el.wait_for(state='visible', timeout=2000)
                                    await el.click(force=True)
                                    await page.wait_for_timeout(800)
                                    selected = True
                                    logger.info(f"Selected via scroll-scan (step {scroll_idx}): {aria_label}")
                                except Exception as ce:
                                    logger.debug(f"Scroll-scan click failed at step {scroll_idx}: {ce}")
                                break
                            await page.evaluate("""
                                () => {
                                    const list = document.querySelector(
                                        '#with-selector-list, ul[id*="selector"], [class*="selector-list"]'
                                    );
                                    if (list) list.scrollTop += 300;
                                    else window.scrollBy(0, 300);
                                }
                            """)
                            await page.wait_for_timeout(150)
                        else:
                            logger.warning("Scroll-scan exhausted without finding target")
                    except Exception as se:
                        logger.debug(f"Scroll-scan error: {se}")

                if not selected:
                    logger.error(f"All country selection attempts failed for: {aria_label}")
                    return False

                # After selecting a country the page navigates back to the phone input form
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(1000)

            # Step 3: Wait for phone input
            try:
                await page.wait_for_selector('#phone, input[name="phone"], input[type="tel"]', timeout=10000, state='visible')
            except:
                pass

            local_phone = self._extract_local_phone(phone.number)
            phone_filled = False
            for sel in ['#phone', 'input[name="phone"]', 'input[type="tel"]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(force=True)
                        await el.fill(local_phone)
                        phone_filled = True
                        break
                except:
                    continue

            if not phone_filled:
                try:
                    await page.get_by_role('textbox', name='Enter your phone number').click()
                    await page.get_by_role('textbox', name='Enter your phone number').fill(local_phone)
                    phone_filled = True
                except:
                    pass

            if not phone_filled:
                return False

            # Click Continue
            continue_clicked = False
            for sel in ['button[name="action"][value="default"]', 'button[name="action"][value="continue"]',
                       'button[data-action-button-primary="true"]', 'button[name="Continue"]', 'button[type="submit"]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(force=True)
                        await page.wait_for_timeout(2000)
                        continue_clicked = True
                        break
                except:
                    continue

            if not continue_clicked:
                try:
                    await page.get_by_role('button', name='Continue').click()
                    await page.wait_for_timeout(2000)
                except:
                    return False

            logger.info(f"Phone {phone.number} submitted successfully")
            return True

        except Exception as e:
            logger.error(f"Error filling phone on MFA page: {e}")
            return False

    async def _resend_exact_flow(self, page: Page) -> bool:
        try:
            await page.wait_for_timeout(500)
            
            # Try direct JS click first (fastest)
            try:
                result = await page.evaluate("""
                    () => {
                        // Try by value first
                        const byValue = document.querySelector('button[value="resend-code"]');
                        if (byValue) { byValue.click(); return 'by-value'; }
                        // Try by text
                        const byText = Array.from(document.querySelectorAll('button'))
                            .find(btn => btn.textContent && btn.textContent.trim().toLowerCase() === 'resend');
                        if (byText) { byText.click(); return 'by-text'; }
                        // Try in form
                        const form = document.querySelector('.ulp-action-form-resend-code, form[class*="resend"]');
                        if (form) {
                            const btn = form.querySelector('button');
                            if (btn) { btn.click(); return 'in-form'; }
                        }
                        return 'not-found';
                    }
                """)
                if result != 'not-found':
                    logger.info(f"Resend clicked via: {result}")
                    await page.wait_for_timeout(500)
                    return True
            except:
                pass

            # Fallback to locator
            resend_selectors = [
                'button[name="action"][value="resend-code"]',
                'button:has-text("Resend")',
                'button[value="resend-code"]',
                '.ulp-action-form-resend-code button',
                'button[class*="resend"]',
            ]

            for selector in resend_selectors:
                try:
                    resend_btn = page.locator(selector).first
                    if await resend_btn.count() > 0 and await resend_btn.is_visible():
                        await resend_btn.click(force=True)
                        logger.info("Resend clicked")
                        await page.wait_for_timeout(500)
                        return True
                except:
                    pass

            return False

        except Exception as e:
            logger.error(f"Error in resend: {e}")
            return False

    def _get_country_button_name(self, phone: PhoneNumber) -> str:
        for country in self.country_codes:
            if country['country_name'] == phone.country:
                return f"{country['country_name']} (+{country['phone_code']})"
        for country in self.country_codes:
            if country['phone_code'] == phone.country_code:
                return f"{country['country_name']} (+{country['phone_code']})"
        return 'Central African Republic (+236)'

    def _get_country_selection_value(self, phone: PhoneNumber) -> str:
        for country in self.country_codes:
            if country['country_name'] == phone.country:
                return f"selection-action::{country.get('selection_value', country['iso_code'] + country['phone_code'])}"
        for country in self.country_codes:
            if country['phone_code'] == phone.country_code:
                return f"selection-action::{country.get('selection_value', country['iso_code'] + country['phone_code'])}"
        return 'selection-action::CF236'

    def _extract_local_phone(self, phone_number: str) -> str:
        clean_phone = phone_number.replace('+', '')
        sorted_codes = sorted(self.country_codes, key=lambda c: len(c['phone_code']), reverse=True)
        for country in sorted_codes:
            phone_code = country['phone_code']
            if clean_phone.startswith(phone_code):
                return clean_phone[len(phone_code):]
        return clean_phone[-8:] if len(clean_phone) >= 8 else clean_phone

    async def _handle_survey_popup(self, page: Page) -> None:
        try:
            await page.wait_for_timeout(300)
            await page.evaluate("""
                const surveySelectors = ['.QSIWebResponsive', '[class*="survey"]', '[id*="survey"]',
                    'iframe[title*="Survey"]', '[class*="qualtrics"]', '.modal', '.overlay'];
                surveySelectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        try { el.remove(); } catch(e) { el.style.display = 'none'; }
                    });
                });
            """)
        except:
            pass
