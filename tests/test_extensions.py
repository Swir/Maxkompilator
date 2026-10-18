from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import platform
import sys
import tempfile
import unittest
from unittest.mock import patch

from maxkompilator.adapters import create_plan, register_adapter, unregister_adapter
from maxkompilator.adapters.python_adapter import native_target
from maxkompilator.detection import detect_project
from maxkompilator.engine import execute_build
from maxkompilator.environment import probe_tool
from maxkompilator.models import BuildPlan, BuildStep, PlanError, Project, ToolRequirement


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'main.py').write_text("print('OK')", encoding='utf-8')
        self.addCleanup(unregister_adapter, 'copy-text')

    def test_pinned_python_version_is_checked_and_mismatch_prevents_build(self):
        config = self.root / 'maxkompilator.toml'
        config.write_text(f'[tools]\npython="{platform.python_version()}"\n', encoding='utf-8')
        plan = create_plan(detect_project(self.root), format='zipapp')
        self.assertTrue(probe_tool(plan.requirements[0])['available'])
        config.write_text('[tools]\npython="0.0.1"\n', encoding='utf-8')
        report = execute_build(create_plan(detect_project(self.root), format='zipapp'))
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['artifacts'], [])
        self.assertFalse(report['environment']['checks'][0]['available'])

    def test_version_probe_does_not_accept_a_prefix(self):
        requirement = ToolRequirement('example', (sys.executable, '-c', "print('Tool 6.22.30')"), '', '6.22.3')
        self.assertFalse(probe_tool(requirement)['available'])

    def test_wrong_tool_pin_is_rejected_while_planning(self):
        (self.root / 'maxkompilator.toml').write_text('[tools]\ndotnet="8.0.1"\n', encoding='utf-8')
        with self.assertRaisesRegex(PlanError, 'Unsupported tool pins'):
            create_plan(detect_project(self.root), format='zipapp')

    @staticmethod
    def factory(project, target, format, output, python):
        command = (python or sys.executable, '-c',
                   'import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.mkdir(parents=True,exist_ok=True); (p/"copy.txt").write_bytes(pathlib.Path("main.py").read_bytes())', str(output))
        return BuildPlan(project, 'any', 'text', output,
                         steps=(BuildStep('Copy text resource', command, project.root),), artifact_patterns=('copy.txt',))

    def test_registered_adapter_builds_a_real_artifact_with_report(self):
        register_adapter('copy-text', self.factory)
        project = Project(self.root, 'copy-text', 'demo')
        plan = create_plan(project)
        self.assertFalse(plan.output_dir.exists())
        report = execute_build(plan)
        self.assertEqual(report['status'], 'built', report['error'])
        self.assertEqual(Path(report['artifacts'][0]['path']).read_bytes(), (self.root / 'main.py').read_bytes())
        self.assertEqual(len(report['artifacts'][0]['sha256']), 64)

    def test_adapter_cannot_shadow_builtins_or_change_output_contract(self):
        with self.assertRaisesRegex(PlanError, 'already registered'):
            register_adapter('python', self.factory)
        with self.assertRaisesRegex(PlanError, 'API version'):
            register_adapter('copy-text', self.factory, api_version=2)
        def invalid(*args):
            return replace(self.factory(*args), output_dir=self.root)
        register_adapter('copy-text', invalid)
        with self.assertRaisesRegex(PlanError, 'contract'):
            create_plan(Project(self.root, 'copy-text', 'demo'))

    def test_python_additional_architectures_require_matching_workers(self):
        cases = [('Windows', 'AMD64', 8, 'win-x64'), ('Windows', 'AMD64', 4, 'win-x86'),
                 ('Windows', 'ARM64', 8, 'win-arm64'), ('Linux', 'aarch64', 8, 'linux-arm64'),
                 ('Linux', 'armv7l', 4, 'linux-arm'), ('Darwin', 'x86_64', 8, 'macos-x64'),
                 ('Darwin', 'arm64', 8, 'macos-arm64')]
        project = detect_project(self.root)
        for system, machine, width, target in cases:
            with self.subTest(target=target), patch('maxkompilator.adapters.python_adapter.platform.system', return_value=system), patch('maxkompilator.adapters.python_adapter.platform.machine', return_value=machine), patch('maxkompilator.adapters.python_adapter.struct.calcsize', return_value=width):
                self.assertEqual(native_target(), target)
                self.assertEqual(create_plan(project, target=target).target, target)
                foreign = 'win-x64' if not target.startswith('win-') else 'linux-x64'
                with self.assertRaisesRegex(PlanError, 'cannot cross-build'):
                    create_plan(project, target=foreign)

    def test_dotnet_additional_architecture_rids(self):
        (self.root / 'demo.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>', encoding='utf-8')
        project = detect_project(self.root, kind='dotnet')
        for target, rid in [('win-x86', 'win-x86'), ('win-arm64', 'win-arm64'), ('linux-arm', 'linux-arm'), ('linux-arm64', 'linux-arm64'), ('macos-x64', 'osx-x64'), ('macos-arm64', 'osx-arm64')]:
            with self.subTest(target=target):
                plan = create_plan(project, target=target)
                self.assertEqual(plan.target, rid)
                self.assertIn(rid, plan.steps[0].command)
        with self.assertRaisesRegex(PlanError, 'Unsupported .NET runtime'):
            create_plan(project, target='linux-x86')
