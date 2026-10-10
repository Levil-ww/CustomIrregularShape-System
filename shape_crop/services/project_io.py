"""Versioned JSON projects. Paths are relative to the project file when saved."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from shape_crop.models.design import BorderSpec, CropBox, DesignSpec, MaterialSpec


def save_project(path, design):
    design.validate()
    path = Path(path)
    payload = asdict(design)
    for key in ('material', 'inner_material'):
        if payload[key] and payload[key]['path']:
            try:
                payload[key]['path'] = os.path.relpath(payload[key]['path'], path.parent)
            except ValueError:  # Different Windows drives.
                pass
    handle, temporary = tempfile.mkstemp(prefix='.project-', suffix='.json', dir=path.parent)
    os.close(handle)
    try:
        with open(temporary, 'w', encoding='utf-8') as f:
            json.dump({'schema_version': 1, 'design': payload}, f, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_project(path):
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise ValueError(f'项目文件不存在：{path}')
    except PermissionError:
        raise ValueError(f'项目文件无权限：{path}')
    except json.JSONDecodeError:
        raise ValueError(f'项目文件格式损坏：{path}')
    if raw.get('schema_version') != 1:
        raise ValueError('不支持的项目文件版本')
    if 'design' not in raw:
        raise ValueError('项目文件缺少设计数据')
    data = raw['design']
    for key in ('material', 'inner_material'):
        if data.get(key) is not None:
            item = data[key]
            for region in ('content_box', 'strip_box'):
                if region in item:
                    item[region] = CropBox(**item[region])
            if item.get('path'):
                item['path'] = str((path.parent / item['path']).resolve())
            data[key] = MaterialSpec(**item)
    if 'border' in data:
        data['border']['color'] = tuple(data['border'].get('color', (155, 138, 107)))
        data['border'] = BorderSpec(**data['border'])
    if 'background' in data:
        data['background'] = tuple(data['background'])
    design = DesignSpec(**data)
    design.validate()
    return design
