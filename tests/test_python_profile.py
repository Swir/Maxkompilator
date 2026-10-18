from pathlib import Path
import ast
import subprocess
import sys
import tempfile
import unittest

from maxkompilator.models import PlanError, Project
from maxkompilator.python_profile import resolve_python_profile


class PythonProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'app'
        self.root.mkdir()
        self.project = Project(self.root, 'python', 'source_name', 'main.py')
        self.output = Path(self.temp.name).resolve() / 'results'

    def config(self, text):
        (self.root / 'maxkompilator.toml').write_text(text, encoding='utf-8')

    def test_unconfigured_project_preserves_adapter_defaults(self):
        plan = resolve_python_profile(self.project, 'executable', 'win-x64', self.output, sys.executable)
        self.assertEqual(plan.project, self.project)
        self.assertEqual(plan.pyinstaller_arguments, ())
        self.assertEqual(plan.steps, ())
        self.assertFalse(self.output.exists())

    def test_windows_name_icon_and_version_generate_real_version_metadata(self):
        icon = self.root / 'brand.ico'
        icon.write_bytes(b'fake-icon-for-planning-only')
        self.config('[app]\nname = "BrightDemo"\nversion = "1.2.3-beta.1"\nicon = "brand.ico"\n')
        plan = resolve_python_profile(self.project, 'executable', 'win-x64', self.output, sys.executable)
        self.assertEqual(plan.project.name, 'BrightDemo')
        self.assertEqual(plan.pyinstaller_arguments[0:2], ('--icon', str(icon)))
        self.assertEqual(plan.pyinstaller_arguments[2], '--version-file')
        self.assertEqual(len(plan.steps), 1)
        self.assertFalse(self.output.exists(), 'Planning unexpectedly wrote generated files')
        result = subprocess.run(plan.steps[0].command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = Path(plan.pyinstaller_arguments[-1])
        self.assertEqual(metadata.parent.name, '.metadata')
        self.assertTrue(metadata.is_file())
        resource = metadata.read_text(encoding='utf-8')
        ast.parse(resource)
        self.assertIn('filevers=(1, 2, 3, 0)', resource)
        self.assertIn("'BrightDemo.exe'", resource)
        self.assertIn("'1.2.3-beta.1'", resource)

    def test_non_windows_version_fails_instead_of_misreporting_embedding(self):
        self.config('[app]\nversion = "1.2.3"\n')
        with self.assertRaisesRegex(PlanError, 'Windows target'):
            resolve_python_profile(self.project, 'executable', 'linux-x64', self.output, sys.executable)

    def test_mac_icon_uses_icns_and_rejects_ico(self):
        (self.root / 'badge.icns').write_bytes(b'icns-planning-fixture')
        self.config('[app]\nicon="badge.icns"\n')
        plan = resolve_python_profile(self.project, 'executable', 'macos-arm64', self.output, sys.executable)
        self.assertEqual(plan.pyinstaller_arguments[0], '--icon')
        self.config('[app]\nicon="badge.ico"\n')
        (self.root / 'badge.ico').write_bytes(b'fake')
        with self.assertRaisesRegex(PlanError, 'must use .icns'):
            resolve_python_profile(self.project, 'executable', 'macos-arm64', self.output, sys.executable)

    def test_zipapp_name_supported_but_embedded_metadata_rejected(self):
        self.config('[app]\nname="PortableDemo"\n')
        plan = resolve_python_profile(self.project, 'zipapp', None, self.output, sys.executable)
        self.assertEqual(plan.project.name, 'PortableDemo')
        self.assertEqual(plan.steps, ())
        self.config('[app]\nname="PortableDemo"\nversion="1.2.3"\n')
        with self.assertRaisesRegex(PlanError, 'zipapp cannot embed'):
            resolve_python_profile(self.project, 'zipapp', None, self.output, sys.executable)

    def test_rejects_icon_symlink_escape_before_compiling(self):
        out = Path(self.temp.name) / 'outside.ico'
        out.write_bytes(b'outside')
        (self.root / 'badge.ico').symlink_to(out)
        self.config('[app]\nicon="badge.ico"\n')
        with self.assertRaisesRegex(PlanError, 'symlinks'):
            resolve_python_profile(self.project, 'executable', 'win-x64', self.output, sys.executable)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
