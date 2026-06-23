#!/bin/bash
set -e

apt-get update -y

apt-get install -y \
    zfsutils-linux \
    python3 \
    curl \
    build-essential

# install uv
su vagrant -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

# shellcheck disable=SC2016
echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/vagrant/.bashrc
