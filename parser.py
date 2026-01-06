import re
import logging
from typing import List, Dict, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class PurgeFileParser:
    """Parser for purge configuration files with robust error handling."""
    
    SUPPORTED_PROTOCOLS = ('http', 'https')
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_URLS_PER_ACCOUNT = 10000
    
    @staticmethod
    def validate_url(url: str) -> Tuple[bool, str]:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            Tuple of (is_valid, cleaned_url or error_message)
        """
        try:
            url = url.strip()
            
            if not url:
                return False, "Empty URL"
            
            parsed = urlparse(url)
            
            if parsed.scheme not in PurgeFileParser.SUPPORTED_PROTOCOLS:
                return False, f"Invalid protocol: {parsed.scheme}"
            
            if not parsed.netloc:
                return False, "Missing domain"
            
            if len(url) > 2048:
                return False, "URL too long (max 2048 chars)"
            
            return True, url
            
        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"
    
    @staticmethod
    def validate_api_key(api_key: str) -> Tuple[bool, str]:
        """
        Validate API key format.
        
        Args:
            api_key: API key to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        api_key = api_key.strip()
        
        if not api_key:
            return False, "API key is empty"
        
        if len(api_key) < 10:
            return False, "API key too short (min 10 chars)"
        
        if len(api_key) > 256:
            return False, "API key too long (max 256 chars)"
        
        return True, ""
    
    @staticmethod
    def normalize_content(content: str) -> str:
        """
        Normalize file content by handling different encodings and line endings.
        
        Args:
            content: Raw file content
            
        Returns:
            Normalized content string
        """
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        content = ''.join(char for char in content if char.isprintable() or char == '\n')
        
        return content.strip()
    
    def parse_file(self, content: str) -> List[Dict[str, any]]:
        """
        Parse the purge file content with validation and error handling.
        
        Expected format:
        acc1
        api : <api_key>
        <link1>
        <link2>
        
        acc2
        api : <api_key>
        <link1>
        <link2>
        
        Returns:
            List of dictionaries with account name, api key, and links
            
        Raises:
            ValueError: If file format is invalid
        """
        if not content:
            raise ValueError("File content is empty")
        
        if len(content) > self.MAX_FILE_SIZE:
            raise ValueError(f"File too large (max {self.MAX_FILE_SIZE // 1024 // 1024}MB)")
        
        content = self.normalize_content(content)
        lines = content.split('\n')
        
        accounts = []
        current_account = None
        current_api = None
        current_links = []
        line_number = 0
        errors = []
        warnings = []
        
        for line in lines:
            line_number += 1
            original_line = line
            line = line.strip()
            
            if not line or line.startswith('#'):
                if current_account and current_api and current_links:
                    accounts.append({
                        'account': current_account,
                        'api_key': current_api,
                        'links': current_links
                    })
                    current_account = None
                    current_api = None
                    current_links = []
                continue
            
            if line.lower().startswith('api'):
                api_match = re.match(r'api\s*[:=]\s*(.+)', line, re.IGNORECASE)
                if api_match:
                    api_key = api_match.group(1).strip()
                    
                    is_valid, error_msg = self.validate_api_key(api_key)
                    if not is_valid:
                        errors.append(f"Line {line_number}: {error_msg}")
                        logger.warning(f"Invalid API key at line {line_number}: {error_msg}")
                        continue
                    
                    if current_account is None:
                        errors.append(f"Line {line_number}: API key found without account name")
                        continue
                    
                    current_api = api_key
                else:
                    warnings.append(f"Line {line_number}: Malformed API key line")
                    
            elif line.startswith('http://') or line.startswith('https://'):
                if current_api is None:
                    warnings.append(f"Line {line_number}: URL found before API key, skipping")
                    continue
                
                is_valid, result = self.validate_url(line)
                if is_valid:
                    if len(current_links) >= self.MAX_URLS_PER_ACCOUNT:
                        errors.append(f"Line {line_number}: Too many URLs for account {current_account}")
                        break
                    current_links.append(result)
                else:
                    warnings.append(f"Line {line_number}: Invalid URL - {result}")
                    logger.warning(f"Skipping invalid URL at line {line_number}: {result}")
                    
            else:
                if current_account and current_api and current_links:
                    accounts.append({
                        'account': current_account,
                        'api_key': current_api,
                        'links': current_links
                    })
                    current_links = []
                    current_api = None
                
                if line:
                    current_account = line[:100]
        
        if current_account and current_api and current_links:
            accounts.append({
                'account': current_account,
                'api_key': current_api,
                'links': current_links
            })
        
        if not accounts:
            error_summary = "\n".join(errors[:5]) if errors else "Unknown error"
            raise ValueError(
                f"No valid accounts found in file.\n"
                f"Errors encountered:\n{error_summary}"
            )
        
        if warnings:
            logger.warning(f"Parsed with {len(warnings)} warnings")
            for warning in warnings[:10]:
                logger.warning(warning)
        
        total_urls = sum(len(acc['links']) for acc in accounts)
        logger.info(
            f"Successfully parsed {len(accounts)} account(s) "
            f"with {total_urls} total URLs"
        )
        
        return accounts
    
    @staticmethod
    def get_parse_summary(accounts: List[Dict[str, any]]) -> str:
        """
        Get a human-readable summary of parsed accounts.
        
        Args:
            accounts: List of parsed account dictionaries
            
        Returns:
            Summary string
        """
        if not accounts:
            return "No accounts found"
        
        summary_lines = []
        for acc in accounts:
            account_name = acc['account']
            url_count = len(acc['links'])
            api_preview = acc['api_key'][:8] + '...' if len(acc['api_key']) > 8 else acc['api_key']
            summary_lines.append(f"  • {account_name}: {url_count} URLs (API: {api_preview})")
        
        total_urls = sum(len(acc['links']) for acc in accounts)
        
        return (
            f"📊 Parsed {len(accounts)} account(s) with {total_urls} total URLs:\n" +
            "\n".join(summary_lines)
        )
