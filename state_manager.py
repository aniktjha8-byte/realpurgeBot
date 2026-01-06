import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class PurgeStateManager:
    """Manage purge state for resume functionality."""
    
    STATE_DIR = "purge_states"
    
    def __init__(self):
        self.ensure_state_dir()
    
    def ensure_state_dir(self):
        """Create state directory if it doesn't exist."""
        if not os.path.exists(self.STATE_DIR):
            os.makedirs(self.STATE_DIR)
    
    def generate_session_id(self, user_id: int) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{user_id}_{timestamp}"
    
    def save_state(
        self, 
        session_id: str, 
        accounts: List[Dict], 
        completed_accounts: List[str],
        current_account: str,
        completed_urls: List[str],
        failed_urls: List[Tuple[str, str]],
        total_urls: int
    ):
        """
        Save current purge state to disk.
        
        Args:
            session_id: Unique session identifier
            accounts: All accounts to purge
            completed_accounts: List of completed account names
            current_account: Current account being processed
            completed_urls: URLs successfully purged in current account
            failed_urls: List of (url, error_message) tuples
            total_urls: Total number of URLs across all accounts
        """
        state = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "accounts": accounts,
            "completed_accounts": completed_accounts,
            "current_account": current_account,
            "completed_urls": completed_urls,
            "failed_urls": failed_urls,
            "total_urls": total_urls
        }
        
        state_file = os.path.join(self.STATE_DIR, f"{session_id}.json")
        
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"State saved to {state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def load_state(self, session_id: str) -> Optional[Dict]:
        """
        Load purge state from disk.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            State dictionary or None if not found
        """
        state_file = os.path.join(self.STATE_DIR, f"{session_id}.json")
        
        if not os.path.exists(state_file):
            logger.warning(f"State file not found: {state_file}")
            return None
        
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            logger.info(f"State loaded from {state_file}")
            return state
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return None
    
    def list_sessions(self, user_id: int) -> List[Dict]:
        """
        List all saved sessions for a user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of session info dictionaries
        """
        sessions = []
        
        try:
            for filename in os.listdir(self.STATE_DIR):
                if filename.startswith(str(user_id)) and filename.endswith('.json'):
                    session_id = filename[:-5]
                    state_file = os.path.join(self.STATE_DIR, filename)
                    
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                    
                    sessions.append({
                        'session_id': session_id,
                        'timestamp': state.get('timestamp'),
                        'total_urls': state.get('total_urls'),
                        'completed_urls_count': len(state.get('completed_urls', [])),
                        'failed_urls_count': len(state.get('failed_urls', []))
                    })
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
        
        return sorted(sessions, key=lambda x: x['timestamp'], reverse=True)
    
    def delete_state(self, session_id: str):
        """Delete a saved state file."""
        state_file = os.path.join(self.STATE_DIR, f"{session_id}.json")
        
        try:
            if os.path.exists(state_file):
                os.remove(state_file)
                logger.info(f"State file deleted: {state_file}")
        except Exception as e:
            logger.error(f"Failed to delete state: {e}")
    
    def get_resume_info(self, session_id: str) -> Optional[Dict]:
        """
        Get resume information for a session.
        
        Returns:
            Dictionary with resume information or None
        """
        state = self.load_state(session_id)
        
        if not state:
            return None
        
        completed_count = len(state.get('completed_urls', []))
        failed_count = len(state.get('failed_urls', []))
        total = state.get('total_urls', 0)
        remaining = total - completed_count - failed_count
        
        return {
            'session_id': session_id,
            'timestamp': state.get('timestamp'),
            'total_urls': total,
            'completed': completed_count,
            'failed': failed_count,
            'remaining': remaining,
            'progress_percent': int((completed_count / total * 100)) if total > 0 else 0,
            'current_account': state.get('current_account'),
            'completed_accounts': state.get('completed_accounts', [])
        }
