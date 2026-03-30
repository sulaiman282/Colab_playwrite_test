#!/usr/bin/env python3
"""
Colab DentalCare Account Manager - Main Entry Point
Headless version optimized for Google Colab
"""

import sys
import os
import logging
import asyncio
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from models import AccountData, SystemStats
from services.worker_service import WorkerManager


def setup_logging():
    logs_dir = config.storage.logs_dir
    os.makedirs(logs_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(logs_dir, f'colab_run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'), encoding='utf-8'),
            logging.StreamHandler(),
        ]
    )
    logging.getLogger('playwright').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


class ColabRunner:
    def __init__(self, parallel_count: int = 3, batch_count: int = 0, delay: int = 2, phone_api_url: str = None):
        self.parallel_count = parallel_count
        self.batch_count = batch_count
        self.delay = delay
        self.worker_manager = None
        self.completed_accounts = []
        
        if phone_api_url:
            config.update_phone_api(phone_api_url)
        
        config.update_parallel_workers(parallel_count)
        config.update_batch_delay(delay)
        
        setup_logging()
        self.logger = logging.getLogger(__name__)
    
    def _status_callback(self, worker_id: str, status: str, account: AccountData = None):
        if status == "completed" and account:
            self.completed_accounts.append(account)
            phones = [p for p in account.phone_numbers if p.status.value in ['added', 'resent']]
            self.logger.info(f"[{worker_id}] Completed: {account.email} ({len(phones)} phones)")
        
        elif status == "phone_submitted" and account:
            self.logger.info(f"[{worker_id}] Phone submitted for: {account.email}")
        
        elif status == "phone_resent" and account:
            self.logger.info(f"[{worker_id}] Phone resent for: {account.email}")
    
    async def run(self):
        self.logger.info("=" * 60)
        self.logger.info("Colab DentalCare Account Manager Starting")
        self.logger.info("=" * 60)
        self.logger.info(f"Parallel Count: {self.parallel_count}")
        self.logger.info(f"Batch Count: {'Unlimited' if self.batch_count == 0 else self.batch_count}")
        self.logger.info(f"Delay: {self.delay}s")
        self.logger.info(f"Phone API: {config.api.phone_api_url}")
        self.logger.info(f"Headless: {config.browser.headless}")
        self.logger.info(f"API Registration: {config.account.register_via_api}")
        self.logger.info(f"Keep Browser Open: {config.account.keep_browser_open}")
        self.logger.info("=" * 60)
        
        self.worker_manager = WorkerManager(status_callback=self._status_callback)
        self.worker_manager.set_total_accounts(self.batch_count)
        
        try:
            await self.worker_manager.start_workers(self.parallel_count)
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        except Exception as e:
            self.logger.error(f"Error during execution: {e}")
        finally:
            await self.worker_manager.stop_all_workers()
            self._save_results()
            self._print_summary()
    
    def _save_results(self):
        try:
            completed = self.worker_manager.get_completed_accounts()
            
            results_dir = os.path.join(config.storage.base_dir, "results")
            os.makedirs(results_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = os.path.join(results_dir, f"accounts_{timestamp}.json")
            
            data = []
            for account in completed:
                phones = [p for p in account.phone_numbers if p.status.value in ['added', 'resent']]
                data.append({
                    'email': account.email,
                    'password': account.password,
                    'phones': [{'number': p.number, 'country': p.country, 'status': p.status.value} for p in phones],
                    'completed_at': account.completed_at.isoformat() if account.completed_at else None
                })
            
            with open(results_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Results saved to: {results_file}")
            print(f"\n[Saved] {len(data)} accounts to {results_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")
    
    def _print_summary(self):
        stats = self.worker_manager.get_system_stats()
        print("\n" + "=" * 60)
        print("EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Total Accounts Processed: {stats.total_accounts}")
        print(f"Completed Successfully: {stats.completed_accounts}")
        print(f"Failed: {stats.failed_accounts}")
        print(f"Total Phones Processed: {stats.successful_phones}")
        print("=" * 60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Colab DentalCare Account Manager')
    parser.add_argument('--parallel', type=int, default=3, help='Number of parallel browsers (default: 3)')
    parser.add_argument('--batch', type=int, default=0, help='Number of accounts (0=unlimited, default: 0)')
    parser.add_argument('--delay', type=int, default=2, help='Delay between batches in seconds (default: 2)')
    parser.add_argument('--phone-url', type=str, default=None, help='Phone API URL')
    
    args = parser.parse_args()
    
    runner = ColabRunner(
        parallel_count=args.parallel,
        batch_count=args.batch,
        delay=args.delay,
        phone_api_url=args.phone_url
    )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(runner.run())
    finally:
        loop.close()


if __name__ == '__main__':
    main()
