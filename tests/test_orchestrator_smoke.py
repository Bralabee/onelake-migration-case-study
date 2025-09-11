import json, subprocess, sys, tempfile, os, pathlib

def test_orchestrator_smoke_skip_phases():
    """Smoke test: run orchestrator skipping both phases to validate JSON report structure."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td:
        report_path = pathlib.Path(td) / 'report.json'
        cmd = [sys.executable, '-m', 'onelake_migration.orchestration.orchestrator', '--skip-download', '--skip-upload', '--report-json', str(report_path)]
        proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
        assert proc.returncode == 0, f"orchestrator exited {proc.returncode}: stdout={proc.stdout}\nstderr={proc.stderr}"
        assert report_path.exists(), 'report json not created'
        data = json.loads(report_path.read_text())
        # Basic shape assertions
        assert 'start_time' in data and 'end_time' in data
        assert 'download' in data or 'upload' in data  # phases skipped may be None
        assert 'summary' in data
        # When skipping upload there may be no migration_stats; that's fine
        # Validate ISO-like timestamps
        assert data['start_time'].endswith('Z') and data['end_time'].endswith('Z')

if __name__ == '__main__':
    # Allow running standalone for quick dev check
    test_orchestrator_smoke_skip_phases()
    print('smoke ok')
