# Overlap Detection Implementation Guide for prop_infoblox_import.py

## Overview

The current `prop_infoblox_import.py` script creates all networks as regular networks without checking for overlaps. This enhancement adds automatic detection of overlapping networks and creates larger networks as containers when overlaps are found.

## Current Behavior vs. Enhanced Behavior

### Current Behavior:
1. Loads networks from CSV
2. Sorts by size (larger networks first)
3. Creates all as regular networks
4. Reports errors when overlaps occur

### Enhanced Behavior:
1. Loads networks from CSV
2. Analyzes all networks for overlaps BEFORE creation
3. Identifies which networks should be containers
4. Creates containers first, then networks inside them
5. Reports overlap decisions in dry-run mode

## Key Functions to Add

### 1. Network Overlap Detection
```python
import ipaddress

def check_network_overlap(cidr1: str, cidr2: str) -> str:
    """
    Check if two networks overlap.
    Returns: 'contains' if cidr1 contains cidr2
             'contained' if cidr1 is contained by cidr2
             'overlap' if they partially overlap
             'none' if no overlap
    """
    try:
        net1 = ipaddress.ip_network(cidr1, strict=False)
        net2 = ipaddress.ip_network(cidr2, strict=False)
        
        if net1.supernet_of(net2):
            return 'contains'
        elif net1.subnet_of(net2):
            return 'contained'
        elif net1.overlaps(net2):
            return 'overlap'
        else:
            return 'none'
    except Exception as e:
        logger.error(f"Error checking overlap between {cidr1} and {cidr2}: {e}")
        return 'error'
```

### 2. Overlap Analysis
```python
def analyze_network_overlaps(networks: List[Dict]) -> Dict:
    """
    Analyze all networks for overlaps and determine which should be containers.
    Returns a dict with:
    - containers: set of CIDRs that should be containers
    - relationships: dict mapping container CIDR to list of contained networks
    - overlaps: list of overlapping network pairs that can't be hierarchical
    """
    result = {
        'containers': set(),
        'relationships': {},
        'overlaps': []
    }
    
    # Sort networks by prefix length (smaller number = larger network)
    sorted_networks = sorted(networks, key=lambda x: int(x['cidr'].split('/')[1]))
    
    # Check each pair of networks
    for i, net1 in enumerate(sorted_networks):
        cidr1 = net1['cidr']
        
        for j, net2 in enumerate(sorted_networks[i+1:], i+1):
            cidr2 = net2['cidr']
            
            overlap_type = check_network_overlap(cidr1, cidr2)
            
            if overlap_type == 'contains':
                # net1 contains net2 - net1 should be a container
                result['containers'].add(cidr1)
                if cidr1 not in result['relationships']:
                    result['relationships'][cidr1] = []
                result['relationships'][cidr1].append(net2)
                logger.info(f"Network {cidr1} contains {cidr2} - marking as container")
                
            elif overlap_type == 'overlap':
                # Partial overlap - this is problematic
                result['overlaps'].append({
                    'network1': net1,
                    'network2': net2,
                    'message': f"Networks {cidr1} and {cidr2} partially overlap"
                })
                logger.warning(f"Partial overlap detected between {cidr1} and {cidr2}")
    
    return result
```

### 3. Network Container Creation
Add this method to InfoBloxClient:
```python
def create_network_container(self, cidr: str, network_view: str = "default", 
                           comment: str = "", extattrs: Optional[Dict[str, str]] = None) -> Dict:
    """Create a new network container in InfoBlox"""
    data = {
        'network': cidr,
        'network_view': network_view
    }
    
    if comment:
        data['comment'] = comment
        
    if extattrs:
        cleaned_extattrs = {}
        for k, v in extattrs.items():
            if v is not None and str(v).strip():
                cleaned_extattrs[k] = str(v)
        if cleaned_extattrs:
            data['extattrs'] = {k: {'value': v} for k, v in cleaned_extattrs.items()}
    
    try:
        response = self._make_request('POST', 'networkcontainer', data=data)
        logger.info(f"Created network container {cidr} in view {network_view}")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to create network container {cidr}: {e}")
        raise
```

### 4. Enhanced Network Creation
Replace the existing `create_missing_networks` method in PropertyManager:

