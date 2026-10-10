#!/usr/bin/env python3
"""一键打包脚本 - 生成单文件 exe"""
import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).parent
    spec_file = project_root / 'build.spec'

    if not spec_file.exists():
        print(f'错误：找不到 {spec_file}')
        sys.exit(1)

    print('开始打包...')
    print(f'规格文件：{spec_file}')

    result = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', '--clean', str(spec_file)],
        cwd=project_root,
    )

    if result.returncode == 0:
        exe_path = project_root / 'dist' / '异形智裁.exe'
        print(f'\n打包成功！')
        print(f'输出文件：{exe_path}')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f'文件大小：{size_mb:.1f} MB')
    else:
        print('\n打包失败，请检查上方错误信息')
        sys.exit(1)


if __name__ == '__main__':
    main()
