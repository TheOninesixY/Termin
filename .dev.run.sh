#!/usr/bin/env bash
set -euo pipefail

flatpak-builder --user --install --force-clean build-dir io.github.theoninesixy.Termin.yml
flatpak run io.github.theoninesixy.Termin