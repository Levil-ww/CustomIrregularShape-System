#!/usr/bin/env python3
"""Build a standalone Windows executable and a documented distribution ZIP."""
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from shape_crop import __version__


def create_distribution(project_root, exe_path):
    """Copy current documentation and record hashes for the distribution."""
    dist = exe_path.parent
    documents = {
        'docs/用户使用说明.md': '用户使用说明.md',
        f'docs/更新说明_{__version__}.md': f'更新说明_{__version__}.md',
        '异形智裁用户使用说明.pdf': '异形智裁用户使用说明.pdf',
    }
    files = [exe_path]
    for source, name in documents.items():
        target = dist / name
        shutil.copy2(project_root / source, target)
        files.append(target)
    verification = dist / '构建验证.txt'
    if verification.exists():
        files.append(verification)
    manifest = {
        'version': __version__,
        'built_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'platform': platform.platform(),
        'python': sys.version,
        'dependencies': {name: importlib.metadata.version(name)
                         for name in ('PyInstaller', 'PyQt5', 'numpy', 'Pillow')},
        'files': {path.name: {'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                  for path in files},
        'source_sha256': {
            path.relative_to(project_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted([project_root / 'main.py', project_root / 'build.spec',
                                *project_root.glob('shape_crop/**/*.py'),
                                project_root / 'shape_crop/services/windows_ocr.ps1'])
        },
    }
    manifest_path = dist / '发布清单.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    files.append(manifest_path)
    checksums = dist / 'SHA256SUMS.txt'
    checksums.write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
                                for path in files), encoding='utf-8')
    files.append(checksums)
    archive = dist / f'异形智裁-{__version__}-{datetime.now():%Y%m%d}-Windows-x64.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED) as package:
        for path in files:
            package.write(path, path.name)
    return archive


def main():
    project_root = Path(__file__).resolve().parent
    required = ['build.spec', 'shape_crop/services/windows_ocr.ps1',
                'outputs/icon/CustomIrregularShape-256.png',
                'outputs/icon/CustomIrregularShape.ico', 'docs/用户使用说明.md',
                f'docs/更新说明_{__version__}.md', '异形智裁用户使用说明.pdf']
    for relative in required:
        if not (project_root / relative).is_file():
            raise SystemExit(f'错误：缺少打包文件 {relative}')
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('错误：请在 Windows 64 位环境中打包')
    build_dir = project_root / 'build'
    build_dir.mkdir(exist_ok=True)
    dist = project_root / 'dist'
    dist.mkdir(exist_ok=True)
    print(f'开始打包 {__version__}，成功后替换旧程序…', flush=True)
    # Keep the previous executable intact if PyInstaller fails.
    with tempfile.TemporaryDirectory(prefix='release-', dir=build_dir) as staging:
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
                        '--distpath', staging, str(project_root / 'build.spec')],
                       cwd=project_root, check=True)
        exe_path = dist / '异形智裁.exe'
        (Path(staging) / exe_path.name).replace(exe_path)
    # A previous verification report must not describe a new build.
    (dist / '构建验证.txt').unlink(missing_ok=True)
    archive = create_distribution(project_root, exe_path)
    print(f'打包成功：{exe_path}（{exe_path.stat().st_size / 1024 / 1024:.1f} MB）')
    print(f'分发压缩包：{archive}')


if __name__ == '__main__':
    main()
