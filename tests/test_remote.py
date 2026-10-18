from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from maxkompilator.remote import WorkerClient
from maxkompilator.worker import relative_path

ROOT = Path(__file__).resolve().parents[1]


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project źródło'
        self.project.mkdir()
        (self.project / 'main.py').write_text("from pathlib import Path\nimport zipfile\nwith zipfile.ZipFile(__file__.split('.pyz')[0]+'.pyz') as z: print(z.read('resource.txt').decode())\n", encoding='utf-8')
        (self.project / 'resource.txt').write_text('REMOTE_RESOURCE_OK', encoding='utf-8')
        self.command = [sys.executable, '-m', 'maxkompilator', 'worker', '--workspace', str(self.root)]

    def test_real_worker_capabilities_build_download_and_relocated_execution(self):
        logs = []
        with WorkerClient(self.command, cwd=ROOT) as client:
            capabilities = client.request('capabilities')
            self.assertEqual(capabilities['protocol'], 1)
            self.assertIn('dotnet', capabilities['adapters'])
            result = client.request('build', project=self.project.name, format='zipapp', smoke_test=True, on_log=logs.append)
            self.assertEqual(result['status'], 'built', result)
            self.assertEqual(result['smoke_status'], 'passed')
            downloads = client.download(result, self.root / 'download')
            binary = next(Path(item['local_path']) for item in downloads if item['id'].endswith('.pyz'))
            run = subprocess.run([sys.executable, str(binary)], cwd=self.root, capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('REMOTE_RESOURCE_OK', run.stdout)
            self.assertTrue(all(item['checksum_verified'] for item in downloads))
            with self.assertRaisesRegex(ValueError, 'Unknown successful-job artifact'):
                client.request('fetch', job_id=result['job_id'], artifact_id='../main.py')
        self.assertTrue(logs)

    def test_worker_rejects_traversal_unknown_fields_and_recovers(self):
        with WorkerClient(self.command, cwd=ROOT) as client:
            for project in ('../escape', '/absolute', 'C:/Windows', 'a\\b'):
                with self.subTest(project=project), self.assertRaises(ValueError):
                    client.request('build', project=project, format='zipapp')
            with self.assertRaisesRegex(ValueError, 'Unknown build fields'):
                client.request('build', project=self.project.name, command=['whoami'])
            self.assertEqual(client.request('capabilities')['protocol'], 1)

    def test_actual_running_smoke_can_be_cancelled_and_connection_reused(self):
        (self.project / 'main.py').write_text('import time\nprint("RUNNING_REMOTE", flush=True)\ntime.sleep(120)\n', encoding='utf-8')
        cancelled = threading.Event()
        def on_log(text):
            if 'RUNNING_REMOTE' in text:
                cancelled.set()
        with WorkerClient(self.command, cwd=ROOT) as client:
            result = client.request('build', project=self.project.name, format='zipapp', smoke_test=True, on_log=on_log, cancel_event=cancelled, wait_timeout=25)
            self.assertTrue(cancelled.is_set())
            self.assertEqual(result['status'], 'cancelled')
            self.assertEqual(result['artifacts'], [])
            self.assertEqual(client.request('capabilities')['protocol'], 1)

    def test_protocol_version_is_explicitly_rejected(self):
        run = subprocess.run(self.command, cwd=ROOT, input=json.dumps({'protocol': 999, 'id': 'a'*32, 'operation': 'capabilities'})+'\n', capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('Unsupported protocol', json.loads(run.stdout)['error'])

    def test_download_rejects_corrupt_content(self):
        with WorkerClient(self.command, cwd=ROOT) as client:
            result = client.request('build', project=self.project.name, format='zipapp')
            result['artifacts'][0]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                client.download(result, self.root / 'bad-download')
            self.assertFalse(list((self.root / 'bad-download').rglob('*.part')))

    def test_client_timeout_closes_worker(self):
        with WorkerClient([sys.executable, '-c', 'import time; time.sleep(120)']) as client:
            with self.assertRaises(TimeoutError):
                client.request('capabilities', wait_timeout=0.1)
            self.assertIsNotNone(client.process.poll())

    def test_ssh_rejects_options_and_path_traversal(self):
        with self.assertRaises(ValueError):
            WorkerClient.ssh('-oProxyCommand=evil', '/workspace')
        for value in ('../x', '/root', 'a//b', 'a/./b', 'C:x'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                relative_path(value)
