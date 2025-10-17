#!/usr/bin/env bash

# install-sanicdns.sh
# Resilient installer for sanicdns with AF_XDP support
# Usage: Ensure GITHUB_TOKEN is set in environment (GitHub Actions auto-populates it)

set -euo pipefail

# Function to check system requirements
check_requirements() {
    echo "\n==> Checking system requirements..."
    # Check OS
    os_type=$(uname)
    if [[ "$os_type" != "Linux" ]]; then
        echo "Error: sanicdns is only compatible with Linux systems, detected $os_type."
        exit 1
    fi

    # Check architecture
    arch=$(uname -m)
    if [[ "$arch" != "x86_64" ]]; then
        echo "Error: sanicdns requires x86_64 architecture, detected $arch."
        exit 1
    fi

    # Check kernel version >= 5.11
    kernel_version=$(uname -r | cut -d. -f1,2)
    kernel_major=$(echo $kernel_version | cut -d. -f1)
    kernel_minor=$(echo $kernel_version | cut -d. -f2)
    echo "Detected kernel version $kernel_version"
    if [ "$kernel_major" -lt 5 ] || { [ "$kernel_major" -eq 5 ] && [ "$kernel_minor" -lt 11 ]; }; then
        echo "Error: sanicdns requires kernel version 5.11 or higher."
        exit 1
    fi

    # Check number of logical cores
    cores=$(nproc)
    if [[ $cores -lt 2 ]]; then
        echo "Error: sanicdns requires at least 2 logical cores."
        exit 1
    fi
}

# Function to find and download the latest compatible release
find_and_download_release() {
    echo "\n==> Searching for the latest compatible sanicdns release..."
    local releases_url="https://api.github.com/repos/hadriansecurity/sanicdns/releases"
    local resp version url
    local max_attempts=5 retry=0

    while (( retry < max_attempts )); do
        (( retry++ ))
        echo "- Attempt $retry of $max_attempts"

        # Fetch with auth and JSON accept
        resp=$(curl -sS \
          -H "Accept: application/vnd.github+json" \
          -H "Authorization: token ${GITHUB_TOKEN}" \
          "$releases_url" || true)

        # Validate JSON
        if ! echo "$resp" | jq . > /dev/null 2>&1; then
            echo "⚠️  Response was not valid JSON (rate‑limit or network issue)."
        else
            # Extract first compatible tag
            version=$(echo "$resp" | jq -r '
              .[]
              | select(.assets[]? .name == "sanicdns_af_xdp.tar.gz")
              | .tag_name
            ' | head -n1)

            if [[ -n "$version" ]]; then
                url=$(echo "$resp" | jq -r \
                  ".[] | select(.tag_name == \"$version\") | .assets[] | select(.name==\"sanicdns_af_xdp.tar.gz\").browser_download_url"
                )
                break
            else
                echo "⚠️  No matching asset found in this release JSON."
            fi
        fi

        sleep $(( retry * 5 ))
    done

    if [[ -z "$url" ]]; then
        echo "Error: failed to locate sanicdns_af_xdp.tar.gz after $max_attempts attempts."
        return 1
    fi

    echo "Downloading sanicdns version $version from $url"
    if ! curl -sSL -o sanicdns_af_xdp.tar.gz "$url"; then
        echo "Error: download failed."
        return 1
    fi
    return 0
}

# Function to install sanicdns binary
install_sanicdns() {
    echo "\n==> Installing sanicdns..."
    tar xzf sanicdns_af_xdp.tar.gz
    sudo install sanicdns_af_xdp/sanicdns sanicdns_af_xdp/sanicdns_xdp.c.o /usr/local/bin/
    rm -rf sanicdns_af_xdp.tar.gz sanicdns_af_xdp
    echo "sanicdns binary installed to /usr/local/bin"
}

# Function to install dpdk-hugepages.py
install_dpdk_hugepages() {
    echo "\n==> Installing dpdk-hugepages.py..."
    curl -sSL https://raw.githubusercontent.com/DPDK/dpdk/main/usertools/dpdk-hugepages.py -o dpdk-hugepages.py
    sudo install dpdk-hugepages.py /usr/local/bin/
    rm dpdk-hugepages.py
    echo "dpdk-hugepages.py installed to /usr/local/bin"
}

# Main installer
install_all() {
    if find_and_download_release; then
        install_sanicdns
        install_dpdk_hugepages
        echo "\n==> sanicdns installation complete!"
    else
        echo "Installation failed after multiple attempts." >&2
        exit 1
    fi
}

# Entrypoint
check_requirements
install_all
