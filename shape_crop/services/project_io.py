"""Versioned JSON projects. Paths are relative to the project file when saved."""
from dataclasses import asdict
import json
import os
from pathlib import Path
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
    path.write_text(json.dumps({'schema_version': 1, 'design': payload}, ensure_ascii=False, indent=2), encoding='utf-8')


def load_project(path):
    path = Path(path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw.get('schema_version') != 1:
        raise ValueError('不支持的项目文件版本')
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
