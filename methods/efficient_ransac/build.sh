#!/usr/bin/env bash
# Build the CGAL Efficient-RANSAC cylinder detector to bin/cgal_ransac.
# CGAL 5.x is header-only; we only link gmp/mpfr. Re-run if cgal_ransac.cpp changes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$SCRIPT_DIR/bin"
echo ">> compiling cgal_ransac (g++ -O2 -std=c++17)"
g++ -O2 -std=c++17 -DCGAL_NDEBUG \
    "$SCRIPT_DIR/cgal_ransac.cpp" \
    -lgmp -lmpfr \
    -o "$SCRIPT_DIR/bin/cgal_ransac"
echo ">> built $SCRIPT_DIR/bin/cgal_ransac"
