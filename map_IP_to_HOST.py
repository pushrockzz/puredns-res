#!/usr/bin/env python3
import json
import sys
import ipaddress
from collections import defaultdict

def load_ip_map(sanicdns_file):
    """
    Parse sanicdns.json (newline-delimited JSON).
    Builds a mapping from IP -> list of hostnames for A, AAAA records.
    Also resolves CNAME chains to their final IP addresses.
    """
    ip_map = defaultdict(list)
    cname_map = {}  # hostname -> CNAME target
    
    # First pass: collect A, AAAA, and CNAME records
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
                continue

            for ans in answers:
                record_type = ans.get('type')
                data = ans.get('data')
                
                if not data:
                    continue
                
                # Process A and AAAA records (direct IP resolution)
                if record_type in ('A', 'AAAA'):
                    try:
                        ipaddress.ip_address(data)
                        ip_map[data].append(host)
                    except ValueError:
                        continue
                
                # Process CNAME records
                elif record_type == 'CNAME':
                    cname_target = data.rstrip('.')
                    cname_map[host] = cname_target
    
    # Second pass: resolve CNAME chains to IPs
    for cname_host, cname_target in cname_map.items():
        resolved_ips = resolve_cname_chain(cname_target, cname_map, ip_map)
        for ip in resolved_ips:
            if cname_host not in ip_map[ip]:  # Avoid duplicates
                ip_map[ip].append(cname_host)
    
    return ip_map

def resolve_cname_chain(target, cname_map, ip_map, visited=None, max_depth=10):
    """
    Recursively resolve a CNAME chain to find all IPs it points to.
    Returns a list of IP addresses.
    """
    if visited is None:
        visited = set()
    
    # Prevent infinite loops in CNAME chains
    if target in visited or len(visited) >= max_depth:
        return []
    
    visited.add(target)
    resolved_ips = []
    
    # Check if target directly resolves to an IP
    for ip, hosts in ip_map.items():
        if target in hosts:
            resolved_ips.append(ip)
    
    # If target is also a CNAME, follow the chain
    if target in cname_map:
        next_target = cname_map[target]
        resolved_ips.extend(resolve_cname_chain(next_target, cname_map, ip_map, visited, max_depth))
    
    return resolved_ips

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
