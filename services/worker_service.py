#!/usr/bin/env python3
"""
Worker Service for Colab
Manages parallel account creation with headless Chrome
"""

import asyncio
import logging
import uuid
import threading
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime

from config import config
from models import AccountData, AccountStatus, SystemStats
from services.api_registration_service import APIRegistrationService, APIGenerator
from services.browser_flow_service import BrowserFlowService
from services.mfa_service import MFAService

logger = logging.getLogger(__name__)


class BatchController:
    def __init__(self, status_callback: Optional[Callable] = None,
                 browser_semaphore: Optional[asyncio.Semaphore] = None,
                 total_accounts: int = 0,
                 phone_api_url: str = None):
        self.status_callback = status_callback
        self.browser_semaphore = browser_semaphore
        self.total_accounts = total_accounts
        self.unlimited_mode = (total_accounts == 0)
        self.phone_api_url = phone_api_url or config.api.phone_api_url

        self.max_browsers = config.account.parallel_workers
        self.register_via_api = config.account.register_via_api
        self.keep_browser_open = config.account.keep_browser_open

        self.completed_accounts: List[AccountData] = []
        self.failed_accounts: List[AccountData] = []

        self.accounts_lock = threading.Lock()
        self.is_running = False
        self.should_stop = False

        self.system_stats = SystemStats()
        self.system_stats.start_time = datetime.now()

        mode_str = "UNLIMITED" if self.unlimited_mode else str(self.total_accounts)
        logger.info(f"[WORKER] Init: browsers={self.max_browsers}, mode={mode_str}")

    async def run(self) -> Dict[str, List[AccountData]]:
        self.is_running = True

        try:
            tasks = []
            for i in range(self.max_browsers):
                task = asyncio.create_task(self._browser_pipeline(i + 1))
                tasks.append(task)
                self.system_stats.active_workers += 1
                if self.status_callback:
                    self.status_callback(f"BROWSER-{i+1}", "browser_started", None)

            await asyncio.gather(*tasks, return_exceptions=True)

            logger.info(f"[WORKER] STOPPED: {len(self.completed_accounts)} completed, {len(self.failed_accounts)} failed")

        except Exception as e:
            logger.error(f"[WORKER] Critical error: {e}")
        finally:
            self.is_running = False
            self.system_stats.active_workers = 0

        return {
            'completed': self.completed_accounts.copy(),
            'failed': self.failed_accounts.copy(),
            'registered': []
        }

    async def _browser_pipeline(self, browser_id: int) -> None:
        logger.info(f"[BROWSER-{browser_id}] Pipeline started")

        pending_reg: Optional[asyncio.Future] = None
        current_account = None
        accounts_processed = 0

        while not self.should_stop:
            try:
                if current_account is None:
                    if pending_reg is None:
                        logger.info(f"[BROWSER-{browser_id}] Starting registration...")
                        pending_reg = asyncio.create_task(self._register_account(browser_id))

                    logger.info(f"[BROWSER-{browser_id}] Waiting for registration...")
                    current_account = await pending_reg
                    pending_reg = None

                    if not current_account:
                        logger.error(f"[BROWSER-{browser_id}] Registration failed, retrying...")
                        await asyncio.sleep(2)
                        continue
                    logger.info(f"[BROWSER-{browser_id}] Registered: {current_account.email}")

                if pending_reg is None:
                    logger.info(f"[BROWSER-{browser_id}] Pre-registering next account...")
                    pending_reg = asyncio.create_task(self._register_account(browser_id))

                logger.info(f"[BROWSER-{browser_id}] Processing MFA: {current_account.email}")
                success = await self._mfa_single_account(browser_id, current_account)

                if success:
                    with self.accounts_lock:
                        self.completed_accounts.append(current_account)
                    accounts_processed += 1
                    logger.info(f"[BROWSER-{browser_id}] COMPLETED ({accounts_processed}): {current_account.email}")
                else:
                    with self.accounts_lock:
                        self.failed_accounts.append(current_account)

                current_account = await pending_reg
                pending_reg = None

                if not current_account:
                    logger.error(f"[BROWSER-{browser_id}] Pre-registration failed, retrying...")
                    await asyncio.sleep(2)
                    continue

            except Exception as e:
                logger.error(f"[BROWSER-{browser_id}] Pipeline error: {e}")
                await asyncio.sleep(2)

        logger.info(f"[BROWSER-{browser_id}] Pipeline stopped. Processed: {accounts_processed}")

    async def _register_account(self, browser_id: int) -> Optional[AccountData]:
        try:
            account = APIGenerator.generate_account()

            if self.register_via_api:
                api_service = APIRegistrationService(f"reg-{browser_id}")
                success, error, cookies = api_service.register_account(account)
                api_service.close()

                if success:
                    account.status = AccountStatus.CREATED
                    self.system_stats.total_accounts += 1
                    return account
                else:
                    account.status = AccountStatus.FAILED
                    account.error_message = error
                    return None

            return None

        except Exception as e:
            logger.error(f"[BROWSER-{browser_id}] Registration error: {e}")
            return None

    async def _mfa_single_account(self, browser_id: int, account: AccountData) -> bool:
        if not account:
            return False

        try:
            browser_flow = BrowserFlowService(f"browser-{browser_id}", headless=True)

            result = await browser_flow.login_and_navigate(account)
            if isinstance(result, tuple):
                success, error = result[0], result[1] if len(result) > 1 else None
            else:
                success, error = result, None
            
            if not success:
                logger.error(f"[MFA-{browser_id}] Login failed: {error}")
                await browser_flow.stop_browser()
                account.status = AccountStatus.FAILED
                return False

            page = browser_flow.get_page()
            if not page:
                await browser_flow.stop_browser()
                account.status = AccountStatus.FAILED
                return False

            mfa_service = MFAService(self._phone_callback, self.phone_api_url)
            mfa_result = await mfa_service.process_account_phones(account, page)

            await browser_flow.stop_browser()

            if mfa_result:
                account.status = AccountStatus.COMPLETED
                account.completed_at = datetime.now()
                self.system_stats.completed_accounts += 1
                self.system_stats.successful_phones += len([p for p in account.phone_numbers if p.status.value in ['added', 'resent']])
                return True
            else:
                account.status = AccountStatus.FAILED
                return False

        except Exception as e:
            logger.error(f"[MFA-{browser_id}] Error: {e}")
            account.status = AccountStatus.FAILED
            return False

    async def _phone_callback(self, event: str, account: AccountData) -> None:
        if self.status_callback:
            try:
                self.status_callback("SYSTEM", event, account)
            except Exception as e:
                logger.debug(f"Callback error: {e}")

    def stop(self) -> None:
        logger.info("[WORKER] Stopping all browsers...")
        self.should_stop = True
        self.is_running = False


