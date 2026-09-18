"""Shared NSL-KDD feature schema and preprocessing."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

FEATURE_NAMES = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes', 'land',
    'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in', 'num_compromised',
    'root_shell', 'su_attempted', 'num_root', 'num_file_creations', 'num_shells',
    'num_access_files', 'num_outbound_cmds', 'is_host_login', 'is_guest_login', 'count',
    'srv_count', 'serror_rate', 'srv_serror_rate', 'rerror_rate', 'srv_rerror_rate',
    'same_srv_rate', 'diff_srv_rate', 'srv_diff_host_rate', 'dst_host_count',
    'dst_host_srv_count', 'dst_host_same_srv_rate', 'dst_host_diff_srv_rate',
    'dst_host_same_src_port_rate', 'dst_host_srv_diff_host_rate', 'dst_host_serror_rate',
    'dst_host_srv_serror_rate', 'dst_host_rerror_rate', 'dst_host_srv_rerror_rate',
]
CATEGORICAL_FIELDS = {'protocol_type': 1, 'service': 2, 'flag': 3}


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(lambda column: column.map(lambda value: value.strip() if isinstance(value, str) else value))


def encode_frame(frame: pd.DataFrame, categories: dict[str, list[Any]] | None = None):
    encoded = (frame.iloc[:, :41].copy() if frame.shape[1] > 41 else frame.copy()).astype(object)
    category_map = categories or {}
    for field, column in CATEGORICAL_FIELDS.items():
        key = str(column)
        values = category_map.get(key)
        if values is None:
            values = sorted(encoded.iloc[:, column].dropna().unique().tolist())
            category_map[key] = values
        mapping = {value: index for index, value in enumerate(values)}
        encoded.iloc[:, column] = encoded.iloc[:, column].map(mapping).fillna(-1)
    return encoded.astype(float), category_map


def preprocess_raw_record(values: Mapping[str, Any], categories: dict[str, list[Any]]):
    missing = [name for name in FEATURE_NAMES if name not in values]
    if missing:
        raise ValueError(f'Missing feature fields: {", ".join(missing[:5])}')
    frame = pd.DataFrame([[values[name] for name in FEATURE_NAMES]], columns=FEATURE_NAMES)
    encoded, _ = encode_frame(frame, categories)
    result = encoded.to_numpy(dtype=float)
    if not np.isfinite(result).all():
        raise ValueError('Feature values must be finite numbers or known categorical values')
    return result


def validate_numeric_vector(values):
    result = np.asarray(values, dtype=float)
    if result.shape != (41,):
        raise ValueError('features must contain exactly 41 values')
    if not np.isfinite(result).all():
        raise ValueError('features must contain finite numbers')
    return result
