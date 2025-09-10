# Compatibility shim recreated after cleanup.
# Provides SimpleProgressMonitor expected by legacy tests.
from pathlib import Path
import json

class SimpleProgressMonitor:
    """Minimal compatibility stub for legacy dashboard tests.
    Exposes attributes and methods referenced in tests with safe defaults.
    """
    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path or '.')
        # Expected file attributes
        self.progress_file = self.base_path / 'download_progress_turbo.json'
        self.cache_file = self.base_path / 'file_list_cache.json'

    def load_data(self):
        data = {}
        if self.cache_file.exists():
            try:
                data['cache'] = json.loads(self.cache_file.read_text() or '{}')
            except json.JSONDecodeError:
                data['cache'] = {}
        if self.progress_file.exists():
            try:
                data['progress'] = json.loads(self.progress_file.read_text() or '{}')
            except json.JSONDecodeError:
                data['progress'] = {}
        return data

    def generate_file_insights(self, success_files, failed_files):
        return {
            'file_types': {},
            'top_folders': [],
            'success_count': len(success_files),
            'failed_count': len(failed_files),
        }

    def generate_insights_html(self, data):
        return "<html><body><h1>Insights</h1></body></html>"

    def record(self, message: str):
        pass

    def summary(self):
        return {"event_count": 0}