class WorkerManager:
    MAX_CONCURRENT_BROWSERS = 50

    def __init__(self, status_callback: Optional[Callable] = None, phone_api_url: str = None):
        self.status_callback = status_callback
        self.is_running = False
        self.system_stats = SystemStats()
        self._browser_semaphore = None
        self._batch_controller: Optional[BatchController] = None
        self._batch_task: Optional[asyncio.Task] = None
        self._total_accounts_to_create = 0
        self._phone_api_url = phone_api_url
        self.completed_accounts: List[AccountData] = []
        self.accounts_lock = threading.Lock()

    def set_total_accounts(self, count: int) -> None:
        self._total_accounts_to_create = count
        logger.info(f"[MANAGER] Total accounts to create: {count}")
    
    def set_phone_api_url(self, url: str) -> None:
        self._phone_api_url = url
        logger.info(f"[MANAGER] Phone API URL: {url}")

    async def start_workers(self, num_workers: int) -> None:
        self.is_running = True
        self.system_stats.start_time = datetime.now()

        max_limit = max(num_workers, self.MAX_CONCURRENT_BROWSERS)
        self._browser_semaphore = asyncio.Semaphore(max_limit)

        logger.info(f"[MANAGER] Starting with {num_workers} parallel workers")

        self._batch_controller = BatchController(
            status_callback=self._worker_status_callback,
            browser_semaphore=self._browser_semaphore,
            total_accounts=self._total_accounts_to_create,
            phone_api_url=self._phone_api_url
        )

        self._batch_task = asyncio.create_task(self._run_batch_controller())

        while self.is_running and self._batch_task and not self._batch_task.done():
            await asyncio.sleep(1)

    async def _run_batch_controller(self) -> None:
        try:
            if not self._batch_controller:
                return

            results = await self._batch_controller.run()

            with self.accounts_lock:
                self.completed_accounts = results.get('completed', [])

            logger.info(f"[MANAGER] Batch processing complete: {len(self.completed_accounts)} completed")

        except Exception as e:
            logger.error(f"[MANAGER] Batch controller error: {e}")
        finally:
            self.is_running = False

    async def stop_all_workers(self) -> None:
        logger.info("Stopping all workers...")
        self.is_running = False

        if self._batch_controller:
            self._batch_controller.stop()

        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        logger.info("All workers stopped")

    def _worker_status_callback(self, worker_id: str, status: str, account: Optional[AccountData]) -> None:
        try:
            if status == "completed" and account:
                with self.accounts_lock:
                    if account.status == AccountStatus.COMPLETED:
                        self.completed_accounts.append(account)
                        phone_count = len([p for p in account.phone_numbers if p.status.value in ['added', 'resent']])
                        if phone_count > 0:
                            self.system_stats.completed_accounts += 1
                            self.system_stats.successful_phones += phone_count
                        else:
                            self.system_stats.failed_accounts += 1

            self.system_stats.active_workers = self._batch_controller.system_stats.active_workers if self._batch_controller else 0

            if self.status_callback:
                self.status_callback(worker_id, status, account)

        except Exception as e:
            logger.error(f"Error in worker status callback: {e}")

    def get_completed_accounts(self) -> List[AccountData]:
        with self.accounts_lock:
            return [a for a in self.completed_accounts
                    if a.status == AccountStatus.COMPLETED
                    and sum(1 for p in a.phone_numbers if p.status.value in ['added', 'resent']) > 0]

    def get_system_stats(self) -> SystemStats:
        if self._batch_controller:
            self.system_stats.total_accounts = self._batch_controller.system_stats.total_accounts
            self.system_stats.completed_accounts = self._batch_controller.system_stats.completed_accounts
            self.system_stats.failed_accounts = self._batch_controller.system_stats.failed_accounts
            self.system_stats.successful_phones = self._batch_controller.system_stats.successful_phones
            self.system_stats.active_workers = self._batch_controller.system_stats.active_workers
        return self.system_stats
