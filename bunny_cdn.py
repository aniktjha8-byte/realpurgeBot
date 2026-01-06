import aiohttp
import asyncio
from typing import List, Dict, Tuple, Callable, Optional
import logging
import time
from collections import deque

logger = logging.getLogger(__name__)

class BunnyCDNPurger:
    """Handle Bunny CDN cache purging operations."""
    
    PURGE_ENDPOINT = "https://api.bunny.net/purge"
    DEFAULT_CONCURRENCY = 15
    MAX_RETRIES = 3
    
    def __init__(self, concurrency: int = DEFAULT_CONCURRENCY, state_manager=None, session_id: str = None):
        self.session = None
        self.concurrency = concurrency
        self.semaphore = None
        self.state_manager = state_manager
        self.session_id = session_id
        self.retry_queue = deque()
        self.failed_urls = []
        self.completed_urls = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        self.semaphore = asyncio.Semaphore(self.concurrency)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def purge_url(self, url: str, api_key: str, retry: int = 0) -> Tuple[bool, str, int]:
        """
        Purge a single URL from Bunny CDN cache with retry logic.
        
        Args:
            url: The URL to purge
            api_key: The Bunny CDN API key
            retry: Current retry attempt
            
        Returns:
            Tuple of (success: bool, message: str, retry_after: int)
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        if not self.semaphore:
            self.semaphore = asyncio.Semaphore(self.concurrency)
        
        headers = {
            "AccessKey": api_key,
            "Content-Type": "application/json"
        }
        
        params = {
            "url": url
        }
        
        async with self.semaphore:
            try:
                async with self.session.post(
                    self.PURGE_ENDPOINT,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        return True, f"✅ {url}", 0
                    elif response.status == 429:
                        retry_after = int(response.headers.get('Retry-After', '5'))
                        if retry < 3:
                            await asyncio.sleep(retry_after)
                            return await self.purge_url(url, api_key, retry + 1)
                        return False, f"⚠️ Rate limited: {url}", retry_after
                    elif response.status == 401:
                        return False, f"❌ Auth failed: {url}", 0
                    else:
                        text = await response.text()
                        return False, f"❌ Failed ({response.status}): {url}", 0
                        
            except asyncio.TimeoutError:
                if retry < 2:
                    await asyncio.sleep(2)
                    return await self.purge_url(url, api_key, retry + 1)
                return False, f"⏱️ Timeout: {url}", 0
            except Exception as e:
                logger.error(f"Error purging {url}: {str(e)}")
                return False, f"❌ Error: {url}", 0
    
    async def purge_urls_batch(
        self, 
        urls: List[str], 
        api_key: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        skip_urls: Optional[List[str]] = None
    ) -> List[Tuple[str, bool, str]]:
        """
        Purge multiple URLs concurrently with progress tracking and error recovery.
        
        Args:
            urls: List of URLs to purge
            api_key: The Bunny CDN API key
            progress_callback: Optional callback for progress updates (completed, total)
            skip_urls: URLs to skip (already completed)
            
        Returns:
            List of tuples (url, success, message)
        """
        skip_set = set(skip_urls or [])
        urls_to_process = [url for url in urls if url not in skip_set]
        total = len(urls_to_process)
        completed = 0
        results = []
        
        if not urls_to_process:
            logger.info("No URLs to process (all already completed)")
            return []
        
        async def purge_with_progress(url: str) -> Tuple[str, bool, str]:
            nonlocal completed
            
            try:
                success, message, _ = await self.purge_url(url, api_key)
                completed += 1
                
                if success:
                    self.completed_urls.append(url)
                else:
                    self.failed_urls.append((url, message))
                
                if progress_callback and completed % 50 == 0:
                    progress_callback(completed, total)
                
                return (url, success, message)
                
            except Exception as e:
                logger.error(f"Critical error purging {url}: {e}")
                completed += 1
                self.failed_urls.append((url, str(e)))
                return (url, False, f"❌ Critical error: {str(e)}")
        
        try:
            tasks = [purge_with_progress(url) for url in urls_to_process]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            final_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed with exception: {result}")
                    error_msg = f"❌ Exception: {str(result)}"
                    final_results.append(("", False, error_msg))
                    self.failed_urls.append(("", error_msg))
                else:
                    final_results.append(result)
            
            if progress_callback:
                progress_callback(completed, total)
            
            return final_results
            
        except Exception as e:
            logger.error(f"Critical error in batch processing: {e}")
            raise
    
    async def purge_accounts(
        self, 
        accounts: List[Dict[str, any]],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        resume_state: Optional[Dict] = None
    ) -> Dict[str, List[Tuple[str, bool, str]]]:
        """
        Purge URLs for multiple accounts with progress tracking and resume capability.
        
        Args:
            accounts: List of account dictionaries with 'account', 'api_key', and 'links'
            progress_callback: Optional callback for progress updates (account, completed, total)
            resume_state: Optional state to resume from
            
        Returns:
            Dictionary mapping account names to their purge results
        """
        all_results = {}
        completed_accounts = resume_state.get('completed_accounts', []) if resume_state else []
        
        for account_data in accounts:
            account_name = account_data['account']
            api_key = account_data['api_key']
            links = account_data['links']
            
            if account_name in completed_accounts:
                logger.info(f"Skipping already completed account: {account_name}")
                continue
            
            skip_urls = []
            if resume_state and resume_state.get('current_account') == account_name:
                skip_urls = resume_state.get('completed_urls', [])
                logger.info(f"Resuming {account_name}: {len(skip_urls)} URLs already completed")
            
            logger.info(f"Purging {len(links)} URLs for account: {account_name}")
            start_time = time.time()
            
            self.completed_urls = skip_urls.copy()
            self.failed_urls = []
            
            def account_progress(completed: int, total: int):
                if progress_callback:
                    progress_callback(account_name, completed, total)
                
                if self.state_manager and self.session_id:
                    try:
                        self.state_manager.save_state(
                            session_id=self.session_id,
                            accounts=accounts,
                            completed_accounts=completed_accounts,
                            current_account=account_name,
                            completed_urls=self.completed_urls,
                            failed_urls=self.failed_urls,
                            total_urls=sum(len(acc['links']) for acc in accounts)
                        )
                    except Exception as e:
                        logger.error(f"Failed to save checkpoint: {e}")
            
            try:
                results = await self.purge_urls_batch(links, api_key, account_progress, skip_urls)
                all_results[account_name] = results
                
                elapsed = time.time() - start_time
                success_count = sum(1 for _, success, _ in results if success)
                logger.info(
                    f"Completed {account_name}: {success_count}/{len(links)} successful in {elapsed:.1f}s "
                    f"({len(links)/elapsed:.1f} URLs/sec)" if elapsed > 0 else f"Completed {account_name}"
                )
                
                completed_accounts.append(account_name)
                
                if self.failed_urls:
                    logger.warning(f"{len(self.failed_urls)} URLs failed for {account_name}")
                    await self.retry_failed_urls(api_key, account_name)
                
            except Exception as e:
                logger.error(f"Error processing account {account_name}: {e}")
                all_results[account_name] = [("", False, f"❌ Account error: {str(e)}")]
                
                if self.state_manager and self.session_id:
                    self.state_manager.save_state(
                        session_id=self.session_id,
                        accounts=accounts,
                        completed_accounts=completed_accounts,
                        current_account=account_name,
                        completed_urls=self.completed_urls,
                        failed_urls=self.failed_urls,
                        total_urls=sum(len(acc['links']) for acc in accounts)
                    )
                raise
        
        return all_results
    
    async def retry_failed_urls(self, api_key: str, account_name: str, max_attempts: int = 2):
        """
        Retry failed URLs with exponential backoff.
        
        Args:
            api_key: The Bunny CDN API key
            account_name: Name of the account
            max_attempts: Maximum retry attempts
        """
        if not self.failed_urls:
            return
        
        logger.info(f"Retrying {len(self.failed_urls)} failed URLs for {account_name}")
        retry_list = self.failed_urls.copy()
        self.failed_urls = []
        
        for attempt in range(max_attempts):
            if not retry_list:
                break
            
            wait_time = 2 ** attempt
            logger.info(f"Retry attempt {attempt + 1}/{max_attempts}, waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
            
            for url, error in retry_list:
                if not url:
                    continue
                
                try:
                    success, message, _ = await self.purge_url(url, api_key)
                    
                    if success:
                        self.completed_urls.append(url)
                        logger.info(f"Retry successful: {url}")
                    else:
                        self.failed_urls.append((url, message))
                        
                except Exception as e:
                    logger.error(f"Retry failed for {url}: {e}")
                    self.failed_urls.append((url, str(e)))
            
            retry_list = self.failed_urls.copy()
            self.failed_urls = []
        
        self.failed_urls = retry_list
