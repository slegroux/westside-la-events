#!/bin/bash
# Wrapper script to run tests without ROS/system interference

# Unset ROS-specific variables and PYTHONPATH
unset PYTHONPATH
unset AMENT_PREFIX_PATH
unset ROS_DISTRO
unset CMAKE_PREFIX_PATH

# Disable user site-packages to avoid conflicts with system packages
export PYTHONNOUSERSITE=1

# Run pytest within the la micromamba environment
exec micromamba run -n la python -m pytest "$@"
