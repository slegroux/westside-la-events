#!/usr/bin/env python3
"""
Wrapper to run pytest with filtered sys.path to avoid ROS/system plugin conflicts.
"""
import sys
import os

# Filter out ROS paths from sys.path before pytest loads
filtered_path = [
    p for p in sys.path
    if '/opt/ros' not in p
]

sys.path = filtered_path

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Monkey-patch importlib.metadata to filter out problematic plugins
import importlib.metadata

_original_entry_points = importlib.metadata.entry_points

def filtered_entry_points(**kwargs):
    """Filter out problematic pytest plugins."""
    eps = _original_entry_points(**kwargs)

    blocked_plugins = {
        'dash',
        'rostest',
        'launch_testing',
        'launch_testing_ros',
        'launch_ros',
        'ament_xmllint',
        'ament_lint',
        'ament_pep257',
        'ament_flake8',
        'ament_copyright'
    }

    # Filter based on pytest version - Python 3.10+ uses select()
    if hasattr(eps, 'select'):
        # Create a wrapper that filters the results
        class FilteredEntryPoints:
            def __init__(self, original_eps, blocked):
                self._original = original_eps
                self._blocked = blocked

            def select(self, **kw):
                if kw.get('group') == 'pytest11':
                    result = self._original.select(**kw)
                    filtered_list = [ep for ep in result if ep.name not in self._blocked]
                    return FilteredEntryPoints._make_iterable(filtered_list)
                return self._original.select(**kw)

            @staticmethod
            def _make_iterable(items):
                class IterableWrapper:
                    def __init__(self, data):
                        self._data = data
                    def __iter__(self):
                        return iter(self._data)
                return IterableWrapper(items)

        return FilteredEntryPoints(eps, blocked_plugins)
    else:
        # Older API
        if 'group' in kwargs and kwargs['group'] == 'pytest11':
            return [ep for ep in eps if ep.name not in blocked_plugins]
        return eps

importlib.metadata.entry_points = filtered_entry_points

# Now import and run pytest
import pytest

if __name__ == '__main__':
    # Run pytest with arguments
    sys.exit(pytest.main(sys.argv[1:]))
