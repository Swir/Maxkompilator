from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from maxkompilator.adapters.dotnet_adapter import create_dotnet_plan
from maxkompilator.models import PlanError, Project


class DotnetProfileIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'App.csproj').write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
            '<TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>', encoding='utf-8')
        self.project=Project(self.root, 'dotnet', 'App', project_file='App.csproj')
        self.output=self.root/'dist'/'maxkompilator'

    def write_profile(self, settings):
        (self.root/'maxkompilator.toml').write_text(settings, encoding='utf-8')

    def plan(self, target='linux-x64'):
        return create_dotnet_plan(self.project,target,None,self.output)

    def test_default_does_not_override_csproj_metadata(self):
        command=self.plan().steps[0].command
        self.assertFalse(any(arg.startswith('-p:') for arg in command))
        self.assertEqual(command[0:3],('dotnet','publish',str(self.root/'App.csproj')))
        self.assertEqual(command[command.index('--self-contained')+1], 'true')

    def test_name_and_version_override_are_actual_msbuild_properties(self):
        self.write_profile('[app]\nname="CustomApp"\nversion="2.3.4-beta.1"\n')
        plan=self.plan()
        self.assertEqual(plan.project.name,'CustomApp')
        self.assertIn('-p:AssemblyName=CustomApp', plan.steps[0].command)
        self.assertIn('-p:Version=2.3.4-beta.1',plan.steps[0].command)
        self.assertFalse(self.output.exists(), 'Planning cannot write output')

    def test_windows_ico_reaches_real_dotnet_publish_command(self):
        icon=self.root/'bright.ico'
        icon.write_bytes(b'fake icon: path only, not a real SDK publish')
        self.write_profile('[app]\nicon="bright.ico"\n')
        plan=self.plan('win-x64')
        self.assertIn(f'-p:ApplicationIcon={icon}',plan.steps[0].command)
        self.assertEqual(plan.target,'win-x64')

    def test_png_and_linux_are_not_claimed_embedded(self):
        (self.root/'logo.png').write_bytes(b'fixture')
        self.write_profile('[app]\nicon="logo.png"\n')
        for target in ('win-x64','linux-x64'):
            with self.subTest(target=target),self.assertRaises(PlanError):
                self.plan(target)

    def test_macos_icon_is_not_falsely_claimed_in_managed_publish(self):
        (self.root/'mac.icns').write_bytes(b'fixture')
        self.write_profile('[app]\nicon="mac.icns"\n')
        with self.assertRaisesRegex(PlanError, 'only for Windows'):
            self.plan('macos-arm64')

    def test_cannot_inject_properties_via_version_or_name(self):
        for value in ('-p:Unsafe=true','name;Injected=yes','x y'):
            self.write_profile('[app]\nname="'+value+'"\n')
            with self.subTest(value=value),self.assertRaises(PlanError):
                self.plan()

    def test_explicit_default_name_overrides_csproj_custom_name(self):
        self.write_profile('[app]\nname="App"\n')
        self.assertIn('-p:AssemblyName=App',self.plan().steps[0].command)

if __name__=='__main__':unittest.main()
