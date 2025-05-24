"""Text export utilities for evaluation."""
from pathlib import Path
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)

class ExportUtility:
    """Utility for exporting sessions in various formats."""
    
    @staticmethod
    def jsonl_to_text(jsonl_path: Path) -> str:
        """Convert JSONL session file to readable text format.
        
        Args:
            jsonl_path: Path to JSONL file
            
        Returns:
            Formatted text transcript
        """
        lines = []
        session_info = {}
        messages = []
        
        try:
            with open(jsonl_path, 'r') as f:
                for line in f:
                    entry = json.loads(line.strip())
                    
                    if entry["type"] == "session_start":
                        session_info = {
                            "session_id": entry["session_id"],
                            "participant": entry["participant"],
                            "scenario": entry["scenario"],
                            "character": entry["character"],
                            "operator": entry["operator"],
                            "started": entry["timestamp"]
                        }
                    
                    elif entry["type"] == "message":
                        messages.append({
                            "role": entry["role"],
                            "content": entry["content"],
                            "timestamp": entry["timestamp"],
                            "number": entry["message_number"]
                        })
                    
                    elif entry["type"] == "session_end":
                        session_info["ended"] = entry["timestamp"]
                        session_info["total_messages"] = entry["total_messages"]
                        session_info["duration"] = entry["duration_seconds"]
            
            # Format the transcript
            lines.append("=" * 70)
            lines.append("ROLEPLAY SESSION TRANSCRIPT")
            lines.append("=" * 70)
            lines.append("")
            
            # Session metadata
            lines.append("SESSION INFORMATION:")
            lines.append(f"  Session ID: {session_info.get('session_id', 'Unknown')}")
            lines.append(f"  Participant: {session_info.get('participant', 'Unknown')}")
            lines.append(f"  Scenario: {session_info.get('scenario', 'Unknown')}")
            lines.append(f"  Character: {session_info.get('character', 'Unknown')}")
            lines.append(f"  Operator: {session_info.get('operator', 'Unknown')}")
            lines.append(f"  Started: {session_info.get('started', 'Unknown')}")
            
            if 'ended' in session_info:
                lines.append(f"  Ended: {session_info['ended']}")
                lines.append(f"  Duration: {session_info['duration']} seconds")
                lines.append(f"  Total Messages: {session_info['total_messages']}")
            
            lines.append("")
            lines.append("=" * 70)
            lines.append("CONVERSATION:")
            lines.append("=" * 70)
            lines.append("")
            
            # Messages
            for msg in messages:
                speaker = "Participant" if msg["role"] == "participant" else "Character"
                lines.append(f"[{msg['number']}] {speaker}:")
                lines.append(msg["content"])
                lines.append(f"(Timestamp: {msg['timestamp']})")
                lines.append("")
            
            if not messages:
                lines.append("[No messages in session]")
            
            lines.append("=" * 70)
            lines.append("END OF TRANSCRIPT")
            lines.append("=" * 70)
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to convert JSONL to text: {e}")
            return f"Error processing session file: {str(e)}"
    
    @staticmethod
    def get_session_summary(jsonl_path: Path) -> Dict[str, Any]:
        """Get summary information from a JSONL session file.
        
        Args:
            jsonl_path: Path to JSONL file
            
        Returns:
            Summary dictionary
        """
        summary = {
            "session_id": None,
            "participant": None,
            "scenario": None,
            "character": None,
            "message_count": 0,
            "started": None,
            "ended": None,
            "duration": None
        }
        
        try:
            with open(jsonl_path, 'r') as f:
                for line in f:
                    entry = json.loads(line.strip())
                    
                    if entry["type"] == "session_start":
                        summary.update({
                            "session_id": entry["session_id"],
                            "participant": entry["participant"],
                            "scenario": entry["scenario"],
                            "character": entry["character"],
                            "started": entry["timestamp"]
                        })
                    
                    elif entry["type"] == "message":
                        summary["message_count"] += 1
                    
                    elif entry["type"] == "session_end":
                        summary.update({
                            "ended": entry["timestamp"],
                            "duration": entry["duration_seconds"]
                        })
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get session summary: {e}")
            return summary