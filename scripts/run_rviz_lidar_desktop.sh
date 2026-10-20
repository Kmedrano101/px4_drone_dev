#!/usr/bin/env bash

source /opt/ros/jazzy/setup.bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROS_DOMAIN_ID=10
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://${repo_root}/ros2/cyclonedds-desktop.xml"
export ROS_LOCALHOST_ONLY=0

exec rviz2 -d "${repo_root}/ros2/slam_test.rviz"
