"""Run a built executable's isolated smoke test and check its result."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    executable = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='xlauncher-bundle-check-') as directory:
        report = Path(directory) / 'result.json'
        result = subprocess.run([str(executable), '--smoke-test', '--smoke-report', str(report)],
                                timeout=60, check=False)
        data = json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
        if result.returncode or not data.get('ok'):
            raise RuntimeError(f'Packaged smoke test failed ({result.returncode}): {data}')
        print(f'XLauncher {data["version"]}: packaged GUI smoke test passed.')


if __name__ == '__main__':
    main()
