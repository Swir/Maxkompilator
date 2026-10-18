"""Inspect actual PE resources and compare two builds of the pinned fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(report_path: Path, *, desktop: bool = False) -> dict:
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report['status'] != 'built' or report['smoke_test']['status'] != 'passed':
        raise ValueError('Build and runtime must pass before qualification')
    name = 'SwirDesktopDemo' if desktop else 'SwirProfileDemo'
    candidates = [Path(a['path']) for a in report['artifacts'] if Path(a['path']).name == name + '.exe']
    if len(candidates) != 1:
        raise ValueError('Expected a single profiled executable')
    binary = candidates[0]
    for artifact in report['artifacts']:
        if sha(Path(artifact['path'])) != artifact['sha256']:
            raise ValueError('Artifact changed after build')
    icon = Path(report['project']['root']) / 'branding' / 'app.ico'
    raw = icon.read_bytes()
    reserved, kind, count = struct.unpack_from('<HHH', raw)
    if (reserved, kind) != (0, 1) or count < 1:
        raise ValueError('Invalid source icon')
    expected_icons = []
    for index in range(count):
        size, offset = struct.unpack_from('<II', raw, 6 + 16 * index + 8)
        expected_icons.append(hashlib.sha256(raw[offset:offset+size]).hexdigest())
    with pefile.PE(str(binary)) as pe:
        if pe.FILE_HEADER.Machine != 0x8664:
            raise ValueError('Expected Windows x64 PE')
        actual_icons = []
        groups = 0
        for category in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if category.id == 14:
                groups += len(category.directory.entries)
            if category.id == 3:
                for image in category.directory.entries:
                    for language in image.directory.entries:
                        data = language.data.struct
                        actual_icons.append(hashlib.sha256(pe.get_data(data.OffsetToData, data.Size)).hexdigest())
        if sorted(expected_icons) != sorted(actual_icons) or not groups:
            raise ValueError('The embedded executable icon does not match the selected profile')
        version = pe.VS_FIXEDFILEINFO[0]
        actual_version = [version.FileVersionMS >> 16, version.FileVersionMS & 65535,
                          version.FileVersionLS >> 16, version.FileVersionLS & 65535]
        if actual_version != [1, 0, 0, 0]:
            raise ValueError(f'Unexpected file version: {actual_version}')
    tree = {str(Path(a['path']).relative_to(binary.parent).as_posix()): a['sha256'] for a in report['artifacts']}
    required = ['System.Windows.Forms.dll', 'Microsoft.Win32.SystemEvents.dll', 'coreclr.dll', 'hostfxr.dll', 'Assets/greeting.txt'] if desktop else ['_internal/assets/message.json']
    if any(item not in tree for item in required):
        raise ValueError('Published runtime dependencies or data missing')
    return {'status': 'passed', 'binary': str(binary), 'sha256': sha(binary), 'machine': 'win-x64',
            'name': name, 'version': actual_version, 'icon_images': count, 'source_icon_sha256': sha(icon),
            'all_icon_payloads_match': True, 'resource_and_runtime_passed': True,
            'required_files': required, 'files': tree, 'build_run_id': report['run_id']}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('first', type=Path)
    parser.add_argument('--second', type=Path)
    parser.add_argument('--desktop', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = qualify(args.first, desktop=args.desktop)
    if args.second:
        second = qualify(args.second, desktop=args.desktop)
        if result['files'] != second['files']:
            changed = sorted(name for name in set(result['files']) | set(second['files']) if result['files'].get(name) != second['files'].get(name))
            raise ValueError(f'Repeat build payload differs: {changed}')
        result['repeat_build'] = {'status': 'passed', 'run_id': second['build_run_id'], 'all_payload_hashes_identical': True, 'file_count': len(second['files'])}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
