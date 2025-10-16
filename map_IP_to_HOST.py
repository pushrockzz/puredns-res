#!/usr/bin/env python3
import json
import sys
import ipaddress
from collections import defaultdict

def load_ip_map(sanicdns_file):
    """
    Parse sanicdns.json (newline-delimited JSON).
    Builds a mapping from IP -> list of hostnames, but only for A-records.
    """
    ip_map = defaultdict(list)
    with open(sanicdns_file, 'r') as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line or not line.startswith('{'):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print(f"[WARN] skipping invalid JSON on line {lineno}", file=sys.stderr)
                continue

            host = obj.get('name', '').rstrip('.')
            answers = obj.get('data', {}).get('answers', [])
            if not host or not answers:
                # no A-answers at all → skip
                continue

            for ans in answers:
                # only process A-records
                if ans.get('type') != 'A':
                    continue

                ip = ans.get('data')
                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    continue

                ip_map[ip].append(host)
    return ip_map

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <sanicdns.json> <smap.txt>", file=sys.stderr)
        sys.exit(1)

    dns_file = sys.argv[1]
    smap_file = sys.argv[2]
    ip_map = load_ip_map(dns_file)

    with open(smap_file, 'r') as f:
        for lineno, raw in enumerate(f, start=1):
            entry = raw.strip()
            if not entry:
                continue

            parts = entry.split(':', 1)
            if len(parts) == 1:
                ip_part, port = parts[0], None
            else:
                ip_part, port = parts

            try:
                ipaddress.ip_address(ip_part)
            except ValueError:
                print(f"[WARN] invalid IP on line {lineno}: '{ip_part}'", file=sys.stderr)
                continue

            hosts = ip_map.get(ip_part)
            if not hosts:
                print(f"[WARN] no subdomain for IP {ip_part} (line {lineno})", file=sys.stderr)
                continue

            for host in hosts:
                print(f"{host}:{port}" if port else host)

if __name__ == '__main__':
    main()