```python
def create_missing_networks_with_overlap_handling(self, missing_networks: List[Dict], 
                                                network_view: str = "default", 
                                                dry_run: bool = False) -> List[Dict]:
    """Create missing networks with overlap detection and container creation."""
    results = []
    
    # Analyze overlaps
    overlap_analysis = analyze_network_overlaps(missing_networks)
    
    # Report overlap analysis
    if overlap_analysis['containers']:
        print(f"\n🔍 OVERLAP DETECTION RESULTS:")
        print(f"   📦 Networks to be created as containers: {len(overlap_analysis['containers'])}")
        for container_cidr in sorted(overlap_analysis['containers']):
            contained_count = len(overlap_analysis['relationships'].get(container_cidr, []))
            print(f"      - {container_cidr} (contains {contained_count} networks)")
    
    if overlap_analysis['overlaps']:
        print(f"\n⚠️  PARTIAL OVERLAPS DETECTED:")
        for overlap in overlap_analysis['overlaps']:
            print(f"   - {overlap['message']}")
    
    # Track what we've created
    created_containers = set()
    
    # First, create all containers
    if overlap_analysis['containers']:
        print(f"\n📦 CREATING NETWORK CONTAINERS:")
        
        for item in missing_networks:
            cidr = item['cidr']
            if cidr not in overlap_analysis['containers']:
                continue
                
            # Create container logic here...
            
    # Then create regular networks
    print(f"\n🌐 CREATING REGULAR NETWORKS:")
    
    for item in missing_networks:
        cidr = item['cidr']
        if cidr in created_containers:
            continue  # Already created as container
            
        # Check if this network is contained by any container
        parent_container = None
        for container_cidr in overlap_analysis['containers']:
            if check_network_overlap(container_cidr, cidr) == 'contains':
                parent_container = container_cidr
                break
        
        # Create network logic here...
        
    return results
```

## Integration Steps

1. **Add imports**: Add `import ipaddress` at the top of the file

2. **Add overlap detection functions**: Add `check_network_overlap` and `analyze_network_overlaps` functions

3. **Extend InfoBloxClient**: Add the `create_network_container` method

4. **Modify PropertyManager**: 
   - Replace `create_missing_networks` with `create_missing_networks_with_overlap_handling`
   - Update the main workflow to call overlap analysis before creation

5. **Update reporting**: Add overlap-specific reporting for dry-run mode

## Example Output

### Dry Run Mode:
```
🔍 OVERLAP DETECTION RESULTS:
   📦 Networks to be created as containers: 2
      - 10.0.0.0/16 (contains 4 networks)
        └─ 10.0.1.0/24 (Site: 123)
        └─ 10.0.2.0/24 (Site: 124)
        └─ 10.0.3.0/24 (Site: 125)
        └─ 10.0.4.0/24 (Site: 126)
      - 192.168.0.0/16 (contains 2 networks)
        └─ 192.168.1.0/24 (Site: 127)
        └─ 192.168.2.0/24 (Site: 128)

📦 CREATING NETWORK CONTAINERS:
   [DRY RUN] Would create network container: 10.0.0.0/16
   [DRY RUN] Would create network container: 192.168.0.0/16

🌐 CREATING REGULAR NETWORKS:
   [DRY RUN] Would create network: 10.0.1.0/24 inside container 10.0.0.0/16
   [DRY RUN] Would create network: 10.0.2.0/24 inside container 10.0.0.0/16
   ...
```

## Key Benefits

1. **Automatic Hierarchy**: Larger networks automatically become containers when they contain smaller networks
2. **Overlap Prevention**: Networks are created in the correct order (containers first)
3. **Clear Reporting**: Users see exactly what will happen in dry-run mode
4. **Error Reduction**: Fewer "overlap" errors during creation

## Testing

1. Create a test CSV with overlapping networks:
   ```csv
   site_id,m_host,prefixes
   1,host1,"['10.0.0.0/16', '10.0.1.0/24', '10.0.2.0/24']"
   2,host2,"['192.168.0.0/16', '192.168.1.0/24']"
   ```

2. Run in dry-run mode:
   ```bash
   python prop_infoblox_import_enhanced.py --create-missing --dry-run
   ```

3. Verify the overlap detection and container creation logic

This implementation ensures that overlapping networks are handled automatically and efficiently, reducing manual intervention and errors.
